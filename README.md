# Q-Grid

Decentralised, quantum-optimised scheduling for campus solar+battery microgrids.
EUREKA hackathon — Track 3: Smart Decentralised Energy Systems.

Each building solves a small local QUBO (≤16 qubits) with QAOA, and neighbouring buildings
agree on tie-line flows via consensus-ADMM — no central solver at runtime. Every QAOA result is
checked for feasibility and against the exact local optimum, with a tiered fallback
(QAOA → simulated annealing → exact) and a safety layer that clamps every command.

> QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed.

See [docs/BRIEF.md](docs/BRIEF.md) for the design.

## Status

| Phase | What | State |
|---|---|---|
| 0 | Scaffold (layout, pyproject, Makefile, CI, Vite+R3F frontend) | ✅ done |
| 1 | Real data pipeline, test days, problem-day analysis | ✅ done — NASA POWER + Ausgrid REAL; tariff A, IEX, CEA **PENDING** (labelled stand-ins, see data/SOURCES.md) |
| 2 | Building model, safety layer, local QUBO (≤15 qubits), penalty auto-tuning | ✅ done — see docs/qubo.md |
| 3 | Solvers: QAOA / annealing / exact, tiered fallback | — |
| 4 | Decentralised consensus-ADMM (in-process + networked) | — |
| 5 | Baselines B0–B5 + benchmark | — |
| 6 | Replay export | — |
| 7 | 3D cinematic demo | — |
| 8 | Ship (README, pitch) | — |

## Quick start

```bash
conda activate qgrid          # Python 3.11
make install                  # pip install -e .[dev] + frontend npm install
make test                     # pytest
make demo                     # frontend dev server (offline replay mode)
```

Other targets: `make data`, `make bench`, `make replay` (implemented in later phases).
