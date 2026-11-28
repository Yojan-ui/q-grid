"""Monthly demand-charge billing (qgrid/ablation/demand.py) on hand-made months, tariff reading with and without the
tariff_ht2c config section, and the scorecard writer's monthly bill on a copy of the benchmark runs."""
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

from qgrid.ablation import demand as D

ROOT = Path(__file__).resolve().parents[2]
P = {"rate": 350.0, "pf": 0.95, "floor_frac": 0.85, "excess_mult": 2.0, "contract_kva": 1000.0}


def test_monthly_charge_floor_and_excess():
    below = D.monthly_charge(500.0, P)                    # under the floor: billed on 0.85 x contract
    assert below["billing_kva"] == pytest.approx(850.0) and below["charge_rs"] == pytest.approx(350 * 850)
    mid = D.monthly_charge(900.0, P)                      # between floor and contract: billed on MD
    assert mid["charge_rs"] == pytest.approx(350 * 900)
    over = D.monthly_charge(1200.0, P)                    # 200 kVA over contract at 2x
    assert over["charge_rs"] == pytest.approx(350 * 1000 + 2 * 350 * 200)
    nocontract = D.monthly_charge(500.0, {**P, "contract_kva": None})
    assert nocontract["charge_rs"] == pytest.approx(350 * 500)


def test_settlement_of_a_hand_made_month():
    df = pd.DataFrame([  # February 2023 (28 days): two sampled days; March 2023 (31 days): one sampled day
        {"dataset": "rvce", "method": "m", "day": "2023-02-03", "peak_kva": 900.0, "cost_rs": 1000.0},
        {"dataset": "rvce", "method": "m", "day": "2023-02-17", "peak_kva": 1200.0, "cost_rs": 2000.0},
        {"dataset": "rvce", "method": "m", "day": "2023-03-09", "peak_kva": 500.0, "cost_rs": 1500.0},
        {"dataset": "rvce", "method": "n", "day": "2023-02-03", "peak_kva": 800.0, "cost_rs": 1000.0},
    ])
    out = D.monthly_settlement(df, lambda ds, day: P)
    feb = 350 * 1000 + 2 * 350 * 200                      # MD 1200 for method m in February
    mar = 350 * 850                                       # March below the floor
    m = out[out.method == "m"].set_index("day")
    assert m.loc["2023-02-03", "md_month_kva"] == 1200.0 and m.loc["2023-02-17", "md_month_kva"] == 1200.0
    assert m.loc["2023-02-03", "demand_charge_month_rs"] == pytest.approx(feb)
    assert m.loc["2023-02-03", "demand_share_rs"] == pytest.approx(feb / 28)
    assert m.loc["2023-02-17", "bill_rs"] == pytest.approx(2000 + feb / 28)
    assert m.loc["2023-03-09", "bill_rs"] == pytest.approx(1500 + mar / 31)
    n = out[out.method == "n"].iloc[0]                    # each method is billed on its own maximum demand
    assert n.md_month_kva == 800.0 and n.demand_share_rs == pytest.approx(350 * 850 / 28)


def test_tariff_params_fallback_and_ht2c():
    fb = D.tariff_params({"tariff_v2": {"demand_rs_per_kva_month": 350.0, "power_factor": 0.95, "status": "PENDING"}})
    assert fb["rate"] == 350.0 and fb["floor_frac"] == D.FALLBACK_FLOOR_FRAC and fb["excess_mult"] == D.FALLBACK_EXCESS_MULT
    assert fb["contract_kva"] is None and "fallback" in fb["source"]
    cfg = {"tariff_v2": {"demand_rs_per_kva_month": 350.0, "power_factor": 0.95},
           "tariff_ht2c": {"status": "REAL", "power_factor": 0.9, "billing_demand_floor_frac": 0.75,
                           "excess_demand_multiplier": 2.0, "contract_demand_kva": 1300,
                           "orders": [{"valid_from": "2023-04-01", "valid_to": "2024-03-31", "demand_rs_kva_month": 340},
                                      {"valid_from": "2024-04-01", "valid_to": "2025-03-31", "demand_rs_kva_month": 350}]}}
    p = D.tariff_params(cfg, "2023-06-20")
    assert p["contract_kva"] == 1300 and p["pf"] == 0.9 and p["floor_frac"] == 0.75 and p["source"] == "tariff_ht2c"
    assert p["rate"] in (340.0, 350.0)                    # the tariff module's order_for may choose; fallback: by date
    assert D.tariff_params(cfg, "2023-06-20", contract_kva=None)["contract_kva"] is None
    assert D.tariff_params(cfg, "2023-06-20", contract_kva=1600)["contract_kva"] == 1600.0
    assert D.planning_term(1300.0, p) == pytest.approx(p["rate"] * (1300 - 975))


def test_scorecard_bill_is_energy_plus_monthly_share(tmp_path, monkeypatch):
    src = ROOT / "results" / "bench_v3"
    if not (src / "runs.csv").exists() or not (src / "bounds.csv").exists():
        pytest.skip("benchmark runs not available")
    for f in ("runs.csv", "bounds.csv"):
        shutil.copy(src / f, tmp_path / f)
    sys.path.insert(0, str(ROOT / "scripts"))
    import write_bench_v3 as wb
    monkeypatch.setattr(wb, "OUT", tmp_path)              # never touch the committed results
    r = wb.daily()
    assert (r.bill_rs - (r.cost_rs + r.demand_share_rs)).abs().max() < 1e-6
    g = r.groupby(["dataset", "method", "month"])
    assert (g.md_month_kva.nunique() == 1).all()
    assert (r.gap_pct >= -1e-9).all()
