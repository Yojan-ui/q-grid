"""SYNTHETIC day for unit tests / CI only (no real data is available in CI). Never used for results."""
from __future__ import annotations

import numpy as np

from .model import T, Campus, DayData


def synthetic_day(campus: Campus, seed: int = 0, scenario: str = "A") -> DayData:
    rng = np.random.default_rng(seed)
    h = np.arange(T) / 4
    sun = np.clip(np.sin((h - 6) / 12 * np.pi), 0, None)
    pv = np.array([b.pv_kwp * 0.8 * sun for b in campus.buildings])
    base = 0.55 + 0.25 * np.exp(-((h - 20) / 2.5) ** 2) + 0.1 * np.exp(-((h - 9) / 2) ** 2)
    load = np.array([b.peak_kw * base * rng.uniform(0.85, 1.15) for b in campus.buildings])
    imp = np.where((h >= 18) & (h < 22), 9.0, np.where((h >= 22) | (h < 6), 7.0, 8.0))
    exp = np.full(T, 3.0) if scenario == "A" else imp.copy()
    return DayData("SYNTHETIC", scenario, pv, load, imp, exp, 0.7, 0.0, {"synthetic": True})
