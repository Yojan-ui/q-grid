"""Local QUBO solvers with a tiered, verified fallback.

solve_local(lp, method="qaoa"):
  exact brute force ALWAYS runs (ground truth, n <= 16)
  tier 1  QAOA:   best feasible sample; accepted only if verified optimal (approx ratio >= accept_ratio,
                  default 1 - 1e-9)
  tier 2  SA:     same acceptance test
  tier 3  exact:  the verified optimum
method="exact" skips tiers 1-2 (used by B5). method="qaoa_only" (ablation) accepts any feasible QAOA
sample and falls back only on infeasibility, to expose QAOA's raw effect on cost. Every call returns metrics: tier used, feasibility of the
QAOA output, approx ratio, P(optimum) under the QAOA distribution, timings.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .. import qubo as Q
from .anneal import anneal
from .exact import approx_ratio, solve_exact
from .qaoa import run_qaoa


@dataclass
class LocalSolution:
    x: np.ndarray
    tier: str
    objective: float
    exact_objective: float
    metrics: dict = field(default_factory=dict)
    qaoa_probs: np.ndarray | None = None


def _best_feasible(lp, X, obj_q):
    X = np.unique(np.atleast_2d(X), axis=0)
    feas = Q.feasible_mask(lp, X)
    if not feas.any():
        return None, np.inf, False
    Xf = X[feas]
    o = obj_q.energy(Xf)
    i = int(np.argmin(o))
    return Xf[i], float(o[i]), True


def solve_local(lp: Q.LocalProblem, method: str = "qaoa", p: int = 2, shots: int = 256, seed: int = 0,
                accept_ratio: float = 1 - 1e-9, backend: str = "numpy", keep_probs: bool = False) -> LocalSolution:
    t0 = time.perf_counter()
    qubos = Q.build(lp)
    ob = qubos[0]
    en = Q.enumerate_all(lp, qubos)
    total, A_x, A_s, _ = Q.auto_tune(lp, qubos, enum=en)
    ex = solve_exact(lp, qubos, enum=en)
    t_exact = time.perf_counter() - t0
    m = {"n_qubits": lp.n, "A_x": A_x, "A_s": A_s, "t_exact_s": t_exact}

    if method == "exact":
        return LocalSolution(ex.x, "exact", ex.objective, ex.objective, {**m, "tier": "exact"})

    tq = time.perf_counter()
    qr = run_qaoa(total, p=p, shots=shots, seed=seed, backend=backend, total_energies=en["total"])
    p_opt = float(qr.probs[ex.opt_mask].sum())
    p_feas = float(qr.probs[ex.feasible].sum())
    xq, oq, fq = _best_feasible(lp, qr.samples, ob)
    ar_q = approx_ratio(oq, ex) if fq else 0.0
    m.update({"qaoa_p_opt": p_opt, "qaoa_p_feasible": p_feas, "qaoa_feasible": fq, "qaoa_approx_ratio": ar_q,
              "qaoa_found_opt": bool(fq and ar_q >= 1 - 1e-9), "t_qaoa_s": time.perf_counter() - tq})
    probs = qr.probs if keep_probs else None
    if method == "qaoa_only" and fq:
        return LocalSolution(xq, "qaoa", oq, ex.objective, {**m, "tier": "qaoa"}, probs)
    if fq and ar_q >= accept_ratio:
        return LocalSolution(xq, "qaoa", oq, ex.objective, {**m, "tier": "qaoa"}, probs)

    ta = time.perf_counter()
    xs, os_, fs = _best_feasible(lp, anneal(total, seed=seed), ob)
    ar_s = approx_ratio(os_, ex) if fs else 0.0
    m.update({"sa_feasible": fs, "sa_approx_ratio": ar_s, "t_sa_s": time.perf_counter() - ta})
    if fs and ar_s >= accept_ratio:
        return LocalSolution(xs, "anneal", os_, ex.objective, {**m, "tier": "anneal"}, probs)

    return LocalSolution(ex.x, "exact", ex.objective, ex.objective, {**m, "tier": "exact"}, probs)
