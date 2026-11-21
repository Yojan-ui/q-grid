"""QIEA — quantum-INSPIRED evolutionary algorithm. Classical CPU algorithm; NOT quantum computing.

Each individual is a vector of Q-bit angles theta_i with P(bit_i = 1) = sin^2(theta_i). Every generation
the population is "observed" (sampled) into bitstrings, evaluated on the QUBO, and every angle is rotated
by a fixed step towards the best bitstring found so far (rotation-gate update). Used as a local tier
(QAOA -> QIEA -> SA -> exact) and as a whole-campus centralised QUBO solver (C-QIEA baseline).
"""
from __future__ import annotations

import numpy as np

from ..qubo import QUBO


def qiea(q: QUBO, pop: int = 12, gens: int = 80, seed: int = 0, delta: float = 0.03 * np.pi,
         repair=None, x0: np.ndarray | None = None) -> tuple[np.ndarray, float, np.ndarray]:
    """Return (best bitstring, its energy, last observed population). `repair(X)` (optional) maps
    observed bitstrings to feasible ones before evaluation; `x0` biases the initial angles (warm start)."""
    rng = np.random.default_rng(seed)
    n = len(q.M)
    theta = np.full((pop, n), np.pi / 4)
    if x0 is not None:
        theta[:] = np.where(np.asarray(x0) > 0.5, np.pi / 4 + 0.15 * np.pi, np.pi / 4 - 0.15 * np.pi)
    best_x, best_e = None, np.inf
    X = None
    for _ in range(gens):
        X = (rng.random((pop, n)) < np.sin(theta) ** 2).astype(float)
        if repair is not None:
            X = repair(X)
        e = q.energy(X)
        i = int(np.argmin(e))
        if e[i] < best_e:
            best_e, best_x = float(e[i]), X[i].copy()
        # rotation gate towards the best solution (only where the observation differs from it)
        diff = X != best_x[None, :]
        direction = np.where(best_x[None, :] > 0.5, 1.0, -1.0)
        theta = np.clip(theta + diff * direction * delta, 0.02 * np.pi, 0.48 * np.pi)
    return best_x, best_e, X
