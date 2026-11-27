# Q-Grid scorecard

**Q-Grid lands 0.8% from the best possible plan; the closest alternative without a central controller, Per-building MPC (MILP), lands 21.7% (paired Wilcoxon p < 0.001).** Among methods that work without a central controller, Q-Grid is closest to the best possible plan on 4 of 5 campuses; elsewhere (BDG2 university site 'Cockatoo' (New York)) another method is closer.

_All figures: mean over evaluation days, from `results/bench_v3/summary.csv`. Stand-in tariff (PENDING), synthetic outages._

| Method (RVCE) | Gap to best plan % | Certified gap % | Bill Rs/day | Saving vs today % | Critical downtime h | Peak kVA | Works without a central controller |
|---|---:|---:|---:|---:|---:|---:|:---:|
| Status quo (no coordination) | 28.73 | 28.73 | 177,985 | 0.0 | 0.26 | 1,623 | ✓ |
| Rule-based battery controller | 35.75 | 35.76 | 173,613 | 2.6 | 0.26 | 1,557 | ✓ |
| Genetic algorithm | 23.41 | 23.42 | 175,630 | 1.4 | 0.26 | 1,593 | ✓ |
| Particle swarm optimisation | 23.55 | 23.55 | 175,757 | 1.3 | 0.26 | 1,620 | ✓ |
| Per-building MPC (MILP) | 21.70 | 21.70 | 176,197 | 1.1 | 0.26 | 1,597 | ✓ |
| Central MPC with forecasts | 1.86 | 1.86 | 173,797 | 2.5 | 0.09 | 1,601 | ✗ |
| Central MPC when communication fails | 5.36 | 5.36 | 174,170 | 2.3 | 0.11 | 1,632 | ✗ |
| **Q-Grid** | 0.76 | 0.76 | 172,293 | 3.3 | 0.14 | 1,609 | ✓ |
| Q-Grid when communication fails | 2.87 | 2.87 | 173,692 | 2.5 | 0.16 | 1,606 | ✓ |
| Best possible plan (central MILP, perfect information) | 0.02 | 0.02 | 169,219 | 5.1 | 0.00 | 1,595 | — |

| Dataset | Q-Grid gap % | best alternative without a central controller | its gap % |
|---|---:|---|---:|
| RVCE, Bengaluru (case study) | 0.76 | Per-building MPC (MILP) | 21.70 |
| BDG2 university site 'Fox' (Arizona) | 0.36 | Per-building MPC (MILP) | 0.59 |
| BDG2 university site 'Bull' (Texas) | 0.87 | Per-building MPC (MILP) | 0.94 |
| BDG2 university site 'Cockatoo' (New York) | 1.99 | Per-building MPC (MILP) | 1.94 |
| CU-BEMS office building, Bangkok (7 floors) | 3.13 | Per-building MPC (MILP) | 5.91 |
