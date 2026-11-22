# Why quantum? — an honest answer

> QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed.
> Real-hardware runs (IBM Quantum, D-Wave Leap) are optional, need the team lead's tokens, and are experimental.

## Where quantum sits in optimiser v2

The v2 optimiser splits each 24 h plan into two halves (hybrid Benders decomposition):

| Half | What it decides | Kind of problem | Solved by |
|---|---|---|---|
| **Master** (combinatorial) | per building and clock hour: diesel on/off, battery charge-or-discharge mode, pump on/off, flexible-load start slot | binary, small, mostly linear with a few couplings (one start per job, tank levels) | **QAOA** on blocks of ≤ 16 qubits, or QIEA / simulated annealing; an exact MILP master runs every time for the lower bound and to check them |
| **Subproblem** (continuous) | battery kW, diesel kW, tie-line flows, grid import/export, campus peak | convex LP | HiGHS / OSQP per building, coordinated by consensus ADMM between neighbours — classical |

The halves talk through **Benders cuts**: each building's LP prices what its binary choices would cost (from its own LP
duals at the prices its neighbours agreed), and its master avoids plans the cuts show to be expensive.

So quantum is used for the part that is genuinely combinatorial — the on/off commitment — and nowhere else. The
continuous dispatch is a convex problem that classical solvers handle exactly; putting it on a quantum computer would
only add noise.

## What the results say (v2 benchmark, `results/v2/`)

1. **No advantage at this size.** Every QAOA master block has ≤ 16 qubits; each block is also brute-forced (2^16 states take
   milliseconds), and QAOA's best measured assignment equalled the exact block optimum in {{v2.scen.V2-QAOA.block_opt_pct|1}} %
   of {{v2.scen.V2-QAOA.block_solves}} blocks. Whole masters driven by QAOA reached the exact MILP master's optimum in
   {{v2.scen.V2-QAOA.master_opt_pct|1}} % of cases. The exact master is faster.
2. **Same schedule quality either way.** On the six named days, the hybrid with a QAOA master averages
   {{v2.V2-QAOA.scenarios.gap_to_opt_pct|2}} % above the central optimum, with a QIEA master {{v2.V2-QIEA.scenarios.gap_to_opt_pct|2}} %,
   and with the exact master {{v2.V2-EXACT.scenarios.gap_to_opt_pct|2}} % (old Q-Grid: {{v2.V1.scenarios.gap_to_opt_pct|2}} %).
   The improvement over v1 comes from the decomposition and the 24 h horizon, not from quantum.
3. **Why decomposition matters for hardware.** The whole-campus 24 h commitment QUBO has {{v2.hw.campus_n}} binaries and
   separates by building, so it never needs to be solved in one piece; per building and hour block it fits today's devices.
   Simulated annealing on the full campus QUBO lands {{v2.hw.sa_gap_pct|2}} % from the exact masters.
4. **Verified, not trusted.** A QAOA proposal is kept only if it lowers the true master objective; the exact master gives the
   bound and the reference, and a safety layer clamps every command. A wrong quantum answer can cost iterations, never safety.
5. **QAOA vs QIEA.** QAOA is a *quantum circuit* (simulated with Qiskit Aer for the demo's shots and with a numpy statevector in
   the benchmark loop, same circuit). QIEA (Han & Kim 2002) is a *quantum-inspired* evolutionary algorithm on a classical CPU.
6. **Real hardware.** `scripts/hardware_v2.py` runs recorded building master blocks on IBM Quantum and the whole-campus QUBO on
   D-Wave Leap, only when the tokens and an explicit opt-in are set. Current status — IBM: {{v2.hw.ibm_status}}; D-Wave:
   {{v2.hw.dwave_status}}. Any hardware numbers will be shown next to the simulator and exact results and labelled noisy.

## v1 (kept for reference)

v1 put QAOA on each zone's 3-slot QUBO inside a binary consensus-ADMM. Binary ADMM is non-convex, so neighbours fully agreed in
only {{admm.conv_pct|0}} % of slots on the scenarios and the rest needed bilateral resolution. v2 runs ADMM only on the convex
LP, where it converges ({{v2.scen.V2-EXACT.admm_conv_pct|0}} % of ADMM runs reached tolerance).
