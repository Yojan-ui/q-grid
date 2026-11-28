# Q&A prep — the 20 hardest judge questions

_Rendered from `docs/templates/qa_prep.md`; every number from `results/` (locked headline: `results/headline.json`;
scorecard: `results/bench_v3`; impact: `results/impact`; live moments: `results/replay/live.json`). Answer in one or two
sentences, then offer the source: "it's clickable in Verify"._

**The headline you are defending:** In a BESCOM outage Q-Grid cuts critical-load downtime from 2.6 h to 20 min per outage (45 L more diesel, 122 kg CO₂, to keep those loads up); on normal days the bill is 0.1% lower and the demand charge falls by Rs 5,278 a month at 1,300 kVA contract demand; with no central controller it averages 1.1% from the best possible plan against 9.2% for Per-building MPC, a lead made on the outage days (normal days: 0.6% against 0.3%).

## Quantum

**1. Where is the quantum advantage?**
There is none, and we say so. QAOA ran on a local simulator and every answer was checked against exact search. In the
placement test (1,080 building problems) branch and bound already finished at its first node
99.9 % of the time. The quantum starting plan was correct (100 % of blocks)
but saved no work, so Q-Grid does not use it in the control loop.

**2. Then why is quantum in the project at all?**
The track asked us to evaluate it, and an honest negative result is still a result. The QUBO formulation, the verification
harness and the tiered fallback (QAOA → simulated annealing → exact, with a safety layer on every command) stay in the repo
for problems where branch and bound does struggle: larger blocks, more devices per building.

**3. Earlier runs showed the QAOA master beating the exact master. Was the exact solver wrong?**
No, the comparison was. The QAOA proposal was used unverified while the exact master had a trust region, so the two runs took
different paths through the day. Now every heuristic proposal is checked against the exact one and the exact one is kept.
In the re-run the QAOA variant beat the exact variant on 0 of 30 days; QAOA's own
proposal matched the exact one in 97.3 % of master solves. A test enforces it. docs/consistency.md §1.

## Why this design

**4. Why not just solve one big MILP centrally?**
We do use MILP, inside each building: every node solves its own on/off plan exactly. The central MILP with perfect
information is our reference, the "best possible plan". A central MPC with the same forecasts lands
1.37 % from it; Q-Grid lands 1.06 %. With a working network the two are
close; the real difference is what happens when the network fails (question 6).

**5. RVCE has one owner. Why decentralise at all?**
One owner still means one server and one network to keep alive. A node per building keeps optimising alone when links drop,
can be installed one building at a time, and keeps each department's rules local. If you trust one server and its network,
central MPC is a reasonable choice, and our scorecard shows how close it gets.

**6. What happens if the campus network goes down?**
Each building keeps optimising alone with its own forecast and safety layer; cables idle until links return. In a seeded
3-hour network failure, central control loses 2.68 points of gap and Q-Grid
0.01, because the central controller's buildings fall back to simple rules.

**7. And if one building's node fails?**
That is live moment 2. Mechanical labs go offline, its 3 cables go dark, the others re-agree in
46 rounds, and every critical load in the other buildings is still served.

## Data

**8. Is the data real?**
Solar: NASA POWER (real). Layout: OpenStreetMap (real), rescaled to RVCE's own buildings. Tariff: BESCOM HT-2(c)(ii) from the
KERC Tariff Orders 2022 and 2023 (verified page by page, docs/data_verification.md). CO₂: CEA 0.727 t/MWh (verified). Solar
500.48 kWp, floor areas and 2 × 490 kVA diesel: RVCE team brief. RVCE meter loads and calendar: pending, so loads are floor
area × energy intensity on BDG2 university load shapes, and labelled. Four other campuses use public BDG2 and CU-BEMS meters.

**9. Are the outages real?**
No. They are synthetic and seeded, the same for every method, because we don't have RVCE's outage or diesel logs yet. We've
asked the estate office for them (docs/rvce_data_request_email.md).

**10. Are your rupee figures real?**
The tariff is: days before 1 April 2023 use Tariff Order 2022 (Rs 8.25 / 8.65 per kWh, Rs 265 per kVA a month), days from
1 April 2023 use Tariff Order 2023 (Rs 8.50 per kWh, Rs 350 per kVA a month), with time-of-day ±Rs 1 and billing demand at
least 85 % of contract demand. RVCE's contract demand is assumed (1,300 kVA) and its loads are modelled, so
absolute rupees are modelled; every method sees the same prices, so comparisons hold.

## Money

**11. Does it save money?**
On normal days the bill is 0.1 % lower than today; over all days, 0.4 %
higher. At 1,300 kVA contract demand the monthly demand charge falls by Rs
5,278. We lead with outages and diesel, and report the everyday bill exactly as measured.

**12. The demand charge depends on a contract demand you don't know.**
Right, so we show three: change per month at 1,000 kVA Rs -21,882, at 1,300 kVA Rs
-5,278, at 1,600 kVA Rs 0 (negative = Q-Grid pays less). One RVCE bill settles it.

**13. So what's the payback?**
Node hardware ≈ Rs 7.9 lakh for 9 buildings (assumed costs); the bill rises by ≈ Rs 3.2 lakh/year; extra battery wear ≈ Rs 3.3 lakh/year (every optimiser prices wear in its objective). On these assumptions the nodes do not pay back on the electricity bill alone (10-year NPV Rs -56.4 lakh) (Monte Carlo P5–P95: Rs -90.5 to -18.7 lakh; P(NPV > 0) = 0 %).

**14. What about battery degradation?**
It's in the objective. Every optimiser, Q-Grid, both MPCs, GA/PSO and the best possible plan, prices wear per kWh charged or
discharged (`config.yaml` → `battery_wear`), and the scorecard counts it. Q-Grid cycles the batteries
0.08 times a day.

## Results

**15. A small gap but non-zero critical downtime. Which is it?**
Both, from the same run. Strict downtime counts any 15-minute slot with any critical shortfall: Q-Grid
0.03 h a day on average; counting only shortfalls above 1 % of critical load,
0.01 h. On outage days the figure is 0.33 h per outage, against
2.58 h today and 0.00 h for the best possible plan.

**16. Where does the value of lost load come from?**
An assumption, stated: Rs 40/kWh non-critical, Rs 1,000/kWh critical (`config.yaml` → `outage_costs`), used only inside
objectives. Every gap is also reported on money alone: Q-Grid 2.66 %.

**17. Does it work on other campuses?**
Among methods without a central controller, Q-Grid is closest to the best plan on 3 of 5
campuses. Where it isn't, docs/benchmark_v3.md names the method that was closer, with Wilcoxon verdicts.

**18. What is a "certified gap", and is ADMM guaranteed to converge?**
A certified gap is a proven upper bound on distance from optimal, from lower bounds (LP relaxation, MILP dual bound):
Q-Grid 1.07 % on RVCE. The part we coordinate between buildings is a convex LP, where
consensus ADMM converges (Boyd et al. 2011); the on/off choices stay inside each building and are solved exactly.

## Limits and rollout

**19. What are the limits?**
No quantum advantage. Outages and network failures are synthetic. RVCE loads are modelled until meter data arrives. Batteries,
EV chargers and inter-building cables don't exist on campus today (PROPOSED). The outage gain comes from sharing the two
diesel sets' power with other buildings, so it depends on which buildings those sets can feed. There is no real bill saving: on
normal days the bill is 0.1 % lower, over all days 0.4 % higher (diesel in outages),
and the nodes don't pay back on the bill. Contract demand is assumed until RVCE's bill arrives. Cables are lossless, without AC
power flow.

**20. What do you need to deploy at RVCE?**
One node per building (edge computer, meter, network: Rs 46,000–130,000 each, assumed), read access to the
diesel and (future) battery controllers, one BESCOM HT bill, the diesel logs and 30 days of meter data. Start in shadow mode:
the node recommends, staff decide, and we compare. The demo already runs offline from replay files.
