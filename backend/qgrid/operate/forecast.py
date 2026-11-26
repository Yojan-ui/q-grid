"""Live weather for RVCE from Open-Meteo (https://open-meteo.com, CC BY 4.0): hourly shortwave radiation, temperature and
cloud cover for yesterday, today and tomorrow, refreshed at most once an hour and cached on disk. Offline, the newest
cache is used and labelled with its fetch time; with no cache at all the caller falls back to a historical day."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

LAT, LON = 12.92, 77.50
IST = timezone(timedelta(hours=5, minutes=30))
URL = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
       "&hourly=shortwave_radiation,temperature_2m,cloud_cover&past_days=1&forecast_days=2&timezone=Asia%2FKolkata")
LABEL = "Live forecast, Open-Meteo"


class OpenMeteo:
    def __init__(self, cache_dir: Path, max_age_s: float = 3600.0):
        self.dir = Path(cache_dir); self.dir.mkdir(parents=True, exist_ok=True)
        self.max_age = max_age_s
        self.data: dict | None = None
        self.fetched_at: float | None = None
        self.error: str | None = None
        self._load_cache()

    def _load_cache(self):
        files = sorted(self.dir.glob("open_meteo_*.json"))
        if files:
            d = json.loads(files[-1].read_text())
            self.data, self.fetched_at = d["data"], d["fetched_at"]

    def refresh(self, force: bool = False) -> bool:
        """Fetch if the cache is older than max_age. Returns True if new data arrived."""
        if not force and self.fetched_at and time.time() - self.fetched_at < self.max_age:
            return False
        try:
            import httpx
            r = httpx.get(URL.format(lat=LAT, lon=LON), timeout=10.0)
            r.raise_for_status()
            data = r.json()
            assert "hourly" in data and data["hourly"]["shortwave_radiation"]
        except Exception as e:                                     # offline: keep the cache, say so
            self.error = f"{type(e).__name__}: {e}"[:160]
            return False
        self.data, self.fetched_at, self.error = data, time.time(), None
        stamp = datetime.fromtimestamp(self.fetched_at, IST).strftime("%Y%m%d%H%M")
        (self.dir / f"open_meteo_{stamp}.json").write_text(json.dumps({"fetched_at": self.fetched_at, "data": data}))
        for old in sorted(self.dir.glob("open_meteo_*.json"))[:-48]:   # keep two days of hourly fetches
            old.unlink(missing_ok=True)
        return True

    @property
    def available(self) -> bool:
        return self.data is not None

    def series(self, start: datetime, n15: int) -> dict:
        """15-minute series from `start` (IST): ghi W/m2, temperature C, cloud %, linearly interpolated from hourly."""
        h = self.data["hourly"]
        t = np.array([datetime.fromisoformat(x).replace(tzinfo=IST).timestamp() for x in h["time"]])
        q = start.timestamp() + 900.0 * np.arange(n15) + 450.0                # slot midpoints
        f = lambda k: np.interp(q, t, np.asarray(h[k], float), left=np.nan, right=np.nan)   # noqa: E731
        ghi, tc, cc = f("shortwave_radiation"), f("temperature_2m"), f("cloud_cover")
        return {"ghi": np.nan_to_num(ghi, nan=0.0).clip(min=0), "t2m": np.nan_to_num(tc, nan=25.0), "cloud": np.nan_to_num(cc, nan=0.0),
                "covered": ~np.isnan(ghi)}

    def meta(self) -> dict:
        return {"label": LABEL, "source": "Open-Meteo (open-meteo.com, CC BY 4.0)", "lat": LAT, "lon": LON,
                "fetched_at": self.fetched_at, "fetched_at_ist": datetime.fromtimestamp(self.fetched_at, IST).strftime("%d %b %H:%M") if self.fetched_at else None,
                "error": self.error, "available": self.available}


def pv_kw(ghi: np.ndarray, t2m: np.ndarray, kwp: float, pv_model: dict) -> np.ndarray:
    """Same PVWatts-style model as the data pipeline (qgrid.data.pv_output_kw)."""
    tcell = t2m + (pv_model["noct_c"] - 20.0) / 800.0 * ghi
    return np.clip(kwp * ghi / 1000.0 * (1 + pv_model["gamma_per_c"] * (tcell - 25.0)) * pv_model["system_derate"], 0, kwp)
