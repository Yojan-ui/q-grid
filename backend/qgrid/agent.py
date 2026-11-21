"""BuildingAgent: one zone's controller. Holds ONLY its own private data (PV, load, critical load,
battery, DG, tank, flexible loads, cost-to-go) plus public prices / grid status; talks to neighbours only
through tie-line proposals and one marginal price per slot."""
from __future__ import annotations

import numpy as np

from . import qubo as Q
from . import safety
from .costtogo import CostToGo
from .model import DT, T, Campus, DayData, slot_cost, water_value


class BuildingAgent:
    def __init__(self, campus: Campus, day: DayData, i: int, horizon: int = 3, rules: list[dict] | None = None):
        b = campus.buildings[i]
        self.i, self.name, self.H = i, b.name, horizon
        self.bat, self.jobs, self.dg, self.tank = b.battery, list(b.flex), b.dg, b.tank
        self.pv, self.load, self.crit = day.pv[i].copy(), day.load[i].copy(), day.crit[i].copy()
        self.pi, self.pe = day.obj_imp.copy(), day.price_exp.copy()
        self.gridup = day.grid.copy()
        self.voll_nc, self.voll_c = day.voll_nc, day.voll_c
        self.water = day.water.copy() if b.tank else np.zeros(T)
        self.lam_ef = day.lam
        self.incident = campus.incident(i)
        self.F = campus.step_kw
        self.rules = [r for r in (rules or []) if r.get("zone") in (self.name, "*")]
        default_flex = np.zeros(T)
        for j in self.jobs:
            default_flex += j.profile(j.default)
        pump_avg = (self.water.mean() / self.tank.pump_m3 * self.tank.pump_kw) if self.tank else 0.0
        self.r_fore = self.load - self.pv + default_flex + pump_avg
        self.noncrit_fore = np.maximum(self.load + default_flex - self.crit, 0)
        self.ctg = CostToGo(self.bat, self.r_fore, self.pi, self.pe, day.term_value, self.gridup, self.noncrit_fore,
                            self.voll_nc, self.voll_c)
        self.mp = self._marginal_prices()
        self.wv = water_value(campus, day, i)
        self.e = self.bat.e0
        self.started: dict[str, int] = {}
        self.running = np.zeros(T)
        self.dg_run = 0
        self.level = self.tank.level0 if self.tank else 0.0
        self.pump_prev = False
        self.hist = {"p_bat": np.zeros(T), "dg_kw": np.zeros(T), "pump_on": np.zeros(T)}

    # ------------------------------------------------------------------ helpers
    def _cost(self, t, r):
        return slot_cost(r, self.pi[t], self.pe[t], bool(self.gridup[t]), self.noncrit_fore[t], self.voll_nc, self.voll_c)

    def _marginal_prices(self) -> np.ndarray:
        mp = np.empty(T)
        e = self.bat.e0
        for t in range(T):
            # islanded: the marginal kWh is worth VOLL_c once the deficit exceeds the sheddable (non-critical) load
            hi_p = self.pi[t] if self.gridup[t] else (self.voll_c if self.r_fore[t] > self.noncrit_fore[t] else self.voll_nc)
            lo_p = self.pe[t] if self.gridup[t] else 0.0
            if not self.bat.present:
                mp[t] = hi_p if self.r_fore[t] > 0 else lo_p
                continue
            lo, hi = safety.battery_limits(self.bat, e)
            cand = np.linspace(lo, hi, 41)
            c = self._cost(t, self.r_fore[t] + cand) + self.ctg(t + 1, self.bat.step(e, cand))
            p = float(cand[int(np.argmin(c))])
            e1 = float(self.bat.step(e, p))
            w = -(self.ctg(t + 1, e1 + 0.5) - self.ctg(t + 1, e1 - 0.5))
            if lo + 1e-6 < p < hi - 1e-6:
                mp[t] = float(np.clip(w / self.bat.eta_dis if p <= 0 else w * self.bat.eta_ch, lo_p, hi_p))
            else:
                mp[t] = hi_p if self.r_fore[t] + p > 0 else lo_p
            e = e1
        return mp

    def pending_jobs(self):
        return [j for j in self.jobs if j.name not in self.started]

    def dg_allowed(self, t: int, H: int) -> bool:
        for r in self.rules:
            if r["type"] == "dg_forbid":
                outage_now = not self.gridup[t:t + H].all()
                if not (r.get("unless_outage", True) and outage_now):
                    return False
        return True

    def _tank_rule(self, t: int):
        for r in self.rules:
            if r["type"] == "tank_min_by" and self.tank is not None and t <= r["by_slot"]:
                return r
        return None

    # ------------------------------------------------------------------ problem construction
    def local_problem(self, t: int, free_lines, fixed_out: float = 0.0, v: dict | None = None,
                      rho: float = 0.0) -> Q.LocalProblem:
        H = min(self.H, T - t)
        sl = slice(t, t + H)
        r0 = self.load[sl] - self.pv[sl] + self.running[sl]
        noncrit = np.maximum(self.load[sl] - self.crit[sl] + self.running[sl], 0)
        rr = r0 + fixed_out
        P = self.bat.kw
        extra = self.F if free_lines else 0.0
        surplus, deficit = np.maximum(-rr, 0), np.maximum(rr, 0)
        pc = np.where(surplus >= 0.1 * P, np.minimum(surplus + extra, P), P) if self.bat.present else None
        pd = np.where(deficit >= 0.1 * P, np.minimum(deficit + extra, P), P) if self.bat.present else None
        ctg = (0.0, 0.0, 0.0)
        if self.bat.present:
            qc, qd = self.bat.eta_ch * P * DT, P * DT / self.bat.eta_dis
            ctg = self.ctg.quad_fit(t + H, max(self.bat.e_min, self.e - H * qd), min(self.bat.e_max, self.e + H * qc))
        jobs = []
        for j in self.pending_jobs():
            if t < j.earliest:
                continue
            must = t >= j.latest
            end = t + j.slots
            tail = float((self.mp[min(t + H, end):end] * j.kw * DT).sum())
            now = float((self.mp[t:min(t + H, end)] * j.kw * DT).sum())
            costs = [float((self.mp[tau:tau + j.slots] * j.kw * DT).sum()) for tau in range(t + 1, j.latest + 1)]
            defer = (min(costs) if costs else tail) + 1e-3 * j.kw * j.slots * DT
            jobs.append(Q.FlexState(j.name, j.kw, j.slots, True, must, tail, defer, now, j.latest))
        dg = None
        rule_terms: list[dict] = []
        if self.dg is not None:
            q = np.clip(deficit + extra, self.dg.p_min, self.dg.kw)
            litres = float(((self.dg.fuel_a * self.dg.kw + self.dg.fuel_b * q) * DT).sum())
            fuel = litres * (self.dg.price + self.lam_ef * self.dg.co2_per_l)
            forced = 0 < self.dg_run < self.dg.min_on_slots
            dg = Q.DGState(q, fuel, forced, True)
            if not forced and not self.dg_allowed(t, H):
                rule_terms.append({"id": next(r["id"] for r in self.rules if r["type"] == "dg_forbid"),
                                   "var": "g", "coef": 10.0 * fuel + 1000.0})
        tank = None
        if self.tank is not None:
            tk = self.tank
            dem = self.water[sl]
            forced = None
            if self.level - dem[0] < tk.l_min:
                forced = 1
            elif self.level + tk.pump_m3 - dem[0] > tk.l_max:
                forced = 0
            target, wgt = None, 0.0
            rule = self._tank_rule(t)
            if rule is not None:
                target = rule["level_frac"] * tk.capacity
                need = target - (self.level - self.water[t:rule["by_slot"]].sum())
                slots_left = max(rule["by_slot"] - t, 1)
                if forced is None and need > 0 and need / tk.pump_m3 >= slots_left - 1:
                    forced = 1   # safety: otherwise the operator's target becomes unreachable
                wgt = 5.0 * float(self.pi.mean()) * tk.pump_kw * DT
            tank = Q.TankState(self.level, dem, tk.pump_kw, tk.pump_m3, tk.l_min, tk.l_max, self.wv, forced, target, wgt)
        return Q.LocalProblem(t=t, bat=self.bat, e_now=self.e, r0=r0, pi=self.pi[sl], pe=self.pe[sl],
                              lines=list(free_lines), F=self.F, fixed_out=fixed_out, v=v or {}, rho=rho, ctg=ctg,
                              jobs=jobs, dg=dg, tank=tank, grid=self.gridup[sl], noncrit=noncrit,
                              voll_nc=self.voll_nc, voll_c=self.voll_c, pc=pc, pd=pd, rule_terms=rule_terms)

    def critical_shortfall(self, t: int, outflow_kw: float) -> float:
        """Upper bound check used by the safety layer in islanded slots: critical kW that could not be served
        even with full battery discharge and full DG output, given the agreed outflow."""
        if self.gridup[t]:
            return 0.0
        dis = -safety.battery_limits(self.bat, self.e)[0] if self.bat.present else 0.0
        dg = self.dg.kw if (self.dg is not None and self.dg_allowed(t, 1)) else 0.0
        deficit = self.load[t] + self.running[t] + outflow_kw - self.pv[t] - dis - dg
        noncrit = max(self.load[t] - self.crit[t] + self.running[t], 0)
        return max(0.0, deficit - noncrit)

    # ------------------------------------------------------------------ apply slot t
    def apply(self, t: int, dec: dict, outflow_kw: float) -> dict:
        """Commit flex starts, pump and DG on/off (through the safety layer) and the agreed flows; dispatch
        battery power and DG output continuously (exact slot cost + fuel + cost-to-go); update state."""
        starts = dec.get("starts", {})
        for j in self.pending_jobs():
            if safety.flex_decision(j, t, False, starts.get(j.name, False)):
                self.started[j.name] = t
                self.running += j.profile(t)
        pump = False
        if self.tank is not None:
            pump = safety.pump_decision(self.tank, self.level, self.water[t], dec.get("pump_on", False))
            rule = self._tank_rule(t)
            if rule is not None:
                need = rule["level_frac"] * self.tank.capacity - (self.level - self.water[t:rule["by_slot"]].sum())
                if need > 0 and need / self.tank.pump_m3 >= max(rule["by_slot"] - t, 1) - 1:
                    pump = pump or (self.level + self.tank.pump_m3 - self.water[t] <= self.tank.l_max)
        dg_on = False
        if self.dg is not None:
            dg_on = safety.dg_decision(self.dg, dec.get("dg_on", False), self.dg_run, self.dg_allowed(t, 1))
        r_now = self.load[t] - self.pv[t] + self.running[t] + outflow_kw + (self.tank.pump_kw if pump else 0.0)
        if self.bat.present:
            lo, hi = safety.battery_limits(self.bat, self.e)
            pb = np.append(np.linspace(lo, hi, 41), 0.0)
        else:
            pb = np.array([0.0])
        pg = np.linspace(self.dg.p_min, self.dg.kw, 8) if dg_on else np.array([0.0])
        PB, PG = np.meshgrid(pb, pg, indexing="ij")
        nc = max(self.load[t] - self.crit[t] + self.running[t], 0)
        cost = slot_cost(r_now + PB - PG, self.pi[t], self.pe[t], bool(self.gridup[t]), nc, self.voll_nc, self.voll_c)
        if dg_on:
            cost = cost + self.dg.litres(1, PG) * (self.dg.price + self.lam_ef * self.dg.co2_per_l)
        if self.bat.present:
            cost = cost + self.ctg(t + 1, self.bat.step(self.e, PB))
        k = np.unravel_index(int(np.argmin(cost)), cost.shape)
        p = safety.clamp_battery(self.bat, self.e, float(PB[k])) if self.bat.present else 0.0
        g = float(PG[k])
        if self.bat.present:
            self.e = float(self.bat.step(self.e, p))
        self.dg_run = self.dg_run + 1 if dg_on else 0
        if self.tank is not None:
            self.level += (self.tank.pump_m3 if pump else 0.0) - self.water[t]
        self.pump_prev = pump
        self.hist["p_bat"][t], self.hist["dg_kw"][t], self.hist["pump_on"][t] = p, g, float(pump)
        return {"p_bat": p, "dg_kw": g, "pump_on": pump, "e": self.e, "qubo_mode": dec.get("mode0", 0)}

    def apply_safe_default(self, t: int, outflow_kw: float = 0.0) -> dict:
        """Status-quo / offline behaviour: flexible loads at default time (or forced), float-switch pump,
        battery only as UPS during an outage, DG only during an outage (with min on-time)."""
        for j in self.pending_jobs():
            if t == j.default or t >= j.latest:
                self.started[j.name] = t
                self.running += j.profile(t)
        pump = False
        if self.tank is not None:
            pump = safety.pump_decision(self.tank, self.level, self.water[t],
                                        safety.float_switch(self.tank, self.level, self.pump_prev))
        r = self.load[t] - self.pv[t] + self.running[t] + outflow_kw + (self.tank.pump_kw if pump else 0.0)
        g = 0.0
        if self.dg is not None:
            on = safety.dg_decision(self.dg, (not self.gridup[t]) and r > 0, self.dg_run, True)
            g = float(np.clip(r, self.dg.p_min, self.dg.kw)) if on else 0.0
            self.dg_run = self.dg_run + 1 if on else 0
        p = 0.0
        if self.bat.present and not self.gridup[t] and r - g > 0:
            p = safety.clamp_battery(self.bat, self.e, -(r - g))
            self.e = float(self.bat.step(self.e, p))
        if self.tank is not None:
            self.level += (self.tank.pump_m3 if pump else 0.0) - self.water[t]
        self.pump_prev = pump
        self.hist["p_bat"][t], self.hist["dg_kw"][t], self.hist["pump_on"][t] = p, g, float(pump)
        return {"p_bat": p, "dg_kw": g, "pump_on": pump, "e": self.e}
