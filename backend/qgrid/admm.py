"""Decentralised consensus ADMM over tie-lines, receding horizon over the 96 slots of a day.

No coordinator: for each line the two endpoint buildings exchange only their proposed flow; both
compute the same z = (f_a + f_b)/2 locally and update their own scaled dual u. Buildings never share
load, PV or battery data.

Per slot t:
  1. neighbours exchange their marginal energy price for the slot (one number, no load/PV data);
     duals start at the mean price (initial_duals), z_l warm-starts from the previous agreed flow,
     rho_k = rho0 * growth^k
  2. every live building solves its local QUBO (tiered solver) with targets v_l = z_l - u_l
     (sticky agreement: a building whose lines all agreed last round keeps its proposal)
  3. exchange proposals with neighbours -> z, u update; stop when every line is agreed (both ends
     propose the same level) or at max_iter
  4. disagreeing lines -> 0 (always feasible); buildings whose final flows differ from their last
     proposal re-solve once with flows fixed; apply slot t through the safety layer
A killed / silent building is islanded: its lines carry 0 and it runs its safe default.
`run_day` is the in-process engine (benchmark); `qgrid.node` runs the same math one process per
building over websockets.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .agent import BuildingAgent
from .model import DT, T, Campus, DayData, Schedule
from .qubo import decode
from .solvers import solve_local


def consensus_update(f_self: float, f_other: float, u_self: float) -> tuple[float, float]:
    z = 0.5 * (f_self + f_other)
    return z, u_self + f_self - z


def initial_duals(mp_a: float, mp_b: float, rho: float, H: int) -> tuple[float, float]:
    """Price-initialised scaled duals for a line a->b. Neighbours exchange only their marginal energy
    price for the slot; pi0 = mean. rho*u is the price the local QUBO sees on the flow, held over H slots:
    the sender (a) earns pi0*dt*H per kW, the receiver (b) pays it."""
    pi0 = 0.5 * (mp_a + mp_b)
    u = pi0 * DT * H / rho
    return -u, u


def rho0(campus: Campus, day: DayData) -> float:
    c = campus.cfg["admm"]
    return float(c["rho"]) * float(day.obj_imp.mean()) * DT / campus.step_kw


@dataclass
class DayStats:
    iters: list[int] = field(default_factory=list)
    tiers: dict = field(default_factory=lambda: {"qaoa": 0, "anneal": 0, "exact": 0})
    qaoa: list[dict] = field(default_factory=list)
    n_solves: int = 0
    solve_time_s: float = 0.0
    disagreements: int = 0
    log: list[dict] = field(default_factory=list)
    slots: list[dict] = field(default_factory=list)
    kill: dict | None = None

    def summary(self) -> dict:
        q = self.qaoa
        out = {
            "admm_iters_mean": float(np.mean(self.iters)) if self.iters else 0.0,
            "admm_iters_max": int(np.max(self.iters)) if self.iters else 0,
            "n_local_solves": self.n_solves, "local_solve_time_s": self.solve_time_s,
            "tiers": dict(self.tiers), "line_disagreements": self.disagreements,
        }
        if q:
            out.update({
                "qaoa_p_opt": float(np.mean([m["qaoa_p_opt"] for m in q])),
                "qaoa_approx_ratio": float(np.mean([m["qaoa_approx_ratio"] for m in q])),
                "qaoa_feasible_rate": float(np.mean([m["qaoa_feasible"] for m in q])),
                "qaoa_found_opt_rate": float(np.mean([m["qaoa_found_opt"] for m in q])),
                "qaoa_n_qubits_mean": float(np.mean([m["n_qubits"] for m in q])),
            })
        if self.kill:
            out["kill"] = self.kill
        return out


def run_day(campus: Campus, day: DayData, method: str = "qaoa", log: bool = False,
            kill: tuple[int, int] | None = None, seed: int | None = None) -> tuple[Schedule, DayStats]:
    cfg = campus.cfg
    ac, qc = cfg["admm"], cfg["qaoa"]
    seed = qc["seed"] if seed is None else seed
    agents = [BuildingAgent(campus, day, i, ac["horizon_slots"]) for i in range(campus.n)]
    sched = Schedule.empty(campus)
    st = DayStats()
    r0 = rho0(campus, day)
    growth = float(ac.get("rho_growth", 1.5))
    nL = len(campus.lines)
    prev_flow = np.zeros(nL)
    all_agreed = []

    def solve(ag, t, free, fixed_out, v, rho, k):
        t0 = time.perf_counter()
        lp = ag.local_problem(t, free, fixed_out=fixed_out, v=v, rho=rho)
        sol = solve_local(lp, method=method, p=qc["p"], shots=qc["shots"], seed=seed + 7919 * t + 101 * ag.i + k)
        st.solve_time_s += time.perf_counter() - t0
        st.n_solves += 1
        st.tiers[sol.tier] += 1
        if "qaoa_p_opt" in sol.metrics:
            st.qaoa.append({k2: sol.metrics[k2] for k2 in
                            ("qaoa_p_opt", "qaoa_approx_ratio", "qaoa_feasible", "qaoa_found_opt", "n_qubits")})
        return lp, sol, decode(lp, sol.x)

    for t in range(T):
        dead = set()
        if kill is not None and t >= kill[1]:
            dead.add(kill[0])
        alive = [i for i in range(campus.n) if i not in dead]
        active = [l for l, (a, b) in enumerate(campus.lines) if a not in dead and b not in dead]
        z = {l: float(prev_flow[l]) for l in active}
        u = {}
        H = min(ac["horizon_slots"], T - t)
        for l in active:
            a, b = campus.lines[l]
            u[(l, a)], u[(l, b)] = initial_duals(agents[a].mp[t], agents[b].mp[t], r0, H)
        prop = {}
        last = {}
        settled = set()  # sticky agreement: a building whose lines all agree keeps its proposal
        k_used = 0
        t_slot = time.perf_counter()
        for k in range(ac["max_iter"]):
            rho = r0 * growth ** k
            for i in alive:
                if i in settled:
                    continue
                ag = agents[i]
                free = [(l, s) for (l, s) in ag.incident if l in z]
                v = {l: z[l] - u[(l, i)] for l, _ in free}
                lp, sol, dec = solve(ag, t, free, 0.0, v, rho, k)
                last[i] = (lp, sol, dec)
                for l, _ in free:
                    prop[(l, i)] = dec["flows"][l]
            z_prev = dict(z)
            agreed = True
            rp = 0.0
            for l in active:
                a, b = campus.lines[l]
                za, u[(l, a)] = consensus_update(prop[(l, a)], prop[(l, b)], u[(l, a)])
                _, u[(l, b)] = consensus_update(prop[(l, b)], prop[(l, a)], u[(l, b)])
                z[l] = za
                rp = max(rp, abs(prop[(l, a)] - prop[(l, b)]))
                agreed &= prop[(l, a)] == prop[(l, b)]
            settled = {i for i in alive
                       if all(prop[(l, campus.lines[l][0])] == prop[(l, campus.lines[l][1])]
                              for l, _ in agents[i].incident if l in z)}
            k_used = k + 1
            if log:
                st.log.append({
                    "t": t, "k": k, "rho": rho,
                    "proposals": {l: [prop[(l, campus.lines[l][0])], prop[(l, campus.lines[l][1])]] for l in active},
                    "z": {l: z[l] for l in active},
                    "u": {l: [u[(l, campus.lines[l][0])], u[(l, campus.lines[l][1])]] for l in active},
                    "r_primal": rp, "r_dual": rho * max([abs(z[l] - z_prev[l]) for l in active] or [0.0]),
                    "agreed": bool(agreed),
                })
            if agreed:
                break
        st.iters.append(k_used)
        all_agreed.append(bool(all(prop[(l, campus.lines[l][0])] == prop[(l, campus.lines[l][1])] for l in active)))

        flow = np.zeros(nL)
        for l in active:
            a, b = campus.lines[l]
            if prop[(l, a)] == prop[(l, b)]:
                flow[l] = prop[(l, a)]
            else:
                st.disagreements += 1
        for i in range(campus.n):
            ag = agents[i]
            if i in dead:
                cmd = ag.apply_safe_default(t)
            else:
                lp, sol, dec = last[i]
                out = sum(s * flow[l] for l, s in ag.incident)
                if any(dec["flows"].get(l, 0.0) != flow[l] for l, _ in ag.incident if l in active):
                    lp, sol, dec = solve(ag, t, [], out, {}, 0.0, 99)
                cmd = ag.apply(t, dec["mode0"], dec["start"], out)
            sched.p_bat[i, t] = cmd["p_bat"]
        for i, ag in enumerate(agents):
            for name, s in ag.started.items():
                sched.flex_start[i][name] = s
        sched.flows[:, t] = flow
        prev_flow = flow
        if log:
            st.slots.append({"t": t, "iters": k_used, "time_s": time.perf_counter() - t_slot,
                             "flows": flow.tolist(), "alive": alive})
        if kill is not None and t == kill[1]:
            st.kill = {"building": campus.names[kill[0]], "slot": t, "iters_at_kill_slot": k_used,
                       "agreed_at_kill_slot": all_agreed[-1], "slot_time_s": time.perf_counter() - t_slot}
    if st.kill is not None:
        later = [t for t in range(kill[1], T) if all_agreed[t]]
        st.kill["first_full_agreement_slot"] = later[0] if later else None
        st.kill["slots_to_reconverge"] = (later[0] - kill[1]) if later else None
    st.all_agreed = all_agreed
    sched.info = {"method": f"ADMM+{method}", **st.summary()}
    return sched, st
