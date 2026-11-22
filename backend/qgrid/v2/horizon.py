"""Rolling-horizon data for the v2 optimiser: actual year series from data/processed plus a solar forecast.

Solar forecast (uses only data observed before the decision slot):
  PV_fc(t0 + k) = kWp * PVclear(t0 + k) * kt(k)
  PVclear       = the same PV model driven by NASA POWER clear-sky irradiance (CLRSKY_SFC_SW_DWN)
  kt(k)         = w(k) * kt_last_hour + (1 - w(k)) * kt_yesterday,  w(k) = exp(-k / tau)
  kt_last_hour  = observed PV / clear-sky PV over the last hour (persistence of clearness)
  kt_yesterday  = the same ratio over the whole previous day
Loads, critical loads, water demand, prices and the outage window are taken as known (modelled profiles and
a published tariff); only solar is forecast.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

from .. import data as qdata
from ..model import T, Campus, hhmm_to_slot

RAW_CS = qdata.ROOT / "data" / "raw" / "nasa_power"


@lru_cache(maxsize=2)
def _per_kwp(year: int) -> tuple[np.ndarray, np.ndarray]:
    """(actual, clear-sky) PV output per kWp for every 15-min slot of the year."""
    cfg = qdata.load_config()
    w = qdata.load_weather(year)
    act = qdata.pv_output_kw(w, 1.0, cfg["pv_model"]).to_numpy()
    p = json.loads((RAW_CS / f"bengaluru_{year}_hourly_clearsky.json").read_text())["properties"]["parameter"]
    cs_h = pd.Series(list(p["CLRSKY_SFC_SW_DWN"].values()),
                     index=pd.to_datetime(list(p["CLRSKY_SFC_SW_DWN"].keys()), format="%Y%m%d%H"))
    cs_h = cs_h.where(cs_h >= 0, 0.0).reindex(w.index, method="ffill").fillna(0.0)
    wcs = w.copy()
    wcs["ghi_wm2"] = cs_h.to_numpy()
    cs = qdata.pv_output_kw(wcs, 1.0, cfg["pv_model"]).to_numpy()
    return act, np.maximum(cs, act)          # clear-sky envelope never below the observed output


def _ratio(num: np.ndarray, den: np.ndarray, default: float) -> float:
    d = float(den.sum())
    return float(np.clip(num.sum() / d, 0.0, 1.2)) if d > 1e-3 else default


class SolarForecast:
    def __init__(self, year: int, tau_slots: float = 16.0):
        self.act, self.cs = _per_kwp(year)
        self.tau = tau_slots

    def kt(self, g0: int, H: int) -> np.ndarray:
        """Clearness-index path for absolute slots g0 .. g0+H-1, using observations before g0 only."""
        d0 = (g0 // T) * T
        yd = slice(max(0, d0 - T), d0) if d0 > 0 else slice(0, 0)
        kt_y = _ratio(self.act[yd], self.cs[yd], 0.75) if d0 > 0 else 0.75
        last = slice(max(0, g0 - 4), g0)
        kt_now = _ratio(self.act[last], self.cs[last], np.nan) if g0 > 0 else np.nan
        k = np.arange(H)
        if np.isnan(kt_now):
            return np.full(H, kt_y)
        w = np.exp(-k / self.tau)
        return w * kt_now + (1 - w) * kt_y

    def per_kwp(self, g0: int, H: int) -> np.ndarray:
        idx = np.clip(np.arange(g0, g0 + H), 0, len(self.cs) - 1)
        return self.cs[idx] * self.kt(g0, H)


@dataclass
class Window:
    """Horizon arrays for absolute slots g0 .. g0+H-1 (n zones)."""
    g0: int
    pv: np.ndarray          # (n, H) kW — forecast (or actual in perfect-forecast mode)
    load: np.ndarray        # (n, H)
    crit: np.ndarray        # (n, H)
    water: np.ndarray       # (H,)
    pi: np.ndarray          # import price incl. CO2 shadow price (H,)
    pe: np.ndarray          # export price (H,)
    grid: np.ndarray        # (H,) bool
    today: np.ndarray       # (H,) bool: slot belongs to the day being operated
    term_value: float       # Rs per kWh stored at the horizon end


class YearData:
    """Year arrays for one price scenario; the outage window applies to the operated day only."""

    def __init__(self, campus: Campus, proc: dict, scenario: str, forecast: bool, tau: float = 16.0):
        names = campus.names
        self.campus = campus
        self.pv = proc["pv"][names].to_numpy().T
        self.load = proc["load"][names].to_numpy().T
        self.crit = proc["crit"][names].to_numpy().T
        self.water = proc["water"].to_numpy()
        pr = proc["price"]
        lam = float(campus.cfg["co2"]["lambda_rs_per_kg"])
        ef = float(proc["meta"]["co2"]["tco2_per_mwh"])
        self.pi = pr[f"{scenario}_import"].to_numpy() + lam * ef
        self.pi_raw = pr[f"{scenario}_import"].to_numpy()
        self.pe = pr[f"{scenario}_export"].to_numpy()
        self.index = proc["pv"].index
        self.kwp = np.array([b.pv_kwp for b in campus.buildings])
        self.fc = SolarForecast(int(self.index[0].year), tau) if forecast else None

    def day_start(self, day: str) -> int:
        return int(np.searchsorted(self.index, pd.Timestamp(day)))

    def window(self, day0: int, t0: int, H: int, outage: list[str] | None) -> Window:
        g0 = day0 + t0
        N = self.pv.shape[1]
        idx = np.arange(g0, g0 + H)
        cl = np.clip(idx, 0, N - 1)               # past the last day of the year: repeat the final slot
        grid = np.ones(H, bool)
        if outage:
            a, b = hhmm_to_slot(outage[0]), hhmm_to_slot(outage[1])
            rel = idx - day0
            grid[(rel >= a) & (rel < b)] = False
        if self.fc is None:
            pv = self.pv[:, cl]
        else:
            pv = self.kwp[:, None] * self.fc.per_kwp(g0, H)[None, :]
        day_pi = self.pi_raw[day0:day0 + T]
        return Window(g0, pv, self.load[:, cl], self.crit[:, cl], self.water[cl], self.pi[cl], self.pe[cl], grid,
                      (idx - day0) < T, float(day_pi.mean()))


def forecast_error(yd: YearData, day: str, horizon: int = 96) -> dict:
    """Errors of every forecast issued during `day` (one per slot, lead times 1..horizon) against actual PV."""
    assert yd.fc is not None
    d0 = yd.day_start(day)
    act_all, fc_all, lead = [], [], []
    tot_act = yd.pv.sum(axis=0)
    for t0 in range(T):
        g0 = d0 + t0
        fc = yd.kwp.sum() * yd.fc.per_kwp(g0, horizon)
        a = tot_act[np.clip(np.arange(g0, g0 + horizon), 0, tot_act.size - 1)]
        act_all.append(a); fc_all.append(fc); lead.append(np.arange(1, horizon + 1))
    A, Fc, L = np.concatenate(act_all), np.concatenate(fc_all), np.concatenate(lead)
    day_mask = A > 0.02 * max(A.max(), 1e-9)
    mean_act = float(A[day_mask].mean()) if day_mask.any() else 1.0
    out = {"day": day, "nmae_pct": 100 * float(np.abs(Fc - A)[day_mask].mean()) / mean_act,
           "nrmse_pct": 100 * float(np.sqrt(((Fc - A)[day_mask] ** 2).mean())) / mean_act,
           "bias_pct": 100 * float((Fc - A)[day_mask].mean()) / mean_act}
    for lo, hi, nm in ((1, 4, "1h"), (5, 16, "1-4h"), (17, 96, "4-24h")):
        m = day_mask & (L >= lo) & (L <= hi)
        out[f"nmae_{nm}_pct"] = 100 * float(np.abs(Fc - A)[m].mean()) / mean_act if m.any() else np.nan
    return out
