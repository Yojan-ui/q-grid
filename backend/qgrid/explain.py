"""Deterministic explanations generated from the QUBO terms that drove each decision.

For every committed decision bit (battery mode now, DG, pump, job starts, tie-line levels) the bit is flipped
and the change of every term group is computed exactly: Delta_g = E_g(x with bit flipped) - E_g(x). The
largest contributions become a sentence with the real numbers (prices, kW, SoC, tank level, Rs). An LLM may
only rephrase this text; it never changes the numbers or the decision.
"""
from __future__ import annotations

import numpy as np

from . import qubo as Q

GROUP_TEXT = {
    "grid": "grid cost",
    "battery_ctg": "value of battery energy for later today",
    "water_value": "value of water stored for later",
    "dg_fuel": "diesel fuel",
    "flex_timing": "cost of running the job now vs. its best later slot",
    "admm": "agreement with the neighbouring zone",
}


def _label(var: str, lp: Q.LocalProblem, on: bool) -> str:
    if var == "c0":
        return "charge the battery now" if on else "not charge the battery now"
    if var == "d0":
        return "discharge the battery now" if on else "not discharge the battery now"
    if var == "g":
        return "run the diesel generator" if on else "keep the diesel generator off"
    if var == "w":
        return "run the borewell pump" if on else "keep the pump off"
    if var.startswith("s:"):
        return f"start {var[2:].replace('_', ' ')} now" if on else f"defer {var[2:].replace('_', ' ')}"
    if var[0] in "pn":
        return None
    return var


def explain(lp: Q.LocalProblem, x: np.ndarray, zone: str = "", top: int = 2) -> list[dict]:
    groups, _, _ = Q.build_groups(lp)
    x = np.asarray(x, float)
    out = []
    committed = [v for v in lp.names if v in ("c0", "d0", "g", "w") or v.startswith("s:")]
    for v in committed:
        i = lp.idx[v]
        y = x.copy(); y[i] = 1 - y[i]
        deltas = {g: float(q.energy(y)[0] - q.energy(x)[0]) for g, q in groups.items()}
        total = sum(deltas.values())
        reasons = sorted(((d, g) for g, d in deltas.items() if abs(d) > 1e-6), key=lambda t: -abs(t[0]))[:top]
        label = _label(v, lp, bool(x[i]))
        parts = [f"{'+' if d > 0 else '-'}Rs {abs(d):,.1f} {GROUP_TEXT.get(g, g.replace('rule:', 'operator rule: '))}"
                 for d, g in reasons]
        ctx = (f"price now Rs {lp.pi[0]:.2f}/kWh import" + (f", Rs {lp.pe[0]:.2f}/kWh export" if lp.grid[0] else ", grid DOWN (islanded)")
               + f", net load {lp.r0[0] + lp.fixed_out:+.0f} kW")
        if lp.bat.present:
            ctx += f", battery {lp.e_now / lp.bat.kwh:.0%}"
        if lp.tank is not None:
            ctx += f", tank {lp.tank.level:.0f} m3"
        text = (f"{zone + ': ' if zone else ''}Chose to {label}. Doing the opposite would change the objective by "
                f"{'+' if total >= 0 else '-'}Rs {abs(total):,.1f} ({'; '.join(parts) or 'no difference'}). Context: {ctx}.")
        out.append({"var": v, "value": int(x[i]), "decision": label, "delta_total_rs": total, "deltas_rs": deltas,
                    "text": text})
    for l, _ in lp.lines:
        f = lp.F * (x[lp.idx[f"p{l}"]] - x[lp.idx[f"n{l}"]])
        out.append({"var": f"line{l}", "value": float(f), "decision": f"tie-line {l}: {f:+.0f} kW",
                    "text": f"{zone + ': ' if zone else ''}Tie-line {l} proposal {f:+.0f} kW (agreed with the neighbour via ADMM)."})
    return out
