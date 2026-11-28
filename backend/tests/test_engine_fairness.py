"""Fairness: every planning method prices the same monthly-peak term (qgrid/ablation/demand.py).

SYNTHETIC toy campus (unit test only, never used for results): two buildings joined by one cable, flat price, building A
has an evening peak. Without the peak term no planner has a reason to cycle its battery at the peak (flat price, losses
and wear make cycling cost money); with it, shaving the campus peak is far cheaper than paying the demand rate on it,
so every planner (Q-Grid, per-building MPC, central MPC, best possible plan, GA, PSO) must lower the campus peak."""
from types import SimpleNamespace

import numpy as np
import pytest

from qgrid import data as qd
from qgrid.model import T, Battery, Building, Campus, DayData, Schedule, net_power
from qgrid.v2.horizon import Window

PRICE, EXPORT = 8.0, 3.0


def _campus():
    cfg = qd.load_config()
    bat = lambda: Battery(kwh=200.0, kw=100.0, soc_min=0.2, soc_max=0.95, soc0=0.9, eta_ch=0.95, eta_dis=0.95)   # noqa: E731
    blds = [Building("toy_a", 0.0, 0.05, bat(), []), Building("toy_b", 0.0, 0.05, bat(), [])]
    return Campus(blds, [(0, 1)], 50.0, cfg, {})


def _load():
    a = np.full(2 * T, 100.0)
    for d in (0, T):
        a[d + 72:d + 80] = 200.0          # 18:00-20:00 peak in building A
    return np.vstack([a, np.full(2 * T, 100.0)])


class ToyYear:
    """YearData stand-in (two identical SYNTHETIC days so the 24 h horizon can look past midnight)."""
    def __init__(self):
        self.load = _load()
        self.pv = np.zeros_like(self.load)
        self.crit = 0.05 * self.load
        self.water = np.zeros(2 * T)

    def day_start(self, day):
        return 0

    def window(self, day0, t0, H, outage):
        idx = np.arange(day0 + t0, day0 + t0 + H)
        return Window(int(idx[0]), self.pv[:, idx], self.load[:, idx], self.crit[:, idx], self.water[idx],
                      np.full(H, PRICE), np.full(H, EXPORT), np.ones(H, bool), idx < T, PRICE)


def _day(campus):
    load = _load()[:, :T]
    from qgrid.model import wear_rate
    return DayData("SYNTHETIC", "A", np.zeros_like(load), load, 0.05 * load, np.zeros(T), np.full(T, PRICE),
                   np.full(T, EXPORT), 0.0, 0.0, np.ones(T, bool), 40.0, 1000.0, {}, wear=wear_rate(campus.cfg))


def _demand(contract=None):
    from qgrid.ablation.demand import planner_params
    p = {"rate": 350.0, "pf": 0.95, "floor_frac": 0.85, "excess_mult": 2.0, "contract_kva": contract}
    return planner_params(p, [1.0, 1.0])


def _peak_kva(campus, day, sched):
    net = net_power(campus, day, sched)
    return float(np.maximum(net, 0).sum(axis=0).max()) / 0.95


def _run(method, campus, day, demand):
    from baselines import b2_ga_pso, b4_central_milp
    from qgrid.ablation.engine import ACfg, run_day
    yd = ToyYear()
    if method == "optimum":
        return b4_central_milp.solve(campus, day, demand=demand)
    if method in ("GA", "PSO"):
        return b2_ga_pso.solve(campus, day, method, demand=demand)
    cfg = {"qgrid": ACfg(True, True, True, False, demand=demand),
           "per_building_mpc": ACfg(True, True, True, False, share=False, demand=demand),
           "central_mpc": ACfg(True, True, True, False, central=True, demand=demand)}[method]
    s, _ = run_day(campus, yd, "toy", None, cfg)
    return s


@pytest.mark.parametrize("method", ["qgrid", "per_building_mpc", "central_mpc", "optimum", "GA", "PSO"])
def test_every_planner_shaves_the_campus_peak_when_it_is_priced(method):
    campus = _campus()
    day = _day(campus)
    off = _peak_kva(campus, day, _run(method, campus, day, None))
    on = _peak_kva(campus, day, _run(method, campus, day, _demand()))
    assert off > 300 / 0.95 - 1.0, off              # unpriced: nothing to gain from shaving (flat price)
    assert on < off - 20.0, (method, off, on)        # priced: the campus peak comes down


def test_peak_term_objective_rows():
    """LocalModel's per-building rows and the central campus rows price exactly rate x max(0, peak - budget)."""
    from qgrid.ablation.bounds import _central
    from qgrid.ablation.local import LocalModel, LState
    campus = _campus()
    yd = ToyYear()
    w = yd.window(0, 0, T, None)
    dem = _demand(contract=200.0)
    ref = dem["ref_kva"]
    assert ref == pytest.approx(170.0)
    models = []
    for i, b in enumerate(campus.buildings):
        sh = np.full(T, dem["weights"][i])
        models.append(LocalModel(campus, i, w, LState(e=b.battery.e0, level=0.0), 0, T, disc=False, disc_flows=False,
                                 term_slope=PRICE, voll=(40.0, 1000.0), peak={"rate": 350.0, "pf": 0.95, "budget": ref * sh,
                                 "cbudget": 200.0 * sh, "xs_rate": dem["xs_rate"]}))
    for m in models:
        assert "pk" in m.col and "px" in m.col and len(m.peak_rows) == T
    plain = [LocalModel(campus, i, w, LState(e=b.battery.e0, level=0.0), 0, T, disc=False, disc_flows=False,
                        term_slope=PRICE, voll=(40.0, 1000.0)) for i, b in enumerate(campus.buildings)]
    r0 = _central(campus, plain, relax=True)
    r1 = _central(campus, plain, relax=True, peak=dem)
    assert r1["obj"] > r0["obj"]                      # the campus peak above the floor now costs money


def test_monthly_peak_ref_raised_by_todays_recorded_peak():
    """After the evening peak is recorded, later decisions plan against it (the peak already set this month)."""
    from qgrid.ablation.engine import _realised_peak
    campus = _campus()
    yd = ToyYear()
    s = Schedule.empty(campus)
    states = [SimpleNamespace(started={}) for _ in campus.buildings]
    pk = _realised_peak(campus, yd, 0, 72, 4, None, s, states, 0.95)
    assert pk == pytest.approx(300 / 0.95)
