"""Day-ahead MILP (perfect forecast) shared by B3 (per building, no tie-lines) and B4 (whole campus).
Same objective as model.settle(): grid cost + carbon shadow price - terminal value of stored energy."""
from __future__ import annotations

import numpy as np
import pulp

from qgrid.model import DT, T, Campus, DayData, Schedule


def _solver():
    s = pulp.HiGHS(msg=False, timeLimit=120)
    return s if s.available() else pulp.PULP_CBC_CMD(msg=False, timeLimit=120)


def solve_milp(campus: Campus, day: DayData, buildings: list[int], with_lines: bool) -> dict:
    m = pulp.LpProblem("qgrid", pulp.LpMinimize)
    V = pulp.LpVariable
    pi, pe = day.obj_imp, day.price_exp
    vars_ = {}
    obj = []
    balance = {}
    for i in buildings:
        b = campus.buildings[i]
        bat = b.battery
        ch = [V(f"ch_{i}_{t}", 0, bat.kw) for t in range(T)]
        dis = [V(f"dis_{i}_{t}", 0, bat.kw) for t in range(T)]
        mode = [V(f"m_{i}_{t}", cat="Binary") for t in range(T)]
        imp = [V(f"imp_{i}_{t}", 0) for t in range(T)]
        exp = [V(f"exp_{i}_{t}", 0) for t in range(T)]
        e = [V(f"e_{i}_{t}", bat.e_min, bat.e_max) for t in range(T + 1)]
        m += e[0] == bat.e0
        for t in range(T):
            m += ch[t] <= bat.kw * mode[t]
            m += dis[t] <= bat.kw * (1 - mode[t])
            m += e[t + 1] == e[t] + (bat.eta_ch * ch[t] - dis[t] * (1 / bat.eta_dis)) * DT
        flex_t = [0] * T
        ys = {}
        for j in b.flex:
            y = {tau: V(f"y_{i}_{j.name}_{tau}", cat="Binary") for tau in range(j.earliest, j.latest + 1)}
            m += pulp.lpSum(y.values()) == 1
            ys[j.name] = y
            for tau, yv in y.items():
                for k in range(j.slots):
                    flex_t[tau + k] = flex_t[tau + k] + j.kw * yv
        for t in range(T):
            balance[(i, t)] = day.load[i, t] + flex_t[t] + ch[t] - dis[t] - day.pv[i, t] - imp[t] + exp[t]
            obj.append((pi[t] * imp[t] - pe[t] * exp[t]) * DT)
        obj.append(-day.term_value * (e[T] - bat.e0))
        vars_[i] = dict(ch=ch, dis=dis, ys=ys)
    flows = None
    if with_lines:
        F = campus.step_kw
        flows = {(l, t): V(f"f_{l}_{t}", -F, F) for l in range(len(campus.lines)) for t in range(T)}
        for (l, t), f in flows.items():
            a, c = campus.lines[l]
            balance[(a, t)] = balance[(a, t)] + f
            balance[(c, t)] = balance[(c, t)] - f
    for k, expr in balance.items():
        m += expr == 0
    m += pulp.lpSum(obj)
    status = m.solve(_solver())
    return {"status": pulp.LpStatus[status], "vars": vars_, "flows": flows, "objective": pulp.value(m.objective)}


def to_schedule(campus: Campus, res: dict, sched: Schedule) -> None:
    for i, v in res["vars"].items():
        sched.p_bat[i] = np.array([(c.value() or 0) - (d.value() or 0) for c, d in zip(v["ch"], v["dis"])])
        for name, y in v["ys"].items():
            sched.flex_start[i][name] = max(y, key=lambda tau: y[tau].value() or 0)
    if res["flows"] is not None:
        for (l, t), f in res["flows"].items():
            sched.flows[l, t] = f.value() or 0.0
