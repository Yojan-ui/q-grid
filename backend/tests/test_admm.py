"""Phase 4: decentralised consensus ADMM (in-process + networked). SYNTHETIC day (CI has no real data)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from qgrid.admm import consensus_update, run_day
from qgrid.model import T, check_feasibility, load_campus, settle
from qgrid.synthetic import synthetic_day

ROOT = Path(__file__).resolve().parents[2]


def test_consensus_update_math():
    z, u = consensus_update(40.0, 0.0, 0.0)
    assert z == 20.0 and u == 20.0
    z, u = consensus_update(40.0, 40.0, 5.0)
    assert z == 40.0 and u == 5.0   # agreement leaves the dual unchanged


@pytest.fixture(scope="module")
def campus():
    return load_campus()


@pytest.mark.parametrize("method", ["exact", "qaoa"])
def test_admm_day_feasible_and_beats_status_quo(campus, method):
    from baselines import b0_status_quo
    day = synthetic_day(campus)
    sched, st = run_day(campus, day, method=method, log=True)
    assert check_feasibility(campus, sched)["feasible"]
    assert settle(campus, day, sched)["cost_rs"] < settle(campus, day, b0_status_quo.solve(campus, day))["cost_rs"]
    assert len(st.iters) == T and max(st.iters) <= campus.cfg["admm"]["max_iter"]
    rec = st.log[0]
    assert {"t", "k", "proposals", "z", "u", "r_primal", "r_dual", "agreed"} <= set(rec)
    # every flexible job ran exactly once inside its window
    for i, b in enumerate(campus.buildings):
        for j in b.flex:
            assert j.earliest <= sched.flex_start[i][j.name] <= j.latest


def test_admm_kill_node_islands_and_stays_feasible(campus):
    day = synthetic_day(campus, seed=1)
    k = campus.names.index("lab_block")
    sched, st = run_day(campus, day, method="exact", kill=(k, 40))
    assert check_feasibility(campus, sched)["feasible"]
    for l, (a, b) in enumerate(campus.lines):
        if k in (a, b):
            assert np.all(sched.flows[l, 40:] == 0)
    assert np.all(sched.p_bat[k, 40:] == 0)
    assert st.kill["slots_to_reconverge"] is not None and st.kill["slots_to_reconverge"] <= 4


def test_networked_nodes_with_crash(tmp_path, campus):
    """5 OS processes over websockets, no coordinator; lab_block crashes at slot 2 of 5."""
    env = {**os.environ, "PYTHONPATH": f"{ROOT / 'backend'}:{ROOT}"}
    procs, outs = [], {}
    for b in campus.names:
        out = tmp_path / f"{b}.json"
        outs[b] = out
        cmd = [sys.executable, "-m", "qgrid.node", "--building", b, "--day", "SYNTHETIC", "--synthetic",
               "--method", "exact", "--port-base", "18765", "--slots", "5", "--out", str(out)]
        if b == "lab_block":
            cmd += ["--die-at-slot", "2"]
        procs.append(subprocess.Popen(cmd, cwd=ROOT, env=env))
    for p in procs:
        p.wait(timeout=120)
    recs = {b: json.loads(o.read_text()) for b, o in outs.items() if o.exists()}
    assert "lab_block" not in recs or len(recs["lab_block"]["p_bat"]) == 2
    survivors = [b for b in campus.names if b != "lab_block"]
    for b in survivors:
        assert len(recs[b]["p_bat"]) == 5
    for b in ("hostel", "library", "canteen"):   # lab_block's neighbours detected the silence
        assert "lab_block" in recs[b]["dead_neighbours"]
    assert recs["admin"]["dead_neighbours"] == {}  # no false death cascade
    for l, (a, c) in enumerate(campus.lines):
        A, C = campus.names[a], campus.names[c]
        if A in survivors and C in survivors:
            assert recs[A]["flows"][str(l)] == recs[C]["flows"][str(l)]
