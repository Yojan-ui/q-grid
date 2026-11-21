"""Campus model: buildings, batteries, flexible loads, tie-lines; settlement and feasibility.

Every method (B0..B5, OURS) produces a `Schedule`; `settle()` computes cost/CO2/metrics with the
same rules and `check_feasibility()` audits it, so all methods are compared identically.

Sign conventions
  battery p_bat[t] > 0 charging, < 0 discharging (kW at the battery terminals)
  line flow f[l, t] > 0 means power flows lines[l][0] -> lines[l][1]
  building net[t] = load + flex + p_bat + outflows - inflows - pv   (> 0 import, < 0 export)
Terminal SoC: all methods are scored with the same terminal adjustment
  cost += term_value * (e0 - e_end) summed over buildings, term_value = day's mean import price,
so leftover / borrowed battery energy is valued identically for every method.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import data as qdata

DT = 0.25
T = 96


def hhmm_to_slot(s: str) -> int:
    return (int(s[:2]) * 60 + int(s[3:])) // 15


@dataclass
class Battery:
    kwh: float
    kw: float
    soc_min: float
    soc_max: float
    soc0: float
    eta_ch: float
    eta_dis: float

    @property
    def e_min(self): return self.soc_min * self.kwh
    @property
    def e_max(self): return self.soc_max * self.kwh
    @property
    def e0(self): return self.soc0 * self.kwh

    def step(self, e: float | np.ndarray, p: float | np.ndarray):
        """Energy after one slot at battery power p (kW)."""
        return e + (self.eta_ch * np.maximum(p, 0) + np.minimum(p, 0) / self.eta_dis) * DT


@dataclass
class FlexJob:
    name: str
    kw: float
    slots: int
    earliest: int
    latest: int
    default: int

    def profile(self, start: int) -> np.ndarray:
        x = np.zeros(T)
        x[start:start + self.slots] = self.kw
        return x


@dataclass
class Building:
    name: str
    pv_kwp: float
    peak_kw: float
    critical_frac: float
    battery: Battery
    flex: list[FlexJob]


@dataclass
class Campus:
    buildings: list[Building]
    lines: list[tuple[int, int]]
    step_kw: float
    cfg: dict = field(repr=False, default_factory=dict)

    @property
    def names(self): return [b.name for b in self.buildings]
    @property
    def n(self): return len(self.buildings)

    def incident(self, i: int) -> list[tuple[int, int]]:
        """(line index, sign) where sign=+1 if flow on the line is an outflow of building i."""
        out = []
        for l, (a, b) in enumerate(self.lines):
            if a == i:
                out.append((l, +1))
            elif b == i:
                out.append((l, -1))
        return out

    def neighbours(self, i: int) -> list[int]:
        return [b if a == i else a for (a, b) in self.lines if i in (a, b)]


def load_campus(cfg: dict | None = None) -> Campus:
    cfg = cfg or qdata.load_config()
    bd = cfg["battery_defaults"]
    blds = []
    for name, s in cfg["buildings"].items():
        bat = Battery(kwh=s["battery"]["kwh"], kw=s["battery"]["kw"], **bd)
        jobs = [FlexJob(j["name"], j["kw"], j["slots"], hhmm_to_slot(j["earliest"]),
                        min(hhmm_to_slot(j["latest"]), T - j["slots"]), hhmm_to_slot(j["default"]))
                for j in s.get("flex", [])]
        blds.append(Building(name, s["pv_kwp"], s["peak_kw"], s["critical_frac"], bat, jobs))
    names = [b.name for b in blds]
    lines = [(names.index(a), names.index(b)) for a, b in cfg["tie_lines"]["lines"]]
    return Campus(blds, lines, float(cfg["tie_lines"]["step_kw"]), cfg)


@dataclass
class DayData:
    day: str
    scenario: str
    pv: np.ndarray          # (n, T) kW
    load: np.ndarray        # (n, T) kW, inflexible load (Ausgrid-derived)
    price_imp: np.ndarray   # (T,) Rs/kWh (incl. carbon shadow price if lambda > 0 is applied in objective)
    price_exp: np.ndarray   # (T,)
    ef: float               # kg CO2 / kWh
    lam: float              # Rs / kg CO2 shadow price used in optimisation objectives
    status: dict            # data status flags (REAL / PENDING)

    @property
    def term_value(self) -> float:
        return float(self.price_imp.mean())

    @property
    def obj_imp(self) -> np.ndarray:
        """Import price used by optimisers (tariff + carbon shadow price)."""
        return self.price_imp + self.lam * self.ef


def make_day(campus: Campus, processed: dict, day: str, scenario: str) -> DayData:
    pv = qdata.day_slice(processed["pv"], day)[campus.names].to_numpy().T
    load = qdata.day_slice(processed["load"], day)[campus.names].to_numpy().T
    pr = qdata.day_slice(processed["price"], day)
    meta = processed["meta"]
    return DayData(day, scenario, pv, load, pr[f"{scenario}_import"].to_numpy(), pr[f"{scenario}_export"].to_numpy(),
                   float(meta["co2"]["tco2_per_mwh"]), float(campus.cfg["co2"]["lambda_rs_per_kg"]),
                   {**meta["data_status"], "price_scenario": meta["prices"][scenario]["status"]})


@dataclass
class Schedule:
    p_bat: np.ndarray                 # (n, T)
    flex_start: list[dict[str, int]]  # per building: job name -> start slot
    flows: np.ndarray                 # (n_lines, T)
    info: dict = field(default_factory=dict)

    @staticmethod
    def empty(campus: Campus) -> "Schedule":
        return Schedule(np.zeros((campus.n, T)), [dict() for _ in campus.buildings],
                        np.zeros((len(campus.lines), T)))


def flex_load(campus: Campus, sched: Schedule) -> np.ndarray:
    out = np.zeros((campus.n, T))
    for i, b in enumerate(campus.buildings):
        for j in b.flex:
            s = sched.flex_start[i].get(j.name, j.default)
            out[i] += j.profile(s)
    return out


def net_power(campus: Campus, day: DayData, sched: Schedule) -> np.ndarray:
    net = day.load + flex_load(campus, sched) + sched.p_bat - day.pv
    for l, (a, b) in enumerate(campus.lines):
        net[a] += sched.flows[l]
        net[b] -= sched.flows[l]
    return net


def soc_trajectory(bat: Battery, p: np.ndarray) -> np.ndarray:
    e = np.empty(T + 1)
    e[0] = bat.e0
    for t in range(T):
        e[t + 1] = bat.step(e[t], p[t])
    return e


def slot_cost(r: np.ndarray, pi: np.ndarray, pe: np.ndarray) -> np.ndarray:
    """Grid settlement per slot (Rs) for net power r (kW)."""
    return (pi * np.maximum(r, 0) - pe * np.maximum(-r, 0)) * DT


def settle(campus: Campus, day: DayData, sched: Schedule) -> dict:
    net = net_power(campus, day, sched)
    imp, exp = np.maximum(net, 0), np.maximum(-net, 0)
    energy_cost = float((imp * day.price_imp - exp * day.price_exp).sum() * DT)
    e_end = np.array([soc_trajectory(b.battery, sched.p_bat[i])[-1] for i, b in enumerate(campus.buildings)])
    e0 = np.array([b.battery.e0 for b in campus.buildings])
    term_adj = float(day.term_value * (e0 - e_end).sum())
    imp_kwh = float(imp.sum() * DT)
    pv_kwh = float(day.pv.sum() * DT)
    return {
        "cost_rs": energy_cost + term_adj,
        "energy_cost_rs": energy_cost,
        "terminal_adj_rs": term_adj,
        "co2_kg": imp_kwh * day.ef,
        "import_kwh": imp_kwh,
        "export_kwh": float(exp.sum() * DT),
        "peak_import_kw": float(imp.sum(axis=0).max()),
        "self_consumption_pct": 100.0 * (1 - float(exp.sum() * DT) / pv_kwh) if pv_kwh > 0 else 100.0,
        "net_kw": net,
    }


def check_feasibility(campus: Campus, sched: Schedule, tol: float = 1e-6) -> dict:
    """Audit every hard constraint. Returns violations and the per-(building, slot) feasibility rate."""
    viol = []
    ok = np.ones((campus.n, T), dtype=bool)
    for i, b in enumerate(campus.buildings):
        bat = b.battery
        p = sched.p_bat[i]
        bad_p = np.abs(p) > bat.kw + tol
        e = soc_trajectory(bat, p)
        bad_e = (e[1:] < bat.e_min - 1e-3) | (e[1:] > bat.e_max + 1e-3)
        for t in np.nonzero(bad_p | bad_e)[0]:
            viol.append(f"{b.name} slot {t}: battery p={p[t]:.2f} e={e[t + 1]:.2f}")
        ok[i] &= ~(bad_p | bad_e)
        for j in b.flex:
            s = sched.flex_start[i].get(j.name, j.default)
            if s != j.default and not (j.earliest <= s <= j.latest):
                viol.append(f"{b.name}/{j.name}: start {s} outside window [{j.earliest},{j.latest}]")
                ok[i] = False
    bad_f = np.abs(sched.flows) > campus.step_kw + tol
    for l, t in zip(*np.nonzero(bad_f)):
        a, c = campus.lines[l]
        viol.append(f"line {campus.names[a]}-{campus.names[c]} slot {t}: |f|={abs(sched.flows[l, t]):.1f}")
        ok[a, t] = ok[c, t] = False
    # critical load: grid-connected buildings always serve critical load (no shedding is modelled);
    # flagged here so a future islanded-without-grid mode is audited too.
    return {"feasible": not viol, "violations": viol[:20], "feasibility_rate": float(ok.mean())}
