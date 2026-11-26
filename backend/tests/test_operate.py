"""Operate mode: the session runs the stack on a clock, labels its data, keeps safety in charge of overrides,
logs every operator action, and settles the day against the status quo on the same data."""
import numpy as np
import pytest

from qgrid import data as qd


@pytest.fixture(scope="module")
def S(tmp_path_factory):
    if not (qd.PROC / "pv.parquet").exists():
        pytest.skip("processed data not built")
    from qgrid.model import load_campus
    from qgrid.operate.forecast import OpenMeteo
    from qgrid.operate.session import Session
    OpenMeteo.refresh = lambda self, force=False: False          # offline: no network in tests
    Session._threaded = False
    s = Session(load_campus(), qd.load_processed(), cache_dir=tmp_path_factory.mktemp("wx"), mqtt=False)
    return s


def test_offline_without_forecast_falls_back_to_a_labelled_historical_day(S):
    assert S.source == "historical"
    assert "NASA POWER" in S.data_label["solar"] and "no RVCE meters" in S.data_label["loads"]
    assert S.plan is not None and S.admm["rounds"] >= 1


def test_clock_outage_override_audit_and_report(S):
    S.reset("historical", "2023-06-15")
    S.advance(3600)
    assert S.snapshot()["clock"]["time"] == "07:00"
    S.inject("outage", 30)
    S.advance(15 * 60)
    snap = S.snapshot()
    assert not snap["grid_up_now"] and all(z["state"] in ("island", "shedding") for z in snap["zones"])
    S.override("hostels", "pump", "on", 30)
    actions = [a["action"] for a in S.audit]
    assert "inject outage" in actions and "override" in actions
    S.advance(45 * 60)
    for i, b in enumerate(S.campus.buildings):                    # safety: charge always within limits
        if b.battery.present:
            assert b.battery.e_min - 1e-6 <= S.states[i].e <= b.battery.e_max + 1e-6
    r = S.report()
    assert r["slots"] >= 8 and "status_quo" in r and "Day so far" in r["note"]
    assert any(l["source"] == "Solar" for l in r["flows"]["links"])
    assert all(z["source"] == "simulated" for z in S.snapshot()["zones"])   # no hardware connected: labelled simulated


def test_rule_validation(S):
    bad = S.add_rule("EV charging only after 10 pm")
    assert not all(x["ok"] for x in bad["results"])
    assert "EV charging only after 10 pm" not in S.rule_texts
