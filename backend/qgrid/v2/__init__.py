"""Optimiser v2: 24 h rolling-horizon MPC with a hybrid Benders decomposition.

Master (binary, combinatorial): per building, hourly on/off commitment of the diesel generator, battery
charge/discharge mode, pump and flexible-load start slots. Solved by QAOA on blocks of <= 16 qubits (verified
against exact search), QIEA, simulated annealing, or exactly (MILP) for verification.
Subproblem (continuous, convex): battery power, diesel output, tie-line flows, grid import/export and peak
demand given the binaries, solved decentralised by consensus ADMM between neighbouring buildings (convex, so
it converges). Benders optimality cuts come from each building's own LP duals.

QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed.
"""
