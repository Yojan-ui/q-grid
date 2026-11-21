# Why quantum? — an honest answer

> QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed.

1. **No advantage at this size.** Each zone's QUBO has at most 14 qubits. Exhaustive search over 2^16 states
   takes milliseconds on a laptop, so the exact optimum is computed for *every* local problem and QAOA is checked against it.
2. **Verified, not trusted.** QAOA's answer is used only when it equals the exact optimum (66.0 % of local solves
   on the 6 scenarios); otherwise the solve falls back to QIEA → simulated annealing → exact. Without the fallback (ablation) the
   schedule gets measurably worse — that is why it exists.
3. **Quality vs qubits and depth.** At 13 qubits, P(optimum) is 0.0077 / 0.0115 /
   0.0149 for p = 1 / 2 / 3 versus 0.00012 for random guessing: QAOA concentrates
   probability on good schedules, and deeper circuits help, but the probability falls quickly with size.
4. **Why decomposition matters for hardware.** A centralised full-day formulation needs N = 4,416 binary variables
   (10^1,329.3 states). Consensus ADMM splits it into hardware-sized subproblems (≤ 14 qubits) that
   neighbouring buildings solve in parallel and coordinate by exchanging only tie-line proposals — the shape near-term devices can run.
5. **QAOA vs QIEA.** QAOA is a *quantum circuit* (simulated here with Qiskit/Aer and a verified numpy statevector). QIEA
   (Han & Kim 2002) is a *quantum-inspired* evolutionary algorithm that runs on a classical CPU; it borrows the Q-bit
   representation and rotation-gate update but is not quantum computing. We label them separately everywhere.
6. **Path to hardware.** `qgrid.solvers.qaoa.run_ibm` is wired but disabled; running on IBM Quantum needs credentials and may
   cost money, so it is off until the team lead approves.
