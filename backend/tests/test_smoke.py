"""Phase 0 smoke test: core stack imports and a tiny Aer circuit runs deterministically."""
import qgrid


def test_label_present():
    assert "no quantum advantage claimed" in qgrid.QUANTUM_LABEL


def test_aer_runs_bell_state():
    from qiskit import QuantumCircuit, transpile
    from qiskit_aer import AerSimulator

    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure_all()
    sim = AerSimulator(seed_simulator=7)
    counts = sim.run(transpile(qc, sim), shots=512).result().get_counts()
    assert set(counts) <= {"00", "11"}


def test_milp_solver_available():
    import pulp

    prob = pulp.LpProblem("t", pulp.LpMinimize)
    x = pulp.LpVariable("x", 0, 10)
    prob += x
    prob += x >= 3
    prob.solve(pulp.HiGHS(msg=False) if pulp.HiGHS().available() else pulp.PULP_CBC_CMD(msg=False))
    assert abs(x.value() - 3) < 1e-6
