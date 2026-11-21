"""B3 per-building MPC-MILP, no sharing. With a perfect forecast, shrinking-horizon MPC re-solving every
slot reproduces the full-day MILP plan, so we solve the full-day MILP once per building."""
from __future__ import annotations

import numpy as np

from qgrid.model import Campus, DayData, Schedule

from .milp import solve_milp, to_schedule


def solve(campus: Campus, day: DayData) -> Schedule:
    s = Schedule.empty(campus)
    st = []
    for i in range(campus.n):
        r = solve_milp(campus, day, [i], with_lines=False)
        st.append(r["status"])
        to_schedule(campus, r, s)
    # remove numerical noise outside battery limits
    for i, b in enumerate(campus.buildings):
        s.p_bat[i] = np.clip(s.p_bat[i], -b.battery.kw, b.battery.kw)
    s.info = {"method": "B3", "milp_status": st}
    return s
