"""Building Data Genome Project 2 (BDG2) education-campus meter data -> per-zone load shapes.

Source: Miller et al., "The Building Data Genome Project 2, energy meter data from the ASHRAE Great Energy
Predictor III competition", Scientific Data 7, 368 (2020); data github.com/buds-lab/building-data-genome-project-2,
licence CC BY-SA 4.0 (data/raw/bdg2/LICENSE). Hourly whole-building electricity, 2016-2017, 1,578 buildings.

For each zone type (config.yaml: bdg2.zones) the buildings of the mapped primary/sub use are kept if >= 90 % of
hours are present; each building's series is divided by its own mean and the zone-type shape is the median
across buildings per hour (real meters, no template). Every 2023 date takes the shape of one real 2016/17
source day of the matching kind:
  RVCE teaching / exam / fest weekday -> a source term-time weekday (same weekday where possible)
  RVCE vacation                       -> a source break weekday   (June-August, 20 Dec - 5 Jan: ASSUMPTION)
  RVCE holiday (Sat/Sun)              -> a source term-time weekend day
chosen deterministically (seeded by zone and date). Annual energy still comes from floor area x EPI.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

RAW = Path(__file__).resolve().parents[2] / "data" / "raw" / "bdg2"
METERS = RAW / "electricity_cleaned.csv"
META = RAW / "metadata.csv"


def available() -> bool:
    return METERS.exists() and META.exists()


@lru_cache(maxsize=1)
def _meters() -> tuple[pd.DataFrame, pd.DataFrame]:
    el = pd.read_csv(METERS, index_col=0, parse_dates=True)
    md = pd.read_csv(META).set_index("building_id")
    return el, md


def _is_break(d: pd.Timestamp) -> bool:
    return d.month in (6, 7, 8) or (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 5)


@lru_cache(maxsize=16)
def zone_type_shape(primary: str, subs: tuple[str, ...], min_coverage: float = 0.9) -> tuple[pd.Series, dict]:
    """Median of mean-normalised hourly series over the qualifying buildings; (series, info)."""
    el, md = _meters()
    ids = [b for b in md.index[(md.primaryspaceusage == primary) & (md.sub_primaryspaceusage.isin(subs))] if b in el.columns]
    x = el[ids]
    ok = [b for b in ids if x[b].notna().mean() >= min_coverage and x[b].mean() > 1.0]
    if not ok:
        raise ValueError(f"no BDG2 buildings for {primary}/{subs}")
    xn = x[ok].clip(upper=x[ok].quantile(0.999), axis=1)
    xn = xn / xn.mean()
    s = xn.median(axis=1, skipna=True).interpolate(limit=6).bfill().ffill()
    info = {"primary": primary, "subs": list(subs), "buildings": len(ok),
            "sites": md.loc[ok, "site_id"].value_counts().to_dict()}
    return s, info


def day_pools(s: pd.Series) -> dict:
    days = {}
    for d, g in s.groupby(s.index.normalize()):
        if len(g) != 24:
            continue
        kind = ("break" if _is_break(d) else "term") + ("_weekend" if d.weekday() >= 5 else "_weekday")
        days.setdefault(kind, []).append((d, g.to_numpy()))
    return days


def year_shape(zone: str, primary: str, subs: list[str], idx15: pd.DatetimeIndex, day_type: np.ndarray) -> tuple[np.ndarray, dict]:
    """15-min relative load for every slot of idx15 (day_type per slot from the RVCE calendar)."""
    s, info = zone_type_shape(primary, tuple(subs))
    pools = day_pools(s)
    want = {"teaching": "term_weekday", "exam": "term_weekday", "fest": "term_weekday",
            "vacation": "break_weekday", "holiday": "term_weekend"}
    out = np.empty(len(idx15))
    dates = idx15.normalize()
    seed0 = sum(ord(c) for c in zone)
    used = {}
    for d in pd.unique(dates):
        d = pd.Timestamp(d)
        m = dates == d
        dt = day_type[np.argmax(m)]
        pool = pools.get(want.get(dt, "term_weekday")) or pools["term_weekday"]
        same = [p for p in pool if p[0].weekday() == d.weekday()] or pool
        rng = np.random.default_rng(seed0 * 100003 + d.dayofyear)
        src_day, shape = same[int(rng.integers(len(same)))]
        out[m] = np.repeat(shape, 4)[: m.sum()]
        used[str(d.date())] = str(src_day.date())
    info = {**info, "pool_sizes": {k: len(v) for k, v in pools.items()}, "n_source_days_used": len(set(used.values()))}
    return out, info
