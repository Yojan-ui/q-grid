"""Data-pipeline unit tests. All inputs here are SYNTHETIC (unit tests only, never headline results)."""
import numpy as np
import pandas as pd
import pytest

from baselines.b0_status_quo import status_quo
from qgrid import data


def test_pv_model_stc_and_night():
    idx = pd.date_range("2023-01-01", periods=3, freq="15min")
    w = pd.DataFrame({"ghi_wm2": [0.0, 1000.0, 500.0], "t2m_c": [20.0, 25.0 - 31.25, 25.0]}, index=idx)
    pm = {"noct_c": 45.0, "gamma_per_c": -0.004, "system_derate": 0.86}
    p = data.pv_output_kw(w, 100.0, pm).to_numpy()
    assert p[0] == 0
    assert p[1] == pytest.approx(86.0)          # Tcell = 25 C exactly -> no derating
    assert 0 < p[2] < 43.0                      # hotter cell -> derated below linear


def test_map_dates_weekday_and_range():
    m = data.map_dates(2023)
    assert len(m) == 365
    for d, s in m.items():
        assert d.weekday() == s.weekday()
        assert pd.Timestamp("2012-07-01") <= s <= pd.Timestamp("2013-06-30")


def _synthetic_ausgrid_csv(n_cust=12, days=3):
    rng = np.random.default_rng(0)
    cols = [f"{h}:{m:02d}" for h in range(24) for m in (0, 30)][1:] + ["0:00"]
    rows = []
    for c in range(1, n_cust + 1):
        for d in pd.date_range("2012-07-01", periods=days):
            for cat in ("GC", "CL", "GG"):
                rows.append([c, 2.0, 2000, cat, d.strftime("%d/%m/%Y")] + list(rng.random(48).round(3)))
    hdr = ["Customer", "Generator Capacity", "Postcode", "Consumption Category", "date"] + cols
    body = pd.DataFrame(rows, columns=hdr).to_csv(index=False)
    return ("Solar home half-hour data - SYNTHETIC test file\n" + body).encode()


def test_ausgrid_parse_and_cluster():
    df = data._parse_ausgrid(_synthetic_ausgrid_csv())
    kw = data.ausgrid_customer_loads(df)
    assert kw.shape == (3 * 48, 12)
    assert kw.index[0] == pd.Timestamp("2012-07-01 00:00")
    # GC + CL only, kWh/0.5h -> kW
    raw = df[(df.Customer == 1) & (df["Consumption Category"].isin(["GC", "CL"])) & (df.date == "01/07/2012")]
    assert kw.iloc[0, 0] == pytest.approx(raw["0:30"].sum() / 0.5)
    ids, labels, cents = data.cluster_profiles(kw, k=3)
    assert len(ids) == 12 and cents.shape == (3, 48)


def test_iex_parser(tmp_path):
    rows = [["IEX DAM Market Snapshot (SYNTHETIC)", None, None], [None, None, None],
            ["Date", "Time Block", "MCP (Rs/MWh) *"]]
    for i in range(96):
        h, m = divmod(i * 15, 60)
        rows.append(["01-01-2023" if i == 0 else None, f"{h:02d}:{m:02d} - {h:02d}:{m + 14:02d}", f"{3000 + i:,}"])
    p = tmp_path / "x.xlsx"
    pd.DataFrame(rows).to_excel(p, header=False, index=False)
    out = data.parse_iex_file(p)
    assert len(out) == 96
    assert out.iloc[0].ts == pd.Timestamp("2023-01-01 00:00")
    assert out.iloc[-1].mcp_rs_mwh == 3095


def test_status_quo_balance():
    idx = pd.date_range("2023-01-01", periods=4, freq="15min")
    pv = pd.DataFrame({"a": [0, 10, 20, 0.0]}, index=idx)
    load = pd.DataFrame({"a": [5, 5, 5, 5.0]}, index=idx)
    price = pd.Series([4, 2, 2, 8.0], index=idx)
    r = status_quo(pv, load, price, 0.7)
    assert r["import_kwh"] == pytest.approx(2.5)        # (5+5) kW x 0.25 h
    assert r["export_kwh"] == pytest.approx(5.0)        # (5+15) x 0.25
    assert r["cost_rs"] == pytest.approx(5 * .25 * 4 + 5 * .25 * 8 - 20 * .25 * 2)
    assert r["co2_kg"] == pytest.approx(2.5 * 0.7)
