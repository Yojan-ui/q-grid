# Review: real data on the `real-data` branch

Status on 27 Nov 2026, for the lead's decision before any headline text changes. Branch `real-data` (integration of
agents A, B and C by the lead, plus the regenerated scenario replays). Page numbers: PDF page (printed page).

## Where the job stands

| Part | State |
|---|---|
| Agent A (data): official tariff, CEA CO₂, campus rescale | merged (3445170) |
| Agent B (engine): diesel backup-only, monthly-peak term in every planner, monthly bill, Wilcoxon names, UTF-8 | merged (0a4c6b5) |
| Agent C (UI): Plan tab, PROPOSED badges, data-provenance dialog, Step 1 problem cards | merged (1b3e56b) |
| Integration: backup-only diesel in status quo / Operate / v2, rescaled layout, official prices; processed data rebuilt | done (0d6dd7b) |
| Scenario replays on the rescaled campus and new tariff; Plan, badges, provenance, problem cards | done (0290cfa) |
| Investment planner | done (eb3a989), stand-in costs |
| Quick RVCE run | done 27 Nov under both FY2023-24 tariff options (see "Quick RVCE run"); TO-2023 approved by the lead |
| FY2023-24 tariff | TO-2023 (Rs 8.50/kWh, Rs 350/kVA) VERIFIED and in `config.yaml` (e4e144b) |
| **Full benchmark (5 campuses)** | **done 28 Nov**, 8 workers, 6,955 s; see "Full benchmark: what it shows" below |
| Feasibility audit vs backup-only diesel | fixed (`check_feasibility`), regression test added, 37 rows re-run |
| Scorecard, locked headline, replays, docs | regenerated from the full run on 28 Nov |

## a) Every changed figure

| Figure | Old (stand-in, `harden`) | New (`real-data`) | Source file + page | Status |
|---|---|---|---|---|
| Tariff category | "HT educational institutions" | BESCOM HT-2(c)(ii) "Hospitals and Educational Institutions other than HT-2(c)(i)" | TO-2023 p382 (373); RVCE is self-financing: NAAC SSR 2024 p2, p11 | VERIFIED category text; RVCE's billing PENDING its bill |
| Energy charge FY2022-23 (Jan–Mar 2023) | Rs 8.00 base | Rs 8.25 first 1 lakh units/month, Rs 8.65 balance | TO-2022 printed p412 | VERIFIED (Agent A) |
| Energy charge FY2023-24 (from 1 Apr 2023; all headline days) | Rs 8.00 base | **branch: Rs 8.25 / 8.65 carried over from TO-2022** · **TO-2023 PDF: Rs 8.50 single slab** | TO-2023 `KERC_tariff_order_BESCOM_FY2023-24.pdf` p215 (206), p382 (373) | see c) and decision 1 |
| Demand charge FY2022-23 | Rs 350/kVA/month | Rs 265/kVA/month | TO-2022 printed p412 | VERIFIED |
| Demand charge FY2023-24 | Rs 350/kVA/month | **branch: Rs 265 carried over** · **TO-2023 PDF: Rs 350** | TO-2023 p215 (206), p382 (373) | see decision 1 |
| Demand billing | 1/30 of the charge per day on the day's peak | monthly: billing demand = max(MD, 85 % of CD), excess over CD at 2×, MD rounded to whole kVA | TO-2022 printed p404, p405 | VERIFIED |
| ToD | +Rs 1 06–10 h and 18–22 h, −Rs 1 22–06 h, all year | Dec–Jun only: +Rs 1 18–22 h, −Rs 1 22–06 h; Jul–Nov none; no morning peak | TO-2022 p412; TO-2023 p215 (206) | VERIFIED (both orders) |
| ToD only at contract demand ≥ 500 kVA | – | FY2023-24 yes; FY2022-23 no threshold | TO-2023 p208 (199); TO-2022 p412 | VERIFIED |
| Solar export | Rs 3.00/kWh | Rs 3.74/kWh | KERC solar order dated 01.06.2023, `KERC_solar_export_tariff.pdf` p30: SRTPV 1–2000 kW (excl. 1–10 kW) "Rs.3.74 per unit" | VERIFIED here (branch still says TEAM BRIEF) |
| CO₂ factor | 0.727 t/MWh (secondary sources) | 0.727 t/MWh | CEA CO₂ Baseline Database User Guide v20.0, Table S, p4 (1); unchanged in v21.0 p27 (21) | VERIFIED |
| Rooftop solar | 3,974 kWp (45 % of all mapped roofs) | 500.48 kWp existing, split over zones by roof area | RVCE grid-connection note (1,564 × 320 Wp, 21 roofs; page since removed); NAAC Cr 7.1.2 ≈ 525 kW | SOURCED, zone split ASSUMPTION |
| Built-up floor area (non-hostel) | OSM outline of all of RV Vidyaniketan (incl. RV University) | 67,721 m² (RVU buildings dropped) | NAAC SSR 2024 p12 | SOURCED; whether it includes hostels is ASSUMPTION (no) |
| Boys' hostels | from OSM | 38,659 m², 1,185 rooms, 1,450 beds | NAAC SSR 2024 p78 | SOURCED |
| Total floor area | 156,588 m² | 106,440 m² | derived | – |
| Diesel | 100 + 200 kW | 2 × 490 kVA = 980 kVA (392 kW each at 0.8 pf) | NAAC SSR 2024 p69: "two generators of capacity 980 KVA" | SOURCED total; 490 + 490 split and hosts ASSUMPTION |
| Diesel operation | could run with the grid up (min on-time) | backup only: off whenever the grid is up | engine fix, regression tests on 2023-06-20 | code |
| Annual campus load (model) | 12.29 GWh | 7.56 GWh | floor area × EPI (ASSUMPTION) on BDG2 shapes | model output |
| Campus peak (model) | 1,977 kW | 1,166 kW (≈ 1,227 kVA) | same | model output |
| Headline day 15 Jun 2023 energy | 36,791 kWh | 22,565 kWh; solar share 11 % (was 54 %) | same | model output |
| Batteries, EV charging, inter-building cables | shown as campus assets | labelled PROPOSED (not on campus today); UPS at server room EXISTS, size ASSUMPTION | NAAC SSR p69 (UPS) | PROPOSED |

Results figures (bill saving, gap to best plan, downtime, diesel litres, payback) are **not** in this table: they
have not been regenerated on the branch. The quick RVCE run below gives the first values.

## b) Still stand-in, PENDING or PROPOSED

- **IEX prices** (price scenario B, sensitivity only): SYNTHETIC STAND-IN.
- **RVCE's BESCOM bill**: tariff category actually billed, contract demand (1,300 kVA assumed), recorded maximum
  demand, whether hostels / staff quarters are metered separately (HT-2(c)(i) / HT-4).
- **RVCE academic calendar**: day types are PENDING templates; **lab schedule**: TEMPLATE.
- **Campus loads**: floor area × energy-per-m² ASSUMPTION on real BDG2 shapes; no RVCE meter data.
- **Diesel**: 490 + 490 kVA split, which buildings each set backs, fuel curve: ASSUMPTION.
- **Outages** in the benchmark: synthetic (seeded); the 18–21 h fest outage is an ASSUMED window.
- **PROPOSED assets**: batteries (all zones), EV charging, inter-building cables; battery and node costs are ASSUMPTION.
- **Battery wear** price (cost and cycle life): ASSUMPTION. **Value of lost load**: ASSUMPTION.
- **Not modelled**: electricity tax 9 %, fuel-cost adjustment, power-factor surcharge.
- **QAOA**: simulated (ideal, noiseless); not in the control loop.

## c) The Rs 8.50/kWh check

Source: KERC "Tariff Order 2023 of BESCOM … Revision of Retail Supply Tariff for FY24", dated 12th May 2023
(`data/raw/tariff/KERC_tariff_order_BESCOM_FY2023-24.pdf`, SHA-256 `018d3be5…0987b5b`, 385 pages).

PDF p215 (printed 206), Commission's decision, which also introduces a single slab in place of the two:

> HT-2(c)(ii) (Applicable for all areas) … Fixed Charges / month / KVA of Billing Demand: Per KVA Rs.350/-
> Energy Charges per kWh: For entire consumption 850 paise

The same values are in the tariff schedule, PDF p382 (printed 373): "HT-2(c)(ii): Applicable to Hospitals and
Educational Institutions other than those covered under HT-2 (c) (i) … Per KVA Rs.350/- … For entire consumption
850 paise".

- **Year:** FY2023-24 (from 1 April 2023). **Sub-category:** HT-2(c)(ii).
- **Rs 8.50 is correct for FY2023-24.** It differs from the ~Rs 7.5–7.9 seen in secondary sources because those
  are the **other** sub-category: HT-2(c)(i) (government / aided institutions and hostels of all educational
  institutions) is Rs 7.50 for FY2023-24 on the same page (Rs 300/kVA), and Rs 7.25 / 7.65 in FY2022-23.
- It also differs from the branch's FY2023-24 value (Rs 8.65 marginal, Rs 265/kVA), which is the FY2022-23 rate
  carried over because Agent A could not obtain this PDF.
- ToD for FY2023-24 (p215): Dec–Jun +100 paise 18–22 h, −100 paise 22–06 h; Jul–Nov none; 06–10 h zero.
  Mandatory at contract demand ≥ 500 kVA (p208, printed 199).

## Quick RVCE run

`python scripts/run_bench_v3.py --datasets=rvce --methods=status_quo,qgrid,optimum --no-design --no-bounds`, the 30
seeded RVCE evaluation days of 2023 (3 with a synthetic outage), rescaled campus, contract demand 1,300 kVA, bill
settled monthly (`write_bench_v3.monthly_bill`). Run on 27 Nov 2026 under both FY2023-24 tariff options. Outputs:
`results/sensitivity/tariff_A_carried/`, `results/sensitivity/tariff_B_to2023/` (not committed). Quick runs are not
the scorecard: one campus, three methods, no certified bounds.

| Mean over 30 days | A: TO-2022 carried over (branch) | | | B: TO-2023 verified (Rs 8.50, Rs 350/kVA) | | |
|---|---:|---:|---:|---:|---:|---:|
| | status quo | Q-Grid | best plan | status quo | Q-Grid | best plan |
| Bill, Rs/day (energy + monthly demand charge) | 177,512 | 179,032 | 178,022 | 177,694 | 179,552 | 178,144 |
| Bill vs status quo | – | **+0.8 %** | +0.2 % | – | **+1.0 %** | +0.2 % |
| Gap to best plan (planning objective incl. lost load) | 16.2 % | **9.1 %** | 0 | 16.8 % | **10.6 %** | 0 |
| Critical downtime, h/day (all days) | 0.26 | 0.20 | 0.00 | 0.26 | 0.18 | 0.00 |
| Critical downtime on the 3 outage days, h | 2.58 | **2.00** | 0.00 | 2.58 | **1.83** | 0.00 |
| Diesel on the 3 outage days, L/day | 373 | 354 | 389 | 373 | 390 | 389 |
| CO₂, kg/day | 14,030 | 13,967 | 14,032 | 14,030 | 13,992 | 14,032 |
| Highest daily peak, kVA | 1,194 | **1,452** | 1,105 | 1,194 | **1,452** | 1,105 |
| Feasible days | 30/30 | **29/30** | 30/30 | 30/30 | 30/30 | 30/30 |

What this says (both tariffs agree; the tariff choice moves bills by under Rs 700/day):

- **No everyday bill saving.** Q-Grid's bill is 0.8–1.0 % above the status quo; even the best possible plan is
  0.2 % above it, because it spends diesel to keep critical loads up during outages, where the status quo sheds them.
  The earlier "saves 3.3 %" came from the stand-in tariff and the 8× oversized solar, and no longer holds.
- **The gain is reliability.** On outage days Q-Grid cuts critical downtime from 2.58 h to 1.8–2.0 h, and it
  roughly halves the gap to the best plan (16–17 % → 9–11 %) without a central controller.
- **Two Q-Grid defects, traced to the run, not the method:**
  - a peak of 1,452 kVA (2023-01-19; also 2023-04-14 or 2023-09-19 above 1,300 kVA), above the assumed contract
    demand, which BESCOM charges at 2×; the status quo never exceeds 1,194 kVA.
  - one infeasible day under tariff A (2023-09-19).
  - **Cause:** CPU oversubscription. The quick runs used 22 workers on an Intel Core Ultra 9 275HX (8 performance + 16
    efficiency cores) while each HiGHS solve picks its own thread count. Each building MILP has a 5 s wall-clock limit;
    under that load a Q-Grid day took ~600 s instead of ~200 s alone, and time-limited solves returned poor plans.
    Re-run alone, Q-Grid on 2023-01-19 peaks at **1,055 kVA** (status quo 1,162 kVA), no battery charging at the peak.
  - **Remedy for the full benchmark:** 8 workers (one per performance core, like the earlier 9-worker Mac run), and
    a check that the high-peak days match their single-run values. Making the solves independent of machine load
    (a node limit instead of a wall-clock limit, or one HiGHS thread per solve) is the proper fix, after the event.

## Full benchmark: what it shows (28 Nov 2026)

`python scripts/run_bench_v3.py --workers=8`: 5 datasets × 30 days × 10 methods, the RVCE design rows and the
certified bounds; 1,650 runs + 150 bounds, no failures, 6,955 s. Files: `results/bench_v3/` (runs, bounds, daily,
summary, wilcoxon, `run_info.json`).

**Two checks before trusting it**

- **Feasibility audit.** 37 outage-day rows (0 in the committed run) were marked infeasible, among them the status quo
  and the best possible plan. Every one was a diesel run cut short because the grid came back: the planners already do
  this (backup-only diesel, `baselines/milp.py`, `qgrid/ablation/local.py`), but `check_feasibility` still demanded the
  full 1 h minimum. The audit now applies the planners' rule (`backend/qgrid/model.py`; test
  `test_feasibility_audit_allows_dg_run_cut_by_grid_return`). The 37 rows were re-run with `scripts/rerun_rows_v3.py`
  (215 s): all feasible; 35 have identical objectives, 2 Q-Grid rows differ (time-limited solves): BDG2 Fox 2017-11-30
  Rs 3,954,129 → 4,193,494 and BDG2 Bull 2017-10-28 (network failure) Rs 3,182,841 → 3,177,180. Both are logged under
  `reruns` in `run_info.json`.
- **CPU load.** The quick run's 1,452 kVA peak on 2023-01-19 is gone (Q-Grid 1,055 kVA, status quo 1,162). Q-Grid
  re-run alone on its three worst normal days reproduced the full-run numbers exactly (2023-02-24 gap 56.90 %, peak
  1,371 kVA; 2023-08-14 17.97 %; 2023-06-16 16.17 %), so the results below are not a machine-load artefact.

**RVCE, mean of 30 days** (3 with a synthetic outage; tariff TO-2022 / TO-2023; contract demand 1,300 kVA assumed)

| | Status quo | Per-building MPC | Central MPC | **Q-Grid** | Best possible plan |
|---|---:|---:|---:|---:|---:|
| Gap to best plan (incl. lost load) | 16.75 % | 9.17 % | 1.37 % | **8.37 %** | 0.00 % |
| Gap on the 27 normal days | 2.41 % | 0.34 % | 1.33 % | **7.43 %** | – |
| Gap, money only (no lost-load value) | 3.04 % | 0.30 % | 2.88 % | **9.62 %** | 1.54 % |
| Bill change vs status quo (all days) | – | −1.27 % | +0.92 % | **+0.86 %** | +0.20 % |
| Critical downtime per outage | 2.58 h | 2.58 h | 0.00 h | **0.92 h** | 0.00 h |
| Diesel per outage day | 373 L | 68 L | 396 L | **414 L** | 389 L |
| Highest monthly peak | 1,194 kVA | 1,136 kVA | 1,140 kVA | **1,371 kVA** | 1,105 kVA |

(Bill change: + = more expensive than the status quo.)

- **Reliability is the win.** In an outage Q-Grid cuts critical-load downtime from 2.58 h to 0.92 h (55 min), using
  41 L more diesel than the status quo to keep those loads up. Per-building MPC saves money but leaves critical loads
  dark as long as today.
- **Its average lead comes from the 3 outage days.** Per-building MPC is closer to the best plan on 27 of 30 days;
  the paired Wilcoxon p = 0.002 is in *its* favour day by day. The scorecard sentence now says so.
- **Normal days cost more.** Bill +0.43 % on normal days; monthly demand charge +Rs 41,261 at 1,000 kVA, +Rs 16,685 at
  1,300 kVA, +Rs 238 at 1,600 kVA. Main cause, a **defect**: on 2023-02-24 Q-Grid charges the (proposed) batteries at
  about 369 kW between 18:00 and 18:45, the dearest slot (Rs 9.65/kWh with ToD), pushing campus import to 1,302 kW
  (1,371 kVA, above the 1,300 kVA contract, billed at 2×); per-building MPC peaks at 941 kW and the status quo at 987 kW
  that day. Cause not yet found; candidates in `qgrid/ablation/engine.py` (~l.330–349): the per-building peak budgets
  from the ADMM import shares, or the 24 h window's terminal value (`DayData.term_value` = mean import price).
  Reproduce: `run_bench_v3.run_one("rvce", "2023-02-24", "qgrid", return_sched=True)` and look at `sched.p_bat[:, 72:76]`.
- **Network failure.** Central MPC loses 2.7 points of gap (1.37 → 4.06 %), Q-Grid 0.7 (8.37 → 9.08 %).
- **Other campuses.** Among methods without a central controller Q-Grid is closest on 1 of 5 (RVCE). Per-building MPC
  is closer on BDG2 Fox (8.69 vs 9.90 %), Bull (9.61 vs 9.79 %) and Cockatoo (10.28 vs 11.82 %); PSO on CU-BEMS
  (27.48 vs 27.66 %).
- **What no longer holds** from the pitch plan (old stand-in protocol): "0.76 % from the best plan", "best other
  method 21.7 %", "downtime halves 16 → 8 min a day", "closest on four of five", "3.5 vs 2.1 points", "within 1 % of a
  perfect central optimiser", "sells noon solar cheaply".

## d) Decisions needed

0. **Which build goes on the presenting laptop (28 Nov)?** The old portal (`harden`) matches Shoumik's pitch plan
   number for number but rests on a stand-in tariff and 3,974 kWp of solar. `real-data` has the verified tariff and
   RVCE's 500 kWp; its story is reliability in outages, with higher normal-day cost and the defect above. Every
   spoken number must match the build on screen.
10. **The evening-peak charging defect.** Fix it before claiming any cost result for Q-Grid; afterwards re-run the
   Q-Grid rows (about 300 rows, roughly 1–2 h on 8 workers) and regenerate. Not attempted overnight: it is an engine
   change the team should review.
1. ~~FY2023-24 tariff~~: **resolved 27 Nov** (lead: "Approve, TO-2023 rates"), committed in e4e144b.
2. **Export rate**: mark Rs 3.74 VERIFIED (KERC solar order 01.06.2023 p30) and commit the source PDFs? The branch
   git-ignores PDFs (SHA-256 only); Shoumik's copy commits them (≈ 25 MB in total).
3. **Campus labels**: upgrade solar, floor areas and diesel from "TEAM BRIEF" to the NAAC SSR / NAAC Cr 7.1.2
   sources with page numbers?
4. **Built-up area**: keep the reading that 67,721 m² excludes the 38,659 m² of hostels (campus 106,440 m²), or
   include them (67,721 m² in total)? Changes loads by about a third.
5. **Diesel**: "two generators of capacity 980 KVA": 980 kVA in total (2 × 490, current) or each?
6. **Contract demand**: keep 1,300 kVA as the base case and report 1,000 / 1,300 / 1,600 kVA, until RVCE's bill
   arrives?
7. ~~Full benchmark~~: **done 28 Nov** (8 workers); the oversubscription defects did not recur, the evening-peak
   charging defect (decision 10) did.
9. **Story**: the honest pitch on real data is reliability (critical downtime during outages, gap to the best plan
   without a central controller), not bill savings. Accept this framing for Part 2?
8. **My earlier branch `fix/real-data-prep`** (Shoumik's commits cherry-picked onto `product-modes`) is superseded by
   `real-data`; close it once the PDFs and page references above are carried over?
