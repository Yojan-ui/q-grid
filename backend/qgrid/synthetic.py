"""SYNTHETIC day for unit tests / CI only (CI has no processed real data). Never used for results."""
from __future__ import annotations

import numpy as np

from .model import T, Campus, DayData, hhmm_to_slot, load_campus


def synthetic_campus() -> Campus:
    """The configured campus (layout from the committed data/processed/campus.json)."""
    return load_campus()


def synthetic_day(campus: Campus, seed: int = 0, scenario: str = "A", outage: tuple[str, str] | None = None) -> DayData:
    rng = np.random.default_rng(seed)
    h = np.arange(T) / 4
    sun = np.clip(np.sin((h - 6) / 12 * np.pi), 0, None)
    pv = np.array([b.pv_kwp * 0.8 * sun for b in campus.buildings])
    base = 0.55 + 0.25 * np.exp(-((h - 20) / 2.5) ** 2) + 0.2 * np.exp(-((h - 11) / 3) ** 2)
    peak = np.array([max(b.pv_kwp, 30.0) * 0.5 for b in campus.buildings])
    load = np.array([p * base * rng.uniform(0.85, 1.15) for p in peak])
    load[[i for i, b in enumerate(campus.buildings) if b.tank is not None]] = 0.0
    crit = load * np.array([[b.critical_frac] for b in campus.buildings])
    water = 3.0 + 2.0 * np.exp(-((h - 7) / 2) ** 2) + 2.0 * np.exp(-((h - 19) / 2) ** 2)
    imp = np.where((h >= 18) & (h < 22), 9.0, np.where((h >= 22) | (h < 6), 7.0, 8.0))
    exp = np.full(T, 3.0) if scenario == "A" else imp.copy()
    grid = np.ones(T, bool)
    if outage:
        grid[hhmm_to_slot(outage[0]):hhmm_to_slot(outage[1])] = False
    return DayData("SYNTHETIC", scenario, pv, load, crit, water, imp, exp, 0.7, 0.0, grid, 40.0, 1000.0,
                   {"synthetic": True}, "synthetic", "teaching")
