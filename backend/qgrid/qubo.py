"""Local per-building QUBO (see docs/qubo.md for the derivation).

Binary variables for building i at slot t, horizon H <= 4 slots (1 h):
  c_k, d_k      battery charge / discharge at rated power in slot k            (2H bits)
  p_l, n_l      tie-line flow on each free incident line: f_l = F (p_l - n_l)   (2 bits per line)
  s             start the pending flexible job now                              (0 or 1 bit)
At most 8 + 2*3 + 1 = 15 qubits.

Energy  E(x) = objective(x) + A_x * P_excl(x) + A_s * P_soc(x), all written as const + x^T M x.
  objective = sum_k dt*(alpha_k r_k + beta_k r_k^2)          grid cost surrogate (fitted, convex)
            + V_{t+H}(e_H) quadratic fit                      battery cost-to-go (local DP)
            + s*tail_cost + (1-s)*defer_cost                  flexible-load timing
            + sum_l rho/2 (f_l - v_l)^2                       ADMM consensus term, v_l = z_l - u_l
  P_excl    = sum_k c_k d_k + sum_l p_l n_l                   one action per slot / unique flow code
  P_soc     = sum_{k tight} ((e_k - e_now)/q)^2               soft push into SoC bounds
Feasibility (hard, checked exactly by evaluate/feasible_mask): exclusivity, encoding, and
SoC within [e_min, e_max] after every slot of the horizon.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from .model import DT, Battery


@dataclass
class FlexState:
    kw: float
    slots: int
    can_start: bool        # bit s exists
    must_start: bool       # start forced now (s fixed to 1, no bit)
    tail_cost: float = 0.0  # cost of the job's slots beyond the horizon if started now
    defer_cost: float = 0.0  # estimated cost if deferred (best later start)


@dataclass
class LocalProblem:
    t: int
    bat: Battery
    e_now: float
    r0: np.ndarray                     # (H,) kW: inflexible load + running flex - pv
    pi: np.ndarray                     # (H,) import price used in optimisation
    pe: np.ndarray                     # (H,) export price
    lines: list[tuple[int, int]]       # free incident lines (line idx, sign)
    F: float
    fixed_out: float = 0.0             # kW outflow on fixed/islanded lines (constant)
    v: dict[int, float] = field(default_factory=dict)   # ADMM targets per free line
    rho: float = 0.0
    ctg: tuple[float, float, float] = (0.0, 0.0, 0.0)    # V_{t+H}(e) ~ a2 e^2 + a1 e + a0
    flex: FlexState | None = None

    @property
    def H(self) -> int:
        return len(self.r0)

    @property
    def has_s(self) -> bool:
        return self.flex is not None and self.flex.can_start and not self.flex.must_start

    @property
    def n(self) -> int:
        return 2 * self.H + 2 * len(self.lines) + int(self.has_s)

    def var_names(self) -> list[str]:
        H = self.H
        names = [f"c{k}" for k in range(H)] + [f"d{k}" for k in range(H)]
        for l, _ in self.lines:
            names += [f"p{l}", f"n{l}"]
        if self.has_s:
            names.append("s")
        return names

    # index helpers
    def ic(self, k): return k
    def id(self, k): return self.H + k
    def ip(self, j): return 2 * self.H + 2 * j
    def in_(self, j): return 2 * self.H + 2 * j + 1
    def is_(self): return self.n - 1


@dataclass
class QUBO:
    const: float
    M: np.ndarray  # symmetric; E(x) = const + x^T M x (diagonal holds linear terms)

    def energy(self, X: np.ndarray) -> np.ndarray:
        X = np.atleast_2d(X).astype(float)
        return self.const + np.einsum("bi,ij,bj->b", X, self.M, X)

    def __add__(self, o: "QUBO") -> "QUBO":
        return QUBO(self.const + o.const, self.M + o.M)

    def scale(self, a: float) -> "QUBO":
        return QUBO(self.const * a, self.M * a)

    def to_ising(self):
        """x = (1 - z)/2 -> E = c + sum h_i z_i + sum_{i<j} J_ij z_i z_j (qubit i <-> bit i)."""
        M = (self.M + self.M.T) / 2
        n = len(M)
        off = M - np.diag(np.diag(M))
        c = self.const + np.trace(M) / 2 + off.sum() / 4
        h = -np.diag(M) / 2 - off.sum(axis=1) / 2
        J = np.triu(off * 0.5, 1)  # pair i<j: (M_ij + M_ji)/4 = M_ij/2
        return c, h, J


class _Builder:
    def __init__(self, n):
        self.const = 0.0
        self.M = np.zeros((n, n))

    def lin(self, a: np.ndarray, w: float = 1.0, c: float = 0.0):
        self.M[np.diag_indices_from(self.M)] += w * a
        self.const += w * c

    def sq(self, a: np.ndarray, c: float, w: float):
        """w * (c + a.x)^2 with x binary."""
        self.M += w * np.outer(a, a)
        self.M[np.diag_indices_from(self.M)] += w * 2 * c * a
        self.const += w * c * c

    def pair(self, i, j, w):
        self.M[i, j] += w / 2
        self.M[j, i] += w / 2

    def qubo(self) -> QUBO:
        return QUBO(self.const, (self.M + self.M.T) / 2)


def residual_affine(lp: LocalProblem, k: int) -> tuple[float, np.ndarray]:
    """r_k = c0 + a.x (kW)."""
    a = np.zeros(lp.n)
    P = lp.bat.kw
    a[lp.ic(k)] = P
    a[lp.id(k)] = -P
    for j, (l, sgn) in enumerate(lp.lines):
        a[lp.ip(j)] = sgn * lp.F
        a[lp.in_(j)] = -sgn * lp.F
    c0 = lp.r0[k] + lp.fixed_out
    if lp.flex is not None and k < lp.flex.slots:
        if lp.has_s:
            a[lp.is_()] = lp.flex.kw
        elif lp.flex.must_start:
            c0 += lp.flex.kw
    return c0, a


def energy_affine(lp: LocalProblem, k: int) -> tuple[float, np.ndarray]:
    """Battery energy after slot k (inclusive), with rated-power quanta."""
    a = np.zeros(lp.n)
    qc = lp.bat.eta_ch * lp.bat.kw * DT
    qd = lp.bat.kw * DT / lp.bat.eta_dis
    for j in range(k + 1):
        a[lp.ic(j)] = qc
        a[lp.id(j)] = -qd
    return lp.e_now, a


def fit_cost_surrogate(c0: float, a: np.ndarray, pi: float, pe: float) -> tuple[float, float, float]:
    """Fit gamma + alpha r + beta r^2 (beta >= 0) to the exact tariff cost over reachable residuals."""
    vals = {0.0}
    for ai in a[a != 0]:
        vals = vals | {v + ai for v in vals}
    r = c0 + np.array(sorted(vals))
    cost = pi * np.maximum(r, 0) - pe * np.maximum(-r, 0)
    if np.ptp(r) < 1e-9:
        return float(cost[0]), 0.0, 0.0
    beta, alpha, gamma = np.polyfit(r, cost, 2)
    if beta < 0:
        alpha, gamma = np.polyfit(r, cost, 1)
        beta = 0.0
    return float(gamma), float(alpha), float(beta)


def build(lp: LocalProblem) -> tuple[QUBO, QUBO, QUBO]:
    """Return (objective, exclusivity penalty, SoC penalty) QUBOs."""
    n = lp.n
    ob = _Builder(n)
    for k in range(lp.H):
        c0, a = residual_affine(lp, k)
        gamma, alpha, beta = fit_cost_surrogate(c0, a, lp.pi[k], lp.pe[k])
        # dt * (gamma + alpha*r + beta*r^2), r = c0 + a.x
        ob.const += DT * (gamma + alpha * c0)
        ob.lin(a, DT * alpha)
        ob.sq(a, c0, DT * beta)
    e0, ae = energy_affine(lp, lp.H - 1)
    a2, a1, a0 = lp.ctg
    ob.sq(ae, e0, a2)
    ob.lin(ae, a1, e0)
    ob.const += a0
    if lp.flex is not None:
        if lp.has_s:
            s = np.zeros(n); s[lp.is_()] = 1
            ob.lin(s, lp.flex.tail_cost - lp.flex.defer_cost)
            ob.const += lp.flex.defer_cost
        elif lp.flex.must_start:
            ob.const += lp.flex.tail_cost
    for j, (l, _) in enumerate(lp.lines):
        if lp.rho > 0:
            a = np.zeros(n); a[lp.ip(j)] = lp.F; a[lp.in_(j)] = -lp.F
            ob.sq(a, -lp.v.get(l, 0.0), lp.rho / 2)

    px = _Builder(n)
    for k in range(lp.H):
        px.pair(lp.ic(k), lp.id(k), 1.0)
    for j in range(len(lp.lines)):
        px.pair(lp.ip(j), lp.in_(j), 1.0)

    ps = _Builder(n)
    qd = lp.bat.kw * DT
    for k in range(lp.H):
        e0k, ak = energy_affine(lp, k)
        hi, lo = e0k + ak[ak > 0].sum(), e0k + ak[ak < 0].sum()
        if hi > lp.bat.e_max + 1e-9 or lo < lp.bat.e_min - 1e-9:
            ps.sq(ak / qd, 0.0, 1.0)
    return ob.qubo(), px.qubo(), ps.qubo()


# ----------------------------------------------------------------------------- evaluation
@lru_cache(maxsize=32)
def all_bitstrings(n: int) -> np.ndarray:
    """(2^n, n) matrix; row z has bit i = (z >> i) & 1 (Qiskit little-endian ordering)."""
    z = np.arange(2 ** n, dtype=np.int64)
    X = ((z[:, None] >> np.arange(n)[None, :]) & 1).astype(np.float64)
    X.setflags(write=False)
    return X


def feasible_mask(lp: LocalProblem, X: np.ndarray) -> np.ndarray:
    X = np.atleast_2d(X).astype(np.float64)
    ok = np.ones(len(X), dtype=bool)
    H = lp.H
    for k in range(H):
        ok &= ~((X[:, lp.ic(k)] == 1) & (X[:, lp.id(k)] == 1))
    for j in range(len(lp.lines)):
        ok &= ~((X[:, lp.ip(j)] == 1) & (X[:, lp.in_(j)] == 1))
    for k in range(H):
        e0k, ak = energy_affine(lp, k)
        e = e0k + np.einsum("bi,i->b", X, ak)
        ok &= (e >= lp.bat.e_min - 1e-6) & (e <= lp.bat.e_max + 1e-6)
    return ok


def decode(lp: LocalProblem, x: np.ndarray) -> dict:
    x = np.asarray(x).astype(int)
    H = lp.H
    c = x[:H]
    d = x[H:2 * H]
    flows = {l: lp.F * (x[lp.ip(j)] - x[lp.in_(j)]) for j, (l, _) in enumerate(lp.lines)}
    start = bool(x[lp.is_()]) if lp.has_s else bool(lp.flex and lp.flex.must_start)
    mode = int(c[0]) - int(d[0])  # +1 charge, -1 discharge, 0 idle (slot 0 is applied)
    return {"c": c, "d": d, "flows": flows, "start": start, "mode0": mode}


def evaluate(lp: LocalProblem, x: np.ndarray, qubos=None) -> dict:
    """Objective, penalties, feasibility and exact (piecewise) horizon grid cost of one bitstring."""
    ob, px, ps = qubos or build(lp)
    x = np.asarray(x).astype(float)
    r = np.array([residual_affine(lp, k)[0] + residual_affine(lp, k)[1] @ x for k in range(lp.H)])
    exact_grid = float(((lp.pi * np.maximum(r, 0) - lp.pe * np.maximum(-r, 0)) * DT).sum())
    return {
        "objective": float(ob.energy(x)[0]),
        "pen_excl": float(px.energy(x)[0]),
        "pen_soc": float(ps.energy(x)[0]),
        "feasible": bool(feasible_mask(lp, x)[0]),
        "residual_kw": r,
        "exact_grid_cost": exact_grid,
        **decode(lp, x),
    }


def coeff_scale(q: QUBO) -> float:
    """Upper bound on the objective's range: sum of absolute coefficients."""
    M = q.M
    return float(np.abs(np.diag(M)).sum() + np.abs(M - np.diag(np.diag(M))).sum()) + 1e-9


def auto_tune(lp: LocalProblem, qubos=None, max_doublings: int = 12):
    """Penalty auto-tuning: A_x = coefficient bound of the objective (a violated exclusivity costs
    more than any objective gain); A_s doubled from 5 % of that bound until the ground state of the
    full QUBO is feasible (checked exhaustively). Returns (total QUBO, A_x, A_s, ground-state index)."""
    ob, px, ps = qubos or build(lp)
    X = all_bitstrings(lp.n)
    feas = feasible_mask(lp, X)
    S = coeff_scale(ob)
    A_x = S
    e_ob, e_px, e_ps = ob.energy(X), px.energy(X), ps.energy(X)
    A_s = 0.0
    for _ in range(max_doublings + 1):
        tot = e_ob + A_x * e_px + A_s * e_ps
        g = int(np.argmin(tot))
        if feas[g]:
            break
        A_s = 0.05 * S if A_s == 0 else 2 * A_s
    total = ob + px.scale(A_x) + ps.scale(A_s)
    return total, A_x, A_s, g
