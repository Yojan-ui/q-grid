"""Campus model (zones, batteries, diesel generators, water tanks, flexible loads, tie-lines) with one
settlement and one feasibility audit shared by every method.

Sign conventions
  battery p_bat > 0 charging, < 0 discharging (kW)          DG dg_kw >= 0 output (kW, on iff > 0)
  line flow f[l] > 0: power flows lines[l][0] -> lines[l][1]  pump_on in {0,1}
  zone net = load + flex + pump + p_bat + outflows - inflows - pv - dg   (> 0 deficit, < 0 surplus)
Grid available: deficit imported at the import price, surplus exported at the export price.
Grid outage (island): deficit is unserved (non-critical first, then critical), surplus is spilled.
Money cost = grid energy + diesel fuel + terminal adjustment (battery energy and tank water valued at the
day's mean import price). Optimisers additionally minimise value-of-lost-load (VOLL, an ASSUMPTION) and
critical-load downtime is reported separately.
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
    @property
    def present(self) -> bool: return self.kw > 0 and self.kwh > 0

    def step(self, e, p):
        return e + (self.eta_ch * np.maximum(p, 0) + np.minimum(p, 0) / self.eta_dis) * DT


@dataclass
class DG:
    kw: float
    min_load_frac: float
    min_on_slots: int
    fuel_a: float          # L/h per kW rated
    fuel_b: float          # L per kWh out
    price: float           # Rs/L
    co2_per_l: float

    @property
    def p_min(self): return self.min_load_frac * self.kw

    def litres(self, on, p):
        return (np.asarray(on, float) * self.fuel_a * self.kw + self.fuel_b * np.asarray(p, float)) * DT


@dataclass
class Tank:
    capacity: float
    level0: float
    l_min: float
    l_max: float
    pump_kw: float
    pump_m3: float          # per slot when running


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
class Building:  # a campus zone
    name: str
    pv_kwp: float
    critical_frac: float
    battery: Battery
    flex: list[FlexJob]
    dg: DG | None = None
    tank: Tank | None = None


@dataclass
class Campus:
    buildings: list[Building]
    lines: list[tuple[int, int]]
    step_kw: float
    cfg: dict = field(repr=False, default_factory=dict)
    layout: dict = field(repr=False, default_factory=dict)

    @property
    def names(self): return [b.name for b in self.buildings]
    @property
    def n(self): return len(self.buildings)

    def incident(self, i: int) -> list[tuple[int, int]]:
        out = []
        for l, (a, b) in enumerate(self.lines):
            if a == i:
                out.append((l, +1))
            elif b == i:
                out.append((l, -1))
        return out

    def neighbours(self, i: int) -> list[int]:
        return [b if a == i else a for (a, b) in self.lines if i in (a, b)]


def load_campus(cfg: dict | None = None, layout: dict | None = None) -> Campus:
    import json
    cfg = cfg or qdata.load_config()
    if layout is None:
        p = qdata.PROC / "campus.json"
        layout = json.loads(p.read_text()) if p.exists() else None
    bd = cfg["battery_defaults"]
    dsl = cfg["diesel"]
    blds = []
    for name, s in cfg["campus"]["zones"].items():
        b = s.get("battery", {"kwh": 0, "kw": 0})
        bat = Battery(kwh=float(b["kwh"]), kw=float(b["kw"]), **bd)
        jobs = [FlexJob(j["name"], j["kw"], j["slots"], hhmm_to_slot(j["earliest"]),
                        min(hhmm_to_slot(j["latest"]), T - j["slots"]), hhmm_to_slot(j["default"]))
                for j in s.get("flex", [])]
        dg = None
        if "dg" in s:
            g = s["dg"]
            dg = DG(g["kw"], g["min_load_frac"], g["min_on_slots"], dsl["fuel_l_per_kwh_rated"],
                    dsl["fuel_l_per_kwh_out"], dsl["price_rs_per_l"], dsl["co2_kg_per_l"])
        tank = None
        if "tank" in s:
            t = s["tank"]
            tank = Tank(t["capacity_m3"], t["level0_frac"] * t["capacity_m3"], t["min_frac"] * t["capacity_m3"],
                        t["max_frac"] * t["capacity_m3"], t["pump_kw"], t["pump_m3_per_slot"])
        pv = layout["zones"][name]["pv_kwp"] if layout else 0.0
        blds.append(Building(name, pv, s.get("critical_frac", 0.0), bat, jobs, dg, tank))
    names = [b.name for b in blds]
    lines = [(names.index(a), names.index(b)) for a, b in (layout["lines"] if layout else [])]
    return Campus(blds, lines, float(cfg["campus"]["tie_lines"]["step_kw"]), cfg, layout or {})


@dataclass
class DayData:
    day: str
    scenario: str                 # price scenario A / B
    pv: np.ndarray                # (n, T) kW
    load: np.ndarray              # (n, T) kW inflexible load
    crit: np.ndarray              # (n, T) kW critical part of load
    water: np.ndarray             # (T,) m3 per slot campus demand from tanks
    price_imp: np.ndarray
    price_exp: np.ndarray
    ef: float                     # kg CO2 / kWh grid
    lam: float                    # Rs / kg CO2 shadow price
    grid: np.ndarray              # (T,) bool grid available
    voll_nc: float
    voll_c: float
    status: dict
    scen_name: str = ""
    day_type: str = ""
    wear: float = 0.0             # Rs per kWh charged or discharged (battery wear), priced in the objective

    @property
    def term_value(self) -> float:
        return float(self.price_imp.mean())

    @property
    def obj_imp(self) -> np.ndarray:
        return self.price_imp + self.lam * self.ef


def make_day(campus: Campus, processed: dict, day: str, scenario: str, scen_name: str = "",
             outage: list[str] | None = None) -> DayData:
    sl = lambda df: qdata.day_slice(df, day)  # noqa: E731
    pv = sl(processed["pv"])[campus.names].to_numpy().T
    load = sl(processed["load"])[campus.names].to_numpy().T
    crit = sl(processed["crit"])[campus.names].to_numpy().T
    water = sl(processed["water"]).to_numpy()
    pr = sl(processed["price"])
    meta = processed["meta"]
    grid = np.ones(T, dtype=bool)
    if outage:
        a, b = hhmm_to_slot(outage[0]), hhmm_to_slot(outage[1])
        grid[a:b] = False
    oc = campus.cfg["outage_costs"]
    dtype = ""
    for v in meta["days"]["scenarios"].values():
        if v["date"] == day:
            dtype = v["day_type"]
    return DayData(day, scenario, pv, load, crit, water, pr[f"{scenario}_import"].to_numpy(),
                   pr[f"{scenario}_export"].to_numpy(), float(meta["co2"]["tco2_per_mwh"]),
                   float(campus.cfg["co2"]["lambda_rs_per_kg"]), grid, float(oc["voll_noncritical_rs_kwh"]),
                   float(oc["voll_critical_rs_kwh"]),
                   {**meta["data_status"], "price_scenario": meta["prices"][scenario]["status"]}, scen_name, dtype,
                   wear_rate(campus.cfg))


def wear_rate(cfg: dict) -> float:
    """Battery wear in Rs per kWh charged or discharged = capex / (2 x cycle life x depth of discharge) (economics block,
    ASSUMPTIONS), when config battery_wear.in_objective is true; 0 otherwise. The same rate is the scorecard's degradation
    metric, so what the optimisers price and what the scorecard reports agree."""
    bw = cfg.get("battery_wear", {})
    if not bw.get("in_objective", False):
        return 0.0
    e = cfg["economics"]
    return float(e["battery_capex_rs_per_kwh"]) / (2 * float(e["battery_cycle_life"]) * float(bw.get("depth_of_discharge", 0.75)))


@dataclass
class Schedule:
    p_bat: np.ndarray
    flex_start: list[dict[str, int]]
    flows: np.ndarray
    dg_kw: np.ndarray
    pump_on: np.ndarray
    info: dict = field(default_factory=dict)

    @staticmethod
    def empty(campus: Campus) -> "Schedule":
        n = campus.n
        return Schedule(np.zeros((n, T)), [dict() for _ in campus.buildings], np.zeros((len(campus.lines), T)),
                        np.zeros((n, T)), np.zeros((n, T)))


def flex_load(campus: Campus, sched: Schedule) -> np.ndarray:
    out = np.zeros((campus.n, T))
    for i, b in enumerate(campus.buildings):
        for j in b.flex:
            out[i] += j.profile(sched.flex_start[i].get(j.name, j.default))
    return out


def pump_load(campus: Campus, sched: Schedule) -> np.ndarray:
    out = np.zeros((campus.n, T))
    for i, b in enumerate(campus.buildings):
        if b.tank:
            out[i] = sched.pump_on[i] * b.tank.pump_kw
    return out


def net_power(campus: Campus, day: DayData, sched: Schedule) -> np.ndarray:
    net = day.load + flex_load(campus, sched) + pump_load(campus, sched) + sched.p_bat - day.pv - sched.dg_kw
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


def tank_trajectory(tank: Tank, pump_on: np.ndarray, demand: np.ndarray) -> np.ndarray:
    lv = np.empty(T + 1)
    lv[0] = tank.level0
    for t in range(T):
        lv[t + 1] = lv[t] + pump_on[t] * tank.pump_m3 - demand[t]
    return lv


def slot_cost(r, pi, pe, grid: bool = True, noncrit=0.0, voll_nc=0.0, voll_c=0.0):
    """Exact per-slot cost (Rs) of zone net power r (kW): tariff when grid is up; VOLL when islanded."""
    r = np.asarray(r, float)
    if grid:
        return (pi * np.maximum(r, 0) - pe * np.maximum(-r, 0)) * DT
    d = np.maximum(r, 0)
    nc = np.minimum(d, noncrit)
    return (voll_nc * nc + voll_c * (d - nc)) * DT


def water_value(campus: Campus, day: DayData, i: int) -> float:
    """Rs per m3 stored: pumping energy avoided later, at the day's mean import price."""
    t = campus.buildings[i].tank
    return day.term_value * t.pump_kw * DT / t.pump_m3 if t else 0.0


def settle(campus: Campus, day: DayData, sched: Schedule) -> dict:
    net = net_power(campus, day, sched)
    g = day.grid[None, :]
    imp = np.where(g, np.maximum(net, 0), 0.0)
    exp = np.where(g, np.maximum(-net, 0), 0.0)
    deficit = np.where(g, 0.0, np.maximum(net, 0))
    spill = np.where(g, 0.0, np.maximum(-net, 0))
    demand = day.load + flex_load(campus, sched) + pump_load(campus, sched)
    noncrit = np.maximum(demand - day.crit, 0)
    shed_nc = np.minimum(deficit, noncrit)
    shed_c = deficit - shed_nc
    energy_cost = float((imp * day.price_imp - exp * day.price_exp).sum() * DT)
    litres = fuel = dg_co2 = dg_hours = 0.0
    for i, b in enumerate(campus.buildings):
        if b.dg:
            on = sched.dg_kw[i] > 1e-9
            L = float(b.dg.litres(on, sched.dg_kw[i]).sum())
            litres += L
            fuel += L * b.dg.price
            dg_co2 += L * b.dg.co2_per_l
            dg_hours += float(on.sum() * DT)
    e_end = np.array([soc_trajectory(b.battery, sched.p_bat[i])[-1] for i, b in enumerate(campus.buildings)])
    e0 = np.array([b.battery.e0 for b in campus.buildings])
    term = float(day.term_value * (e0 - e_end).sum())
    tank_end = {}
    for i, b in enumerate(campus.buildings):
        if b.tank:
            lv = tank_trajectory(b.tank, sched.pump_on[i], day.water)
            term += water_value(campus, day, i) * (b.tank.level0 - lv[-1])
            tank_end[b.name] = float(lv[-1])
    imp_kwh = float(imp.sum() * DT)
    pv_kwh = float(day.pv.sum() * DT)
    voll = float((day.voll_nc * shed_nc + day.voll_c * shed_c).sum() * DT)
    crit_slots = (shed_c > 1e-6).any(axis=0)
    wear = float(getattr(day, "wear", 0.0) * np.abs(sched.p_bat).sum() * DT)
    return {
        "cost_rs": energy_cost + fuel + term,
        "objective_rs": energy_cost + fuel + term + voll + wear, "wear_rs": wear,
        "energy_cost_rs": energy_cost, "fuel_cost_rs": fuel, "terminal_adj_rs": term, "voll_rs": voll,
        "co2_kg": imp_kwh * day.ef + dg_co2, "grid_co2_kg": imp_kwh * day.ef, "dg_co2_kg": dg_co2,
        "import_kwh": imp_kwh, "export_kwh": float(exp.sum() * DT), "spill_kwh": float(spill.sum() * DT),
        "dg_hours": dg_hours, "dg_litres": litres,
        "unserved_kwh": float(deficit.sum() * DT), "critical_unserved_kwh": float(shed_c.sum() * DT),
        "critical_downtime_h": float(crit_slots.sum() * DT),
        "peak_import_kw": float(imp.sum(axis=0).max()),
        "self_consumption_pct": 100.0 * (1 - float((exp.sum() + spill.sum()) * DT) / pv_kwh) if pv_kwh > 0 else 100.0,
        "tank_end_m3": tank_end, "net_kw": net,
    }


def check_feasibility(campus: Campus, sched: Schedule, day: DayData | None = None, tol: float = 1e-6) -> dict:
    """Audit hard constraints: battery power/SoC, flex windows, line ratings, DG min load / min on-time,
    tank levels (needs `day` for water demand). Critical-load shortfall in an outage is reported by
    settle() as downtime, not as infeasibility (it can be physically unavoidable)."""
    viol = []
    ok = np.ones((campus.n, T), dtype=bool)
    for i, b in enumerate(campus.buildings):
        bat, p = b.battery, sched.p_bat[i]
        if not bat.present:
            bad = np.abs(p) > tol
        else:
            e = soc_trajectory(bat, p)
            bad = (np.abs(p) > bat.kw + tol) | (e[1:] < bat.e_min - 1e-3) | (e[1:] > bat.e_max + 1e-3)
        for t in np.nonzero(bad)[0][:3]:
            viol.append(f"{b.name} slot {t}: battery p={p[t]:.2f}")
        ok[i] &= ~bad
        for j in b.flex:
            s = sched.flex_start[i].get(j.name, j.default)
            if s != j.default and not (j.earliest <= s <= j.latest):
                viol.append(f"{b.name}/{j.name}: start {s} outside [{j.earliest},{j.latest}]")
                ok[i] = False
        g = sched.dg_kw[i]
        if b.dg is None:
            if np.any(g > tol):
                viol.append(f"{b.name}: DG output without a DG"); ok[i] = False
        else:
            on = g > tol
            badg = on & ((g < b.dg.p_min - 1e-6) | (g > b.dg.kw + 1e-6))
            ok[i] &= ~badg
            if badg.any():
                viol.append(f"{b.name}: DG output outside [min load, rated]")
            # backup-only DG: a run that starts in an outage has its minimum on-time cut short when the grid returns
            # (the planners' rule: baselines/milp.py, qgrid/ablation/local.py). Needs `day`; runs that start with the
            # grid up, or without `day`, keep the full minimum.
            down = None if day is None else ~np.asarray(day.grid, bool)
            t = 0
            while t < T:
                if on[t]:
                    u = t
                    while u < T and on[u]:
                        u += 1
                    need = b.dg.min_on_slots
                    if down is not None and down[t]:
                        need = min(need, int(np.argmin(np.append(down[t:], False))))   # outage slots left from t
                    if u - t < need and u < T:
                        viol.append(f"{b.name}: DG run {t}-{u} shorter than min on-time")
                        ok[i, t:u] = False
                    t = u
                else:
                    t += 1
        if b.tank and day is not None:
            lv = tank_trajectory(b.tank, sched.pump_on[i], day.water)
            badt = (lv[1:] < b.tank.l_min - 1e-6) | (lv[1:] > b.tank.l_max + 1e-6)
            if badt.any():
                viol.append(f"{b.name}: tank level outside bounds at {int(np.argmax(badt))}")
            ok[i] &= ~badt
    bad_f = np.abs(sched.flows) > campus.step_kw + tol
    for l, t in zip(*np.nonzero(bad_f)):
        a, c = campus.lines[l]
        viol.append(f"line {campus.names[a]}-{campus.names[c]} slot {t}")
        ok[a, t] = ok[c, t] = False
    return {"feasible": not viol, "violations": viol[:20], "feasibility_rate": float(ok.mean())}
