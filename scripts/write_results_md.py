"""Generate docs/results.md from results/*.csv and render the doc templates (docs/templates/*.md -> docs/ and
README.md). Every number is read from the result files; placeholders look like {{key}} (see values())."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]
from qgrid import QUANTUM_LABEL  # noqa: E402

ORDER = ["B0", "B1", "B2-GA", "B2-PSO", "B3", "C-QIEA", "B5", "OURS-QIEA", "OURS", "B4"]
NAMES = {"B0": "B0 status quo", "B1": "B1 rule-based", "B2-GA": "B2 genetic algorithm", "B2-PSO": "B2 particle swarm",
         "B3": "B3 per-zone MPC-MILP", "B4": "B4 central MILP (optimum)", "B5": "B5 ADMM + exact local solver",
         "OURS": "**OURS ADMM + QAOA**", "OURS-QIEA": "OURS-QIEA ADMM + QIEA†", "C-QIEA": "C-QIEA central QUBO + QIEA†",
         "B5-nobattery": "B5 without batteries"}


def f(x, d=0):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:,.{d}f}"


def table(df, price, day_set):
    d = df[(df.price_scenario == price) & (df.day_set == day_set)].set_index("method")
    cols = [("cost_rs", "Rs/day", 0), ("objective_rs", "Rs incl. VOLL", 0), ("gap_to_B4_pct", "gap to B4 %", 2),
            ("critical_downtime_h", "crit. downtime h", 2), ("dg_hours", "DG h", 1), ("dg_litres", "DG L", 0),
            ("co2_kg", "CO2 kg", 0), ("self_consumption_pct", "self-cons. %", 1), ("peak_import_kw", "peak kW", 0),
            ("replan_time_s", "re-plan s/slot", 3), ("feasibility_rate", "feasible %", 1), ("qaoa_p_opt", "QAOA P(opt)", 4),
            ("admm_convergence_rate", "ADMM conv. %", 1)]
    out = ["| Method | " + " | ".join(c[1] for c in cols) + " |", "|---|" + "---:|" * len(cols)]
    for m in ORDER:
        if m not in d.index:
            continue
        r = d.loc[m]
        vals = []
        for k, _, dd in cols:
            v = r.get(k, np.nan)
            v = 100 * v if k in ("feasibility_rate", "admm_convergence_rate") and not pd.isna(v) else v
            vals.append(f(v, dd))
        out.append(f"| {NAMES[m]} | " + " | ".join(vals) + " |")
    return "\n".join(out)


def values() -> dict:
    """Flat dict of every number the templates may use."""
    b = pd.read_csv(ROOT / "results" / "benchmark.csv")
    s = pd.read_csv(ROOT / "results" / "benchmark_summary.csv")
    v = {}
    for _, r in s.iterrows():
        for k in ("cost_rs", "objective_rs", "gap_to_B4_pct", "critical_downtime_h", "dg_hours", "dg_litres", "co2_kg",
                  "replan_time_s", "admm_convergence_rate", "qaoa_p_opt", "cost_rs_semester", "co2_t_year", "self_consumption_pct"):
            if k in r and not pd.isna(r[k]):
                v[f"{r.method}.{r.day_set}.{r.price_scenario}.{k}"] = float(r[k])
    h = json.loads((ROOT / "results" / "headline.json").read_text())
    for side in ("before", "after", "optimum_B4"):
        for k, x in h[side].items():
            v[f"headline.{side}.{k}"] = x
    eco = json.loads((ROOT / "results" / "economics.json").read_text())
    for sc_, e in eco.items():
        for k, x in e.items():
            if isinstance(x, (int, float)) or x is None:
                v[f"eco.{sc_}.{k}"] = x
    ss = json.loads((ROOT / "results" / "search_space.json").read_text())
    v["search.N"] = ss["centralised_full_day"]["N_binary"]
    v["search.log10"] = ss["centralised_full_day"]["log10_states"]
    v["search.max_qubits"] = max(ss["local_qubo_qubits"].values())
    o = b[(b.method == "OURS") & (b.scenario != "eval")]
    tq, ti, ta, tx = (o[f"tier_{k}"].sum() for k in ("qaoa", "qiea", "anneal", "exact"))
    tot = tq + ti + ta + tx
    v.update({"tiers.qaoa_pct": 100 * tq / tot, "tiers.qiea_pct": 100 * ti / tot, "tiers.anneal_pct": 100 * ta / tot,
              "tiers.exact_pct": 100 * tx / tot, "tiers.total": tot, "qaoa.solves": o.qaoa_solves.sum(),
              "qaoa.time_s": o.qaoa_time_s.sum(), "qaoa.p_opt_mean": o.qaoa_p_opt.mean(),
              "qaoa.found_opt_pct": 100 * o.qaoa_found_opt_rate.mean(), "admm.conv_pct": 100 * o.admm_convergence_rate.mean(),
              "admm.iters": o.admm_iters.mean(), "admm.osc": o.admm_oscillations.sum()})
    rob = pd.read_csv(ROOT / "results" / "robustness.csv")
    net = rob[rob["mode"] == "networked"]
    v["robust.recovery_s"] = float(net.recovery_time_s.max()) if len(net) else float("nan")
    v["robust.all_feasible"] = bool(rob.feasible.all())
    sc = pd.read_csv(ROOT / "results" / "qaoa_scaling.csv")
    t = sc[(sc.params == "trained")].groupby(["n_qubits", "p"]).p_opt.mean()
    nmax = int(sc.n_qubits.max())
    for p in (1, 2, 3):
        v[f"scaling.p{p}.nmax.p_opt"] = float(t.loc[(nmax, p)])
    v["scaling.nmax"] = nmax
    v["scaling.uniform_nmax"] = 2.0 ** -nmax
    meta = json.loads((ROOT / "data" / "processed" / "meta.json").read_text())
    v["price_A_status"] = meta["prices"]["A"]["status"]
    v["price_B_status"] = meta["prices"]["B"]["status"]
    return v


def render(text: str, v: dict) -> str:
    def rep(m):
        key, _, fmt_ = m.group(1).partition("|")
        x = v.get(key.strip())
        if x is None:
            return f"⟨missing {key.strip()}⟩"
        if isinstance(x, bool):
            return "yes" if x else "no"
        d = int(fmt_) if fmt_ else 0
        return f"{x:,.{d}f}" if isinstance(x, (int, float)) else str(x)
    return re.sub(r"\{\{([^}]+)\}\}", rep, text)


def main():
    s = pd.read_csv(ROOT / "results" / "benchmark_summary.csv")
    meta = json.loads((ROOT / "data" / "processed" / "meta.json").read_text())
    st = meta["data_status"]
    pend = [f"{k}: {x}" for k, x in st.items() if x != "REAL"]
    out = [f"# Results (RVCE campus model)\n\n> {QUANTUM_LABEL}. † QIEA = quantum-inspired evolutionary algorithm, classical CPU — not quantum computing.\n",
           "_Generated by `scripts/write_results_md.py` from `results/*.csv`; do not edit numbers by hand. "
           "Earlier generic 5-building results: `docs/results_v1.md`._\n",
           "## ⚠️ Data status — read first\n",
           "Real: NASA POWER (PV), Ausgrid (hostel load shape), OpenStreetMap (layout). **PENDING:** " + "; ".join(pend) + ". "
           "Both price scenarios use labelled STAND-IN prices and campus loads are area-based estimates, so **no Rs figure "
           "below is a headline result yet**; comparisons between methods on identical inputs are meaningful. "
           "Re-run `scripts/refresh_all.sh` when the files in `docs/data_request.md` arrive.\n",
           "## Setup\n",
           "9 OSM-derived zones, tie-lines from the real layout (MST + 2 mesh links), 96 × 15-min slots. QAOA in the loop on "
           "the 6 named scenarios; on the 30-day set the OURS row uses the classical local tiers (SA → exact). B4 = MILP to a "
           "0.1 % gap with continuous tie-line flows (a relaxation of the decentralised methods' discrete levels). Objective "
           "comparisons (gap to B4) include value of lost load (VOLL, an ASSUMPTION) so that shedding is never 'cheaper'.\n"]
    for p in ("A", "B"):
        out.append(f"## Price scenario {p} ({'headline: BESCOM HT ToD + KERC export' if p == 'A' else 'sensitivity: IEX DAM both ways'}) — {meta['prices'][p]['status']}\n")
        out.append("### 30-day evaluation set (mean per day)\n\n" + table(s, p, "eval30_mean") + "\n")
        for k in meta["days"]["scenarios"]:
            sc = meta["days"]["scenarios"][k]
            out.append(f"### {k.replace('_', ' ')} — {sc['date']} ({sc['note']})\n\n" + table(s, p, k) + "\n")
    v = values()
    tmpl = (ROOT / "docs" / "templates" / "results_tail.md")
    if tmpl.exists():
        out.append(render(tmpl.read_text(), v))
    (ROOT / "docs" / "results.md").write_text("\n".join(out))
    for t in (ROOT / "docs" / "templates").glob("*.md"):
        if t.name == "results_tail.md":
            continue
        dest = ROOT / ("README.md" if t.name == "README.md" else f"docs/{t.name}")
        dest.write_text(render(t.read_text(), v))
    missing = sum(p.read_text().count("⟨missing") for p in [ROOT / "README.md", *(ROOT / "docs").glob("*.md")])
    print(f"wrote docs/results.md and rendered templates ({missing} missing placeholders)")


if __name__ == "__main__":
    main()
