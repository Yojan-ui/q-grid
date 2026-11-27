"""Live demo moments of the current Q-Grid design, each one decision (< 5 s on a laptop).

remove_building: re-plan one 15-minute decision (24 h horizon) with a building taken offline. Its cables go dark;
the remaining buildings re-agree with their neighbours (LP consensus ADMM) and each re-solves its own on/off plan.
Each building's starting state (battery energy, tank level, diesel state, started jobs) is read from the replay run
of the same day (results/replay/scenario_<key>.json), so the what-if starts where the replayed day actually was.
The horizon uses the day's actual solar and load (no forecast error) - labelled as a what-if, never a headline result.

The same functions write the offline copies (scripts/make_live.py -> results/replay/live.json) and serve the live API
(/live/remove), so offline and live show the same computation.
"""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path

import numpy as np

from .ablation.engine import ACfg, plan_hour
from .ablation.local import LocalModel, LState
from .model import T, wear_rate

ROOT = Path(__file__).resolve().parents[2]
LABEL = "What-if (one decision, current Q-Grid design, actual solar and load over the horizon) — not a headline result"


def _replay(key: str) -> dict:
    for p in (ROOT / "results" / "replay" / f"scenario_{key}.json", ROOT / "frontend" / "public" / "replay" / f"scenario_{key}.json"):
        if p.exists():
            return json.loads(p.read_text())
    raise FileNotFoundError(f"scenario_{key}.json not found (run make replay)")


def states_at(campus, run: dict, slot: int) -> list[LState]:
    """Building states at the start of `slot`, from a replay run block."""
    out = []
    for i, b in enumerate(campus.buildings):
        e = float(run["soc"][i][slot]) * b.battery.kwh if b.battery.present else 0.0
        lvl = 0.0
        if b.tank:
            tk = run.get("tank_m3", {}).get(campus.names[i])
            lvl = float(tk[max(slot - 1, 0)]) if tk else b.tank.level0
        dg = run["dg_kw"][i]
        on = bool(slot > 0 and dg[slot - 1] > 1e-9)
        k, run_len = slot - 1, 0
        while k >= 0 and (dg[k] > 1e-9) == on:
            run_len += 1; k -= 1
        started = {j: int(t) for j, t in (run.get("flex_start", [{}] * campus.n)[i] or {}).items() if int(t) < slot}
        out.append(LState(e=e, level=lvl, dg_on=on, dg_run=run_len if slot > 0 else 99, started=started))
    return out


def _models(campus, w, states, slot, cfg: ACfg):
    oc = campus.cfg["outage_costs"]
    voll = (float(oc["voll_noncritical_rs_kwh"]), float(oc["voll_critical_rs_kwh"]))
    lam = float(campus.cfg["co2"]["lambda_rs_per_kg"])
    return [LocalModel(campus, i, w, copy.deepcopy(states[i]), slot, cfg.H, disc=False, disc_flows=False, term_slope=w.term_value,
                       voll=voll, lam_co2=lam, quad_flows=False, time_limit=cfg.mip_time, mip_gap=cfg.mip_gap,
                       wear=wear_rate(campus.cfg))
            for i in range(campus.n)]


def _plan(campus, w, states, slot, cfg):
    t0 = time.perf_counter()
    models = _models(campus, w, states, slot, cfg)
    trace: dict = {}
    xs, st = plan_hour(campus, models, cfg, {}, trace=trace)
    rounds = trace.get("admm_rounds") or []
    per_b = []
    for i, (m, x) in enumerate(zip(models, xs)):
        per_b.append({"cost_rs": float(m.cost0 @ x), "crit_shed_kwh": float(m.get(x, "sc").sum() * 0.25),
                      "shed_kwh": float((m.get(x, "sc").sum() + m.get(x, "snc").sum()) * 0.25),
                      "battery_kw_now": float(m.get(x, "ch")[0] - m.get(x, "dis")[0]), "diesel_kw_now": float(m.get(x, "pg")[0])})
    return {"time_s": time.perf_counter() - t0, "admm_rounds": int(st["rounds"]), "converged": bool(st["converged"]),
            "messages": int(st.get("messages", 0)), "buildings": per_b,
            "residuals": [round(float(r.get("r_primal", 0.0)), 3) for r in rounds][:60]}


def remove_building(campus, yd, key: str, zone: str, slot: int | None = None, baseline: dict | None = None) -> dict:
    sc = _replay(key)
    slot = int(slot if slot is not None else (sc.get("qgrid_story") or {}).get("slot", 72))
    run = sc["runs"]["qgrid"]
    outage = sc["scenario"].get("outage")
    d0 = yd.day_start(sc["scenario"]["date"])
    cfg = ACfg(True, True, True, True)
    w = yd.window(d0, slot, cfg.H, outage)
    states = states_at(campus, run, slot)
    k = campus.names.index(zone)
    base = baseline or _plan(campus, w, states, slot, cfg)
    c2 = copy.copy(campus)
    c2.lines = [ln for ln in campus.lines if k not in ln]           # its cables go dark
    after = _plan(c2, w, states, slot, cfg)
    others = [i for i in range(campus.n) if i != k]
    tot = lambda r, f: float(sum(r["buildings"][i][f] for i in others))   # noqa: E731
    return {"label": LABEL, "scenario": key, "slot": slot, "time": f"{slot // 4:02d}:{slot % 4 * 15:02d}", "zone": zone,
            "grid_up_now": bool(w.grid[0]), "lines_dark": [i for i, ln in enumerate(campus.lines) if k in ln],
            "before": base, "after": after,
            "others": {"cost_before_rs": tot(base, "cost_rs"), "cost_after_rs": tot(after, "cost_rs"),
                       "crit_shed_before_kwh": tot(base, "crit_shed_kwh"), "crit_shed_after_kwh": tot(after, "crit_shed_kwh"),
                       "n": len(others)},
            "compute_s": after["time_s"]}


RULE_LABEL = ("What-if: the best possible plan for the day (central MILP, perfect information) with and without the rule "
              "as a hard constraint - the rule's cost, not a headline result")
PRESETS = ["no DG", "keep hostel tanks above 90% by 6 am", "EV charging only after 10 pm"]   # one binding, one cheap, one rejected


def rule_effect(campus, day, text: str) -> dict:
    """Parse and validate a faculty rule (templates; optional LLM only turns text into JSON), then price it."""
    from baselines.milp import solve_milp, to_schedule
    from .model import Schedule, settle
    from .rules import apply_rules, parse_rule
    t0 = time.perf_counter()
    res = [r.model_dump() for r in parse_rule(text, campus)]
    ok = [r["rule"] for r in res if r["ok"]]
    effect = None
    if ok:
        c2, d2, ar = apply_rules(campus, day, ok)
        out = {}
        for tag, (cc, dd, rr) in {"before": (campus, day, []), "after": (c2, d2, ar)}.items():
            r = solve_milp(cc, dd, list(range(cc.n)), with_lines=True, time_limit=20, rules=rr)
            if r["status"] != "Optimal":
                out[tag] = {"status": r["status"]}
                continue
            s = Schedule.empty(cc); to_schedule(cc, r, s)
            m = settle(cc, dd, s)
            out[tag] = {"status": "Optimal", **{k: float(m[k]) for k in ("cost_rs", "objective_rs", "dg_hours", "dg_litres", "critical_downtime_h", "critical_unserved_kwh") if k in m},
                         "shed_noncritical_kwh": float(m["unserved_kwh"] - m["critical_unserved_kwh"])}
        effect = {**out, "label": RULE_LABEL, "agent_rules": ar}
    return {"text": text, "results": res, "effect": effect, "day": day.day, "day_type": day.day_type,
            "time_s": time.perf_counter() - t0}


QAOA_LABEL = "QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed"


def qaoa_block(key: str, seed: int = 1234, shots: int = 256, backend: str = "aer") -> dict:
    """Re-measure the worked example's QUBO block (from the replay) with QAOA and check it against exact search."""
    from .qubo import QUBO
    from .solvers.qaoa import load_params, run_qaoa
    sc = _replay(key)
    blk = (sc.get("qgrid_story") or {}).get("block") or ((sc.get("v2") or {}).get("example") or {}).get("block")
    if not blk:
        # the current design's decision needed no block that day: use the worked example the explainer shows instead
        # (frontend/src/lib/story.ts pickExample: server room at slot 76, else the first QAOA = exact record)
        live = sc.get("live_solve") or []
        blk = (next((x for x in live if x.get("zone") == "server_room" and x.get("slot") == 76), None)
               or next((x for x in live if (x.get("qaoa") or {}).get("best_bits") == (x.get("exact") or {}).get("bits")), None)
               or (live[0] if live else None))
    if not blk:
        raise ValueError(f"scenario_{key}.json has no worked-example block")
    M = np.array(blk["qubo_matrix"], float)
    q = QUBO(0.0, M)
    n = len(M)
    t0 = time.perf_counter()
    Z = ((np.arange(1 << n)[:, None] >> np.arange(n)[None, :]) & 1).astype(float)
    E = q.energy(Z)
    jx = int(np.argmin(E)); opt = float(E[jx])
    t_ex = time.perf_counter() - t0
    t0 = time.perf_counter()
    qr = run_qaoa(q, p=2, shots=shots, seed=seed, backend=backend, params=load_params(2))
    t_q = time.perf_counter() - t0
    keys, cnt = np.unique(qr.samples.astype(int), axis=0, return_counts=True)
    Ek = q.energy(keys.astype(float))
    tol = 1e-9 * max(1.0, abs(opt))
    rows = sorted([{"bits": "".join(map(str, k)), "count": int(c), "feasible": True, "optimal": bool(e <= opt + tol),
                    "objective": round(float(e), 4)} for k, c, e in zip(keys, cnt, Ek)], key=lambda r: (-r["count"], r["bits"]))
    best = min(rows, key=lambda r: r["objective"])
    return {"label": QAOA_LABEL, "zone": blk.get("zone"), "time": blk.get("time"), "n_qubits": n, "var_names": blk.get("var_names"),
            "seed": seed, "shots_total": shots, "backend": f"qiskit-{backend} (ideal, noiseless), {shots} shots, seed {seed}",
            "exact": {"bits": "".join(str(int(v)) for v in Z[jx]), "objective": round(opt, 4), "time_s": t_ex},
            "qaoa": {"best_bits": best["bits"], "best_objective": best["objective"], "matches_exact": bool(best["optimal"]),
                     "p_opt": float(sum(r["count"] for r in rows if r["optimal"]) / shots), "time_s": t_q, "shots": rows}}
