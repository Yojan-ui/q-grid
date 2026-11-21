"""BuildingAgent: one building's controller. Holds ONLY its own private data (PV, load, battery,
flexible loads, cost-to-go) plus public prices; talks to neighbours only through tie-line proposals."""
from __future__ import annotations

import numpy as np

from . import qubo as Q
from . import safety
from .costtogo import CostToGo
from .model import DT, T, Campus, DayData, slot_cost


class BuildingAgent:
    def __init__(self, campus: Campus, day: DayData, i: int, horizon: int = 4):
        b = campus.buildings[i]
        self.i, self.name, self.H = i, b.name, horizon
        self.bat, self.jobs = b.battery, list(b.flex)
        self.pv, self.load = day.pv[i].copy(), day.load[i].copy()
        self.pi, self.pe = day.obj_imp.copy(), day.price_exp.copy()
        self.incident = campus.incident(i)
        self.F = campus.step_kw
        default_flex = np.zeros(T)
        for j in self.jobs:
            default_flex += j.profile(j.default)
        self.r_fore = self.load - self.pv + default_flex
        self.ctg = CostToGo(self.bat, self.load - self.pv + default_flex, self.pi, self.pe, day.term_value)
        self.mp = self._marginal_prices()   # forecast marginal cost of energy per slot (Rs/kWh)
        self.e = self.bat.e0
        self.started: dict[str, int] = {}
        self.running = np.zeros(T)
        self.p_hist = np.zeros(T)

    def _marginal_prices(self) -> np.ndarray:
        """Marginal cost of one extra kWh at each slot along the DP-optimal battery trajectory:
        clip(battery marginal value, export price, import price) - the battery is the marginal
        resource when it is active, otherwise the grid price on the relevant side."""
        mp = np.empty(T)
        e = self.bat.e0
        d = 0.5
        for t in range(T):
            lo, hi = safety.battery_limits(self.bat, e)
            cand = np.linspace(lo, hi, 41)
            c = slot_cost(self.r_fore[t] + cand, self.pi[t], self.pe[t]) + self.ctg(t + 1, self.bat.step(e, cand))
            p = float(cand[int(np.argmin(c))])
            e1 = float(self.bat.step(e, p))
            w = -(self.ctg(t + 1, e1 + d) - self.ctg(t + 1, e1 - d)) / (2 * d)   # Rs per stored kWh
            r = self.r_fore[t] + p
            if lo + 1e-6 < p < hi - 1e-6:          # battery interior -> it absorbs the marginal kWh
                mp[t] = float(np.clip(w / self.bat.eta_dis if p <= 0 else w * self.bat.eta_ch, self.pe[t], self.pi[t]))
            else:
                mp[t] = self.pi[t] if r > 0 else self.pe[t]
            e = e1
        return mp

    # ------------------------------------------------------------------ problem construction
    def pending_job(self):
        for j in self.jobs:
            if j.name not in self.started:
                return j
        return None

    def flex_state(self, t: int, H: int) -> Q.FlexState | None:
        j = self.pending_job()
        if j is None or t < j.earliest:
            return None
        must = t >= j.latest
        end = t + j.slots
        tail = float((self.mp[min(t + H, end):end] * j.kw * DT).sum())
        now = float((self.mp[t:min(t + H, end)] * j.kw * DT).sum())
        defer = 0.0
        if not must:
            costs = [float((self.mp[tau:tau + j.slots] * j.kw * DT).sum()) for tau in range(t + 1, j.latest + 1)]
            defer = (min(costs) if costs else tail) + 1e-3 * j.kw * j.slots * DT  # tie -> start now
        return Q.FlexState(j.kw, j.slots, can_start=True, must_start=must, tail_cost=tail, defer_cost=defer,
                           now_cost=now)

    def local_problem(self, t: int, free_lines: list[tuple[int, int]], fixed_out: float = 0.0,
                      v: dict | None = None, rho: float = 0.0) -> Q.LocalProblem:
        H = min(self.H, T - t)
        r0 = self.load[t:t + H] - self.pv[t:t + H] + self.running[t:t + H]
        qc = self.bat.eta_ch * self.bat.kw * DT
        qd = self.bat.kw * DT / self.bat.eta_dis
        lo = max(self.bat.e_min, self.e - H * qd)
        hi = min(self.bat.e_max, self.e + H * qc)
        P = self.bat.kw
        rr = r0 + fixed_out
        extra = self.F if free_lines else 0.0   # room to store / supply one tie-line step
        surplus, deficit = np.maximum(-rr, 0), np.maximum(rr, 0)
        pc = np.where(surplus >= 0.1 * P, np.minimum(surplus + extra, P), P)
        pd = np.where(deficit >= 0.1 * P, np.minimum(deficit + extra, P), P)
        return Q.LocalProblem(t=t, bat=self.bat, e_now=self.e, r0=r0, pi=self.pi[t:t + H], pe=self.pe[t:t + H],
                              lines=list(free_lines), F=self.F, fixed_out=fixed_out, v=v or {}, rho=rho,
                              ctg=self.ctg.quad_fit(t + H, lo, hi), flex=self.flex_state(t, H), pc=pc, pd=pd)

    # ------------------------------------------------------------------ apply slot 0
    def apply(self, t: int, mode: int, want_start: bool, outflow_kw: float) -> dict:
        """Apply slot t: committed flex decision (through the safety layer) and agreed tie-line flows;
        the battery set-point is dispatched by a continuous local step over its full feasible range
        (exact slot cost + cost-to-go); the QUBO's battery bits are planning variables for the hour.
        `mode` (the QUBO's slot-0 battery mode) is recorded only. Safety clamp, state update."""
        j = self.pending_job()
        start = False
        if j is not None:
            start = safety.flex_decision(j, t, False, want_start)
            if start:
                self.started[j.name] = t
                self.running += j.profile(t)
        r_now = self.load[t] - self.pv[t] + self.running[t] + outflow_kw
        lo, hi = safety.battery_limits(self.bat, self.e)
        cand = np.append(np.linspace(lo, hi, 81), 0.0)
        if lo <= -r_now <= hi:
            cand = np.append(cand, -r_now)
        cost = slot_cost(r_now + cand, self.pi[t], self.pe[t]) + self.ctg(t + 1, self.bat.step(self.e, cand))
        p = safety.clamp_battery(self.bat, self.e, float(cand[int(np.argmin(cost))]))
        self.e = float(self.bat.step(self.e, p))
        self.p_hist[t] = p
        return {"p_bat": p, "start": start, "e": self.e, "qubo_mode": mode}

    def apply_safe_default(self, t: int) -> dict:
        """Controller offline / killed: battery idle, flexible load at its status-quo time (or forced)."""
        j = self.pending_job()
        start = False
        if j is not None and (t == j.default or t >= j.latest):
            start = True
            self.started[j.name] = t
            self.running += j.profile(t)
        self.p_hist[t] = 0.0
        return {"p_bat": 0.0, "start": start, "e": self.e}
