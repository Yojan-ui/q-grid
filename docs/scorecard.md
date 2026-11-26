# Q-Grid scorecard

**Q-Grid lands 2.3% from the best possible plan; the closest alternative without a central controller, Particle swarm optimisation, lands 23.5% (paired Wilcoxon p < 0.001).** Among methods that work without a central controller, Q-Grid is closest to the best possible plan on 3 of 5 campuses; elsewhere (BDG2 university site 'Bull' (Texas); BDG2 university site 'Cockatoo' (New York)) another method is closer.

_All figures: mean over evaluation days, from `results/bench_v3/summary.csv`. Stand-in tariff (PENDING), synthetic outages._

| Method (RVCE) | Gap to best plan % | Certified gap % | Bill Rs/day | Saving vs today % | Critical downtime h | Peak kVA | Works without a central controller |
|---|---:|---:|---:|---:|---:|---:|:---:|
| Status quo (no coordination) | 34.27 | 34.17 | 177,985 | 0.0 | 0.26 | 1,623 | ✓ |
| Rule-based battery controller | 35.61 | 35.52 | 173,613 | 2.6 | 0.26 | 1,557 | ✓ |
| Genetic algorithm | 23.50 | 23.40 | 176,902 | 0.6 | 0.26 | 1,986 | ✓ |
| Particle swarm optimisation | 23.48 | 23.38 | 175,963 | 1.2 | 0.26 | 1,906 | ✓ |
| Per-building MPC (MILP) | 23.74 | 23.65 | 175,172 | 1.7 | 0.26 | 1,813 | ✓ |
| Central MPC with forecasts | 2.72 | 2.62 | 174,698 | 2.1 | 0.10 | 2,032 | ✗ |
| Central MPC when communication fails | 5.43 | 5.33 | 175,734 | 1.4 | 0.12 | 2,030 | ✗ |
| **Q-Grid** | 2.28 | 2.18 | 173,510 | 2.7 | 0.15 | 1,997 | ✓ |
| Q-Grid when communication fails | 4.22 | 4.13 | 175,163 | 1.7 | 0.14 | 2,030 | ✓ |
| Best possible plan (central MILP, perfect information) | 0.01 | -0.08 | 171,919 | 3.6 | 0.00 | 2,143 | — |

| Dataset | Q-Grid gap % | best alternative without a central controller | its gap % |
|---|---:|---|---:|
| RVCE, Bengaluru (case study) | 2.28 | Particle swarm optimisation | 23.48 |
| BDG2 university site 'Fox' (Arizona) | 1.49 | Per-building MPC (MILP) | 1.75 |
| BDG2 university site 'Bull' (Texas) | 2.75 | Per-building MPC (MILP) | 2.72 |
| BDG2 university site 'Cockatoo' (New York) | 4.66 | Per-building MPC (MILP) | 4.34 |
| CU-BEMS office building, Bangkok (7 floors) | 7.92 | Per-building MPC (MILP) | 11.50 |
