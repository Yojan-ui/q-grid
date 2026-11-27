# Handoff: Agent A (data and model), branch `agent/data`

Base: `real-data` (6de0bd2). Nothing merged or pushed.

## Main findings (read these first)

I got official PDFs (BESCOM's tariff page and CEA's report API; the KERC site failed TLS verification) and read the
values from the pages. Two of the brief's tariff numbers **disagree with the official FY2022-23 order**:

| Item | Team brief | KERC Tariff Order 2022 (BESCOM), HT-2(c)(ii), effective 1 Apr 2022 | Where |
|---|---|---|---|
| Energy charge | Rs 8.50/kWh (secondary sources ~7.5-7.9) | **825 paise for the first 1 lakh units/month, 865 paise for the balance** | printed p.412 [PDF p.38] |
| Demand charge | Rs 350/kVA/month | **Rs 265/kVA/month** | p.412 [38] |
| ToD | Dec-Jun +1.00 (18-22 h) / -1.00 (22-06 h), none Jul-Nov | same | p.412 [38], p.408 [34] |
| ToD only at >= 500 kVA | yes | **no threshold in TO-2022** (ToD applies to HT-2(a)/(b)/(c); the peak adder to "all the HT consumers") | p.412 [38], p.408 [34] note 11 |
| Billing demand = max(MD, 85 % CD) | yes | same | p.404 [30] |
| Excess over CD at 2x | yes | same | p.404 [30] |
| CO2 factor | 0.727 tCO2/MWh | **0.727 VERIFIED** for FY2023-24 (CEA User Guide v20.0 Table S, p.1 [4]; unchanged in v21.0 Annexure-I, p.21 [27]); FY2022-23 = 0.716 | CEA PDFs |

The "~7.5-7.9" secondary figure is close to **HT-2(c)(i)** (government/aided institutions and hostels of all
educational institutions: 725 / 765 paise, p.411 [37]). The FY2023-24 order (KERC TO-2023, dated 12.05.2023) rate
schedule was **not** obtainable, so FY2023-24 keeps the brief's 8.50 and 350, labelled PENDING. I did not pick between
8.50 and 7.5-7.9: FY2022-23 uses the verified slabs, FY2023-24 uses the brief value with a flag. Details:
`docs/data_verification.md`.

## Changes

1. **Tariff module** `backend/qgrid/v2/tariff.py`: `settle_v2` / `demand_params` unchanged (same signature and output).
   New pure functions:
   - `ht2c_params(cfg) -> dict`
   - `order_for(cfg, date) -> dict` (the order dict from config; switches on 2023-04-01; raises outside the orders)
   - `energy_price_slots(cfg, date, n_slots=96, contract_kva=None) -> np.ndarray` = order `energy_rs_kwh` + ToD adder
     (by month and hour, only if contract demand >= threshold; the threshold is the order's `tod_min_contract_kva`, or
     `tod.min_contract_kva` when that is null)
   - `tod_adder_slots(cfg, date, n_slots=96, contract_kva=None)`, `tod_applies(cfg, date, contract_kva=None)`,
     `slab_energy_rs(order, kwh)` (helpers)
   - `monthly_bill(cfg, import_kw, export_kw=None, contract_kva=None, dates=None, pf=None) -> dict`: inputs are
     `{date: array}` or a 2-D array (days x slots) plus `dates`; all days in one calendar month. Returns `energy_rs`
     (slab energy + ToD), `export_credit_rs`, `recorded_max_kva`, `billing_demand_kva`, `demand_rs`, `excess_rs`,
     `total_rs`, `order` (the dict), plus `energy_base_rs`, `tod_rs`, `import_kwh`, `export_kwh`, `excess_kva`,
     `peak_import_kw`, `order_status`, `tariff_status`.
     `total_rs = energy_rs + demand_rs + excess_rs - export_credit_rs`; `demand_rs = rate x min(billing, CD)`;
     `excess_rs = 2 x rate x max(MD - CD, 0)`; MD = max slot import kW / pf, rounded half-up to whole kVA (TO-2022
     p.405 cond. 1(G); switch `round_billing_demand`). Electricity tax 9 %, FAC and PF surcharge are not modelled.
   - Note for Agent B: `energy_rs_kwh` of the FY2022-23 order is 8.65 (the balance-units slab = marginal rate, since
     campus import is far above 1 lakh units/month); `monthly_bill` applies both slabs exactly.
2. **config.yaml**
   - new `tariff_ht2c` section (keys below), `status: PENDING`.
   - `co2`: `status: VERIFIED`, `tco2_per_mwh: 0.727`, `by_fy`, `source`; kept `standin_tco2_per_mwh` (0.727) because
     `qgrid/data.py` reads that key.
   - campus rescale: `campus.rescale`, `campus.asset_status`, `campus.facts`, `campus.pv_existing`, `campus.dg_sets`,
     `campus.osm_exclude`; zone DGs changed to `hostels.dg.kw: 392` and `admin.dg.kw: 392` (was 100 / 200) so that
     `load_campus()` matches the two 490 kVA sets x 0.8.
3. **Campus rescale** `backend/qgrid/v2/campus_scale.py` (new, pure functions): `rescale_layout(cfg, layout)` drops the
   4 RV University buildings (OSM ids in config and in data/SOURCES.md), sets hostels floor area to 38,659 m², scales
   the other OSM zones to 67,721 m² in total, spreads 500.48 kWp over zones by footprint x `pv_roof`, and records all this
   under `layout["rescale"]` (idempotent). `apply_dg_sets(cfg)` writes zone `dg` entries from `campus.dg_sets`
   (move a set by changing its `host`). `asset_status(cfg)`, `dg_kw(cfg)`, `pv_total_kwp(cfg)`, `enabled(cfg)`.
4. **`backend/qgrid/datasets.py`**: `build("rvce")` applies the rescale when `campus.rescale.enabled` (default true):
   campus from `load_campus(apply_dg_sets(cfg), rescaled layout)`, PV series recomputed per zone from the new kWp,
   loads rebuilt with `qgrid.data.build_zone_loads` on the new floor areas (needs BDG2 raw files; raises otherwise),
   `meta.campus_rescale` and `meta.data_status.campus_assets` added. The non-RVCE sites' meta `co2.status` now reads
   `cfg.co2.status`.
   Effect on the RVCE model: PV 3,974 -> 500.48 kWp; floor area 156,588 -> 106,440 m²; annual load 12.29 -> 7.56 GWh;
   campus peak load 1,977 -> 1,166 kW (about 1,227 kVA at pf 0.95, so CD 1,300 kVA sits just above it).
5. **Data**: `data/raw/tariff/` (3 PDFs) and `data/raw/cea/` (v20.0, v21.0 PDFs) fetched with SHA-256 in
   `data/SOURCES.md`; PDFs are git-ignored like all raw data (re-fetch from the URLs); `data/raw/cea/emission_factor.yaml`
   force-added (makes `load_co2_factor` report REAL when a CEA PDF is present).
6. **Docs**: `docs/data_verification.md` (every value, unit, source, page, status; missing PDFs), `data/SOURCES.md`.

## Files touched
- `backend/qgrid/v2/tariff.py` (extended), `backend/qgrid/v2/campus_scale.py` (new)
- `backend/qgrid/datasets.py`
- `config.yaml`
- `backend/tests/test_tariff_ht2c.py` (new), `backend/tests/test_campus_rescale.py` (new)
- `data/SOURCES.md`, `data/raw/cea/emission_factor.yaml` (new, force-added)
- `docs/data_verification.md` (new), `docs/handoff/agent-data/HANDOFF.md` (this file)

## Tests
Command: `python -m pytest -q -p no:warnings` (conda env qgrid). For the run I copied the processed parquet files and
the BDG2 / NASA POWER raw folders from the main checkout into this worktree's git-ignored `data/` so the
data-dependent tests (test_v2, test_operate, the dataset test) run too, instead of skipping.
- `backend/tests/test_tariff_ht2c.py`: 8 tests (hand-computed January 2023 bill matched to the rupee:
  Rs 2,792,831.25; order switch 31 Mar / 1 Apr 2023; ToD Dec-Jun only; no ToD below 500 kVA (FY2023-24) and the
  FY2022-23 no-threshold rule; 85 % floor; excess at 2x; input forms). Pass.
- `backend/tests/test_campus_rescale.py`: 7 tests. Pass.
- Full suite: **91 passed, 0 skipped, 0 failed** (with the copied data). Without the data copy (clean worktree)
  the earlier run had all non-data tests passing and the data tests skipping, as on `real-data`.
- Not run (per instructions): `scripts/run_bench_v3.py`, `make replay`. results/*.csv are therefore NOT regenerated
  for the new campus or tariff; every headline number must be re-run by the lead after Agent B's settlement change.

## Open questions for the lead
1. Energy and demand charges: accept TO-2022's verified 8.25/8.65 slabs and Rs 265 for FY2022-23? For FY2023-24 we need
   the TO-2023 rate schedule ("Electricity Tariff-2024", KERC, dated 12.05.2023); until then 8.50 / 350 are unverified.
2. Is RVCE billed under HT-2(c)(ii) (private) or HT-2(c)(i) (aided)? Are hostels / staff quarters separately metered
   (HT-2(c)(i) / HT-4)? One BESCOM bill answers this and the contract demand.
3. Does the 67,721 m² built-up area include the 38,659 m² of hostels? (`campus.facts.built_up_includes_hostels`.)
4. DG split (490 + 490 kVA assumed) and which buildings each set actually backs.
5. Source of the Rs 3.74/kWh export rate (which KERC solar order / RVCE's net-metering agreement).
6. Should the RVCE PDFs be committed (about 3.4 MB), or stay git-ignored with SHA-256 as now?

## Changes needed outside my folders (not made)
1. `backend/qgrid/campus.py` `build_layout`: before writing `data/processed/campus.json`, apply
   `from .v2.campus_scale import rescale_layout, enabled` -> `if enabled(cfg): out = rescale_layout(cfg, out)`. Then
   `make data` rebuilds pv/load parquet from the rescaled layout and `load_campus()` (API, replay, operate, test_v2)
   sees the same campus as `datasets.build("rvce")`; the datasets path then becomes a no-op (idempotent). Today
   `load_campus()` without arguments still uses the old OSM PV (3,974 kWp) and floor areas, with the new DG sizes.
2. `backend/qgrid/data.py` `load_co2_factor`: report `cfg["co2"]["status"]` (VERIFIED) instead of hard-coded PENDING
   when the PDF is absent; optionally use `co2.by_fy` (0.716 before 1 Apr 2023, 0.727 after).
3. Settlement (Agent B): replace `settle_v2`'s 1/30-per-day demand charge with `monthly_bill` per calendar month;
   per-slot optimiser prices from `energy_price_slots`; contract-demand sweep from `tariff_ht2c.contract_demand_sweep`.
4. `data.build_prices` scenario A and `datasets.py` non-RVCE sites still use the `prices.A` stand-in (8.00 base,
   +1.00 06-10 h). Switch them to `energy_price_slots` if the lead wants one tariff everywhere.
5. Frontend 3D campus draws polygons from `campus.json`, so the RVU blocks still appear until item 1 is done.

## Config keys created
```
tariff_ht2c.status | category | category_note
tariff_ht2c.orders[].valid_from | valid_to | energy_rs_kwh | energy_slabs[{upto_kwh, rs_kwh}] | demand_rs_kva_month
                     | tod_min_contract_kva | source | file | page | status
tariff_ht2c.tod.months | peak_hours | peak_adder_rs_kwh | offpeak_hours | offpeak_adder_rs_kwh | min_contract_kva
tariff_ht2c.export_rs_kwh | billing_demand_floor_frac | excess_demand_multiplier | round_billing_demand
tariff_ht2c.power_factor | contract_demand_kva | contract_demand_sweep | billing_month | not_modelled
co2.tco2_per_mwh | co2.source | co2.by_fy   (co2.status changed to VERIFIED; co2.standin_* kept)
campus.rescale.enabled
campus.asset_status.{pv, dg, battery, ev, cables}
campus.facts.{status, source, built_up_m2, built_up_includes_hostels, hostel_zone, boys_hostels_m2, boys_hostel_beds}
campus.pv_existing.{status, source, roofs, modules, module_wp, total_kwp, allocation}
campus.dg_sets.{status, source, total_kva, rated_pf, operating{min_load_frac, min_on_slots}, sets[{name, kva, host, backs}]}
campus.osm_exclude[{osm_id, name, reason}]
```
