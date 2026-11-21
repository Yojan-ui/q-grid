"""B1 rule-based self-consumption: charge from PV surplus, discharge to cover deficits (within SoC
limits), flexible loads at default times, no sharing."""
from __future__ import annotations

import numpy as np

from qgrid import safety
from qgrid.model import T, Campus, DayData, Schedule, flex_load


def solve(campus: Campus, day: DayData) -> Schedule:
    s = Schedule.empty(campus)
    s.flex_start = [{j.name: j.default for j in b.flex} for b in campus.buildings]
    fl = flex_load(campus, s)
    for i, b in enumerate(campus.buildings):
        e = b.battery.e0
        for t in range(T):
            net = day.load[i, t] + fl[i, t] - day.pv[i, t]
            p = safety.clamp_battery(b.battery, e, -net)   # surplus (net<0) -> charge; deficit -> discharge
            s.p_bat[i, t] = p
            e = b.battery.step(e, p)
    s.info = {"method": "B1"}
    return s
