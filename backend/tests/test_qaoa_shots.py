"""Aer shots: Qiskit's big-endian count keys map back to variable order, and measured shots follow the
statevector probabilities (synthetic QUBOs, unit test only)."""
import numpy as np
import pytest

from qgrid import qubo as Q
from qgrid.solvers.qaoa import run_qaoa, shots_from_counts


def test_shots_from_counts_bit_order():
    # key '011' means qubit0=1, qubit1=1, qubit2=0 -> variables [1, 1, 0]
    s = shots_from_counts({"011": 2, "100": 1}, 3)
    assert s.shape == (3, 3)
    assert s.tolist().count([1.0, 1.0, 0.0]) == 2
    assert s.tolist().count([0.0, 0.0, 1.0]) == 1


def test_aer_shots_follow_statevector():
    pytest.importorskip("qiskit_aer")
    rng = np.random.default_rng(3)
    n = 5
    M = rng.normal(size=(n, n)); M = np.triu(M + M.T) / 2
    qr = run_qaoa(Q.QUBO(0.0, M), p=2, shots=4000, seed=7, backend="aer")
    assert qr.samples.shape == (4000, n)
    idx = (qr.samples.astype(int) * (1 << np.arange(n))).sum(1)
    emp = np.bincount(idx, minlength=2 ** n) / len(idx)
    # empirical frequencies agree with the Aer statevector probabilities (total variation distance)
    assert 0.5 * np.abs(emp - qr.probs).sum() < 0.08
