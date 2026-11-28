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
    from ..model import wear_rate
    wear = wear_rate(campus.cfg)
    d0 = yd.day_start(day)
    w = yd.window(d0, 0, T, outage)
    models, const = [], 0.0
    for i, b in enumerate(campus.buildings):
        st = LState(e=b.battery.e0, level=b.tank.level0 if b.tank else 0.0)
        models.append(LocalModel(campus, i, w, st, 0, T, disc=False, disc_flows=False, term_slope=w.term_value,
                                 voll=voll, lam_co2=lam, quad_flows=False, time_limit=60.0, mip_gap=1e-4, wear=wear))
        # settle() values stored energy relative to the start: term_value * (e0 - e_end) (+ water); the models
        # carry -term_value * e_end, so add the constants back
        if b.battery.present:
            const += w.term_value * b.battery.e0
        if b.tank:
            const += w.term_value * b.tank.pump_kw * DT / b.tank.pump_m3 * b.tank.level0
    return models, const


def _central(campus, models, relax: bool, time_limit: float = 120.0, want_x: bool = False, peak: dict | None = None):
    """peak: campus monthly-peak term {rate, pf, ref_kva, contract_kva, xs_rate} (qgrid/ablation/demand.py): extra columns
    P >= sum_i imp_i[h] / pf - ref (cost rate) and X >= sum_i imp_i[h] / pf - contract (cost xs_rate), after the buildings' columns."""
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
    cost = np.concatenate([m.cost0 for m in models])
    lo_c = np.concatenate([m.lb0 for m in models]); hi_c = np.concatenate([m.ub0 for m in models])
    r_lo = np.concatenate([m.rlo for m in models] + [np.zeros(len(rows))])
    r_hi = np.concatenate([m.rhi for m in models] + [np.zeros(len(rows))])
    integ = np.concatenate([m.integ for m in models])
    extra = _peak_block(models, offs, peak)
    if extra is not None:
        P, c_add, rlo_add, rhi_add = extra
        A = sp.hstack([A, sp.csc_matrix((A.shape[0], len(c_add)))], format="csc")
        A = sp.vstack([A, P], format="csc")
        cost = np.r_[cost, c_add]; lo_c = np.r_[lo_c, np.zeros(len(c_add))]; hi_c = np.r_[hi_c, np.full(len(c_add), highspy.kHighsInf)]
        r_lo = np.r_[r_lo, rlo_add]; r_hi = np.r_[r_hi, rhi_add]; integ = np.r_[integ, np.zeros(len(c_add), bool)]
    h = highspy.Highs(); h.setOptionValue("output_flag", False)
    h.setOptionValue("time_limit", time_limit); h.setOptionValue("mip_rel_gap", 1e-4)
    lp = highspy.HighsLp(); lp.num_col_, lp.num_row_ = A.shape[1], A.shape[0]
    lp.col_cost_, lp.col_lower_, lp.col_upper_ = cost, lo_c, hi_c
    lp.row_lower_, lp.row_upper_ = r_lo, r_hi
    lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_, lp.a_matrix_.index_, lp.a_matrix_.value_ = A.indptr, A.indices, A.data
    lp.a_matrix_.num_col_, lp.a_matrix_.num_row_ = A.shape[1], A.shape[0]
    if not relax:
        lp.integrality_ = [highspy.HighsVarType.kInteger if t else highspy.HighsVarType.kContinuous for t in integ]
    h.passModel(lp); h.run()
    info = h.getInfo()
    if want_x:
        return {"x": np.array(h.getSolution().col_value), "obj": float(info.objective_function_value)}
    return {"obj": float(info.objective_function_value), "bound": float(info.mip_dual_bound) if not relax else float(info.objective_function_value),
            "status": str(h.getModelStatus()), "gap": float(getattr(info, "mip_gap", 0.0))}


def _peak_block(models, offs, peak):
    """Rows / columns of the campus monthly-peak term (None when off)."""
    if not peak or peak.get("rate", 0) <= 0:
        return None
    H = models[0].H
    ncol = int(offs[-1])
    cols = [("rate", peak.get("ref_kva", 0.0) or 0.0, float(peak["rate"]))]
    if peak.get("contract_kva") and peak.get("xs_rate", 0) > 0:
        cols.append(("xs", float(peak["contract_kva"]), float(peak["xs_rate"])))
    P = sp.lil_matrix((H * len(cols), ncol + len(cols)))
    rhi = []
    for k, (_, lim, _) in enumerate(cols):
        for h in range(H):
            r = k * H + h
            for i, m in enumerate(models):
                P[r, offs[i] + m.col["imp"][h]] = 1.0 / peak["pf"]
            P[r, ncol + k] = -1.0
            rhi.append(lim)
    return P.tocsc(), np.array([c for *_, c in cols]), np.full(len(rhi), -highspy.kHighsInf), np.array(rhi)


def _central_solve(campus, models, time_limit: float = 10.0, peak: dict | None = None) -> list:
    """Central MILP over the given building models (cables tied); returns each building's solution vector."""
    offs = np.cumsum([0] + [m.ncol for m in models])
    r = _central(campus, models, relax=False, time_limit=time_limit, want_x=True, peak=peak)
    return [r["x"][offs[i]:offs[i + 1]] for i in range(len(models))]


def day_bounds(campus: Campus, yd, day: str, outage, demand: dict | None = None) -> dict:
    """demand: the monthly-peak term (demand.planner_params) -> opt_central / LB_mip / LB_lp include it. LB_lag stays on
    the energy objective alone, still a valid lower bound because the peak term is >= 0."""
    models, const = _day_models(campus, yd, day, outage)
    lpb = _central(campus, models, relax=True, peak=demand)
    mip = _central(campus, models, relax=False, peak=demand)
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
