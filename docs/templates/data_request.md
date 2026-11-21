# Data request — RVCE Estate Office / Department of Electrical Engineering

To replace every PENDING estimate in Q-Grid with RVCE's own data. Files go into `data/raw/`; then run
`bash scripts/refresh_all.sh` (all results, docs and the demo regenerate).

| # | Data | Detail | Format → file |
|---|---|---|---|
| 1 | BESCOM electricity bills | 12 consecutive months (2023 preferred), all HT connections: kWh, kVAh, max demand, ToD kWh split, tariff category, Rs | CSV `month,kwh` → `data/raw/rvce_bills.csv` (+ scanned bills) |
| 2 | Interval meter data | 15/30-min kW for the campus incomer and any building sub-meters (hostels, labs, library, admin, server room) | CSV `timestamp,meter,kw` |
| 3 | Rooftop PV | installed kWp per building, inverter make, monthly generation | CSV |
| 4 | Diesel generators | kVA rating, location, fuel logs (litres/month), run-hour logs, outage dates/durations | CSV |
| 5 | Lab schedules | per lab: day, start, end, kW of heavy equipment, critical yes/no | CSV `zone,day,start,end,kw,critical,name` → `data/raw/lab_schedule.csv` |
| 6 | Academic calendar | teaching / exam / vacation / fest dates for 2023 | CSV `date,day_type` → `data/raw/rvce_calendar.csv` |
| 7 | Water | borewell pump kW, overhead tank capacities, daily consumption | CSV |
| 8 | Electrical single-line diagram | feeders between buildings, cable ratings (to replace the assumed tie-line layout/rating) | PDF |
| 9 | UPS / battery assets | server-room UPS kWh/kW, any battery storage | CSV |

Public documents also still needed (not RVCE-specific): KERC tariff order for BESCOM HT educational institutions (ToD) and the
KERC solar export / net-metering rate; IEX day-ahead prices 2023; CEA CO2 baseline database user guide (see `data/SOURCES.md`).
