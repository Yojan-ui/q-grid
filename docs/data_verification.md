# Data verification: tariff, CO2 and campus figures

Every tariff, CO2 and campus value the model uses, where it comes from and whether it has been checked against an
official document. Status: **VERIFIED** = read from the official PDF at the page given · **PENDING** = official
document not in the repo, value unverified · **TEAM BRIEF** = figure from the team's brief, no document yet ·
**ASSUMPTION** = modelling choice, not data.

Page numbers: printed page [PDF page]. The tariff PDFs are scans; values were read from the rendered page images.
Files, URLs and SHA-256: `data/SOURCES.md`. Config keys: `config.yaml` `tariff_ht2c`, `co2`, `campus.*`.

Abbreviations: **TO-2022** = KERC Tariff Order 2022 (BESCOM), dated 04.04.2022, Annexure-5 "Electricity Tariff-2023",
effective from the first meter-reading date on or after 01.04.2022, file `data/raw/tariff/bescom_tariff_2023.pdf`.
**TO-2023** = KERC Tariff Order 2023 (BESCOM), dated 12.05.2023, effective from the first meter-reading date on or after
01.04.2023 (date and effect from the BESCOM public notice `bescom_tariff_order_2023_highlights.pdf`; the rate schedule
itself is missing).

## 1. Flags for the lead

1. **Energy charge, Rs 8.50 vs ~Rs 7.5-7.9/kWh: neither matches FY2022-23.** TO-2022 HT-2(c)(ii) charges 825 paise
   per unit for the first one lakh units in a month and 865 paise for the balance (p.412 [38]). The ~7.5-7.9 figure in
   secondary sources is close to HT-2(c)(i) (government/aided institutions, hostels of all educational institutions):
   725 / 765 paise (p.411 [37]). **Resolved by lead decision:** the brief's 8.50 is dropped. Both orders use the
   TO-2022 slabs; for FY2023-24 they are carried over (status `PENDING_CARRIED_OVER`, "TO-2022 values carried over
   until the TO-2023 rate schedule is obtained"), not verified. `energy_rs_kwh` = 8.65 (the balance-units slab, i.e.
   the marginal rate at campus scale) and `monthly_bill` applies both slabs exactly. Open: obtain TO-2023 to confirm
   the FY2023-24 rates.
2. **Demand charge: Rs 265/kVA/month in TO-2022, not Rs 350.** Resolved by lead decision: 265 for both orders
   (FY2023-24 carried over, `PENDING_CARRIED_OVER`).
3. **ToD threshold 500 kVA:** not found in TO-2022, which applies ToD to HT-2(a), (b) and (c) without a demand
   threshold (p.412 [38]) and says the evening +100 paise applies to "all the HT consumers" (p.408 [34], note 11).
   The FY2022-23 order therefore sets `tod_min_contract_kva: 0`; the 500 kVA rule (brief) applies to FY2023-24 only.
   With the default contract demand (1,300 kVA) this makes no difference.
4. **Category:** HT-2(c)(i) covers government/local-body and aided institutions and **hostels of all educational
   institutions** (p.411 [37]); residential quarters on a bulk HT supply must be metered separately and billed at HT-4
   (p.406 [32] note 4; p.409 [35]). If RVCE's hostels or staff quarters are separately metered, part of the campus is not
   on HT-2(c)(ii). Needs an RVCE BESCOM bill.
5. **Built-up area and hostels:** the brief gives 67,721 m² built-up and 38,659 m² of boys' hostels but does not say
   whether the first includes the second. Default `built_up_includes_hostels: false` (campus floor area 106,380 m² +
   60 m² pump house); set `true` for 67,721 m² in total.

## 2. Tariff (`tariff_ht2c`)

| Value | Config key | Unit | Source document | Page | Status |
|---|---|---|---|---|---|
| Tariff order switch on 1 Apr 2023 | `orders[*].valid_from/valid_to` | date | TO-2022 cover (effective 01.04.2022); BESCOM notice for TO-2023 (dated 12.05.2023, effective 01.04.2023) | p.375 [1]; notice p.1 | VERIFIED |
| FY2022-23 energy charge, first 1 lakh units/month | `orders[0].energy_slabs[0]` | 8.25 Rs/kWh | TO-2022, HT-2(c)(ii) rate schedule | p.412 [38] | VERIFIED |
| FY2022-23 energy charge, balance units | `orders[0].energy_slabs[1]`, `orders[0].energy_rs_kwh` | 8.65 Rs/kWh | TO-2022, HT-2(c)(ii) | p.412 [38] | VERIFIED |
| FY2022-23 demand charge | `orders[0].demand_rs_kva_month` | 265 Rs/kVA/month | TO-2022, HT-2(c)(ii) | p.412 [38] | VERIFIED |
| FY2023-24 energy charge | `orders[1].energy_slabs`, `orders[1].energy_rs_kwh` | 8.25 / 8.65 Rs/kWh | TO-2022 values carried over (lead decision); TO-2023 rate schedule missing | TO-2022 p.412 [38] | PENDING_CARRIED_OVER |
| FY2023-24 demand charge | `orders[1].demand_rs_kva_month` | 265 Rs/kVA/month | TO-2022 value carried over (lead decision); TO-2023 missing | TO-2022 p.412 [38] | PENDING_CARRIED_OVER |
| ToD months | `tod.months` | Dec-Jun (none Jul-Nov) | TO-2022, ToD table for HT-2(a)/(b)/(c) | p.412 [38] | VERIFIED (FY2022-23); FY2023-24 PENDING |
| ToD peak 18-22 h | `tod.peak_hours`, `tod.peak_adder_rs_kwh` | +1.00 Rs/kWh | TO-2022 | p.412 [38]; p.408 [34] note 11 | VERIFIED (FY2022-23) |
| ToD off-peak 22-06 h | `tod.offpeak_hours`, `tod.offpeak_adder_rs_kwh` | -1.00 Rs/kWh | TO-2022 (not with the Special Incentive Scheme, note 10) | p.412 [38]; p.408 [34] | VERIFIED (FY2022-23) |
| ToD only at contract demand >= 500 kVA | `tod.min_contract_kva` | 500 kVA | team brief; not in TO-2022 | – | TEAM BRIEF (FY2023-24 only) |
| No ToD threshold in FY2022-23 | `orders[0].tod_min_contract_kva` | 0 kVA | TO-2022 | p.412 [38]; p.408 [34] | VERIFIED |
| Billing demand = max(recorded MD, 85 % CD) | `billing_demand_floor_frac` | 0.85 | TO-2022, conditions for HT billing, 1(A) | p.404 [30] | VERIFIED |
| Excess over CD at 2x | `excess_demand_multiplier` | 2.0 | TO-2022, 1(D) (Section 126(6) EA 2003) | p.404 [30] | VERIFIED |
| Billing demand rounding (>= 0.5 kVA up, < 0.5 ignored) | `round_billing_demand` | – | TO-2022, 1(G) | p.405 [31] | VERIFIED |
| Power factor for kW -> kVA | `power_factor` | 0.95 | modelling choice (TO-2022 specifies PF >= 0.90, 3 paise/unit surcharge per 0.01 below, p.405 [31]) | – | ASSUMPTION |
| Solar export rate | `export_rs_kwh` | 3.74 Rs/kWh | team brief; KERC rooftop solar tariff order missing | – | PENDING (TEAM BRIEF) |
| Contract demand | `contract_demand_kva` | 1,300 kVA | team brief / lead; RVCE bill missing | – | TEAM BRIEF |
| Contract demand sweep | `contract_demand_sweep` | 1,000 / 1,300 / 1,600 kVA | lead's brief (sensitivity) | – | ASSUMPTION |
| Billing month = calendar month | `billing_month` | – | modelling choice (BESCOM bills meter-reading to meter-reading) | – | ASSUMPTION |
| Not modelled: electricity tax 9 % ad valorem | `not_modelled` | – | BESCOM "Other tariff related issues FY-23" (GoK notification 24, 19.07.2018) | p.3 | VERIFIED (not applied) |
| Not modelled: FY-23 cross-subsidy surcharge HT-2(c)(ii) | – | 2.15 Rs/kWh (open access only) | same | p.2 | VERIFIED (not applicable) |

`tariff_ht2c.status` stays **PENDING** because the FY2023-24 order, the export rate and the ToD threshold are not
verified. It may become REAL only when every value above is VERIFIED.

## 3. CO2 (`co2`)

| Value | Config key | Unit | Source document | Page | Status |
|---|---|---|---|---|---|
| Grid weighted-average emission factor FY2023-24 | `co2.tco2_per_mwh`, `co2.standin_tco2_per_mwh`, `co2.by_fy["2023-24"]` | 0.727 tCO2/MWh | CEA CO2 Baseline Database User Guide v20.0 (Dec 2024), Table S | p.1 [4]; calculation p.12 [15] | VERIFIED |
| same, after final captive data | – | 0.727 tCO2/MWh | CEA User Guide v21.0 (Nov 2025), Annexure-I | p.21 [27] | VERIFIED |
| FY2022-23 (Jan-Mar of the model year) | `co2.by_fy["2022-23"]` | 0.716 tCO2/MWh | CEA User Guide v21.0, Annexure-I (also v19.0 summary) | p.21 [27] | VERIFIED (stored, not yet used by the code) |

## 4. Campus (`campus.*`)

| Value | Config key | Unit | Source | Status |
|---|---|---|---|---|
| Existing PV: 21 roofs, 1,564 modules x 320 Wp = 500.48 kWp | `campus.pv_existing` | kWp | team brief, RVCE estate data pending | TEAM BRIEF |
| PV split over zones by footprint x `pv_roof` | `campus.pv_existing.allocation` | – | the 21 roofs are not identified | ASSUMPTION |
| Built-up area of RVCE's buildings | `campus.facts.built_up_m2` | 67,721 m² | team brief, RVCE estate data pending | TEAM BRIEF |
| Built-up area excludes hostels | `campus.facts.built_up_includes_hostels` | false | not stated in the brief | ASSUMPTION (open question) |
| Boys' hostels floor area | `campus.facts.boys_hostels_m2` | 38,659 m² | team brief, RVCE estate data pending | TEAM BRIEF |
| Boys' hostel beds | `campus.facts.boys_hostel_beds` | 1,450 | team brief (metadata; loads remain floor area x EPI) | TEAM BRIEF |
| DG total 980 kVA in two sets | `campus.dg_sets.total_kva`, `.sets` | kVA | team brief, RVCE estate data pending | TEAM BRIEF |
| DG split 490 + 490 kVA, hosts hostels / admin, zones each set backs | `campus.dg_sets.sets[*].kva/host/backs` | – | not in the brief | ASSUMPTION |
| DG kW = kVA x 0.8 (392 kW per set) | `campus.dg_sets.rated_pf`, zone `dg.kw` | – | genset rating convention | ASSUMPTION |
| Asset status | `campus.asset_status` | pv EXISTING, dg EXISTING, battery PROPOSED, ev PROPOSED, cables PROPOSED | team brief | TEAM BRIEF |
| Battery sizes per zone | `campus.zones.*.battery` | kWh / kW | modelling choice; batteries are PROPOSED | ASSUMPTION |
| OSM buildings removed (not RVCE's) | `campus.osm_exclude` | 4 buildings, 7,911.6 m² footprint | OSM names "RVU ..." (RV University); list in data/SOURCES.md | ASSUMPTION based on OSM names |
| Non-hostel floor-area scale factor | computed | 0.584 | 67,721 m² / OSM floor area of the kept non-hostel buildings (115,946 m²) | derived |

Result of the rescale on the committed OSM layout (`data/processed/campus.json`):

| Zone | footprint m² | floor m² | PV kWp | DG kW |
|---|---:|---:|---:|---:|
| academic | 22,385 | 40,068 | 272.2 | – |
| heavy_labs | 9,035 | 15,573 | 109.9 | – |
| hostels | 2,879 | 38,659 | 35.0 | 392 |
| library | 2,788 | 6,512 | 33.9 | – |
| canteen | 1,923 | 3,013 | 23.4 | – |
| admin | 792 | 1,388 | 9.6 | 392 |
| server_room | 645 | 753 | 7.8 | – |
| health_centre | 706 | 413 | 8.6 | – |
| pumping_station (virtual) | 60 | 60 | 0.0 | – |
| **total** | | **106,440** | **500.48** | **784** |

With these floor areas the BDG2-shaped loads total about 7.56 GWh/yr with a campus peak near 1,166 kW (about 1,227 kVA
at pf 0.95), down from 12.29 GWh/yr and 1,977 kW before the rescale. Both are model outputs (floor area x EPI
ASSUMPTION), not measurements.

## 5. Missing documents

| Document | Issuing body | Order / date | Where to get it | Expected file |
|---|---|---|---|---|
| Tariff Order 2023 (BESCOM), Annexure "Electricity Tariff-2024" (rate schedule incl. HT-2(c)(ii), ToD, billing conditions) | KERC | dated 12.05.2023, FY2023-24 | kerc.karnataka.gov.in (Tariff Orders, 2023, BESCOM); BESCOM's tariff page lists only an xlsx for 2024 | `data/raw/tariff/bescom_tariff_2024.pdf` |
| Order fixing the rooftop solar / net-metering export tariff applicable to RVCE's PV (source of Rs 3.74/kWh) | KERC | not known (generic RE tariff order for solar rooftop; RVCE's PPA/commissioning date decides which) | kerc.karnataka.gov.in (Generic tariff orders); RVCE's BESCOM net-metering agreement | `data/raw/tariff/kerc_solar_rooftop_tariff_order.pdf` |
| One RVCE BESCOM HT bill (2023) | BESCOM / RVCE estate office | – | RVCE estate office | `data/raw/rvce_bills.csv` + scan (tariff category, contract demand, recorded MD, kWh) |
| RVCE estate data: building list with built-up areas, PV roofs, DG sets and the loads they back | RVCE | – | RVCE estate office | `data/raw/rvce_estate.xlsx` (proposed) |
| Fuel-cost adjustment orders for BESCOM 2023 (if FAC is to be modelled) | KERC | quarterly | kerc.karnataka.gov.in FAC orders | `data/raw/tariff/fac_2023/` |
