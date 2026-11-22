# Data sources

Status legend: **REAL** = official/primary data in `data/raw/` and used for results ·
**PENDING** = file not yet obtained; a clearly labelled STAND-IN keeps the pipeline runnable and
**no stand-in value is ever presented as a headline result**. After adding the missing files run
`scripts/refresh_all.sh`.

| Dataset | Status | Used for | Raw file(s) |
|---|---|---|---|
| NASA POWER hourly (ALLSKY_SFC_SW_DWN, T2M), 12.92N 77.50E, 2023 | **REAL** | PV output, sun position | `data/raw/nasa_power/bengaluru_2023_hourly.json` |
| NASA POWER hourly clear-sky (CLRSKY_SFC_SW_DWN), same site, 2023 | **REAL** | v2 solar forecast (clear-sky envelope) | `data/raw/nasa_power/bengaluru_2023_hourly_clearsky.json` |
| Ausgrid Solar Home Electricity Data 2012-13 (half-hourly, 300 homes) | **REAL** | building load shapes | `data/raw/ausgrid/Solar home 2012-2013.csv` (+ archive zip, notes PDF) |
| BESCOM HT educational tariff with ToD + KERC solar export rate | **PENDING** | price scenario A (headline) | `data/raw/tariff/` |
| IEX Day-Ahead Market 15-min MCP, 2023 | **PENDING** | price scenario B | `data/raw/iex/` |
| CEA CO2 Baseline Database (grid weighted-average emission factor) | **PENDING** | CO2 accounting | `data/raw/cea/` |
| OpenStreetMap: RVCE campus outline + building footprints | **REAL** | zones, roof area → PV kWp, tie-line layout, 3D campus | `data/raw/osm_rvce.json`, `osm_rvce.geojson` |
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

## Ausgrid Solar Home Electricity Data — REAL
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
- Needed: the KERC tariff order applicable to 2023 (BESCOM HT educational institutions category,
  energy charge + ToD adders) and the KERC order fixing the solar (rooftop/export) tariff.
- STAND-IN currently used (config.yaml `prices.A`, labelled STAND-IN everywhere): base 8.00 Rs/kWh,
  +1.00 06–10 h and 18–22 h, −1.00 22–06 h, export 3.00 Rs/kWh. **These are placeholders, not KERC figures.**

## Price scenario B — IEX DAM — PENDING
- Needed: 15-min MCP for 2023 from `https://www.iexindia.com/market-data/day-ahead-market/market-snapshot`
  (Excel export). Parser: `qgrid.data.parse_iex_file` (tolerant to header rows / merged date cells).
- STAND-IN currently used: synthetic hour-window price shape (config.yaml `prices.B.standin_profile_rs_kwh`).

## CEA CO2 baseline — PENDING
- Needed: latest "CO2 Baseline Database for the Indian Power Sector — User Guide" PDF from `https://cea.nic.in/`.
- STAND-IN currently used: 0.727 tCO2/MWh — the v20.0 weighted average for FY2023-24 as quoted by
  secondary sources (Climatiq `https://www.climatiq.io/data/source/government-of-india-_-central-electricity-authority`;
  Saur Energy `https://www.saurenergy.com/solar-energy-news/ceas-co2-baseline-database-impact-of-re-on-indian-grid-emissions-intensity`).
  A later version (v22.0) may revise it; to be verified against the PDF and recorded in
  `data/raw/cea/emission_factor.yaml` with the page number.

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
