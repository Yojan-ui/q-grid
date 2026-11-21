"""Local battery cost-to-go by dynamic programming (classical, per zone, own forecast only, no sharing).

V_t(e) = min cost from slot t to the end of the day with battery energy e, using the exact slot cost
(tariff when the grid is up, value-of-lost-load when islanded). Terminal value matches model.settle().
"""
from __future__ import annotations

import warnings

import numpy as np

from .model import T, Battery, slot_cost
from .safety import battery_limits


class CostToGo:
    def __init__(self, bat: Battery, r0: np.ndarray, pi: np.ndarray, pe: np.ndarray, term_value: float,
                 grid: np.ndarray | None = None, noncrit: np.ndarray | None = None, voll_nc: float = 0.0,
                 voll_c: float = 0.0, n_levels: int = 81, n_actions: int = 24):
        self.bat = bat
        grid = np.ones(T, bool) if grid is None else grid
        noncrit = np.zeros(T) if noncrit is None else noncrit
        if not bat.present:
            self.grid = np.array([0.0, 1.0])
            self.V = np.zeros((T + 1, 2))
            return
        self.grid = np.linspace(bat.e_min, bat.e_max, n_levels)
        V = np.empty((T + 1, n_levels))
        V[T] = -term_value * (self.grid - bat.e0)
        lims = np.array([battery_limits(bat, e) for e in self.grid])
        frac = np.linspace(0, 1, n_actions)
        P = lims[:, :1] + frac[None, :] * (lims[:, 1:] - lims[:, :1])
        P = np.concatenate([P, np.zeros((n_levels, 1))], axis=1)
        E1 = bat.step(self.grid[:, None], P)
        for t in range(T - 1, -1, -1):
            c = slot_cost(r0[t] + P, pi[t], pe[t], bool(grid[t]), noncrit[t], voll_nc, voll_c)
            V[t] = (c + np.interp(E1, self.grid, V[t + 1])).min(axis=1)
        self.V = V

    def __call__(self, t: int, e):
        return np.interp(e, self.grid, self.V[min(t, T)])

    def quad_fit(self, t: int, e_lo: float, e_hi: float) -> tuple[float, float, float]:
        if not self.bat.present or e_hi - e_lo < 1e-6:
            return 0.0, 0.0, float(self(t, e_lo)) if self.bat.present else 0.0
        e = np.linspace(e_lo, e_hi, 25)
        v = self(t, e)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            a2, a1, a0 = np.polyfit(e, v, 2)
        if a2 < 0:
            a1, a0 = np.polyfit(e, v, 1)
            a2 = 0.0
        return float(a2), float(a1), float(a0)
