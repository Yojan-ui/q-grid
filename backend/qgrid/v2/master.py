"""Benders master of one building: choose the hourly binaries y given the optimality cuts from its subproblem.

    J(y) = c y + c0 + max_k (a_k + g_k y) + BIG * (tank-level violation + one-hot violation)

Exact master: MILP (HiGHS) with all cuts, tank levels and one-hot starts as hard constraints (tank bounds
softened with a large penalty so the master is always feasible). Its optimum is the lower bound and the
reference that every heuristic master is checked against.

QUBO master (QAOA / QIEA / simulated annealing): block coordinate descent. Blocks hold <= 16 binaries
(12 consecutive hours of one device, or one flexible job's start options). For a block, the other binaries are
fixed and the block QUBO is
    linear: c_B + g_{k*,B}   (k* = cut active at the incumbent)
    one-hot penalty for a job's start options, quadratic tank-band penalty for the pump hours.
The solver's candidate bitstrings (QAOA: the measured shots) are scored with the true J and the best is kept
if it improves J. Each QAOA block is verified against brute force over all 2^|B| assignments of the block.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import highspy
import numpy as np

from ..qubo import QUBO
from ..solvers.anneal import anneal
from ..solvers.qaoa import load_params, run_qaoa
from ..solvers.qiea import qiea
from .building import Layout

BIG = 1e5          # Rs per m3 of tank violation / per unit one-hot violation (ASSUMPTION, dominates any cost)


@dataclass
class MasterStats:
    blocks: int = 0
    block_solves: int = 0
    block_opt: int = 0               # QAOA's best measured block assignment == exact block optimum
    improved: int = 0
    time_s: float = 0.0


@dataclass
class Master:
    lay: Layout
    cuts_a: list = field(default_factory=list)
    cuts_g: list = field(default_factory=list)

    def add_cut(self, value: float, grad: np.ndarray, y: np.ndarray):
        self.cuts_a.append(float(value - grad @ y))
        self.cuts_g.append(np.asarray(grad, float).copy())

    # ---------------------------------------------------------------- objective
    def J(self, Y: np.ndarray) -> np.ndarray:
        Y = np.atleast_2d(Y)
        lay = self.lay
        G = np.array(self.cuts_g)
        out = np.einsum("mj,j->m", Y, lay.c) + lay.c0
        out = out + (np.einsum("mj,kj->mk", Y, G) + np.array(self.cuts_a)[None, :]).max(axis=1)
        return out + BIG * self.violation(Y)

    def violation(self, Y: np.ndarray) -> np.ndarray:
        lay = self.lay
        v = np.zeros(len(Y))
        if lay.tank_A is not None:
            lv = lay.tank_b[None, :] + np.einsum("mj,hj->mh", Y, lay.tank_A)
            v += np.maximum(lay.tank_lo - lv, 0).sum(axis=1) + np.maximum(lv - lay.tank_hi, 0).sum(axis=1)
        for g in lay.onehot:
            v += np.abs(Y[:, g].sum(axis=1) - 1)
        for k, val in lay.fixed.items():
            v += np.abs(Y[:, k] - val) * 10
        return v

    # ---------------------------------------------------------------- exact MILP
    def exact(self, time_limit: float = 20.0, center: np.ndarray | None = None,
              radius: int | None = None) -> tuple[np.ndarray, float]:
        """Exact master. With (center, radius): trust region, at most `radius` binaries flipped from center."""
        lay = self.lay
        ny = lay.ny
        H = len(lay.tank_b) if lay.tank_A is not None else 0
        h = highspy.Highs()
        h.setOptionValue("output_flag", False)
        h.setOptionValue("time_limit", time_limit)
        h.setOptionValue("mip_rel_gap", 1e-6)
        lo = np.zeros(ny); hi = np.ones(ny)
        for k, v in lay.fixed.items():
            lo[k] = hi[k] = v
        # columns: y (ny), theta, tank slack low (H), tank slack high (H)
        ncol = ny + 1 + 2 * H
        cost = np.r_[lay.c, 1.0, np.full(2 * H, BIG)]
        clo = np.r_[lo, -highspy.kHighsInf, np.zeros(2 * H)]
        chi = np.r_[hi, highspy.kHighsInf, np.full(2 * H, highspy.kHighsInf)]
        h.addVars(ncol, clo, chi)
        h.changeColsCost(ncol, np.arange(ncol, dtype=np.int32), cost)
        h.changeColsIntegrality(ny, np.arange(ny, dtype=np.int32), np.full(ny, highspy.HighsVarType.kInteger))
        th = ny
        for a, g in zip(self.cuts_a, self.cuts_g):          # theta - g y >= a
            idx = np.r_[np.arange(ny), th].astype(np.int32)
            h.addRow(a, highspy.kHighsInf, ny + 1, idx, np.r_[-g, 1.0])
        for grp in lay.onehot:
            h.addRow(1.0, 1.0, len(grp), np.array(grp, np.int32), np.ones(len(grp)))
        for t in range(H):                                   # lo <= b + A y + sl_lo - sl_hi <= hi
            idx = np.r_[np.arange(ny), ny + 1 + t, ny + 1 + H + t].astype(np.int32)
            val = np.r_[lay.tank_A[t], 1.0, -1.0]
            h.addRow(lay.tank_lo - lay.tank_b[t], lay.tank_hi - lay.tank_b[t], len(idx), idx, val)
        if center is not None and radius is not None:      # sum_{c=0} y + sum_{c=1} (1 - y) <= radius
            sgn = np.where(center > 0.5, -1.0, 1.0)
            h.addRow(-highspy.kHighsInf, radius - float(center.sum()), ny, np.arange(ny, dtype=np.int32), sgn)
        h.run()
        x = np.array(h.getSolution().col_value)
        y = np.round(x[:ny])
        return y, float(self.J(y)[0])

    # ---------------------------------------------------------------- QUBO block descent
    def blocks(self, max_q: int = 16) -> list[np.ndarray]:
        lay = self.lay
        out, grouped = [], set()
        for g in lay.onehot:
            g = [k for k in g if k not in lay.fixed]
            for s in range(0, len(g), max_q):
                out.append(np.array(g[s:s + max_q]))
            grouped.update(g)
        by_kind: dict = {}
        for k, nm in enumerate(lay.names):
            if k in grouped or k in lay.fixed or nm[0] == "flex":
                continue
            by_kind.setdefault(nm[0], []).append(k)
        chunk = min(12, max_q)
        for ks in by_kind.values():
            for s in range(0, len(ks), chunk):
                out.append(np.array(ks[s:s + chunk]))
        return [b for b in out if len(b)]

    def block_qubo(self, y: np.ndarray, B: np.ndarray) -> QUBO:
        lay = self.lay
        n = len(B)
        k_act = int(np.argmax(np.array(self.cuts_a) + np.array(self.cuts_g) @ y))
        lin = lay.c[B] + self.cuts_g[k_act][B]
        M = np.diag(lin)
        const = 0.0
        scale = float(np.abs(lin).max()) + 1.0
        for g in lay.onehot:                                 # A (sum y - 1)^2 on a job's options in the block
            m = np.isin(B, g)
            if m.any():
                A = 2 * scale
                a = m.astype(float)
                M += A * np.outer(a, a)
                M[np.diag_indices(n)] += -2 * A * a
                const += A
        if lay.tank_A is not None and any(lay.names[k][0] == "pump" for k in B):
            rest = y.copy(); rest[B] = 0
            base = lay.tank_b + lay.tank_A @ rest
            mid = 0.5 * (lay.tank_lo + lay.tank_hi)
            span = max(lay.tank_hi - lay.tank_lo, 1e-6)
            AB = lay.tank_A[:, B] / span
            d = (base - mid) / span
            lam = scale / max(len(base), 1) * 4
            M += lam * AB.T @ AB
            M[np.diag_indices(n)] += lam * 2 * AB.T @ d
            const += lam * float(d @ d)
        return QUBO(const, M)

    def heuristic(self, y0: np.ndarray, solver: str, seed: int, sweeps: int = 2, max_q: int = 16,
                  verify: bool = True, p: int = 2, shots: int = 256) -> tuple[np.ndarray, float, MasterStats]:
        import time
        t0 = time.perf_counter()
        st = MasterStats()
        y = y0.astype(float).copy()
        for k, v in self.lay.fixed.items():
            y[k] = v
        Jy = float(self.J(y)[0])
        blocks = self.blocks(max_q)
        st.blocks = len(blocks)
        params = load_params(p) if solver == "qaoa" else None
        rng = np.random.default_rng(seed)
        for sw in range(sweeps):
            for bi, B in enumerate(blocks):
                q = self.block_qubo(y, B)
                s = int(rng.integers(1 << 30))
                if solver == "qaoa":
                    cand = run_qaoa(q, p=p, shots=shots, seed=s, params=params).samples
                elif solver == "qiea":
                    best, _, pop = qiea(q, pop=12, gens=60, seed=s, x0=y[B])
                    cand = np.vstack([best[None, :], pop])
                elif solver == "sa":
                    cand = anneal(q, n_chains=8, sweeps=40, seed=s)
                else:
                    raise ValueError(solver)
                cand = np.unique(np.vstack([cand, y[B][None, :]]), axis=0)
                Y = np.repeat(y[None, :], len(cand), axis=0)
                Y[:, B] = cand
                Jc = self.J(Y)
                j = int(np.argmin(Jc))
                st.block_solves += 1
                if verify and solver == "qaoa":
                    ex = self._block_exact(y, B)
                    st.block_opt += int(Jc[j] <= ex + 1e-6 * max(1.0, abs(ex)))
                if Jc[j] < Jy - 1e-9:
                    y, Jy = Y[j].copy(), float(Jc[j])
                    st.improved += 1
        st.time_s = time.perf_counter() - t0
        return y, Jy, st

    def _block_exact(self, y: np.ndarray, B: np.ndarray) -> float:
        n = len(B)
        Z = ((np.arange(1 << n)[:, None] >> np.arange(n)[None, :]) & 1).astype(float)
        best = np.inf
        for s in range(0, len(Z), 8192):
            Y = np.repeat(y[None, :], min(8192, len(Z) - s), axis=0)
            Y[:, B] = Z[s:s + 8192]
            best = min(best, float(self.J(Y).min()))
        return best
