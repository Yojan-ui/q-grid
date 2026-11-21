# Local QUBO — derivation

Implementation: `backend/qgrid/qubo.py`. Tests: `backend/tests/test_model_qubo.py`.

Each building *i* solves, every 15-min slot *t* and every ADMM iteration, a small binary problem over
a 1-hour horizon (H = 4 slots, truncated at the end of the day). Only the first slot is applied
(receding horizon); the rest of the day is represented by a cost-to-go term.

## 1. Variables (≤ 15 qubits)

| bits | meaning | count |
|---|---|---|
| c_k, d_k | battery charges / discharges at rated power P in slot k | 2H = 8 |
| p_l, n_l | flow on free incident tie-line l: f_l = F (p_l − n_l) ∈ {−F, 0, +F} | 2 per line |
| s | start the pending flexible job now | 0 or 1 |

Degree-3 buildings (lab_block, canteen: ring + cross-link) with a flexible job → 8 + 6 + 1 = **15
qubits**; degree-2 buildings → 13. Islanded / fixed lines are removed from the bit set and enter as a
constant outflow. A job at its latest feasible start is forced (no bit, constant load).

## 2. Affine building blocks

With x the bit vector, everything below is affine in x:

- Net power (kW) in slot k:
  r_k = r0_k + f_fixed + P(c_k − d_k) + Σ_l σ_l F(p_l − n_l) + s · kw_job · [k < duration],
  where r0_k = inflexible load + already-running flexible load − PV and σ_l = ±1 is the line orientation.
- Battery energy after slot k:
  e_k = e_now + Σ_{j≤k} (η_ch P Δt · c_j − P Δt / η_dis · d_j).

## 3. Objective

**Grid cost.** The true settlement cost of slot k is piecewise linear,
π_k·max(r_k, 0) − π^exp_k·max(−r_k, 0), which is not quadratic. We replace it by a convex quadratic
surrogate γ_k + α_k r_k + β_k r_k² (β_k ≥ 0), least-squares fitted to the exact cost over **every residual
value reachable** by the bits (all subset sums of the bit coefficients). When import and export prices
are equal (scenario B) the fit is exact (β = 0); this is unit-tested. π_k includes the optional carbon
shadow price λ·EF (λ = 0 in the reported runs; CO2 is still reported).

**Battery cost-to-go.** `qgrid/costtogo.py` runs a local dynamic program over the rest of the day
(81 energy levels × 25 power levels, the building's own forecast only, no sharing) giving V_t(e).
The terminal value V_T(e) = −v·(e − e0), v = the day's mean import price, matches the terminal
adjustment used by `model.settle()` for every method. In the QUBO we add a convex quadratic fit
a₂e_H² + a₁e_H + a₀ of V_{t+H} over the energy range reachable within the horizon.

**Flexible load.** s·tail + (1 − s)·defer, where *tail* = forecast cost of the job's slots beyond the
horizon if started now, *defer* = the cheapest forecast cost of starting later within the window
(marginal price = import price if forecast net load > 0, else export price).

**ADMM consensus.** Σ_l ρ/2 · (f_l − v_l)², v_l = z_l − u_l (Section 5). Quadratic, so it fits the QUBO.

Squares of affine terms are expanded with x_i² = x_i:
w(c + aᵀx)² = wc² + Σ_i w(2c a_i + a_i²) x_i + Σ_{i≠j} w a_i a_j x_i x_j.
The QUBO is stored as E(x) = const + xᵀMx with M symmetric (diagonal = linear terms).

## 4. Constraints and penalties

Hard constraints (checked **exactly** for every bitstring by `feasible_mask`):

1. c_k·d_k = 0 (no simultaneous charge and discharge),
2. p_l·n_l = 0 (unique flow code),
3. e_min ≤ e_k ≤ e_max for every k in the horizon (SoC 20–95 %).

Penalties: P_excl = Σ_k c_k d_k + Σ_l p_l n_l, and a soft SoC term
P_soc = Σ_{k tight} ((e_k − e_now)/(PΔt))², added only for slots where the bound can actually be hit.

**Penalty auto-tuning** (`auto_tune`): A_x = Σ|M_obj| (an upper bound on the objective's range, so
violating an exclusivity constraint can never pay off). A_s starts at 0 and is set to 5 % of that bound,
then doubled, until the ground state of the full QUBO (found exhaustively) is feasible. Doing nothing
(all zeros) is always feasible, so this always ends.

## 5. Consensus ADMM coupling

Tie-line l between buildings i and j has one orientation. Each endpoint proposes f_l^i, f_l^j from its own
QUBO; the neighbours exchange only these proposals (never load, PV or battery data):

z_l = (f_l^i + f_l^j)/2, u_l^i ← u_l^i + f_l^i − z_l, with ρ increased geometrically per iteration
(standard for non-convex / discrete ADMM) to force agreement. A line is agreed when both endpoints
propose the same level. After the iteration cap, disagreeing lines are set to 0 (always feasible).
Each building then re-solves once with its agreed flows fixed.

## 6. From bits to commands

The applied slot uses the QUBO's **mode** (charge / discharge / idle), flex start and agreed flows. The
battery power within the chosen mode is refined continuously (1-D search over [0, P_max] minimising
exact slot cost + V_{t+1}) and then clamped by the safety layer (`qgrid/safety.py`). So the QUBO decides
the combinatorial part (modes, timing, sharing) and a tiny classical step sets the magnitude.

## 7. Ising form for QAOA

x_i = (1 − z_i)/2 gives E = c + Σ h_i z_i + Σ_{i<j} J_ij z_i z_j with
h_i = −M_ii/2 − Σ_{j≠i} M_ij/2, J_ij = M_ij/2, c = const + tr(M)/2 + Σ_{i≠j} M_ij/4
(qubit i ↔ bit i, Qiskit little-endian). Before QAOA the Hamiltonian is divided by its standard
deviation under the uniform distribution, √(Σh_i² + ΣJ_ij²), computed from the coefficients alone
(no enumeration), so that one pre-trained set of (γ, β) transfers across instances.

## 8. Verification

Every local solve also runs exhaustive search (2^15 = 32 768 states, vectorised) over the feasible set.
The QAOA result is checked for feasibility and compared to that exact optimum (approximation ratio,
P(optimum)); tiered fallback QAOA → simulated annealing → exact (`qgrid/solvers`).

> QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed.
