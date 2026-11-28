# Q-Grid — decentralised scheduling for a campus solar + battery microgrid

EUREKA Track 3 · Smart Decentralised Energy Systems · RVCE, Bengaluru

![Q-Grid explainer: the campus, the decisions, the neighbour agreement, the scorecard](docs/media/hero.gif)

**In a BESCOM outage Q-Grid cuts critical-load downtime from 2.6 h to 20 min per outage (45 L more diesel, 122 kg CO₂, to keep those loads up); on normal days the bill is 0.1% lower and the demand charge falls by Rs 5,278 a month at 1,300 kVA contract demand; with no central controller it averages 1.1% from the best possible plan against 9.2% for Per-building MPC, a lead made on the outage days (normal days: 0.6% against 0.3%).**

When the campus network fails for 3 hours, central control loses 2.7 points of gap and Q-Grid 0.0, because each building keeps optimising on its own. (Mean of 30 modelled RVCE days, 3 with a synthetic BESCOM outage;
locked headline and its table: [docs/headline.md](docs/headline.md).)

> QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed.
> Tariff: BESCOM HT-2(c)(ii) from the KERC Tariff Order 2022 (days before 1 April 2023) and the KERC Tariff Order 2023
> (from 1 April 2023), both verified against the official PDFs. CO₂: CEA baseline 0.727 t/MWh (verified). RVCE loads,
> battery, EV chargers and cables are stand-ins or proposals and are labelled; see [docs/data_verification.md](docs/data_verification.md).
> Every number in this README is rendered from `results/` by `scripts/write_results_md.py`.

## Open the demo

- **Live link:** `⟨paste the Vercel URL here after deploying⟩` — static build, offline replay, no backend needed.
- **Locally:** `cd frontend && npm install && npm run dev` → <http://localhost:5173>. Press **P** for presenter mode,
  **D** for dark mode, ← → to move through the seven steps.
- **With the live backend** (the three live moments compute on the spot): `make backend` in a second terminal; the top bar
  turns to **Live backend**.
- **Deploy your own:** import the repo in Vercel with root directory `frontend` (`frontend/vercel.json` sets
  `npm run build:static`, output `dist`). Or `cd frontend && npm run build:static` and serve `dist/` from any static host
  (Windows PowerShell: `$env:VITE_QGRID_OFFLINE=1; npm run build`). Check it with `npx vite preview` → <http://localhost:4173>.
  The replay files the build ships are `frontend/public/replay/*.json`, copied there by the result scripts.
- **Backup video (90 s):** [docs/media/demo_backup.webm](docs/media/demo_backup.webm) · **one-page summary:** the
  "Download summary (PDF)" button in the demo.

## The problem

Today each building acts on its own: when BESCOM supply fails, critical loads go dark for 2.6 h per outage while the diesel sets burn 373 L; the electricity bill averages Rs 177,694 a day.

## Results (scorecard: 30 RVCE days, same data, forecasts and constraints for every method)

| Method | Gap to best plan % | Certified gap % | Bill saving vs today %* | Critical downtime h/day | …counting >1 % shortfalls | Works without a central controller |
|---|---:|---:|---:|---:|---:|:---:|
| Status quo (no coordination) | 16.75 | 16.75 | 0.0 | 0.26 | 0.26 | ✓ |
| Rule-based battery controller | 21.16 | 21.17 | -0.1 | 0.26 | 0.26 | ✓ |
| Particle swarm optimisation | 12.32 | 12.32 | -0.2 | 0.26 | 0.26 | ✓ |
| Per-building MPC (MILP) | 9.17 | 9.17 | 1.3 | 0.26 | 0.26 | ✓ |
| Central MPC with forecasts | 1.37 | 1.38 | -0.9 | 0.00 | 0.00 | ✗ |
| Central MPC, 3 h network failure | 4.06 | 4.06 | -1.0 | 0.12 | 0.02 | ✗ |
| **Q-Grid** | **1.06** | **1.07** | **-0.4** | **0.03** | **0.01** | ✓ |
| Q-Grid, 3 h network failure | 1.08 | 1.08 | -0.5 | 0.13 | 0.02 | ✓ |
| _Best possible plan (central MILP, perfect information; reference)_ | _0.00_ | _0.00_ | _-0.2_ | _0.00_ | _0.00_ | — |

\* BESCOM HT-2(c)(ii) (KERC Tariff Orders 2022 and 2023), energy charge plus the day's share of the monthly demand charge at
1,300 kVA contract demand (assumed). Across 5 campuses (RVCE + four public meter datasets), Q-Grid is the closest
method without a central controller on 3. Full tables with ± and 95 % intervals, Wilcoxon verdicts:
[docs/benchmark_v3.md](docs/benchmark_v3.md) · consistency checks: [docs/consistency.md](docs/consistency.md).

**Is it worth it?** Node hardware ≈ Rs 7.9 lakh for 9 buildings (assumed costs); the bill rises by ≈ Rs 3.2 lakh/year; extra battery wear ≈ Rs 3.3 lakh/year (every optimiser prices wear in its objective). On these assumptions the nodes do not pay back on the electricity bill alone (10-year NPV Rs -56.4 lakh) (Monte Carlo P5–P95: Rs -90.5 to -18.7 lakh; P(NPV > 0) = 0 %). Assumptions and sources: [docs/impact.md](docs/impact.md).

**What should RVCE build next?** The investment planner (Plan tab, `scripts/plan_investment.py`) sizes extra rooftop
solar per roof group, a battery and the contract demand with one linear programme over the 30 RVCE days at the real
tariff. Today: 500 kWp, contract 1,300 kVA, energy + demand + diesel ≈ Rs
617.6 lakh/year. The cost-minimising plan adds 1,416 kWp and a 257 kWh
battery at 1,000 kVA contract: investment ≈ Rs 701.3 lakh, saving ≈ Rs
175.0 lakh/year, payback ≈ 4.0 years. PV and battery costs are ASSUMPTIONS (quotes
pending) and operation is planned with perfect information, so this is an upper bound on savings.

## Architecture

```mermaid
flowchart LR
  subgraph data[Data]
    N[NASA POWER solar] --> F
    O[OpenStreetMap RVCE: 9 zones, 10 cables] --> F
    M[meter load shapes: BDG2, CU-BEMS] --> F[gradient-boosted forecasts]
  end
  subgraph b["each building — its own node, every 15 min, 24 h ahead"]
    BB[exact branch and bound: on/off plan] --> LP[continuous dispatch LP]
    LP --> SAFE[safety layer: battery limits, diesel min-on, tank, critical loads]
    QA[QAOA block, simulator] -. tested, verified vs exact, not in the loop .-> BB
  end
  F --> b
  b <-->|cable-flow proposals + prices, neighbours only: consensus ADMM| nb[neighbour buildings]
  SAFE --> R[replay JSON] --> UI[explainer: 7 steps, live moments, Verify]
  API[FastAPI: /live/remove · /live/qaoa · /live/rule] --- UI
```

RVCE is modelled as 9 zones (buildings or building groups) joined by 10 cables. No central computer at runtime: each building solves its own commitment exactly and agrees cable flows with its neighbours
(convex LP, consensus ADMM). If the network fails, buildings keep optimising alone. Faculty rules in plain English are parsed,
validated and priced before they can touch a schedule.

## How to run

```bash
conda activate qgrid && make install
make test                                  # pytest (backend) ; cd frontend && npm run test:contrast  (WCAG AA, both themes)
make demo                                  # frontend + live backend on :8000 (the frontend alone works offline)
python scripts/run_bench_v3.py --workers=8 # scorecard benchmark (5 datasets x 30 days x 10 methods + design rows; ~3 h on a 24-thread laptop)
python scripts/write_bench_v3.py && python scripts/write_consistency.py && python scripts/write_impact.py
make replay && python scripts/make_live.py # replay JSON + precomputed live moments for the offline demo
python scripts/write_results_md.py         # re-render README and docs from results/
make verify                                # recompute headline numbers, PASS/FAIL vs results/manifest.json
```

## Data sources and pending items

| Source | Use | Status |
|---|---|---|
| NASA POWER (NASA LaRC) | solar irradiance, Bengaluru | real |
| OpenStreetMap (© contributors, ODbL) | campus layout, roof areas | real |
| Building Data Genome 2 (CC BY-SA 4.0) | load shapes for 7 of the 9 RVCE zones; three other campuses in the benchmark | real |
| CU-BEMS (CC BY 4.0) | fifth campus in the benchmark (Bangkok office building) | real |
| Ausgrid Solar Home Electricity Data (CC BY 3.0 AU) | earlier hostel load shape (superseded by BDG2) | real |
| KERC Tariff Orders 2023 and 2022 (BESCOM), HT-2(c)(ii) | energy charge, ToD, demand charge, billing demand | verified (TO-2023 p.199–206, 365–373; TO-2022 p.404–412) — REAL |
| KERC solar tariff order, 01.06.2023 | rooftop PV export rate Rs 3.74/kWh | verified (p.30) |
| IEX day-ahead prices | sensitivity scenario | **PENDING** — PENDING |
| CEA CO₂ Baseline Database v20/v21 | grid emission factor 0.727 t/MWh | verified |
| RVCE team brief | 500.48 kWp on 21 roofs, 67,721 m² built-up, 38,659 m² hostels, 2 × 490 kVA diesel | team brief (estate data pending) |
| RVCE meter data, calendar | loads, day types | **PENDING** — area-based estimates |

Licences, URLs and fetch dates: `data/SOURCES.md` · what we asked RVCE for: `docs/data_request.md`.

## Pitch materials

[locked headline](docs/headline.md) · [judge brief: the project in plain words](docs/judge_brief.md) · [3-minute script](docs/pitch_3min.md) · [1-minute script](docs/pitch_1min.md) ·
[Q&A prep: 20 hardest questions](docs/qa_prep.md) · [deck outline](docs/deck_outline.md) · [demo runbook](docs/demo_runbook.md) ·
[impact](docs/impact.md) · [why quantum](docs/why_quantum.md) · [real-data review](docs/review_real_data.md) ·
[RVCE data request email](docs/rvce_data_request_email.md)

## Status

- **Real-data pass (branch `real-data`):** campus rescaled to the team brief (500.48 kWp on 21 roofs, 2 × 490 kVA diesel);
  BESCOM HT-2(c)(ii) tariff verified against the KERC Tariff Orders 2022 and 2023 and the KERC solar order; CEA CO₂ factor
  verified; five-campus scorecard, replays and docs regenerated from it.
- **Planner fix (28 Nov):** Q-Grid's campus peak budgets no longer starve a building that planned no import in a slot
  (the cause of batteries charging at the 18:00 peak); every Q-Grid row re-run with the same seeds
  ([docs/review_real_data.md](docs/review_real_data.md)).
- **Waiting on RVCE:** one BESCOM HT bill (contract demand, recorded maximum demand), which buildings the two diesel sets
  back, diesel logs, meter data. See [docs/rvce_data_request_email.md](docs/rvce_data_request_email.md).
- **Proposed, not on campus today:** batteries, EV chargers, inter-building cables.

## Team and faculty guide

- **Team lead:** Yashas (GitHub: Yojan-ui)
- **Team members:** ⟨add names⟩
- **Faculty guide:** ⟨add name, department⟩
- RV College of Engineering, Bengaluru

## Honest limits

- No quantum advantage: QAOA is simulated (ideal, noiseless) and is not in the control loop; it was tested and verified.
- RVCE loads and calendar are stand-ins until meter data arrives; solar, diesel and floor areas are from the team brief.
- Battery, EV chargers and inter-building cables do not exist on campus today: they are PROPOSED, and labelled so.
  Q-Grid's outage gain comes from sharing the two diesel sets' power with buildings that have none, so on campus it
  depends on which buildings those sets can actually feed (asked of the estate office).
- No real bill saving: on normal days the bill is 0.1 % lower than today's practice, over
  all days 0.4 % higher (diesel burned in outages to keep critical loads up), and the nodes do not
  pay back on the bill. A planner defect found in the full run (batteries charged at the 18:00 peak, 24 Feb 2023) was
  fixed and every Q-Grid row re-run (docs/review_real_data.md).
- Tariff: RVCE's billing category (HT-2(c)(ii)) and its contract demand (1,300 kVA assumed) need one RVCE BESCOM bill to confirm.
- Outages and network failures in the benchmark are synthetic (seeded). Cables are modelled as lossless, without AC power flow.
- Battery wear is priced with an assumed battery cost and cycle life; real warranty data will change the rate.
- Value of lost load (Rs 40 / 1,000 per kWh) is an assumption; every gap is also reported without it.
- Feeder-scale operation is a plan, not a result.

## Credits

The QIEA solver tier and the LLM rule-guard idea were inspired by RVCE team ReZero's *Q-Route* project. Map data
© OpenStreetMap contributors (ODbL). Ausgrid Solar Home Electricity Data (CC BY 3.0 AU). NASA POWER (NASA LaRC).
BDG2 and CU-BEMS under their published licences (see `data/SOURCES.md`).
