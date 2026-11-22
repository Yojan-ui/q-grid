"""Day-ahead MILP (perfect forecast) shared by B3 (per zone, no tie-lines) and B4 (whole campus).
Same objective as model.settle() + VOLL: grid cost + diesel fuel + value of lost load - terminal values
of stored energy and water. DG unit commitment (min load, min on-time), pump/tank dynamics, outage
islanding (no import/export, shedding, spill) and flexible-job start binaries are modelled exactly.
Solved with HiGHS to a relative MIP gap of 0.1 % (status and gap are reported)."""
from __future__ import annotations

import numpy as np
import pulp

from qgrid.model import DT, T, Campus, DayData, Schedule, water_value

MIP_GAP = 1e-3


def _solver(time_limit=120):
    s = pulp.HiGHS(msg=False, timeLimit=time_limit, gapRel=MIP_GAP)
    return s if s.available() else pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit, gapRel=MIP_GAP)


def solve_milp(campus: Campus, day: DayData, zones: list[int], with_lines: bool, time_limit: int = 120,
               demand_charge: dict | None = None) -> dict:
    """demand_charge = {rate_day, pf}: adds rate_day * campus peak kVA (v2 tariff) to the objective."""
    m = pulp.LpProblem("qgrid", pulp.LpMinimize)
    V = pulp.LpVariable
    pi, pe, grid = day.obj_imp, day.price_exp, day.grid
    obj, bal, vars_ = [], {}, {}
    imps: dict = {}
    for i in zones:
        b = campus.buildings[i]
        bat = b.battery
        zv = {"ch": [0] * T, "dis": [0] * T, "dg": [0] * T, "w": [0] * T, "ys": {}}
        if bat.present:
            ch = [V(f"ch_{i}_{t}", 0, bat.kw) for t in range(T)]
            dis = [V(f"dis_{i}_{t}", 0, bat.kw) for t in range(T)]
            md = [V(f"m_{i}_{t}", cat="Binary") for t in range(T)]
            e = [V(f"e_{i}_{t}", bat.e_min, bat.e_max) for t in range(T + 1)]
            m += e[0] == bat.e0
            for t in range(T):
                m += ch[t] <= bat.kw * md[t]
                m += dis[t] <= bat.kw * (1 - md[t])
                m += e[t + 1] == e[t] + (bat.eta_ch * ch[t] - dis[t] * (1 / bat.eta_dis)) * DT
            obj.append(-day.term_value * (e[T] - bat.e0))
            zv["ch"], zv["dis"] = ch, dis
        flex_t = [0] * T
        for j in b.flex:
            y = {tau: V(f"y_{i}_{j.name}_{tau}", cat="Binary") for tau in range(j.earliest, j.latest + 1)}
            m += pulp.lpSum(y.values()) == 1
            zv["ys"][j.name] = y
            for tau, yv in y.items():
                for k in range(j.slots):
                    flex_t[tau + k] = flex_t[tau + k] + j.kw * yv
        pump_t = [0] * T
        if b.tank:
            tk = b.tank
            w = [V(f"w_{i}_{t}", cat="Binary") for t in range(T)]
            lv = [V(f"lv_{i}_{t}", tk.l_min, tk.l_max) for t in range(T + 1)]
            m += lv[0] == tk.level0
            for t in range(T):
                m += lv[t + 1] == lv[t] + tk.pump_m3 * w[t] - float(day.water[t])
            pump_t = [tk.pump_kw * w[t] for t in range(T)]
            obj.append(-water_value(campus, day, i) * (lv[T] - tk.level0))
            zv["w"] = w
        dg_t = [0] * T
        if b.dg:
            g = b.dg
            on = [V(f"on_{i}_{t}", cat="Binary") for t in range(T)]
            pg = [V(f"pg_{i}_{t}", 0, g.kw) for t in range(T)]
            stt = [V(f"st_{i}_{t}", cat="Binary") for t in range(T)]
            for t in range(T):
                m += pg[t] <= g.kw * on[t]
                m += pg[t] >= g.p_min * on[t]
                m += stt[t] >= on[t] - (on[t - 1] if t > 0 else 0)
                L = min(g.min_on_slots, T - t)
                m += pulp.lpSum(on[t:t + L]) >= L * stt[t]
                obj.append((g.fuel_a * g.kw * on[t] + g.fuel_b * pg[t]) * DT * (g.price + day.lam * g.co2_per_l))
            dg_t = pg
            zv["dg"] = pg
        for t in range(T):
            demand = float(day.load[i, t]) + flex_t[t] + pump_t[t]
            ex = demand + zv["ch"][t] - zv["dis"][t] - float(day.pv[i, t]) - dg_t[t]
            if grid[t]:
                imp, exp = V(f"imp_{i}_{t}", 0), V(f"exp_{i}_{t}", 0)
                ex = ex - imp + exp
                obj.append((pi[t] * imp - pe[t] * exp) * DT)
                imps.setdefault(t, []).append(imp)
            else:
                snc, sc, sp = V(f"snc_{i}_{t}", 0), V(f"sc_{i}_{t}", 0), V(f"sp_{i}_{t}", 0)
                m += snc <= demand - float(day.crit[i, t])
                ex = ex - snc - sc + sp
                obj.append((day.voll_nc * snc + day.voll_c * sc) * DT)
            bal[(i, t)] = ex
        vars_[i] = zv
    flows = None
    if with_lines:
        F = campus.step_kw
        flows = {(l, t): V(f"f_{l}_{t}", -F, F) for l in range(len(campus.lines)) for t in range(T)}
        for (l, t), f in flows.items():
            a, c = campus.lines[l]
            if (a, t) in bal and (c, t) in bal:
                bal[(a, t)] = bal[(a, t)] + f
                bal[(c, t)] = bal[(c, t)] - f
    for k, expr in bal.items():
        m += expr == 0
    if demand_charge and demand_charge.get("rate_day", 0) > 0:
        Pk = V("peak_kva", 0)
        for t, lst in imps.items():
            m += pulp.lpSum(lst) * (1.0 / demand_charge["pf"]) <= Pk
        obj.append(demand_charge["rate_day"] * Pk)
    m += pulp.lpSum(obj)
    status = m.solve(_solver(time_limit))
    return {"status": pulp.LpStatus[status], "vars": vars_, "flows": flows, "objective": pulp.value(m.objective)}


def _val(x):
    return float(x.value() or 0.0) if hasattr(x, "value") else float(x)


def to_schedule(campus: Campus, res: dict, s: Schedule) -> None:
    for i, v in res["vars"].items():
        b = campus.buildings[i]
        s.p_bat[i] = np.array([_val(c) - _val(d) for c, d in zip(v["ch"], v["dis"])])
        if b.battery.present:
            s.p_bat[i] = np.clip(s.p_bat[i], -b.battery.kw, b.battery.kw)
        s.dg_kw[i] = np.array([_val(x) for x in v["dg"]])
        s.dg_kw[i][s.dg_kw[i] < 1e-6] = 0.0
        if b.dg is not None:
            on = s.dg_kw[i] > 0
            s.dg_kw[i] = np.where(on, np.clip(s.dg_kw[i], b.dg.p_min, b.dg.kw), 0.0)
        s.pump_on[i] = np.array([round(_val(x)) for x in v["w"]], float)
        for name, y in v["ys"].items():
            s.flex_start[i][name] = max(y, key=lambda tau: _val(y[tau]))
    if res["flows"] is not None:
        for (l, t), f in res["flows"].items():
            s.flows[l, t] = np.clip(_val(f), -campus.step_kw, campus.step_kw)
