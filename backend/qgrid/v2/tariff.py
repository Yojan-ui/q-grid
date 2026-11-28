"""Tariffs for the campus HT connection.

1. settle_v2 (unchanged, kept for existing callers): energy charges (price scenario A) plus 1/days_per_month of a monthly
   demand charge on the day's peak kVA (config.yaml: tariff_v2, PENDING stand-in).

2. HT-2(c)(ii) pure-function API (config.yaml: tariff_ht2c). This is the interface the settlement engine reads:
     ht2c_params(cfg)                       resolved parameters (dict)
     order_for(cfg, date)                   the applicable tariff order (switches on 2023-04-01)
     energy_price_slots(cfg, date, ...)     Rs/kWh per slot: energy charge + ToD adder for that month/hour
     monthly_bill(cfg, import_kw, ...)      one month's bill: energy (slabs + ToD), export credit, demand charge on the
                                            billing demand max(recorded MD, 85 % of CD), excess over CD at 2x
   Sources, page numbers and the status of every value are in config.yaml (tariff_ht2c) and docs/data_verification.md.
   The FY2022-23 order is checked against the KERC Tariff Order 2022 (BESCOM) annexure; the FY2023-24 order is NOT
   (its PDF is missing) and stays PENDING.

Conventions (ASSUMPTIONS, stated in config): a billing month is a calendar month (BESCOM bills from meter-reading date
to meter-reading date); the recorded maximum demand is the largest slot-average import kW / power factor; ToD hour
windows are [start, end) in local clock time and wrap past midnight when start > end.
"""
from __future__ import annotations

import datetime as _dt
import math
from typing import Mapping

import numpy as np

from ..model import Campus, DayData, Schedule, settle


# ----------------------------------------------------------------------------- v2 settlement (legacy, unchanged API)
def demand_params(campus: Campus) -> dict:
    tv = campus.cfg["tariff_v2"]
    return {"rate_day": tv["demand_rs_per_kva_month"] / tv["days_per_month"], "pf": float(tv["power_factor"]),
            "rate_month": float(tv["demand_rs_per_kva_month"]), "status": tv["status"]}


def settle_v2(campus: Campus, day: DayData, sched: Schedule) -> dict:
    m = settle(campus, day, sched)
    dp = demand_params(campus)
    peak_kva = m["peak_import_kw"] / dp["pf"]
    dc = dp["rate_day"] * peak_kva
    m.update({"peak_kva": peak_kva, "demand_charge_rs": dc, "demand_charge_month_rs": dp["rate_month"] * peak_kva,
              "cost_incl_demand_rs": m["cost_rs"] + dc, "objective_incl_demand_rs": m["objective_rs"] + dc,
              "tariff_v2_status": dp["status"]})
    return m


# ----------------------------------------------------------------------------- HT-2(c)(ii)
def _date(d) -> _dt.date:
    if isinstance(d, _dt.datetime):
        return d.date()
    if isinstance(d, _dt.date):
        return d
    return _dt.date.fromisoformat(str(d)[:10])


def ht2c_params(cfg: dict) -> dict:
    """Resolved HT-2(c)(ii) parameters from cfg['tariff_ht2c'] (a copy; orders sorted by valid_from)."""
    t = cfg["tariff_ht2c"]
    tod = dict(t["tod"])
    orders = sorted((dict(o) for o in t["orders"]), key=lambda o: o["valid_from"])
    return {
        "status": t["status"], "category": t["category"], "orders": orders, "tod": tod,
        "export_rs_kwh": float(t["export_rs_kwh"]),
        "billing_demand_floor_frac": float(t["billing_demand_floor_frac"]),
        "excess_demand_multiplier": float(t["excess_demand_multiplier"]),
        "power_factor": float(t["power_factor"]),
        "contract_demand_kva": float(t["contract_demand_kva"]),
        "contract_demand_sweep": [float(x) for x in t.get("contract_demand_sweep", [])],
        "round_billing_demand": bool(t.get("round_billing_demand", True)),
    }


def order_for(cfg: dict, date) -> dict:
    """The tariff order in force on `date` (valid_from <= date <= valid_to). Raises if no order covers the date."""
    d = _date(date)
    for o in ht2c_params(cfg)["orders"]:
        if _date(o["valid_from"]) <= d <= _date(o["valid_to"]):
            return o
    raise ValueError(f"tariff_ht2c: no order covers {d.isoformat()}")


def _tod_min_kva(p: dict, order: dict) -> float:
    v = order.get("tod_min_contract_kva")
    return float(p["tod"]["min_contract_kva"] if v is None else v)


def tod_applies(cfg: dict, date, contract_kva: float | None = None) -> bool:
    p = ht2c_params(cfg)
    d = _date(date)
    cd = p["contract_demand_kva"] if contract_kva is None else float(contract_kva)
    return d.month in [int(m) for m in p["tod"]["months"]] and cd >= _tod_min_kva(p, order_for(cfg, d))


def _in_window(h: np.ndarray, win) -> np.ndarray:
    a, b = float(win[0]), float(win[1])
    return (h >= a) & (h < b) if a < b else (h >= a) | (h < b)


def tod_adder_slots(cfg: dict, date, n_slots: int = 96, contract_kva: float | None = None) -> np.ndarray:
    """Rs/kWh ToD increase (+) / reduction (-) per slot over the normal energy charge (zeros when ToD does not apply)."""
    out = np.zeros(n_slots)
    if not tod_applies(cfg, date, contract_kva):
        return out
    tod = ht2c_params(cfg)["tod"]
    h = np.arange(n_slots) * 24.0 / n_slots          # slot start hour
    out[_in_window(h, tod["peak_hours"])] += float(tod["peak_adder_rs_kwh"])
    out[_in_window(h, tod["offpeak_hours"])] += float(tod["offpeak_adder_rs_kwh"])
    return out


def energy_price_slots(cfg: dict, date, n_slots: int = 96, contract_kva: float | None = None) -> np.ndarray:
    """Rs/kWh per slot on `date`: the order's energy_rs_kwh (the marginal slab rate, see config) + the ToD adder.
    ToD applies only in tod.months and only if the contract demand >= the threshold (tod.min_contract_kva, or the
    order's own tod_min_contract_kva when given)."""
    o = order_for(cfg, date)
    return float(o["energy_rs_kwh"]) + tod_adder_slots(cfg, date, n_slots, contract_kva)


def slab_energy_rs(order: dict, kwh: float) -> float:
    """Energy charge (Rs) for `kwh` units in one month under the order's slabs ([{upto_kwh, rs_kwh}], last upto null);
    flat energy_rs_kwh when the order has no slabs."""
    slabs = order.get("energy_slabs")
    if not slabs:
        return float(order["energy_rs_kwh"]) * kwh
    rs, lo = 0.0, 0.0
    for s in slabs:
        hi = math.inf if s.get("upto_kwh") is None else float(s["upto_kwh"])
        q = max(0.0, min(kwh, hi) - lo)
        rs += q * float(s["rs_kwh"])
        lo = hi
        if kwh <= hi:
            break
    return rs


def _as_days(x, dates) -> dict[str, np.ndarray]:
    if x is None:
        return {}
    if isinstance(x, Mapping):
        return {str(_date(k)): np.asarray(v, float) for k, v in x.items()}
    arr = np.atleast_2d(np.asarray(x, float))
    if dates is None or len(dates) != arr.shape[0]:
        raise ValueError("monthly_bill: a 2-D array needs `dates` with one date per row")
    return {str(_date(d)): arr[i] for i, d in enumerate(dates)}


def _round_half_up(x: float) -> float:
    return float(math.floor(x + 0.5))


def monthly_bill(cfg: dict, import_kw, export_kw=None, contract_kva: float | None = None, dates=None,
                 pf: float | None = None) -> dict:
    """One month's HT-2(c)(ii) bill (Rs, before electricity tax and fuel-cost adjustment).

    import_kw / export_kw: per-slot campus import / export kW for every day of ONE calendar month, either a dict
    {date: array(n_slots)} or a 2-D array (days x n_slots) with `dates`. Slot length = 24 h / n_slots.
      energy_rs          slab energy charge on the month's kWh + sum over slots of ToD adder x kWh
      export_credit_rs   export kWh x export_rs_kwh
      recorded_max_kva   max slot import kW / pf (rounded half-up to whole kVA if round_billing_demand)
      billing_demand_kva max(recorded_max_kva, billing_demand_floor_frac x contract demand)
      demand_rs          demand rate x min(billing_demand_kva, contract demand)
      excess_rs          excess_demand_multiplier x demand rate x max(recorded_max_kva - contract demand, 0)
      total_rs           energy_rs + demand_rs + excess_rs - export_credit_rs
    """
    p = ht2c_params(cfg)
    imp = _as_days(import_kw, dates)
    exp = _as_days(export_kw, dates)
    if not imp:
        raise ValueError("monthly_bill: no days given")
    days = sorted(imp)
    months = {d[:7] for d in days} | {d[:7] for d in exp}
    if len(months) != 1:
        raise ValueError(f"monthly_bill: days span more than one calendar month: {sorted(months)}")
    order = order_for(cfg, days[0])
    if len({order_for(cfg, d)["valid_from"] for d in days}) != 1:
        raise ValueError("monthly_bill: days fall under different tariff orders")
    cd = p["contract_demand_kva"] if contract_kva is None else float(contract_kva)
    pf = p["power_factor"] if pf is None else float(pf)
    rate = float(order["demand_rs_kva_month"])

    kwh_total, tod_rs, peak_kw = 0.0, 0.0, 0.0
    for d in days:
        kw = np.maximum(imp[d], 0.0)
        dt_h = 24.0 / len(kw)
        kwh = kw * dt_h
        kwh_total += float(kwh.sum())
        tod_rs += float((tod_adder_slots(cfg, d, len(kw), cd) * kwh).sum())
        peak_kw = max(peak_kw, float(kw.max()))
    export_kwh = 0.0
    for d, v in exp.items():
        v = np.maximum(v, 0.0)
        export_kwh += float(v.sum() * 24.0 / len(v))

    base_rs = slab_energy_rs(order, kwh_total)
    energy_rs = base_rs + tod_rs
    export_credit_rs = p["export_rs_kwh"] * export_kwh
    rec = peak_kw / pf
    if p["round_billing_demand"]:
        rec = _round_half_up(rec)
    billing = max(rec, p["billing_demand_floor_frac"] * cd)
    demand_rs = rate * min(billing, cd)
    excess_kva = max(rec - cd, 0.0)
    excess_rs = p["excess_demand_multiplier"] * rate * excess_kva
    total = energy_rs + demand_rs + excess_rs - export_credit_rs
    return {
        "month": days[0][:7], "n_days": len(days), "order": order, "order_label": order.get("source", ""),
        "order_status": order.get("status", p["status"]), "tariff_status": p["status"],
        "contract_kva": cd, "power_factor": pf,
        "import_kwh": kwh_total, "export_kwh": export_kwh,
        "energy_base_rs": base_rs, "tod_rs": tod_rs, "energy_rs": energy_rs,
        "export_credit_rs": export_credit_rs,
        "peak_import_kw": peak_kw, "recorded_max_kva": rec, "billing_demand_kva": billing,
        "excess_kva": excess_kva, "demand_rs": demand_rs, "excess_rs": excess_rs, "total_rs": total,
    }
