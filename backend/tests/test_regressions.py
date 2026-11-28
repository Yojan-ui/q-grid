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


# ---------------------------------------------------------------- audit vs backup-only diesel (full scorecard, 28 Nov 2026)
# Cause: the planners cut a DG run's minimum on-time short when the grid returns (baselines/milp.py, ablation/local.py),
# but check_feasibility still demanded the full minimum, so 37 outage-day rows (status quo and the best possible plan
# among them) were marked infeasible. The audit now applies the same rule; a run that stops mid-outage is still flagged.
def test_feasibility_audit_allows_dg_run_cut_by_grid_return():
    import copy

    from baselines import b1_rule_based
    from qgrid.model import check_feasibility, make_day
    rb, c = _rvce()
    campus = c["campus"]
    dd = make_day(campus, c["proc"], "2023-06-20", "A", "eval", ["18:00", "18:15"])     # one-slot outage
    s = b1_rule_based.solve(campus, dd)
    assert s.dg_kw[:, ~dd.grid.astype(bool)].sum() > 0                                  # the DG covers the outage
    assert not [v for v in check_feasibility(campus, s, dd)["violations"] if "min on-time" in v]
    # a run that stops while the grid is still down keeps failing the minimum on-time
    dd2 = make_day(campus, c["proc"], "2023-06-20", "A", "eval", ["18:00", "19:00"])    # four-slot outage
    i = next(k for k, b in enumerate(campus.buildings) if b.dg)
    s2 = copy.deepcopy(s)
    s2.dg_kw[:] = 0.0
    s2.dg_kw[i, 72] = campus.buildings[i].dg.p_min                                       # one slot of a 4-slot outage
    assert [v for v in check_feasibility(campus, s2, dd2)["violations"] if "min on-time" in v]


# ---------------------------------------------------------------- Q-Grid peak budgets (full scorecard, 28 Nov 2026)
# Cause: Q-Grid split the campus peak allowance in proportion to each building's planned import, slot by slot, so a
# building that planned no import at some slot got a near-zero budget there and priced a private peak; once paid, that
# headroom let it import freely at every other slot. On RVCE 2023-02-24 two buildings charged their batteries at the
# 18:00 tariff peak and set a 1,371 kVA month peak (above the 1,300 kVA contract demand). Now a building keeps its
# planned import plus its static share of the headroom while the campus is under the allowance.
def test_peak_budgets_never_starve_a_building_with_campus_headroom():
    import numpy as np
    from qgrid.ablation.engine import _budgets
    pf, cap = 0.95, 1105.0
    w = np.array([0.5, 0.3, 0.2])
    imp = np.array([[400.0, 300.0, 0.0],          # kW per building and slot
                    [300.0, 0.0, 200.0],
                    [0.0, 100.0, 100.0]])
    b = _budgets(imp, w, cap, pf)
    assert np.allclose(b.sum(axis=0), cap)                        # the budgets add up to the campus allowance
    assert np.all(b >= imp / pf - 1e-9)                           # nobody gets less than it planned (headroom here)
    assert np.all(b[imp == 0] > 0)                                # a zero-import slot still has its share of headroom
    over = np.array([[900.0], [300.0], [0.0]])                    # campus above the allowance at this slot
    bo = _budgets(over, w, cap, pf)
    assert np.isclose(bo.sum(), cap) and np.isclose(bo[0, 0] / bo[1, 0], 3.0) and bo[2, 0] == 0.0
    bz = _budgets(np.zeros((3, 1)), w, cap, pf)                   # nothing planned: the static shares
    assert np.allclose(bz[:, 0], w * cap)
    assert np.allclose(_budgets(imp, w, 0.0, pf), 0.0)            # no allowance (no contract demand, start of day)
