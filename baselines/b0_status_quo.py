"""B0 status quo: battery idle, flexible loads at their default (status-quo) start times,
no inter-building sharing. Each building imports its deficit / exports its surplus to the grid."""
from __future__ import annotations

from qgrid.model import Campus, DayData, Schedule


def solve(campus: Campus, day: DayData) -> Schedule:
    s = Schedule.empty(campus)
    s.flex_start = [{j.name: j.default for j in b.flex} for b in campus.buildings]
    s.info = {"method": "B0"}
    return s
