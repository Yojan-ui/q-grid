"""Operator rules (parse -> guard -> effect) and deterministic explanations. SYNTHETIC days / instances."""
import numpy as np
import pytest

from qgrid import qubo as Q
from qgrid.admm import run_day
from qgrid.agent import BuildingAgent
from qgrid.explain import explain
from qgrid.model import load_campus, tank_trajectory
from qgrid.rules import apply_rules, guard, parse_rule
from qgrid.solvers import solve_local
from qgrid.synthetic import synthetic_day

from test_model_qubo import lp_example


@pytest.fixture(scope="module")
def campus():
    return load_campus()


@pytest.mark.parametrize("text,ok", [
    ("keep hostel tanks above 40% by 6 am", True),
    ("no DG during exams unless outage", True),
    ("Thermal lab compressor must run Tue 2-4 pm", True),
    ("EV charging only after 10 pm", False),           # 3 h job cannot fit 22:00-24:00 in one day
    ("make the sun shine brighter", False),             # no supported pattern
])
def test_parse_and_guard(campus, text, ok):
    r = parse_rule(text, campus)[0]
    assert r.ok is ok
    if not ok:
        assert r.reason


def test_guard_rejects_bad_values(campus):
    assert not guard({"type": "tank_min_by", "zone": "library", "level_frac": 0.4, "by_time": "06:00"}, campus)[0]
    assert not guard({"type": "tank_min_by", "zone": "pumping_station", "level_frac": 1.5, "by_time": "06:00"}, campus)[0]
    assert not guard({"type": "job_window", "zone": "academic", "job": "nope", "earliest": "08:00", "latest": "12:00"}, campus)[0]
    assert not guard({"type": "dg_forbid", "zone": "library"}, campus)[0]          # library has no DG
    assert not guard({"type": "fixed_run", "zone": "heavy_labs", "day": "Tue", "start": "16:00", "end": "14:00",
                      "kw": 40}, campus)[0]


def test_tank_rule_effect(campus):
    day = synthetic_day(campus)
    i = next(k for k, b in enumerate(campus.buildings) if b.tank)
    campus.buildings[i].tank.level0 = 0.3 * campus.buildings[i].tank.capacity
    try:
        rule = parse_rule("keep hostel tanks above 55% by 6 am", campus)[0].rule
        c2, d2, ar = apply_rules(campus, day, [rule])
        s, _ = run_day(c2, d2, method="exact", rules=ar, t_range=(0, 26))
        lv = tank_trajectory(c2.buildings[i].tank, s.pump_on[i], d2.water)
        assert lv[24] >= 0.55 * c2.buildings[i].tank.capacity - 1e-6
    finally:
        campus.buildings[i].tank.level0 = 0.6 * campus.buildings[i].tank.capacity


def test_dg_rule_effect_in_qubo():
    lp = lp_example(dg=True, grid=np.array([True, True, True]))
    lp.dg.fuel_cost = -500.0                      # make the DG artificially attractive
    assert Q.decode(lp, solve_local(lp, "exact", use_cache=False).x)["dg_on"]
    lp.rule_terms = [{"id": "no_dg", "var": "g", "coef": 1e5}]
    assert not Q.decode(lp, solve_local(lp, "exact", use_cache=False).x)["dg_on"]


def test_fixed_run_adds_critical_load(campus):
    day = synthetic_day(campus)
    day.day = "2023-06-13"                        # a Tuesday
    rule = parse_rule("Thermal lab compressor must run Tue 2-4 pm", campus)[0].rule
    _, d2, _ = apply_rules(campus, day, [rule])
    i = campus.names.index(rule["zone"])
    assert np.allclose(d2.load[i, 56:64] - day.load[i, 56:64], rule["kw"])
    assert np.allclose(d2.crit[i, 56:64] - day.crit[i, 56:64], rule["kw"])


def test_explanations_reference_real_values(campus):
    day = synthetic_day(campus)
    i = campus.names.index("hostels")
    ag = BuildingAgent(campus, day, i)
    lp = ag.local_problem(76, ag.incident)
    sol = solve_local(lp, "exact", use_cache=False)
    ex = explain(lp, sol.x, zone="hostels")
    groups, _, _ = Q.build_groups(lp)
    for e in ex:
        if e["var"].startswith("line"):
            continue
        assert f"Rs {lp.pi[0]:.2f}/kWh" in e["text"] and "hostels" in e["text"]
        y = np.array(sol.x, float); y[lp.idx[e["var"]]] = 1 - y[lp.idx[e["var"]]]
        exact = sum(float(q.energy(y)[0] - q.energy(sol.x)[0]) for q in groups.values())
        assert e["delta_total_rs"] == pytest.approx(exact)
        assert e["delta_total_rs"] >= -1e-6       # the chosen value is locally optimal (verified exact optimum)
