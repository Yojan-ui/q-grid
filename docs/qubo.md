# Local QUBO — derivation

Implementation: `backend/qgrid/qubo.py`. Tests: `backend/tests/test_model_qubo.py`.

Each building *i* solves, every 15-min slot *t* and every ADMM iteration, a small binary problem over
a 1-hour horizon (H = 4 slots, truncated at the end of the day). Only the first slot is applied
(receding horizon); the rest of the day is represented by a cost-to-go term.

## 1. Variables (≤ 15 qubits)

| bits | meaning | count |
|---|---|---|
| c_k, d_k | battery charges / discharges one quantum in slot k | 2H = 8 |
| p_l, n_l | flow on free incident tie-line l: f_l = F (p_l − n_l) ∈ {−F, 0, +F} | 2 per line |
| s | start the pending flexible job now | 0 or 1 |

Degree-3 buildings (lab_block, canteen: ring + cross-link) with a flexible job → 8 + 6 + 1 = **15
qubits**; degree-2 buildings → 13. Islanded / fixed lines are removed from the bit set and enter as a
constant outflow. A job at its latest feasible start is forced (no bit, constant load).

**Battery quanta (net-load matched).** A charge bit stands for absorbing the forecast surplus plus one
tie-line step, P_c,k = min(P, surplus_k + F); a discharge bit for covering the forecast deficit plus one
step, P_d,k = min(P, deficit_k + F); rated power P when there is no surplus/deficit (< 10 % of P). With
plain rated-power quanta, absorbing a 20 kW surplus looked like "charge 125 kW and import the rest", so
the QUBO chose idle and exported surplus cheaply (diagnosed: Rs 1.2k/day worse than the local DP).

## 2. Affine building blocks

With x the bit vector, everything below is affine in x:

- Net power (kW) in slot k:
  r_k = r0_k + f_fixed + P_c,k c_k − P_d,k d_k + Σ_l σ_l F(p_l − n_l) + s · kw_job · [k < duration],
  where r0_k = inflexible load + already-running flexible load − PV and σ_l = ±1 is the line orientation.
- Battery energy after slot k:
  e_k = e_now + Σ_{j≤k} (η_ch P_c,j Δt · c_j − P_d,j Δt / η_dis · d_j).

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

**Flexible load.** s·tail + (1 − s)·defer, where *tail* = cost of the job's slots beyond the horizon if
started now and *defer* = the cheapest cost of starting later within the window, both at the building's
**battery-aware marginal price** m_t = clip(marginal value of stored energy from the DP, export price,
import price) along the DP-optimal trajectory. The start bit's own coefficient is calibrated so that, with
no other action, starting costs Σ m_t·kw·Δt over the horizon (its couplings to battery/flow bits through
r_k are kept); ties are broken towards starting (prevents procrastination to the latest slot).

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

z_l = (f_l^i + f_l^j)/2, u_l^i ← u_l^i + f_l^i − z_l, with ρ_k = ρ0·1.2^k (standard for non-convex /
discrete ADMM) to force agreement. A line is agreed when both endpoints propose the same level; a building
whose lines all agree keeps its proposal (sticky). After 15 iterations disagreeing lines are set to 0
(always feasible); buildings whose final flows differ from their proposal re-solve with flows fixed.

**Price-initialised duals.** Free energy always looks attractive to the receiver, so with u = 0 both ends
open with "receive", z averages to 0 and discrete ADMM locks at 0 (a fixed point: agreement and zero dual
residual). Before round 0 the two neighbours therefore exchange one number each, their marginal energy
price m_t (no load/PV/battery data), and start from π0 = (m_a + m_b)/2:
ρ·u_a = −π0·Δt·H (the sender earns π0 per kWh), ρ·u_b = +π0·Δt·H. This is the transactive-energy
price signal; the cheap side then sells and the expensive side buys. ρ0 = 0.25·mean price·Δt/F and the
growth rate were chosen on training days only (disjoint from test/eval days).

## 6. From bits to commands

What is committed from the QUBO for the applied slot: the **tie-line levels** (via ADMM agreement) and the
**flexible-load start**. The QUBO's battery bits are planning variables that value the hour (they decide
whether receiving/sending and starting a job pay off). The battery set-point of the applied slot is then
dispatched by a 1-D continuous search over its full feasible range minimising exact slot cost + V_{t+1}
(the same cost-to-go), and clamped by the safety layer (`qgrid/safety.py`). Stated plainly: the QUBO
decides the combinatorial coordination (sharing, timing); a tiny classical step sets battery power.

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

---

## RVCE campus model — additions

**Horizon** H = 3 slots (45 min). **Variables** per zone: 2H battery bits (if a battery), `g` diesel generator on for the
horizon (if a DG and not forced on by its minimum on-time), `w` borewell pump on for the horizon (if a tank and not forced by
level safety), one start bit per flexible job in its window (most urgent first), 2 bits per free tie-line; budget ≤ 16 qubits
(lowest-priority job bits are dropped first; their jobs are still forced at their latest start by the safety layer).

**Residual** r_k = r0_k + f_fixed + P_c,k c_k − P_d,k d_k + Σ σ_l F(p_l − n_l) + Σ_j kw_j s_j[k < dur_j] + P_pump w − q_k g,
with the DG quantum q_k = clip(deficit_k + F, P_min, P_rated).

**Groups** (each a separate QUBO so decisions can be explained term by term):
`grid` (surrogate of the exact slot cost: tariff when the grid is up; when islanded, value of lost load — 0 for spill,
VOLL_nc up to the non-critical demand, VOLL_c beyond), `battery_ctg`, `water_value` (−v_w · level_H, v_w = pumping energy
avoided later), `dg_fuel` (litres(q) × diesel price over the horizon), `flex_timing`, `admm`, `rule:<id>` (operator rules,
e.g. a large linear penalty on `g` for "no DG during exams unless outage"; a quadratic shortfall term on the tank level for
"keep tanks above X % by T").

**Hard constraints** add: tank level within [min, max] over the horizon (where a feasible pump decision exists) and — in
islanded slots where at least one bitstring achieves it — **critical-load service**: r_k ≤ non-critical demand_k. In those
slots the surrogate is fitted only over the residuals that satisfy it (the 0 → 40 → 1000 Rs/kWh kink is too sharp for one
quadratic; diagnosed when zones exported power they needed for their own critical loads).

**Safety additions** (`qgrid/safety.py`, `admm.critical_guard`): DG minimum on-time and minimum load; pump forced on below the
minimum level, off before overflow; operator tank targets forced when the remaining time requires it; in islanded slots a zone
never exports on a tie-line if that would leave its own critical load unserved (the line drops to 0 at both ends).

**Explanations** (`qgrid/explain.py`): for each committed bit, ΔE_g = E_g(x with the bit flipped) − E_g(x) per group; the largest
terms become a sentence with the actual prices, kW, SoC, tank level and Rs.

**Solver tiers** QAOA (simulated circuit) → QIEA (quantum-inspired, classical CPU; Han & Kim 2002 rotation-gate update) →
simulated annealing → exact; each tier accepted only if verified optimal. QAOA parameters are warm-started per zone (6 COBYLA
steps from the zone's previous parameters); solved QUBOs are cached.

**ADMM with binaries** has no convergence guarantee. Reported per run: convergence rate (slots with full agreement), mean
iterations, oscillation cases (proposal vectors repeating with period 2). Disagreeing lines → bilateral resolution (each end
evaluates its exact local optimum with the line at −F, 0, +F; the level with the lowest summed *exact* cost wins) → else 0.
Optional over-relaxation/damping of z (`admm.relax`).
