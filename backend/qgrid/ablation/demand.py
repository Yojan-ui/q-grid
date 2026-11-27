"""Demand charge: monthly billing for settlement and the monthly-peak term every planner optimises.

Tariff parameters are read from config.yaml `tariff_ht2c` (BESCOM HT-2(c) educational institutions; added by the
tariff work) and fall back to the older `tariff_v2` stand-in when that section is absent:

  rate          Rs/kVA/month on the billing demand            tariff_ht2c.orders[..].demand_rs_kva_month | tariff_v2
  pf            kVA = kW / pf                                 tariff_ht2c.power_factor | tariff_v2.power_factor
  floor_frac    billing demand >= floor_frac x contract       tariff_ht2c.billing_demand_floor_frac | FALLBACK 0.85
  excess_mult   kVA above contract billed at excess_mult x    tariff_ht2c.excess_demand_multiplier | FALLBACK 2.0
  contract_kva  contract demand of the HT connection          tariff_ht2c.contract_demand_kva | none (no floor/excess)

Monthly bill (settlement):
  MD       = the month's recorded maximum demand (kVA)
  billing  = max(MD, floor_frac x contract)
  charge   = rate x billing + (excess_mult - 1) x rate x max(0, MD - contract)
           (= rate x contract + excess_mult x rate x (MD - contract) when MD exceeds the contract)

Planning term (one decision, all planners identically):
  rate x max(0, P - ref) + (excess_mult - 1) x rate x max(0, P - contract)
  P   = campus peak kVA over the planning horizon (sum of the buildings' grid imports / pf)
  ref = the peak already set this month; in the benchmark (independent sampled days) that is the billing floor
        floor_frac x contract, raised during the day to the campus peak already recorded today (meter reading).
  Without a contract demand (datasets other than RVCE) ref starts at 0: every sampled day is planned as if it
  could set the month's maximum (the largest incentive to shave; documented in docs/handoff/agent-engine/HANDOFF.md).
"""
from __future__ import annotations

import calendar
from datetime import date as _date

import numpy as np

FALLBACK_FLOOR_FRAC = 0.85        # FALLBACK (used only when config has no tariff_ht2c): KERC HT billing-demand floor
FALLBACK_EXCESS_MULT = 2.0        # FALLBACK (used only when config has no tariff_ht2c): excess over contract at 2x


def _d(x) -> _date:
    if isinstance(x, _date):
        return x
    return _date.fromisoformat(str(x)[:10])


def _order(cfg: dict, day) -> dict | None:
    t = cfg.get("tariff_ht2c") or {}
    orders = t.get("orders") or []
    if not orders:
        return None
    try:                                              # the tariff module's own selection when it exists
        from ..v2 import tariff as _tariff
        if hasattr(_tariff, "order_for") and day is not None:
            o = _tariff.order_for(cfg, str(day)[:10])
            if o:
                return o
    except Exception:                                 # noqa: BLE001  (module older than the interface)
        pass
    if day is not None:
        d = _d(day)
        for o in orders:
            lo = _d(o["valid_from"]) if o.get("valid_from") else _date.min
            hi = _d(o["valid_to"]) if o.get("valid_to") else _date.max
            if lo <= d <= hi:
                return o
    return max(orders, key=lambda o: str(o.get("valid_from", "")))   # the latest order


def tariff_params(cfg: dict, day=None, contract_kva: float | None | str = "config") -> dict:
    """Demand-charge parameters for a day. contract_kva: "config" = tariff_ht2c.contract_demand_kva (RVCE),
    None = no contract demand (no floor, no excess), or a number (e.g. a contract-demand sweep)."""
    t = cfg.get("tariff_ht2c")
    tv = cfg.get("tariff_v2", {})
    if t:
        o = _order(cfg, day) or {}
        rate = float(o.get("demand_rs_kva_month", tv.get("demand_rs_per_kva_month", 0.0)))
        pf = float(t.get("power_factor", tv.get("power_factor", 0.95)))
        floor = float(t.get("billing_demand_floor_frac", FALLBACK_FLOOR_FRAC))
        xs = float(t.get("excess_demand_multiplier", FALLBACK_EXCESS_MULT))
        cfg_contract = t.get("contract_demand_kva")
        status, source = str(t.get("status", "")), "tariff_ht2c"
    else:
        rate = float(tv.get("demand_rs_per_kva_month", 0.0))
        pf = float(tv.get("power_factor", 0.95))
        floor, xs, cfg_contract = FALLBACK_FLOOR_FRAC, FALLBACK_EXCESS_MULT, None
        status, source = str(tv.get("status", "")), "tariff_v2 (fallback)"
    contract = cfg_contract if contract_kva == "config" else contract_kva
    contract = None if contract is None else float(contract)
    return {"rate": rate, "pf": pf, "floor_frac": floor, "excess_mult": xs, "contract_kva": contract,
            "status": status, "source": source}


def floor_kva(p: dict) -> float:
    return p["floor_frac"] * p["contract_kva"] if p.get("contract_kva") else 0.0


def monthly_charge(md_kva: float, p: dict) -> dict:
    """Monthly demand charge on a recorded maximum demand md_kva (see module docstring)."""
    md = max(float(md_kva), 0.0)
    billing = max(md, floor_kva(p))
    excess = max(0.0, md - p["contract_kva"]) if p.get("contract_kva") else 0.0
    charge = p["rate"] * billing + (p["excess_mult"] - 1.0) * p["rate"] * excess
    return {"md_kva": md, "billing_kva": billing, "excess_kva": excess, "charge_rs": charge}


def planning_term(peak_kva: float, p: dict, ref_kva: float | None = None) -> float:
    """The monthly-peak term of the planning objective evaluated on a realised campus peak (ref: day-start ref)."""
    ref = floor_kva(p) if ref_kva is None else ref_kva
    c = p["rate"] * max(0.0, peak_kva - ref)
    if p.get("contract_kva"):
        c += (p["excess_mult"] - 1.0) * p["rate"] * max(0.0, peak_kva - p["contract_kva"])
    return c


def planner_params(p: dict, weights) -> dict:
    """What the controllers get (engine ACfg.demand, milp demand_charge, GA/PSO): rate, pf, starting ref, contract,
    excess rate and the static per-building shares used by the decentralised methods."""
    w = np.asarray(weights, float)
    w = w / w.sum() if w.sum() > 0 else np.full(len(w), 1.0 / max(len(w), 1))
    return {"rate": p["rate"], "pf": p["pf"], "ref_kva": floor_kva(p), "contract_kva": p.get("contract_kva"),
            "xs_rate": (p["excess_mult"] - 1.0) * p["rate"], "weights": w.tolist()}


def static_weights(proc: dict, names: list[str]) -> np.ndarray:
    """Offline per-building shares of the campus demand (mean load over the dataset year), used to split the
    campus peak allowance between buildings that do not communicate."""
    m = proc["load"][names].mean().to_numpy(float)
    return np.maximum(m, 0.0)


def monthly_settlement(df, params_for, peak_col: str = "peak_kva", energy_col: str = "cost_rs",
                       group=("dataset", "method")):
    """Monthly billing for a seeded sample of days (not whole months).

    For every (dataset, method, calendar month present in the sample): MD = the maximum of that month's sampled
    daily peaks; the month's charge (monthly_charge) is spread over the calendar days of the month, so each sampled
    day carries charge / days_in_month (a Rs/day figure comparable with the daily energy bill; the mean over days
    estimates the annual bill / 365). Returns df with columns month, md_month_kva, billing_kva_month,
    demand_charge_month_rs, demand_share_rs (Rs/day) and bill_rs = energy + demand_share_rs.
    params_for(dataset, day) -> tariff_params dict."""
    out = df.copy()
    out["month"] = out.day.astype(str).str[:7]
    keys = list(group) + ["month"]
    md = out.groupby(keys)[peak_col].transform("max")
    rows = []
    for (idx, r), m in zip(out.iterrows(), md):
        p = params_for(r["dataset"], r["day"])
        ch = monthly_charge(m, p)
        d = _d(r["day"])
        ndays = calendar.monthrange(d.year, d.month)[1]
        rows.append((m, ch["billing_kva"], ch["charge_rs"], ch["charge_rs"] / ndays))
    a = np.array(rows, float).reshape(-1, 4)
    out["md_month_kva"], out["billing_kva_month"], out["demand_charge_month_rs"], out["demand_share_rs"] = a.T
    out["bill_rs"] = out[energy_col] + out["demand_share_rs"]
    return out
