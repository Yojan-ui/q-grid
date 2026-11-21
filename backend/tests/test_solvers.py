"""Phase 3: QAOA / annealing / exact solvers and tiered fallback. Instances are SYNTHETIC."""
import numpy as np
import pytest

from qgrid import qubo as Q
from qgrid.solvers import solve_local
from qgrid.solvers.anneal import anneal
from qgrid.solvers.exact import approx_ratio, solve_exact
from qgrid.solvers.qaoa import probabilities_aer, run_qaoa, statevector_numpy

from test_model_qubo import lp_example


def test_numpy_statevector_matches_aer():
    rng = np.random.default_rng(3)
    n = 6
    h = rng.normal(size=n)
    J = np.triu(rng.normal(size=(n, n)), 1)
    g, b = np.array([0.4, 0.9]), np.array([0.7, 0.3])
    p_np = np.abs(statevector_numpy(h, J, g, b)) ** 2
    p_aer = probabilities_aer(h, J, g, b)
    assert np.allclose(p_np, p_aer, atol=1e-10)


def test_exact_is_true_feasible_minimum():
    lp = lp_example(rho=0.3, v={0: 40.0, 3: 0.0})
    ex = solve_exact(lp)
    ob = Q.build(lp)[0]
    best = min(ob.energy(x)[0] for x in Q.all_bitstrings(lp.n) if Q.evaluate(lp, x)["feasible"])
    assert ex.objective == pytest.approx(best)
    assert Q.evaluate(lp, ex.x)["feasible"]
    assert approx_ratio(ex.objective, ex) == 1.0


def test_anneal_finds_ground_state_small():
    lp = lp_example(flex=False, lines=((0, 1),))
    total, _, _, g = Q.auto_tune(lp)
    X = anneal(total, seed=0)
    e = total.energy(X)
    assert e.min() == pytest.approx(total.energy(Q.all_bitstrings(lp.n)[g])[0])


@pytest.mark.parametrize("e_now", [21.0, 50.0, 94.0])
@pytest.mark.parametrize("method", ["qaoa", "exact"])
def test_solve_local_always_feasible_and_verified(method, e_now):
    lp = lp_example(e_now=e_now, rho=0.2, v={0: -40.0, 3: 40.0})
    s = solve_local(lp, method=method, seed=0)
    assert Q.evaluate(lp, s.x)["feasible"]
    assert s.metrics["tier"] in ("qaoa", "anneal", "exact")
    assert s.objective <= s.exact_objective + 1e-6 * max(1.0, abs(s.exact_objective))  # verified optimal
    if method == "qaoa":
        assert 0.0 <= s.metrics["qaoa_p_opt"] <= 1.0


def test_qaoa_distribution_and_concentration():
    lp = lp_example()
    total, *_ = Q.auto_tune(lp)
    r = run_qaoa(total, p=2, shots=128, seed=5)
    assert r.probs.sum() == pytest.approx(1.0)
    assert r.samples.shape == (128, lp.n)
    ex = solve_exact(lp)
    # QAOA concentrates probability on the optimum above the uniform baseline
    assert r.probs[ex.opt_mask].sum() > ex.opt_mask.sum() / 2 ** lp.n


def test_qaoa_deterministic_with_seed():
    lp = lp_example()
    total, *_ = Q.auto_tune(lp)
    a, b = run_qaoa(total, seed=11), run_qaoa(total, seed=11)
    assert np.array_equal(a.samples, b.samples)
