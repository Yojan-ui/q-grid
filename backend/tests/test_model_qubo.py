"""Phase 2: building model, safety layer, local QUBO. Inputs are SYNTHETIC unless loaded from config."""
import numpy as np
import pytest

from qgrid import qubo, safety
from qgrid.model import DT, T, Battery, FlexJob, Schedule, check_feasibility, load_campus, settle


def bat(**kw):
    d = dict(kwh=100.0, kw=50.0, soc_min=0.2, soc_max=0.95, soc0=0.5, eta_ch=0.95, eta_dis=0.95)
    d.update(kw)
    return Battery(**d)


def lp_example(e_now=50.0, rho=0.0, v=None, flex=True, pi=None, pe=None, lines=((0, 1), (3, -1))):
    pi = np.array([8.0, 8.0, 9.0, 9.0]) if pi is None else pi
    pe = np.array([3.0, 3.0, 3.0, 3.0]) if pe is None else pe
    fx = qubo.FlexState(kw=20, slots=6, can_start=True, must_start=False, tail_cost=12.0, defer_cost=9.0) if flex else None
    return qubo.LocalProblem(t=40, bat=bat(), e_now=e_now, r0=np.array([-30.0, -10.0, 20.0, 40.0]), pi=pi, pe=pe,
                             lines=list(lines), F=40.0, v=v or {}, rho=rho, ctg=(0.001, -5.0, 100.0), flex=fx)


# ----------------------------------------------------------------------------- QUBO structure
def test_qubit_budget_all_buildings():
    campus = load_campus()
    for i, b in enumerate(campus.buildings):
        deg = len(campus.incident(i))
        n = 2 * 4 + 2 * deg + (1 if b.flex else 0)
        assert n <= 16, (b.name, n)


def test_ising_conversion_exact():
    rng = np.random.default_rng(0)
    M = rng.normal(size=(6, 6)); M = (M + M.T) / 2
    q = qubo.QUBO(1.5, M)
    c, h, J = q.to_ising()
    X = qubo.all_bitstrings(6)
    Z = 1 - 2 * X
    e_ising = c + Z @ h + np.einsum("bi,ij,bj->b", Z, J, Z)
    assert np.allclose(e_ising, q.energy(X))


def test_objective_matches_direct_formula():
    lp = lp_example(rho=0.5, v={0: 20.0, 3: -40.0})
    ob, px, ps = qubo.build(lp)
    rng = np.random.default_rng(1)
    for x in rng.integers(0, 2, size=(25, lp.n)):
        direct = 0.0
        for k in range(lp.H):
            c0, a = qubo.residual_affine(lp, k)
            g, al, be = qubo.fit_cost_surrogate(c0, a, lp.pi[k], lp.pe[k])
            r = c0 + a @ x
            direct += DT * (g + al * r + be * r * r)
        e0, ae = qubo.energy_affine(lp, lp.H - 1)
        eH = e0 + ae @ x
        direct += 0.001 * eH ** 2 - 5.0 * eH + 100.0
        s = x[lp.is_()]
        direct += s * 12.0 + (1 - s) * 9.0
        for j, (l, _) in enumerate(lp.lines):
            f = 40.0 * (x[lp.ip(j)] - x[lp.in_(j)])
            direct += 0.25 * (f - lp.v[l]) ** 2
        assert ob.energy(x)[0] == pytest.approx(direct, rel=1e-9, abs=1e-6)


def test_surrogate_exact_for_symmetric_prices():
    p = np.array([5.0, 5.0, 6.0, 4.0])
    lp = lp_example(pi=p, pe=p, flex=False)
    lp.ctg = (0.0, 0.0, 0.0)
    ob, _, _ = qubo.build(lp)
    X = qubo.all_bitstrings(lp.n)
    for x in X[::37]:
        assert ob.energy(x)[0] == pytest.approx(qubo.evaluate(lp, x)["exact_grid_cost"], abs=1e-6)


# ----------------------------------------------------------------------------- constraints
def test_exclusivity_and_encoding_infeasible():
    lp = lp_example()
    x = np.zeros(lp.n, dtype=int)
    assert qubo.evaluate(lp, x)["feasible"]
    y = x.copy(); y[lp.ic(0)] = y[lp.id(0)] = 1
    assert not qubo.evaluate(lp, y)["feasible"]
    y = x.copy(); y[lp.ip(0)] = y[lp.in_(0)] = 1
    assert not qubo.evaluate(lp, y)["feasible"]


def test_soc_bounds_infeasible_near_full_and_empty():
    full = lp_example(e_now=94.0)   # e_max = 95
    x = np.zeros(full.n, dtype=int); x[full.ic(0)] = 1
    assert not qubo.evaluate(full, x)["feasible"]
    empty = lp_example(e_now=21.0)  # e_min = 20
    x = np.zeros(empty.n, dtype=int); x[empty.id(0)] = 1
    assert not qubo.evaluate(empty, x)["feasible"]


def test_auto_tune_ground_state_feasible():
    for e in (21.0, 50.0, 94.0):
        lp = lp_example(e_now=e)
        total, A_x, A_s, g = qubo.auto_tune(lp)
        X = qubo.all_bitstrings(lp.n)
        assert qubo.feasible_mask(lp, X[g:g + 1])[0]
        assert int(np.argmin(total.energy(X))) == g


def test_flex_must_start_has_no_bit_and_adds_load():
    lp = lp_example()
    lp.flex = qubo.FlexState(kw=20, slots=6, can_start=True, must_start=True, tail_cost=5.0)
    assert lp.n == 8 + 4 and not lp.has_s
    c0, _ = qubo.residual_affine(lp, 0)
    assert c0 == pytest.approx(lp.r0[0] + 20)


# ----------------------------------------------------------------------------- safety
def test_safety_battery_clamp_keeps_soc_in_bounds():
    b = bat()
    rng = np.random.default_rng(2)
    e = b.e0
    for p in rng.uniform(-200, 200, size=500):
        p2 = safety.clamp_battery(b, e, p)
        assert abs(p2) <= b.kw + 1e-9
        e = b.step(e, p2)
        assert b.e_min - 1e-9 <= e <= b.e_max + 1e-9


def test_safety_flex_and_flow():
    j = FlexJob("x", 10, 4, earliest=20, latest=60, default=50)
    assert not safety.flex_decision(j, 10, False, True)      # before window
    assert safety.flex_decision(j, 30, False, True)
    assert not safety.flex_decision(j, 30, False, False)
    assert safety.flex_decision(j, 60, False, False)         # forced at latest
    assert not safety.flex_decision(j, 61, True, True)       # already started
    assert safety.clamp_flow(99, 40) == 40 and safety.clamp_flow(-99, 40) == -40
    assert safety.critical_served(100, 0.3, 30) and not safety.critical_served(100, 0.3, 29)


# ----------------------------------------------------------------------------- model audit
def test_feasibility_audit_flags_violations():
    campus = load_campus()
    s = Schedule.empty(campus)
    assert check_feasibility(campus, s)["feasible"]
    s.p_bat[0, 5] = campus.buildings[0].battery.kw * 2
    assert not check_feasibility(campus, s)["feasible"]
    s = Schedule.empty(campus); s.flows[0, 3] = campus.step_kw * 1.5
    assert not check_feasibility(campus, s)["feasible"]
    s = Schedule.empty(campus); j = campus.buildings[0].flex[0]
    s.flex_start[0][j.name] = j.latest + 1
    assert not check_feasibility(campus, s)["feasible"]
    s = Schedule.empty(campus); s.p_bat[1, :] = -campus.buildings[1].battery.kw   # drains below soc_min
    assert not check_feasibility(campus, s)["feasible"]


def test_settle_energy_balance_synthetic():
    from qgrid.model import DayData
    campus = load_campus()
    n = campus.n
    day = DayData("synthetic", "A", pv=np.full((n, T), 10.0), load=np.full((n, T), 30.0),
                  price_imp=np.full(T, 8.0), price_exp=np.full(T, 3.0), ef=0.7, lam=0.0, status={})
    s = Schedule.empty(campus)
    s.flex_start = [{j.name: j.default for j in b.flex} for b in campus.buildings]
    m = settle(campus, day, s)
    flex_kwh = sum(j.kw * j.slots * DT for b in campus.buildings for j in b.flex)
    assert m["import_kwh"] == pytest.approx(n * 20 * 24 + flex_kwh)
    # a lossless tie-line transfer between two importing buildings leaves the total unchanged
    s.flows[0, :] = 10.0
    assert settle(campus, day, s)["import_kwh"] == pytest.approx(m["import_kwh"])
