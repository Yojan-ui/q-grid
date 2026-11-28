"""B2 metaheuristics (pymoo GA and PSO), per zone, no sharing, same day-ahead information.
Decision vector: 24 hourly battery set-points in [-P, P] (held for 4 slots) + one start slot per flexible
job. Pump and DG schedules follow the B1 rules. Fitness = exact settlement cost + VOLL after the clamp
(+ the monthly-peak term on the building's own peak above its static share of the campus allowance, when priced)."""
from __future__ import annotations

import numpy as np
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.algorithms.soo.nonconvex.pso import PSO
from pymoo.core.problem import Problem
from pymoo.optimize import minimize

from qgrid.model import T, Campus, DayData, Schedule

from . import b1_rule_based
from .common import simulate_building


class _ZoneProblem(Problem):
    def __init__(self, b, i, day, pump_kw, dg_kw, peak=None):
        self.b, self.i, self.day, self.pump_kw, self.dg_kw, self.peak = b, i, day, pump_kw, dg_kw, peak
        P = max(b.battery.kw, 1e-6)
        lo = np.r_[-np.ones(24) * P, [j.earliest for j in b.flex]]
        hi = np.r_[np.ones(24) * P, [j.latest for j in b.flex]]
        super().__init__(n_var=len(lo), n_obj=1, xl=lo, xu=hi)

    def _evaluate(self, X, out, *a, **k):
        p = np.repeat(X[:, :24], T // 24, axis=1)
        out["F"], _ = simulate_building(self.b, self.i, self.day, p, X[:, 24:], self.pump_kw, self.dg_kw, self.peak)


def _peak(demand, i):
    """Building i's static share of the campus peak allowance (no communication between buildings)."""
    if not demand or demand.get("rate", 0) <= 0:
        return None
    w = float(demand["weights"][i])
    return {"rate": demand["rate"], "pf": demand["pf"], "budget": float(demand.get("ref_kva") or 0.0) * w,
            "cbudget": (float(demand["contract_kva"]) * w) if demand.get("contract_kva") else None,
            "xs_rate": demand.get("xs_rate", 0.0)}


def solve(campus: Campus, day: DayData, algo: str = "GA", pop: int = 40, n_gen: int = 60, seed: int = 1, rules=None,
          demand: dict | None = None) -> Schedule:
    base = b1_rule_based.solve(campus, day, rules)
    s = Schedule.empty(campus)
    s.pump_on, s.dg_kw = base.pump_on.copy(), base.dg_kw.copy()
    for i, b in enumerate(campus.buildings):
        pump_kw = base.pump_on[i] * (b.tank.pump_kw if b.tank else 0.0)
        if not b.battery.present and not b.flex:
            s.flex_start[i] = dict(base.flex_start[i])
            continue
        prob = _ZoneProblem(b, i, day, pump_kw, base.dg_kw[i], _peak(demand, i))
        alg = GA(pop_size=pop, eliminate_duplicates=True) if algo == "GA" else PSO(pop_size=pop)
        res = minimize(prob, alg, ("n_gen", n_gen), seed=seed + i, verbose=False)
        x = np.atleast_2d(res.X)[0]
        _, p_app = simulate_building(b, i, day, np.repeat(x[None, :24], T // 24, axis=1), x[None, 24:], pump_kw, base.dg_kw[i])
        s.p_bat[i] = p_app[0]
        for k, j in enumerate(b.flex):
            s.flex_start[i][j.name] = int(np.clip(round(x[24 + k]), j.earliest, j.latest))
    s.info = {"method": f"B2-{algo}"}
    return s
