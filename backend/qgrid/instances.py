"""Realistic local-QUBO instances sampled from real days (for QAOA parameter training and studies)."""
from __future__ import annotations

import numpy as np

from .agent import BuildingAgent
from .model import T, load_campus, make_day


def training_days(meta: dict, k: int = 12) -> list[str]:
    """Days disjoint from the test days and the 30-day evaluation set (15th of each month, nudged)."""
    used = set(meta["days"]["eval_days"]) | {meta["days"][x] for x in ("sunny", "monsoon_cloudy", "high_price")}
    out = []
    for m in range(1, 13):
        for d in (15, 16, 17, 18, 19):
            s = f"{meta['year']}-{m:02d}-{d:02d}"
            if s not in used:
                out.append(s)
                break
    return out[:k]


def sample_instances(proc: dict, days: list[str], n: int, seed: int = 0, scenario: str = "A",
                     with_admm: bool = True):
    """Yield (meta, LocalProblem) with random building, slot, battery SoC and ADMM targets."""
    rng = np.random.default_rng(seed)
    campus = load_campus()
    cache = {}
    out = []
    for _ in range(n):
        day = days[rng.integers(len(days))]
        i = int(rng.integers(campus.n))
        if (day, i) not in cache:
            cache[(day, i)] = BuildingAgent(campus, make_day(campus, proc, day, scenario), i)
        ag = cache[(day, i)]
        t = int(rng.integers(24, T - 8))
        ag.e = float(rng.uniform(ag.bat.e_min, ag.bat.e_max))
        ag.started = {}
        ag.running[:] = 0
        lines = ag.incident
        v, rho = {}, 0.0
        if with_admm and rng.random() < 0.7:
            v = {l: float(rng.choice([-1, 0, 1]) * campus.step_kw) for l, _ in lines}
            rho = float(rng.uniform(0.005, 0.2))
        lp = ag.local_problem(t, lines, v=v, rho=rho)
        out.append(({"day": day, "building": ag.name, "t": t, "n": lp.n}, lp))
    return out
