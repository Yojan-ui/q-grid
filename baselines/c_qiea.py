"""C-QIEA: centralised whole-campus QUBO per slot, solved by QIEA (quantum-INSPIRED, classical CPU).

Per slot the zone QUBOs are stacked into one campus QUBO (~100 binary variables). Each tie-line has one
copy of its two flow bits in each endpoint zone; a penalty A (p_a - p_b)^2 + A (n_a - n_b)^2 ties the copies,
and a repair step makes every observed bitstring consistent and exclusive before evaluation. Penalties are
set heuristically (the instance is too large to enumerate). Decisions are applied through the same agents
and safety layer as every other method.
"""
from __future__ import annotations

import time

import numpy as np

from qgrid import qubo as Q
from qgrid.agent import BuildingAgent
from qgrid.model import T, Campus, DayData, Schedule
from qgrid.qubo import decode
from qgrid.solvers.qiea import qiea


def solve(campus: Campus, day: DayData, rules=None, pop: int = 16, gens: int = 120, seed: int = 7) -> Schedule:
    H = campus.cfg["admm"]["horizon_slots"]
    agents = [BuildingAgent(campus, day, i, H, rules) for i in range(campus.n)]
    s = Schedule.empty(campus)
    times = []
    for t in range(T):
        t0 = time.perf_counter()
        lps, offs, totals = [], [], []
        off = 0
        for ag in agents:
            lp = ag.local_problem(t, ag.incident)
            total, _, _ = Q.penalty_tune_heuristic(Q.build(lp))
            lps.append(lp); offs.append(off); totals.append(total)
            off += lp.n
        N = off
        M = np.zeros((N, N)); const = 0.0
        for lp, o, q in zip(lps, offs, totals):
            M[o:o + lp.n, o:o + lp.n] += q.M
            const += q.const
        A = sum(np.abs(q.M).sum() for q in totals) / max(len(totals), 1)
        pairs = []
        for l, (a, b) in enumerate(campus.lines):
            for v in (f"p{l}", f"n{l}"):
                ia, ib = offs[a] + lps[a].idx[v], offs[b] + lps[b].idx[v]
                pairs.append((ia, ib))
                M[ia, ia] += A; M[ib, ib] += A; M[ia, ib] -= A; M[ib, ia] -= A
        big = Q.QUBO(const, M)
        excl = []
        for lp, o in zip(lps, offs):
            if lp.bat.present:
                excl += [(o + lp.idx[f"c{k}"], o + lp.idx[f"d{k}"]) for k in range(lp.H)]
        for l, (a, b) in enumerate(campus.lines):
            excl.append((offs[a] + lps[a].idx[f"p{l}"], offs[a] + lps[a].idx[f"n{l}"]))

        def repair(X):
            X = X.copy()
            for ia, ib in pairs:
                X[:, ib] = X[:, ia]
            for i1, i2 in excl:
                both = (X[:, i1] == 1) & (X[:, i2] == 1)
                X[both, i1] = 0; X[both, i2] = 0
            for l, (a, b) in enumerate(campus.lines):
                X[:, offs[b] + lps[b].idx[f"n{l}"]] = X[:, offs[a] + lps[a].idx[f"n{l}"]]
                X[:, offs[b] + lps[b].idx[f"p{l}"]] = X[:, offs[a] + lps[a].idx[f"p{l}"]]
            return X

        x, _, _ = qiea(big, pop=pop, gens=gens, seed=seed + t, repair=repair)
        flows = np.zeros(len(campus.lines))
        decs = []
        for lp, o in zip(lps, offs):
            xi = x[o:o + lp.n]
            if not Q.feasible_mask(lp, xi)[0]:          # local repair: drop to idle battery actions
                for k in range(lp.H):
                    if lp.bat.present:
                        xi[lp.idx[f"c{k}"]] = 0; xi[lp.idx[f"d{k}"]] = 0
            decs.append(decode(lp, xi))
        for l, (a, b) in enumerate(campus.lines):
            flows[l] = decs[a]["flows"][l]
        for i, ag in enumerate(agents):
            out = sum(sg * flows[l] for l, sg in ag.incident)
            c = ag.apply(t, decs[i], out)
            s.p_bat[i, t], s.dg_kw[i, t], s.pump_on[i, t] = c["p_bat"], c["dg_kw"], float(c["pump_on"])
        s.flows[:, t] = flows
        times.append(time.perf_counter() - t0)
    for i, ag in enumerate(agents):
        s.flex_start[i] = dict(ag.started)
    s.info = {"method": "C-QIEA", "replan_time_s": float(np.mean(times)), "n_binary_per_slot": int(N)}
    return s
