# Viva prep: Sidhartha

**Area: results, benchmark, statistics, economics.**

Phone version, rendered from `docs/templates/viva_sidhartha.md`: every number is from `results/` (the `real-data` full
run). Question numbers in (brackets) are Shoumik's PDF. Your spoken script: [segment4_sidhartha.md](segment4_sidhartha.md).

---

## The headline you defend

**{{headline.sentence}}**

---

## How to answer

1. **Claim** in one sentence.
2. **One number.**
3. **Source or limit:** "it's clickable in Verify".

Under 20 seconds. If you don't know: "We haven't measured that; here's how we would." Never guess a number.

**Never say:** quantum advantage · RVCE's real load · proven rupee savings.

---

## Your segment (3:00–4:15)

**In:** Harshith says "Sidhartha has the numbers across all days."
**You:** "That was one day. Here are all {{hl.n_days|0}}."

- **7a scorecard:** outage downtime {{hl.sq_downtime_h|1}} h → {{hl.q_downtime_min|0}} min; {{hl.diesel_abs_l|0}} L more diesel
- **7f energy flows:** pass through
- **7b other campuses:** closest on {{q3.best_on_n|0}} of {{q3.n_campuses|0}} (drop if 15 s late at 3:00)
- **7c network failure:** central loses {{q3.n.central_comms_penalty|1}} points, Q-Grid {{q3.n.qgrid_comms_penalty|2}}
- skip **7d**
- **7e:** "Q-Grid buys reliability, not savings."

**Out:** "Shoumik will show how we'd deploy it."

Also: write down every question the judges ask (for Round 2).

---

## 1. Is the benchmark fair?

**What did you compare?**
Ten ways of running the same campus on the same 30 days: today's practice, rule-based, GA, PSO, per-building MPC, central MPC (with and without a network failure), Q-Grid (with and without), and a perfect-hindsight optimum. Same data, forecasts, constraints, 24 h horizon and cost function.

**What is the "best possible plan"? (31)**
One central MILP that knows the future perfectly. No real controller can match it, so it's the yardstick, not a competitor. Its own certified gap: {{q3.b.rvce.optimum.certified_gap_pct|3}} %.

**What does "gap" mean?**
How much more a method's plan costs than the best possible plan on the same day, in %. The cost counts energy, the monthly demand charge, diesel, battery wear and a penalty for unserved load.

**What is a "certified gap"?**
A proven upper bound on how far a plan is from the true optimum, from lower bounds (LP relaxation, the MILP's dual bound, a Lagrangian bound). It means "at most this far", without knowing the true optimum. Q-Grid on RVCE: {{q3.b.rvce.qgrid.certified_gap_pct|2}} %.

**Did every method get the same information?**
Yes. All except the perfect-hindsight reference get the same gradient-boosted solar and load forecasts; MPC methods re-plan as the day goes. Every plan is scored on what actually happened.

**Did central MPC get a fair solver budget? (32)**
Yes: same forecasts, same objective, its own time budget for one central problem. With a working network it lands {{q3.b.rvce.central_mpc.gap_pct|1}} % from the best plan.

**How was the network failure simulated?**
One 3-hour campus network outage per day, at the same seeded time for central MPC and Q-Grid. Central control's buildings fall back to simple rules; Q-Grid's buildings keep optimising alone.

**Why five campuses?**
To show it isn't tuned to RVCE. Three university campuses from Building Data Genome 2 and a Bangkok office building (CU-BEMS), each with its own real meter data. Q-Grid is closest on {{q3.best_on_n|0}} of {{q3.n_campuses|0}}; on the other two (BDG2 Bull and Cockatoo) per-building MPC is closer, and we say so.

**How do we know you didn't cherry-pick? (47)**
Seeded days, the same for every method; every result file hashed in a manifest; `make verify` recomputes the headline numbers; we name where another method beats Q-Grid. Money-only gap (no lost-load penalty): today {{q3.b.rvce.status_quo.gap_novoll_pct|2}} %, Q-Grid {{q3.b.rvce.qgrid.gap_novoll_pct|2}} %, so on money alone Q-Grid is behind.

**Only 30 days? (46)**
30 days across the year on each of 5 datasets, as paired comparisons. A 365-day RVCE run follows once we have meter data.

**Did anything in the run need fixing?**
Yes, and it's logged. The feasibility audit wrongly flagged 37 outage-day rows (diesel runs cut short when the grid returns, which the planners allow). We fixed the audit and re-ran those rows: 35 came back identical. Details: docs/review_real_data.md.

---

## 2. Statistics

**Why Wilcoxon, not a t-test?**
Paired comparison (same days for both methods), and daily differences are skewed because outage days dominate. The Wilcoxon signed-rank test doesn't assume a normal distribution.

**Is Q-Grid significantly better than per-building MPC?**
Not significantly. Day by day Q-Grid is closer on {{q3.rv.qgrid_closer_days|0}} of {{q3.rv.n_days|0}} days (Wilcoxon p = {{q3.rv.p|3}}, above 0.05). Most of its lower average comes from the outage days, where it keeps critical loads up; on normal days per-building MPC is slightly closer ({{hl.ngap.per_building_mpc|1}} % against {{hl.ngap.qgrid|1}} %).

**Q-Grid vs nine methods: what about multiple comparisons?**
We report each p-value as it is. With 9 comparisons a Bonferroni threshold is 0.05 / 9 ≈ 0.006.

**What do the ± and 95 % intervals mean?**
The uncertainty of each mean across the 30 days. Where two methods' intervals overlap heavily, we don't claim a difference.

---

## 3. Reading the results

**Does it save money?**
Barely. On normal days the bill is {{hl.normal_abs_pct|1}} % {{hl.normal_dir}}; over all days {{hl.all_abs_pct|1}} % {{hl.all_dir}}, because it burns diesel in outages, and the nodes don't pay back on the bill. The value is reliability: {{hl.downtime_cut_min|0}} fewer minutes of blackout for critical loads per outage.

**It uses more diesel in outages. Isn't that worse?**
Today's practice saves diesel by letting critical loads go dark: {{hl.sq_diesel_l|0}} L and {{hl.sq_downtime_h|1}} h dark, against Q-Grid's {{hl.q_diesel_l|0}} L and {{hl.q_downtime_h|2}} h. That's a deliberate trade, priced in the objective.

**Why is per-building MPC slightly better on normal days?**
On normal days Q-Grid is {{hl.ngap.qgrid|1}} % from the best plan, against {{hl.ngap.per_building_mpc|1}} % for per-building MPC and {{hl.ngap.status_quo|1}} % for today. Q-Grid's buildings share one campus peak allowance, and splitting it between them isn't perfect.

**Didn't you change the planner the morning of the expo?**
Yes, one defect the full run exposed, and we re-ran every Q-Grid row with the same data and seeds. Each building got a share of the campus peak allowance that followed its own plan, so a building that planned no import in a slot got almost none there. It then paid for a private peak, and that made extra import look free at other times. On 24 February two buildings charged their batteries at the 18:00 peak (1,371 kVA). Now a building keeps what it planned plus a fixed share of the spare allowance. There's a regression test, and the old and new rows are logged in `run_info.json`.

**Why not use central MPC? (37)**
On RVCE it isn't closer even with a working network ({{q3.b.rvce.central_mpc.gap_pct|1}} % against Q-Grid's {{q3.b.rvce.qgrid.gap_pct|1}} %), and in a 3-hour network failure it loses {{q3.n.central_comms_penalty|1}} points while Q-Grid moves by {{q3.n.qgrid_comms_penalty|2}}. One server and one network are a single point of failure.

**How does diesel reach buildings without a diesel set?**
In the model, over proposed links between buildings. On campus it depends on which buildings the two diesel sets can feed, which we've asked the estate office. If they back only their own buildings, the outage gain shrinks.

**Why non-zero critical downtime?**
Strict counting flags any 15-minute slot with any critical shortfall. Counting only shortfalls above 1 % of critical load, Q-Grid is {{q3.b.rvce.qgrid.critical_downtime_1pct_h|2}} h a day on average.

---

## 4. Tariff and economics

**Which tariff, and is it real? (23)**
BESCOM HT-2(c)(ii), "Hospitals and Educational Institutions", checked page by page in the KERC Tariff Orders:
- Jan–Mar 2023 days (Order 2022): Rs 8.25 / 8.65 per kWh, Rs 265 per kVA a month
- from 1 April 2023 (Order 2023): Rs 8.50 per kWh, Rs 350 per kVA a month
- time-of-day, Dec–Jun: +Rs 1 from 18–22 h, −Rs 1 from 22–06 h

What's assumed: contract demand and the building loads.

**How did you bill the demand charge? (22)**
Monthly, per kVA, on the month's highest 15-minute demand, with a floor of 85 % of contract demand and double rate above it, settled exactly like that, and every planner sees it in its objective. Today's highest monthly peak: {{hl.dc.1300.sq_md_kva|0}} kVA; Q-Grid's: {{hl.dc.1300.q_md_kva|0}} kVA.

**You don't know RVCE's contract demand.**
Assumed 1,300 kVA. Change in the monthly demand charge with Q-Grid: Rs {{hl.dc.1000.change_rs|0}} at 1,000 kVA, Rs {{hl.dc.1300.change_rs|0}} at 1,300 kVA, Rs {{hl.dc.1600.change_rs|0}} at 1,600 kVA (positive = Q-Grid pays more). One BESCOM bill settles it.

**Export rate? (24)**
Rs 3.74 per kWh, KERC solar order of 1 June 2023 (rooftop PV 1–2,000 kW). With RVCE's 500 kWp there's little export anyway.

**What's the payback? (21, 26)**
{{imp.sentence}}

**Why is battery wear in the objective?**
Without it the optimiser cycles for tiny price gaps and loses money after wear. Wear = battery cost ÷ (2 × cycle life × depth of discharge), so it cycles only when that pays. Q-Grid cycles {{q3.b.rvce.qgrid.battery_cycles|2}} times a day.

**Value of lost load?**
A penalty for unserved energy: Rs 40/kWh non-critical, Rs 1,000/kWh critical. An assumption, labelled as one; every gap is also reported without it (see above).

**Business model? (25)**
Per-building subscription or a share of measured savings, after a shadow-mode period proves the value. On these numbers, the pitch to RVCE is reliability, not savings.

---

## 5. Data questions you may get

**Is the load RVCE's?**
No: RVCE's floor areas × typical energy use, on real university load shapes. Labelled pending until meter data.

**Are the outages real?**
No: simulated, seeded, identical for every method ({{hl.n_outage_days|0}} of the {{hl.n_days|0}} RVCE days). BESCOM outage logs would replace them.

**Do the batteries and cables exist?**
No: proposed, and labelled. Solar (500 kWp on 21 roofs) and two 490 kVA diesel sets are RVCE's own figures.

---

## 6. Answers in Shoumik's PDF that change on `real-data`

If the team presents the `real-data` build, don't use these old lines:

- **7a:** "0.76 % from the best plan; best other method 21.7 %" → {{q3.b.rvce.qgrid.gap_pct|1}} % vs {{q3.b.rvce.per_building_mpc.gap_pct|1}} % (lead made on outage days)
- **7a:** "downtime halves, 16 to 8 minutes a day" → per outage: {{hl.sq_downtime_h|1}} h → {{hl.q_downtime_min|0}} min
- **7b:** "closest on four of five" → {{q3.best_on_n|0}} of {{q3.n_campuses|0}}
- **7c:** "3.5 vs 2.1 points" → {{q3.n.central_comms_penalty|1}} vs {{q3.n.qgrid_comms_penalty|2}}
- **7c:** "rupee figures use a stand-in tariff" → it's the verified KERC tariff
- **Shoumik's opening:** "within 1 % of a perfect central optimiser" → {{q3.b.rvce.qgrid.gap_pct|1}} % from the best possible plan; "sells noon solar cheaply" → no longer true
- **Q19 (Shoumik):** "3,974 kWp" → RVCE has 500 kWp; 3,974 was roof potential
- **Q21 / Q26:** "NPV positive in every sample" → P(NPV > 0) = {{imp.mc.npv_net_rs.prob_positive|0}} %
- **Q22:** "1/30 per day" → billed monthly, as the tariff says
- **Q24:** "export at Rs 3" → Rs 3.74
- **Q37:** "0.09 vs 0.14 h/day" → central {{q3.b.rvce.central_mpc.critical_downtime_h|2}}, Q-Grid {{q3.b.rvce.qgrid.critical_downtime_h|2}} h/day
- **Q47:** "money-only gap 4.96 % vs 1.46 %" → today {{q3.b.rvce.status_quo.gap_novoll_pct|2}} %, Q-Grid {{q3.b.rvce.qgrid.gap_novoll_pct|2}} %
- **Q28 (Harshith):** "0.5 s per building": the scorecard code I ran uses 5 s; check with Yashas

If the team presents the old portal, the PDF's numbers match the screen. Just don't call its tariff real.

---

## 7. Curveballs

**What did you personally do?**
In your own words. True version: "I led the real-data pass. I checked the BESCOM tariff against the KERC orders, re-ran the five-campus benchmark on RVCE's real assets, found and documented what changed, and I own the results and the economics."

**What's the weakest part?**
The money: over all days the bill is {{hl.all_abs_pct|1}} % {{hl.all_dir}} (diesel in outages) and the nodes don't pay back. Loads are modelled and outages simulated; RVCE's own data fixes both. And we fixed a planner defect after the full run, so the scorecard is from the re-run.

**Three more months?**
RVCE meter data and a 365-day run; the real BESCOM bill; which buildings the diesel sets feed; a pilot building in shadow mode.

**How would you know if a number on your slide is wrong?**
Every number links to the file that produced it ("clickable in Verify"), and `make verify` recomputes the headline numbers from scratch.
