# Viva prep: Sidhartha

**Area: results, benchmark, statistics, economics.**

Phone version, rendered from `docs/templates/viva_sidhartha.md`: every number is from `results/` (the `real-data` full
run). Question numbers in (brackets) are Shoumik's PDF. Your spoken script: [segment4_sidhartha.md](segment4_sidhartha.md).

---

## The headline you defend

**In a BESCOM outage Q-Grid cuts critical-load downtime from 2.6 h to 55 min per outage (41 L more diesel, 110 kg CO₂, to keep those loads up); on normal days the bill is 0.4% higher and the demand charge rises by Rs 16,685 a month at 1,300 kVA contract demand; with no central controller it averages 8.4% from the best possible plan against 9.2% for Per-building MPC, a lead made on the outage days (normal days: 7.4% against 0.3%).**

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
**You:** "That was one day. Here are all 30."

- **7a scorecard:** outage downtime 2.6 h → 55 min; 41 L more diesel
- **7f energy flows:** pass through
- **7b other campuses:** closest on 1 of 5 (drop if 15 s late at 3:00)
- **7c network failure:** central loses 2.7 points, Q-Grid 0.7
- skip **7d**
- **7e:** "Q-Grid buys reliability, not savings."

**Out:** "Shoumik will show how we'd deploy it."

Also: write down every question the judges ask (for Round 2).

---

## 1. Is the benchmark fair?

**What did you compare?**
Ten ways of running the same campus on the same 30 days: today's practice, rule-based, GA, PSO, per-building MPC, central MPC (with and without a network failure), Q-Grid (with and without), and a perfect-hindsight optimum. Same data, forecasts, constraints, 24 h horizon and cost function.

**What is the "best possible plan"? (31)**
One central MILP that knows the future perfectly. No real controller can match it, so it's the yardstick, not a competitor. Its own certified gap: 0.004 %.

**What does "gap" mean?**
How much more a method's plan costs than the best possible plan on the same day, in %. The cost counts energy, the monthly demand charge, diesel, battery wear and a penalty for unserved load.

**What is a "certified gap"?**
A proven upper bound on how far a plan is from the true optimum, from lower bounds (LP relaxation, the MILP's dual bound, a Lagrangian bound). It means "at most this far", without knowing the true optimum. Q-Grid on RVCE: 8.37 %.

**Did every method get the same information?**
Yes. All except the perfect-hindsight reference get the same gradient-boosted solar and load forecasts; MPC methods re-plan as the day goes. Every plan is scored on what actually happened.

**Did central MPC get a fair solver budget? (32)**
Yes: same forecasts, same objective, its own time budget for one central problem. With a working network it lands 1.4 % from the best plan.

**How was the network failure simulated?**
One 3-hour campus network outage per day, at the same seeded time for central MPC and Q-Grid. Central control's buildings fall back to simple rules; Q-Grid's buildings keep optimising alone.

**Why five campuses?**
To show it isn't tuned to RVCE. Three university campuses from Building Data Genome 2 and a Bangkok office building (CU-BEMS), each with its own real meter data. Q-Grid is closest on 1 of 5; on the others per-building MPC (or PSO on CU-BEMS) is closer, and we say so.

**How do we know you didn't cherry-pick? (47)**
Seeded days, the same for every method; every result file hashed in a manifest; `make verify` recomputes the headline numbers; we name where another method beats Q-Grid. Money-only gap (no lost-load penalty): today 3.04 %, Q-Grid 9.62 %, so on money alone Q-Grid is behind.

**Only 30 days? (46)**
30 days across the year on each of 5 datasets, as paired comparisons. A 365-day RVCE run follows once we have meter data.

**Did anything in the run need fixing?**
Yes, and it's logged. The feasibility audit wrongly flagged 37 outage-day rows (diesel runs cut short when the grid returns, which the planners allow). We fixed the audit and re-ran those rows: 35 came back identical. Details: docs/review_real_data.md.

---

## 2. Statistics

**Why Wilcoxon, not a t-test?**
Paired comparison (same days for both methods), and daily differences are skewed because outage days dominate. The Wilcoxon signed-rank test doesn't assume a normal distribution.

**Is Q-Grid significantly better than per-building MPC?**
No, the honest answer is the other way round. Per-building MPC is closer to the best plan on 27 of 30 days (Wilcoxon p = 0.002). Q-Grid's lower average comes from the outage days, where it keeps critical loads up.

**Q-Grid vs nine methods: what about multiple comparisons?**
We report each p-value as it is. With 9 comparisons a Bonferroni threshold is 0.05 / 9 ≈ 0.006.

**What do the ± and 95 % intervals mean?**
The uncertainty of each mean across the 30 days. Where two methods' intervals overlap heavily, we don't claim a difference.

---

## 3. Reading the results

**Does it save money?**
No. On normal days the bill is 0.4 % higher; over all days 0.9 % higher. The value is reliability: 100 fewer minutes of blackout for critical loads per outage.

**It uses more diesel in outages. Isn't that worse?**
Today's practice saves diesel by letting critical loads go dark: 373 L and 2.6 h dark, against Q-Grid's 414 L and 0.92 h. That's a deliberate trade, priced in the objective.

**Why is Q-Grid worse on normal days?**
On normal days it's 7.4 % from the best plan, against 0.3 % for per-building MPC and 2.4 % for today. One cause we found: on 24 February it charges the batteries at about 369 kW between 18:00 and 18:45, the dearest slot, and sets the month's peak above contract demand. It's reproducible and we're tracing it in the planner.

**Central MPC beats Q-Grid with a healthy network. Why not use it? (37)**
With a working network central control is closer (1.4 % vs 8.4 %). In a 3-hour network failure it loses 2.7 points and Q-Grid 0.7. One server and one network are a single point of failure.

**How does diesel reach buildings without a diesel set?**
In the model, over proposed links between buildings. On campus it depends on which buildings the two diesel sets can feed, which we've asked the estate office. If they back only their own buildings, the outage gain shrinks.

**Why non-zero critical downtime?**
Strict counting flags any 15-minute slot with any critical shortfall. Counting only shortfalls above 1 % of critical load, Q-Grid is 0.00 h a day on average.

---

## 4. Tariff and economics

**Which tariff, and is it real? (23)**
BESCOM HT-2(c)(ii), "Hospitals and Educational Institutions", checked page by page in the KERC Tariff Orders:
- Jan–Mar 2023 days (Order 2022): Rs 8.25 / 8.65 per kWh, Rs 265 per kVA a month
- from 1 April 2023 (Order 2023): Rs 8.50 per kWh, Rs 350 per kVA a month
- time-of-day, Dec–Jun: +Rs 1 from 18–22 h, −Rs 1 from 22–06 h

What's assumed: contract demand and the building loads.

**How did you bill the demand charge? (22)**
Monthly, per kVA, on the month's highest 15-minute demand, with a floor of 85 % of contract demand and double rate above it, settled exactly like that, and every planner sees it in its objective. Today's highest monthly peak: 1,194 kVA; Q-Grid's: 1,371 kVA.

**You don't know RVCE's contract demand.**
Assumed 1,300 kVA. Change in the monthly demand charge with Q-Grid: Rs 41,261 at 1,000 kVA, Rs 16,685 at 1,300 kVA, Rs 238 at 1,600 kVA (positive = Q-Grid pays more). One BESCOM bill settles it.

**Export rate? (24)**
Rs 3.74 per kWh, KERC solar order of 1 June 2023 (rooftop PV 1–2,000 kW). With RVCE's 500 kWp there's little export anyway.

**What's the payback? (21, 26)**
Node hardware ≈ Rs 7.9 lakh for 9 buildings (assumed costs); the bill rises by ≈ Rs 5.8 lakh/year; extra battery wear ≈ Rs 8.9 lakh/year (every optimiser prices wear in its objective). On these assumptions the nodes do not pay back on the electricity bill alone (10-year NPV Rs -111.6 lakh) (Monte Carlo P5–P95: Rs -136.2 to -64.5 lakh; P(NPV > 0) = 0 %).

**Why is battery wear in the objective?**
Without it the optimiser cycles for tiny price gaps and loses money after wear. Wear = battery cost ÷ (2 × cycle life × depth of discharge), so it cycles only when that pays. Q-Grid cycles 0.21 times a day.

**Value of lost load?**
A penalty for unserved energy: Rs 40/kWh non-critical, Rs 1,000/kWh critical. An assumption, labelled as one; every gap is also reported without it (see above).

**Business model? (25)**
Per-building subscription or a share of measured savings, after a shadow-mode period proves the value. On these numbers, the pitch to RVCE is reliability, not savings.

---

## 5. Data questions you may get

**Is the load RVCE's?**
No: RVCE's floor areas × typical energy use, on real university load shapes. Labelled pending until meter data.

**Are the outages real?**
No: simulated, seeded, identical for every method (3 of the 30 RVCE days). BESCOM outage logs would replace them.

**Do the batteries and cables exist?**
No: proposed, and labelled. Solar (500 kWp on 21 roofs) and two 490 kVA diesel sets are RVCE's own figures.

---

## 6. Answers in Shoumik's PDF that change on `real-data`

If the team presents the `real-data` build, don't use these old lines:

- **7a:** "0.76 % from the best plan; best other method 21.7 %" → 8.4 % vs 9.2 % (lead made on outage days)
- **7a:** "downtime halves, 16 to 8 minutes a day" → per outage: 2.6 h → 55 min
- **7b:** "closest on four of five" → 1 of 5
- **7c:** "3.5 vs 2.1 points" → 2.7 vs 0.7
- **7c:** "rupee figures use a stand-in tariff" → it's the verified KERC tariff
- **Shoumik's opening:** "within 1 % of a perfect central optimiser" and "sells noon solar cheaply" → no longer true
- **Q19 (Shoumik):** "3,974 kWp" → RVCE has 500 kWp; 3,974 was roof potential
- **Q21 / Q26:** "NPV positive in every sample" → P(NPV > 0) = 0 %
- **Q22:** "1/30 per day" → billed monthly, as the tariff says
- **Q24:** "export at Rs 3" → Rs 3.74
- **Q37:** "0.09 vs 0.14 h/day" → central 0.00, Q-Grid 0.09 h/day
- **Q47:** "money-only gap 4.96 % vs 1.46 %" → today 3.04 %, Q-Grid 9.62 %
- **Q28 (Harshith):** "0.5 s per building": the scorecard code I ran uses 5 s; check with Yashas

If the team presents the old portal, the PDF's numbers match the screen. Just don't call its tariff real.

---

## 7. Curveballs

**What did you personally do?**
In your own words. True version: "I led the real-data pass. I checked the BESCOM tariff against the KERC orders, re-ran the five-campus benchmark on RVCE's real assets, found and documented what changed, and I own the results and the economics."

**What's the weakest part?**
On real data Q-Grid helps in outages but costs more on normal days, partly from a defect we found. Loads are modelled and outages simulated; RVCE's own data fixes both.

**Three more months?**
Fix the evening-peak defect and re-run; RVCE meter data and a 365-day run; the real BESCOM bill; which buildings the diesel sets feed; a pilot building in shadow mode.

**How would you know if a number on your slide is wrong?**
Every number links to the file that produced it ("clickable in Verify"), and `make verify` recomputes the headline numbers from scratch.
