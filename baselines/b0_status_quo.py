"""B0 status quo: no optimisation and no sharing. Flexible loads at their default times, float-switch pumps,
batteries act only as UPS during a grid outage, DGs run only during an outage."""
from __future__ import annotations

from qgrid.agent import BuildingAgent
from qgrid.model import T, Campus, DayData, Schedule


def solve(campus: Campus, day: DayData, rules=None) -> Schedule:
    s = Schedule.empty(campus)
    for i in range(campus.n):
        ag = BuildingAgent(campus, day, i, rules=rules)
        for t in range(T):
            c = ag.apply_safe_default(t)
            s.p_bat[i, t], s.dg_kw[i, t], s.pump_on[i, t] = c["p_bat"], c["dg_kw"], float(c["pump_on"])
        s.flex_start[i] = dict(ag.started)
    s.info = {"method": "B0"}
    return s
