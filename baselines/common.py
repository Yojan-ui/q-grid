"""Shared helpers for baselines: per-building simulation with the safety clamp."""
from __future__ import annotations

import numpy as np

from qgrid.model import DT, T, Building, DayData


def simulate_building(b: Building, i: int, day: DayData, p_cmd: np.ndarray, starts: np.ndarray):
    """Vectorised over a population. p_cmd (pop, T) requested battery kW, starts (pop,) flex start slots
    (one job). Applies the SoC/power clamp; returns (cost (pop,), p_applied (pop, T))."""
    bat = b.battery
    pop = p_cmd.shape[0]
    e = np.full(pop, bat.e0)
    p_app = np.zeros((pop, T))
    flex = np.zeros((pop, T))
    for j in b.flex:
        s = np.clip(np.round(starts).astype(int), j.earliest, j.latest)
        for k in range(j.slots):
            flex[np.arange(pop), s + k] += j.kw
    pi, pe = day.obj_imp, day.price_exp
    cost = np.zeros(pop)
    for t in range(T):
        hi = np.minimum(bat.kw, np.maximum(0, (bat.e_max - e) / (bat.eta_ch * DT)))
        lo = -np.minimum(bat.kw, np.maximum(0, (e - bat.e_min) * bat.eta_dis / DT))
        p = np.clip(p_cmd[:, t], lo, hi)
        p_app[:, t] = p
        e = bat.step(e, p)
        r = day.load[i, t] + flex[:, t] + p - day.pv[i, t]
        cost += (pi[t] * np.maximum(r, 0) - pe[t] * np.maximum(-r, 0)) * DT
    cost += day.term_value * (bat.e0 - e)
    return cost, p_app
