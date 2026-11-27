"""Regression tests for bugs found in review (scorecard writer, engine)."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def test_every_method_id_maps_to_a_unique_display_name():
    import run_bench_v3 as rb
    import write_bench_v3 as wb
    ids = list(rb.MAIN) + list(rb.DESIGN)
    names = {m: wb.display_name(m) for m in ids}
    assert len(set(names.values())) == len(ids), names
    assert names["optimum"] == wb.REF[1]
    assert all(names[m] == wb.NAMES[m][0] for m in wb.NAMES)
    assert all(names[m] == wb.DESIGN[m][0] for m in rb.DESIGN)
    # an id the writer does not know is shown as itself, never as another method's name
    assert wb.display_name("some_new_method") == "some_new_method"


def test_wilcoxon_table_names_match_method_ids():
    """The 'where Q-Grid wins/ties/loses' table: every row's method column is that method's own name."""
    p = ROOT / "results" / "bench_v3" / "wilcoxon.csv"
    if not p.exists():
        return
    import write_bench_v3 as wb
    w = pd.read_csv(p)
    for m in w.method.unique():
        assert wb.display_name(m) != m or m not in set(wb.NAMES) | set(wb.DESIGN) | {wb.REF[0]}
        if m != wb.REF[0]:
            assert wb.display_name(m) != wb.REF[1], m


# ---------------------------------------------------------------- diesel while the grid is up (RVCE 2023-06-20)
# Cause: the minimum on-time (safety.dg_decision forces the DG on while 0 < run < min_on) kept a backup DG running
# after the grid returned, in the rule-based controller, the engine's fallback / apply step and the min-on rows of the
# MILPs; and the planners' MILPs allowed DG output in grid-up slots (any price above the diesel cost, e.g. a demand
# term, made them run it in parallel with the grid). The DG is now backup-only: off whenever the grid is up.
def _rvce():
    import pytest
    if not (ROOT / "data" / "processed" / "pv.parquet").exists():
        pytest.skip("processed RVCE data not available")
    sys.path.insert(0, str(ROOT / "scripts"))
    import run_bench_v3 as rb
    return rb, rb.ctx("rvce")


def test_rule_based_dg_stops_when_grid_returns_2023_06_20():
    import numpy as np
    from baselines import b1_rule_based
    from qgrid.model import make_day
    rb, c = _rvce()
    dd = make_day(c["campus"], c["proc"], "2023-06-20", "A", "eval", ["18:00", "18:15"])   # one-slot outage
    s = b1_rule_based.solve(c["campus"], dd)
    up = dd.grid.astype(bool)
    assert s.dg_kw[:, ~up].sum() > 0                      # the DG does cover the outage
    assert np.all(s.dg_kw[:, up] == 0)                    # ...and stops when the grid is back (min on-time cut)


def test_planners_never_run_dg_with_grid_up_2023_06_20():
    import numpy as np
    from baselines import b4_central_milp
    from qgrid.ablation.engine import ACfg, run_day
    from qgrid.model import make_day
    rb, c = _rvce()
    day = "2023-06-20"
    old = rb.PEAK
    rb.PEAK = True
    try:
        dem = rb.planner_demand("rvce", day)
    finally:
        rb.PEAK = old
    dd = make_day(c["campus"], c["proc"], day, "A", "eval", None)                # no outage that day
    s = b4_central_milp.solve(c["campus"], dd, demand=dem)                      # demand term makes import dear
    assert np.all(s.dg_kw == 0)
    out = ["18:00", "18:15"]
    s, _ = run_day(c["campus"], c["yd"], day, out, ACfg(True, True, True, False, share=False, demand=dem))
    up = make_day(c["campus"], c["proc"], day, "A", "eval", out).grid.astype(bool)
    assert np.all(s.dg_kw[:, up] == 0)
