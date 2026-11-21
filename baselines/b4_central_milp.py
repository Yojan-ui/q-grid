"""B4 centralised campus MILP: all buildings + continuous tie-line flows in [-F, F] (a relaxation of the
discrete {-F, 0, F} levels used by the decentralised methods) -> global optimum / lower bound."""
from __future__ import annotations

import numpy as np

from qgrid.model import Campus, DayData, Schedule

from .milp import solve_milp, to_schedule


def solve(campus: Campus, day: DayData) -> Schedule:
    s = Schedule.empty(campus)
    r = solve_milp(campus, day, list(range(campus.n)), with_lines=True)
    to_schedule(campus, r, s)
    for i, b in enumerate(campus.buildings):
        s.p_bat[i] = np.clip(s.p_bat[i], -b.battery.kw, b.battery.kw)
    s.flows = np.clip(s.flows, -campus.step_kw, campus.step_kw)
    s.info = {"method": "B4", "milp_status": r["status"], "milp_objective": r["objective"]}
    return s
