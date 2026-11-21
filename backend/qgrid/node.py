"""Networked mode: one process per building, peer-to-peer websockets, no coordinator.

    python -m qgrid.node --building hostel --day 2023-04-13 --scenario A --out results/net/hostel.json

Each node owns ONE building's private data and talks only to its tie-line neighbours. Per slot it runs
synchronous ADMM rounds; every message carries its proposed flows plus two counters used for
distributed termination without a coordinator:
  s  rounds of uninterrupted local agreement, s_i <- 1 + min(s_i, s_j over neighbours) if agreed else 0
     -> stop proposing when s_i >= 2D+1 (or at max_iter, which every node reaches in the same round)
  q  rounds of being stopped,               q_i <- 1 + min(q_i, q_j) if stopped else 0
     -> finalise when q_i >= D+1; all nodes reach this in the same round (D = n-1 >= diameter)
Every node also sends a heartbeat every 0.5 s, so a node that is itself waiting on a dead neighbour is
not mistaken for dead. A neighbour silent (no message of any kind) for > neighbour_timeout_s (3 s) is declared dead: its lines go to 0 (island mode)
for the rest of the day. Final flow on a line = common proposal if both ends agree, else 0.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import websockets

from . import data as qdata
from .admm import consensus_update, rho0
from .agent import BuildingAgent
from .model import T, load_campus, make_day
from .qubo import decode
from .solvers import solve_local

HOST = "127.0.0.1"


class Node:
    def __init__(self, building: str, day: str, scenario: str, method: str, port_base: int,
                 die_at_slot: int | None = None, slots: int = T, synthetic: bool = False):
        self.campus = load_campus()
        cfg = self.campus.cfg
        self.i = self.campus.names.index(building)
        if synthetic:  # unit tests / CI only
            from .synthetic import synthetic_day
            proc, dd = None, synthetic_day(self.campus, scenario=scenario)
        else:
            proc = qdata.load_processed()
            dd = make_day(self.campus, proc, day, scenario)
        self.agent = BuildingAgent(self.campus, dd, self.i, cfg["admm"]["horizon_slots"])
        self.r0 = rho0(self.campus, dd)
        del dd, proc  # the node keeps only its own building's data (inside the agent) + public prices
        self.method, self.port_base, self.die_at, self.slots = method, port_base, die_at_slot, slots
        self.neigh = self.campus.neighbours(self.i)
        self.line_of = {}  # neighbour -> line idx
        for l, (a, b) in enumerate(self.campus.lines):
            if self.i in (a, b):
                self.line_of[b if a == self.i else a] = l
        self.alive = set(self.neigh)
        self.timeout = float(cfg["admm"]["neighbour_timeout_s"])
        self.max_iter = int(cfg["admm"]["max_iter"])
        self.D = self.campus.n - 1
        self.inbox: dict[tuple, dict] = {}
        self.cond = asyncio.Condition()
        self.out: dict[int, websockets.ClientConnection] = {}
        self.last_seen: dict[int, float] = {}
        self.record = {"building": building, "i": self.i, "p_bat": [], "flows": {}, "flex_start": {},
                       "slots": [], "dead_neighbours": {}}

    # ------------------------------------------------------------------ transport
    async def _handler(self, ws):
        async for raw in ws:
            m = json.loads(raw)
            async with self.cond:
                self.last_seen[m["from"]] = time.monotonic()
                if m.get("type") != "hb":
                    self.inbox[(m["slot"], m["round"], m["from"])] = m
                self.cond.notify_all()

    async def _heartbeat(self):
        while True:
            await self._send({"type": "hb", "from": self.i})
            await asyncio.sleep(0.5)

    async def _connect(self):
        for j in self.neigh:
            uri = f"ws://{HOST}:{self.port_base + j}"
            for _ in range(200):
                try:
                    self.out[j] = await websockets.connect(uri, max_size=None)
                    break
                except OSError:
                    await asyncio.sleep(0.05)

    async def _send(self, msg: dict):
        raw = json.dumps(msg)
        for j in list(self.alive):
            try:
                await self.out[j].send(raw)
            except Exception:
                pass  # detected as silence by the receiver side

    async def _recv(self, t: int, k: int) -> dict[int, dict]:
        got = {}
        t0 = time.monotonic()
        async with self.cond:
            while True:
                for j in list(self.alive):
                    if j not in got and (t, k, j) in self.inbox:
                        got[j] = self.inbox.pop((t, k, j))
                if all(j in got for j in self.alive):
                    return got
                now = time.monotonic()
                waiting = [j for j in self.alive if j not in got]
                for j in waiting:
                    if now - max(self.last_seen.get(j, t0), t0) > self.timeout:
                        self.alive.discard(j)
                        self.record["dead_neighbours"][self.campus.names[j]] = {
                            "slot": t, "round": k, "detected_after_s": round(now - t0, 3)}
                if all(j in got for j in self.alive):
                    return got
                rem = min(max(self.last_seen.get(j, t0), t0) + self.timeout for j in self.alive if j not in got) - now
                rem = max(rem, 0.01)
                try:
                    await asyncio.wait_for(self.cond.wait(), rem)
                except asyncio.TimeoutError:
                    pass

    # ------------------------------------------------------------------ ADMM per slot
    def _solve(self, t, free, fixed_out, v, rho, k):
        lp = self.agent.local_problem(t, free, fixed_out=fixed_out, v=v, rho=rho)
        qc = self.campus.cfg["qaoa"]
        sol = solve_local(lp, method=self.method, p=qc["p"], shots=qc["shots"],
                          seed=qc["seed"] + 7919 * t + 101 * self.i + k)
        return decode(lp, sol.x), sol.tier

    async def run_slot(self, t: int):
        t_start = time.monotonic()
        lines = {self.line_of[j]: j for j in self.alive}
        sign = dict(self.agent.incident)
        z = {l: self.prev_flow.get(l, 0.0) for l in lines}
        u = {l: 0.0 for l in lines}
        prop, nprop = {}, {}
        dec = None
        s = q = 0
        stopped = settled = False
        k = 0
        tiers = []
        while True:
            lines = {l: j for l, j in lines.items() if j in self.alive}
            if not stopped and not settled:
                free = [(l, sign[l]) for l in lines]
                v = {l: z[l] - u[l] for l in lines}
                dec, tier = self._solve(t, free, 0.0, v, self.r0 * 1.5 ** min(k, self.max_iter), k)
                tiers.append(tier)
                prop = {l: dec["flows"][l] for l in lines}
            await self._send({"from": self.i, "slot": t, "round": k, "flows": {str(l): f for l, f in prop.items()},
                              "s": s, "q": q, "stopped": stopped})
            got = await self._recv(t, k)
            lines = {l: j for l, j in lines.items() if j in self.alive}
            nprop = {l: got[j]["flows"].get(str(l), 0.0) for l, j in lines.items()}
            for l in lines:
                z[l], u[l] = consensus_update(prop.get(l, 0.0), nprop[l], u[l])
            agree = all(prop.get(l, 0.0) == nprop[l] for l in lines)
            settled = agree
            nb_s = [got[j]["s"] for j in lines.values()]
            nb_q = [got[j]["q"] for j in lines.values()]
            s = 1 + min([s] + nb_s) if agree else 0
            if not stopped and (s >= 2 * self.D + 1 or k + 1 >= self.max_iter):
                stopped = True
            q = 1 + min([q] + nb_q) if stopped else 0
            k += 1
            if q >= self.D + 1 or k > self.max_iter + 4 * self.D + 4:
                break
        flow = {l: (prop.get(l, 0.0) if prop.get(l, 0.0) == nprop.get(l) else 0.0) for l in sign}
        for l in sign:
            if l not in lines:
                flow[l] = 0.0
        out = sum(sign[l] * flow[l] for l in sign)
        if dec is None or any(dec["flows"].get(l, 0.0) != flow[l] for l in sign):
            dec, tier = self._solve(t, [], out, {}, 0.0, 99)
            tiers.append(tier)
        cmd = self.agent.apply(t, dec["mode0"], dec["start"], out)
        self.prev_flow = {l: flow[l] for l in lines}
        self.record["p_bat"].append(cmd["p_bat"])
        for l in sign:
            self.record["flows"].setdefault(str(l), []).append(flow[l])
        self.record["slots"].append({"t": t, "rounds": k, "solves": len(tiers), "tiers": tiers,
                                     "time_s": time.monotonic() - t_start, "alive": sorted(self.alive),
                                     "agreed_all": all(prop.get(l) == nprop.get(l) for l in lines)})

    async def main(self, out_path: str):
        server = await websockets.serve(self._handler, HOST, self.port_base + self.i, max_size=None)
        await self._connect()
        hb = asyncio.create_task(self._heartbeat())
        self.prev_flow = {}
        try:
            for t in range(self.slots):
                if self.die_at is not None and t == self.die_at:
                    os._exit(0)  # simulated crash: no goodbye, neighbours must detect silence
                await self.run_slot(t)
        finally:
            self.record["flex_start"] = dict(self.agent.started)
            Path(out_path).write_text(json.dumps(self.record))
            await asyncio.sleep(1.0)  # keep answering heartbeats while neighbours finish
            hb.cancel()
            server.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--building", required=True)
    ap.add_argument("--day", required=True)
    ap.add_argument("--scenario", default="A")
    ap.add_argument("--method", default="qaoa")
    ap.add_argument("--port-base", type=int, default=8765)
    ap.add_argument("--die-at-slot", type=int, default=None)
    ap.add_argument("--slots", type=int, default=T)
    ap.add_argument("--out", required=True)
    ap.add_argument("--synthetic", action="store_true", help="SYNTHETIC day (tests/CI only)")
    a = ap.parse_args()
    node = Node(a.building, a.day, a.scenario, a.method, a.port_base, a.die_at_slot, a.slots, a.synthetic)
    asyncio.run(node.main(a.out))


if __name__ == "__main__":
    main()
