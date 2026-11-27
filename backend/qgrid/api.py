"""FastAPI backend for the live demo. The frontend works offline from replay JSON; when this server runs
(`uvicorn qgrid.api:app --port 8000`), Judge mode solves QUBOs live, the sandbox recomputes what-ifs and the
live websocket streams ADMM slot results. Sandbox results are labelled what-if and never mixed into headlines."""
from __future__ import annotations

import asyncio
import copy
import threading
import time

import numpy as np
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import QUANTUM_LABEL
from . import data as qdata
from . import qubo as Q
from .agent import BuildingAgent
from .model import load_campus, make_day, settle

app = FastAPI(title="Q-Grid live API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
_STATE: dict = {}


def _ctx():
    if not _STATE:
        _STATE["campus"] = load_campus()
        _STATE["proc"] = qdata.load_processed()
    return _STATE["campus"], _STATE["proc"]


def _day(key: str, scen: str = "A", outage=None):
    campus, proc = _ctx()
    sc = proc["meta"]["days"]["scenarios"][key]
    return make_day(campus, proc, sc["date"], scen, key, outage if outage is not None else sc.get("outage"))


@app.get("/health")
def health():
    return {"ok": True, "label": QUANTUM_LABEL}


class SolveReq(BaseModel):
    scenario: str = "outage_fest"
    zone: str = "hostels"
    slot: int = 76
    backend: str = "aer"
    p: int = 2


@app.post("/solve")
def solve(req: SolveReq):
    from .solvers.exact import approx_ratio, solve_exact
    from .solvers.qaoa import run_qaoa
    campus, _ = _ctx()
    day = _day(req.scenario)
    i = campus.names.index(req.zone)
    ag = BuildingAgent(campus, day, i, campus.cfg["admm"]["horizon_slots"])
    lp = ag.local_problem(req.slot, ag.incident, v={l: 0.0 for l, _ in ag.incident}, rho=0.05)
    qubos = Q.build(lp)
    en = Q.enumerate_all(lp, qubos)
    total, *_ = Q.auto_tune(lp, qubos, enum=en)
    t0 = time.perf_counter(); ex = solve_exact(lp, qubos, enum=en); t_ex = time.perf_counter() - t0
    t0 = time.perf_counter(); qr = run_qaoa(total, p=req.p, shots=512, seed=1234, backend=req.backend); t_q = time.perf_counter() - t0
    feas = Q.feasible_mask(lp, qr.samples)
    bits = lambda x: "".join(str(int(v)) for v in x)  # noqa: E731
    best = qr.samples[feas][np.argmin(qubos[0].energy(qr.samples[feas]))] if feas.any() else None
    order = np.argsort(-qr.probs)[:64]
    return {"zone": req.zone, "slot": req.slot, "n_qubits": lp.n, "var_names": lp.var_names(),
            "qubo_matrix": np.round(total.M, 3).tolist(), "label": QUANTUM_LABEL, "simulator": req.backend,
            "exact": {"bits": bits(ex.x), "objective": ex.objective, "time_s": t_ex},
            "qaoa": {"best_bits": bits(best) if best is not None else None, "feasible": bool(feas.any()),
                     "approx_ratio": approx_ratio(float(qubos[0].energy(best)[0]), ex) if best is not None else 0.0,
                     "p_opt": float(qr.probs[ex.opt_mask].sum()), "time_s": t_q,
                     "top": [{"bits": bits(en["X"][k]), "p": float(qr.probs[k]), "feasible": bool(en["feas"][k]),
                              "optimal": bool(ex.opt_mask[k])} for k in order]}}


class WhatIf(BaseModel):
    scenario: str = "outage_fest"
    battery_scale: float = 1.0
    pv_scale: float = 1.0
    price: str = "A"
    outage_hours: float | None = None
    dg_cost_scale: float = 1.0
    kill_zone: str | None = None
    tariff_scale: float = 1.0      # evening (18-22 h) import price multiplier


@app.post("/whatif")
def whatif(req: WhatIf):
    """Fast what-if recompute with the centralised QIEA solver (quantum-inspired, classical CPU). Labelled
    what-if; never part of headline results."""
    from baselines import b0_status_quo, c_qiea
    campus, _ = _ctx()
    c2 = copy.deepcopy(campus)
    for b in c2.buildings:
        b.battery.kwh *= req.battery_scale
        b.battery.kw *= req.battery_scale
        if b.dg:
            b.dg.price *= req.dg_cost_scale
    outage = None
    if req.outage_hours is not None and req.outage_hours > 0:
        h = max(0.25, min(req.outage_hours, 6))
        end = 18 + h
        outage = ["18:00", f"{int(end):02d}:{int((end % 1) * 60):02d}"]
    elif req.outage_hours == 0:
        outage = []
    day = _day(req.scenario, req.price, outage)
    day.pv = day.pv * req.pv_scale
    if req.tariff_scale != 1.0:
        day.price_imp = day.price_imp.copy()
        day.price_imp[72:88] *= req.tariff_scale
    if req.kill_zone:   # zone offline: its lines carry 0 -> remove its tie-lines for the what-if
        k = c2.names.index(req.kill_zone)
        c2.lines = [l for l in c2.lines if k not in l]
    t0 = time.perf_counter()
    s = c_qiea.solve(c2, day, gens=60)
    m, m0 = settle(c2, day, s), settle(c2, day, b0_status_quo.solve(c2, day))
    keep = ("cost_rs", "objective_rs", "dg_hours", "dg_litres", "critical_downtime_h", "critical_unserved_kwh", "co2_kg")
    return {"label": "WHAT-IF (C-QIEA, quantum-inspired classical solver) — not a headline result",
            "params": req.model_dump(), "qgrid": {k: m[k] for k in keep}, "status_quo": {k: m0[k] for k in keep},
            "time_s": time.perf_counter() - t0}


class RuleReq(BaseModel):
    text: str
    scenario: str = "exam_week"


@app.post("/rules/parse")
def rules_parse(req: RuleReq):
    from .rules import apply_rules, parse_rule
    campus, _ = _ctx()
    res = [r.model_dump() for r in parse_rule(req.text, campus)]
    effect = None
    ok = [r["rule"] for r in res if r["ok"]]
    if ok:
        from baselines import c_qiea
        day = _day(req.scenario)
        c2, d2, ar = apply_rules(campus, day, ok)
        s0 = c_qiea.solve(campus, day, gens=40)
        s1 = c_qiea.solve(c2, d2, rules=ar, gens=40)
        m0, m1 = settle(campus, day, s0), settle(c2, d2, s1)
        effect = {"before": {k: m0[k] for k in ("cost_rs", "dg_hours")}, "after": {k: m1[k] for k in ("cost_rs", "dg_hours")},
                  "agent_rules": ar, "note": "what-if with C-QIEA (quantum-inspired, classical CPU)"}
    return {"results": res, "effect": effect}


# ---------------------------------------------------------------- live demo moments (each one decision, < 5 s)
def _yd():
    if "yd" not in _STATE:
        from .v2.horizon import YearData
        campus, proc = _ctx()
        _STATE["yd"] = YearData(campus, proc, "A", forecast=False)
    return _STATE["yd"]


class RemoveReq(BaseModel):
    scenario: str = "outage_fest"
    zone: str = "heavy_labs"
    slot: int | None = None


@app.post("/live/remove")
def live_remove(req: RemoveReq):
    """Take a building offline for one decision of the current design; neighbours re-agree without its cables."""
    from .live import remove_building
    campus, _ = _ctx()
    key = (req.scenario, req.slot)
    base = _STATE.setdefault("remove_base", {}).get(key)
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        out = remove_building(campus, _yd(), req.scenario, req.zone, req.slot, baseline=base)
    _STATE["remove_base"][key] = out["before"]
    return out


@app.post("/live/warm")
def live_warm(scenario: str = "outage_fest"):
    """Demo preset: load the year data and compute the remove-a-building baseline once, so the first live click is fast."""
    import time as _t
    from .live import remove_building
    t0 = _t.perf_counter()
    campus, _ = _ctx()
    key = (scenario, None)
    if key not in _STATE.setdefault("remove_base", {}):
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            out = remove_building(campus, _yd(), scenario, campus.names[1])
        _STATE["remove_base"][key] = out["before"]
    return {"ok": True, "warm_s": _t.perf_counter() - t0}


class QaoaReq(BaseModel):
    scenario: str = "outage_fest"
    seed: int = 1234
    shots: int = 256


@app.post("/live/qaoa")
def live_qaoa(req: QaoaReq):
    """Re-measure the worked example's QUBO block with QAOA (simulator) and check it against exact search."""
    from .live import qaoa_block
    return qaoa_block(req.scenario, seed=req.seed, shots=min(max(req.shots, 64), 2048))


@app.post("/live/rule")
def live_rule(req: RuleReq):
    """Parse and validate a faculty rule, then price it: best possible plan with vs without it (exact MILP)."""
    from .live import rule_effect
    campus, _ = _ctx()
    return rule_effect(campus, _day(req.scenario), req.text)


# ---------------------------------------------------------------- Operate mode (control room)
def _op():
    """The operate session: created on first use (it loads a year of data and makes the first plan) and kept running."""
    if "op" not in _STATE:
        from .operate.session import Session
        campus, proc = _ctx()
        s = Session(campus, proc)
        s.start()
        _STATE["op"] = s
    return _STATE["op"]


@app.get("/operate/state")
def operate_state():
    return _op().snapshot()


class ControlReq(BaseModel):
    speed: float | None = None          # 0 pause, 1 live, 60 fast-forward
    source: str | None = None           # "today" | "historical"
    hist_day: str | None = None


@app.post("/operate/control")
def operate_control(req: ControlReq):
    s = _op()
    if req.source:
        s.reset(req.source, req.hist_day)
    if req.speed is not None:
        if req.speed not in (0, 1, 60):
            raise ValueError("speed must be 0, 1 or 60")
        s.set_speed(req.speed)
    return s.snapshot()


class EventReq(BaseModel):
    kind: str                           # "outage" | "comms_loss"
    minutes: int = 60


@app.post("/operate/event")
def operate_event(req: EventReq):
    return _op().inject(req.kind, max(5, min(req.minutes, 360)))


class OverrideReq(BaseModel):
    zone: str
    device: str                         # battery | diesel | pump
    state: str                          # on | off | hold
    minutes: int = 30
    confirm: bool = False
    who: str = "operator"


@app.post("/operate/override")
def operate_override(req: OverrideReq):
    if not req.confirm:
        return {"ok": False, "error": "confirmation required"}
    return _op().override(req.zone, req.device, req.state, max(5, min(req.minutes, 480)), who=req.who)


@app.delete("/operate/override/{oid}")
def operate_override_clear(oid: int):
    return _op().clear_override(oid)


@app.post("/operate/rule")
def operate_rule(req: RuleReq):
    return _op().add_rule(req.text)


@app.get("/operate/report")
def operate_report():
    s = _op()
    return s.reports[-1] if s.reports and s.snapshot()["clock"]["day_over"] else s.report()


@app.websocket("/operate/ws")
async def operate_ws(ws: WebSocket):
    """One snapshot per second (the clock, set-points, plan, events, ADMM traffic, device health)."""
    await ws.accept()
    s = await asyncio.get_running_loop().run_in_executor(None, _op)
    try:
        while True:
            await ws.send_json(s.snapshot())
            await asyncio.sleep(1.0)
    except Exception:
        return


@app.websocket("/live")
async def live(ws: WebSocket):
    """Streams one ADMM (exact local solver for speed) slot result per message for the requested scenario."""
    from .admm import run_day
    await ws.accept()
    req = await ws.receive_json()
    campus, _ = _ctx()
    day = _day(req.get("scenario", "outage_fest"))
    kill = None
    if req.get("kill_zone"):
        kill = (campus.names.index(req["kill_zone"]), int(req.get("kill_slot", 74)))
    q: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def work():
        run_day(campus, day, method=req.get("method", "exact"), kill=kill,
                on_slot=lambda d: loop.call_soon_threadsafe(q.put_nowait, d))
        loop.call_soon_threadsafe(q.put_nowait, None)

    threading.Thread(target=work, daemon=True).start()
    while True:
        d = await q.get()
        if d is None:
            break
        await ws.send_json(d)
    await ws.close()
