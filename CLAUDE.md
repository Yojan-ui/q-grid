# Q-Grid — project rules for Claude Code

Decentralised, quantum-optimised scheduling for campus solar+battery microgrids.
EUREKA hackathon, Track 3: Smart Decentralised Energy Systems. Team lead: Yashas (Yojan-ui).

## Non-negotiables
- Quantum = QAOA on QUBOs (Qiskit). NO post-quantum cryptography in this project.
- No central solver at runtime: consensus-ADMM between neighbouring buildings.
- Every QAOA result is checked for feasibility AND compared to the exact local optimum (brute force).
  Tiered fallback: QAOA -> simulated annealing -> exact. A safety layer clamps every command.
- Never claim quantum advantage. Label: "QAOA on a local simulator: verified against exact
  solutions, no quantum advantage claimed".
- Real data only for headline results (NASA POWER, Ausgrid Solar Home, IEX DAM, CEA CO2).
  Cache raw data in data/raw/ with a SOURCES.md (URL, licence, date fetched). Synthetic data only
  for unit tests, and labelled as synthetic.
- Never invent benchmark numbers or citations. Every number in the UI/README comes from
  results/*.csv produced by scripts in this repo. Verify any paper you cite exists; otherwise omit it.
- All baselines run on identical data, days, constraints and horizon.
- Demo must run offline in replay mode from results/replay/*.json.

## Layout
backend/qgrid/   model, data loaders, qubo, solvers/, admm, safety, node, api
backend/tests/   pytest
baselines/       rule_based, ga_pso, mpc_milp, central_milp, admm_classical
scripts/         fetch_data, run_benchmark, make_replay, kill_node
data/raw, data/processed
results/         benchmark.csv, plots/, replay/
frontend/        Vite + React + react-three-fiber + drei + GSAP + Recharts
docs/            BRIEF.md, qubo.md, results.md, pitch.md

## Workflow
- Small commits with clear messages; push after each phase.
- Run pytest before every commit; never commit failing tests.
- Update README "Status" after each phase.
- Python env: conda env "qgrid" (Python 3.11).
