"""Investment planner: how much rooftop solar per roof group, how big a battery, and which contract demand.

  python scripts/plan_investment.py [--workers=6]   -> results/planner/planner.json, results/replay/planner.json
                                                       (+ frontend/public/replay/planner.json), results/planner/cases.csv

Model (one linear programme, HiGHS): the campus as one connection over the 30 RVCE evaluation days (the scorecard's days,
their seeded outages included), every 15-minute slot. Per slot: solar = sum over roof groups of (existing + extra kWp) x
the zone's measured solar per kWp (NASA POWER), a campus battery (PROPOSED) with charge / discharge, grid import /
export, the two diesel sets during outages only (backup), load shedding at the value of lost load. Costs: BESCOM
HT-2(c)(ii) energy per slot (official KERC TO-2022 rates, marginal slab; FY2023-24 carried over), export credit, the
monthly demand charge on billing demand = max(month's sampled maximum kVA, 85 % of contract demand) with kVA above the
contract at 2x (qgrid/v2/tariff.py parameters), diesel fuel, battery wear, value of lost load. Days are weighted 365/30;
each calendar month's demand charge comes from that month's sampled days.
  optimum : capacities are decision variables, priced at their annualised cost (capital recovery over the asset life)
  cases   : the grid of capacities in config planner.* evaluated with capacities fixed (what the Plan tab looks up)
Operation is planned with perfect information on these days, so savings are an upper bound on what a controller gets.
Every cost is an ASSUMPTION (config planner, labelled); tariff FY2023-24 rates are carried over (PENDING)."""
from __future__ import annotations

import itertools
import json
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import highspy
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]
_C: dict = {}


def crf(r: float, n: int) -> float:
    return r * (1 + r) ** n / ((1 + r) ** n - 1)


def setup():
    """Day arrays for the 30 evaluation days, roof groups and tariff, built once per process."""
    if _C:
        return _C
    from qgrid import data as qd
    from qgrid.v2.tariff import energy_price_slots, ht2c_params
    from qgrid.datasets import build
    cfg = qd.load_config()
    campus, proc = build("rvce")          # same campus, days and seeded outages as the scorecard benchmark
    lay = proc["campus"]
    days = proc["meta"]["days"]["eval_days"][:30]
    outages = proc["meta"]["days"].get("outages", {})
    pc = cfg["planner"]
    names = campus.names
    groups = []
    for key, g in pc["roof_groups"].items():
        zs = [z for z in g["zones"] if z in names]
        ex = sum(lay["zones"][z]["pv_kwp"] for z in zs)
        mx = sum(max(lay["zones"][z].get("pv_kwp_osm_roof", 0.0) - lay["zones"][z]["pv_kwp"], 0.0) for z in zs)
        groups.append({"key": key, "label": g["label"], "zones": zs, "existing_kwp": ex, "max_extra_kwp": mx})
    pv = proc["pv"]; load = proc["load"][names]; crit = proc["crit"][names]
    D = []
    for d in days:
        sl = slice(pd.Timestamp(d), pd.Timestamp(d) + pd.Timedelta(minutes=15 * 95))
        per = {}
        for g in groups:      # solar per kWp of the group = its zones' series / their kWp (same weather, same model)
            kw = sum(lay["zones"][z]["pv_kwp"] for z in g["zones"])
            s_ = pv.loc[sl, g["zones"]].sum(axis=1).to_numpy()
            per[g["key"]] = s_ / kw if kw > 0 else pv.loc[sl].sum(axis=1).to_numpy() / max(sum(b.pv_kwp for b in campus.buildings), 1e-9)
        grid = np.ones(96, bool)
        o = outages.get(d)
        if o:
            from qgrid.model import hhmm_to_slot
            grid[hhmm_to_slot(o[0]):hhmm_to_slot(o[1])] = False
        D.append({"day": d, "month": int(d[5:7]), "load": load.loc[sl].sum(axis=1).to_numpy(), "crit": crit.loc[sl].sum(axis=1).to_numpy(),
                  "per_kwp": per, "price": energy_price_slots(cfg, d, 96), "grid": grid})
    tp = ht2c_params(cfg)
    dg_kw = sum(b.dg.kw for b in campus.buildings if b.dg)
    dgc = cfg["diesel"]
    from qgrid.model import wear_rate
    _C.update({"cfg": cfg, "groups": groups, "days": D, "tp": tp, "dg_kw": dg_kw, "wear": wear_rate(cfg),
               "fuel_l_per_kwh": float(dgc["fuel_l_per_kwh_out"]), "fuel_rs_per_l": float(dgc["price_rs_per_l"]),
               "co2_per_l": float(dgc["co2_kg_per_l"]), "ef": float(cfg["co2"].get("tco2_per_mwh", 0.727)),
               "voll": (float(cfg["outage_costs"]["voll_noncritical_rs_kwh"]), float(cfg["outage_costs"]["voll_critical_rs_kwh"]))})
    return _C


def solve(extra: dict | None, bat_kwh: float | None, contract_kva: float, size: bool = False) -> dict:
    """extra / bat_kwh None with size=True -> capacities are variables. Returns annual figures."""
    C = setup()
    cfg, G, D, tp = C["cfg"], C["groups"], C["days"], C["tp"]
    pc = cfg["planner"]
    r = float(cfg["economics"]["discount_rate"])
    pf = float(tp.get("power_factor", 0.95))
    rate = float(tp.get("demand_rs_kva_month", tp["orders"][0]["demand_rs_kva_month"] if "orders" in tp else 265))
    floor = float(tp.get("billing_demand_floor_frac", 0.85)) * contract_kva
    excess_mult = float(tp.get("excess_demand_multiplier", 2.0))
    export_rs = float(tp.get("export_rs_kwh", 3.74))
    w = 365.0 / len(D)
    T, dt = 96, 0.25
    h = highspy.Highs(); h.setOptionValue("output_flag", False)
    inf = highspy.kHighsInf
    cols_cost, lo, hi = [], [], []

    def var(c, l, u):
        cols_cost.append(c); lo.append(l); hi.append(u); return len(cols_cost) - 1
    # capacities
    xg = {}
    for g in G:
        if size:
            ann = crf(r, int(pc["pv_life_years"])) * float(pc["pv_capex_rs_per_kwp"]) + float(pc["pv_om_frac_per_year"]) * float(pc["pv_capex_rs_per_kwp"])
            xg[g["key"]] = var(ann, 0.0, g["max_extra_kwp"])
        else:
            v = float((extra or {}).get(g["key"], 0.0)); xg[g["key"]] = var(0.0, v, v)
    bcap_cost = (crf(r, int(pc["battery_life_years"])) + float(pc["battery_om_frac_per_year"])) * float(pc["battery_capex_rs_per_kwh"])
    xb = var(bcap_cost if size else 0.0, 0.0 if size else float(bat_kwh or 0), float(max(pc["battery_kwh_steps"])) if size else float(bat_kwh or 0))
    kpk = float(pc["battery_kw_per_kwh"])
    rows = []   # (cols, vals, lo, hi)
    months = sorted({d["month"] for d in D})
    md = {m: var(0.0, 0.0, inf) for m in months}          # month's sampled maximum kVA
    bd = {m: var(rate * (12.0 / len(months)) * 0 + rate, floor, inf) for m in months}   # billing demand (>= floor), Rs/kVA once per month
    ex = {m: var(excess_mult * rate, 0.0, inf) for m in months}                          # kVA above contract
    # demand charge counted for every calendar month: months present in the sample stand for themselves
    for m in months:
        rows.append(([bd[m], md[m]], [1.0, -1.0], 0.0, inf))          # bd >= md
        rows.append(([ex[m], md[m]], [1.0, -1.0], -contract_kva, inf))  # ex >= md - CD
    track = []
    e_cap = xb
    for di, d in enumerate(D):
        e_prev = None
        idx = {}
        for t in range(T):
            up = bool(d["grid"][t])
            imp = var(w * d["price"][t] * dt if up else 0.0, 0.0, inf if up else 0.0)
            exp_ = var(-w * export_rs * dt if up else 0.0, 0.0, inf if up else 0.0)
            ch = var(w * C["wear"] * dt, 0.0, inf); dis = var(w * C["wear"] * dt, 0.0, inf)
            dg = var(w * C["fuel_l_per_kwh"] * C["fuel_rs_per_l"] * dt if not up else 0.0, 0.0, 0.0 if up else C["dg_kw"])
            snc = var(w * C["voll"][0] * dt, 0.0, max(d["load"][t] - d["crit"][t], 0.0) if not up else 0.0)
            sc = var(w * C["voll"][1] * dt, 0.0, d["crit"][t] if not up else 0.0)
            e = var(0.0, 0.0, inf)
            # balance: load - pv - dis + ch - imp + exp - dg - snc - sc = 0  -> pv terms carry capacity variables
            cols = [imp, exp_, ch, dis, dg, snc, sc] + [xg[g["key"]] for g in G]
            vals = [-1.0, 1.0, 1.0, -1.0, -1.0, -1.0, -1.0] + [-float(d["per_kwp"][g["key"]][t]) for g in G]
            existing_pv = sum(g["existing_kwp"] * float(d["per_kwp"][g["key"]][t]) for g in G)
            rhs = existing_pv - float(d["load"][t])
            rows.append((cols, vals, rhs, rhs))
            rows.append(([ch, e_cap], [1.0, -kpk], -inf, 0.0)); rows.append(([dis, e_cap], [1.0, -kpk], -inf, 0.0))
            rows.append(([e, e_cap], [1.0, -0.95], -inf, 0.0)); rows.append(([e, e_cap], [1.0, -0.20], 0.0, inf))  # SoC 20-95 %
            # energy: e_t = e_{t-1} + 0.95 ch dt - dis dt / 0.95 ; day starts and ends at 50 %
            if e_prev is None:
                rows.append(([e, e_cap, ch, dis], [1.0, -0.5, -0.95 * dt, dt / 0.95], 0.0, 0.0))
            else:
                rows.append(([e, e_prev, ch, dis], [1.0, -1.0, -0.95 * dt, dt / 0.95], 0.0, 0.0))
            e_prev = e
            if up:
                rows.append(([md[d["month"]], imp], [1.0, -1.0 / pf], 0.0, inf))
            idx[t] = (imp, exp_, dg, snc, sc, ch, dis)
        rows.append(([e_prev, e_cap], [1.0, -0.5], 0.0, inf))
        track.append(idx)
    n = len(cols_cost)
    h.addVars(n, np.array(lo, float), np.array(hi, float))
    h.changeColsCost(n, np.arange(n, dtype=np.int32), np.array(cols_cost, float))
    for cols, vals, l, u in rows:
        h.addRow(float(l), float(u), len(cols), np.array(cols, np.int32), np.array(vals, float))
    h.run()
    st = str(h.getModelStatus())
    x = np.array(h.getSolution().col_value)
    imp_kwh = exp_kwh = dg_kwh = shed = peak = 0.0
    for idx in track:
        for t, (imp, exp_, dg, snc, sc, ch, dis) in idx.items():
            imp_kwh += x[imp] * dt; exp_kwh += x[exp_] * dt; dg_kwh += x[dg] * dt; shed += (x[snc] + x[sc]) * dt
            peak = max(peak, x[imp] / pf)
    litres = dg_kwh * w * C["fuel_l_per_kwh"]
    energy_rs = sum(x[imp] * dt * D[di]["price"][t] for di, idx in enumerate(track) for t, (imp, *_r) in idx.items()) * w
    export_credit = exp_kwh * w * export_rs
    demand_rs = sum(x[bd[m]] * rate + x[ex[m]] * excess_mult * rate for m in months) * (12.0 / len(months))
    wear_rs = sum((x[ch] + x[dis]) * dt for idx in track for (_i, _e, _d, _n, _c, ch, dis) in idx.values()) * w * C["wear"]
    money = energy_rs - export_credit + demand_rs + litres * C["fuel_rs_per_l"] + wear_rs
    caps = {g["key"]: float(x[xg[g["key"]]]) for g in G}
    capex = sum(caps.values()) * float(pc["pv_capex_rs_per_kwp"]) + float(x[xb]) * float(pc["battery_capex_rs_per_kwh"])
    om = sum(caps.values()) * float(pc["pv_capex_rs_per_kwp"]) * float(pc["pv_om_frac_per_year"]) + float(x[xb]) * float(pc["battery_capex_rs_per_kwh"]) * float(pc["battery_om_frac_per_year"])
    return {"status": st, "extra_kwp": {k: round(v, 1) for k, v in caps.items()}, "battery_kwh": round(float(x[xb]), 1), "contract_kva": contract_kva,
            "capex_rs": capex, "om_rs_year": om, "annual_cost_rs": money, "energy_rs": energy_rs, "export_credit_rs": export_credit,
            "demand_rs": demand_rs, "wear_rs": wear_rs, "import_mwh": imp_kwh * w / 1000, "peak_kva": peak,
            "diesel_litres_year": litres, "co2_t_year": (imp_kwh * w * C["ef"] / 1000) + litres * C["co2_per_l"] / 1000,
            "unserved_kwh_year": shed * w}


def _case(args):
    extra, b, cd = args
    return solve(extra, b, cd)


def main(workers: int):
    t0 = time.time()
    C = setup()
    cfg = C["cfg"]; pc = cfg["planner"]; G = C["groups"]
    r = float(cfg["economics"]["discount_rate"]); N = int(pc["npv_years"])
    ann = sum(1 / (1 + r) ** y for y in range(1, N + 1))
    cd0 = float(cfg["tariff_ht2c"].get("contract_demand_kva", 1300))
    cds = [float(c) for c in cfg["tariff_ht2c"].get("contract_demand_sweep", [1300])]
    cds = [cd0] + [c for c in cds if c != cd0]      # today's contract first: the Plan tab starts on the first option
    base = solve({g["key"]: 0.0 for g in G}, 0.0, cd0)
    grid = []
    for fr in itertools.product(pc["extra_kwp_fracs"], repeat=len(G)):
        ex = {g["key"]: round(f * g["max_extra_kwp"], 1) for g, f in zip(G, fr)}
        for b in pc["battery_kwh_steps"]:
            for cd in cds:
                grid.append((ex, float(b), cd))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        res = list(pool.map(_case, grid))
    cases = []
    for c in res:
        sav = base["annual_cost_rs"] - c["annual_cost_rs"] - c["om_rs_year"]
        c["annual_saving_rs"] = sav
        c["payback_years"] = (c["capex_rs"] / sav) if sav > 0 and c["capex_rs"] > 0 else (0.0 if c["capex_rs"] == 0 and sav >= 0 else None)
        c["npv10_rs"] = -c["capex_rs"] + sav * ann
        cases.append(c)
    opt = solve(None, None, cd0, size=True)
    best_cd = min(cds, key=lambda cd: next(c for c in cases if c["contract_kva"] == cd and c["battery_kwh"] == 0 and all(v == 0 for v in c["extra_kwp"].values()))["annual_cost_rs"])
    if best_cd != cd0:
        opt = solve(None, None, best_cd, size=True)
    sav = base["annual_cost_rs"] - opt["annual_cost_rs"] - opt["om_rs_year"]
    opt.update({"annual_saving_rs": sav, "payback_years": (opt["capex_rs"] / sav) if sav > 0 and opt["capex_rs"] > 0 else None,
                "npv10_rs": -opt["capex_rs"] + sav * ann,
                "note": "Sizing LP: extra kWp per roof group and battery kWh chosen to minimise annualised capital + operating cost "
                        f"at contract demand {opt['contract_kva']:.0f} kVA (the cheapest of the sweep with today's assets)."})
    steps = sorted(set(pc["extra_kwp_fracs"]))
    out = {"status": "ASSUMPTION costs; tariff HT-2(c)(ii) official TO-2022 rates (FY2023-24 carried over); not a headline result",
           "generated_by": "scripts/plan_investment.py",
           "labels": {"tariff": "BESCOM HT-2(c)(ii), KERC TO-2022 (FY2023-24 rates carried over, PENDING)",
                      "costs": "PV, battery and O&M costs are ASSUMPTIONS (config planner); quotes PENDING",
                      "operation": "perfect-information operation on the 30 RVCE evaluation days (an upper bound on savings)"},
           "roof_groups": [{"key": g["key"], "label": g["label"], "existing_kwp": round(g["existing_kwp"], 1),
                            "max_extra_kwp": round(g["max_extra_kwp"], 1),
                            "step_kwp": round(g["max_extra_kwp"] * (steps[1] - steps[0]), 1) if len(steps) > 1 else round(g["max_extra_kwp"], 1)} for g in G],
           "battery": {"max_kwh": float(max(pc["battery_kwh_steps"])), "step_kwh": float(sorted(pc["battery_kwh_steps"])[1]) if len(pc["battery_kwh_steps"]) > 1 else 0.0,
                       "steps_kwh": [float(b) for b in pc["battery_kwh_steps"]], "status": "PROPOSED"},
           "contract_demand_options": cds, "baseline": {**base, "contract_kva": cd0},
           "cases": [{k: v for k, v in c.items() if k != "status"} for c in cases], "optimum": {k: v for k, v in opt.items() if k != "status"},
           "assumptions": [{"name": "Rooftop PV installed cost", "value": pc["pv_capex_rs_per_kwp"], "unit": "Rs/kWp", "source": "ASSUMPTION — quote PENDING"},
                           {"name": "PV O&M", "value": 100 * pc["pv_om_frac_per_year"], "unit": "% of capex per year", "source": "ASSUMPTION"},
                           {"name": "PV life", "value": pc["pv_life_years"], "unit": "years", "source": "ASSUMPTION"},
                           {"name": "Battery installed cost", "value": pc["battery_capex_rs_per_kwh"], "unit": "Rs/kWh", "source": "ASSUMPTION (config economics)"},
                           {"name": "Battery power", "value": pc["battery_kw_per_kwh"], "unit": "kW per kWh", "source": "ASSUMPTION"},
                           {"name": "Battery life", "value": pc["battery_life_years"], "unit": "years", "source": "ASSUMPTION"},
                           {"name": "Discount rate", "value": 100 * r, "unit": "%", "source": "ASSUMPTION (config economics)"},
                           {"name": "Demand charge", "value": C["tp"].get("demand_rs_kva_month", 265), "unit": "Rs/kVA/month", "source": "KERC TO-2022 HT-2(c)(ii), p.412"},
                           {"name": "Export rate", "value": C["tp"].get("export_rs_kwh", 3.74), "unit": "Rs/kWh", "source": "team brief (order PENDING)"}],
           "runtime_s": time.time() - t0, "n_days": len(C["days"])}
    d = ROOT / "results" / "planner"; d.mkdir(parents=True, exist_ok=True)
    pd.json_normalize(cases).to_csv(d / "cases.csv", index=False)
    js = json.dumps(out, default=float)
    (d / "planner.json").write_text(js, encoding="utf-8")
    shutil.copy(d / "planner.json", ROOT / "results" / "replay" / "planner.json")
    shutil.copy(d / "planner.json", ROOT / "frontend" / "public" / "replay" / "planner.json")
    o = out["optimum"]
    print(f"{len(cases)} cases in {time.time() - t0:.0f} s. Baseline cost Rs {base['annual_cost_rs'] / 1e5:,.1f} lakh/yr, peak {base['peak_kva']:,.0f} kVA.")
    print(f"Optimum @ {o['contract_kva']:.0f} kVA: extra kWp {o['extra_kwp']}, battery {o['battery_kwh']:.0f} kWh, capex Rs {o['capex_rs'] / 1e5:,.1f} lakh, "
          f"saving Rs {o['annual_saving_rs'] / 1e5:,.1f} lakh/yr, payback {o['payback_years']}, NPV10 Rs {o['npv10_rs'] / 1e5:,.1f} lakh, peak {o['peak_kva']:,.0f} kVA")


if __name__ == "__main__":
    main(next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--workers=")), 6))
