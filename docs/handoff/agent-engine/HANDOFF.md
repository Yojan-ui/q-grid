# Agent B (engine, bugs, fairness): handoff

Branch `agent/engine` (from `real-data` @ 6de0bd2). Nothing has been merged or pushed. **No results were regenerated.**
Every committed number in `results/` and `docs/` still comes from the old protocol until the lead re-runs the scripts
listed at the end.

## Commits

| commit | what |
|---|---|
| 015a5be | `encoding="utf-8"` on every text `read_text` / `write_text` / `open` in `scripts/` (25 files, mechanical) |
| d462ec6 | Wilcoxon "wins / ties / losses" table: `display_name()` maps every method id to its own name, including the reference `optimum` and the 5 `design_*` ids. The old `NAMES.get(m, (REF[1],))` fallback showed every design variant as "Best possible plan" (15 such rows in the current `docs/benchmark_v3.md`). Test added |
| 833479a | `make_replay.attach_qgrid`: every named scenario gets a `qgrid_story`, not only the headline day (`headline: true` flag on that one). Without it, `frontend/src/lib/story.ts` swaps `runs.qgrid` for the older `runs.qgrid_v2` on the non-headline days |
| a72cfeb | Diesel-while-grid-up fix + regression tests (see below) |
| ab0b002 | Monthly-peak demand term in every planner's objective + fairness tests |
| 39bbd5b | Scorecard: monthly billing, gap on the planning objective + tests |

## Task 3: replay files
`impact.json`, `live.json`, `operate_session.json`, `data_status.json`, all 6 `sankey_*.json` and all 6 `scenario_*.json`
are present and git-tracked in both `results/replay/` and `frontend/public/replay/`, and the two folders list the same
files, so there was nothing to add. Only `scenario_outage_fest.json` (the headline day) has `qgrid_story`. This is fixed
in `make_replay.py`, but the files only change once **make replay** is re-run.

## Task 4: diesel while the grid is up
- **2023-06-20 is not in the committed results.** It is not an RVCE evaluation or scenario day, and no runs/bounds/replay
  file or commit mentions it (`git log -S`). I re-ran every main method on RVCE 2023-06-20 with `run_bench_v3.run_one`,
  plus the design methods `design_prototype_1h_binary`, `design_earlier_prototype` and `design_benders_exact`. With
  the committed code none of them runs diesel that day. I found two real causes, and they reproduce on that day:
  1. **Minimum on-time outlasting the outage.** `safety.dg_decision` forces the DG on while `0 < run < min_on` (4 slots
     at RVCE), whether or not the grid is up. The rule-based controller, the engine's `_rule_fallback` and the engine's
     apply step (`if s.dg_on and s.dg_run < min_on: on = True`) all relied on it. A DG started near the end of an outage
     kept running in parallel with the grid. Reproduced on 2023-06-20 with a 15-min outage at 18:00: the old rule-based
     controller ran 182 kW of diesel across grid-up slots.
  2. **Planner MILPs allowed DG output in grid-up slots** (`ablation/local.py`, `baselines/milp.py`). This is harmless at
     today's prices, but any term that makes grid import expensive turns it on. Once the peak term was added, the best
     possible plan on 2023-06-26 cut its peak to 1,084 kVA while its energy-side objective rose by about Rs 71k. That is
     consistent with diesel running alongside the grid (not measured directly). After the fix it reaches 1,395 kVA with
     0 L of diesel.
- **Fix:** the DG is backup-only. It is off in every grid-up slot, and its minimum on-time is cut short when the grid
  returns. This is applied in `b1_rule_based.py`, `engine._rule_fallback`, the engine's apply step, `LocalModel` (DG
  columns bounded to 0 when the grid is up; min-on rows truncated at the end of the outage, helper `outage_run_lengths`)
  and `baselines/milp.py` (the same rule, so the bounds and B4 stay consistent with `LocalModel`).
- **Tests** in `backend/tests/test_regressions.py`, all on RVCE 2023-06-20:
  - rule-based with a one-slot outage: the DG covers the outage and is 0 in every grid-up slot;
  - best plan with the peak term on, no outage: 0 diesel;
  - per-building MPC with the one-slot outage: 0 diesel with the grid up.
- **NOT fixed (outside my folders), same bug:** `backend/qgrid/agent.py:224` `apply_safe_default` drives **status quo**
  and makes the same `dg_decision(..., self.dg_run, True)` call. The one-line fix is
  `on = (not self.gridup[t]) and safety.dg_decision(self.dg, r > 0, self.dg_run, True)`. Please also check
  `operate/session.py:312` and `v2/mpc.py:340`.

## Task 5: monthly billing (settlement)
`backend/qgrid/ablation/demand.py`:
- `tariff_params(cfg, day, contract_kva="config")` reads `tariff_ht2c` and picks the order with
  `v2.tariff.order_for` when that exists. Otherwise it takes the order whose `valid_from`/`valid_to` contains the
  day, or else the latest order. Keys read: `demand_rs_kva_month`, `power_factor`, `billing_demand_floor_frac`,
  `excess_demand_multiplier`, `contract_demand_kva`. Without `tariff_ht2c` it falls back to `tariff_v2`
  (350 Rs/kVA/month, pf 0.95) and to `FALLBACK_FLOOR_FRAC = 0.85` / `FALLBACK_EXCESS_MULT = 2.0` (labelled constants),
  with **no contract demand**, so no floor and no excess. That is the state on this branch, because `config.yaml` has
  no `tariff_ht2c` yet.
- `monthly_charge(MD, p)`: billing demand = max(MD, floor × contract); charge = rate × billing + (excess − 1) × rate ×
  max(0, MD − contract).
- `monthly_settlement(df, params_for)` is the aggregation for a **sampled** year (2–3 seeded days per calendar month,
  11–12 months per dataset):
  - per (dataset, method, calendar month), MD = the highest sampled daily peak;
  - the month's charge is spread over the month's **calendar** days;
  - each sampled day gets `demand_share_rs = charge / days_in_month`, and `bill_rs = cost_rs (energy, per day) +
    demand_share_rs`.
- `scripts/write_bench_v3.py daily()` now uses this for `bill_rs`, so saving %, NPV and `write_impact.py` (which reads
  `daily.csv` `bill_rs`) follow automatically. The old 1/30-per-day figure is kept as `bill_prorata_rs`.
- **The contract demand applies to RVCE only.** BDG2 sites peak at about 17,000–27,000 kVA and CU-BEMS at about
  680 kVA, so a 1,300 kVA contract would be meaningless there. They are billed on MD with no floor or excess.
- **Trade-offs of this aggregation:**
  - it keeps Rs/day units, and the mean over sampled days estimates annual bill / 365;
  - each method is billed on its own monthly maximum;
  - the sampled MD can only **under**-estimate the true monthly maximum (2–3 of about 30 days), equally for all methods;
  - sharing the charge over the *sampled* days instead would turn one month's charge into 2–3 days' worth and inflate
    Rs/day about 10×;
  - simulating whole months would be exact but costs about 12× the benchmark.

## Task 6: the same monthly-peak term in every planner
Planning term, identical for all planners: rate × max(0, P − ref) + (excess − 1) × rate × max(0, P − contract), where:
- P = the campus peak kVA (sum of the buildings' grid imports / pf) over the horizon;
- ref = "the peak already set this month". Sampled days are independent, so this is the billing floor
  (0.85 × contract on RVCE), raised during the day to the campus peak already recorded today (main meter);
- without a contract (fallback, and the non-RVCE datasets) ref starts at 0. Every sampled day is then planned as if it
  could set the month's maximum, which is the strongest shaving incentive. This is an assumption the lead should
  accept or change.

| method | how the coupling is handled |
|---|---|
| best possible plan (`baselines/milp.py`, `b4_central_milp.solve(demand=)`) | exact campus peak variables |
| central MPC (`engine` `central=True` → `bounds._central(peak=)`) | exact campus peak columns/rows, rolling ref |
| per-building MPC (`share=False`) | per-building, per-slot budgets = static share × ref (share = building's mean-load share, offline; no communication) |
| Q-Grid (C1) | same budgets, but the shares are **re-agreed between the price rounds** from the buildings' planned imports (budget_i[h] = ref × imp_i[h] / Σ imp[h]); the campus import profile is obtained over the cable graph (flooding, counted as 2·lines·n messages per update); warm-started from the previous decision |
| C0 binary ADMM (design row) | static budgets |
| GA / PSO (`b2_ga_pso.solve(demand=)`, `common.simulate_building(peak=)`) | building's own peak above its static share, in the fitness |
| status quo / rule-based | not optimised, only settled |

- **Properties of the per-building budgets:** they sum to the campus allowance at every slot, so the per-building
  terms are ≥ the campus term, and equal to it when the buildings' peaks coincide. The decentralised methods therefore
  over-weight non-coincident peaks somewhat. This is the price of not having a coordinator, and it is the honest
  comparison.
- **Known wrinkle:** a building with zero mean load (the pump/tank zone) gets a static share of 0, so it pays the full
  rate on its own pump import.
- **Bounds** (`day_bounds(demand=)`): `opt_central`, `LB_mip` and `LB_lp` include the campus term. `LB_lag` stays
  energy-only, which is still a valid lower bound because the term is ≥ 0, but it is weaker.
- **Scorecard:** `run_bench_v3.run_one` writes the new columns `peak_import_kw`, `peak_kva_tariff`, `peak_term_rs`,
  `objective_plan_rs` (= objective + term at the day-start ref), `peak_priced` and `tariff_source`. `daily()` computes
  gap / certified gap / no-VoLL gap on `objective_plan_rs` when present, and on `objective_rs` for old runs. The
  "Same objective" protocol sentence switches on `peak_priced`. `--peak=0` reproduces the earlier protocol.
- **Note for the narrative:** the planning term counts the full monthly rate on each sampled day, but the bill counts it
  once a month. Gaps are therefore on the planning objective, while bills and savings are monthly.
- **Sanity run** on RVCE 2023-06-26 with the fallback tariff (ref 0, no contract). These are not results; do not
  publish them. Peak kVA without → with the term:

  | method | peak kVA without | peak kVA with |
  |---|---:|---:|
  | best plan | 1702 | 1395 |
  | GA | 1702 | 1559 |
  | PSO | 1726 | 1523 |
  | per-building MPC | 1702 | 1565 |
  | central MPC | 1717 | 1655 |
  | Q-Grid | 1702 | 1528 |

  All runs were feasible, with 0 L of diesel. Q-Grid took 82 s that day instead of 64 s. The best-plan MILP solves in
  about 1 s after the DG fix (129 s before it).

## Tests
`python -m pytest -q -p no:warnings`: **all pass** (full suite, run before each commit after the restart). New files:
- `backend/tests/test_regressions.py`: display names unique and correct; Wilcoxon names; the 2023-06-20 diesel tests.
  Uses RVCE processed data and skips without it.
- `backend/tests/test_engine_fairness.py`: SYNTHETIC two-building toy campus, labelled. With a flat price and no peak
  term nobody shaves; with the term each of Q-Grid, per-building MPC, central MPC, best plan, GA and PSO lowers the
  campus peak by more than 20 kVA. It also checks the peak-row structure and that today's recorded peak raises ref.
  Runs in about 40 s.
- `backend/tests/test_monthly_demand.py`: floor / excess / no-contract charges; a hand-made month (February 2023 with
  2 days, March 2023 with 1, two methods) equals the monthly billing by hand; `tariff_ht2c` reading and the fallback;
  the scorecard's `bill_rs` = energy + monthly share on a temp copy of `runs.csv` (committed results untouched).

## What the lead must re-run (after merging Agent A's `tariff_ht2c` and fixing `agent.py:224`)
1. `python scripts/run_bench_v3.py` (full benchmark; the runs **and** `bounds.csv` must be regenerated together,
   because both now carry the peak term).
2. `python scripts/write_bench_v3.py` → `daily/summary/wilcoxon.csv`, `docs/benchmark_v3.md`, `docs/scorecard.md`,
   `bench_v3.json` (with the fixed Wilcoxon names and monthly bill).
3. `python scripts/write_impact.py` (reads `bill_rs`).
4. `make replay` (`scripts/make_replay.py`): `qgrid_story` on every scenario. Then the dependants: `make_sankey.py`,
   `data_status.py`, `make_live.py`, `record_operate.py`, `make_manifest.py` and `write_results_md.py`, as in
   `scripts/refresh_all.sh`.
5. Optional: `scripts/run_ablation.py` and `run_wear_variant.py` do not pass `demand`, so they still use the earlier
   protocol. Decide whether to align them.

## Open questions
- ref = 0 without a contract demand (non-RVCE and fallback): keep it, or plan against e.g. the status-quo monthly peak?
- Contract-demand sweep (`contract_demand_sweep` [1000, 1300, 1600]): `tariff_params(..., contract_kva=x)` supports
  it, but no script runs the sweep yet.
- Should the rest of the codebase also treat the DG as backup-only? That covers `agent.py` (status quo, live agent),
  `operate/session.py` and `v2/`, which are not my folders.
