"""Decentralised ADMM (in-process + networked), kill-node, outage, C-QIEA. SYNTHETIC day (CI has no real data)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from qgrid.admm import consensus_update, initial_duals, run_day
from qgrid.model import T, check_feasibility, load_campus, settle
from qgrid.synthetic import synthetic_day

ROOT = Path(__file__).resolve().parents[2]


def test_consensus_and_duals():
    z, u = consensus_update(40.0, 0.0, 0.0)
    assert z == 20.0 and u == 20.0
    ua, ub = initial_duals(4.0, 8.0, 0.1, 3)
    assert ua == -ub and ub > 0


@pytest.fixture(scope="module")
def campus():
    return load_campus()


@pytest.mark.parametrize("method", ["classical", "qaoa"])
def test_admm_day_feasible_and_beats_status_quo(campus, method):
    from baselines import b0_status_quo
    day = synthetic_day(campus)
    sched, st = run_day(campus, day, method=method, log=True, t_range=(36, 60))
    assert check_feasibility(campus, sched, day)["feasible"]
    assert settle(campus, day, sched)["objective_rs"] < settle(campus, day, b0_status_quo.solve(campus, day))["objective_rs"]
    s = st.summary()
    assert len(st.iters) == T and 0 <= s["admm_convergence_rate"] <= 1
    assert {"t", "k", "proposals", "z", "u", "r_primal", "r_dual", "agreed"} <= set(st.log[0])


def test_outage_island_feasible_and_better_than_status_quo(campus):
    from baselines import b0_status_quo
    day = synthetic_day(campus, outage=("18:00", "21:00"))
    sched, _ = run_day(campus, day, method="classical", t_range=(66, 90))
    assert check_feasibility(campus, sched, day)["feasible"]
    m, m0 = settle(campus, day, sched), settle(campus, day, b0_status_quo.solve(campus, day))
    assert m["critical_unserved_kwh"] <= m0["critical_unserved_kwh"] + 1e-6
    assert m["import_kwh"] >= 0


def test_kill_node_islands_and_stays_feasible(campus):
    day = synthetic_day(campus, seed=1)
    k = campus.names.index("heavy_labs")
    sched, st = run_day(campus, day, method="classical", kill=(k, 40), t_range=(36, 52))
    assert check_feasibility(campus, sched, day)["feasible"]
    for l, (a, b) in enumerate(campus.lines):
        if k in (a, b):
            assert np.all(sched.flows[l, 40:] == 0)
    assert st.kill is not None


def test_c_qiea_feasible(campus):
    from baselines import c_qiea
    day = synthetic_day(campus)
    s = c_qiea.solve(campus, day, gens=40)
    assert check_feasibility(campus, s, day)["feasible"]


def test_networked_nodes_with_crash(tmp_path, campus):
    env = {**os.environ, "PYTHONPATH": f"{ROOT / 'backend'}:{ROOT}"}
    procs, outs = [], {}
    victim = "heavy_labs"
    for b in campus.names:
        out = tmp_path / f"{b}.json"
        outs[b] = out
        cmd = [sys.executable, "-m", "qgrid.node", "--building", b, "--day", "SYNTHETIC", "--synthetic",
               "--method", "exact", "--port-base", "18765", "--slots", "5", "--out", str(out)]
        if b == victim:
            cmd += ["--die-at-slot", "2"]
        procs.append(subprocess.Popen(cmd, cwd=ROOT, env=env))
    for p in procs:
        p.wait(timeout=180)
    recs = {b: json.loads(o.read_text()) for b, o in outs.items() if o.exists()}
    survivors = [b for b in campus.names if b != victim]
    for b in survivors:
        assert len(recs[b]["p_bat"]) == 5
    vi = campus.names.index(victim)
    for j in campus.neighbours(vi):
        assert victim in recs[campus.names[j]]["dead_neighbours"]
    for b in survivors:
        if campus.names.index(b) not in campus.neighbours(vi):
            assert recs[b]["dead_neighbours"] == {}
    for l, (a, c) in enumerate(campus.lines):
        A, C = campus.names[a], campus.names[c]
        if A in survivors and C in survivors:
            assert recs[A]["flows"][str(l)] == recs[C]["flows"][str(l)]
