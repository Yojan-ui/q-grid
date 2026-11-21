"""B5: the same decentralised consensus ADMM as OURS with the exact (brute-force) local solver."""
from __future__ import annotations

from qgrid.admm import run_day
from qgrid.model import Campus, DayData, Schedule


def solve(campus: Campus, day: DayData, rules=None, **kw) -> Schedule:
    s, st = run_day(campus, day, method="exact", rules=rules, **kw)
    s.info["method"] = "B5"
    s.info["_stats"] = st
    return s
