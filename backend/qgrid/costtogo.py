"""Local battery cost-to-go by dynamic programming (classical, per building, no sharing).

Gives each building's 1-hour QUBO a view of the rest of the day: V_t(e) = minimum cost from slot t
to the end of the day starting with battery energy e, using only the building's own forecast
(net load, prices). Terminal value matches model.settle(): V_T(e) = -term_value * (e - e0).
"""
from __future__ import annotations

import numpy as np

from .model import DT, T, Battery, slot_cost
from .safety import battery_limits


class CostToGo:
    def __init__(self, bat: Battery, r0: np.ndarray, pi: np.ndarray, pe: np.ndarray, term_value: float,
                 n_levels: int = 81, n_actions: int = 24):
        self.bat = bat
        self.grid = np.linspace(bat.e_min, bat.e_max, n_levels)
        V = np.empty((T + 1, n_levels))
        V[T] = -term_value * (self.grid - bat.e0)
        lims = np.array([battery_limits(bat, e) for e in self.grid])
        frac = np.linspace(0, 1, n_actions)
        P = lims[:, :1] + frac[None, :] * (lims[:, 1:] - lims[:, :1])
        P = np.concatenate([P, np.zeros((n_levels, 1))], axis=1)          # always allow idle
        E1 = bat.step(self.grid[:, None], P)
        for t in range(T - 1, -1, -1):
            c = slot_cost(r0[t] + P, pi[t], pe[t]) + np.interp(E1, self.grid, V[t + 1])
            V[t] = c.min(axis=1)
        self.V = V

    def __call__(self, t: int, e):
        return np.interp(e, self.grid, self.V[min(t, T)])

    def quad_fit(self, t: int, e_lo: float, e_hi: float) -> tuple[float, float, float]:
        """Convex quadratic a2 e^2 + a1 e + a0 fitted to V_t on [e_lo, e_hi]."""
        if e_hi - e_lo < 1e-6:
            return 0.0, 0.0, float(self(t, e_lo))
        e = np.linspace(e_lo, e_hi, 25)
        v = self(t, e)
        a2, a1, a0 = np.polyfit(e, v, 2)
        if a2 < 0:
            a1, a0 = np.polyfit(e, v, 1)
            a2 = 0.0
        return float(a2), float(a1), float(a0)
