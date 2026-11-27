# Q-Grid scorecard

**Q-Grid lands 8.4% from the best possible plan on average; the closest alternative without a central controller, Per-building MPC (MILP), lands 9.2%; day by day, Per-building MPC (MILP) is closer on 27 of 30 days, and Q-Grid's lower mean comes from a few days with large differences (paired Wilcoxon p = 0.002).** Among methods that work without a central controller, Q-Grid is closest to the best possible plan on 1 of 5 campuses; elsewhere (BDG2 university site 'Fox' (Arizona); BDG2 university site 'Bull' (Texas); BDG2 university site 'Cockatoo' (New York); CU-BEMS office building, Bangkok (7 floors)) another method is closer.

_All figures: mean over evaluation days, from `results/bench_v3/summary.csv`. Tariff BESCOM HT-2(c)(ii), KERC Tariff Orders 2022 / 2023; synthetic outages._

| Method (RVCE) | Gap to best plan % | Certified gap % | Bill Rs/day | Saving vs today % | Critical downtime h | Peak kVA | Works without a central controller |
|---|---:|---:|---:|---:|---:|---:|:---:|
| Status quo (no coordination) | 16.75 | 16.75 | 177,694 | 0.0 | 0.26 | 1,055 | ✓ |
| Rule-based battery controller | 21.16 | 21.17 | 177,831 | -0.1 | 0.26 | 1,055 | ✓ |
| Genetic algorithm | 12.09 | 12.10 | 178,248 | -0.3 | 0.26 | 1,006 | ✓ |
| Particle swarm optimisation | 12.32 | 12.32 | 178,105 | -0.2 | 0.26 | 999 | ✓ |
| Per-building MPC (MILP) | 9.17 | 9.17 | 175,232 | 1.3 | 0.26 | 1,014 | ✓ |
| Central MPC with forecasts | 1.37 | 1.38 | 179,408 | -0.9 | 0.00 | 1,038 | ✗ |
| Central MPC when communication fails | 4.06 | 4.06 | 179,555 | -1.0 | 0.12 | 1,031 | ✗ |
| **Q-Grid** | 8.37 | 8.37 | 179,271 | -0.9 | 0.09 | 1,101 | ✓ |
| Q-Grid when communication fails | 9.08 | 9.08 | 179,273 | -0.9 | 0.21 | 1,104 | ✓ |
| Best possible plan (central MILP, perfect information) | 0.00 | 0.00 | 178,144 | -0.2 | 0.00 | 1,014 | — |

| Dataset | Q-Grid gap % | best alternative without a central controller | its gap % |
|---|---:|---|---:|
| RVCE, Bengaluru (case study) | 8.37 | Per-building MPC (MILP) | 9.17 |
| BDG2 university site 'Fox' (Arizona) | 9.90 | Per-building MPC (MILP) | 8.69 |
| BDG2 university site 'Bull' (Texas) | 9.79 | Per-building MPC (MILP) | 9.61 |
| BDG2 university site 'Cockatoo' (New York) | 11.82 | Per-building MPC (MILP) | 10.28 |
| CU-BEMS office building, Bangkok (7 floors) | 27.66 | Particle swarm optimisation | 27.48 |
