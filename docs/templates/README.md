# Q-Grid — decentralised, QAOA-verified scheduling for the RVCE campus microgrid

EUREKA Track 3 · Smart Decentralised Energy Systems

![Q-Grid demo](docs/media/hero.gif)

> QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed.
> QIEA = quantum-inspired evolutionary algorithm on a classical CPU (not quantum computing).

**Data status:** real NASA POWER irradiance, Ausgrid household shapes (hostels), OpenStreetMap layout (© OpenStreetMap
contributors). **PENDING:** KERC/BESCOM tariff ({{price_A_status}}), IEX prices ({{price_B_status}}), CEA CO2 factor, RVCE calendar
and meter data — labelled stand-ins, never headline results. See `data/SOURCES.md`, `docs/BLOCKERS.md`, `docs/data_request.md`.

## The problem (status quo, from results/*.csv)
BESCOM outage during the fest evening: status quo **{{headline.before.critical_downtime_h|2}} h** of critical-load downtime,
{{headline.before.dg_hours|1}} DG hours, Rs {{headline.before.cost_rs}} for the day (stand-in prices).

## Result
| Outage during fest (scenario A) | Status quo | Q-Grid | Central optimum (B4) |
|---|---:|---:|---:|
| Critical-load downtime (h) | {{headline.before.critical_downtime_h|2}} | **{{headline.after.critical_downtime_h|2}}** | {{headline.optimum_B4.critical_downtime_h|2}} |
| Cost (Rs/day) | {{headline.before.cost_rs}} | {{headline.after.cost_rs}} | {{headline.optimum_B4.cost_rs}} |
| DG hours | {{headline.before.dg_hours|2}} | {{headline.after.dg_hours|2}} | – |
| Re-plan time per slot | – | {{headline.after.replan_time_s|3}} s | – |

30-day evaluation set (scenario A, mean Rs/day): status quo {{B0.eval30_mean.A.cost_rs}} · per-zone MILP {{B3.eval30_mean.A.cost_rs}} ·
**Q-Grid {{OURS.eval30_mean.A.cost_rs}}** ({{OURS.eval30_mean.A.gap_to_B4_pct|2}} % above optimum) · central optimum {{B4.eval30_mean.A.cost_rs}}.
QAOA answers verified optimal in {{tiers.qaoa_pct|1}} % of local solves (rest: QIEA / annealing / exact fallback).
Full tables: [docs/results.md](docs/results.md).

## Architecture
```mermaid
flowchart LR
  subgraph Data
    N[NASA POWER] --> PV[PV per zone]
    O[OpenStreetMap RVCE] --> Z[9 zones + tie-lines + roof area]
    A[Ausgrid shapes + timetables] --> L[zone loads]
  end
  subgraph Zone_i["each zone (own process)"]
    Q[local QUBO ≤16 qubits] --> S{QAOA → QIEA → SA → exact}
    E[exhaustive search] -->|verify| S
    S --> SAFE[safety layer: SoC, DG min-on, tanks, critical loads]
  end
  Z --> Zone_i
  PV --> Zone_i
  L --> Zone_i
  Zone_i <-->|tie-line proposals + 1 price, websockets| Zone_j[neighbour zones]
  SAFE --> R[replay JSON] --> UI[3D demo: story · judge · sandbox]
  API[FastAPI live] --- UI
```

## How to run
```bash
conda activate qgrid && make install
make test                      # pytest
make demo                      # frontend (+ live backend on :8000); frontend alone works offline
make data && make qaoa && make bench && make replay   # full pipeline (~20 min on a MacBook)
make verify                    # recompute headline numbers, PASS/FAIL vs results/manifest.json
bash scripts/refresh_all.sh    # after adding the PENDING files
python scripts/new_campus.py --name "<campus>" --lat <lat> --lon <lon>   # another campus
```

## Status
| Step | What | State |
|---|---|---|
| 0–5 (v1) | generic 5-building pipeline, kept in docs/results_v1.md | ✅ |
| 1 | pricing scenarios A (headline) / B (sensitivity), SOURCES with page numbers when REAL | ✅ code · data PENDING |
| 2 | RVCE campus from OSM, timetable/Ausgrid loads, DG, tanks, outage islanding, 6 scenarios | ✅ (calendar/loads PENDING) |
| 3 | QAOA only on scenarios, warm start, QUBO cache, ADMM convergence stats & fallbacks | ✅ |
| 4 | QAOA → QIEA → SA → exact tiers, C-QIEA, baselines B0–B5, benchmark both price scenarios | ✅ |
| 5 | plain-English operator rules (guarded) + deterministic explanations | ✅ |
| 6 | replay export | ✅ |
| 7 | 3D demo: light step-by-step explainer (7 steps, one continuous 3D thread: campus → decisions → qubits → QAOA circuit → measurement → decoded plan → ADMM → storage → results), Verify and Try it tabs, honesty strip | ✅ |
| 8 | new_campus.py, manifest + make verify, CI | ✅ |
| 9 | report, why-quantum, viva Q&A, pitch, data request | ✅ |
| v2 | optimiser v2 (branch `optimiser-v2`): 24 h rolling MPC, hybrid Benders (QAOA/QIEA/SA/exact master on hourly commitments, LP subproblem by consensus ADMM), solar forecast, demand charge (PENDING), optional IBM/D-Wave runs; results in [docs/results_v2.md](docs/results_v2.md) | ✅ code · tariff PENDING · hardware needs tokens |

## Honest limits
PENDING prices/CO2/calendar/meter data; loads are area-based estimates; perfect forecasts; QAOA simulated (ideal, noiseless);
ADMM with binaries has no convergence guarantee (full agreement in {{admm.conv_pct|1}} % of slots, rest settled safely);
lossless tie-lines without AC power flow. Docs: [report](docs/report.md) · [why quantum](docs/why_quantum.md) ·
[viva Q&A](docs/viva_qa.md) · [pitch](docs/pitch.md) · [QUBO derivation](docs/qubo.md).

## Credits
The QIEA solver tier and the LLM rule-guard idea were inspired by RVCE team ReZero's *Q-Route* project. Map data
© OpenStreetMap contributors (ODbL). Ausgrid Solar Home Electricity Data (CC BY 3.0 AU). NASA POWER (NASA LaRC).
