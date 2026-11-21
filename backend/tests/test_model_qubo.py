"""Model, safety layer and local QUBO (v2: DG, tanks, outage, multiple jobs). Inputs are SYNTHETIC."""
import numpy as np
import pytest

from qgrid import qubo as Q
from qgrid import safety
from qgrid.model import DG, DT, T, Battery, FlexJob, Schedule, Tank, check_feasibility, load_campus, settle
from qgrid.synthetic import synthetic_day


def bat(**kw):
    d = dict(kwh=100.0, kw=50.0, soc_min=0.2, soc_max=0.95, soc0=0.5, eta_ch=0.95, eta_dis=0.95)
    d.update(kw)
    return Battery(**d)


def lp_example(e_now=50.0, rho=0.0, v=None, jobs=True, dg=False, tank=False, grid=None, lines=((0, 1), (3, -1)),
               pi=None, pe=None):
    H = 3
    pi = np.array([8.0, 9.0, 9.0]) if pi is None else pi
    pe = np.array([3.0, 3.0, 3.0]) if pe is None else pe
    js = [Q.FlexState("pump_a", 20, 6, True, False, 12.0, 9.0, None, 50),
          Q.FlexState("ev", 30, 8, True, False, 10.0, 11.0, None, 60)] if jobs else []
    d = Q.DGState(np.array([60.0, 60, 60]), 150.0) if dg else None
    tk = Q.TankState(100.0, np.array([3.0, 3, 3]), 30.0, 8.0, 40.0, 290.0, 2.0) if tank else None
    return Q.LocalProblem(t=40, bat=bat(), e_now=e_now, r0=np.array([-30.0, 20.0, 40.0]), pi=pi, pe=pe,
                          lines=list(lines), F=40.0, v=v or {}, rho=rho, ctg=(0.001, -5.0, 100.0), jobs=js, dg=d,
                          tank=tk, grid=grid, noncrit=np.array([15.0, 15.0, 15.0]), voll_nc=40.0, voll_c=1000.0)


def test_qubit_budget_all_zones():
    campus = load_campus()
    for i, b in enumerate(campus.buildings):
        n = (6 if b.battery.present else 0) + 2 * len(campus.incident(i)) + (1 if b.dg else 0) + (1 if b.tank else 0)
        assert n <= Q.MAX_QUBITS, (b.name, n)


def test_job_bits_respect_budget():
    lp = lp_example(dg=True, tank=True, lines=((0, 1), (3, -1), (5, 1)))
    assert lp.n <= Q.MAX_QUBITS


def test_ising_conversion_exact():
    rng = np.random.default_rng(0)
    M = rng.normal(size=(6, 6)); M = (M + M.T) / 2
    q = Q.QUBO(1.5, M)
    c, h, J = q.to_ising()
    X = Q.all_bitstrings(6)
    Z = 1 - 2 * X
    assert np.allclose(c + Z @ h + np.einsum("bi,ij,bj->b", Z, J, Z), q.energy(X))


def test_groups_sum_to_objective():
    lp = lp_example(rho=0.4, v={0: 40.0, 3: 0.0}, dg=True, tank=True)
    groups, _, _ = Q.build_groups(lp)
    ob, _, _ = Q.build(lp)
    X = Q.all_bitstrings(lp.n)[::97]
    assert np.allclose(sum(g.energy(X) for g in groups.values()), ob.energy(X))
    assert {"grid", "battery_ctg", "dg_fuel", "water_value", "admm", "flex_timing"} <= set(groups)


def test_surrogate_exact_for_symmetric_prices():
    p = np.array([5.0, 6.0, 4.0])
    lp = lp_example(pi=p, pe=p, jobs=False)
    lp.ctg = (0.0, 0.0, 0.0)
    groups, _, _ = Q.build_groups(lp)
    for x in Q.all_bitstrings(lp.n)[::37]:
        assert groups["grid"].energy(x)[0] == pytest.approx(Q.evaluate(lp, x)["exact_grid_cost"], abs=1e-6)


def test_exclusivity_and_encoding():
    lp = lp_example()
    x = np.zeros(lp.n)
    assert Q.evaluate(lp, x)["feasible"]
    y = x.copy(); y[lp.idx["c0"]] = y[lp.idx["d0"]] = 1
    assert not Q.evaluate(lp, y)["feasible"]
    y = x.copy(); y[lp.idx["p0"]] = y[lp.idx["n0"]] = 1
    assert not Q.evaluate(lp, y)["feasible"]


def test_soc_bounds():
    full = lp_example(e_now=94.0)
    x = np.zeros(full.n); x[full.idx["c0"]] = 1
    assert not Q.evaluate(full, x)["feasible"]
    empty = lp_example(e_now=21.0)
    x = np.zeros(empty.n); x[empty.idx["d0"]] = 1
    assert not Q.evaluate(empty, x)["feasible"]


def test_tank_bounds_and_pump_bit():
    lp = lp_example(tank=True)
    assert lp.has("w")
    lp.tank.level = 288.0           # pumping would overflow
    x = np.zeros(lp.n); x[lp.idx["w"]] = 1
    assert not Q.evaluate(lp, x)["feasible"]
    lp.tank.level = 41.0            # not pumping would drain below the minimum
    assert not Q.evaluate(lp, np.zeros(lp.n))["feasible"]


def test_dg_bit_reduces_residual_and_costs_fuel():
    lp = lp_example(dg=True)
    x = np.zeros(lp.n); x[lp.idx["g"]] = 1
    c0, a = Q.residual_affine(lp, 1)
    assert a[lp.idx["g"]] == -60.0
    groups, _, _ = Q.build_groups(lp)
    assert groups["dg_fuel"].energy(x)[0] == pytest.approx(150.0)


def test_outage_critical_constraint():
    grid = np.array([False, False, False])
    lp = lp_example(grid=grid, jobs=False)
    X = Q.all_bitstrings(lp.n)
    feas = Q.feasible_mask(lp, X)
    for k in range(lp.H):
        if Q.crit_active(lp, k):
            c0, a = Q.residual_affine(lp, k)
            assert np.all(c0 + X[feas] @ a <= lp.noncrit[k] + 1e-6)


def test_rule_term_penalises_variable():
    lp = lp_example(dg=True)
    lp.rule_terms = [{"id": "no_dg", "var": "g", "coef": 1e4}]
    groups, _, _ = Q.build_groups(lp)
    x = np.zeros(lp.n); x[lp.idx["g"]] = 1
    assert groups["rule:no_dg"].energy(x)[0] == pytest.approx(1e4)


def test_auto_tune_ground_state_feasible():
    for kw in ({"e_now": 21.0}, {"e_now": 94.0}, {"tank": True, "dg": True}):
        lp = lp_example(**kw)
        total, _, _, g = Q.auto_tune(lp)
        X = Q.all_bitstrings(lp.n)
        assert Q.feasible_mask(lp, X[g:g + 1])[0]


# ----------------------------------------------------------------------------- safety
def test_battery_clamp():
    b = bat()
    e = b.e0
    for p in np.random.default_rng(2).uniform(-200, 200, 300):
        e = b.step(e, safety.clamp_battery(b, e, p))
        assert b.e_min - 1e-9 <= e <= b.e_max + 1e-9


def test_flex_dg_pump_safety():
    j = FlexJob("x", 10, 4, 20, 60, 50)
    assert not safety.flex_decision(j, 10, False, True) and safety.flex_decision(j, 60, False, False)
    g = DG(100, 0.3, 4, 0.08, 0.25, 90, 2.68)
    assert safety.dg_decision(g, False, 2, True)          # min on-time binds
    assert not safety.dg_decision(g, True, 0, False)      # rule ban
    tk = Tank(300, 100, 45, 290, 30, 8)
    assert safety.pump_decision(tk, 46, 3, False)          # would fall below minimum -> forced on
    assert not safety.pump_decision(tk, 288, 3, True)      # would overflow -> forced off


# ----------------------------------------------------------------------------- model audit
def test_feasibility_audit_flags_violations():
    campus = load_campus()
    day = synthetic_day(campus)
    s = Schedule.empty(campus)
    i_t = next(i for i, b in enumerate(campus.buildings) if b.tank)
    s.pump_on[i_t] = 1.0                       # pump all day -> overflow
    assert not check_feasibility(campus, s, day)["feasible"]
    s = Schedule.empty(campus)
    i_g = next(i for i, b in enumerate(campus.buildings) if b.dg)
    s.dg_kw[i_g, 10] = campus.buildings[i_g].dg.kw   # one slot only -> min on-time violated
    assert not check_feasibility(campus, s, day)["feasible"]
    s = Schedule.empty(campus); s.flows[0, 3] = campus.step_kw * 1.5
    assert not check_feasibility(campus, s, day)["feasible"]


def test_settle_outage_accounting():
    campus = load_campus()
    day = synthetic_day(campus, outage=("18:00", "21:00"))
    s = Schedule.empty(campus)
    m = settle(campus, day, s)
    assert m["unserved_kwh"] > 0 and m["critical_downtime_h"] > 0
    assert m["import_kwh"] == pytest.approx(settle(campus, day, s)["import_kwh"])
    i_g = next(i for i, b in enumerate(campus.buildings) if b.dg)
    s.dg_kw[i_g, 72:84] = campus.buildings[i_g].dg.kw
    m2 = settle(campus, day, s)
    g = campus.buildings[i_g].dg
    assert m2["dg_hours"] == pytest.approx(3.0)
    assert m2["dg_litres"] == pytest.approx(12 * (g.fuel_a * g.kw + g.fuel_b * g.kw) * DT)
    assert m2["unserved_kwh"] < m["unserved_kwh"]
