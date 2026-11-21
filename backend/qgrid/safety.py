"""Safety layer: clamps every command before it is applied, whatever solver produced it.

- Battery: SoC kept within [soc_min, soc_max] (20-95 %), |p| <= rated kW.
- Flexible loads: never start outside their window; forced to start at the latest feasible slot.
- Tie-lines: |flow| <= rating; silent / disagreeing neighbour -> flow 0 (island mode).
- Critical load: always served; the grid connection covers any deficit (no shedding of critical load).
"""
from __future__ import annotations

import numpy as np

from .model import DT, Battery, FlexJob


def battery_limits(bat: Battery, e: float) -> tuple[float, float]:
    """Feasible battery power range [p_min, p_max] for one slot from energy e."""
    p_max = min(bat.kw, max(0.0, (bat.e_max - e) / (bat.eta_ch * DT)))
    p_min = max(-bat.kw, -max(0.0, (e - bat.e_min) * bat.eta_dis / DT))
    return p_min, p_max


def clamp_battery(bat: Battery, e: float, p: float) -> float:
    lo, hi = battery_limits(bat, e)
    return float(np.clip(p, lo, hi))


def clamp_flow(f: float, rating: float) -> float:
    return float(np.clip(f, -rating, rating))


def flex_decision(job: FlexJob, t: int, started: bool, want_start: bool) -> bool:
    """Return True if the job should start at slot t."""
    if started:
        return False
    if t >= job.latest:  # must-run: last chance to finish within the day
        return True
    return bool(want_start) and job.earliest <= t <= job.latest


def critical_served(load_kw: float, critical_frac: float, supply_kw: float) -> bool:
    """Supply available to the building (PV + battery + tie-lines + grid) covers its critical share."""
    return supply_kw + 1e-9 >= critical_frac * load_kw
