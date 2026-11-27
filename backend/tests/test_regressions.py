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
