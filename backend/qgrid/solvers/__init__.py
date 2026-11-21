"""Local QUBO solvers with a tiered, verified fallback.

The exact brute-force optimum is ALWAYS computed (ground truth, n <= 16). Tiers by method:
  "qaoa"      QAOA (quantum circuit, simulated) -> QIEA -> SA -> exact
  "qiea"      QIEA (quantum-inspired, classical CPU) -> SA -> exact
  "classical" SA -> exact
  "exact"     exact only
  "qaoa_only" ablation: any feasible QAOA sample is accepted (fallback only on infeasibility)
A tier's answer is accepted only if feasible and verified optimal (approx ratio >= accept_ratio).
Solved QUBOs are cached; counters record QAOA solves and wall time.
"""
from __future__ import annotations

import hashlib
import time
from collections import OrderedDict
from dataclasses import dataclass, field

import numpy as np

from .. import qubo as Q
from .anneal import anneal
from .exact import approx_ratio, solve_exact
from .qaoa import load_params, run_qaoa
from .qiea import qiea

STATS = {"qaoa_solves": 0, "qaoa_time_s": 0.0, "cache_hits": 0, "solves": 0}
_CACHE: "OrderedDict[str, LocalSolution]" = OrderedDict()
_PARAMS: dict = {}   # warm-start parameters per key (zone)


@dataclass
class LocalSolution:
    x: np.ndarray
    tier: str
    objective: float
    exact_objective: float
    metrics: dict = field(default_factory=dict)
    qaoa_probs: np.ndarray | None = None


def reset_stats():
    for k in STATS:
        STATS[k] = 0 if isinstance(STATS[k], int) else 0.0
    _CACHE.clear()
    _PARAMS.clear()


def _best_feasible(lp, X, obj_q):
    X = np.unique(np.atleast_2d(X), axis=0)
    feas = Q.feasible_mask(lp, X)
    if not feas.any():
        return None, np.inf, False
    Xf = X[feas]
    o = obj_q.energy(Xf)
    i = int(np.argmin(o))
    return Xf[i], float(o[i]), True


def _key(lp, total, method, p) -> str:
    h = hashlib.blake2b(digest_size=16)
    h.update(np.round(total.M, 6).tobytes())
    h.update(np.round([total.const, lp.e_now, lp.tank.level if lp.tank else 0.0], 6).tobytes())
    h.update(("|".join(lp.names) + method + str(p)).encode())
    return h.hexdigest()


def solve_local(lp: Q.LocalProblem, method: str = "qaoa", p: int = 2, shots: int = 256, seed: int = 0,
                accept_ratio: float = 1 - 1e-9, backend: str = "numpy", keep_probs: bool = False,
                warm_key: str | None = None, warm_iters: int = 0, use_cache: bool = True) -> LocalSolution:
    t0 = time.perf_counter()
    STATS["solves"] += 1
    qubos = Q.build(lp)
    ob = qubos[0]
    en = Q.enumerate_all(lp, qubos)
    total, A_x, A_s, _ = Q.auto_tune(lp, qubos, enum=en)
    key = _key(lp, total, method, p) if use_cache and not keep_probs else None
    if key and key in _CACHE:
        STATS["cache_hits"] += 1
        _CACHE.move_to_end(key)
        return _CACHE[key]
    ex = solve_exact(lp, qubos, enum=en)
    m = {"n_qubits": lp.n, "A_x": A_x, "A_s": A_s, "t_exact_s": time.perf_counter() - t0}

    def done(sol):
        if key:
            _CACHE[key] = sol
            if len(_CACHE) > 20000:
                _CACHE.popitem(last=False)
        return sol

    if method == "exact":
        return done(LocalSolution(ex.x, "exact", ex.objective, ex.objective, {**m, "tier": "exact"}))
    probs = None
    if method in ("qaoa", "qaoa_only"):
        tq = time.perf_counter()
        params0 = _PARAMS.get(warm_key) if warm_key else None
        params0 = params0 if params0 is not None else load_params(p)
        qr = run_qaoa(total, p=p, shots=shots, seed=seed, backend=backend, params=params0,
                      total_energies=en["total"], warm_iters=warm_iters)
        if warm_key:
            _PARAMS[warm_key] = (qr.gammas, qr.betas)
        dt_q = time.perf_counter() - tq
        STATS["qaoa_solves"] += 1
        STATS["qaoa_time_s"] += dt_q
        xq, oq, fq = _best_feasible(lp, qr.samples, ob)
        ar_q = approx_ratio(oq, ex) if fq else 0.0
        m.update({"qaoa_p_opt": float(qr.probs[ex.opt_mask].sum()), "qaoa_p_feasible": float(qr.probs[ex.feasible].sum()),
                  "qaoa_feasible": fq, "qaoa_approx_ratio": ar_q, "qaoa_found_opt": bool(fq and ar_q >= 1 - 1e-9),
                  "t_qaoa_s": dt_q})
        probs = qr.probs if keep_probs else None
        if fq and (method == "qaoa_only" or ar_q >= accept_ratio):
            return done(LocalSolution(xq, "qaoa", oq, ex.objective, {**m, "tier": "qaoa"}, probs))
    if method in ("qaoa", "qiea"):
        ti = time.perf_counter()
        xi, _, Xi = qiea(total, seed=seed)
        xb, ob_i, fi = _best_feasible(lp, np.vstack([xi[None, :], Xi]), ob)
        ar_i = approx_ratio(ob_i, ex) if fi else 0.0
        m.update({"qiea_feasible": fi, "qiea_approx_ratio": ar_i, "t_qiea_s": time.perf_counter() - ti})
        if fi and ar_i >= accept_ratio:
            return done(LocalSolution(xb, "qiea", ob_i, ex.objective, {**m, "tier": "qiea"}, probs))
    ta = time.perf_counter()
    xs, os_, fs = _best_feasible(lp, anneal(total, seed=seed), ob)
    ar_s = approx_ratio(os_, ex) if fs else 0.0
    m.update({"sa_feasible": fs, "sa_approx_ratio": ar_s, "t_sa_s": time.perf_counter() - ta})
    if fs and ar_s >= accept_ratio:
        return done(LocalSolution(xs, "anneal", os_, ex.objective, {**m, "tier": "anneal"}, probs))
    return done(LocalSolution(ex.x, "exact", ex.objective, ex.objective, {**m, "tier": "exact"}, probs))
