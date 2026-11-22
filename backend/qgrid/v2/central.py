"""Verification only (never used to operate the campus): the same continuous subproblem solved as one LP,
with each cable's copies tied by equality constraints. Used to check that decentralised ADMM reaches the
central optimum and that the Benders cuts are valid."""
from __future__ import annotations

import highspy
import numpy as np
import scipy.sparse as sp

from ..model import Campus
from .admm_lp import _edge_slices
from .building import BuildingLP


def central_lp(campus: Campus, blp: list[BuildingLP], ys: list[np.ndarray]) -> tuple[float, list[np.ndarray]]:
    H = blp[0].H
    offs = np.cumsum([0] + [b.ncol for b in blp])
    blocks, lo, hi = [], [], []
    for b, y in zip(blp, ys):
        l_, h_ = b.row_bounds(y)
        blocks.append(b.A); lo.append(l_); hi.append(h_)
    A = sp.block_diag(blocks, format="lil")
    rows = []
    for l, (a, c) in enumerate(campus.lines):
        ka = [k for k, (ll, _) in enumerate(blp[a].inc) if ll == l][0]
        kc = [k for k, (ll, _) in enumerate(blp[c].inc) if ll == l][0]
        ia = offs[a] + blp[a].coupled[_edge_slices(H, len(blp[a].inc), ka, blp[a].peak)]
        ic = offs[c] + blp[c].coupled[_edge_slices(H, len(blp[c].inc), kc, blp[c].peak)]
        for p, q in zip(ia, ic):
            rows.append((p, q))
    E = sp.lil_matrix((len(rows), offs[-1]))
    for r, (p, q) in enumerate(rows):
        E[r, p] = 1.0; E[r, q] = -1.0
    A = sp.vstack([A.tocsc(), E.tocsc()], format="csc")
    lo = np.concatenate(lo + [np.zeros(len(rows))]); hi = np.concatenate(hi + [np.zeros(len(rows))])
    h = highspy.Highs(); h.setOptionValue("output_flag", False)
    lp = highspy.HighsLp(); lp.num_col_, lp.num_row_ = A.shape[1], A.shape[0]
    lp.col_cost_ = np.concatenate([b.cost0 for b in blp])
    lp.col_lower_ = np.concatenate([b.lb for b in blp]); lp.col_upper_ = np.concatenate([b.ub for b in blp])
    lp.row_lower_, lp.row_upper_ = lo, hi
    lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_, lp.a_matrix_.index_, lp.a_matrix_.value_ = A.indptr, A.indices, A.data
    lp.a_matrix_.num_col_, lp.a_matrix_.num_row_ = A.shape[1], A.shape[0]
    h.passModel(lp); h.run()
    assert h.getModelStatus() == highspy.HighsModelStatus.kOptimal, h.getModelStatus()
    x = np.array(h.getSolution().col_value)
    return float(h.getInfo().objective_function_value), [x[offs[i]:offs[i + 1]] for i in range(len(blp))]
