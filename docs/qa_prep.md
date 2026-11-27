# Q&A prep — the 20 hardest judge questions

_Rendered from `docs/templates/qa_prep.md`; every number from `results/` (scorecard: `results/bench_v3`, impact:
`results/impact`, live moments: `results/replay/live.json`). Answer short, then offer the source: "it's clickable in Verify"._

**1. Where is the quantum advantage?**
There is none, and we say so. QAOA ran on a local simulator, every answer was checked against exact search, and in the
placement test (1,080 building problems from five days) branch and bound already finished at its first node
99.9 % of the time. The quantum starting plan was correct (100 % of blocks)
but did not save work, so Q-Grid does not use it.

**2. Then why is quantum in the project at all?**
Because the track asked us to evaluate it, and an honest negative result is a result. The QUBO formulation, the verification
harness and the hardware path stay in the repo for problems where branch and bound does struggle (larger blocks, more devices).

**3. Earlier results showed the QAOA master beating the exact master. Was the exact solver wrong?**
No — the comparison was. The QAOA proposal was used unverified while the exact master had a trust region, so the two runs took
different paths through the day. Now every heuristic proposal is checked against the exact master and the exact one is used
(tiered fallback). In the re-run the QAOA variant beat the exact variant on 0 of 30
days; QAOA's own proposal matched the exact one in 99.0 % of master solves. A test enforces it
(`test_exact_master_never_loses_to_a_heuristic_master`). Details: docs/consistency.md §1.

**4. Central MPC is right there. Why not just use it?**
With working communication it lands 1.86 % from the best plan; Q-Grid 0.76 %.
The difference is the single point of failure: when the campus network fails for 3 hours, central control loses
3.50 points of gap and Q-Grid 2.11.

**5. A 2 % gap but non-zero critical downtime — which is it?**
Both, from the same run. Strict downtime counts any 15-minute slot with *any* critical shortfall, however small: Q-Grid
0.14 h/day; counting only shortfalls above 1 % of critical load,
0.00 h/day. We show both, plus the energy unserved. docs/consistency.md §2.

**6. Where does the value of lost load come from?**
It's an assumption, stated: Rs 40/kWh non-critical, Rs 1,000/kWh critical (`config.yaml` → `outage_costs`). No official
BESCOM figure exists that we could cite. Every gap is also reported on money alone: Q-Grid 1.46 %.

**7. Are your rupee figures real?**
The energy tariff and demand charge are labelled stand-ins (PENDING the KERC/BESCOM order); the UI badges them. Comparisons
between methods are fair because every method sees the same prices; absolute rupees will move.

**8. What about battery degradation?**
It's in the objective. Every optimiser — Q-Grid, both MPCs, GA/PSO and the best possible plan — prices wear at Rs per kWh
charged or discharged (battery cost ÷ 2 × cycle life × depth of discharge, `config.yaml` → `battery_wear`), and the scorecard
scores it. An earlier run without that term cycled the batteries for tiny spreads and lost money after wear; that pilot is why
we changed it (`results/impact/wear_pilot_2.96.csv`). Q-Grid now cycles 0.05 times a day.

**9. So what's the payback?**
On assumed costs (Rs 7.9 lakh of node hardware), with battery wear counted: about 0.4 years;
10-year NPV Rs 113.1 lakh (Monte Carlo P5–P95 Rs 71.0 to 158.1 lakh,
100 % of samples positive). The tariff is a stand-in, so this moves when the real order arrives.

**10. What happens if the network goes down?**
Each building keeps optimising alone with its own forecast and safety layer; cables idle until links return. That's the
2.11-point penalty above. Central MPC's buildings fall back to simple rules.

**11. Does it scale?**
Each building talks only to its neighbours: 399 messages per decision on RVCE and
4.6 s per decision on a laptop. Work grows with a building's neighbours, not the
network. Not yet tested on a feeder model — that's in the scale path.

**12. Is the data real?**
Solar: NASA POWER (real). Hostel load shape: Ausgrid (real). Layout: OpenStreetMap (real). RVCE meter loads, calendar, tariff,
CO₂ factor: PENDING, labelled stand-ins. Four other campuses use public BDG2 and CU-BEMS meter data.

**13. Does it work on other campuses?**
Among methods without a central controller, Q-Grid is closest to the best plan on 4 of 5
campuses. Where it isn't, we name the method that was closer (docs/benchmark_v3.md, Wilcoxon verdicts).

**14. On the US sites every optimiser raises the bill. Why?**
No method optimises the demand charge; batteries charged from the grid raise the peak, and the stand-in demand charge bills
it. Q-Grid on BDG2 Fox: -0.4 % bill change. It's reported, not hidden.

**15. Why not reinforcement learning?**
Out of scope for this build and not in the benchmark; we didn't want an under-tuned RL baseline to flatter us.

**16. How do you handle forecast error?**
Every non-oracle method gets the same gradient-boosted solar and load forecasts (rolling for MPC). Only the reference "best
possible plan" sees the future, and it's shown as a reference line, not a competitor.

**17. Is ADMM guaranteed to converge?**
The part we coordinate is a convex LP, where consensus ADMM converges (Boyd et al. 2011). The on/off decisions stay inside each
building and are solved exactly. Measured convergence is in Verify.

**18. What is a "certified gap"?**
A proven upper bound on how far from optimal a plan is, from lower bounds (LP relaxation, MILP dual bound, Lagrangian bound):
Q-Grid 0.76 % on RVCE.

**19. What if a faculty rule is impossible?**
It's refused with a reason before it can touch a schedule — e.g. "EV charging only after 10 pm": window 22:00-23:45 is shorter than the job's duration (180 min) within one day; widen the window.

**20. What do you need to deploy at RVCE?**
One node per building (edge computer, meter, network: Rs 46,000–130,000 each, assumed), read access to the battery
and diesel controllers, 30 days of meter data, and the BESCOM tariff order. The demo already runs offline from replay files.
