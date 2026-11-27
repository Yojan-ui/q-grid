"""Consensus ADMM on the continuous subproblem (convex): each building solves its own QP; neighbours exchange
only their copies of the shared quantities of the cable between them:
  f_l  flow on cable l              v_l  virtual import-accounting flow on cable l
  s    campus import share          P    campus peak kVA (today, tomorrow)
For a convex problem ADMM converges (Boyd et al., Foundations and Trends in ML, 2011). Residual balancing
adapts rho. At the end every building also solves its Lagrangian LP with the consensus prices, which gives
a valid Benders optimality cut for its own binaries (see benders.py).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..model import Campus
from .building import BuildingLP


@dataclass
class AdmmResult:
    x: list                  # per building primal (columns of BuildingLP)
    z: dict                  # line -> consensus vector [f, v, s, P]
    u: dict                  # (building, line) -> scaled dual
    rho: float
    iters: int
    converged: bool
    r_hist: list
    s_hist: list
    lp_cost: float           # sum of building LP costs at the final iterate


def _edge_slices(H: int, L: int, k: int, peak: bool = True):
    """Positions of an edge copy [f_k, v_k, s, P] (or [f_k] without peak coupling) in a building's coupled vector."""
    if not peak:
        return np.arange(H * k, H * (k + 1))
    f = np.arange(2 * H * k, 2 * H * k + H)
    v = np.arange(2 * H * k + H, 2 * H * (k + 1))
    s = np.arange(2 * H * L, 2 * H * L + H)
    P = np.arange(2 * H * L + H, 2 * H * L + H + 2)
    return np.concatenate([f, v, s, P])


def run_admm(campus: Campus, blp: list[BuildingLP], ys: list[np.ndarray], rho: float, max_iter: int,
             tol: float, z0: dict | None = None, u0: dict | None = None, x0: list | None = None,
             alpha: float = 1.6, balance: bool = True, trace: list | None = None) -> AdmmResult:
    H = blp[0].H
    n = campus.n
    sl = {}
    for i, b in enumerate(blp):
        L = len(b.inc)
        for k, (l, _) in enumerate(b.inc):
            sl[(i, l)] = _edge_slices(H, L, k, b.peak)
    ends = {l: (a, c) for l, (a, c) in enumerate(campus.lines)}
    m = 3 * H + 2 if blp[0].peak else H
    z = {l: (z0[l].copy() if z0 and l in z0 else np.zeros(m)) for l in ends}
    u = {key: (u0[key].copy() if u0 and key in u0 else np.zeros(m)) for key in sl}
    x = [None] * n if x0 is None else list(x0)
    r_hist, s_hist = [], []
    converged = False
    it = 0
    for it in range(1, max_iter + 1):
        # 1) local QPs (in a deployment these run in parallel, one per building)
        for i, b in enumerate(blp):
            nc = len(b.coupled)
            lin, hess = np.zeros(nc), np.zeros(nc)
            for (l, _) in b.inc:
                idx = sl[(i, l)]
                lin[idx] += rho * (u[(i, l)] - z[l])
                hess[idx] += rho
            x[i] = b.admm_step(ys[i], rho, lin, hess, warm=x[i])
        # 2) neighbours average their copies of each cable's shared quantities; 3) dual update
        r_max, s_max = 0.0, 0.0
        for l, (a, c) in ends.items():
            xa = x[a][blp[a].coupled][sl[(a, l)]]
            xc = x[c][blp[c].coupled][sl[(c, l)]]
            ha = alpha * xa + (1 - alpha) * z[l]          # over-relaxation
            hc = alpha * xc + (1 - alpha) * z[l]
            zn = 0.5 * (ha + u[(a, l)] + hc + u[(c, l)])
            s_max = max(s_max, float(np.abs(zn - z[l]).max()))
            z[l] = zn
            u[(a, l)] += ha - zn
            u[(c, l)] += hc - zn
            r_max = max(r_max, float(np.abs(xa - zn).max()), float(np.abs(xc - zn).max()))
        r_hist.append(r_max); s_hist.append(s_max)
        if trace is not None:        # both ends' proposals for each cable's flow in the current slot
            trace.append({"k": it, "r": r_max, "proposals": {
                l: [float(x[a][blp[a].coupled][sl[(a, l)]][0]), float(x[c][blp[c].coupled][sl[(c, l)]][0])]
                for l, (a, c) in ends.items()}})
        if r_max <= tol and s_max <= tol:
            converged = True
            break
        # residual balancing (rho changes rescale the scaled duals)
        if balance and it % 15 == 0:
            if r_max > 10 * s_max and rho < 10:
                rho *= 2.0
                for key in u: u[key] /= 2.0
            elif s_max > 10 * r_max and rho > 1e-4:
                rho /= 2.0
                for key in u: u[key] *= 2.0
    cost = sum(b.lp_cost(xi) for b, xi in zip(blp, x))
    return AdmmResult(x, z, u, rho, it, converged, r_hist, s_hist, cost)


def prices(blp: list[BuildingLP], res: AdmmResult, campus: Campus) -> list[np.ndarray]:
    """Consensus multipliers on each building's coupled columns: lambda_i = rho * sum over its cables of u."""
    H = blp[0].H
    out = []
    for i, b in enumerate(blp):
        lam = np.zeros(len(b.coupled))
        L = len(b.inc)
        for k, (l, _) in enumerate(b.inc):
            lam[_edge_slices(H, L, k, b.peak)] += res.rho * res.u[(i, l)]
        out.append(lam)
    return out
