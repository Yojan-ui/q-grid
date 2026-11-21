"""B4 centralised campus MILP: all zones + continuous tie-line flows in [-F, F] (a relaxation of the
discrete {-F, 0, F} levels of the decentralised methods) -> global optimum / lower bound (within MIP gap)."""
from __future__ import annotations

from qgrid.model import Campus, DayData, Schedule

from .milp import MIP_GAP, solve_milp, to_schedule


def solve(campus: Campus, day: DayData, rules=None) -> Schedule:
    s = Schedule.empty(campus)
    r = solve_milp(campus, day, list(range(campus.n)), with_lines=True, time_limit=300)
    to_schedule(campus, r, s)
    s.info = {"method": "B4", "milp_status": r["status"], "milp_objective": r["objective"], "mip_gap": MIP_GAP}
    return s
