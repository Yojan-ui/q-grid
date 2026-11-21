"""B0 status quo: no battery dispatch, no load shifting, no inter-building sharing.
Each building imports (load - PV) when positive and exports the surplus at the DAM price."""
from __future__ import annotations

import numpy as np
import pandas as pd

DT_H = 0.25  # 15-min slot in hours


def status_quo(pv: pd.DataFrame, load: pd.DataFrame, price_rs_kwh: pd.Series,
               co2_t_per_mwh: float, export_price_factor: float = 1.0) -> dict:
    net = load - pv                                    # kW per building, + = deficit
    imp = net.clip(lower=0)
    exp = (-net).clip(lower=0)
    p = price_rs_kwh.to_numpy()[:, None]
    import_cost = (imp.to_numpy() * p * DT_H).sum()
    export_rev = (exp.to_numpy() * p * export_price_factor * DT_H).sum()
    imp_kwh = imp.to_numpy().sum() * DT_H
    return {
        "import_kw": imp, "export_kw": exp,
        "cost_rs": float(import_cost - export_rev),
        "import_cost_rs": float(import_cost),
        "export_revenue_rs": float(export_rev),
        "import_kwh": float(imp_kwh),
        "export_kwh": float(exp.to_numpy().sum() * DT_H),
        "co2_kg": float(imp_kwh * co2_t_per_mwh),        # t/MWh == kg/kWh
        "peak_import_kw": float(imp.sum(axis=1).max()),
        "self_consumption_pct": float(100 * (1 - exp.to_numpy().sum() / max(pv.to_numpy().sum(), 1e-9))),
    }
