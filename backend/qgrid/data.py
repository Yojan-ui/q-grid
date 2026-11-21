"""Real-data pipeline: raw files in data/raw/ -> 15-min series in data/processed/*.parquet.

Run:  python -m qgrid.data
Outputs:
  data/processed/pv.parquet         per-building PV output (kW), 15-min, 2023
  data/processed/load.parquet       per-building load (kW), 15-min, 2023
  data/processed/price.parquet      IEX DAM MCP (Rs/kWh), 15-min, 2023
  data/processed/weather.parquet    GHI (W/m2), T2M (C), 15-min
  data/processed/meta.json          CO2 factor, test days, eval days, mapping details
"""
from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
SLOT = "15min"
SLOTS_PER_DAY = 96


def load_config(path: Path | None = None) -> dict:
    return yaml.safe_load((path or ROOT / "config.yaml").read_text())


def year_index(year: int) -> pd.DatetimeIndex:
    return pd.date_range(f"{year}-01-01", f"{year + 1}-01-01", freq=SLOT, inclusive="left")


# ----------------------------------------------------------------------------- NASA POWER / PV
def load_weather(year: int) -> pd.DataFrame:
    """Hourly NASA POWER (local solar time) -> 15-min by repeating each hourly mean 4x
    (energy-preserving; NASA hourly values are hour averages)."""
    raw = json.loads((RAW / "nasa_power" / f"bengaluru_{year}_hourly.json").read_text())
    p = raw["properties"]["parameter"]
    idx = pd.to_datetime(list(p["T2M"].keys()), format="%Y%m%d%H")
    hourly = pd.DataFrame(
        {"ghi_wm2": list(p["ALLSKY_SFC_SW_DWN"].values()), "t2m_c": list(p["T2M"].values())},
        index=idx,
    ).astype(float)
    hourly[hourly < -900] = np.nan  # NASA fill value
    hourly = hourly.interpolate(limit=3)
    out = hourly.reindex(year_index(year), method="ffill")
    out["ghi_wm2"] = out["ghi_wm2"].clip(lower=0)
    return out


def pv_output_kw(weather: pd.DataFrame, kwp: float, pv_model: dict) -> pd.Series:
    """PVWatts-style: P = kWp * G/1000 * (1 + gamma*(Tcell-25)) * derate,
    Tcell = Tamb + (NOCT-20)/800 * G."""
    g = weather["ghi_wm2"].to_numpy()
    tcell = weather["t2m_c"].to_numpy() + (pv_model["noct_c"] - 20.0) / 800.0 * g
    p = kwp * g / 1000.0 * (1 + pv_model["gamma_per_c"] * (tcell - 25.0)) * pv_model["system_derate"]
    return pd.Series(np.clip(p, 0, kwp), index=weather.index)


# ----------------------------------------------------------------------------- Ausgrid
def _read_ausgrid_csv() -> pd.DataFrame:
    """Return the 2012-13 Ausgrid half-hourly table (one row per customer/category/date)."""
    d = RAW / "ausgrid"
    csvs = sorted(d.glob("*2012*2013*.csv")) or sorted(d.glob("*.csv"))
    if csvs:
        return _parse_ausgrid(csvs[0].read_bytes())
    for zpath in sorted(d.glob("*.zip")):
        found = _find_in_zip(zipfile.ZipFile(zpath))
        if found is not None:
            return _parse_ausgrid(found)
    raise FileNotFoundError("No Ausgrid 2012-13 CSV found in data/raw/ausgrid (zip or csv)")


def _find_in_zip(z: zipfile.ZipFile) -> bytes | None:
    names = z.namelist()
    for n in names:  # direct CSV
        if n.lower().endswith(".csv") and "2012" in n and "2013" in n:
            return z.read(n)
    for n in names:  # nested zip (the mirror bundles the yearly zips)
        if n.lower().endswith(".zip") and "2012" in n and "2013" in n:
            return _find_in_zip(zipfile.ZipFile(io.BytesIO(z.read(n))))
    return None


def _parse_ausgrid(blob: bytes) -> pd.DataFrame:
    text = blob.decode("latin-1")
    lines = text.splitlines()
    # first line is a free-text title in the original files; header starts with "Customer"
    start = next(i for i, l in enumerate(lines[:5]) if l.lower().startswith("customer"))
    df = pd.read_csv(io.StringIO("\n".join(lines[start:])))
    df.columns = [c.strip() for c in df.columns]
    return df


def ausgrid_customer_loads(df: pd.DataFrame) -> pd.DataFrame:
    """Customer x half-hour load (kW) = (GC + CL) kWh / 0.5h. Index: timestamps, cols: customer."""
    cat_col = next(c for c in df.columns if c.lower().startswith("consumption category"))
    date_col = next(c for c in df.columns if c.lower() == "date")
    hh_cols = [c for c in df.columns if re.fullmatch(r"\d{1,2}:\d{2}", c)]
    assert len(hh_cols) == 48, f"expected 48 half-hour columns, got {len(hh_cols)}"
    df = df[df[cat_col].isin(["GC", "CL"])].copy()
    df["date"] = pd.to_datetime(df[date_col], dayfirst=True, format="mixed")
    g = df.groupby(["Customer", "date"])[hh_cols].sum()  # GC + CL
    long = g.stack().rename("kwh").reset_index().rename(columns={"level_2": "hh"})
    # column "0:30" is the half hour ending 00:30 -> start 00:00; "0:00" is ending midnight
    hh_end = pd.to_timedelta(long["hh"].str.replace(r"^(\d+):(\d+)$", r"\1:\2:00", regex=True))
    hh_end = hh_end.where(hh_end > pd.Timedelta(0), pd.Timedelta(hours=24))
    long["ts"] = long["date"] + hh_end - pd.Timedelta(minutes=30)
    wide = long.pivot_table(index="ts", columns="Customer", values="kwh", aggfunc="sum")
    return (wide / 0.5).sort_index()


def cluster_profiles(cust_kw: pd.DataFrame, k: int = 5, seed: int = 0):
    """k-means on each customer's normalised mean daily profile (48 values)."""
    from scipy.cluster.vq import kmeans2

    daily = cust_kw.groupby(cust_kw.index.time).mean().T  # customers x 48
    daily = daily.dropna()
    norm = daily.div(daily.sum(axis=1), axis=0).to_numpy()
    rng = np.random.default_rng(seed)
    centroids, labels = kmeans2(norm, k, seed=rng, minit="++")
    return daily.index.to_numpy(), labels, centroids


def daytime_share(profile48: np.ndarray) -> float:
    return float(profile48[18:34].sum() / profile48.sum())  # 09:00-17:00


def map_dates(target_year: int, src_start: str = "2012-07-01", src_end: str = "2013-06-30"):
    """Map each target-year date to a source date with the same month/day (Jul-Dec from 2012,
    Jan-Jun from 2013), then shift by up to +-3 days so the weekday matches."""
    s0, s1 = pd.Timestamp(src_start), pd.Timestamp(src_end)
    out = {}
    for d in pd.date_range(f"{target_year}-01-01", f"{target_year}-12-31", freq="D"):
        y = 2012 if d.month >= 7 else 2013
        day = min(d.day, 28) if d.month == 2 else d.day
        base = pd.Timestamp(year=y, month=d.month, day=day)
        shift = (d.weekday() - base.weekday() + 3) % 7 - 3
        src = base + pd.Timedelta(days=shift)
        if src < s0:
            src += pd.Timedelta(days=7)
        if src > s1:
            src -= pd.Timedelta(days=7)
        out[d] = src
    return out


def build_loads(cfg: dict) -> tuple[pd.DataFrame, dict]:
    year = cfg["site"]["year"]
    cust = ausgrid_customer_loads(_read_ausgrid_csv())
    ids, labels, centroids = cluster_profiles(cust, k=len(cfg["buildings"]))
    shares = [daytime_share(c) for c in centroids]
    order = np.argsort(shares)[::-1]  # highest daytime share first
    mapping = {}
    for bname, ci in zip(cfg["load_mapping_order"], order):
        mapping[bname] = int(ci)

    dmap = map_dates(year)
    idx = year_index(year)
    loads = {}
    for bname, ci in mapping.items():
        members = ids[labels == ci]
        mean_kw = cust[members].mean(axis=1)  # cluster-average household kW, half-hourly
        mean_kw = mean_kw.reindex(pd.date_range(mean_kw.index[0], mean_kw.index[-1] + pd.Timedelta("15min"), freq=SLOT)).ffill()
        series = np.empty(len(idx))
        for i, d in enumerate(pd.date_range(f"{year}-01-01", periods=len(idx) // SLOTS_PER_DAY, freq="D")):
            src = dmap[d]
            day = mean_kw.loc[src: src + pd.Timedelta(hours=23, minutes=45)].to_numpy()
            if len(day) != SLOTS_PER_DAY or np.isnan(day).any():
                day = mean_kw.groupby(mean_kw.index.time).mean().to_numpy()  # fallback: mean day
            series[i * SLOTS_PER_DAY:(i + 1) * SLOTS_PER_DAY] = day
        s = pd.Series(series, index=idx)
        scale = cfg["buildings"][bname]["peak_kw"] / s.quantile(0.99)
        loads[bname] = s * scale
    info = {
        "n_customers": int(len(ids)),
        "cluster_sizes": {b: int((labels == c).sum()) for b, c in mapping.items()},
        "cluster_daytime_share": {b: round(shares[c], 3) for b, c in mapping.items()},
        "date_mapping": "same month/day from Jul-2012..Jun-2013, shifted <=3 days to match weekday",
        "scaling": "cluster-mean household kW scaled so annual p99 = building peak_kw",
    }
    return pd.DataFrame(loads), info


# ----------------------------------------------------------------------------- IEX
def _find_col(cols, *keys):
    for c in cols:
        lc = str(c).lower()
        if all(k in lc for k in keys):
            return c
    return None


def parse_iex_file(path: Path) -> pd.DataFrame:
    """Tolerant parser for IEX DAM market-snapshot exports -> DataFrame[ts, mcp_rs_mwh]."""
    if path.suffix.lower() == ".csv":
        sheets = {"csv": pd.read_csv(path, header=None)}
    else:
        sheets = pd.read_excel(path, sheet_name=None, header=None)
    frames = []
    for raw in sheets.values():
        # locate header row: the first row containing both 'date' and 'mcp'
        hdr = None
        for i in range(min(30, len(raw))):
            row = " ".join(str(x).lower() for x in raw.iloc[i].tolist())
            if "date" in row and "mcp" in row:
                hdr = i
                break
        if hdr is None:
            continue
        df = raw.iloc[hdr + 1:].copy()
        df.columns = [str(c).strip() for c in raw.iloc[hdr]]
        dcol = _find_col(df.columns, "date")
        tcol = _find_col(df.columns, "time", "block") or _find_col(df.columns, "time")
        mcol = _find_col(df.columns, "mcp")
        df = df[[dcol, tcol, mcol]].copy()
        df[dcol] = df[dcol].ffill()  # exports often merge the date cell across a day's blocks
        df = df.dropna()
        date = pd.to_datetime(df[dcol], dayfirst=True, format="mixed", errors="coerce")
        start = df[tcol].astype(str).str.extract(r"(\d{1,2}:\d{2})")[0]
        ts = date + pd.to_timedelta(start + ":00", errors="coerce")
        price = pd.to_numeric(df[mcol].astype(str).str.replace(",", ""), errors="coerce")
        frames.append(pd.DataFrame({"ts": ts, "mcp_rs_mwh": price}).dropna())
    if not frames:
        raise ValueError(f"Could not find a Date/MCP table in {path.name}")
    return pd.concat(frames)


def _window_mask(idx: pd.DatetimeIndex, start: str, end: str) -> np.ndarray:
    """[start, end) by time of day; wraps midnight when end <= start. '24:00' allowed."""
    mins = idx.hour * 60 + idx.minute
    a = int(start[:2]) * 60 + int(start[3:])
    b = int(end[:2]) * 60 + int(end[3:])
    return (mins >= a) & (mins < b) if a < b else (mins >= a) | (mins < b)


def iex_series(year: int) -> pd.Series | None:
    """Real IEX DAM MCP (Rs/kWh) if data/raw/iex covers the year (<=3 days gap-filled), else None."""
    d = RAW / "iex"
    files = sorted(p for p in d.glob("*") if p.suffix.lower() in {".xlsx", ".xls", ".csv"}) if d.exists() else []
    if not files:
        return None
    df = pd.concat([parse_iex_file(p) for p in files]).drop_duplicates("ts").set_index("ts").sort_index()
    s = df["mcp_rs_mwh"].reindex(year_index(year))
    if s.isna().sum() > 4 * 24 * 3:
        print(f"[iex] only {int(s.notna().sum())} of {len(s)} slots present -> treating IEX as PENDING")
        return None
    return s.interpolate(limit_direction="both") / 1000.0


def build_prices(cfg: dict) -> tuple[pd.DataFrame, dict]:
    """Columns A_import, A_export, B_import, B_export (Rs/kWh). Returns (prices, status)."""
    year = cfg["site"]["year"]
    idx = year_index(year)
    pc = cfg["prices"]
    status = {}

    a = pc["A"]
    imp = np.full(len(idx), float(a["import_base_rs_kwh"]))
    for w in a["tod"]:
        imp += w["adder"] * _window_mask(idx, w["start"], w["end"])
    out = pd.DataFrame({"A_import": imp, "A_export": float(a["export_rs_kwh"])}, index=idx)
    status["A"] = {"status": a["status"], "source": a["source"],
                   "note": a["standin_note"] if a["status"] != "REAL" else ""}

    b = pc["B"]
    real = iex_series(year)
    if real is not None:
        out["B_import"] = real.to_numpy()
        status["B"] = {"status": "REAL", "source": b["source"], "note": ""}
    else:
        prof = np.zeros(len(idx))
        for w in b["standin_profile_rs_kwh"]:
            prof = np.where(_window_mask(idx, w["start"], w["end"]), w["price"], prof)
        out["B_import"] = prof
        status["B"] = {"status": "PENDING", "source": b["source"], "note": b["standin_note"]}
    out["B_export"] = out["B_import"] * float(b["export_price_factor"])
    return out, status


# ----------------------------------------------------------------------------- CEA
def load_co2_factor(cfg: dict) -> dict:
    f = RAW / "cea" / "emission_factor.yaml"
    if f.exists() and list((RAW / "cea").glob("*.pdf")):
        d = yaml.safe_load(f.read_text())
        v = float(d["weighted_average_tco2_per_mwh"])
        assert 0.3 < v < 1.5
        return {"status": "REAL", "tco2_per_mwh": v, **d}
    c = cfg["co2"]
    return {"status": "PENDING", "tco2_per_mwh": float(c["standin_tco2_per_mwh"]), "note": c["standin_note"]}


# ----------------------------------------------------------------------------- test days
def pick_days(pv_total: pd.Series, load_total: pd.Series, price: pd.Series | None, n_eval: int) -> dict:
    daily_pv = pv_total.resample("D").sum() / 4.0  # kWh
    monsoon = daily_pv[(daily_pv.index.month >= 6) & (daily_pv.index.month <= 9)]
    days = pd.Series(daily_pv.index)
    step = len(days) / n_eval
    eval_days = [str(days.iloc[int(step * i + step / 2)].date()) for i in range(n_eval)]
    if price is not None:
        hp = price.between_time("18:00", "21:45").resample("D").mean().idxmax()
        hp_crit = "max mean IEX DAM price 18:00-22:00"
    else:  # stand-in prices have no day-to-day variation -> use highest evening net import
        net = (load_total - pv_total).between_time("18:00", "21:45").resample("D").sum()
        hp = net.idxmax()
        hp_crit = "PENDING IEX: stand-in criterion = max campus evening (18-22h) net load"
    return {
        "sunny": str(daily_pv.idxmax().date()),
        "monsoon_cloudy": str(monsoon.idxmin().date()),
        "high_price": str(hp.date()),
        "eval_days": eval_days,
        "criteria": {
            "sunny": "max campus daily PV energy in the year",
            "monsoon_cloudy": "min campus daily PV energy in Jun-Sep",
            "high_price": hp_crit,
            "eval_days": f"{n_eval} days evenly spaced across the year",
        },
    }


# ----------------------------------------------------------------------------- main
def build_all(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    PROC.mkdir(parents=True, exist_ok=True)
    year = cfg["site"]["year"]
    weather = load_weather(year)
    weather.to_parquet(PROC / "weather.parquet")
    pv = pd.DataFrame({b: pv_output_kw(weather, s["pv_kwp"], cfg["pv_model"]) for b, s in cfg["buildings"].items()})
    pv.to_parquet(PROC / "pv.parquet")
    loads, load_info = build_loads(cfg)
    loads.to_parquet(PROC / "load.parquet")
    prices, price_status = build_prices(cfg)
    prices.to_parquet(PROC / "price.parquet")
    co2 = load_co2_factor(cfg)
    real_iex = prices["B_import"] if price_status["B"]["status"] == "REAL" else None
    days = pick_days(pv.sum(axis=1), loads.sum(axis=1), real_iex, cfg["test_days"]["n_eval_days"])
    meta = {"year": year, "co2": co2, "prices": price_status, "days": days, "load_mapping": load_info,
            "data_status": {"nasa_power": "REAL", "ausgrid": "REAL", "iex": price_status["B"]["status"],
                            "tariff_A": price_status["A"]["status"], "cea": co2["status"]}}
    (PROC / "meta.json").write_text(json.dumps(meta, indent=2, default=str))
    return meta


def load_processed() -> dict:
    return {
        "pv": pd.read_parquet(PROC / "pv.parquet"),
        "load": pd.read_parquet(PROC / "load.parquet"),
        "price": pd.read_parquet(PROC / "price.parquet"),
        "weather": pd.read_parquet(PROC / "weather.parquet"),
        "meta": json.loads((PROC / "meta.json").read_text()),
    }


def day_slice(df: pd.DataFrame | pd.Series, day: str):
    d = pd.Timestamp(day)
    return df.loc[d: d + pd.Timedelta(hours=23, minutes=45)]


if __name__ == "__main__":
    print(json.dumps(build_all(), indent=2, default=str))
