## v1 headline day: BESCOM outage during the fest evening (price scenario A, {{price_A_status}} prices)

_The project's locked headline is in [headline.md](headline.md) (five-campus scorecard). This card is the v1 pipeline's
single headline day._

| | Status quo (B0) | Q-Grid (OURS) | B4 optimum |
|---|---:|---:|---:|
| Cost Rs/day | {{headline.before.cost_rs}} | {{headline.after.cost_rs}} | {{headline.optimum_B4.cost_rs}} |
| Critical-load downtime h | {{headline.before.critical_downtime_h|2}} | {{headline.after.critical_downtime_h|2}} | {{headline.optimum_B4.critical_downtime_h|2}} |
| Critical energy unserved kWh | {{headline.before.critical_unserved_kwh|1}} | {{headline.after.critical_unserved_kwh|1}} | {{headline.optimum_B4.critical_unserved_kwh|1}} |
| DG hours | {{headline.before.dg_hours|2}} | {{headline.after.dg_hours|2}} | – |
| Re-plan time per slot | – | {{headline.after.replan_time_s|3}} s | – |

## Honest interpretation

- **Against the optimum.** On the 30-day set (scenario A) OURS is {{OURS.eval30_mean.A.gap_to_B4_pct|2}} % above B4 and B5
  {{B5.eval30_mean.A.gap_to_B4_pct|2}} %; B3 (no sharing) is {{B3.eval30_mean.A.gap_to_B4_pct|2}} % and the status quo
  {{B0.eval30_mean.A.gap_to_B4_pct|2}} %. The decentralised method approaches but does not reach the centralised optimum.
- **Why the gap.** Discrete tie-line levels (B4 is continuous), 45-minute local horizons with a local cost-to-go instead of a
  joint day-ahead plan, and ADMM with binaries: only {{admm.conv_pct|1}} % of slots reached full agreement within 15 iterations
  (mean {{admm.iters|1}} iterations; {{admm.osc}} oscillation cases detected). Unresolved lines are settled bilaterally or set to
  0 — always feasible, but sharing is lost.
- **QAOA's real contribution.** Local solves on the 6 scenarios: {{tiers.total}}; answered by QAOA and verified optimal
  {{tiers.qaoa_pct|1}} %, by QIEA {{tiers.qiea_pct|1}} %, by annealing {{tiers.anneal_pct|1}} %, by exact {{tiers.exact_pct|1}} %.
  Mean P(optimum) {{qaoa.p_opt_mean|4}}; best-of-256 found the optimum in {{qaoa.found_opt_pct|1}} % of solves. Because every
  answer is verified against brute force, OURS and B5 differ only by ties between equally optimal bitstrings.
- **Where Q-Grid helps.** Outage handling: sharing DG and battery power over tie-lines plus the critical-load safety rule
  (see headline). On ordinary days savings are small because the assumed batteries are small relative to MW-scale loads.
- **Battery payback (ASSUMED capex {{eco.A.capex_rs_ASSUMPTION}} Rs):** {{eco.A.simple_payback_years|1}} years in scenario A
  (saving {{eco.A.battery_saving_rs_per_day}} Rs/day vs. the same ADMM without batteries).
- **Search space.** A centralised full-day formulation has N = {{search.N}} binary variables (10^{{search.log10|1}} states);
  each local QUBO has at most {{search.max_qubits}} qubits.
- **Robustness.** Networked mode (one process per zone, websockets, no coordinator): recovery after a zone crash
  {{robust.recovery_s|2}} s (3 s silence detection + re-convergence); all kill runs feasible: {{robust.all_feasible}}.

## QAOA scaling (`results/qaoa_scaling.csv`, `results/plots/qaoa_scaling.png`)

At {{scaling.nmax}} qubits, P(optimum) with transferred parameters is {{scaling.p1.nmax.p_opt|4}} (p=1),
{{scaling.p2.nmax.p_opt|4}} (p=2), {{scaling.p3.nmax.p_opt|4}} (p=3) vs. uniform {{scaling.uniform_nmax|5}}. Exhaustive search at
these sizes takes milliseconds: no quantum advantage, as labelled.

## Related work (verified references only)

- E. Farhi, J. Goldstone, S. Gutmann, *A Quantum Approximate Optimization Algorithm*, arXiv:1411.4028 (2014).
- A. Lucas, *Ising formulations of many NP problems*, Frontiers in Physics 2:5 (2014), doi:10.3389/fphy.2014.00005.
- S. Boyd, N. Parikh, E. Chu, B. Peleato, J. Eckstein, *Distributed Optimization and Statistical Learning via the ADMM*,
  Foundations and Trends in Machine Learning 3(1):1–122 (2011), doi:10.1561/2200000016.
- K.-H. Han, J.-H. Kim, *Quantum-inspired evolutionary algorithm for a class of combinatorial optimization*,
  IEEE Trans. Evolutionary Computation 6(6):580–593 (2002), doi:10.1109/TEVC.2002.804320.
- E. L. Ratnam et al., *Residential load and rooftop PV generation: an Australian distribution network dataset*,
  Int. J. Sustainable Energy (2017), doi:10.1080/14786451.2015.1100196.

## Limitations

PENDING prices, CO2 factor, calendar and campus loads (see top); perfect day-ahead forecasts for every method; QAOA simulated
classically (ideal, noiseless); lossless tie-lines with a fixed rating, no AC power flow; ADMM convergence with binaries is not
guaranteed (handled by bilateral resolution and safe fallbacks, reported above).
