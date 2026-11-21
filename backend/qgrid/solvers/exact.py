"""Tier 3 / ground truth: exhaustive search over all 2^n bitstrings (vectorised, n <= 16)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .. import qubo as Q


@dataclass
class ExactResult:
    x: np.ndarray
    objective: float           # pure objective of the optimum (feasible set)
    worst_feasible: float
    obj_all: np.ndarray        # pure objective of every bitstring
    feasible: np.ndarray       # feasibility mask of every bitstring
    opt_mask: np.ndarray       # bitstrings achieving the optimum (ties)


def solve_exact(lp: Q.LocalProblem, qubos=None, enum: dict | None = None) -> ExactResult:
    en = enum or Q.enumerate_all(lp, qubos)
    X, feas, obj = en["X"], en["feas"], en["ob"]
    masked = np.where(feas, obj, np.inf)
    g = int(np.argmin(masked))
    best = float(masked[g])
    worst = float(np.max(np.where(feas, obj, -np.inf)))
    tol = 1e-9 * max(1.0, abs(best))
    return ExactResult(X[g].copy(), best, worst, obj, feas, feas & (obj <= best + tol))


def approx_ratio(obj: float, ex: ExactResult) -> float:
    """1 = optimal, 0 = worst feasible; minimisation, works for negative objectives."""
    span = ex.worst_feasible - ex.objective
    if span <= 1e-12:
        return 1.0
    return float((ex.worst_feasible - obj) / span)
