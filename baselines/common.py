"""Shared helper for metaheuristic baselines: vectorised per-zone simulation with the safety clamp.
Pump and DG schedules are taken from B1 (rule-based) and kept fixed; battery set-points and job starts vary."""
from __future__ import annotations

import numpy as np

from qgrid.model import DT, T, Building, DayData, slot_cost


def simulate_building(b: Building, i: int, day: DayData, p_cmd: np.ndarray, starts: np.ndarray,
                      pump_kw: np.ndarray, dg_kw: np.ndarray, peak: dict | None = None):
    """p_cmd (pop, T), starts (pop, n_jobs). Returns (objective incl. VOLL (pop,), p_applied (pop, T)).
    peak: this building's monthly-peak term {rate, pf, budget, cbudget, xs_rate} (kVA; qgrid/ablation/demand.py):
    rate * max(0, own peak import kVA - budget) + xs_rate * max(0, own peak - cbudget)."""
    bat = b.battery
    pop = p_cmd.shape[0]
    e = np.full(pop, bat.e0)
    p_app = np.zeros((pop, T))
    flex = np.zeros((pop, T))
    for k, j in enumerate(b.flex):
        s = np.clip(np.round(starts[:, k]).astype(int), j.earliest, j.latest)
        for q in range(j.slots):
            flex[np.arange(pop), s + q] += j.kw
    cost = np.zeros(pop)
    pk = np.zeros(pop)
    for t in range(T):
        if bat.present:
            hi = np.minimum(bat.kw, np.maximum(0, (bat.e_max - e) / (bat.eta_ch * DT)))
            lo = -np.minimum(bat.kw, np.maximum(0, (e - bat.e_min) * bat.eta_dis / DT))
            p = np.clip(p_cmd[:, t], lo, hi)
            e = bat.step(e, p)
        else:
            p = np.zeros(pop)
        p_app[:, t] = p
        demand = day.load[i, t] + flex[:, t] + pump_kw[t]
        r = demand + p - day.pv[i, t] - dg_kw[t]
        cost += slot_cost(r, day.obj_imp[t], day.price_exp[t], bool(day.grid[t]),
                          np.maximum(demand - day.crit[i, t], 0), day.voll_nc, day.voll_c)
        cost += getattr(day, "wear", 0.0) * np.abs(p) * DT          # battery wear (0 unless priced)
        if day.grid[t]:
            pk = np.maximum(pk, np.maximum(r, 0.0))
    if bat.present:
        cost += day.term_value * (bat.e0 - e)
    if peak is not None and peak.get("rate", 0) > 0:
        kva = pk / peak["pf"]
        cost += peak["rate"] * np.maximum(0.0, kva - peak["budget"])
        if peak.get("cbudget") is not None and peak.get("xs_rate", 0) > 0:
            cost += peak["xs_rate"] * np.maximum(0.0, kva - peak["cbudget"])
    return cost, p_app
