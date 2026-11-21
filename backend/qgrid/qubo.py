"""Local per-zone QUBO (derivation: docs/qubo.md).

Binary variables for zone i at slot t, horizon H (default 3 slots):
  c_k, d_k   battery charge / discharge quantum in slot k              (2H bits, if the zone has a battery)
  g          diesel generator on for the horizon                       (1 bit, if DG present and not forced)
  w          borewell pump on for the horizon                          (1 bit, if tank present and not forced)
  s:<job>    start flexible job now                                    (1 bit per pending job in its window)
  p_l, n_l   tie-line flow f_l = F (p_l - n_l) on each free line       (2 bits per line)
A qubit budget (<= 16) is enforced by dropping the job bits with the latest deadlines.

E(x) = sum_groups objective_g(x) + A_x P_excl(x) + A_s P_soft(x), each as const + x^T M x.
Groups: grid (tariff / VOLL surrogate), battery_ctg, water_value, dg_fuel, flex_timing, admm, rule:<id>.
Hard feasibility (exact, checked by feasible_mask): one battery action per slot, unique flow code,
SoC and tank level within bounds over the horizon.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import warnings

import numpy as np

from .model import DT, Battery, slot_cost

MAX_QUBITS = 16


@dataclass
class FlexState:
    name: str
    kw: float
    slots: int
    can_start: bool = True
    must_start: bool = False
    tail_cost: float = 0.0
    defer_cost: float = 0.0
    now_cost: float | None = None
    deadline: int = 999


@dataclass
class DGState:
    q: np.ndarray            # (H,) output quantum when on (kW)
    fuel_cost: float         # Rs over the horizon if on at q (+ carbon shadow price)
    forced_on: bool = False  # min on-time
    allowed: bool = True     # rules may forbid


@dataclass
class TankState:
    level: float
    demand: np.ndarray       # (H,) m3 per slot
    pump_kw: float
    pump_m3: float
    l_min: float
    l_max: float
    value_per_m3: float
    forced: int | None = None    # None free, 0 forced off, 1 forced on
    target: float | None = None  # operator rule: level >= target (soft, weighted)
    target_weight: float = 0.0


@dataclass
class LocalProblem:
    t: int
    bat: Battery
    e_now: float
    r0: np.ndarray
    pi: np.ndarray
    pe: np.ndarray
    lines: list[tuple[int, int]]
    F: float
    fixed_out: float = 0.0
    v: dict[int, float] = field(default_factory=dict)
    rho: float = 0.0
    ctg: tuple[float, float, float] = (0.0, 0.0, 0.0)
    jobs: list[FlexState] = field(default_factory=list)
    dg: DGState | None = None
    tank: TankState | None = None
    grid: np.ndarray | None = None
    noncrit: np.ndarray | None = None
    voll_nc: float = 0.0
    voll_c: float = 0.0
    pc: np.ndarray | None = None
    pd: np.ndarray | None = None
    rule_terms: list[dict] = field(default_factory=list)   # {"id", "var", "coef"} linear penalties

    def __post_init__(self):
        H = len(self.r0)
        if self.pc is None:
            self.pc = np.full(H, self.bat.kw)
        if self.pd is None:
            self.pd = np.full(H, self.bat.kw)
        if self.grid is None:
            self.grid = np.ones(H, bool)
        if self.noncrit is None:
            self.noncrit = np.zeros(H)
        names = []
        if self.bat.present:
            names += [f"c{k}" for k in range(H)] + [f"d{k}" for k in range(H)]
        for l, _ in self.lines:
            names += [f"p{l}", f"n{l}"]
        if self.dg is not None and not self.dg.forced_on and self.dg.allowed:
            names.append("g")
        if self.tank is not None and self.tank.forced is None:
            names.append("w")
        cand = sorted([j for j in self.jobs if j.can_start and not j.must_start], key=lambda j: j.deadline)
        self.job_bits = []
        for j in cand:
            if len(names) < MAX_QUBITS:
                names.append(f"s:{j.name}")
                self.job_bits.append(j.name)
        self.names = names
        self.idx = {n: k for k, n in enumerate(names)}

    @property
    def H(self) -> int: return len(self.r0)
    @property
    def n(self) -> int: return len(self.names)
    def var_names(self) -> list[str]: return list(self.names)
    def has(self, v: str) -> bool: return v in self.idx

    def unit(self, v: str, w: float = 1.0) -> np.ndarray:
        a = np.zeros(self.n)
        if v in self.idx:
            a[self.idx[v]] = w
        return a

    def dg_on_const(self) -> bool:
        return self.dg is not None and self.dg.forced_on

    def pump_const(self) -> int:
        return int(self.tank.forced) if self.tank is not None and self.tank.forced is not None else 0


@dataclass
class QUBO:
    const: float
    M: np.ndarray

    def energy(self, X: np.ndarray) -> np.ndarray:
        X = np.atleast_2d(X).astype(float)
        with np.errstate(all="ignore"):
            return self.const + ((X @ self.M) * X).sum(axis=1)

    def __add__(self, o: "QUBO") -> "QUBO":
        return QUBO(self.const + o.const, self.M + o.M)

    def scale(self, a: float) -> "QUBO":
        return QUBO(self.const * a, self.M * a)

    def to_ising(self):
        M = (self.M + self.M.T) / 2
        off = M - np.diag(np.diag(M))
        c = self.const + np.trace(M) / 2 + off.sum() / 4
        h = -np.diag(M) / 2 - off.sum(axis=1) / 2
        J = np.triu(off * 0.5, 1)
        return c, h, J


class _Builder:
    def __init__(self, n):
        self.const = 0.0
        self.M = np.zeros((n, n))

    def lin(self, a, w=1.0, c=0.0):
        self.M[np.diag_indices_from(self.M)] += w * a
        self.const += w * c

    def sq(self, a, c, w):
        self.M += w * np.outer(a, a)
        self.M[np.diag_indices_from(self.M)] += w * 2 * c * a
        self.const += w * c * c

    def pair(self, i, j, w):
        self.M[i, j] += w / 2
        self.M[j, i] += w / 2

    def qubo(self) -> QUBO:
        return QUBO(self.const, (self.M + self.M.T) / 2)


# ----------------------------------------------------------------------------- affine pieces
def residual_affine(lp: LocalProblem, k: int) -> tuple[float, np.ndarray]:
    a = np.zeros(lp.n)
    if lp.bat.present:
        a += lp.unit(f"c{k}", lp.pc[k]) + lp.unit(f"d{k}", -lp.pd[k])
    for l, sgn in lp.lines:
        a += lp.unit(f"p{l}", sgn * lp.F) + lp.unit(f"n{l}", -sgn * lp.F)
    c0 = lp.r0[k] + lp.fixed_out
    for j in lp.jobs:
        if k < j.slots:
            if j.name in lp.job_bits:
                a += lp.unit(f"s:{j.name}", j.kw)
            elif j.must_start:
                c0 += j.kw
    if lp.tank is not None:
        if lp.has("w"):
            a += lp.unit("w", lp.tank.pump_kw)
        else:
            c0 += lp.pump_const() * lp.tank.pump_kw
    if lp.dg is not None:
        if lp.has("g"):
            a += lp.unit("g", -lp.dg.q[k])
        elif lp.dg_on_const():
            c0 -= lp.dg.q[k]
    return c0, a


def energy_affine(lp: LocalProblem, k: int) -> tuple[float, np.ndarray]:
    a = np.zeros(lp.n)
    if lp.bat.present:
        for j in range(k + 1):
            a += lp.unit(f"c{j}", lp.bat.eta_ch * lp.pc[j] * DT) + lp.unit(f"d{j}", -lp.pd[j] * DT / lp.bat.eta_dis)
    return lp.e_now, a


def tank_affine(lp: LocalProblem, k: int) -> tuple[float, np.ndarray]:
    tk = lp.tank
    c0 = tk.level - float(tk.demand[:k + 1].sum())
    if lp.has("w"):
        return c0, lp.unit("w", tk.pump_m3 * (k + 1))
    return c0 + lp.pump_const() * tk.pump_m3 * (k + 1), np.zeros(lp.n)


def _reachable(c0: float, a: np.ndarray, cap: int = 4096) -> np.ndarray:
    vals = {0.0}
    for ai in a[np.abs(a) > 1e-12]:
        vals = vals | {round(v + ai, 3) for v in vals}
        if len(vals) > cap:
            vals = set(np.round(np.linspace(min(vals), max(vals), cap), 3))
    return c0 + np.array(sorted(vals))


def crit_active(lp: LocalProblem, k: int) -> bool:
    """Islanded slot where some bitstring can serve all critical load (deficit <= non-critical load)."""
    if lp.grid[k]:
        return False
    c0, a = residual_affine(lp, k)
    return c0 + a[a < 0].sum() <= lp.noncrit[k] + 1e-6


def fit_cost_surrogate(c0, a, pi, pe, grid=True, noncrit=0.0, voll_nc=0.0, voll_c=0.0, rmax=None):
    """Fit gamma + alpha r + beta r^2 (beta >= 0) to the exact slot cost / DT over reachable residuals
    (restricted to r <= rmax when the critical-load constraint is active)."""
    r = _reachable(c0, a)
    if rmax is not None and (r <= rmax + 1e-6).any():
        r = r[r <= rmax + 1e-6]
    cost = slot_cost(r, pi, pe, grid, noncrit, voll_nc, voll_c) / DT
    if np.ptp(r) < 1e-9:
        return float(cost[0]), 0.0, 0.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        beta, alpha, gamma = np.polyfit(r, cost, 2)
    if beta < 0:
        alpha, gamma = np.polyfit(r, cost, 1)
        beta = 0.0
    return float(gamma), float(alpha), float(beta)


# ----------------------------------------------------------------------------- build
def build_groups(lp: LocalProblem) -> tuple[dict[str, QUBO], QUBO, QUBO]:
    n = lp.n
    G: dict[str, _Builder] = {}

    def g(name):
        if name not in G:
            G[name] = _Builder(n)
        return G[name]

    for k in range(lp.H):
        c0, a = residual_affine(lp, k)
        gam, al, be = fit_cost_surrogate(c0, a, lp.pi[k], lp.pe[k], bool(lp.grid[k]), lp.noncrit[k], lp.voll_nc,
                                         lp.voll_c, rmax=lp.noncrit[k] if crit_active(lp, k) else None)
        b = g("grid")
        b.const += DT * (gam + al * c0)
        b.lin(a, DT * al)
        b.sq(a, c0, DT * be)
    if lp.bat.present:
        e0, ae = energy_affine(lp, lp.H - 1)
        a2, a1, a0 = lp.ctg
        b = g("battery_ctg")
        b.sq(ae, e0, a2)
        b.lin(ae, a1, e0)
        b.const += a0
    if lp.tank is not None:
        c0, at = tank_affine(lp, lp.H - 1)
        g("water_value").lin(at, -lp.tank.value_per_m3, c0)
        if lp.tank.target is not None and lp.tank.target_weight > 0 and c0 < lp.tank.target:
            m = max(lp.tank.pump_m3, 1e-9)
            g("rule:tank_target").sq(-at / m, (lp.tank.target - c0) / m, lp.tank.target_weight)
    if lp.dg is not None:
        b = g("dg_fuel")
        if lp.has("g"):
            b.lin(lp.unit("g"), lp.dg.fuel_cost)
        elif lp.dg_on_const():
            b.const += lp.dg.fuel_cost
    b = g("flex_timing")
    for j in lp.jobs:
        if j.name in lp.job_bits:
            b.lin(lp.unit(f"s:{j.name}"), j.tail_cost - j.defer_cost)
            b.const += j.defer_cost
        elif j.must_start:
            b.const += j.tail_cost
    if lp.rho > 0:
        b = g("admm")
        for l, _ in lp.lines:
            a = lp.unit(f"p{l}", lp.F) + lp.unit(f"n{l}", -lp.F)
            b.sq(a, -lp.v.get(l, 0.0), lp.rho / 2)
    for rt in lp.rule_terms:
        if lp.has(rt["var"]):
            g(f"rule:{rt['id']}").lin(lp.unit(rt["var"]), rt["coef"])
    groups = {k: v.qubo() for k, v in G.items()}
    # calibrate each job bit's own cost to its battery-aware marginal-price cost (couplings kept)
    for j in lp.jobs:
        if j.name in lp.job_bits and j.now_cost is not None:
            i = lp.idx[f"s:{j.name}"]
            groups["flex_timing"].M[i, i] += j.now_cost - groups["grid"].M[i, i]

    px = _Builder(n)
    if lp.bat.present:
        for k in range(lp.H):
            px.pair(lp.idx[f"c{k}"], lp.idx[f"d{k}"], 1.0)
    for l, _ in lp.lines:
        px.pair(lp.idx[f"p{l}"], lp.idx[f"n{l}"], 1.0)
    ps = _Builder(n)
    if lp.bat.present:
        q = max(lp.bat.kw * DT, 1e-9)
        for k in range(lp.H):
            e0k, ak = energy_affine(lp, k)
            hi, lo = e0k + ak[ak > 0].sum(), e0k + ak[ak < 0].sum()
            if hi > lp.bat.e_max + 1e-9 or lo < lp.bat.e_min - 1e-9:
                ps.sq(ak / q, 0.0, 1.0)
    for k in range(lp.H):
        if crit_active(lp, k):
            c0, a = residual_affine(lp, k)
            sc = max(lp.F, 1.0)
            ps.sq(a / sc, (c0 - lp.noncrit[k]) / sc, 1.0)
    if lp.tank is not None and lp.has("w"):
        for k in range(lp.H):
            c0, at = tank_affine(lp, k)
            if c0 < lp.tank.l_min:
                ps.lin(lp.unit("w"), -1.0)
            if c0 + at.sum() > lp.tank.l_max:
                ps.lin(lp.unit("w"), 1.0)
    return groups, px.qubo(), ps.qubo()


def build(lp: LocalProblem) -> tuple[QUBO, QUBO, QUBO]:
    groups, px, ps = build_groups(lp)
    ob = QUBO(0.0, np.zeros((lp.n, lp.n)))
    for q in groups.values():
        ob = ob + q
    return ob, px, ps


# ----------------------------------------------------------------------------- evaluation
@lru_cache(maxsize=32)
def all_bitstrings(n: int) -> np.ndarray:
    z = np.arange(2 ** n, dtype=np.int64)
    X = ((z[:, None] >> np.arange(n)[None, :]) & 1).astype(np.float64)
    X.setflags(write=False)
    return X


def feasible_mask(lp: LocalProblem, X: np.ndarray) -> np.ndarray:
    X = np.atleast_2d(X).astype(np.float64)
    ok = np.ones(len(X), dtype=bool)
    if lp.bat.present:
        for k in range(lp.H):
            ok &= ~((X[:, lp.idx[f"c{k}"]] == 1) & (X[:, lp.idx[f"d{k}"]] == 1))
    for l, _ in lp.lines:
        ok &= ~((X[:, lp.idx[f"p{l}"]] == 1) & (X[:, lp.idx[f"n{l}"]] == 1))
    with np.errstate(all="ignore"):
        if lp.bat.present:
            for k in range(lp.H):
                e0k, ak = energy_affine(lp, k)
                e = e0k + X @ ak
                ok &= (e >= lp.bat.e_min - 1e-6) & (e <= lp.bat.e_max + 1e-6)
        if lp.tank is not None:
            for k in range(lp.H):
                c0, at = tank_affine(lp, k)
                lv = c0 + X @ at
                lo_ok = (lv >= lp.tank.l_min - 1e-6) | (c0 + at.sum() < lp.tank.l_min)
                hi_ok = (lv <= lp.tank.l_max + 1e-6) | (c0 > lp.tank.l_max)
                ok &= lo_ok & hi_ok
        for k in range(lp.H):
            if crit_active(lp, k):
                c0, a = residual_affine(lp, k)
                ok &= (c0 + X @ a) <= lp.noncrit[k] + 1e-6
    return ok


def decode(lp: LocalProblem, x: np.ndarray) -> dict:
    x = np.asarray(x).astype(int)
    get = lambda v: int(x[lp.idx[v]]) if v in lp.idx else 0  # noqa: E731
    flows = {l: lp.F * (get(f"p{l}") - get(f"n{l}")) for l, _ in lp.lines}
    starts = {j.name: (bool(get(f"s:{j.name}")) if j.name in lp.job_bits else bool(j.must_start)) for j in lp.jobs}
    mode = get("c0") - get("d0") if lp.bat.present else 0
    dg_on = bool(get("g")) if lp.has("g") else lp.dg_on_const()
    pump = bool(get("w")) if lp.has("w") else bool(lp.pump_const())
    return {"flows": flows, "starts": starts, "start": any(starts.values()), "mode0": mode, "dg_on": dg_on,
            "pump_on": pump}


def evaluate(lp: LocalProblem, x: np.ndarray, qubos=None) -> dict:
    ob, px, ps = qubos or build(lp)
    x = np.asarray(x).astype(float)
    r = np.array([residual_affine(lp, k)[0] + residual_affine(lp, k)[1] @ x for k in range(lp.H)])
    exact = float(sum(slot_cost(r[k], lp.pi[k], lp.pe[k], bool(lp.grid[k]), lp.noncrit[k], lp.voll_nc, lp.voll_c)
                      for k in range(lp.H)))
    return {"objective": float(ob.energy(x)[0]), "pen_excl": float(px.energy(x)[0]), "pen_soc": float(ps.energy(x)[0]),
            "feasible": bool(feasible_mask(lp, x)[0]), "residual_kw": r, "exact_grid_cost": exact, **decode(lp, x)}


def coeff_scale(q: QUBO) -> float:
    M = q.M
    return float(np.abs(np.diag(M)).sum() + np.abs(M - np.diag(np.diag(M))).sum()) + 1e-9


def enumerate_all(lp: LocalProblem, qubos=None) -> dict:
    ob, px, ps = qubos or build(lp)
    X = all_bitstrings(lp.n)
    return {"X": X, "ob": ob.energy(X), "px": px.energy(X), "ps": ps.energy(X), "feas": feasible_mask(lp, X)}


def auto_tune(lp: LocalProblem, qubos=None, max_doublings: int = 12, enum: dict | None = None):
    """A_x = coefficient bound of the objective; A_s doubled from 5 % of it until the exhaustive ground
    state of the full QUBO is feasible. Returns (total QUBO, A_x, A_s, ground-state index)."""
    qubos = qubos or build(lp)
    ob, px, ps = qubos
    en = enum or enumerate_all(lp, qubos)
    S = coeff_scale(ob)
    A_x, A_s, g = S, 0.0, 0
    for _ in range(max_doublings + 1):
        tot = en["ob"] + A_x * en["px"] + A_s * en["ps"]
        g = int(np.argmin(tot))
        if en["feas"][g]:
            break
        A_s = 0.05 * S if A_s == 0 else 2 * A_s
    en["total"] = en["ob"] + A_x * en["px"] + A_s * en["ps"]
    return ob + px.scale(A_x) + ps.scale(A_s), A_x, A_s, g


def penalty_tune_heuristic(qubos):
    """For instances too large to enumerate (centralised QIEA): A_x = coefficient bound, A_s = 0.5 * bound."""
    ob, px, ps = qubos
    S = coeff_scale(ob)
    return ob + px.scale(S) + ps.scale(0.5 * S), S, 0.5 * S
