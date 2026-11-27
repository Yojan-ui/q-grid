# Data sources

Status legend: **REAL** = official/primary data in `data/raw/` and used for results ·
**PENDING** = file not yet obtained; a clearly labelled STAND-IN keeps the pipeline runnable and
**no stand-in value is ever presented as a headline result**. After adding the missing files run
`scripts/refresh_all.sh`.

| Dataset | Status | Used for | Raw file(s) |
|---|---|---|---|
| NASA POWER hourly (ALLSKY_SFC_SW_DWN, T2M), 12.92N 77.50E, 2023 | **REAL** | PV output, sun position | `data/raw/nasa_power/bengaluru_2023_hourly.json` |
| NASA POWER hourly clear-sky (CLRSKY_SFC_SW_DWN), same site, 2023 | **REAL** | v2 solar forecast (clear-sky envelope) | `data/raw/nasa_power/bengaluru_2023_hourly_clearsky.json` |
| Building Data Genome Project 2 (BDG2): hourly electricity meters, 1,578 non-residential buildings, 2016-17 | **REAL** | zone load shapes (7 of 9 zones) | `data/raw/bdg2/electricity_cleaned.csv`, `metadata.csv`, `LICENSE` |
| Ausgrid Solar Home Electricity Data 2012-13 (half-hourly, 300 homes) | REAL, **superseded by BDG2** (used only if `loads.source: templates`) | hostel load shape (v1) | `data/raw/ausgrid/Solar home 2012-2013.csv` (+ archive zip, notes PDF) |
| BESCOM HT educational tariff with ToD + KERC solar export rate | **PENDING** (stand-in, scenario A) | price scenario A (headline) | `data/raw/tariff/` |
| KERC Tariff Order 2022 (BESCOM) HT-2(c)(ii), FY2022-23: energy slabs, demand charge, ToD, billing-demand rules | **VERIFIED** (PDF pages cited) | `tariff_ht2c` FY2022-23 order | `data/raw/tariff/bescom_tariff_2023.pdf` |
| KERC Tariff Order 2023 (BESCOM) HT-2(c)(ii), FY2023-24 rate schedule | **PENDING** (PDF missing; team-brief values) | `tariff_ht2c` FY2023-24 order | expected `data/raw/tariff/bescom_tariff_2024.pdf` |
| KERC rooftop solar export tariff (Rs 3.74/kWh) | **PENDING** (team brief) | `tariff_ht2c.export_rs_kwh` | expected `data/raw/tariff/kerc_solar_rooftop_tariff_order.pdf` |
| IEX Day-Ahead Market 15-min MCP, 2023 | **PENDING** | price scenario B | `data/raw/iex/` |
| CEA CO2 Baseline Database (grid weighted-average emission factor) | **REAL** (0.727 tCO2/MWh, FY2023-24) | CO2 accounting | `data/raw/cea/CEA_CO2_Baseline_User_Guide_v20.0.pdf`, `v21.0.pdf`, `emission_factor.yaml` |
| OpenStreetMap: RVCE campus outline + building footprints | **REAL** | zones, roof area → PV kWp, tie-line layout, 3D campus | `data/raw/osm_rvce.json`, `osm_rvce.geojson` |
| RVCE estate figures (500.48 kWp PV on 21 roofs, 67,721 m² built-up, boys' hostels 38,659 m² / 1,450 beds, DG 980 kVA in two sets) | **TEAM BRIEF** (RVCE estate data pending) | campus rescale (`config.yaml campus.facts / pv_existing / dg_sets`) | none (no document) |
| RVCE academic calendar | **PENDING** (fest dates sourced) | day types / scenario dates | `data/raw/rvce_calendar.csv` (optional) |
| RVCE BESCOM bills / meter data | **PENDING RVCE DATA** | campus load totals | `data/raw/rvce_bills.csv` (optional) |
| Faculty lab schedule | **TEMPLATE** | lab loads, critical labs | `data/raw/lab_schedule.csv` |

## NASA POWER — REAL
- URL: `https://power.larc.nasa.gov/api/temporal/hourly/point?parameters=ALLSKY_SFC_SW_DWN,T2M&community=RE&longitude=77.5&latitude=12.92&start=20230101&end=20231231&format=JSON&time-standard=LST`
- Fetched: 2026-11-21 by `scripts/fetch_data.py` (timestamp stored inside the JSON under `_qgrid_fetch`).
- Licence: NASA POWER data are freely available without restriction (NASA open data policy); cite
  "NASA Langley Research Center POWER Project".
- Processing: hourly means in local solar time repeated to 4 x 15-min slots (energy preserving);
  PV = kWp · G/1000 · (1 + γ(T_cell − 25)) · derate, T_cell = T_air + (NOCT − 20)/800 · G
  (γ = −0.4 %/°C, NOCT 45 °C, derate 0.86 — config.yaml).

## NASA POWER clear-sky — REAL
- URL: `https://power.larc.nasa.gov/api/temporal/hourly/point?parameters=CLRSKY_SFC_SW_DWN&community=RE&longitude=77.5&latitude=12.92&start=20230101&end=20231231&format=JSON&time-standard=LST`
- Fetched: 2026-11-22 by `scripts/fetch_data.py` (`fetch_nasa_clearsky`; timestamp inside the JSON under `_qgrid_fetch`).
- Licence: as NASA POWER above.
- Use: the v2 rolling-horizon optimiser forecasts PV as clear-sky PV x a clearness index (persistence of the
  last observed hour, blended towards yesterday's daily clearness for longer lead times). The forecast only
  uses data up to the decision time; its error against the actual (ALLSKY-based) PV is reported.

## Building Data Genome Project 2 (BDG2) — REAL
- Paper: Miller, C., Kathirgamanathan, A., Picchetti, B. et al. "The Building Data Genome Project 2, energy meter data
  from the ASHRAE Great Energy Predictor III competition." *Scientific Data* 7, 368 (2020). Repository
  `https://github.com/buds-lab/building-data-genome-project-2` (Zenodo record 3887306).
- Files (Git LFS media URLs, fetched 2026-11-22 by `scripts/fetch_data.py`, `fetch_bdg2`):
  `data/meters/cleaned/electricity_cleaned.csv` (174,977,911 bytes, SHA-256 b6ffc9b4dfcefe5c753594730a08ae822b0d50fec6815abb8f185591e6c630a3),
  `data/metadata/metadata.csv` (272,024 bytes, SHA-256 992d0b29f24f96ad4332bc4dbb534b7bdd7dd2689aad093f94e93068ecddca02), `LICENSE`.
- Licence: **Creative Commons Attribution-ShareAlike 4.0** (`data/raw/bdg2/LICENSE`). Derived zone load profiles in
  `data/processed/load.parquet` are shared under the same licence; attribution as above.
- Mapping (config.yaml `bdg2.zones`; buildings kept if >= 90 % of hours present, each normalised by its own mean,
  median across buildings per hour):

  | Zone | BDG2 primary use / sub use | buildings |
  |---|---|---:|
  | academic | Education / College Classroom, Academic, Classroom | 130 |
  | heavy_labs | Education / College Laboratory, Research | 124 |
  | hostels | Lodging/residential / Dormitory, Residence Hall | 86 |
  | library | Public services / Library | 48 |
  | canteen | Education / Student Union | 11 |
  | admin | Office / Office | 235 |
  | health_centre | Healthcare / Hospital, Patient Care | 11 |
  | server_room | none (no data centre in BDG2): flat profile, ASSUMPTION | – |

- Calendar mapping: each 2023 date takes one real 2016/17 source day — RVCE teaching/exam/fest weekdays -> source
  term-time weekdays (same weekday), RVCE vacation -> source break weekdays (June-August and 20 Dec - 5 Jan,
  ASSUMPTION), weekends -> source term-time weekends; seeded per zone and date (`qgrid/bdg2.py`).
- Limitations: the buildings are in North America and Europe (BDG2 sites), so HVAC base load and climate differ from
  Bengaluru, and the source "break" months are northern summer. Shapes are real; magnitudes are still floor area x EPI
  (PENDING RVCE meter data / bills).

## Ausgrid Solar Home Electricity Data — REAL (superseded by BDG2 for loads)
- Original publisher: Ausgrid (dataset page `https://www.ausgrid.com.au/Industry/Our-Research/Data-to-share/Solar-home-electricity-data`,
  no longer online in 2026; metadata record: `https://data.gov.au/data/en/dataset/nsw-solar-home-electricty-data`).
- Copy used: archive by Pierre Haessig, `https://pierreh.eu/downloads/Ausgrid_solar_home_data.zip`
  (linked from `https://github.com/pierre-haessig/ausgrid-solar-data`), fetched 2026-11-21,
  SHA-256 `5a766f52b6c8b3b72730380f4422e478934bc94640a4b089dd0e0e3c055c5d82`. Contains Ausgrid's original
  CSVs and Ausgrid's notes PDF (Aug 2014).
- Licence: Creative Commons Attribution 3.0 Australia (per the archive README); Ausgrid disclaimer in the notes PDF.
- Reference: E. L. Ratnam, S. R. Weller, C. M. Kellett, A. T. Murray, "Residential load and rooftop PV
  generation: an Australian distribution network dataset", Int. J. Sustainable Energy, 2017,
  doi:10.1080/14786451.2015.1100196.
- Processing (`backend/qgrid/data.py`):
  - Load = GC (general consumption) + CL (controlled load) per customer; kWh per half hour → kW.
    Times are Sydney local (EST/EDT) as recorded.
  - k-means (k = 5, fixed seed) on each customer's normalised mean daily profile; clusters assigned
    to buildings by daytime (09–17 h) energy share: highest → lab_block, then admin, library, canteen,
    hostel (lowest daytime share, evening-heavy).
  - **Date alignment: Ausgrid 2012-13 load shapes are weekday-aligned to 2023.** Each 2023 date takes
    the same month/day from Jul-2012..Jun-2013 (Jul–Dec from 2012, Jan–Jun from 2013), shifted by at
    most ±3 days so the weekday matches.
  - Cluster-mean household kW scaled so the annual 99th percentile equals the building's `peak_kw`
    (a design assumption, config.yaml). Half-hourly values repeated to 15-min.
  - Limitation: these are residential shapes from Sydney used as a proxy for campus buildings
    (no open, licence-clear Indian campus metering dataset was available); the lab/admin proxies
    therefore peak in the evening more than a real lab block would.

## Price scenario A — BESCOM HT educational ToD tariff + KERC solar export rate — PENDING
(The HT-2(c)(ii) monthly tariff `tariff_ht2c` below supersedes this stand-in once the settlement engine reads it.)
- Needed: the KERC tariff order applicable to 2023 (BESCOM HT educational institutions category,
  energy charge + ToD adders) and the KERC order fixing the solar (rooftop/export) tariff.
- STAND-IN currently used (config.yaml `prices.A`, labelled STAND-IN everywhere): base 8.00 Rs/kWh,
  +1.00 06–10 h and 18–22 h, −1.00 22–06 h, export 3.00 Rs/kWh. **These are placeholders, not KERC figures.**

## Price scenario B — IEX DAM — PENDING
- Needed: 15-min MCP for 2023 from `https://www.iexindia.com/market-data/day-ahead-market/market-snapshot`
  (Excel export). Parser: `qgrid.data.parse_iex_file` (tolerant to header rows / merged date cells).
- STAND-IN currently used: synthetic hour-window price shape (config.yaml `prices.B.standin_profile_rs_kwh`).

## HT-2(c)(ii) tariff (`config.yaml tariff_ht2c`, `qgrid/v2/tariff.py`) — FY2022-23 VERIFIED, FY2023-24 PENDING
Official files from BESCOM's tariff page `https://bescom.karnataka.gov.in/62/bescom-tariff/en`, fetched 2026-11-27
(the KERC site `kerc.karnataka.gov.in` failed TLS verification from the fetch host, so nothing was taken from it).
The two tariff PDFs are scans: values were read from the rendered page images; page = printed page [PDF page].

| File | URL | SHA-256 | What it is |
|---|---|---|---|
| `data/raw/tariff/bescom_tariff_2023.pdf` | `https://bescom.karnataka.gov.in/storage/pdf-files/RA%20section/Tariff-2023.pdf` | 84662da9160dd429a68971f91c07c0832d804094062444caeece61d91d109c07 | KERC Tariff Order 2022 (BESCOM), dated 04.04.2022, Annexure-5 "Electricity Tariff-2023", effective from the first meter-reading date on or after 01.04.2022 (printed pp. 375-415, 41 PDF pages) |
| `data/raw/tariff/bescom_tariff_order_2023_highlights.pdf` | `https://bescom.karnataka.gov.in/storage/pdf-files/RA%20section/engnotification.pdf` | 51f2d18614ec753a15b1a5309f89974598014799b7532ef2ac8ad0ca6bd3fb8b | BESCOM public notice (Times of India, 24.05.2023): Tariff Order 2023 dated 12.05.2023 applies from the first meter-reading date on or after 01.04.2023; no category rates |
| `data/raw/tariff/bescom_other_tariff_issues_FY23_en.pdf` | `https://bescom.karnataka.gov.in/storage/pdf-files/RA%20section/Other%20tariff%20related%20issues%20for%20FY-23%20-%20English.pdf` | f35a951b201d17499db6eaefb227f7f3c3bb49b35528d78f075a5f363ab3cb66 | FY-23 cross-subsidy surcharge (HT-2(c)(ii) 215 paise/unit, p.2), electricity tax 9 % (p.3), incentive schemes (p.3) |

Values used (TO-2022, `bescom_tariff_2023.pdf`): HT-2(c)(ii) demand Rs 265/kVA/month, energy 825 paise/unit for the
first one lakh units and 865 paise for the balance, p.412 [38]; ToD Dec-Jun +100 paise 18-22 h, -100 paise 22-06 h,
Jul-Nov 0, p.412 [38] and notes 10-12 p.408 [34]; billing demand = max(recorded MD, 85 % of CD) and excess over CD at
two times the rate, p.404 [30]; billing demand rounding and PF 0.90, p.405 [31].
Inspected and NOT used: `Tariff rates FY-2021-22.pdf` (Tariff Order 2021, FY2021-22) and `ElectricityTariff-2024.xlsx`
(a BESCOM working file with FY16-era tables; it does not hold the TO-2023 rate schedule). Missing PDFs:
docs/data_verification.md.

## CEA CO2 baseline — REAL
- Files (fetched 2026-11-27 from CEA's report API, links on `https://cea.nic.in/`):
  - `data/raw/cea/CEA_CO2_Baseline_User_Guide_v20.0.pdf` — `https://cea.nic.in/api/cdm-report-version/view-pdf/en/76`,
    "CO2 Baseline Database for the Indian Power Sector, User Guide, Version 20.0, December 2024",
    SHA-256 b881c258f58fd77c8faeb36479ccd1ed8bd111c45e708196df8a66ff7b29afc6.
  - `data/raw/cea/CEA_CO2_Baseline_User_Guide_v21.0.pdf` — `https://cea.nic.in/api/cdm-report-version/view-pdf/en/78`,
    Version 21.0, November 2025, SHA-256 212a9f7d7a4c2502418924765288b3e4edd3a35d5a87ac87aa611819c16431fa.
  - (`.../view-pdf/en/74` = Version 19.0, Dec 2023, FY2022-23 = 0.716, inspected, not kept.)
- Value: weighted average emission factor of the Indian grid, FY2023-24 = **0.727 tCO2/MWh** (v20.0, Table S, printed
  p.1 [PDF p.4]; worked calculation 1204.51 Mt / 1655.7 BU, p.12 [15]). v21.0 Annexure-I, p.21 [27], after final
  captive data: 2022-23 = 0.716, 2023-24 = 0.727, 2024-25 = 0.710. Recorded in `data/raw/cea/emission_factor.yaml`.
- Licence: Government of India publication (CEA). Like the other raw files, the PDFs are not committed (data/raw is
  git-ignored); re-fetch from the URLs above and check the SHA-256. `emission_factor.yaml` is committed;
  `qgrid.data.load_co2_factor` reports REAL only when it and a CEA PDF are both present.

## Synthetic data
Synthetic inputs appear only in unit tests (`backend/tests/`), labelled SYNTHETIC in the test code.

## OpenStreetMap — REAL
- Overpass API (`https://overpass-api.de/api/interpreter`), campus element `way(55685638)` "R. V. College of Engineering",
  everything inside its area (buildings, amenities). Fetched 2026-11-21 by `qgrid.campus.fetch_osm`; query and
  timestamp stored in the JSON (`_qgrid_fetch`); SHA-256 recorded in `data/processed/campus.json`.
- Licence: ODbL 1.0 — **© OpenStreetMap contributors**.
- Processing (`backend/qgrid/campus.py`, rules in `config.yaml campus.zone_rules`): footprints → 9 zones by name/tag
  regex; floor area = footprint × `building:levels` (or zone default, ASSUMPTION); PV kWp = footprint × 45 % usable
  roof × 0.18 kWp/m² (ASSUMPTION); tie-lines = minimum spanning tree on zone centroids + 2 shortest extra links,
  degree ≤ 3. The pump house is not mapped in OSM; its location/size are ASSUMPTIONS.
- Campus rescale (`config.yaml campus.rescale`, `qgrid/v2/campus_scale.py`, applied in `qgrid/datasets.py` "rvce"):
  OSM buildings that are not RVCE's own are dropped (`campus.osm_exclude`):

  | OSM id | name | zone | footprint m² | reason |
  |---|---|---|---:|---|
  | way/1286468169 | RVU Block | academic | 2,649.6 | RV University building (OSM name) |
  | way/1286468170 | RVU A Block | academic | 2,967.4 | RV University building (OSM name) |
  | way/1313225782 | RVU C Block | academic | 1,200.5 | RV University building (OSM name) |
  | way/1467210438 | RVU Admin Block | admin | 1,094.1 | RV University building (OSM name) |

  Not loaded at all by `campus.py` (unchanged): OSM *relations* (Mechanical Engineering, Chemical Engineering/Chemistry/
  Physics, Biotechnology, Telecommunication Department, Krishna Hostel, Diamond Jubilee Hostel, RVU F Block) and
  buildings tagged construction/roof/garage. Unnamed OSM buildings cannot be attributed to RVCE or RVU from OSM alone and
  are kept. Floor areas are then scaled to the team-brief totals and 500.48 kWp of existing PV is spread over the zones
  by footprint (ASSUMPTION); see docs/data_verification.md.

## Campus loads — PENDING RVCE DATA
- Annual kWh per zone = floor area × energy-use intensity (kWh/m²/yr, ASSUMPTION per zone in `config.yaml`).
- Shapes: timetable templates by building type and day type (`configs/profiles.yaml`, ASSUMPTION); hostels use the
  real Ausgrid residential shape (above). Lab schedule from `data/raw/lab_schedule.csv` (TEMPLATE until faculty input).
- If `data/raw/rvce_bills.csv` (month, kwh) exists, totals are scaled month by month to the bills.

## Calendar — PENDING (partly sourced)
- Fest (8th Mile) 13–15 June 2023: RVCE cultural activities report and technical club report 2023-24
  (`https://rvce.edu.in/sites/default/files/All%20Techclubreport_2023-2024.pdf`, `https://naac.rvce.edu.in/sites/default/files/2024-05/CAT-Report-2019-2023.pdf`).
- Teaching / exam / vacation windows in `config.yaml calendar` are PLACEHOLDERS: rvce.edu.in returned HTTP 403 to
  scripted downloads of the academic-calendar PDFs. Provide `data/raw/rvce_calendar.csv` (date, day_type) to override.

## Engineering assumptions (not data)
Diesel price 90 Rs/L, fuel curve 0.08 L/h per kW rated + 0.25 L/kWh, 2.68 kg CO2/L; VOLL 40 / 1000 Rs/kWh
(optimisation only); battery capex 25,000 Rs/kWh; semester = 120 days; battery/DG/tank sizes per zone. All in
`config.yaml`, all labelled ASSUMPTION; none is presented as data.


## Benchmark datasets (multi-dataset benchmark, `qgrid/datasets.py`)

| Dataset | Status | Loads | Weather | Licence |
|---|---|---|---|---|
| RVCE (case study) | as above | BDG2 shapes x floor area x EPI | NASA POWER 2023 | as above |
| BDG2 site "Fox" (Arizona), 2017 | **REAL** loads | the site's own metered buildings (>= 90 % complete), grouped into zones | NASA POWER at the BDG2 site coordinates | CC BY-SA 4.0 |
| BDG2 site "Bull" (Texas), 2017 | **REAL** loads | same | same | CC BY-SA 4.0 |
| BDG2 site "Cockatoo" (New York), 2017 | **REAL** loads | same | same | CC BY-SA 4.0 |
| CU-BEMS, Chamchuri 5 office building, Bangkok, 2019 | **REAL** loads | the 7 floors' AC, lighting and plug meters (1-min, summed per floor, hourly means) | NASA POWER at 13.7367 N, 100.5332 E | CC BY 4.0 |

- **BDG2 sites**: same files and licence as the BDG2 entry above; zone groups (academic, labs, dorms, library, offices, other)
  from `metadata.csv` primary/sub use; site coordinates from `metadata.csv`. Meter spikes clipped at each building's 99.9th
  percentile.
- **CU-BEMS**: Pipattanasomporn, M., Chitalia, G., Songsiri, J. et al. "CU-BEMS, smart building electricity consumption and
  indoor environmental sensor datasets." *Scientific Data* 7, 241 (2020). Files from
  `https://github.com/SGRUdata/SGRUdata.github.io/tree/master/data` (fetched 2026-11-22):
  - `2019Floor1.csv.zip` SHA-256 f88d0707a4571598bc1be307cf44b6e13d5bf356b9255ed7742f8a279e272e50
  - `2019Floor2.csv.zip` SHA-256 f6a40fa250d095fe9cdb17a302b4f81a7e3f4c2bdf709460b06b242c57ab2516
  - `2019Floor3.csv.zip` SHA-256 a3b10899e070d3a32f3a1e3e8bfc2874eee81d573ddb8031b59801b39064a0c1
  - `2019Floor4.csv.zip` SHA-256 f8ce104a9f1ed938d90cc2a0b02a72dee895c2c672b66ca896461feab02b0e61
  - `2019Floor5.csv.zip` SHA-256 310ca9ae005326975e5161b0672cace46fab73c15d828078552af50ffb7be51c
  - `2019Floor6.csv.zip` SHA-256 ded70a7938030b9bc19a7038ae09cb31d3d8dc18801a054a6a216c483828520d
  - `2019Floor7.csv.zip` SHA-256 f6fb56ee65bb07d0035f51148b86e0caf8030c96c46cf7c0aa2ec9e38196ce05
  Licence: Creative Commons Attribution 4.0 (CC BY 4.0) per the dataset record. It is one office building, so its
  "zones" are floors linked by assumed internal cables.
- **NASA POWER** (sites): `data/raw/nasa_power/<dataset>_<year>_hourly.json`, parameters ALLSKY_SFC_SW_DWN, CLRSKY_SFC_SW_DWN,
  T2M, fetched 2026-11-22 by `scripts/fetch_data.py` (`fetch_nasa_site`); licence as NASA POWER above.
- **ASSUMPTIONS for sites without asset data** (one rule for all, `qgrid/datasets.py`): PV = 30 % of each zone's annual energy,
  battery = 2 h of mean load (C-rate 0.5), one diesel set at the zone with the largest critical load (50 % of its 99th-percentile
  load), critical share 10 % (dorms) / 5 % (others), cables in a chain plus two seeded cross-links rated at 25 % of the median
  zone peak, the stand-in tariff (price scenario A, PENDING) on local clock time.
- **SYNTHETIC (seeded) events**: unplanned grid outages (20 % of evaluation days, 1–3 h, start 08:00–20:00) and one 3-hour
  campus network outage per day (06:00–21:00) for the communication-failure methods. Official BESCOM planned-cut schedules are
  **PENDING**.
