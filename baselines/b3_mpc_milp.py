"""B3 per-zone MPC-MILP, no sharing. With a perfect forecast, shrinking-horizon MPC re-solving every slot
reproduces the full-day MILP plan, so the full-day MILP is solved once per zone."""
from __future__ import annotations

from qgrid.model import Campus, DayData, Schedule

from .milp import solve_milp, to_schedule


def solve(campus: Campus, day: DayData, rules=None) -> Schedule:
    s = Schedule.empty(campus)
    st = []
    for i in range(campus.n):
        r = solve_milp(campus, day, [i], with_lines=False)
        st.append(r["status"])
        to_schedule(campus, r, s)
    s.info = {"method": "B3", "milp_status": st}
    return s
