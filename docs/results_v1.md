# Results v1 — generic 5-building campus (kept for comparison)

_Frozen copy of the Phase-5 benchmark (commit a5ae816) before the RVCE campus model. Generated from results/benchmark.csv of that commit; stand-in prices (PENDING), not headline results._

## Scenario A (30-day mean, STAND-IN prices)

| Method | Rs/day | gap to B4 | CO2 kg/day |
|---|---:|---:|---:|
| B0 | 30,190 | 28.88 % | 3,106 |
| B1 | 28,472 | 20.21 % | 2,650 |
| B2-GA | 27,193 | 14.09 % | 3,067 |
| B2-PSO | 27,212 | 14.19 % | 3,062 |
| B3 | 26,881 | 12.59 % | 3,074 |
| B4 | 24,206 | 0.00 % | 2,719 |
| B5 | 25,706 | 7.37 % | 2,895 |
| OURS | 25,749 | 7.61 % | 2,900 |

## Scenario B (30-day mean, STAND-IN prices)

| Method | Rs/day | gap to B4 | CO2 kg/day |
|---|---:|---:|---:|
| B0 | 24,538 | 29.94 % | 3,106 |
| B1 | 23,368 | 22.59 % | 2,650 |
| B2-GA | 19,516 | -0.00 % | 3,060 |
| B2-PSO | 19,547 | 0.19 % | 3,053 |
| B3 | 19,516 | -0.00 % | 3,234 |
| B4 | 19,516 | 0.00 % | 3,182 |
| B5 | 19,516 | -0.00 % | 3,145 |
| OURS | 19,516 | -0.00 % | 3,145 |

Full v1 report (as generated then):

## Interpretation (honest)

**Scenario A (stand-in prices).** OURS averages Rs 25,749/day vs B4 optimum Rs 24,206 (gap 7.61 %), B5 Rs 25,706 (gap 7.37 %), status quo Rs 30,190 (14.7 % saving vs B0). On the eval-set mean, OURS beats B0, B1, B2-GA, B2-PSO, B3. The best non-sharing classical method is B3 (Rs 26,881). Per day vs B3: OURS cheaper on 29, tied on 0, dearer on 1 of 30 evaluation days. OURS vs B5 (same ADMM, exact local solver): difference +0.17 %. Because QAOA's answer is only used when verified optimal, the two differ only through ties between equally optimal bitstrings, not through solution quality.

**Scenario B (stand-in prices).** OURS averages Rs 19,516/day vs B4 optimum Rs 19,516 (gap -0.00 %), B5 Rs 19,516 (gap -0.00 %), status quo Rs 24,538 (20.5 % saving vs B0). On the eval-set mean, OURS beats B0, B1, B2-PSO, ties (within 0.05 %) with B2-GA, B3. The best non-sharing classical method is B2-GA (Rs 19,516). Per day vs B3: OURS cheaper on 0, tied on 30, dearer on 0 of 30 evaluation days. OURS vs B5 (same ADMM, exact local solver): difference +0.00 %. Because QAOA's answer is only used when verified optimal, the two differ only through ties between equally optimal bitstrings, not through solution quality.

Where the decentralised method loses to B4: discrete tie-line levels (B4 is continuous), 1-hour local horizons with a local cost-to-go instead of a joint day-ahead plan, and ADMM lines that fail to agree within 15 iterations are set to 0. Its advantages are structural, not cost: no central solver or single point of failure, buildings exchange only tie-line proposals and one marginal price per slot (no load/PV/battery data), and a crashed building is islanded automatically (below).

Scenario B note: with import price = export price, sharing between buildings has no economic value (a kWh is worth the same sent to the grid or to a neighbour), so B3 and B4 coincide or nearly so. With the stand-in shape the absolute numbers mean little until real IEX prices are loaded.

## ADMM convergence (honest)

- Mean ADMM iterations per slot: 8.66 (cap 15); mean tie-line disagreements forced to 0 per day: 191.4 (of 6 lines x 96 slots = 576 line-slots). Discrete ADMM often reaches the iteration cap; unresolved lines fall back to 0 flow, which is always feasible but forgoes sharing. This is a main contributor to the gap to B4. The `slots_to_reconverge` column in the robustness table counts slots until *every* surviving line agrees again, so with frequent cap hits it can be large even when the schedule stays feasible.

## QAOA quality inside the benchmark (OURS)

- Local solves: 278,919; accepted from QAOA (verified optimal) 71.6 %, simulated annealing 21.5 %, exact 6.9 %.
- Mean P(optimum) under the QAOA distribution: 0.0356; best-of-256-shots found the optimum in 77.4 % of solves; a feasible sample was returned in 100.0 % of solves.

- Ablation (accept any feasible QAOA sample, test days): cost differs from B5 by +0.31 % on average (range -0.00 … +1.55 %). This is why the verified fallback exists.

## QAOA scaling study (`results/qaoa_scaling.csv`, `results/plots/qaoa_scaling.png`)

| qubits | p | P(optimum) | uniform 2^-n | best-of-256 approx. ratio | found optimum |
|---:|---:|---:|---:|---:|---:|
| 2 | 1 | 0.3926 | 0.25000 | 1.0000 | 100 % |
| 2 | 2 | 0.4941 | 0.25000 | 1.0000 | 100 % |
| 2 | 3 | 0.5916 | 0.25000 | 1.0000 | 100 % |
| 4 | 1 | 0.1992 | 0.06250 | 1.0000 | 100 % |
| 4 | 2 | 0.4815 | 0.06250 | 1.0000 | 100 % |
| 4 | 3 | 0.5497 | 0.06250 | 1.0000 | 100 % |
| 6 | 1 | 0.0486 | 0.01562 | 1.0000 | 100 % |
| 6 | 2 | 0.0628 | 0.01562 | 1.0000 | 100 % |
| 6 | 3 | 0.0747 | 0.01562 | 1.0000 | 100 % |
| 8 | 1 | 0.0301 | 0.00391 | 1.0000 | 100 % |
| 8 | 2 | 0.0591 | 0.00391 | 1.0000 | 100 % |
| 8 | 3 | 0.0770 | 0.00391 | 1.0000 | 100 % |
| 10 | 1 | 0.0090 | 0.00098 | 0.9984 | 92 % |
| 10 | 2 | 0.0329 | 0.00098 | 0.9967 | 83 % |
| 10 | 3 | 0.0480 | 0.00098 | 0.9872 | 67 % |
| 12 | 1 | 0.0023 | 0.00024 | 0.9809 | 50 % |
| 12 | 2 | 0.0096 | 0.00024 | 0.9688 | 50 % |
| 12 | 3 | 0.0150 | 0.00024 | 0.9740 | 50 % |
| 13 | 1 | 0.0019 | 0.00012 | 0.9907 | 83 % |
| 13 | 2 | 0.0082 | 0.00012 | 0.9892 | 67 % |
| 13 | 3 | 0.0124 | 0.00012 | 0.9949 | 67 % |
| 15 | 1 | 0.0003 | 0.00003 | 0.9729 | 17 % |
| 15 | 2 | 0.0010 | 0.00003 | 0.9562 | 0 % |
| 15 | 3 | 0.0015 | 0.00003 | 0.9520 | 17 % |

P(optimum) decays roughly exponentially with qubit count and improves with depth p; with transferred parameters it stays above the uniform baseline. At these sizes exhaustive search takes milliseconds, so there is no runtime advantage — consistent with the no-quantum-advantage label.

## Robustness: kill a building (`results/robustness.csv`)

| Mode | Method | Scenario | Day | Killed @ slot | Feasible | Flows consistent | Recovery time s | Slots to re-converge |
|---|---|---|---|---|---|---|---:|---:|
| networked | OURS | A | 2023-04-13 | lab_block @ 48 | True | True | 3.02 | – |
| networked | B5 | A | 2023-04-13 | lab_block @ 48 | True | True | 3.05 | – |
| networked | OURS | B | 2023-04-13 | lab_block @ 48 | True | True | 3.02 | – |
| networked | B5 | B | 2023-04-13 | lab_block @ 48 | True | True | 3.01 | – |
| in-process | OURS | B | 2023-04-13 | lab_block @ 48 | True | nan | – | 0 |
| in-process | OURS | B | 2023-01-10 | lab_block @ 48 | True | nan | – | 0 |
| in-process | OURS | B | 2023-07-25 | lab_block @ 48 | True | nan | – | 0 |
| in-process | OURS | A | 2023-01-10 | lab_block @ 48 | True | nan | – | 40 |
| in-process | OURS | A | 2023-04-13 | lab_block @ 48 | True | nan | – | 0 |
| in-process | OURS | A | 2023-07-25 | lab_block @ 48 | True | nan | – | 43 |

Networked mode runs one OS process per building over websockets with no coordinator; recovery time includes the 3 s silence detection. Every kill run produced a feasible schedule.

## Related work (verified references only)

- E. Farhi, J. Goldstone, S. Gutmann, *A Quantum Approximate Optimization Algorithm*, arXiv:1411.4028 (2014).
- A. Lucas, *Ising formulations of many NP problems*, Frontiers in Physics 2:5 (2014), doi:10.3389/fphy.2014.00005.
- S. Boyd, N. Parikh, E. Chu, B. Peleato, J. Eckstein, *Distributed Optimization and Statistical Learning via the Alternating Direction Method of Multipliers*, Foundations and Trends in Machine Learning 3(1):1–122 (2011), doi:10.1561/2200000016.
- E. L. Ratnam, S. R. Weller, C. M. Kellett, A. T. Murray, *Residential load and rooftop PV generation: an Australian distribution network dataset*, Int. J. Sustainable Energy (2017), doi:10.1080/14786451.2015.1100196.

## Limitations

- Prices (both scenarios) and the CO2 factor are PENDING official sources (see top).
- Campus loads are residential Ausgrid shapes rescaled to assumed building peaks.
- Perfect day-ahead forecasts for every method; no forecast error study yet.
- QAOA is simulated classically (ideal, noiseless); no hardware runs.
- Tie-lines are lossless with a fixed rating; no AC power-flow / voltage constraints.
