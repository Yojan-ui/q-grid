"""One building's part of the v2 problem over a rolling horizon: the binary commitment layout (master) and
its continuous dispatch (subproblem) as an LP / ADMM QP.

Binaries (one per device per hour of the horizon, `block_slots` = 4):
  dg[b]    diesel generator on in hour b            (min up/down time 1 h is automatic at hourly resolution;
                                                     runs started before the decision slot are carried over)
  mode[b]  battery may charge (1) or discharge (0)
  pump[b]  borewell pump on for the whole hour
  flex[j,c] flexible job j starts at candidate slot c (one-hot per job, hourly-aligned candidates)
Continuous per 15-min slot: ch, dis, e (battery), pg (DG output), imp, exp (grid), snc, sc (shed non-critical /
critical, outage only), spl (spill, outage only), f[l] (tie-line flows), v[l] (virtual flows that move import
accounting along tie-lines), s (campus import per building after sharing), P (campus peak kVA, today/tomorrow).
Peak demand is decentralised: imp_i + sum_l sigma_l v_l = s_i on every slot and all s_i agree through
neighbour consensus, so s = campus import / n everywhere and P >= n s / pf. No building sees the whole campus.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import highspy
import numpy as np
import osqp
import scipy.sparse as sp

from ..model import DT, Campus
from .horizon import Window

INF = highspy.kHighsInf


@dataclass
class BState:
    """Physical state of a building at the decision slot."""
    e: float                         # battery energy kWh
    level: float                     # tank level m3
    dg_on: bool = False
    dg_run: int = 0                  # slots the DG has been on (if on) / off (if off)
    started: dict = field(default_factory=dict)   # job -> absolute day slot it started


@dataclass
class Layout:
    names: list                      # [(kind, ...)]
    fixed: dict                      # index -> 0/1
    onehot: list                     # [indices] per flex job
    D_on: np.ndarray                 # (H, ny) DG on per slot
    D_mode: np.ndarray               # (H, ny)
    D_pump: np.ndarray               # (H, ny) pump on per slot
    D_flex: np.ndarray               # (H, ny) kW flexible load per slot
    flex_fixed: np.ndarray           # (H,) kW of jobs already running / not decidable
    c: np.ndarray                    # (ny,) fixed costs in the master (DG no-load fuel, water terminal value)
    c0: float
    tank_A: np.ndarray | None        # (H, ny) level change from binaries; level_h = tank_b + tank_A y
    tank_b: np.ndarray | None
    tank_lo: float = 0.0
    tank_hi: float = 0.0

    @property
    def ny(self): return len(self.names)


def layout(campus: Campus, i: int, w: Window, st: BState, t0: int, block: int, min_off: int) -> Layout:
    """Binary layout for building i at decision slot t0 of the operated day."""
    b = campus.buildings[i]
    H = w.pv.shape[1]
    # blocks follow clock hours: block of horizon slot h = hour of day slot t0+h (the first block is the rest
    # of the current hour); binaries are named by that absolute hour so plans carry over between slots
    hour = (t0 + np.arange(H)) // block
    blk = hour - hour[0]
    NB = int(blk[-1]) + 1
    names, fixed, onehot = [], {}, []

    def add(nm):
        names.append(nm)
        return len(names) - 1

    h0 = int(hour[0])
    dg_idx = [add(("dg", h0 + k)) for k in range(NB)] if b.dg else []
    mode_idx = [add(("mode", h0 + k)) for k in range(NB)] if b.battery.present else []
    pump_idx = [add(("pump", h0 + k)) for k in range(NB)] if b.tank else []
    if b.dg:
        if st.dg_on and st.dg_run < b.dg.min_on_slots:
            fixed[dg_idx[0]] = 1
        if not st.dg_on and 0 < st.dg_run < min_off:
            fixed[dg_idx[0]] = 0
    flex_fixed = np.zeros(H)
    flex_cols = []
    for j in b.flex:
        if j.name in st.started:                       # running or done: fixed load
            s0 = st.started[j.name]
            for h in range(H):
                if s0 <= t0 + h < s0 + j.slots and w.today[h]:
                    flex_fixed[h] += j.kw
            continue
        lo, hi = max(j.earliest, t0), j.latest
        if hi < t0:                                    # cannot happen (safety forces the start), guard anyway
            lo = hi = t0
        cands = sorted({s for s in range(lo, hi + 1) if s % block == 0} | {lo}) if lo % block else \
            [s for s in range(lo, hi + 1) if s % block == 0]
        cands = [s for s in cands if s - t0 < H]
        grp = []
        for s in cands:
            k = add(("flex", j.name, s))
            grp.append(k)
            flex_cols.append((k, s - t0, j))
        onehot.append(grp)
    ny = len(names)
    D_on, D_mode, D_pump, D_flex = (np.zeros((H, ny)) for _ in range(4))
    for k, ix in enumerate(dg_idx):
        D_on[blk == k, ix] = 1.0
    for k, ix in enumerate(mode_idx):
        D_mode[blk == k, ix] = 1.0
    for k, ix in enumerate(pump_idx):
        D_pump[blk == k, ix] = 1.0
    for ix, rel, j in flex_cols:
        D_flex[rel:rel + j.slots, ix] = j.kw
    c = np.zeros(ny)
    if b.dg:                                           # no-load fuel while on, per slot
        c += D_on.sum(axis=0) * b.dg.fuel_a * b.dg.kw * DT * b.dg.price
    tank_A = tank_b = None
    lo_t = hi_t = 0.0
    c0 = 0.0
    if b.tank:
        tk = b.tank
        tank_A = np.cumsum(D_pump * tk.pump_m3, axis=0)              # level change after slot h
        tank_b = st.level - np.cumsum(w.water)
        wv = w.term_value * tk.pump_kw * DT / tk.pump_m3              # Rs per m3 kept (as model.water_value)
        c += -wv * tank_A[-1]
        c0 += -wv * (tank_b[-1] - st.level)
        lo_t, hi_t = tk.l_min, tk.l_max
    return Layout(names, fixed, onehot, D_on, D_mode, D_pump, D_flex, flex_fixed, c, c0, tank_A, tank_b, lo_t, hi_t)


class BuildingLP:
    """Continuous subproblem of one building for fixed binaries. Columns are laid out once per decision slot;
    binaries only change row bounds, ADMM only changes the linear costs of the coupling columns."""

    def __init__(self, campus: Campus, i: int, w: Window, st: BState, lay: Layout, demand: dict, p_sofar: float):
        b = campus.buildings[i]
        self.b, self.i, self.lay = b, i, lay
        H = w.pv.shape[1]
        self.H = H
        n = campus.n
        self.inc = campus.incident(i)                 # [(line, sigma)]
        L = len(self.inc)
        col = {}
        lb, ub, cost = [], [], []

        def cols(name, k, lo, hi, c):
            col[name] = np.arange(len(lb), len(lb) + k)
            lb.extend(np.broadcast_to(lo, k)); ub.extend(np.broadcast_to(hi, k)); cost.extend(np.broadcast_to(c, k))

        g = w.grid
        bat = b.battery
        if bat.present:
            cols("ch", H, 0.0, bat.kw, 1e-4)
            cols("dis", H, 0.0, bat.kw, 1e-4)
            c_e = np.zeros(H); c_e[-1] = -w.term_value
            cols("e", H, bat.e_min, bat.e_max, c_e)
        if b.dg:
            cols("pg", H, 0.0, b.dg.kw, b.dg.fuel_b * b.dg.price * DT)
        cols("imp", H, 0.0, np.where(g, INF, 0.0), w.pi * DT)
        cols("exp", H, 0.0, np.where(g, INF, 0.0), -w.pe * DT)
        cols("snc", H, 0.0, np.where(g, 0.0, INF), demand["voll_nc"] * DT)
        cols("sc", H, 0.0, np.where(g, 0.0, INF), demand["voll_c"] * DT)
        cols("spl", H, 0.0, np.where(g, 0.0, INF), 1e-3)
        # boxes on the accounting variables: the campus cannot import more than every building's largest
        # possible demand (load + flexible loads + pump + battery charging) at once
        vmax = demand["campus_max_kw"]
        self.peak = bool(demand.get("peak", True))
        for k, (l, _) in enumerate(self.inc):
            cols(f"f{k}", H, -campus.step_kw, campus.step_kw, 0.0)
            if self.peak:
                cols(f"v{k}", H, -vmax, vmax, 0.0)
        if self.peak:
            cols("s", H, 0.0, vmax / n, 0.0)
            rate = demand["rate_day"] / n
            cols("P", 2, [p_sofar, 0.0], max(p_sofar, vmax / demand["pf"]), rate)
        self.col, self.ncol = col, len(lb)
        self.lb, self.ub, self.cost0 = np.array(lb, float), np.array(ub, float), np.array(cost, float)
        if self.peak:
            self.coupled = np.concatenate([np.concatenate([col[f"f{k}"], col[f"v{k}"]]) for k in range(L)] +
                                          [col["s"], col["P"]]) if L else np.array([], int)
        else:
            self.coupled = np.concatenate([col[f"f{k}"] for k in range(L)]) if L else np.array([], int)

        rows, rlo, rhi = [], [], []          # (list of (col, val)), bounds
        R = []                               # y-dependence of the varying bound: rhs = r0 + R y
        ny = lay.ny
        self.rowtype = []                    # 'eq' or 'ub' (y-dependent side)

        def row(entries, lo, hi, Ry=None, kind=None):
            rows.append(entries); rlo.append(lo); rhi.append(hi)
            R.append(np.zeros(ny) if Ry is None else Ry)
            self.rowtype.append(kind)

        base = w.pv[i] - w.load[i] - lay.flex_fixed       # rhs of balance before flex / pump binaries
        pump_kw = b.tank.pump_kw if b.tank else 0.0
        self.r_bal = []
        for h in range(H):
            e = []
            if bat.present:
                e += [(col["ch"][h], 1.0), (col["dis"][h], -1.0)]
            if b.dg:
                e += [(col["pg"][h], -1.0)]
            e += [(col["imp"][h], -1.0), (col["exp"][h], 1.0), (col["snc"][h], -1.0), (col["sc"][h], -1.0),
                  (col["spl"][h], 1.0)]
            for k, (l, sg) in enumerate(self.inc):
                e.append((col[f"f{k}"][h], float(sg)))
            Ry = -lay.D_flex[h] - pump_kw * lay.D_pump[h]
            self.r_bal.append(len(rows))
            row(e, base[h], base[h], Ry, "eq")
        if bat.present:
            for h in range(H):
                row([(col["ch"][h], 1.0)], -INF, 0.0, bat.kw * lay.D_mode[h], "ub")
                row([(col["dis"][h], 1.0)], -INF, bat.kw, -bat.kw * lay.D_mode[h], "ub")
            for h in range(H):
                e = [(col["e"][h], 1.0), (col["ch"][h], -bat.eta_ch * DT), (col["dis"][h], DT / bat.eta_dis)]
                if h > 0:
                    e.append((col["e"][h - 1], -1.0))
                row(e, 0.0, 0.0, None, "eq")
            self.r_soc0 = len(rows) - H
        if b.dg:
            for h in range(H):
                row([(col["pg"][h], 1.0)], -INF, 0.0, b.dg.kw * lay.D_on[h], "ub")
                row([(col["pg"][h], -1.0)], -INF, 0.0, -b.dg.p_min * lay.D_on[h], "ub")
        noncrit0 = w.load[i] + lay.flex_fixed - w.crit[i]
        for h in range(H):
            if not g[h]:
                row([(col["snc"][h], 1.0)], -INF, max(noncrit0[h], 0.0), lay.D_flex[h] + pump_kw * lay.D_pump[h], "ub")
        for h in range(H if self.peak else 0):
            e = [(col["imp"][h], 1.0), (col["s"][h], -1.0)]
            for k, (l, sg) in enumerate(self.inc):
                e.append((col[f"v{k}"][h], float(sg)))
            row(e, 0.0, 0.0, None, "eq")
        pf = demand["pf"]
        for h in range(H if self.peak else 0):
            if g[h]:
                d = 0 if w.today[h] else 1
                row([(col["s"][h], n / pf), (col["P"][d], -1.0)], -INF, 0.0, None, "ub")
        self.nrow = len(rows)
        self.rlo0, self.rhi0 = np.array(rlo, float), np.array(rhi, float)
        if bat.present:                         # initial energy in the first SoC row
            self.rlo0[self.r_soc0] = self.rhi0[self.r_soc0] = st.e
        self.R = np.array(R)
        r_idx, c_idx, vals = [], [], []
        for r, ent in enumerate(rows):
            for c_, v_ in ent:
                r_idx.append(r); c_idx.append(c_); vals.append(v_)
        self.A = sp.csc_matrix((vals, (r_idx, c_idx)), shape=(self.nrow, self.ncol))
        self._lp = None
        self._qp = None
        self._qp_rho = None

    # ---- bounds for binaries y
    def row_bounds(self, y: np.ndarray):
        d = np.einsum("rj,j->r", self.R, y)
        lo, hi = self.rlo0.copy(), self.rhi0.copy()
        eq = np.array([t == "eq" for t in self.rowtype])
        ubr = ~eq
        lo[eq] += d[eq]; hi[eq] += d[eq]
        hi[ubr] += d[ubr]
        return lo, hi

    # ---- Lagrangian LP (coupling columns priced at lam): value and Benders cut gradient
    def _build_lp(self):
        h = highspy.Highs()
        h.setOptionValue("output_flag", False)
        lp = highspy.HighsLp()
        lp.num_col_, lp.num_row_ = self.ncol, self.nrow
        lp.col_cost_, lp.col_lower_, lp.col_upper_ = self.cost0, self.lb, self.ub
        lp.row_lower_, lp.row_upper_ = self.rlo0, self.rhi0
        lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
        lp.a_matrix_.start_, lp.a_matrix_.index_, lp.a_matrix_.value_ = self.A.indptr, self.A.indices, self.A.data
        lp.a_matrix_.num_col_, lp.a_matrix_.num_row_ = self.ncol, self.nrow
        h.passModel(lp)
        self._lp = h

    def lagrangian(self, y: np.ndarray, lam: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        """min c x + lam . x_coupled s.t. local constraints, for binaries y.
        Returns (value, d value / d y, x)."""
        if self._lp is None:
            self._build_lp()
        h = self._lp
        c = self.cost0.copy()
        c[self.coupled] += lam
        h.changeColsCost(self.ncol, np.arange(self.ncol, dtype=np.int32), c)
        lo, hi = self.row_bounds(y)
        h.changeRowsBounds(self.nrow, np.arange(self.nrow, dtype=np.int32), lo, hi)
        h.run()
        st = h.getModelStatus()
        if st != highspy.HighsModelStatus.kOptimal:      # numerical trouble from a warm basis: solve cold
            h.clearSolver()
            h.run()
            st = h.getModelStatus()
        if st != highspy.HighsModelStatus.kOptimal:
            h.setOptionValue("solver", "ipm")
            h.clearSolver()
            h.run()
            h.setOptionValue("solver", "choose")
            st = h.getModelStatus()
        if st != highspy.HighsModelStatus.kOptimal:
            raise RuntimeError(f"building LP {self.b.name}: {st}")
        sol = h.getSolution()
        x = np.array(sol.col_value)
        dual = np.array(sol.row_dual)
        val = float(h.getInfo().objective_function_value)
        # HiGHS row duals are d objective / d (active row bound); y moves the eq rows' both bounds and the
        # upper bound of 'ub' rows, so d value / d y = R^T dual
        return val, np.einsum("rj,r->j", self.R, dual), x

    # ---- ADMM step: min c x + sum (rho/2) || x_c - z + u ||^2 (per incidence)
    def admm_step(self, y: np.ndarray, rho: float, lin: np.ndarray, hess: np.ndarray, warm=None):
        """lin, hess: per coupled column, sum over its incidences of rho (u - z) and rho."""
        q = self.cost0.copy()
        q[self.coupled] += lin
        lo, hi = self.row_bounds(y)
        Aall = sp.vstack([self.A, sp.eye(self.ncol, format="csc")], format="csc")
        l_all = np.r_[lo, self.lb]
        u_all = np.r_[hi, self.ub]
        l_all = np.where(np.isinf(l_all), -1e30, l_all)
        u_all = np.where(np.isinf(u_all), 1e30, u_all)
        if self._qp is None or self._qp_rho != rho:
            d = np.full(self.ncol, 1e-6)             # tiny proximal weight keeps the QP strictly convex
            d[self.coupled] += hess
            P = sp.diags(d, format="csc")
            self._qp = osqp.OSQP()
            self._qp.setup(P, q, Aall, l_all, u_all, verbose=False, eps_abs=1e-3, eps_rel=1e-4, polish=False,
                           warm_starting=True, max_iter=20000, scaling=10)
            self._qp_rho = rho
        else:
            self._qp.update(q=q, l=l_all, u=u_all)
        if warm is not None:
            self._qp.warm_start(x=warm)
        r = self._qp.solve()
        x = np.array(r.x) if r.x is not None else None
        if r.info.status in ("solved", "solved inaccurate") and x is not None and np.isfinite(x).all():
            return x
        # inexact local solve (e.g. OSQP iteration limit): ADMM tolerates it; use the iterate if finite,
        # otherwise keep the previous local solution
        self.inexact = getattr(self, "inexact", 0) + 1
        if x is not None and np.isfinite(x).all():
            return np.clip(x, self.lb, self.ub)
        if warm is not None:
            return np.asarray(warm)
        raise RuntimeError(f"building QP {self.b.name}: {r.info.status}")

    def recover(self, y: np.ndarray, f_fixed: np.ndarray, imp_cap: np.ndarray) -> tuple[np.ndarray, float]:
        """Physically consistent plan after ADMM: cable flows fixed to the agreed values, import capped at the
        ADMM import (keeps the shaved peak); accounting variables free and unpriced. Returns (x, energy cost
        excluding the demand charge). Falls back to an uncapped import if the cap is infeasible."""
        h = highspy.Highs()
        h.setOptionValue("output_flag", False)
        lp = highspy.HighsLp()
        lp.num_col_, lp.num_row_ = self.ncol, self.nrow
        cost = self.cost0.copy()
        if self.peak:
            cost[self.col["P"]] = 0.0
        lb, ub = self.lb.copy(), self.ub.copy()
        fcols = np.concatenate([self.col[f"f{k}"] for k in range(len(self.inc))]) if self.inc else np.array([], int)
        lb[fcols] = ub[fcols] = f_fixed
        if self.peak:
            lb[self.col["P"]] = 0.0
            ub[self.col["P"]] = INF
            lb[self.col["s"]] = -INF; ub[self.col["s"]] = INF
            for k in range(len(self.inc)):
                lb[self.col[f"v{k}"]] = -INF; ub[self.col[f"v{k}"]] = INF
        lo, hi = self.row_bounds(y)
        lp.col_cost_, lp.col_lower_, lp.row_lower_, lp.row_upper_ = cost, lb, lo, hi
        lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
        lp.a_matrix_.start_, lp.a_matrix_.index_, lp.a_matrix_.value_ = self.A.indptr, self.A.indices, self.A.data
        lp.a_matrix_.num_col_, lp.a_matrix_.num_row_ = self.ncol, self.nrow
        for cap in (imp_cap, None):
            u2 = ub.copy()
            if cap is not None:
                u2[self.col["imp"]] = np.minimum(ub[self.col["imp"]], np.maximum(cap, 0.0) + 0.5)
            lp.col_upper_ = u2
            h.passModel(lp)
            h.run()
            if h.getModelStatus() == highspy.HighsModelStatus.kOptimal:
                sol = h.getSolution()
                x = np.array(sol.col_value)
                self.f_marginal = np.array(sol.col_dual)[fcols] if len(fcols) else np.array([])
                return x, float(np.dot(cost, x))
        raise RuntimeError(f"recovery LP {self.b.name}: {h.getModelStatus()}")

    def lp_cost(self, x: np.ndarray) -> float:
        return float(np.dot(self.cost0, x))

    def get(self, x, name):
        return x[self.col[name]] if name in self.col else np.zeros(self.H)


def campus_max_kw(campus: Campus, w: Window) -> float:
    """Largest import the campus could physically draw in the window (box for accounting variables)."""
    tot = 0.0
    for i, b in enumerate(campus.buildings):
        tot += float(w.load[i].max()) + sum(j.kw for j in b.flex) + (b.tank.pump_kw if b.tank else 0.0) + b.battery.kw
    return tot
