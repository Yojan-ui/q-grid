# Q&A prep — the 20 hardest judge questions

_Rendered from `docs/templates/qa_prep.md`; every number from `results/` (locked headline: `results/headline.json`;
scorecard: `results/bench_v3`; impact: `results/impact`; live moments: `results/replay/live.json`). Answer in one or two
sentences, then offer the source: "it's clickable in Verify"._

**The headline you are defending:** {{headline.sentence}}

## Quantum

**1. Where is the quantum advantage?**
There is none, and we say so. QAOA ran on a local simulator and every answer was checked against exact search. In the
placement test ({{q3.qp.instances}} building problems) branch and bound already finished at its first node
{{q3.qp.cold_root_node_pct|1}} % of the time. The quantum starting plan was correct ({{q3.qp.qaoa_block_opt_pct|0}} % of blocks)
but saved no work, so Q-Grid does not use it in the control loop.

**2. Then why is quantum in the project at all?**
The track asked us to evaluate it, and an honest negative result is still a result. The QUBO formulation, the verification
harness and the tiered fallback (QAOA → simulated annealing → exact, with a safety layer on every command) stay in the repo
for problems where branch and bound does struggle: larger blocks, more devices per building.

**3. Earlier runs showed the QAOA master beating the exact master. Was the exact solver wrong?**
No, the comparison was. The QAOA proposal was used unverified while the exact master had a trust region, so the two runs took
different paths through the day. Now every heuristic proposal is checked against the exact one and the exact one is kept.
In the re-run the QAOA variant beat the exact variant on {{cons.qaoa_beats_exact_days|0}} of {{cons.days|0}} days; QAOA's own
proposal matched the exact one in {{cons.qaoa_agree_pct|1}} % of master solves. A test enforces it. docs/consistency.md §1.

## Why this design

**4. Why not just solve one big MILP centrally?**
We do use MILP, inside each building: every node solves its own on/off plan exactly. The central MILP with perfect
information is our reference, the "best possible plan". A central MPC with the same forecasts lands
{{q3.b.rvce.central_mpc.gap_pct|2}} % from it; Q-Grid lands {{q3.b.rvce.qgrid.gap_pct|2}} %. With a working network the two are
close; the real difference is what happens when the network fails (question 6).

**5. RVCE has one owner. Why decentralise at all?**
One owner still means one server and one network to keep alive. A node per building keeps optimising alone when links drop,
can be installed one building at a time, and keeps each department's rules local. If you trust one server and its network,
central MPC is a reasonable choice, and our scorecard shows how close it gets.

**6. What happens if the campus network goes down?**
Each building keeps optimising alone with its own forecast and safety layer; cables idle until links return. In a seeded
3-hour network failure, central control loses {{q3.n.central_comms_penalty|2}} points of gap and Q-Grid
{{q3.n.qgrid_comms_penalty|2}}, because the central controller's buildings fall back to simple rules.

**7. And if one building's node fails?**
That is live moment 2. Mechanical labs go offline, its {{live.remove.lines|0}} cables go dark, the others re-agree in
{{live.remove.rounds_after|0}} rounds, and {{live.remove.crit_text}}.

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
least 85 % of contract demand. RVCE's contract demand is assumed ({{hl.contract_kva|0}} kVA) and its loads are modelled, so
absolute rupees are modelled; every method sees the same prices, so comparisons hold.

## Money

**11. Does it save money?**
On normal days the bill is {{hl.normal_abs_pct|1}} % {{hl.normal_dir}} than today; over all days, {{hl.all_abs_pct|1}} %
{{hl.all_dir}}. At {{hl.contract_kva|0}} kVA contract demand the monthly demand charge {{hl.dc.base.verb}} by Rs
{{hl.dc.base.abs_change_rs|0}}. We lead with outages and diesel, and report the everyday bill exactly as measured.

**12. The demand charge depends on a contract demand you don't know.**
Right, so we show three: change per month at 1,000 kVA Rs {{hl.dc.1000.change_rs|0}}, at 1,300 kVA Rs
{{hl.dc.1300.change_rs|0}}, at 1,600 kVA Rs {{hl.dc.1600.change_rs|0}} (negative = Q-Grid pays less). One RVCE bill settles it.

**13. So what's the payback?**
{{imp.sentence}}

**14. What about battery degradation?**
It's in the objective. Every optimiser, Q-Grid, both MPCs, GA/PSO and the best possible plan, prices wear per kWh charged or
discharged (`config.yaml` → `battery_wear`), and the scorecard counts it. Q-Grid cycles the batteries
{{q3.b.rvce.qgrid.battery_cycles|2}} times a day.

## Results

**15. A small gap but non-zero critical downtime. Which is it?**
Both, from the same run. Strict downtime counts any 15-minute slot with any critical shortfall: Q-Grid
{{q3.b.rvce.qgrid.critical_downtime_h|2}} h a day on average; counting only shortfalls above 1 % of critical load,
{{q3.b.rvce.qgrid.critical_downtime_1pct_h|2}} h. On outage days the figure is {{hl.q_downtime_h|2}} h per outage, against
{{hl.sq_downtime_h|2}} h today and {{hl.opt_downtime_h|2}} h for the best possible plan.

**16. Where does the value of lost load come from?**
An assumption, stated: Rs 40/kWh non-critical, Rs 1,000/kWh critical (`config.yaml` → `outage_costs`), used only inside
objectives. Every gap is also reported on money alone: Q-Grid {{q3.b.rvce.qgrid.gap_novoll_pct|2}} %.

**17. Does it work on other campuses?**
Among methods without a central controller, Q-Grid is closest to the best plan on {{q3.best_on_n|0}} of {{q3.n_campuses|0}}
campuses. Where it isn't, docs/benchmark_v3.md names the method that was closer, with Wilcoxon verdicts.

**18. What is a "certified gap", and is ADMM guaranteed to converge?**
A certified gap is a proven upper bound on distance from optimal, from lower bounds (LP relaxation, MILP dual bound):
Q-Grid {{q3.b.rvce.qgrid.certified_gap_pct|2}} % on RVCE. The part we coordinate between buildings is a convex LP, where
consensus ADMM converges (Boyd et al. 2011); the on/off choices stay inside each building and are solved exactly.

## Limits and rollout

**19. What are the limits?**
No quantum advantage. Outages and network failures are synthetic. RVCE loads are modelled until meter data arrives. Batteries,
EV chargers and inter-building cables don't exist on campus today (PROPOSED). The outage gain comes from sharing the two
diesel sets' power with other buildings, so it depends on which buildings those sets can feed. There is no real bill saving: on
normal days the bill is {{hl.normal_abs_pct|1}} % {{hl.normal_dir}}, over all days {{hl.all_abs_pct|1}} % {{hl.all_dir}} (diesel in outages),
and the nodes don't pay back on the bill. Contract demand is assumed until RVCE's bill arrives. Cables are lossless, without AC
power flow.

**20. What do you need to deploy at RVCE?**
One node per building (edge computer, meter, network: Rs {{imp.hw_lo|0}}–{{imp.hw_hi|0}} each, assumed), read access to the
diesel and (future) battery controllers, one BESCOM HT bill, the diesel logs and 30 days of meter data. Start in shadow mode:
the node recommends, staff decide, and we compare. The demo already runs offline from replay files.
