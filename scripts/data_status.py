"""Which data is real and which files are still missing, for the "Data: x real / y pending" badge and Verify.

  python scripts/data_status.py   -> results/replay/data_status.json (+ frontend/public/replay)
Checks data/raw/ for every source in the replay's data_status (results/replay/index.json) and names the exact files the
pipeline expects for each PENDING item (from scripts/fetch_data.py and docs/BLOCKERS.md)."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
ITEMS = {
    "nasa_power": ("NASA POWER irradiance (Bengaluru, 2023)", ["data/raw/nasa_power/*.json"]),
    "osm_layout": ("OpenStreetMap campus layout", ["data/raw/osm_rvce.json", "data/raw/osm_rvce.geojson"]),
    "bdg2_load_shapes": ("BDG2 education-building meters (load shapes)", ["data/raw/bdg2/electricity_cleaned.csv", "data/raw/bdg2/metadata.csv"]),
    "iex": ("IEX day-ahead prices, 15-min, 2023", ["data/raw/iex/*.xlsx (exports from the IEX market snapshot)"]),
    "tariff_A": ("KERC / BESCOM tariff order (HT educational, ToD) and solar export order",
                 ["data/raw/tariff/KERC_tariff_order_BESCOM_FY2023-24.pdf", "data/raw/tariff/KERC_solar_export_tariff.pdf", "config.yaml prices.A.status: REAL"]),
    "cea": ("CEA CO₂ baseline database (user guide PDF)", ["data/raw/cea/*.pdf", "data/raw/cea/emission_factor.yaml"]),
    "calendar": ("RVCE academic calendar", ["data/raw/rvce_calendar.csv (date, day_type)"]),
    "campus_loads": ("RVCE bills and interval meter data", ["data/raw/rvce_meters/*.csv (15-min kW per building)", "12 months of BESCOM bills"]),
    "lab_schedule": ("RVCE lab schedule", ["data/raw/lab_schedule.csv filled in by RVCE (currently a template)"]),
}


def present(pattern: str) -> bool:
    p = pattern.split(" ")[0]
    if p.startswith("config.yaml") or not p.startswith("data/"):
        return False
    return any(ROOT.glob(p)) if any(c in p for c in "*?") else (ROOT / p).exists()


def main():
    idx = json.loads((ROOT / "results" / "replay" / "index.json").read_text(encoding="utf-8"))
    st = idx["data_status"]
    items = []
    for k, status in st.items():
        label, files = ITEMS.get(k, (k, []))
        real = status == "REAL"
        items.append({"key": k, "label": label, "status": status, "real": real,
                      "files": [{"path": f, "present": present(f)} for f in files],
                      "missing": [] if real else ([f for f in files] if status == "TEMPLATE" else [f for f in files if not present(f)])})
    out = {"checked_at": time.strftime("%Y-%m-%d %H:%M"), "n_real": sum(i["real"] for i in items), "n_pending": sum(not i["real"] for i in items),
           "items": items, "how": "bash scripts/refresh_all.sh after placing the files (see docs/BLOCKERS.md, docs/data_request.md)"}
    p = ROOT / "results" / "replay" / "data_status.json"
    p.write_text(json.dumps(out, indent=1), encoding="utf-8"); shutil.copy(p, ROOT / "frontend" / "public" / "replay" / p.name)
    print(f"{out['n_real']} real, {out['n_pending']} pending")
    for i in items:
        if not i["real"]:
            print(f"  {i['label']}: missing {', '.join(i['missing'])}")


if __name__ == "__main__":
    main()
