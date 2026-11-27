"""Re-run chosen method-days of the scorecard benchmark and replace them in results/bench_v3/runs.csv.

  python scripts/rerun_rows_v3.py --infeasible [--workers=8]

--infeasible re-runs every row marked infeasible (used on 28 Nov 2026 after check_feasibility learnt the planners'
backup-only diesel rule: a minimum on-time is cut short when the grid returns). The same code and seeds as
scripts/run_bench_v3.py; each re-run is recorded in run_info.json under "reruns" with old and new objective.
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


def main(workers: int) -> int:
    out = rb.OUT
    r = pd.read_csv(out / "runs.csv")
    info = json.loads((out / "run_info.json").read_text(encoding="utf-8"))
    sel = r[~r.feasible.astype(bool)]
    if not len(sel):
        print("no infeasible rows")
        return 0
    qg = info.get("qgrid_combo", "1111")
    peak = bool(r.peak_priced.iloc[0]) if "peak_priced" in r else True
    tasks = [(x.dataset, x.day, x.method, qg, peak) for x in sel.itertuples()]
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=workers) as ex:
        new = list(ex.map(_one, tasks))
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
    info.setdefault("reruns", []).append({"when": time.strftime("%Y-%m-%d %H:%M"), "why": "check_feasibility applied the "
                                          "backup-only DG rule (min on-time cut short when the grid returns)",
                                          "workers": workers, "runtime_s": time.time() - t0, "rows": log})
    (out / "run_info.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    still = sum(not x["feasible"] for x in log)
    print(f"re-ran {len(log)} rows in {time.time() - t0:.0f} s; still infeasible: {still}")
    return 0


if __name__ == "__main__":
    sys.exit(main(next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--workers=")), 8)))
