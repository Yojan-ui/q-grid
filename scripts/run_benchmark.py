"""Benchmark all methods on identical data, days, constraints and horizon.

Methods: B0 status quo, B1 rule-based, B2-GA, B2-PSO, B3 per-building MPC-MILP, B4 central MILP
(global optimum), B5 ADMM + exact local solver, OURS ADMM + QAOA (verified tiered), and the ablation
ABL ADMM + QAOA-only (accept any feasible QAOA sample; test days only).
Days: 3 test days + 30-day evaluation set; price scenarios A and B.
Outputs: results/benchmark.csv (per day), results/benchmark_summary.csv, results/robustness.csv,
results/plots/*.png, results/replay/admm_<daytype>_<scenario>.json, results/schedules/*.json.
"""
from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]

METHODS = ["B0", "B1", "B2-GA", "B2-PSO", "B3", "B4", "B5", "OURS"]
TEST_KEYS = ("sunny", "monsoon_cloudy", "high_price")


def _schedule_json(campus, day, sched, metrics):
    from qgrid.model import net_power, soc_trajectory
    net = net_power(campus, day, sched)
    return {
        "p_bat": np.round(sched.p_bat, 3).tolist(),
        "soc": [np.round(soc_trajectory(b.battery, sched.p_bat[i]) / b.battery.kwh, 4).tolist()
                for i, b in enumerate(campus.buildings)],
        "flows": np.round(sched.flows, 3).tolist(), "flex_start": sched.flex_start,
        "net_kw": np.round(net, 3).tolist(), "metrics": {k: v for k, v in metrics.items() if k != "net_kw"},
    }


def run_task(day_str: str, day_type: str, scenario: str) -> dict:
    from baselines import b0_status_quo, b1_rule_based, b2_ga_pso, b3_mpc_milp, b4_central_milp
    from qgrid import data as qdata
    from qgrid.admm import run_day
    from qgrid.model import check_feasibility, load_campus, make_day, settle

    campus = load_campus()
    proc = qdata.load_processed()
    day = make_day(campus, proc, day_str, scenario)
    is_test = day_type in TEST_KEYS
    rows, extra = [], {"schedules": {}, "admm_log": None}
    solvers = {
        "B0": lambda: (b0_status_quo.solve(campus, day), None),
        "B1": lambda: (b1_rule_based.solve(campus, day), None),
        "B2-GA": lambda: (b2_ga_pso.solve(campus, day, "GA"), None),
        "B2-PSO": lambda: (b2_ga_pso.solve(campus, day, "PSO"), None),
        "B3": lambda: (b3_mpc_milp.solve(campus, day), None),
        "B4": lambda: (b4_central_milp.solve(campus, day), None),
        "B5": lambda: run_day(campus, day, method="exact"),
        "OURS": lambda: run_day(campus, day, method="qaoa", log=is_test),
    }
    if is_test:
        solvers["ABL-QAOA-only"] = lambda: run_day(campus, day, method="qaoa_only")
    for name, fn in solvers.items():
        t0 = time.perf_counter()
        sched, st = fn()
        rt = time.perf_counter() - t0
        m = settle(campus, day, sched)
        f = check_feasibility(campus, sched)
        row = {
            "method": name, "scenario": scenario, "day": day_str, "day_type": day_type,
            "price_status": day.status["price_scenario"], "co2_status": day.status["cea"],
            "cost_rs": m["cost_rs"], "energy_cost_rs": m["energy_cost_rs"], "terminal_adj_rs": m["terminal_adj_rs"],
            "co2_kg": m["co2_kg"], "import_kwh": m["import_kwh"], "export_kwh": m["export_kwh"],
            "self_consumption_pct": m["self_consumption_pct"], "peak_import_kw": m["peak_import_kw"],
            "runtime_s": rt, "feasible": f["feasible"], "feasibility_rate": f["feasibility_rate"],
            "qaoa_p_opt": np.nan, "qaoa_approx_ratio": np.nan, "qaoa_found_opt_rate": np.nan,
            "qaoa_feasible_rate": np.nan, "tier_qaoa": np.nan, "tier_anneal": np.nan, "tier_exact": np.nan,
            "admm_iters": np.nan, "line_disagreements": np.nan, "recovery_time_s": np.nan,
            "milp_status": str(sched.info.get("milp_status", "")),
        }
        if st is not None:
            s = st.summary()
            row.update({"admm_iters": s["admm_iters_mean"], "line_disagreements": s["line_disagreements"],
                        "tier_qaoa": s["tiers"]["qaoa"], "tier_anneal": s["tiers"]["anneal"],
                        "tier_exact": s["tiers"]["exact"]})
            if "qaoa_p_opt" in s:
                row.update({k: s[k] for k in ("qaoa_p_opt", "qaoa_approx_ratio", "qaoa_found_opt_rate",
                                              "qaoa_feasible_rate")})
            if name == "OURS" and is_test:
                extra["admm_log"] = {"iterations": st.log, "slots": st.slots, "lines": campus.lines,
                                     "buildings": campus.names}
        rows.append(row)
        if is_test and name in ("B0", "B3", "B4", "B5", "OURS"):
            extra["schedules"][name] = _schedule_json(campus, day, sched, m)
    # in-process kill on test days (OURS): feasibility + re-convergence
    if is_test:
        k = campus.names.index("lab_block")
        sched, st = run_day(campus, day, method="qaoa", kill=(k, 48))
        f = check_feasibility(campus, sched)
        extra["kill_inprocess"] = {"day": day_str, "day_type": day_type, "scenario": scenario, "killed": "lab_block",
                                   "kill_slot": 48, "feasible": f["feasible"], "cost_rs": settle(campus, day, sched)["cost_rs"],
                                   **{k2: v for k2, v in st.kill.items() if k2 != "building"}}
    return {"rows": rows, "extra": extra, "day": day_str, "day_type": day_type, "scenario": scenario}


def main(workers: int | None = None):
    from qgrid import QUANTUM_LABEL
    from qgrid import data as qdata
    from qgrid.model import load_campus

    t_all = time.time()
    proc = qdata.load_processed()
    meta = proc["meta"]
    campus = load_campus()
    scen = campus.cfg["prices"]["scenarios"]
    tasks = [(meta["days"][k], k, s) for s in scen for k in TEST_KEYS]
    tasks += [(d, "eval", s) for s in scen for d in meta["days"]["eval_days"]]
    workers = workers or max(1, (os.cpu_count() or 2) - 2)
    print(f"{len(tasks)} tasks on {workers} workers")
    results = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(run_task, *t): t for t in tasks}
        for n, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            results.append(r)
            ours = next(x for x in r["rows"] if x["method"] == "OURS")
            print(f"[{n}/{len(tasks)}] {r['scenario']} {r['day']} {r['day_type']:<15} OURS Rs {ours['cost_rs']:,.0f} "
                  f"({ours['runtime_s']:.1f}s)  t={time.time() - t_all:.0f}s", flush=True)

    df = pd.DataFrame([row for r in results for row in r["rows"]])
    b4 = df[df.method == "B4"].set_index(["scenario", "day"])["cost_rs"]
    df["gap_to_B4_pct"] = [100 * (c - b4[(s, d)]) / abs(b4[(s, d)]) for c, s, d in zip(df.cost_rs, df.scenario, df.day)]

    # networked kill-node experiment (real processes, websockets), sunny day, OURS and B5
    sys.path.insert(0, str(ROOT / "scripts"))
    from kill_node import run as net_run
    rob = []
    for s in scen:
        for meth, label in (("qaoa", "OURS"), ("exact", "B5")):
            r = net_run(meta["days"]["sunny"], s, meth, kill="lab_block", kill_slot=48)
            rob.append({"mode": "networked", "method": label, "scenario": s, "day": meta["days"]["sunny"],
                        "killed": "lab_block", "kill_slot": 48, "feasible": r["feasible"],
                        "tie_line_flows_consistent": r["tie_line_flows_consistent"],
                        "recovery_time_s": r["recovery_time_s"], "cost_rs": r["cost_rs"],
                        "wall_time_s": r["wall_time_s"], "price_status": r["price_status"]})
            mask = (df.method == label) & (df.scenario == s) & (df.day_type == "sunny")
            df.loc[mask, "recovery_time_s"] = r["recovery_time_s"]
            print(f"[net-kill] {label} {s}: recovery {r['recovery_time_s']:.2f}s feasible={r['feasible']}")
    for r in results:
        if "kill_inprocess" in r["extra"]:
            rob.append({"mode": "in-process", "method": "OURS", **r["extra"]["kill_inprocess"]})
    pd.DataFrame(rob).to_csv(ROOT / "results" / "robustness.csv", index=False)

    cols = ["method", "scenario", "day", "day_type", "price_status", "co2_status", "cost_rs", "co2_kg",
            "gap_to_B4_pct", "self_consumption_pct", "peak_import_kw", "runtime_s", "feasibility_rate", "qaoa_p_opt",
            "admm_iters", "recovery_time_s", "qaoa_approx_ratio", "qaoa_found_opt_rate", "qaoa_feasible_rate",
            "tier_qaoa", "tier_anneal", "tier_exact", "line_disagreements", "energy_cost_rs", "terminal_adj_rs",
            "import_kwh", "export_kwh", "feasible", "milp_status"]
    df = df[cols].sort_values(["scenario", "day_type", "day", "method"])
    df.to_csv(ROOT / "results" / "benchmark.csv", index=False)

    num = ["cost_rs", "co2_kg", "gap_to_B4_pct", "self_consumption_pct", "peak_import_kw", "runtime_s",
           "feasibility_rate", "qaoa_p_opt", "admm_iters", "qaoa_found_opt_rate", "tier_qaoa", "tier_anneal", "tier_exact"]
    ev = df[df.day_type == "eval"].groupby(["scenario", "method"])[num].mean().reset_index()
    ev.insert(2, "day_set", "eval30_mean")
    td = df[df.day_type != "eval"].copy()
    td["day_set"] = td.day_type
    summ = pd.concat([ev, td[["scenario", "method", "day_set"] + num]])
    status = {s: meta["prices"][s]["status"] for s in scen}
    summ.insert(0, "price_status", summ.scenario.map(status))
    summ.to_csv(ROOT / "results" / "benchmark_summary.csv", index=False)

    rdir = ROOT / "results" / "replay"
    sdir = ROOT / "results" / "schedules"
    sdir.mkdir(exist_ok=True)
    for r in results:
        if r["day_type"] in TEST_KEYS:
            if r["extra"]["admm_log"]:
                (rdir / f"admm_{r['day_type']}_{r['scenario']}.json").write_text(
                    json.dumps({"label": QUANTUM_LABEL, "day": r["day"], **r["extra"]["admm_log"]}, default=float))
            (sdir / f"{r['day_type']}_{r['scenario']}.json").write_text(
                json.dumps({"day": r["day"], "scenario": r["scenario"], **r["extra"]["schedules"]}, default=float))
    make_plots(df, summ, status)
    print(f"done in {time.time() - t_all:.0f}s -> results/benchmark.csv, benchmark_summary.csv, robustness.csv")
    print(ev.pivot_table(index="method", columns="scenario", values=["cost_rs", "gap_to_B4_pct"]).round(2))


def make_plots(df, summ, status):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from qgrid import QUANTUM_LABEL

    order = ["B0", "B1", "B2-GA", "B2-PSO", "B3", "B5", "OURS", "B4"]
    ev = df[df.day_type == "eval"]
    fig, axs = plt.subplots(1, 2, figsize=(14, 4.8))
    for ax, s in zip(axs, sorted(ev.scenario.unique())):
        g = ev[ev.scenario == s].groupby("method").cost_rs.mean().reindex(order)
        colors = ["#9aa5b1"] * 5 + ["#5b8def", "#2a9d8f", "#264653"]
        ax.bar(g.index, g.values, color=colors)
        ax.axhline(g["B4"], color="#264653", ls="--", lw=1, label="B4 central optimum")
        for k, v in enumerate(g.values):
            ax.text(k, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=7)
        tag = "" if status[s] == "REAL" else "  [STAND-IN prices — PENDING, not a headline result]"
        ax.set_title(f"Scenario {s}: mean daily cost, 30-day eval set{tag}", fontsize=9,
                     color="k" if status[s] == "REAL" else "#b00020")
        ax.set_ylabel("Rs / day"); ax.legend(fontsize=8); ax.tick_params(axis="x", labelsize=8)
    fig.suptitle(QUANTUM_LABEL, fontsize=8)
    fig.tight_layout()
    fig.savefig(ROOT / "results" / "plots" / "benchmark_cost.png", dpi=130)

    fig, axs = plt.subplots(1, 2, figsize=(14, 4.4))
    for ax, s in zip(axs, sorted(ev.scenario.unique())):
        d = ev[(ev.scenario == s) & (ev.method != "B4")]
        data = [d[d.method == m].gap_to_B4_pct.values for m in order[:-1]]
        ax.boxplot(data, tick_labels=order[:-1])
        ax.axhline(0, color="k", lw=.6)
        ax.set_title(f"Scenario {s}: gap to B4 per day (%)" + ("" if status[s] == "REAL" else " [STAND-IN prices]"), fontsize=9)
        ax.tick_params(axis="x", labelsize=8)
    fig.tight_layout()
    fig.savefig(ROOT / "results" / "plots" / "benchmark_gap.png", dpi=130)

    fig, ax = plt.subplots(figsize=(7, 4))
    g = ev.groupby("method").runtime_s.mean().reindex(order)
    ax.bar(g.index, g.values, color="#5b8def")
    ax.set_yscale("log"); ax.set_ylabel("seconds per day (log)"); ax.set_title("Runtime per simulated day (mean, both scenarios)", fontsize=9)
    ax.tick_params(axis="x", labelsize=8)
    fig.tight_layout()
    fig.savefig(ROOT / "results" / "plots" / "benchmark_runtime.png", dpi=130)


if __name__ == "__main__":
    main()
