"""Tier 2: simulated annealing on the penalty-tuned QUBO (numpy, vectorised over chains, fixed seed)."""
from __future__ import annotations

import numpy as np

from ..qubo import QUBO


def anneal(q: QUBO, n_chains: int = 16, sweeps: int = 120, seed: int = 0,
           t_start: float | None = None, t_end: float | None = None) -> np.ndarray:
    """Return the final states of all chains (n_chains, n), each chain ending at its best visited state."""
    rng = np.random.default_rng(seed)
    M = q.M
    n = len(M)
    diag = np.diag(M).copy()
    scale = np.abs(M).sum(axis=1).max() + 1e-12
    t0 = t_start or scale
    t1 = t_end or scale * 1e-4
    x = rng.integers(0, 2, size=(n_chains, n)).astype(float)
    g = np.einsum("bj,ij->bi", x, M)
    e = q.const + np.einsum("bi,bi->b", x, g)
    best_x, best_e = x.copy(), e.copy()
    temps = np.geomspace(t0, t1, sweeps)
    for T in temps:
        for i in rng.permutation(n):
            xi = x[:, i]
            delta = (1 - 2 * xi) * (diag[i] + 2 * (g[:, i] - M[i, i] * xi))
            acc = (delta <= 0) | (rng.random(n_chains) < np.exp(-np.clip(delta, 0, None) / T))
            if acc.any():
                step = np.where(acc, 1 - 2 * xi, 0.0)
                x[:, i] = xi + step
                g += step[:, None] * M[i][None, :]
                e += np.where(acc, delta, 0.0)
                imp = e < best_e
                best_e = np.where(imp, e, best_e)
                best_x[imp] = x[imp]
    return best_x
