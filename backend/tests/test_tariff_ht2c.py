"""HT-2(c)(ii) tariff API (qgrid.v2.tariff): a full month's bill computed by hand, the 1 Apr 2023 order switch, ToD
months and contract-demand threshold, the 85 % billing-demand floor and excess demand at 2x.
Load profiles here are SYNTHETIC (unit-test inputs only)."""
import copy

import numpy as np
import pytest

from qgrid import data as qd
from qgrid.v2.tariff import energy_price_slots, ht2c_params, monthly_bill, order_for, tod_adder_slots


@pytest.fixture(scope="module")
def cfg():
    return qd.load_config()


def _month(year, month, n_days, base_kw=400.0, n=96):
    return {f"{year}-{month:02d}-{d:02d}": np.full(n, base_kw) for d in range(1, n_days + 1)}


def test_config_interface(cfg):
    p = ht2c_params(cfg)
    for k in ("status", "category", "orders", "tod", "export_rs_kwh", "billing_demand_floor_frac",
              "excess_demand_multiplier", "power_factor", "contract_demand_kva", "contract_demand_sweep"):
        assert k in p
    assert p["contract_demand_sweep"] == [1000.0, 1300.0, 1600.0]
    assert p["contract_demand_kva"] == 1300.0
    for o in p["orders"]:
        assert {"valid_from", "valid_to", "energy_rs_kwh", "demand_rs_kva_month", "source", "page", "status"} <= set(o)
    assert p["status"] != "REAL" or all(o["status"] == "VERIFIED" for o in p["orders"])


def test_order_switch_on_1_april_2023(cfg):
    assert order_for(cfg, "2023-03-31")["valid_from"] == "2022-04-01"      # FY2022-23 (TO-2022)
    assert order_for(cfg, "2023-04-01")["valid_from"] == "2023-04-01"      # FY2023-24 (TO-2023)
    # identity of the order used, independent of the rates (FY2023-24 currently carries the TO-2022 values over)
    assert "Tariff Order 2022" in order_for(cfg, "2023-03-31")["source"]
    assert "Tariff Order 2023" in order_for(cfg, "2023-04-01")["source"]
    assert order_for(cfg, "2023-03-31")["status"] == "VERIFIED"
    assert order_for(cfg, "2023-04-01")["status"] == "PENDING_CARRIED_OVER"
    assert order_for(cfg, "2024-03-31")["valid_from"] == "2023-04-01"
    a = energy_price_slots(cfg, "2023-03-31")
    b = energy_price_slots(cfg, "2023-04-01")
    o22, o23 = order_for(cfg, "2023-03-31"), order_for(cfg, "2023-04-01")
    # both dates are in ToD months (Mar, Apr): slot 48 (12:00) carries no adder, so it is the bare energy rate
    assert a[48] == pytest.approx(o22["energy_rs_kwh"]) and b[48] == pytest.approx(o23["energy_rs_kwh"])
    with pytest.raises(ValueError):
        order_for(cfg, "2021-12-01")


def test_tod_present_dec_to_jun_absent_jul_to_nov(cfg):
    for m in (12, 1, 2, 3, 4, 5, 6):
        y = 2022 if m == 12 else 2023
        add = tod_adder_slots(cfg, f"{y}-{m:02d}-15", contract_kva=1300)
        assert add[18 * 4] == 1.00 and add[21 * 4 + 3] == 1.00       # 18:00 .. 21:45 peak
        assert add[22 * 4] == -1.00 and add[0] == -1.00 and add[6 * 4 - 1] == -1.00   # 22:00 .. 05:45 off-peak
        assert add[6 * 4] == 0.0 and add[12 * 4] == 0.0 and add[18 * 4 - 1] == 0.0    # 06:00 .. 17:45 normal
        assert add.sum() == pytest.approx(16 * 1.0 - 32 * 1.0)
    for m in (7, 8, 9, 10, 11):
        assert not tod_adder_slots(cfg, f"2023-{m:02d}-15", contract_kva=1300).any()


def test_tod_absent_below_500_kva(cfg):
    # FY2023-24 order: threshold tod.min_contract_kva = 500 (TEAM BRIEF)
    assert not tod_adder_slots(cfg, "2023-05-10", contract_kva=499).any()
    assert tod_adder_slots(cfg, "2023-05-10", contract_kva=500).any()
    p = energy_price_slots(cfg, "2023-05-10", contract_kva=400)
    assert np.all(p == order_for(cfg, "2023-05-10")["energy_rs_kwh"])
    # FY2022-23 order: TO-2022 states ToD for HT-2(c) with no threshold (tod_min_contract_kva: 0)
    assert tod_adder_slots(cfg, "2023-01-10", contract_kva=400).any()
    # the threshold is configurable
    c2 = copy.deepcopy(cfg)
    c2["tariff_ht2c"]["orders"][0]["tod_min_contract_kva"] = None       # fall back to tod.min_contract_kva
    assert not tod_adder_slots(c2, "2023-01-10", contract_kva=400).any()


def test_full_month_bill_by_hand(cfg):
    """January 2023 (FY2022-23 order, ToD season), CD 1300 kVA, pf 0.95.
    Import 400 kW in every 15-min slot of all 31 days, except 2023-01-10 slot 76 (19:00-19:15) = 1140 kW.
    Export 50 kW in slots 40..47 (10:00-12:00) every day."""
    o = order_for(cfg, "2023-01-15")
    # the verified TO-2022 HT-2(c)(ii) values the arithmetic below uses (p.412)
    assert o["energy_slabs"] == [{"upto_kwh": 100000, "rs_kwh": 8.25}, {"upto_kwh": None, "rs_kwh": 8.65}]
    assert o["demand_rs_kva_month"] == 265
    assert ht2c_params(cfg)["export_rs_kwh"] == 3.74
    imp = _month(2023, 1, 31)
    imp["2023-01-10"][76] = 1140.0
    exp = {d: np.zeros(96) for d in imp}
    for d in exp:
        exp[d][40:48] = 50.0
    b = monthly_bill(cfg, imp, exp, contract_kva=1300, pf=0.95)
    # kWh: 400 kW x 24 h x 31 d = 297,600; + (1140 - 400) x 0.25 h = 185  -> 297,785 kWh
    assert b["import_kwh"] == pytest.approx(297_785.0)
    # slabs: 100,000 x 8.25 = 825,000.00; 197,785 x 8.65 = 1,710,840.25  -> 2,535,840.25
    assert b["energy_base_rs"] == pytest.approx(2_535_840.25)
    # ToD peak 18-22 h: 16 slots x 100 kWh x 31 d = 49,600 + 185 (the 19:00 spike) = 49,785 kWh x (+1.00) = +49,785
    # ToD off-peak 22-06 h: 32 slots x 100 kWh x 31 d = 99,200 kWh x (-1.00) = -99,200   -> ToD = -49,415
    assert b["tod_rs"] == pytest.approx(-49_415.0)
    # energy = 2,535,840.25 - 49,415 = 2,486,425.25
    assert b["energy_rs"] == pytest.approx(2_486_425.25)
    # export: 50 kW x 2 h x 31 d = 3,100 kWh x 3.74 = 11,594.00
    assert b["export_kwh"] == pytest.approx(3_100.0)
    assert b["export_credit_rs"] == pytest.approx(11_594.0)
    # recorded MD: 1140 kW / 0.95 = 1200 kVA; billing = max(1200, 0.85 x 1300 = 1105) = 1200
    assert b["recorded_max_kva"] == pytest.approx(1200.0)
    assert b["billing_demand_kva"] == pytest.approx(1200.0)
    # demand: 265 x 1200 = 318,000; no excess (1200 <= 1300)
    assert b["demand_rs"] == pytest.approx(318_000.0)
    assert b["excess_rs"] == 0.0
    # total = 2,486,425.25 + 318,000 - 11,594 = 2,792,831.25
    assert round(b["total_rs"]) == 2_792_831
    assert b["total_rs"] == pytest.approx(2_792_831.25)
    assert b["order"]["valid_from"] == "2022-04-01"


def test_billing_demand_floor_85pct(cfg):
    imp = _month(2023, 8, 31, base_kw=500.0)
    imp["2023-08-09"][50] = 800.0              # 800 / 0.95 = 842.1 -> 842 kVA (rounded) < 0.85 x 1300 = 1105
    b = monthly_bill(cfg, imp, contract_kva=1300, pf=0.95)
    assert b["recorded_max_kva"] == 842.0
    assert b["billing_demand_kva"] == pytest.approx(1105.0)
    assert b["demand_rs"] == pytest.approx(1105.0 * order_for(cfg, "2023-08-09")["demand_rs_kva_month"])
    assert b["excess_rs"] == 0.0
    assert b["tod_rs"] == 0.0                  # August: no ToD


def test_excess_over_contract_at_2x(cfg):
    imp = _month(2022, 12, 31, base_kw=500.0)
    imp["2022-12-20"][80] = 1425.0             # 1425 / 0.95 = 1500 kVA, 200 kVA above CD 1300
    b = monthly_bill(cfg, imp, contract_kva=1300, pf=0.95)
    rate = order_for(cfg, "2022-12-20")["demand_rs_kva_month"]       # 265
    assert b["recorded_max_kva"] == pytest.approx(1500.0)
    assert b["demand_rs"] == pytest.approx(rate * 1300)              # 344,500
    assert b["excess_kva"] == pytest.approx(200.0)
    assert b["excess_rs"] == pytest.approx(2.0 * rate * 200)         # 106,000
    assert b["demand_rs"] + b["excess_rs"] == pytest.approx(450_500.0)


def test_bill_inputs_2d_and_month_check(cfg):
    days = [f"2023-09-{d:02d}" for d in range(1, 31)]
    arr = np.full((30, 96), 300.0)
    b1 = monthly_bill(cfg, arr, dates=days, contract_kva=1000)
    b2 = monthly_bill(cfg, {d: arr[i] for i, d in enumerate(days)}, contract_kva=1000)
    assert b1["total_rs"] == pytest.approx(b2["total_rs"])
    with pytest.raises(ValueError):
        monthly_bill(cfg, {"2023-09-30": np.ones(96), "2023-10-01": np.ones(96)})
    with pytest.raises(ValueError):
        monthly_bill(cfg, arr)                 # 2-D without dates
