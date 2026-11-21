"""Status-quo 'problem' analysis -> results/problem_day.json + results/plots/problem_day.png.

Rs lost (per building, no sharing): solar surplus exported during the day that is bought back
later the same day: reusable = min(exported kWh, later-imported kWh);
Rs lost = reusable x (mean later import price - mean export price received).
CO2 avoidable = reusable kWh x grid emission factor.
Both price scenarios are analysed; a scenario whose prices are PENDING is labelled STAND-IN.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]
from baselines import b0_status_quo  # noqa: E402
from qgrid import data as qdata  # noqa: E402
from qgrid.model import DT, flex_load, load_campus, make_day, net_power, settle  # noqa: E402


def lost_value(net, pi, pe):
    kwh = rs = 0.0
    for r in net:
        exp, imp = np.clip(-r, 0, None) * DT, np.clip(r, 0, None) * DT
        if exp.sum() <= 0:
            continue
        last = np.nonzero(exp)[0].max()
        later = imp[last + 1:]
        reuse = min(exp.sum(), later.sum())
        if reuse <= 0:
            continue
        p_exp = (exp * pe).sum() / exp.sum()
        p_imp = (later * pi[last + 1:]).sum() / later.sum()
        kwh += reuse
        rs += reuse * max(p_imp - p_exp, 0.0)
    return kwh, rs


def analyse(campus, proc, day, scen):
    d = make_day(campus, proc, day, scen)
    s = b0_status_quo.solve(campus, d)
    m = settle(campus, d, s)
    net = net_power(campus, d, s)
    imp, exp = np.maximum(net, 0).sum(0), np.maximum(-net, 0).sum(0)
    h = np.arange(96) / 4
    noon, eve = (h >= 10) & (h < 15), (h >= 18) & (h < 22)
    reuse, lost = lost_value(net, d.price_imp, d.price_exp)
    out = {
        "day": day, "scenario": scen, "price_status": d.status["price_scenario"],
        "status_quo_cost_rs": round(m["energy_cost_rs"], 1),
        "import_kwh": round(m["import_kwh"], 1), "export_kwh": round(m["export_kwh"], 1),
        "noon_export_kwh_10_15h": round(float(exp[noon].sum() * DT), 1),
        "evening_import_kwh_18_22h": round(float(imp[eve].sum() * DT), 1),
        "mean_export_price_noon": round(float(d.price_exp[noon].mean()), 3),
        "mean_import_price_evening": round(float(d.price_imp[eve].mean()), 3),
        "co2_kg": round(m["co2_kg"], 1), "peak_import_kw": round(m["peak_import_kw"], 1),
        "self_consumption_pct": round(m["self_consumption_pct"], 1),
        "reusable_surplus_kwh": round(reuse, 1), "rs_lost": round(lost, 1),
        "co2_avoidable_kg": round(reuse * d.ef, 1),
    }
    series = {"pv_kw": d.pv.sum(0), "load_kw": d.load.sum(0) + flex_load(campus, s).sum(0),
              "import_kw": imp, "export_kw": exp, "price_imp": d.price_imp, "price_exp": d.price_exp}
    return out, series


def main():
    campus = load_campus()
    proc = qdata.load_processed()
    days = proc["meta"]["days"]
    res = {"data_status": proc["meta"]["data_status"], "co2": proc["meta"]["co2"],
           "day_criteria": days["criteria"], "definitions": __doc__.strip().splitlines()[2:6],
           "scenarios": {}}
    for scen in campus.cfg["prices"]["scenarios"]:
        tdays = {k: analyse(campus, proc, days[k], scen)[0] for k in ("sunny", "monsoon_cloudy", "high_price")}
        ev = [analyse(campus, proc, day, scen)[0] for day in days["eval_days"]]
        keys = ["status_quo_cost_rs", "co2_kg", "rs_lost", "co2_avoidable_kg", "export_kwh", "import_kwh"]
        res["scenarios"][scen] = {"test_days": tdays,
                                  "eval_30day_mean": {k: round(float(np.mean([e[k] for e in ev])), 1) for k in keys}}
    focus_scen = "A"
    summ, ser = analyse(campus, proc, days["sunny"], focus_scen)
    res["focus"] = {"day": days["sunny"], "scenario": focus_scen, "summary": summ,
                    "series": {k: np.round(v, 3).tolist() for k, v in ser.items()}}
    (ROOT / "results" / "problem_day.json").write_text(json.dumps(res, indent=2, default=str))

    standin = summ["price_status"] != "REAL"
    h = np.arange(96) * DT
    fig, ax = plt.subplots(figsize=(11, 5.4))
    ax.fill_between(h, 0, ser["pv_kw"], color="#f2b705", alpha=.35, label="Campus PV (kW)")
    ax.plot(h, ser["load_kw"], color="#1f3b73", lw=2, label="Campus load (kW)")
    ax.fill_between(h, 0, -ser["export_kw"], color="#2a9d8f", alpha=.75, label="Exported surplus (kW, shown negative)")
    ax.fill_between(h, 0, ser["import_kw"], color="#e63946", alpha=.25, label="Grid import (kW)")
    ax.axhline(0, color="k", lw=.6)
    ax.set_xlabel("Hour of day"); ax.set_ylabel("kW"); ax.set_xlim(0, 24); ax.set_xticks(range(0, 25, 3))
    ax2 = ax.twinx()
    ax2.step(h, ser["price_imp"], where="post", color="#6a4c93", lw=1.4, label="Import price (Rs/kWh)")
    ax2.step(h, ser["price_exp"], where="post", color="#6a4c93", lw=1.0, ls="--", label="Export price (Rs/kWh)")
    ax2.set_ylabel("Rs/kWh"); ax2.set_ylim(0, max(ser["price_imp"].max() * 1.3, 1))
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8)
    s = summ
    tag = "  [PRICES: STAND-IN, PENDING official tariff — not a headline result]" if standin else ""
    ax.set_title(f"Status quo, {s['day']} (sunniest day 2023, Bengaluru) — scenario {focus_scen}{tag}\n"
                 f"Exported {s['noon_export_kwh_10_15h']:.0f} kWh 10-15h, imported {s['evening_import_kwh_18_22h']:.0f} kWh 18-22h · "
                 f"net cost Rs {s['status_quo_cost_rs']:,.0f}/day · Rs lost {s['rs_lost']:,.0f} · CO2 {s['co2_kg']:,.0f} kg "
                 f"(avoidable {s['co2_avoidable_kg']:,.0f} kg)", fontsize=9.5, color="#b00020" if standin else "k")
    st = res["data_status"]
    fig.text(0.01, 0.01, f"Data: NASA POWER irradiance ({st['nasa_power']}), Ausgrid Solar Home load shapes ({st['ausgrid']}), "
             f"tariff A ({st['tariff_A']}), IEX ({st['iex']}), CEA CO2 ({st['cea']}). Capacities: design assumptions (config.yaml).",
             fontsize=7, alpha=.75)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = ROOT / "results" / "plots" / "problem_day.png"
    fig.savefig(out, dpi=140)
    print(json.dumps({"focus": summ, "eval_mean": {k: v["eval_30day_mean"] for k, v in res["scenarios"].items()}}, indent=2))
    print("saved", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
