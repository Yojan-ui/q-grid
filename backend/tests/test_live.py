"""Live demo moments: each answers in under 5 s, works from the replay files, and states its what-if label."""
import time

import pytest

from qgrid import data as qd


@pytest.fixture(scope="module")
def client():
    if not (qd.PROC / "pv.parquet").exists():
        pytest.skip("processed data not built")
    from fastapi.testclient import TestClient
    from qgrid.api import app
    c = TestClient(app)
    c.get("/health")
    return c


def _timed(c, path, body):
    t0 = time.perf_counter()
    r = c.post(path, json=body)
    assert r.status_code == 200, r.text
    return r.json(), time.perf_counter() - t0


def test_rule_presets_are_validated_and_priced_quickly(client):
    from qgrid.live import PRESETS
    oks = []
    for t in PRESETS:
        r, dt = _timed(client, "/live/rule", {"text": t, "scenario": "outage_fest"})
        assert dt < 5.0
        oks.append(all(x["ok"] for x in r["results"]))
        if r["effect"]:
            assert r["effect"]["before"]["status"] == "Optimal"
            # a constraint can never make the best possible plan cheaper on the objective it minimises
            if r["effect"]["after"].get("status") == "Optimal":
                assert r["effect"]["after"]["objective_rs"] >= r["effect"]["before"]["objective_rs"] - 1e-3 * abs(r["effect"]["before"]["objective_rs"])
    assert oks == [True, True, False]       # one binding, one cheap, one rejected by validation


def test_qaoa_block_is_checked_against_exact(client):
    r, dt = _timed(client, "/live/qaoa", {"scenario": "outage_fest", "seed": 5})
    assert dt < 5.0
    assert r["label"].startswith("QAOA on a local simulator")
    assert r["qaoa"]["best_objective"] >= r["exact"]["objective"] - 1e-6 * max(1.0, abs(r["exact"]["objective"]))
