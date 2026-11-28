"""Re-run chosen method-days of the scorecard benchmark and replace them in results/bench_v3/runs.csv.

  python scripts/rerun_rows_v3.py --infeasible [--workers=8]
  python scripts/rerun_rows_v3.py --methods=qgrid,qgrid_comms_fail --why="..." [--workers=8]

--infeasible re-runs every row marked infeasible (used on 28 Nov 2026 after check_feasibility learnt the planners'
backup-only diesel rule: a minimum on-time is cut short when the grid returns). --methods re-runs every row of those
methods (used on 28 Nov 2026 after the fix to Q-Grid's peak budgets, qgrid/ablation/engine.py _budgets). The same code
and seeds as scripts/run_bench_v3.py; each re-run is recorded in run_info.json under "reruns" with old and new objective.
"""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT), str(ROOT / "scripts")]
import run_bench_v3 as rb  # noqa: E402


def _one(t):
    ds, day, m, qg, peak = t
    rb.QGRID, rb.PEAK = qg, peak
    return rb.run_one(ds, day, m)


WHY_INFEASIBLE = "check_feasibility applied the backup-only DG rule (min on-time cut short when the grid returns)"


def main(workers: int, methods: list[str] | None = None, why: str | None = None) -> int:
    out = rb.OUT
    r = pd.read_csv(out / "runs.csv")
    info = json.loads((out / "run_info.json").read_text(encoding="utf-8"))
    sel = r[r.method.isin(methods)] if methods else r[~r.feasible.astype(bool)]
    if not len(sel):
        print("no rows to re-run")
        return 0
    # costliest first so the pool stays busy to the end
    sel = sel.assign(_c=sel.dataset.map(lambda d: 0 if d == "rvce" else 1)).sort_values("_c").drop(columns="_c")
    qg = info.get("qgrid_combo", "1111")
    peak = bool(r.peak_priced.iloc[0]) if "peak_priced" in r else True
    tasks = [(x.dataset, x.day, x.method, qg, peak) for x in sel.itertuples()]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        new = []
        for n, row in enumerate(ex.map(_one, tasks), 1):
            new.append(row)
            print(f"[{n}/{len(tasks)}] {row['dataset']:13s} {row['day']} {row['method']:26s} {row['objective_rs']:14,.0f} "
                  f"{row['runtime_s']:6.1f}s", flush=True)
    log = []
    for (ds, day, m, *_), row in zip(tasks, new):
        i = r.index[(r.dataset == ds) & (r.day == day) & (r.method == m)][0]
        log.append({"dataset": ds, "day": day, "method": m, "old_objective_rs": float(r.at[i, "objective_rs"]),
                    "new_objective_rs": float(row["objective_rs"]), "feasible": bool(row["feasible"])})
        for k, v in row.items():
            if k in r.columns:
                r.at[i, k] = v
        print(f"{ds:13s} {day} {m:26s} feasible={row['feasible']}  objective {log[-1]['old_objective_rs']:,.1f} -> "
              f"{row['objective_rs']:,.1f}", flush=True)
    r.to_csv(out / "runs.csv", index=False)
    info.setdefault("reruns", []).append({"when": time.strftime("%Y-%m-%d %H:%M"), "why": why or WHY_INFEASIBLE,
                                          "workers": workers, "runtime_s": time.time() - t0, "rows": log})
    (out / "run_info.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    still = sum(not x["feasible"] for x in log)
    print(f"re-ran {len(log)} rows in {time.time() - t0:.0f} s; still infeasible: {still}")
    return 0


if __name__ == "__main__":
    me = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--methods=")), None)
    wh = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--why=")), None)
    if me and not wh:
        sys.exit("--methods needs --why=\"...\" (recorded in run_info.json)")
    sys.exit(main(next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--workers=")), 8), me, wh))
