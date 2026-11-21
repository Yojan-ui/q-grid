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
        self.mp = np.where(self.r_fore > 0, self.pi, self.pe)   # forecast marginal price
        self.ctg = CostToGo(self.bat, self.load - self.pv + default_flex, self.pi, self.pe, day.term_value)
        self.e = self.bat.e0
        self.started: dict[str, int] = {}
        self.running = np.zeros(T)
        self.p_hist = np.zeros(T)

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
        defer = 0.0
        if not must:
            costs = [float((self.mp[tau:tau + j.slots] * j.kw * DT).sum()) for tau in range(t + 1, j.latest + 1)]
            defer = min(costs) if costs else tail
        return Q.FlexState(j.kw, j.slots, can_start=True, must_start=must, tail_cost=tail, defer_cost=defer)

    def local_problem(self, t: int, free_lines: list[tuple[int, int]], fixed_out: float = 0.0,
                      v: dict | None = None, rho: float = 0.0) -> Q.LocalProblem:
        H = min(self.H, T - t)
        r0 = self.load[t:t + H] - self.pv[t:t + H] + self.running[t:t + H]
        qc = self.bat.eta_ch * self.bat.kw * DT
        qd = self.bat.kw * DT / self.bat.eta_dis
        lo = max(self.bat.e_min, self.e - H * qd)
        hi = min(self.bat.e_max, self.e + H * qc)
        return Q.LocalProblem(t=t, bat=self.bat, e_now=self.e, r0=r0, pi=self.pi[t:t + H], pe=self.pe[t:t + H],
                              lines=list(free_lines), F=self.F, fixed_out=fixed_out, v=v or {}, rho=rho,
                              ctg=self.ctg.quad_fit(t + H, lo, hi), flex=self.flex_state(t, H))

    # ------------------------------------------------------------------ apply slot 0
    def apply(self, t: int, mode: int, want_start: bool, outflow_kw: float) -> dict:
        """Apply slot t: flex decision (safety), battery magnitude refinement within the chosen mode,
        safety clamp, state update. Returns the applied commands."""
        j = self.pending_job()
        start = False
        if j is not None:
            start = safety.flex_decision(j, t, False, want_start)
            if start:
                self.started[j.name] = t
                self.running += j.profile(t)
        r_now = self.load[t] - self.pv[t] + self.running[t] + outflow_kw
        lo, hi = safety.battery_limits(self.bat, self.e)
        if mode > 0:
            cand = np.linspace(0, hi, 41)
        elif mode < 0:
            cand = np.linspace(lo, 0, 41)
        else:
            cand = np.array([0.0])
        if mode != 0 and lo <= -r_now <= hi and np.sign(-r_now) == mode:
            cand = np.append(cand, -r_now)
        cost = slot_cost(r_now + cand, self.pi[t], self.pe[t]) + self.ctg(t + 1, self.bat.step(self.e, cand))
        p = safety.clamp_battery(self.bat, self.e, float(cand[int(np.argmin(cost))]))
        self.e = float(self.bat.step(self.e, p))
        self.p_hist[t] = p
        return {"p_bat": p, "start": start, "e": self.e}

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
