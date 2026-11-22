"""Realistic forecasts for factor D: gradient-boosted trees (scikit-learn HistGradientBoostingRegressor) for solar
per kWp and for each zone's load, issued at the decision slot for lead times 1..96 slots.

Features use only information available at issue time g0 (observations before g0, calendar, clear-sky):
  solar: lead, target time of day, day of year (sin/cos), clear-sky PV per kWp at the target (NASA POWER CLRSKY),
         clearness of the last observed hour, clearness of the previous day, PV per kWp 24 h before the target
  load:  lead, target time of day, weekday, RVCE day type (calendar), load 24 h and 7 days before the target,
         last observed load, previous day's mean load
Training: every 2nd hour of 2023 as issue time, excluding the 30 evaluation days (and the day before/after) and
the six named scenario days, which are held out. A deployed system would train on past data only; here other
2023 days stand in for "past" (stated in docs/ablation.md). Critical load = forecast load x the zone's
critical share at the target (a fixed property of the zone, not a forecast).
"""
from __future__ import annotations

import pickle
from dataclasses import replace
from pathlib import Path

import numpy as np

from .. import data as qdata
from ..model import T, Campus
from ..v2.horizon import SolarForecast, Window, YearData

DTYPES = ["teaching", "exam", "vacation", "holiday", "fest"]


def _hgb():
    from sklearn.ensemble import HistGradientBoostingRegressor
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=40,
                                         random_state=0)


class GBMForecaster:
    def __init__(self, campus: Campus, proc: dict, yd: YearData, holdout_days: list[str], cache: Path | None = None):
        self.campus, self.yd = campus, yd
        self.sf = SolarForecast(int(yd.index[0].year), arrays=getattr(yd, "arrays", None))
        self.act, self.cs = self.sf.act, self.sf.cs
        cfg = campus.cfg
        dt = proc["day_type"] if "day_type" in proc else qdata.day_types(cfg).reindex(yd.index.normalize()).to_numpy()
        self.dtype = np.array([DTYPES.index(d) if d in DTYPES else 0 for d in dt])
        self.N = yd.pv.shape[1]
        self.hold = set()
        for d in holdout_days:
            k = yd.day_start(d) // T
            self.hold.update({k - 1, k, k + 1})
        self.models = None
        if cache and cache.exists():
            obj = pickle.loads(cache.read_bytes())
            if obj.get("holdout") == sorted(self.hold):
                self.models = obj["models"]
        if self.models is None:
            self.models = self._train()
            if cache:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_bytes(pickle.dumps({"holdout": sorted(self.hold), "models": self.models}))

    # ---------------------------------------------------------------- features
    def _kt(self, a, b):
        num, den = self.act[a:b].sum(), self.cs[a:b].sum()
        return float(np.clip(num / den, 0, 1.2)) if den > 1e-3 else np.nan

    def _solar_X(self, g0: int, H: int) -> np.ndarray:
        tgt = np.clip(np.arange(g0, g0 + H), 0, self.N - 1)
        d0 = (g0 // T) * T
        kt_now = self._kt(max(0, g0 - 4), g0) if g0 > 0 else np.nan
        kt_y = self._kt(max(0, d0 - T), d0) if d0 > 0 else np.nan
        tod = (tgt % T) / T
        doy = (tgt // T) / 365.0
        pers = self.act[np.clip(tgt - T, 0, None)]
        return np.column_stack([np.arange(1, H + 1), tod, np.sin(2 * np.pi * doy), np.cos(2 * np.pi * doy),
                                self.cs[tgt], np.full(H, kt_now), np.full(H, kt_y), pers])

    def _load_X(self, i: int, g0: int, H: int) -> np.ndarray:
        L = self.yd.load[i]
        tgt = np.clip(np.arange(g0, g0 + H), 0, self.N - 1)
        last = L[g0 - 1] if g0 > 0 else L[0]
        d0 = (g0 // T) * T
        ymean = L[max(0, d0 - T):d0].mean() if d0 > 0 else L[:T].mean()
        wk = self.yd.index[tgt].weekday.to_numpy()
        return np.column_stack([np.arange(1, H + 1), (tgt % T) / T, wk, self.dtype[tgt],
                                L[np.clip(tgt - T, 0, None)], L[np.clip(tgt - 7 * T, 0, None)], np.full(H, last),
                                np.full(H, ymean)])

    def _train(self) -> dict:
        issues = [g for g in range(7 * T, self.N - T, 8) if (g // T) not in self.hold]
        Xs, ys = [], []
        for g in issues:
            Xs.append(self._solar_X(g, T)); ys.append(self.act[g:g + T])
        models = {"solar": _hgb().fit(np.vstack(Xs), np.concatenate(ys))}
        for i, b in enumerate(self.campus.buildings):
            L = self.yd.load[i]
            if L.max() <= 1e-9 or np.ptp(L) < 1e-6:
                models[b.name] = None                              # flat or no load: forecast = last value
                continue
            Xs, ys = [], []
            for g in issues:
                Xs.append(self._load_X(i, g, T)); ys.append(L[g:g + T])
            models[b.name] = _hgb().fit(np.vstack(Xs), np.concatenate(ys))
        return models

    # ---------------------------------------------------------------- forecasts
    def solar_per_kwp(self, g0: int, H: int) -> np.ndarray:
        return np.maximum(self.models["solar"].predict(self._solar_X(g0, H)), 0.0) * (self.cs[np.clip(np.arange(g0, g0 + H), 0, self.N - 1)] > 0)

    def load(self, i: int, g0: int, H: int) -> np.ndarray:
        m = self.models[self.campus.buildings[i].name]
        L = self.yd.load[i]
        if m is None:
            return np.full(H, L[g0 - 1] if g0 > 0 else L[0])
        return np.maximum(m.predict(self._load_X(i, g0, H)), 0.0)

    def window(self, day0: int, t0: int, H: int, outage) -> Window:
        w = self.yd.window(day0, t0, H, outage)
        g0 = day0 + t0
        pv = self.yd.kwp[:, None] * self.solar_per_kwp(g0, H)[None, :]
        load = np.vstack([self.load(i, g0, H) for i in range(self.campus.n)])
        with np.errstate(divide="ignore", invalid="ignore"):
            share = np.where(w.load > 1e-9, w.crit / w.load, 0.0)
        return replace(w, pv=pv, load=load, crit=np.minimum(load * share, load))


def forecast_errors(fc: GBMForecaster, days: list[str]) -> dict:
    """MAE of forecasts issued every hour of the given days (lead 1..96), solar (campus kW) and load (campus kW)."""
    yd = fc.yd
    kwp = yd.kwp.sum()
    rows = {"solar": [], "load": []}
    for d in days:
        d0 = yd.day_start(d)
        for t0 in range(0, T, 4):
            g0 = d0 + t0
            idx = np.clip(np.arange(g0, g0 + T), 0, fc.N - 1)
            ps = kwp * fc.solar_per_kwp(g0, T); pa = yd.pv[:, idx].sum(0)
            ls = sum(fc.load(i, g0, T) for i in range(fc.campus.n)); la = yd.load[:, idx].sum(0)
            rows["solar"].append((ps, pa)); rows["load"].append((ls, la))
    out = {}
    lead = np.arange(1, T + 1)
    for k, lst in rows.items():
        F_ = np.concatenate([a for a, _ in lst]); A_ = np.concatenate([b for _, b in lst]); Ld = np.tile(lead, len(lst))
        mask = A_ > 0.02 * A_.max() if k == "solar" else np.ones_like(A_, bool)
        out[f"{k}_mae_kw"] = float(np.abs(F_ - A_)[mask].mean())
        out[f"{k}_nmae_pct"] = 100 * out[f"{k}_mae_kw"] / float(A_[mask].mean())
        for lo, hi, nm in ((1, 4, "1h"), (5, 16, "1-4h"), (17, 96, "4-24h")):
            mm = mask & (Ld >= lo) & (Ld <= hi)
            out[f"{k}_nmae_{nm}_pct"] = 100 * float(np.abs(F_ - A_)[mm].mean()) / float(A_[mask].mean())
    return out
