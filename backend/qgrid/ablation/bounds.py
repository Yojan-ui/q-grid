"""Certified lower bounds on the day's optimum (perfect information, 15-min binaries), per day.

All bounds are on the same objective that model.settle() reports as objective_rs (energy + fuel + VOLL + terminal),
so certified_gap = (our cost - LB) / LB is a proven upper bound on how far a schedule is from optimal.

  LB_lp   LP relaxation of the central MILP (integrality dropped)                       always valid
  LB_mip  HiGHS branch-and-bound dual bound of the central MILP                           always valid
  LB_lag  Lagrangian dual bound of the decomposition: tie-line equalities are priced with the multipliers of
          consensus ADMM run on the day's LP relaxation; each building then solves its own MILP at those
          prices. Valid for any prices whose two ends sum to zero (they do: scaled ADMM duals keep sum(u) = 0).
The central MILP here is assembled from the same building models the controllers use; its optimum is checked
against baselines/milp.py (B4).
"""
from __future__ import annotations

import highspy
import numpy as np
import scipy.sparse as sp

from ..model import DT, T, Campus
from .engine import ACfg, _lp_admm
from .local import LocalModel, LState


def _day_models(campus: Campus, yd, day: str, outage):
    oc = campus.cfg["outage_costs"]
    voll = (float(oc["voll_noncritical_rs_kwh"]), float(oc["voll_critical_rs_kwh"]))
    lam = float(campus.cfg["co2"]["lambda_rs_per_kg"])
    d0 = yd.day_start(day)
    w = yd.window(d0, 0, T, outage)
    models, const = [], 0.0
    for i, b in enumerate(campus.buildings):
        st = LState(e=b.battery.e0, level=b.tank.level0 if b.tank else 0.0)
        models.append(LocalModel(campus, i, w, st, 0, T, disc=False, disc_flows=False, term_slope=w.term_value,
                                 voll=voll, lam_co2=lam, quad_flows=False, time_limit=60.0, mip_gap=1e-4))
        # settle() values stored energy relative to the start: term_value * (e0 - e_end) (+ water); the models
        # carry -term_value * e_end, so add the constants back
        if b.battery.present:
            const += w.term_value * b.battery.e0
        if b.tank:
            const += w.term_value * b.tank.pump_kw * DT / b.tank.pump_m3 * b.tank.level0
    return models, const


def _central(campus, models, relax: bool, time_limit: float = 120.0, want_x: bool = False):
    offs = np.cumsum([0] + [m.ncol for m in models])
    A = sp.block_diag([m.A for m in models], format="lil")
    rows = []
    for l, (a, c) in enumerate(campus.lines):
        ka = [k for k, (ll, _) in enumerate(models[a].inc) if ll == l][0]
        kc = [k for k, (ll, _) in enumerate(models[c].inc) if ll == l][0]
        for p_, q_ in zip(offs[a] + models[a].fcols[ka], offs[c] + models[c].fcols[kc]):
            rows.append((p_, q_))
    E = sp.lil_matrix((len(rows), offs[-1]))
    for r, (p_, q_) in enumerate(rows):
        E[r, p_] = 1.0; E[r, q_] = -1.0
    A = sp.vstack([A.tocsc(), E.tocsc()], format="csc")
    h = highspy.Highs(); h.setOptionValue("output_flag", False)
    h.setOptionValue("time_limit", time_limit); h.setOptionValue("mip_rel_gap", 1e-4)
    lp = highspy.HighsLp(); lp.num_col_, lp.num_row_ = A.shape[1], A.shape[0]
    lp.col_cost_ = np.concatenate([m.cost0 for m in models])
    lp.col_lower_ = np.concatenate([m.lb0 for m in models]); lp.col_upper_ = np.concatenate([m.ub0 for m in models])
    lp.row_lower_ = np.concatenate([m.rlo for m in models] + [np.zeros(len(rows))])
    lp.row_upper_ = np.concatenate([m.rhi for m in models] + [np.zeros(len(rows))])
    lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_, lp.a_matrix_.index_, lp.a_matrix_.value_ = A.indptr, A.indices, A.data
    lp.a_matrix_.num_col_, lp.a_matrix_.num_row_ = A.shape[1], A.shape[0]
    if not relax:
        integ = np.concatenate([m.integ for m in models])
        lp.integrality_ = [highspy.HighsVarType.kInteger if t else highspy.HighsVarType.kContinuous for t in integ]
    h.passModel(lp); h.run()
    info = h.getInfo()
    if want_x:
        return {"x": np.array(h.getSolution().col_value), "obj": float(info.objective_function_value)}
    return {"obj": float(info.objective_function_value), "bound": float(info.mip_dual_bound) if not relax else float(info.objective_function_value),
            "status": str(h.getModelStatus()), "gap": float(getattr(info, "mip_gap", 0.0))}


def _central_solve(campus, models, time_limit: float = 10.0) -> list:
    """Central MILP over the given building models (cables tied); returns each building's solution vector."""
    offs = np.cumsum([0] + [m.ncol for m in models])
    r = _central(campus, models, relax=False, time_limit=time_limit, want_x=True)
    return [r["x"][offs[i]:offs[i + 1]] for i in range(len(models))]


def day_bounds(campus: Campus, yd, day: str, outage) -> dict:
    models, const = _day_models(campus, yd, day, outage)
    lpb = _central(campus, models, relax=True)
    mip = _central(campus, models, relax=False)
    # Lagrangian bound with decentralised ADMM prices from the LP relaxation (integers relaxed: pass LP solution)
    relaxed = []
    for m in models:
        mm = LocalModel.__new__(LocalModel); mm.__dict__.update(m.__dict__)
        mm.integ = np.zeros_like(m.integ); mm._h = None
        relaxed.append(mm)
    cfg = ACfg(True, True, True, False, rho_lp=0.1, lp_iter=600, tol=0.2)
    z, u, it, conv = _lp_admm(campus, relaxed, [np.zeros(m.ncol) for m in relaxed], cfg, None, None)
    lag = 0.0
    for i, m in enumerate(models):
        c = np.zeros(m.ncol)
        for k, (l, _) in enumerate(m.inc):
            c[m.fcols[k]] += cfg.rho_lp * u[(i, l)]
        m.time_limit = 60.0
        s = m.solve(c)
        lag += s["bound"] if np.isfinite(s["bound"]) else s["obj"]   # a building's own B&B bound keeps it valid
    out = {"opt_central": mip["obj"] + const, "LB_mip": mip["bound"] + const, "LB_lp": lpb["obj"] + const,
           "LB_lag": lag + const, "admm_iters_for_prices": it, "admm_converged_for_prices": conv,
           "central_status": mip["status"]}
    out["LB"] = max(out["LB_mip"], out["LB_lp"], out["LB_lag"])
    return out
