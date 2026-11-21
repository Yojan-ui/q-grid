# Q-Grid — Solution Brief

## 1. Problem (Track 3)
A campus has N buildings, each a small microgrid: rooftop solar, battery, flexible loads
(pumps, EV chargers, HVAC pre-cooling), critical loads, grid connection, tie-lines to neighbours.
Every 15 minutes each building decides: battery charge/discharge/idle, which flexible loads run
now vs later, how much power to share with neighbours or import from the grid.
Goal: minimise grid cost and CO2 while always serving critical loads.
Today: solar surplus is exported cheaply at noon and power is bought back expensively in the evening.
These are binary decisions with constraints -> combinatorial -> QUBO -> QAOA.

## 2. Decentralisation: consensus ADMM
No central QUBO (too many qubits, single point of failure). Each building i, iteration k:
1. Solve LOCAL QUBO (~12-16 binary vars) with QAOA -> tie-line proposals x_i
2. Send x_i to neighbours only (no coordinator)
3. Neighbours average proposals -> z
4. Update dual u_i += (x_i - z)
Repeat until |x_i - z| < eps (typically 10-30 iterations).
The ADMM penalty rho/2*(x - z + u)^2 is quadratic, so it fits directly into the QUBO.
Buildings never share private load/battery data, only proposed tie-line flows.

## 3. Local QUBO (per building)
Horizon 4 slots (1 h). Binary vars per slot: battery charge c_t, discharge d_t,
flexible-load starts f_k,t, shared-power bits (2-3 bit encoding per tie-line). ~12-16 qubits.
Minimise: grid cost + lambda*CO2
 + penalties: c_t*d_t, energy-balance violation^2, SoC out of bounds, flexible load not run
 + ADMM consensus term.

## 4. Never-fail design (tiered per building)
Tier 1 QAOA (Qiskit, p=1-3) -> Tier 2 simulated annealing -> Tier 3 exact brute force (2^16).
Brute force always runs as ground truth, so every schedule is provably optimal or has a known gap.
Safety layer: SoC 20-95%, critical loads always on, clamps every command.
Neighbour silent -> tie-line = 0, island mode. ADMM not converged -> last feasible schedule.

## 5. Validation and benchmarks
Same data, days, constraints for all methods:
B0 status quo, B1 rule-based battery, B2 GA/PSO, B3 per-building MPC-MILP,
B4 centralised campus MILP (true optimum), B5 ADMM + classical local solver, OURS ADMM + QAOA.
Metrics: Rs cost/day, kg CO2, % gap to B4, self-consumption %, peak import, runtime,
feasibility rate, QAOA approx ratio and P(optimum), ADMM iterations, recovery after node failure.
Honest claim: beat B0-B3, approach B4 within a few %, while being decentralised, private, robust.
Label: "QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed."

## 6. Demo (3D, four acts)
Act 1 Problem (real-data status-quo day on a 3D campus) -> Act 2 Quantum (QUBO -> QAOA
probability landscape) -> Act 3 Decentralised ADMM negotiation + live node kill ->
Act 4 Results (optimised replay + benchmark bar race vs B4 optimum).
Business: per-building SaaS or share of measured savings.
