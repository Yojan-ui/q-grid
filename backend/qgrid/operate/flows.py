"""Daily energy flows for the Sankey diagram: sources (solar, battery, grid, diesel) -> sinks (each zone's load,
critical loads, battery charging, export). Each 15-minute slot's sources are shared out to that slot's sinks in
proportion (one pool per slot, campus-wide), then summed over the day; kWh. Unserved load is reported as its own sink."""
from __future__ import annotations

import numpy as np

from ..model import DT, flex_load, net_power, pump_load


def energy_flows(campus, day, sched) -> dict:
    net = net_power(campus, day, sched)                          # (n, T) kW, + = import / deficit
    g = day.grid[None, :]
    imp = np.where(g, np.maximum(net, 0), 0).sum(0)
    exp = np.where(g, np.maximum(-net, 0), 0).sum(0)
    deficit = np.where(g, 0.0, np.maximum(net, 0))
    spill = np.where(g, 0.0, np.maximum(-net, 0)).sum(0)
    demand = day.load + flex_load(campus, sched) + pump_load(campus, sched)
    served = demand - deficit                                    # what each zone actually received
    crit_served = np.minimum(day.crit, served)
    noncrit_served = served - crit_served
    pb = np.asarray(sched.p_bat)
    src = {"Solar": np.maximum(day.pv.sum(0) - spill, 0), "Battery": np.maximum(-pb, 0).sum(0), "Grid": imp,
           "Diesel": np.asarray(sched.dg_kw).sum(0)}
    sinks = {**{f"zone:{nm}": noncrit_served[i] for i, nm in enumerate(campus.names)}, "Critical loads": crit_served.sum(0),
             "Battery charging": np.maximum(pb, 0).sum(0), "Export": exp}
    S = np.vstack(list(src.values()))                           # (4, T)
    K = np.vstack(list(sinks.values()))
    tot_s = S.sum(0); tot_k = K.sum(0)
    links = {}
    for t in range(S.shape[1]):
        if tot_s[t] <= 1e-9:
            continue
        share = S[:, t] / tot_s[t]
        scale = min(1.0, tot_s[t] / tot_k[t]) if tot_k[t] > 1e-9 else 0.0   # losses: sinks can't exceed sources
        for a, sa in enumerate(src):
            for b, kb in enumerate(sinks):
                v = share[a] * K[b, t] * scale * DT
                if v > 1e-6:
                    links[(sa, kb)] = links.get((sa, kb), 0.0) + v
    out = [{"source": a, "target": (b.split(":", 1)[1] if b.startswith("zone:") else b), "kind": "zone" if b.startswith("zone:") else "sink",
            "kwh": round(v, 1)} for (a, b), v in links.items() if v >= 0.5]
    return {"links": out, "unserved_kwh": round(float(deficit.sum() * DT), 1),
            "sources_kwh": {k: round(float(v.sum() * DT), 1) for k, v in src.items()},
            "method": "per 15-minute slot, campus-wide pool shared in proportion; kWh over the day"}
