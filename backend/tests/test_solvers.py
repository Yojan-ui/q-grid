"""Solvers: QAOA (Aer-verified), QIEA, SA, exact, tiered fallback, warm start, cache. SYNTHETIC instances."""
import numpy as np
import pytest

from qgrid import qubo as Q
from qgrid.solvers import STATS, reset_stats, solve_local
from qgrid.solvers.anneal import anneal
from qgrid.solvers.exact import approx_ratio, solve_exact
from qgrid.solvers.qaoa import probabilities_aer, run_qaoa, statevector_numpy, warm_start_params
from qgrid.solvers.qiea import qiea

from test_model_qubo import lp_example


def test_numpy_statevector_matches_aer():
    rng = np.random.default_rng(3)
    h = rng.normal(size=6); J = np.triu(rng.normal(size=(6, 6)), 1)
    g, b = np.array([0.4, 0.9]), np.array([0.7, 0.3])
    assert np.allclose(np.abs(statevector_numpy(h, J, g, b)) ** 2, probabilities_aer(h, J, g, b), atol=1e-10)


def test_exact_is_feasible_minimum():
    lp = lp_example(rho=0.3, v={0: 40.0, 3: 0.0}, dg=True, tank=True)
    ex = solve_exact(lp)
    ob = Q.build(lp)[0]
    X = Q.all_bitstrings(lp.n)
    feas = Q.feasible_mask(lp, X)
    assert ex.objective == pytest.approx(ob.energy(X[feas]).min())
    assert approx_ratio(ex.objective, ex) == 1.0


def test_anneal_and_qiea_find_ground_state_small():
    lp = lp_example(jobs=False, lines=((0, 1),))
    total, _, _, g = Q.auto_tune(lp)
    e_opt = total.energy(Q.all_bitstrings(lp.n)[g])[0]
    assert total.energy(anneal(total, seed=0)).min() == pytest.approx(e_opt)
    x, e, _ = qiea(total, seed=0, gens=150)
    assert e == pytest.approx(e_opt)


@pytest.mark.parametrize("method", ["qaoa", "qiea", "classical", "exact"])
def test_solve_local_verified(method):
    reset_stats()
    lp = lp_example(rho=0.2, v={0: -40.0, 3: 40.0}, dg=True, tank=True)
    s = solve_local(lp, method=method, seed=0, use_cache=False)
    assert Q.evaluate(lp, s.x)["feasible"]
    assert s.objective <= s.exact_objective + 1e-6 * max(1.0, abs(s.exact_objective))
    assert s.tier in ("qaoa", "qiea", "anneal", "exact")
    if method == "qaoa":
        assert STATS["qaoa_solves"] == 1 and 0 <= s.metrics["qaoa_p_opt"] <= 1


def test_cache_hit():
    reset_stats()
    lp = lp_example()
    a = solve_local(lp, method="classical")
    b = solve_local(lp, method="classical")
    assert STATS["cache_hits"] == 1 and np.array_equal(a.x, b.x)


def test_warm_start_does_not_worsen_expected_energy():
    lp = lp_example()
    total, *_ = Q.auto_tune(lp)
    en = Q.enumerate_all(lp)
    tot_e = en["ob"] + 0  # objective energies
    c, h, J = total.to_ising()
    sig = np.sqrt((h ** 2).sum() + (J ** 2).sum())
    E = (total.energy(Q.all_bitstrings(lp.n)) - c) / sig
    g0, b0 = np.array([0.5, 1.0]), np.array([0.6, 0.3])
    g1, b1 = warm_start_params(E, (g0, b0), 8)
    def f(g, b):
        pr = np.abs(statevector_numpy(np.zeros(lp.n), np.zeros((lp.n, lp.n)), g, b, energies=E)) ** 2
        return float(np.dot(pr.astype(np.float64), E))
    assert f(g1, b1) <= f(g0, b0) + 1e-9
    assert len(tot_e) == 2 ** lp.n


def test_qaoa_concentrates_on_optimum():
    lp = lp_example()
    total, *_ = Q.auto_tune(lp)
    r = run_qaoa(total, p=2, shots=64, seed=5)
    ex = solve_exact(lp)
    assert r.probs.sum() == pytest.approx(1.0)
    assert r.probs[ex.opt_mask].sum() > ex.opt_mask.sum() / 2 ** lp.n
