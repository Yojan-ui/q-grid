# Blockers and pending items

| # | Item | Status | Impact | Unblock |
|---|---|---|---|---|
| 1 | IEX DAM 15-min prices 2023 | PENDING | Scenario B runs on a labelled SYNTHETIC STAND-IN price shape; the "high-price" test day uses a stand-in criterion (max evening net load). | Export from the IEX market-snapshot page into `data/raw/iex/` (see `python scripts/fetch_data.py`), then `bash scripts/refresh_all.sh`. An attempt to read the site's internal JSON API from a script was blocked by the session's permission policy, so it was not pursued. |
| 2 | KERC tariff order (BESCOM HT educational ToD) + KERC solar export rate | PENDING | Scenario A (headline) runs on labelled STAND-IN rates (`config.yaml prices.A`). No scenario-A number is a headline result until replaced. | Save the official PDFs in `data/raw/tariff/`, copy rates + page numbers into `config.yaml` / `data/SOURCES.md`, set `prices.A.status: REAL`, re-run `scripts/refresh_all.sh`. |
| 3 | CEA CO2 baseline PDF | PENDING | CO2 uses 0.727 tCO2/MWh (v20.0 value as quoted by secondary sources), flagged PENDING. CO2 is proportional to imports, so relative comparisons between methods are unaffected; absolute kg will change if the verified value differs. | Save the PDF in `data/raw/cea/`, write `data/raw/cea/emission_factor.yaml` with version, fiscal year, value and page. |
| 4 | Ausgrid original source offline | Resolved (mirror) | Using the researcher-hosted archive copy (CC BY 3.0 AU, SHA-256 recorded in SOURCES.md). | — |
| 5 | Campus load data | Limitation | Residential Ausgrid shapes are a proxy for campus buildings (evening-heavy). Documented in SOURCES.md and results.md. | Replace with campus meter data if available. |
| 6 | IBM Quantum hardware | Not run (by design) | Needs credentials and may cost money; `run_ibm()` refuses unless `QGRID_ALLOW_IBM=1`. | Ask the team lead before enabling. |
| 7 | RVCE academic calendar | PENDING | rvce.edu.in returns 403 to scripted PDF downloads (also via the fetch agent). Teaching/exam/vacation scenario dates are placeholders; fest dates are sourced. | Put `data/raw/rvce_calendar.csv` (date, day_type). |
| 8 | RVCE bills / interval meters | PENDING RVCE DATA | Campus loads are area x EPI estimates. | See docs/data_request.md. |
