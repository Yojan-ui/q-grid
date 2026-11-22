"""Optimiser v2: cuts are valid, decentralised ADMM reaches the central LP, bounds bracket the optimum, the exact
master is exact, the solar forecast never uses future data, and the demand-charge optimum shaves the peak.
Uses the real campus and processed data on a short horizon (8 slots) to keep the tests fast."""
import numpy as np
import pytest

from qgrid import data as qd
from qgrid.model import load_campus, make_day
from qgrid.v2.admm_lp import prices, run_admm
from qgrid.v2.building import BState, BuildingLP, campus_max_kw, layout
from qgrid.v2.central import central_lp
from qgrid.v2.horizon import YearData
from qgrid.v2.master import Master

DAY, OUT = "2023-06-15", ["18:00", "21:00"]


@pytest.fixture(scope="module")
def setup():
    c = load_campus()
    p = qd.load_processed()
    return c, p, YearData(c, p, "A", forecast=False)


def _build(c, yd, t0=68, H=16, peak=True):
    d0 = yd.day_start(DAY)
    w = yd.window(d0, t0, H, OUT)
    tv, oc = c.cfg["tariff_v2"], c.cfg["outage_costs"]
    dem = {"voll_nc": oc["voll_noncritical_rs_kwh"], "voll_c": oc["voll_critical_rs_kwh"],
           "rate_day": tv["demand_rs_per_kva_month"] / tv["days_per_month"], "pf": tv["power_factor"],
           "campus_max_kw": campus_max_kw(c, w), "peak": peak}
    blp, ys, lays = [], [], []
    rng = np.random.default_rng(0)
    for i, b in enumerate(c.buildings):
        st = BState(e=b.battery.e0, level=b.tank.level0 if b.tank else 0.0, dg_on=False, dg_run=99)
        lay = layout(c, i, w, st, t0, 4, 4)
        y = rng.integers(0, 2, lay.ny).astype(float)
        for g in lay.onehot:
            y[g] = 0; y[g[0]] = 1
        for k, v in lay.fixed.items():
            y[k] = v
        lays.append(lay); ys.append(y); blp.append(BuildingLP(c, i, w, st, lay, dem, 0.0))
    return w, dem, lays, blp, ys


def test_cut_is_a_valid_underestimator(setup):
    c, p, yd = setup
    _, _, lays, blp, ys = _build(c, yd)
    rng = np.random.default_rng(1)
    for i in (2, 5, 8):                                   # hostels (DG), admin (DG), pumping station (tank)
        b, y = blp[i], ys[i]
        lam = rng.normal(size=len(b.coupled)) * 0.05
        v0, g, _ = b.lagrangian(y, lam)
        for _ in range(15):
            y2 = y.copy()
            k = rng.choice(len(y), size=min(3, len(y)), replace=False)
            y2[k] = 1 - y2[k]
            for kk, vv in lays[i].fixed.items():
                y2[kk] = vv
            for grp in lays[i].onehot:
                if y2[grp].sum() != 1:
                    y2[grp] = 0; y2[grp[0]] = 1
            v2, _, _ = b.lagrangian(y2, lam)
            assert v0 + g @ (y2 - y) <= v2 + 1e-6 * max(1.0, abs(v2))


def test_admm_reaches_central_lp_and_bounds_bracket(setup):
    c, p, yd = setup
    _, dem, lays, blp, ys = _build(c, yd, peak=False)
    V, _ = central_lp(c, blp, ys)
    res = run_admm(c, blp, ys, 0.1, 800, 0.2)
    assert res.converged
    # physically consistent recovery: flows fixed to the agreed values -> an upper bound close to the optimum
    ub = 0.0
    for i, b in enumerate(blp):
        f = np.concatenate([res.z[l] for (l, _) in b.inc])
        _, ci = b.recover(ys[i], f, b.get(res.x[i], "imp"))
        ub += ci
    assert ub >= V - 1e-6 * abs(V)
    assert (ub - V) / abs(V) < 0.01
    lam = prices(blp, res, c)
    lb = sum(b.lagrangian(y, l)[0] for b, y, l in zip(blp, ys, lam))
    assert lb <= V + 1e-6 * abs(V)                       # Lagrangian bound is a valid lower bound


def test_exact_master_matches_brute_force(setup):
    c, p, yd = setup
    _, _, lays, blp, ys = _build(c, yd, H=8)
    i = 8                                                # pumping station: pump hours + tank constraints
    m = Master(lays[i])
    lam = np.zeros(len(blp[i].coupled))
    for y in (ys[i], 1 - ys[i]):
        v, g, _ = blp[i].lagrangian(y, lam)
        m.add_cut(v, g, y)
    y_ex, J_ex = m.exact()
    n = lays[i].ny
    Z = ((np.arange(1 << n)[:, None] >> np.arange(n)[None, :]) & 1).astype(float)
    assert J_ex <= float(m.J(Z).min()) + 1e-6 * max(1.0, abs(J_ex))


def test_qaoa_master_blocks_respect_qubit_limit_and_never_worsen(setup):
    c, p, yd = setup
    _, _, lays, blp, ys = _build(c, yd)
    i = 2
    m = Master(lays[i])
    v, g, _ = blp[i].lagrangian(ys[i], np.zeros(len(blp[i].coupled)))
    m.add_cut(v, g, ys[i])
    assert all(len(B) <= 16 for B in m.blocks(16))
    y, J, st = m.heuristic(ys[i], "qaoa", seed=3, sweeps=1)
    assert J <= float(m.J(ys[i])[0]) + 1e-9
    assert st.block_solves == len(m.blocks(16))


def test_forecast_uses_no_future_data(setup):
    c, p, _ = setup
    yd = YearData(c, p, "A", forecast=True)
    d0 = yd.day_start(DAY)
    g0 = d0 + 40
    yd.fc.act = yd.fc.act.copy()                         # private copy (the cached array is shared)
    before = yd.fc.per_kwp(g0, 96).copy()
    yd.fc.act[g0:] = 0.0                                 # wipe everything from the decision slot on
    after = yd.fc.per_kwp(g0, 96)
    assert np.allclose(before, after)


def test_demand_charge_optimum_shaves_peak(setup):
    c, p, _ = setup
    from baselines import b4_central_milp
    from qgrid.v2.tariff import settle_v2
    day = make_day(c, p, DAY, "A", "outage_fest", OUT)
    m0 = settle_v2(c, day, b4_central_milp.solve(c, day))
    m1 = settle_v2(c, day, b4_central_milp.solve_dc(c, day))
    assert m1["peak_kva"] <= m0["peak_kva"] + 1e-6
    assert m1["objective_incl_demand_rs"] <= m0["objective_incl_demand_rs"] * (1 + 1e-3)
