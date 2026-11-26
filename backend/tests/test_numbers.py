"""Numbers consistency: what the UI reads (results/replay/*.json) equals what the scripts wrote (results/*.csv), and the
same quantity never takes two values on two screens. The UI side (every number on screen comes from these files) is
frontend/scripts/check-numbers.mjs."""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
RP = ROOT / "results" / "replay"


def _bench():
    p = RP / "bench_v3.json"
    s = ROOT / "results" / "bench_v3" / "summary.csv"
    if not p.exists() or not s.exists():
        pytest.skip("scorecard not generated")
    return json.loads(p.read_text()), pd.read_csv(s)


def test_scorecard_in_the_ui_equals_summary_csv():
    b, s = _bench()
    n = 0
    for ds, methods in b["table"].items():
        for m, metrics in methods.items():
            row = s[(s.dataset == ds) & (s.method == m)]
            for k, st in metrics.items():
                if not st or st.get("mean") is None or f"{k}__mean" not in s:
                    continue
                assert len(row) == 1, (ds, m)
                assert abs(st["mean"] - float(row.iloc[0][f"{k}__mean"])) <= 1e-9 * max(1, abs(st["mean"])), (ds, m, k)
                n += 1
    assert n > 100


def test_generated_sentences_use_the_scorecard_numbers():
    b, s = _bench()
    st = (b.get("headline") or {}).get("story")
    if not st:
        pytest.skip("headline sentences not generated yet")
    q = s[(s.dataset == "rvce") & (s.method == "qgrid")].iloc[0]
    sq = s[(s.dataset == "rvce") & (s.method == "status_quo")].iloc[0]
    nums = st["numbers"]
    assert abs(nums["qgrid_gap_pct"] - q.gap_pct__mean) < 1e-9
    assert abs(nums["qgrid_downtime_h"] - q.critical_downtime_h__mean) < 1e-9
    assert abs(nums["status_quo_downtime_h"] - sq.critical_downtime_h__mean) < 1e-9
    assert abs(nums["qgrid_saving_pct"] - q.saving_pct__mean) < 1e-9
    assert f"{q.gap_pct__mean:.1f}%" in st["step7"]["text"]


def test_headline_day_problem_matches_its_status_quo_run():
    sc = json.loads((RP / f"scenario_{json.loads((RP / 'index.json').read_text())['headline']}.json").read_text())
    pr, m = sc.get("problem"), sc["runs"]["status_quo"].get("metrics", {})
    if not pr or not m:
        pytest.skip("no problem figures in the replay")
    assert abs(pr["dg_hours"] - m["dg_hours"]) < 1e-6           # Step 1 "diesel running" = Step 6 "today" diesel hours
    assert abs(pr["critical_downtime_h"] - m["critical_downtime_h"]) < 1e-6


def test_impact_benefit_recomputes_from_daily_csv():
    p = RP / "impact.json"
    d = ROOT / "results" / "bench_v3" / "daily.csv"
    if not p.exists() or not d.exists():
        pytest.skip("impact not generated")
    m = json.loads(p.read_text())
    r = pd.read_csv(d)
    rv = r[r.dataset == "rvce"]
    q = rv[rv.method == "qgrid"].set_index("day").sort_index()
    sq = rv[rv.method == "status_quo"].set_index("day").loc[q.index]
    assert abs(m["benefit"]["bill_saving_rs_per_day_mean"] - float((sq.bill_rs - q.bill_rs).mean())) < 1e-6


def test_readme_shows_the_generated_result_sentence():
    b, _ = _bench()
    st = (b.get("headline") or {}).get("story")
    if not st:
        pytest.skip("headline sentences not generated yet")
    readme = (ROOT / "README.md").read_text()
    assert st["step7"]["text"] in readme and "⟨missing" not in readme


def test_the_ui_reads_data_only_through_the_shared_data_layer():
    src = ROOT / "frontend" / "src"
    bad = []
    for f in src.rglob("*.ts*"):
        if f.parent.name == "lib":
            continue
        t = f.read_text()
        for mm in re.finditer(r"\bfetch\(|new WebSocket|['\"`][^'\"`\s]*/replay/", t):
            bad.append(f"{f.relative_to(ROOT)}:{t.count(chr(10), 0, mm.start()) + 1}")
    assert not bad, "data must be loaded through frontend/src/lib (data.ts, story.ts, operate.ts): " + ", ".join(bad)
