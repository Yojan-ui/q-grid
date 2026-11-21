"""Decentralised consensus ADMM over tie-lines, receding horizon over the 96 slots of a day.

No coordinator. Per slot t:
  1. neighbours exchange their marginal energy price for the slot (one number; no load/PV/battery data);
     duals start at the mean price, z warm-starts from the previous agreed flow, rho_k = rho0 * growth^k
  2. every live zone solves its local QUBO (tiered solver) with targets v_l = z_l - u_l; a zone whose lines
     all agreed last round keeps its proposal (sticky)
  3. exchange proposals -> z = relax*avg + (1-relax)*z_prev, u update; stop when every line agrees or at max_iter
  4. ADMM with binary variables has no convergence guarantee. Disagreeing lines go to bilateral resolution
     (each end reports its local optimum with the line fixed at -F, 0, +F; the level with the lowest sum
     wins) or, if disabled, to 0 (always feasible). Zones whose final flows differ from their last proposal
     re-solve with flows fixed; commands pass the safety layer.
A killed / silent zone is islanded: its lines carry 0 and it runs its safe default.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .agent import BuildingAgent
from .model import DT, T, Campus, DayData, Schedule
from . import qubo as Q
from .qubo import decode
from .solvers import solve_local


def true_objective(lp, x) -> float:
    """QUBO objective with the fitted grid surrogate replaced by the exact slot cost (tariff / VOLL)."""
    groups, _, _ = Q.build_groups(lp)
    tot = sum(float(q.energy(x)[0]) for k, q in groups.items() if k != "grid")
    return tot + Q.evaluate(lp, x)["exact_grid_cost"]


def critical_guard(campus, agents, flow, t, dead) -> int:
    """Safety layer, islanded slots: a zone never exports on a tie-line if that leaves its own critical load
    unserved; such lines are set to 0 (both ends apply the same rule). Returns the number of lines cut."""
    cut = 0
    for _ in range(len(campus.lines)):
        changed = False
        for i, ag in enumerate(agents):
            if i in dead:
                continue
            out = sum(s * flow[l] for l, s in ag.incident)
            if ag.critical_shortfall(t, out) > 1e-6:
                exporting = [(s * flow[l], l) for l, s in ag.incident if s * flow[l] > 0]
                if exporting:
                    flow[max(exporting)[1]] = 0.0
                    cut += 1
                    changed = True
        if not changed:
            break
    return cut


def consensus_update(f_self: float, f_other: float, u_self: float) -> tuple[float, float]:
    z = 0.5 * (f_self + f_other)
    return z, u_self + f_self - z


def initial_duals(mp_a: float, mp_b: float, rho: float, H: int) -> tuple[float, float]:
    """Price-initialised scaled duals for a line a->b: the sender earns pi0*dt*H per kW, the receiver pays it."""
    u = 0.5 * (mp_a + mp_b) * DT * H / rho
    return -u, u


def rho0(campus: Campus, day: DayData) -> float:
    return float(campus.cfg["admm"]["rho"]) * float(day.obj_imp.mean()) * DT / campus.step_kw


@dataclass
class DayStats:
    iters: list[int] = field(default_factory=list)
    converged: list[bool] = field(default_factory=list)
    oscillations: int = 0
    tiers: dict = field(default_factory=lambda: {"qaoa": 0, "qiea": 0, "anneal": 0, "exact": 0})
    qaoa: list[dict] = field(default_factory=list)
    n_solves: int = 0
    solve_time_s: float = 0.0
    slot_time_s: list[float] = field(default_factory=list)
    disagreements: int = 0
    resolved_bilateral: int = 0
    critical_cuts: int = 0
    explanations: dict = field(default_factory=dict)
    log: list[dict] = field(default_factory=list)
    slots: list[dict] = field(default_factory=list)
    kill: dict | None = None

    def summary(self) -> dict:
        q = self.qaoa
        out = {"admm_iters_mean": float(np.mean(self.iters)) if self.iters else 0.0,
               "admm_iters_max": int(np.max(self.iters)) if self.iters else 0,
               "admm_convergence_rate": float(np.mean(self.converged)) if self.converged else 0.0,
               "admm_oscillations": self.oscillations,
               "n_local_solves": self.n_solves, "local_solve_time_s": self.solve_time_s,
               "replan_time_s": float(np.mean(self.slot_time_s)) if self.slot_time_s else 0.0,
               "tiers": dict(self.tiers), "line_disagreements": self.disagreements,
               "resolved_bilateral": self.resolved_bilateral, "critical_guard_cuts": self.critical_cuts}
        if q:
            out.update({"qaoa_p_opt": float(np.mean([m["qaoa_p_opt"] for m in q])),
                        "qaoa_approx_ratio": float(np.mean([m["qaoa_approx_ratio"] for m in q])),
                        "qaoa_feasible_rate": float(np.mean([m["qaoa_feasible"] for m in q])),
                        "qaoa_found_opt_rate": float(np.mean([m["qaoa_found_opt"] for m in q])),
                        "qaoa_n_qubits_mean": float(np.mean([m["n_qubits"] for m in q]))})
        if self.kill:
            out["kill"] = self.kill
        return out


def run_day(campus: Campus, day: DayData, method: str = "qaoa", log: bool = False,
            kill: tuple[int, int] | None = None, seed: int | None = None,
            rules: list[dict] | None = None, t_range: tuple[int, int] | None = None,
            explain_slots: set[int] | None = None, on_slot=None) -> tuple[Schedule, DayStats]:
    """t_range (tests/what-if only): optimise slots in [a, b); other slots run the safe default."""
    cfg = campus.cfg
    ac, qc = cfg["admm"], cfg["qaoa"]
    seed = qc["seed"] if seed is None else seed
    H0 = ac["horizon_slots"]
    agents = [BuildingAgent(campus, day, i, H0, rules) for i in range(campus.n)]
    sched = Schedule.empty(campus)
    st = DayStats()
    r0 = rho0(campus, day)
    growth = float(ac.get("rho_growth", 1.2))
    relax = float(ac.get("relax", 1.0))
    nL = len(campus.lines)
    prev_flow = np.zeros(nL)

    def solve(ag, t, free, fixed_out, v, rho, k):
        t0 = time.perf_counter()
        lp = ag.local_problem(t, free, fixed_out=fixed_out, v=v, rho=rho)
        q = method.startswith("qaoa")
        sol = solve_local(lp, method=method, p=qc["p"], shots=qc["shots"], seed=seed + 7919 * t + 101 * ag.i + k,
                          warm_key=ag.name if q else None, warm_iters=int(qc.get("warm_start_iters", 0)) if q else 0)
        st.solve_time_s += time.perf_counter() - t0
        st.n_solves += 1
        st.tiers[sol.tier] += 1
        if "qaoa_p_opt" in sol.metrics:
            st.qaoa.append({k2: sol.metrics[k2] for k2 in
                            ("qaoa_p_opt", "qaoa_approx_ratio", "qaoa_feasible", "qaoa_found_opt", "n_qubits")})
        return lp, sol, decode(lp, sol.x)

    for t in range(T):
        t_slot = time.perf_counter()
        if t_range is not None and not (t_range[0] <= t < t_range[1]):
            for i, ag in enumerate(agents):
                c = ag.apply_safe_default(t)
                sched.p_bat[i, t], sched.dg_kw[i, t], sched.pump_on[i, t] = c["p_bat"], c["dg_kw"], float(c["pump_on"])
            for i, ag in enumerate(agents):
                sched.flex_start[i].update(ag.started)
            st.iters.append(0); st.converged.append(True); st.slot_time_s.append(0.0)
            continue
        dead = {kill[0]} if kill is not None and t >= kill[1] else set()
        alive = [i for i in range(campus.n) if i not in dead]
        active = [l for l, (a, b) in enumerate(campus.lines) if a not in dead and b not in dead]
        H = min(H0, T - t)
        z = {l: float(prev_flow[l]) for l in active}
        u = {}
        for l in active:
            a, b = campus.lines[l]
            u[(l, a)], u[(l, b)] = initial_duals(agents[a].mp[t], agents[b].mp[t], r0, H)
        prop, last, settled, hist = {}, {}, set(), []
        k_used = 0
        agreed = True
        for k in range(ac["max_iter"]):
            rho = r0 * growth ** k
            for i in alive:
                if i in settled:
                    continue
                ag = agents[i]
                free = [(l, s) for (l, s) in ag.incident if l in z]
                lp, sol, dec = solve(ag, t, free, 0.0, {l: z[l] - u[(l, i)] for l, _ in free}, rho, k)
                last[i] = (lp, sol, dec)
                for l, _ in free:
                    prop[(l, i)] = dec["flows"][l]
            z_prev = dict(z)
            agreed, rp = True, 0.0
            for l in active:
                a, b = campus.lines[l]
                z[l] = relax * 0.5 * (prop[(l, a)] + prop[(l, b)]) + (1 - relax) * z_prev[l]
                u[(l, a)] += prop[(l, a)] - z[l]
                u[(l, b)] += prop[(l, b)] - z[l]
                rp = max(rp, abs(prop[(l, a)] - prop[(l, b)]))
                agreed &= prop[(l, a)] == prop[(l, b)]
            vec = tuple(prop[(l, i)] for l in active for i in campus.lines[l])
            if len(hist) >= 2 and vec == hist[-2] and vec != hist[-1]:
                st.oscillations += 1
            hist.append(vec)
            settled = {i for i in alive if all(prop[(l, campus.lines[l][0])] == prop[(l, campus.lines[l][1])]
                                               for l, _ in agents[i].incident if l in z)}
            k_used = k + 1
            if log:
                st.log.append({"t": t, "k": k, "rho": rho,
                               "proposals": {l: [prop[(l, campus.lines[l][0])], prop[(l, campus.lines[l][1])]] for l in active},
                               "z": {l: z[l] for l in active},
                               "u": {l: [u[(l, campus.lines[l][0])], u[(l, campus.lines[l][1])]] for l in active},
                               "r_primal": rp, "r_dual": rho * max([abs(z[l] - z_prev[l]) for l in active] or [0.0]),
                               "agreed": bool(agreed)})
            if agreed:
                break
        st.iters.append(k_used)
        st.converged.append(bool(agreed))

        flow = np.zeros(nL)
        for l in active:
            a, b = campus.lines[l]
            if prop[(l, a)] == prop[(l, b)]:
                flow[l] = prop[(l, a)]
                continue
            st.disagreements += 1
            if ac.get("bilateral_resolution", True):
                levels = [-campus.step_kw, 0.0, campus.step_kw]
                tot = np.zeros(3)
                for end in (a, b):
                    ag = agents[end]
                    others = sum(s * prop[(l2, end)] for l2, s in ag.incident if l2 in z and l2 != l)
                    sgn = dict(ag.incident)[l]
                    for q_, f in enumerate(levels):
                        lp = ag.local_problem(t, [], fixed_out=others + sgn * f)
                        tot[q_] += true_objective(lp, solve_local(lp, method="exact").x)
                flow[l] = levels[int(np.argmin(tot))]
                st.resolved_bilateral += 1
        st.critical_cuts += critical_guard(campus, agents, flow, t, dead)
        for i in range(campus.n):
            ag = agents[i]
            out = sum(s * flow[l] for l, s in ag.incident)
            if i in dead:
                cmd = ag.apply_safe_default(t, out)
            else:
                lp_i, sol_i, dec = last[i] if i in last else (None, None, None)
                if dec is None or any(dec["flows"].get(l, 0.0) != flow[l] for l, _ in ag.incident if l in z):
                    lp_i, sol_i, dec = solve(ag, t, [], out, {}, 0.0, 99)
                if explain_slots and t in explain_slots:
                    from .explain import explain
                    st.explanations.setdefault(t, {})[ag.name] = explain(lp_i, sol_i.x, zone=ag.name)
                cmd = ag.apply(t, dec, out)
            sched.p_bat[i, t], sched.dg_kw[i, t], sched.pump_on[i, t] = cmd["p_bat"], cmd["dg_kw"], float(cmd["pump_on"])
        for i, ag in enumerate(agents):
            for name, s in ag.started.items():
                sched.flex_start[i][name] = s
        sched.flows[:, t] = flow
        prev_flow = flow
        st.slot_time_s.append(time.perf_counter() - t_slot)
        if log:
            st.slots.append({"t": t, "iters": k_used, "converged": bool(agreed), "time_s": st.slot_time_s[-1],
                             "flows": flow.tolist(), "alive": alive})
        if on_slot is not None:
            on_slot({"t": t, "iters": k_used, "converged": bool(agreed), "flows": flow.tolist(),
                     "p_bat": sched.p_bat[:, t].tolist(), "dg_kw": sched.dg_kw[:, t].tolist(),
                     "pump_on": sched.pump_on[:, t].tolist(), "alive": alive, "time_s": st.slot_time_s[-1]})
        if kill is not None and t == kill[1]:
            st.kill = {"building": campus.names[kill[0]], "slot": t, "iters_at_kill_slot": k_used,
                       "agreed_at_kill_slot": bool(agreed), "replan_time_s": st.slot_time_s[-1]}
    if st.kill is not None:
        later = [t for t in range(kill[1], T) if st.converged[t]]
        st.kill["slots_to_reconverge"] = (later[0] - kill[1]) if later else None
    sched.info = {"method": f"ADMM+{method}", **st.summary()}
    return sched, st
