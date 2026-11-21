"""Status-quo 'problem' analysis on real data -> results/problem_day.json + results/plots/problem_day.png.

Rs lost = value of solar surplus exported at the midday price that is later bought back in the
evening: min(exported kWh, later-imported kWh) x (mean evening import price - mean export price).
Computed per building (no sharing) and summed. CO2 avoidable = that re-usable energy x CEA factor.
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
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))
from baselines.b0_status_quo import DT_H, status_quo  # noqa: E402
from qgrid.data import day_slice, load_config, load_processed  # noqa: E402


def lost_value(pv, load, price, factor):
    tot_kwh, tot_rs = 0.0, 0.0
    p = price.to_numpy()
    for b in pv.columns:
        net = (load[b] - pv[b]).to_numpy()
        exp = np.clip(-net, 0, None) * DT_H
        imp = np.clip(net, 0, None) * DT_H
        if exp.sum() <= 0:
            continue
        last_exp = np.nonzero(exp)[0].max()
        later_imp = imp[last_exp + 1:]
        reusable = min(exp.sum(), later_imp.sum())
        if reusable <= 0:
            continue
        p_exp = (exp * p * factor).sum() / exp.sum()
        p_imp = (later_imp * p[last_exp + 1:]).sum() / later_imp.sum()
        tot_kwh += reusable
        tot_rs += reusable * max(p_imp - p_exp, 0.0)
    return tot_kwh, tot_rs


def analyse_day(d, day, cfg):
    pv, load = day_slice(d["pv"], day), day_slice(d["load"], day)
    price = day_slice(d["price"]["price_rs_kwh"], day)
    ef = float(d["meta"]["co2"]["weighted_average_tco2_per_mwh"])
    f = cfg["prices"]["export_price_factor"]
    sq = status_quo(pv, load, price, ef, f)
    noon = (pv.index.hour >= 10) & (pv.index.hour < 15)
    eve = (pv.index.hour >= 18) & (pv.index.hour < 22)
    reuse_kwh, lost_rs = lost_value(pv, load, price, f)
    out = {
        "day": day,
        "status_quo_cost_rs": round(sq["cost_rs"], 2),
        "import_cost_rs": round(sq["import_cost_rs"], 2),
        "export_revenue_rs": round(sq["export_revenue_rs"], 2),
        "import_kwh": round(sq["import_kwh"], 1),
        "export_kwh": round(sq["export_kwh"], 1),
        "noon_export_kwh_10_15h": round(float(sq["export_kw"][noon].to_numpy().sum() * DT_H), 1),
        "evening_import_kwh_18_22h": round(float(sq["import_kw"][eve].to_numpy().sum() * DT_H), 1),
        "mean_price_noon_rs_kwh": round(float(price[noon].mean()), 3),
        "mean_price_evening_rs_kwh": round(float(price[eve].mean()), 3),
        "co2_kg": round(sq["co2_kg"], 1),
        "peak_import_kw": round(sq["peak_import_kw"], 1),
        "self_consumption_pct": round(sq["self_consumption_pct"], 1),
        "reusable_surplus_kwh": round(reuse_kwh, 1),
        "rs_lost": round(lost_rs, 2),
        "co2_avoidable_kg": round(reuse_kwh * ef, 1),
    }
    return out, pv, load, price, sq


def main():
    cfg = load_config()
    d = load_processed()
    days = d["meta"]["days"]
    per_day = {k: analyse_day(d, days[k], cfg)[0] for k in ("sunny", "monsoon_cloudy", "high_price")}
    ev = [analyse_day(d, day, cfg)[0] for day in days["eval_days"]]
    keys = ["status_quo_cost_rs", "co2_kg", "rs_lost", "co2_avoidable_kg", "export_kwh", "import_kwh"]
    eval_mean = {k: round(float(np.mean([e[k] for e in ev])), 2) for k in keys}

    focus = "sunny"
    summary, pv, load, price, sq = analyse_day(d, days[focus], cfg)
    result = {
        "focus_day": focus, "summary": summary, "test_days": per_day,
        "eval_30day_mean": eval_mean, "co2_factor": d["meta"]["co2"],
        "definitions": {"rs_lost": __doc__.strip().splitlines()[2:5]},
        "series": {
            "t": [t.strftime("%H:%M") for t in pv.index],
            "pv_kw": pv.sum(axis=1).round(2).tolist(),
            "load_kw": load.sum(axis=1).round(2).tolist(),
            "import_kw": sq["import_kw"].sum(axis=1).round(2).tolist(),
            "export_kw": sq["export_kw"].sum(axis=1).round(2).tolist(),
            "price_rs_kwh": price.round(4).tolist(),
        },
    }
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "problem_day.json").write_text(json.dumps(result, indent=2, default=str))

    hrs = np.arange(len(pv)) * DT_H
    fig, ax = plt.subplots(figsize=(11, 5.2))
    ax.fill_between(hrs, 0, pv.sum(axis=1), color="#f2b705", alpha=.35, label="Campus PV (kW)")
    ax.plot(hrs, load.sum(axis=1), color="#1f3b73", lw=2, label="Campus load (kW)")
    ax.fill_between(hrs, 0, -sq["export_kw"].sum(axis=1), color="#2a9d8f", alpha=.7, label="Exported surplus (kW)")
    ax.fill_between(hrs, 0, sq["import_kw"].sum(axis=1), color="#e63946", alpha=.25, label="Grid import (kW)")
    ax.axhline(0, color="k", lw=.6)
    ax.set_xlabel("Hour of day"); ax.set_ylabel("kW"); ax.set_xlim(0, 24); ax.set_xticks(range(0, 25, 3))
    ax2 = ax.twinx()
    ax2.step(hrs, price, where="post", color="#6a4c93", lw=1.4, label="IEX DAM price (Rs/kWh)")
    ax2.set_ylabel("Rs/kWh")
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8)
    s = summary
    ax.set_title(f"Status quo on {s['day']} (Bengaluru, real data): exported {s['noon_export_kwh_10_15h']:.0f} kWh "
                 f"at noon @ Rs {s['mean_price_noon_rs_kwh']:.2f}, bought back evening @ Rs {s['mean_price_evening_rs_kwh']:.2f}\n"
                 f"Net cost Rs {s['status_quo_cost_rs']:,.0f}/day · Rs lost {s['rs_lost']:,.0f} · CO2 {s['co2_kg']:,.0f} kg "
                 f"(avoidable {s['co2_avoidable_kg']:,.0f} kg)", fontsize=10)
    fig.text(0.01, 0.01, "Data: NASA POWER, Ausgrid Solar Home (load shapes), IEX DAM, CEA CO2 baseline. "
             "Capacities are design assumptions (config.yaml).", fontsize=7, alpha=.7)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    out = ROOT / "results" / "plots" / "problem_day.png"
    fig.savefig(out, dpi=140)
    print(json.dumps({"summary": summary, "eval_30day_mean": eval_mean}, indent=2))
    print(f"saved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
