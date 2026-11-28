# Q-Grid: Decentralised, QAOA-Verified Scheduling for a Campus Solar–Battery–Diesel Microgrid (RVCE case study)

> **Note.** Sections that quote the v1 headline day and the 30-day v1 set come from the earlier pipeline. The current
> result is the five-campus scorecard ([benchmark_v3.md](benchmark_v3.md)) and the locked headline
> ([headline.md](headline.md)): {{headline.sentence}}

*Technical report, EUREKA Track 3. QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed.*

## Abstract
We schedule batteries, diesel generators, borewell pumps, flexible loads and inter-building tie-lines for nine zones of the RVCE
campus (layout from OpenStreetMap) every 15 minutes. Each zone solves a ≤{{search.max_qubits}}-qubit QUBO with QAOA (simulated),
verified against exhaustive search with a QAOA → QIEA → annealing → exact fallback; zones agree on tie-line flows with consensus
ADMM without a coordinator. On the headline stress test — a BESCOM outage during the fest evening — critical-load downtime falls
from {{headline.before.critical_downtime_h|2}} h (status quo) to {{headline.after.critical_downtime_h|2}} h (centralised optimum:
{{headline.optimum_B4.critical_downtime_h|2}} h). On a 30-day evaluation set the method is {{OURS.eval30_mean.A.gap_to_B4_pct|2}} %
above the centralised MILP optimum (status quo {{B0.eval30_mean.A.gap_to_B4_pct|2}} %). Prices, the CO2 factor, the academic
calendar and campus loads are PENDING official/RVCE data; all figures are reproducible from `results/*.csv`.

## 1 Problem
Rooftop PV surplus is exported cheaply at noon and power is imported at peak price in the evening; BESCOM outages force diesel
operation and risk critical loads (server room, health centre, running labs). Decisions are binary (battery mode, DG on/off,
pump on/off, job start, tie-line level) and coupled across buildings.

## 2 Related work
QAOA [Farhi et al. 2014]; Ising/QUBO formulations of combinatorial problems [Lucas 2014]; ADMM for distributed optimisation
[Boyd et al. 2011]; quantum-inspired evolutionary algorithms [Han & Kim 2002]; residential load/PV data [Ratnam et al. 2017].
Full references: `docs/results.md`.

## 3 System model
Zones from OSM footprints (regex rules in `config.yaml`); PV = roof area × usable fraction × 0.18 kWp/m² (ASSUMPTION) driven by
NASA POWER irradiance; loads = floor area × EPI (ASSUMPTION) with timetable shapes (hostels: Ausgrid shape); batteries with
SoC 20–95 %; DGs with min load 30 %, min on-time 1 h and a linear fuel curve (ASSUMPTION); a pump–tank pair with level bounds;
flexible jobs with start windows; tie-lines from a minimum spanning tree on zone centroids plus two mesh links (rating ±120 kW,
ASSUMPTION). Grid outages island the campus: deficits are shed non-critical first; critical shortfall is reported as downtime.

## 4 Local QUBO
Per zone and slot, horizon H = 3: 2H battery bits, 1 DG bit, 1 pump bit, job-start bits, 2 bits per tie-line, capped at 16.
Objective groups: fitted convex quadratic surrogate of the exact tariff/VOLL cost over all reachable residuals, battery
cost-to-go from a local DP, water value, diesel fuel, job timing at battery-aware marginal prices, ADMM consensus, operator
rules. Hard constraints (exclusivity, SoC and tank bounds, critical-load service when islanded) are checked exactly; penalty
weights are auto-tuned until the exhaustive ground state is feasible. Derivation: `docs/qubo.md`.

## 5 Decentralised coordination
Consensus ADMM per tie-line with price-initialised duals (neighbours exchange one marginal price), sticky agreement, ρ growth,
bilateral resolution of disagreements, and a critical-load guard. Networked mode runs one OS process per zone over websockets
with distributed termination and 3 s silence detection (island mode).

## 6 Solvers
QAOA p = 2 (parameters trained on days disjoint from the test set, warm-started per zone), QIEA (classical, quantum-inspired),
simulated annealing, exhaustive search. Baselines: B0 status quo, B1 rule-based, B2 GA/PSO, B3 per-zone MILP, B4 central MILP,
B5 ADMM + exact; plus C-QIEA (centralised QUBO, QIEA) and OURS-QIEA.

## 7 Experimental setup
Six scenarios (teaching, exam week, vacation, fest, monsoon, outage during fest) and a 30-day evaluation set; two price
scenarios (A: BESCOM HT ToD + KERC export; B: IEX DAM both ways), both STAND-INS until the official files arrive. Identical
data, constraints, horizon and settlement for all methods. QAOA in the loop on the six scenarios; classical local tiers on the
30-day set.

## 8 Results
See `docs/results.md` (all tables generated from CSV). Key numbers (scenario A): 30-day mean cost B0 {{B0.eval30_mean.A.cost_rs}},
B3 {{B3.eval30_mean.A.cost_rs}}, OURS {{OURS.eval30_mean.A.cost_rs}}, B4 {{B4.eval30_mean.A.cost_rs}} Rs/day; per semester (120 days,
ASSUMPTION) OURS {{OURS.eval30_mean.A.cost_rs_semester}} Rs. Local solves answered by verified QAOA: {{tiers.qaoa_pct|1}} %.
ADMM full-agreement rate {{admm.conv_pct|1}} %. Recovery after a zone crash (networked): {{robust.recovery_s|2}} s.

## 9 Limitations and future work
PENDING data (prices, CO2, calendar, RVCE meters); perfect forecasts; ideal simulated QAOA; no AC power flow; ADMM with binaries
lacks convergence guarantees. Future: RVCE meter data, forecast-error study, hardware runs (with approval), continuous tie-line
levels via more bits, learned warm starts.
