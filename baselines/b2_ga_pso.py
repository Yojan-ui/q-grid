"""B2 metaheuristics (pymoo GA and PSO), per building, no sharing, same day-ahead information.
Decision vector: 24 hourly battery set-points in [-P, P] (held for 4 slots) + flexible-job start slot.
Fitness = exact settlement cost (incl. terminal SoC adjustment) after the safety clamp."""
from __future__ import annotations

import numpy as np
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.algorithms.soo.nonconvex.pso import PSO
from pymoo.core.problem import Problem
from pymoo.optimize import minimize

from qgrid.model import T, Campus, DayData, Schedule

from .common import simulate_building


class _BuildingProblem(Problem):
    def __init__(self, b, i, day):
        self.b, self.i, self.day = b, i, day
        j = b.flex[0] if b.flex else None
        lo = np.r_[-np.ones(24) * b.battery.kw, j.earliest if j else 0]
        hi = np.r_[np.ones(24) * b.battery.kw, j.latest if j else 0]
        super().__init__(n_var=25, n_obj=1, xl=lo, xu=hi)

    def _evaluate(self, X, out, *a, **k):
        p = np.repeat(X[:, :24], T // 24, axis=1)
        cost, _ = simulate_building(self.b, self.i, self.day, p, X[:, 24])
        out["F"] = cost


def solve(campus: Campus, day: DayData, algo: str = "GA", pop: int = 40, n_gen: int = 80, seed: int = 1) -> Schedule:
    s = Schedule.empty(campus)
    for i, b in enumerate(campus.buildings):
        prob = _BuildingProblem(b, i, day)
        alg = GA(pop_size=pop, eliminate_duplicates=True) if algo == "GA" else PSO(pop_size=pop)
        res = minimize(prob, alg, ("n_gen", n_gen), seed=seed + i, verbose=False)
        x = np.atleast_2d(res.X)[0]
        p = np.repeat(x[None, :24], T // 24, axis=1)
        _, p_app = simulate_building(b, i, day, p, np.array([x[24]]))
        s.p_bat[i] = p_app[0]
        for j in b.flex:
            s.flex_start[i][j.name] = int(np.clip(round(x[24]), j.earliest, j.latest))
    s.info = {"method": f"B2-{algo}"}
    return s
