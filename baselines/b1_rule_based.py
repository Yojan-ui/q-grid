"""B1 rule-based: battery self-consumption (charge from surplus, discharge to cover deficit) every slot,
DG covers any deficit left during an outage, float-switch pumps, flexible loads at default times, no sharing."""
from __future__ import annotations

import numpy as np

from qgrid import safety
from qgrid.agent import BuildingAgent
from qgrid.model import T, Campus, DayData, Schedule


def solve(campus: Campus, day: DayData, rules=None) -> Schedule:
    s = Schedule.empty(campus)
    for i in range(campus.n):
        ag = BuildingAgent(campus, day, i, rules=rules)
        for t in range(T):
            for j in ag.pending_jobs():
                if t == j.default or t >= j.latest:
                    ag.started[j.name] = t
                    ag.running += j.profile(t)
            pump = False
            if ag.tank is not None:
                pump = safety.pump_decision(ag.tank, ag.level, ag.water[t], safety.float_switch(ag.tank, ag.level, ag.pump_prev))
                ag.level += (ag.tank.pump_m3 if pump else 0.0) - ag.water[t]
                ag.pump_prev = pump
            r = ag.load[t] - ag.pv[t] + ag.running[t] + (ag.tank.pump_kw if pump else 0.0)
            p = safety.clamp_battery(ag.bat, ag.e, -r) if ag.bat.present else 0.0
            if ag.bat.present:
                ag.e = float(ag.bat.step(ag.e, p))
            g = 0.0
            if ag.dg is not None:
                on = safety.dg_decision(ag.dg, (not day.grid[t]) and r + p > 0, ag.dg_run, True)
                g = float(np.clip(r + p, ag.dg.p_min, ag.dg.kw)) if on else 0.0
                ag.dg_run = ag.dg_run + 1 if on else 0
            s.p_bat[i, t], s.dg_kw[i, t], s.pump_on[i, t] = p, g, float(pump)
        s.flex_start[i] = dict(ag.started)
    s.info = {"method": "B1"}
    return s
