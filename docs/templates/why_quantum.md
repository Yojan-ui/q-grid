# Why quantum? — an honest answer

> QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed.
> Real-hardware runs (IBM Quantum, D-Wave Leap) are optional, need the team lead's tokens, and are experimental.

## Where quantum sits in Q-Grid today: nowhere in the operational loop

Q-Grid's current design (chosen by the ablation, docs/ablation.md):

| Part | What it decides | Solved by |
|---|---|---|
| Inside each building | the 24 h on/off plan (diesel, battery charge-or-discharge mode, pump, job start times), every 15 min | exact branch and bound (HiGHS) at the prices the neighbours agreed |
| Between buildings | battery kW, diesel kW, cable flows, grid import — a linear programme | consensus ADMM between neighbours (convex, converges); no central computer |

The two parts exchange prices until the on/off plans stop changing.

## The test that decided it

We tested the most natural place for a near-term quantum circuit: giving each building's exact solver a starting plan
from QAOA on the small block of on/off choices the relaxed problem leaves undecided (scripts/quantum_placement.py,
{{q3.qp.instances}} building problems from five days).

1. **Branch and bound rarely needs help.** It finished at its first node in {{q3.qp.cold_root_node_pct|1}} % of the problems;
   the relaxed problem left on average {{q3.qp.qaoa_block_qubits_mean|1}} choices undecided, so the quantum blocks were tiny.
2. **QAOA was correct.** Its best measured setting matched exact search on the block in {{q3.qp.qaoa_block_opt_pct|0}} % of blocks,
   and the completed starting plan was optimal in {{q3.qp.incumbent_optimal_pct_all|1}} % of problems.
3. **But it saved no work.** Mean branch-and-bound nodes {{q3.qp.nodes_cold_mean|2}} without a start vs
   {{q3.qp.nodes_warm_mean|2}} with the QAOA start; time {{q3.qp.time_cold_mean_s|3}} s vs {{q3.qp.time_warm_plus_incumbent_mean_s|3}} s
   including the QAOA run. So, following our own rule (remove quantum wherever it is not logical), Q-Grid does not use it.

## Where quantum *was* tried and what it showed

- **First prototype**: QAOA on each building's 3-slot problem inside a binary negotiation. It worked and was verified, but the
  binary negotiation itself was the weak point; the ablation removes {{q3.shap.gap_pct.C|1}} points of gap by replacing it
  (Shapley attribution).
- **Hybrid Benders design**: QAOA on the hourly on/off master, blocks of ≤ 16 qubits, each brute-forced. The exact master was
  faster and at least as good; see docs/consistency.md for why one day looked otherwise.

## Why we keep the quantum code

The structure that makes Q-Grid decentralised also produces small, hardware-sized binary blocks per building. When the
on/off problems get harder (finer resolution, many more devices, discrete power levels — the ablation shows discrete
levels make branch and bound work much harder), a verified quantum starting plan may become useful. The test harness stays
in the repository so that question can be re-asked with data, and the optional hardware path (scripts/hardware_v2.py)
runs only with tokens and an explicit opt-in.

## QAOA vs QIEA

QAOA is a *quantum circuit* (simulated with Qiskit Aer). QIEA (Han & Kim 2002) is a *quantum-inspired* evolutionary algorithm
that runs on a classical CPU; it is not quantum computing. They are labelled separately everywhere.
