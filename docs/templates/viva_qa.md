# Viva / judge Q&A (25 questions) — answers grounded in our results

1. **Why QAOA if brute force is instant at 16 qubits?** We need a formulation that is hardware-sized and verifiable. At this size
   we can check every QAOA answer exactly; QAOA is verified optimal in {{tiers.qaoa_pct|1}} % of local solves and the rest fall back.
   We claim no advantage.
2. **Is any result run on a quantum computer?** No. Qiskit circuits simulated with Aer (and an equivalent numpy statevector,
   unit-tested to match). IBM hardware is wired but disabled (credentials/cost).
3. **Why ADMM and not one central MILP?** B4 *is* the central MILP and it is better on cost ({{OURS.eval30_mean.A.gap_to_B4_pct|2}} %
   gap). ADMM gives no single point of failure, privacy (only tie-line proposals and one price are exchanged), and keeps each
   subproblem ≤ {{search.max_qubits}} qubits.
4. **Does ADMM converge with binary variables?** Not guaranteed. Full agreement in {{admm.conv_pct|1}} % of slots (mean
   {{admm.iters|1}} iterations, {{admm.osc}} oscillations detected). Disagreements go to bilateral resolution or 0 flow — always feasible.
5. **What did price-initialised duals fix?** With zero duals both ends "want to receive", z averages to 0 and discrete ADMM locks at
   0 (a fixed point). Exchanging one marginal price starts the negotiation at a fair price.
6. **How are penalties tuned?** Exclusivity weight = coefficient bound of the objective; soft SoC/tank/critical weight doubled from 5 %
   of it until the exhaustive ground state is feasible.
7. **Your QUBO cost is piecewise-linear — how is it quadratic?** A convex quadratic surrogate is least-squares fitted over every
   reachable residual; exact when import = export price. In islanded slots critical-load service becomes a hard constraint.
8. **What is QIEA and is it quantum?** A quantum-inspired evolutionary algorithm (Han & Kim 2002) on a classical CPU. Not quantum
   computing; labelled so everywhere.
9. **Is the data real?** Real: NASA POWER irradiance, Ausgrid household shapes (hostels), OpenStreetMap layout. PENDING: tariffs,
   IEX prices, CEA factor, RVCE calendar and meter data — stand-ins are labelled and never headline.
10. **Why Australian load data?** No open, licence-clear Indian campus meter data; only the hostel shape uses it. `docs/data_request.md`
    lists what we need from the Estate Office.
11. **Is the comparison fair?** Same data, days, constraints, horizon and settlement for every method; B4 even gets continuous
    tie-line flows (a relaxation).
12. **What happens in an outage?** Islanded campus; DG and battery power routed over tie-lines; critical-load guard. Headline downtime
    {{headline.before.critical_downtime_h|2}} h → {{headline.after.critical_downtime_h|2}} h (optimum {{headline.optimum_B4.critical_downtime_h|2}} h).
13. **What if a building's controller dies?** Neighbours detect 3 s of silence, island its lines, the rest re-converge. Recovery
    {{robust.recovery_s|2}} s; every kill run feasible ({{robust.all_feasible}}).
14. **How big is the full problem?** N = {{search.N}} binaries per day centrally (10^{{search.log10|1}} states).
15. **How fast is re-planning?** OURS {{OURS.outage_fest.A.replan_time_s|3}} s per 15-min slot on a laptop (simulation included).
16. **Why do savings look small on normal days?** Assumed batteries are small vs MW-scale loads; PV is mostly self-consumed. The value
    shows in outages and in coordination; we do not inflate it.
17. **Battery economics?** With an ASSUMED capex the simple payback is {{eco.A.simple_payback_years|1}} years (scenario A, stand-in prices).
18. **How are operator rules handled?** Plain English → JSON (template parser offline; Claude API optional) → pydantic + bounds guard
    → QUBO penalty or hard constraint. Invalid rules are rejected with a reason (e.g. a 3-hour EV job after 22:00 cannot fit in a day).
    The LLM never produces schedules.
19. **How are decisions explained?** Flip each decision bit and compute the exact change of every QUBO term group; the biggest
    contributions become a sentence with real prices, kW, SoC and Rs.
20. **What does QAOA quality look like with size?** P(optimum) at {{scaling.nmax}} qubits: {{scaling.p2.nmax.p_opt|4}} (p=2) vs uniform
    {{scaling.uniform_nmax|5}}; it falls with size and rises with depth.
21. **Where were QAOA parameters trained?** On days disjoint from the test and evaluation days; warm-started per zone at runtime.
22. **Can it run on another campus?** `scripts/new_campus.py --name --lat --lon`: OSM → zones → config → pipeline; nothing
    RVCE-specific in code.
23. **How do we know the numbers are right?** `results/manifest.json` (commit, hashes, seeds, versions); `make verify` recomputes
    the headline subset and prints PASS/FAIL; CI checks consistency on every push.
24. **Deployment path?** One controller per building (Raspberry-Pi class) running the node process, BESCOM/inverter/DG interfaces via
    Modbus, the estate office dashboard = this frontend; start in advisory mode.
25. **Biggest weaknesses?** PENDING data; perfect forecasts; ideal simulated QAOA; ADMM convergence with binaries; no AC power flow.
