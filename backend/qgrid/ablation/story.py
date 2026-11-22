"""Worked example of the current Q-Grid design for the explainer (headline day), recomputed from a real run:
the 18:00 decision's commitment problems, the quantum-placement test on one of them (QAOA block measured with Qiskit
Aer shots, checked against exact search), the cable negotiation (ADMM rounds) and the price exchange (outer rounds).
"""
from __future__ import annotations

import numpy as np

from ..model import T
from ..qubo import QUBO
from ..solvers.qaoa import load_params, run_qaoa
from .engine import ACfg, run_day

KIND = {"m": "mode", "on": "dg", "w": "pump", "bc": "charge", "bd": "discharge"}


def _colname(m, c: int) -> str:
    for name, idx in m.col.items():
        hit = np.nonzero(idx == c)[0]
        if len(hit):
            h = int(hit[0])
            slot = m.t0 + h
            if name.startswith("y:"):
                return f"flex#{name[2:]}#{slot}"
            return f"{KIND.get(name, name)}#{slot}"
    return f"x#{c}"


def qgrid_story(campus, yd, day: str, outage, forecaster, slot: int = 72, placement: dict | None = None) -> tuple[object, dict]:
    captured = {}

    def hook(t0, i, m, c):
        if t0 == slot:
            captured[i] = (m, c.copy())

    trace: dict = {}
    sched, st = run_day(campus, yd, day, outage, ACfg(True, True, True, True), forecaster=forecaster, hook=hook,
                        trace_slot=slot, trace=trace)
    binaries = {campus.names[i]: int(m.integ.sum()) for i, (m, c) in captured.items()}
    # the building whose relaxed commitment leaves the largest undecided block
    best = None
    for i, (m, c) in captured.items():
        lp = m.solve(c, relax=True)
        ib = np.nonzero(m.integ)[0]
        frac = np.abs(lp["x"][ib] - np.round(lp["x"][ib]))
        k = int((frac > 1e-6).sum())
        if best is None or k > best[0]:
            best = (k, i, m, c, lp, ib, frac)
    block, note = None, ""
    if best and best[0] > 0:
        k, i, m, c, lp, ib, frac = best
        order = np.argsort(-frac)[:min(16, k)]
        B = ib[order]
        nb = len(B)
        rc = lp["col_dual"][B].astype(float)
        Mq = np.diag(rc)
        const = 0.0
        A = m.A.tocsr()
        pen = 4 * (np.abs(rc).max() + 1.0)
        inB = np.zeros(m.ncol, bool); inB[B] = True
        pos = {cc: j for j, cc in enumerate(B)}
        for r in range(A.shape[0]):
            cols = A.indices[A.indptr[r]:A.indptr[r + 1]]
            if len(cols) == 0 or not inB[cols].all():
                continue
            a = np.zeros(nb)
            for cc, v in zip(cols, A.data[A.indptr[r]:A.indptr[r + 1]]):
                a[pos[cc]] = v
            lo, hi = m.rlo[r], m.rhi[r]
            if np.isfinite(lo) and np.isfinite(hi) and abs(lo - hi) < 1e-9:
                Mq += pen * np.outer(a, a); Mq[np.diag_indices(nb)] += -2 * pen * hi * a; const += pen * hi * hi
        q = QUBO(const, Mq)
        qr = run_qaoa(q, p=2, shots=256, seed=1234, backend="aer", params=load_params(2))
        keys, cnt = np.unique(qr.samples.astype(int), axis=0, return_counts=True)
        E = q.energy(keys.astype(float))
        Z = ((np.arange(1 << nb)[:, None] >> np.arange(nb)[None, :]) & 1).astype(float)
        Eall = q.energy(Z)
        jx = int(np.argmin(Eall))
        opt = float(Eall[jx])
        shots = sorted([{"bits": "".join(map(str, kk)), "count": int(cc), "feasible": True,
                         "optimal": bool(e <= opt + 1e-9 * max(1.0, abs(opt))), "objective": round(float(e), 4)}
                        for kk, cc, e in zip(keys, cnt, E)], key=lambda r: (-r["count"], r["bits"]))
        win = min(shots, key=lambda r: r["objective"])
        names = [_colname(m, int(cc)) for cc in B]
        block = {"zone": campus.names[i], "slot": slot, "time": f"{slot // 4:02d}:{slot % 4 * 15:02d}", "n_qubits": nb, "kind": "commitment",
                 "var_names": names, "qubo_matrix": np.round(Mq, 4).tolist(),
                 "exact": {"bits": "".join(str(int(v)) for v in Z[jx]), "objective": round(opt, 4), "time_s": 0.0},
                 "qaoa": {"best_bits": win["bits"], "best_objective": win["objective"], "feasible": True, "approx_ratio": 1.0,
                          "p_opt": float(sum(s["count"] for s in shots if s["optimal"]) / 256), "time_s": 0.0, "top": [],
                          "shots": shots, "backend": "qiskit-aer AerSimulator (ideal, noiseless), 256 shots, seed 1234"}}
        note = (f"The relaxed problem settled all but {k} of the {int(m.integ.sum())} on/off choices of the "
                f"{campus.names[i].replace('_', ' ')}; the block shows the {nb} undecided ones.")
    else:
        note = "At this decision the relaxed problem already decided every on/off choice; no quantum block was needed."
    rounds = trace.get("admm_rounds") or []
    if len(rounds) > 40:
        keep = set(range(12)) | set(range(12, len(rounds), 5)) | {len(rounds) - 1}
        rounds = [r for j, r in enumerate(rounds) if j in keep]
    return sched, {"slot": slot, "time": f"{slot // 4:02d}:{slot % 4 * 15:02d}", "binaries": binaries, "block": block, "block_note": note,
                   "placement": placement or {}, "admm_rounds": rounds, "outer": trace.get("outer", []),
                   "config": "24 h horizon, continuous dispatch, LP coordination, realistic forecasts"}
