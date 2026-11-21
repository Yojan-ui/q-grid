"""Tier 1: QAOA (Qiskit circuit; simulated locally).

Circuit: |+>^n, then p layers of  exp(-i gamma_k H_C)  [RZ(2 gamma h_i), RZZ(2 gamma J_ij)]
and the mixer exp(-i beta_k sum X_i)  [RX(2 beta)], H_C = normalised Ising form of the QUBO.

Simulators
  * "aer":   qiskit-aer statevector / shot simulation of the Qiskit circuit (reference).
  * "numpy": exact statevector evolution of the same circuit in numpy (diagonal phase + per-qubit RX).
             Numerically identical to Aer (unit-tested); used for the bulk benchmark because it avoids
             per-call transpilation. Both are classical simulations of an ideal (noiseless) device.
Parameters are pre-trained once (scripts/train_qaoa_params.py) on instances from training days that are
disjoint from the test / evaluation days, and reused (parameter transfer); per-instance optimisation is
available for the scaling study.
Optional IBM backend: only with an explicit opt-in (QGRID_ALLOW_IBM=1 + saved account) — never by default.

QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .. import qubo as Q

ROOT = Path(__file__).resolve().parents[3]
PARAMS_FILE = ROOT / "results" / "qaoa_params.json"


def normalised_ising(q: Q.QUBO):
    c, h, J = q.to_ising()
    sigma = float(np.sqrt((h ** 2).sum() + (J ** 2).sum())) or 1.0
    return h / sigma, J / sigma, sigma


def ising_energies(h: np.ndarray, J: np.ndarray) -> np.ndarray:
    """E(z) for every basis state, state index = sum_i bit_i 2^i, z_i = 1 - 2 bit_i."""
    X = Q.all_bitstrings(len(h))
    Z = 1 - 2 * X
    with np.errstate(all="ignore"):
        return Z @ h + ((Z @ J) * Z).sum(axis=1)


def statevector_numpy(h, J, gammas, betas, energies=None) -> np.ndarray:
    n = len(h)
    E = ising_energies(h, J) if energies is None else energies
    psi = np.full(2 ** n, 2 ** (-n / 2), dtype=np.complex128)
    for g, b in zip(gammas, betas):
        psi *= np.exp(-1j * g * E)
        c, s = np.cos(b), -1j * np.sin(b)
        for q in range(n):
            v = psi.reshape(2 ** (n - 1 - q), 2, 2 ** q)
            a0, a1 = v[:, 0, :].copy(), v[:, 1, :].copy()
            v[:, 0, :] = c * a0 + s * a1
            v[:, 1, :] = s * a0 + c * a1
    return psi


def build_circuit(h, J, gammas, betas, measure: bool = False):
    from qiskit import QuantumCircuit

    n = len(h)
    qc = QuantumCircuit(n)
    qc.h(range(n))
    for g, b in zip(gammas, betas):
        for i in range(n):
            if abs(h[i]) > 1e-12:
                qc.rz(2 * g * h[i], i)
        for i in range(n):
            for j in range(i + 1, n):
                if abs(J[i, j]) > 1e-12:
                    qc.rzz(2 * g * J[i, j], i, j)
        qc.rx(2 * b, range(n))
    if measure:
        qc.measure_all()
    return qc


def probabilities_aer(h, J, gammas, betas, seed: int = 0) -> np.ndarray:
    from qiskit import transpile
    from qiskit_aer import AerSimulator

    qc = build_circuit(h, J, gammas, betas)
    qc.save_statevector()
    sim = AerSimulator(method="statevector", seed_simulator=seed)
    sv = np.asarray(sim.run(transpile(qc, sim)).result().get_statevector())
    return np.abs(sv) ** 2


def counts_aer(h, J, gammas, betas, shots: int, seed: int = 0) -> dict[str, int]:
    from qiskit import transpile
    from qiskit_aer import AerSimulator

    qc = build_circuit(h, J, gammas, betas, measure=True)
    sim = AerSimulator(seed_simulator=seed)
    return sim.run(transpile(qc, sim), shots=shots).result().get_counts()


def run_ibm(*_args, **_kw):  # pragma: no cover - never runs without explicit opt-in
    if os.environ.get("QGRID_ALLOW_IBM") != "1":
        raise RuntimeError("IBM Quantum backend disabled: costs money / needs credentials. "
                           "Set QGRID_ALLOW_IBM=1 and save an account with qiskit-ibm-runtime to opt in.")
    raise NotImplementedError("IBM execution intentionally not wired into the benchmark.")


def ramp_params(p: int) -> tuple[np.ndarray, np.ndarray]:
    """Linear-ramp (annealing-inspired) initial parameters."""
    k = (np.arange(p) + 0.5) / p
    return 0.8 * k, 0.8 * (1 - k)


def load_params(p: int) -> tuple[np.ndarray, np.ndarray]:
    if PARAMS_FILE.exists():
        d = json.loads(PARAMS_FILE.read_text())
        if str(p) in d["params"]:
            e = d["params"][str(p)]
            return np.array(e["gammas"]), np.array(e["betas"])
    return ramp_params(p)


def optimise_params(cases, p: int, maxiter: int = 200, x0=None):
    """Minimise mean expected normalised energy over `cases` [(energies E), ...] with COBYLA."""
    from scipy.optimize import minimize

    g0, b0 = ramp_params(p) if x0 is None else x0

    def f(theta):
        g, b = theta[:p], theta[p:]
        tot = 0.0
        for E in cases:
            n = int(np.log2(len(E)))
            pr = np.abs(statevector_numpy(np.zeros(n), np.zeros((n, n)), g, b, energies=E)) ** 2
            tot += float(np.einsum("i,i->", pr, E))
        return tot / len(cases)

    res = minimize(f, np.concatenate([g0, b0]), method="COBYLA", options={"maxiter": maxiter, "rhobeg": 0.2})
    return res.x[:p], res.x[p:], float(res.fun)


@dataclass
class QAOAResult:
    probs: np.ndarray
    samples: np.ndarray        # (shots, n) sampled bitstrings
    gammas: np.ndarray
    betas: np.ndarray
    sigma: float


def run_qaoa(total: Q.QUBO, p: int = 2, shots: int = 256, seed: int = 0, backend: str = "numpy",
             params=None, total_energies: np.ndarray | None = None, warm_iters: int = 0) -> QAOAResult:
    """total_energies (optional): QUBO energies of all bitstrings; the Ising diagonal is then
    (E - c)/sigma exactly, which avoids recomputing it."""
    c, h, J = total.to_ising()
    sigma = float(np.sqrt((h ** 2).sum() + (J ** 2).sum())) or 1.0
    h, J = h / sigma, J / sigma
    g, b = params if params is not None else load_params(p)
    if warm_iters > 0 and total_energies is not None:
        g, b = warm_start_params((total_energies - c) / sigma, (np.asarray(g), np.asarray(b)), warm_iters)
    if backend == "aer":
        probs = probabilities_aer(h, J, g, b, seed=seed)
    else:
        E = None if total_energies is None else (total_energies - c) / sigma
        probs = np.abs(statevector_numpy(h, J, g, b, energies=E)) ** 2
    probs = probs / probs.sum()
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(probs), size=shots, p=probs)
    return QAOAResult(probs, Q.all_bitstrings(len(h))[idx], np.asarray(g), np.asarray(b), sigma)


def warm_start_params(E_norm: np.ndarray, params0, iters: int):
    """Refine (gamma, beta) for this instance with a few COBYLA steps starting from params0 (the zone's
    previous parameters). E_norm = normalised Ising diagonal of the instance."""
    if iters <= 0:
        return params0
    from scipy.optimize import minimize
    g0, b0 = params0
    p = len(g0)
    n = int(np.log2(len(E_norm)))

    def f(th):
        pr = np.abs(statevector_numpy(np.zeros(n), np.zeros((n, n)), th[:p], th[p:], energies=E_norm)) ** 2
        with np.errstate(all="ignore"):
            return float(pr @ E_norm)

    res = minimize(f, np.concatenate([g0, b0]), method="COBYLA", options={"maxiter": iters, "rhobeg": 0.05})
    return res.x[:p], res.x[p:]
