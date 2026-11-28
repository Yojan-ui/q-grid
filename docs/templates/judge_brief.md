# Judge brief — how to explain Q-Grid in plain words

_Rendered from `docs/templates/judge_brief.md` by `scripts/write_results_md.py`; every result number comes from `results/`
(locked headline: `results/headline.json`, [headline.md](headline.md)). For the spoken scripts see
[pitch_3min.md](pitch_3min.md) and [pitch_1min.md](pitch_1min.md); for the hard questions, [qa_prep.md](qa_prep.md)._

## The 30-second version

"RVCE has rooftop solar, two diesel generators and a BESCOM grid connection. Today each building runs on its own, and when
BESCOM fails, only diesel keeps the labs and server room up. Q-Grid gives every building its own small controller: it plans
its own next 24 hours and agrees with its neighbours how much power to share over cables. There's no central computer, so
there's no single point of failure. We also tested whether a quantum algorithm helps with the planning: it gave correct
answers but wasn't faster, so we say so and don't use it in the loop."

## The problem

- Every 15 minutes a campus has small energy decisions: run the diesel set or not, charge or discharge a battery, when the
  water pump or the laundry runs, whether to send spare power to a neighbouring building.
- Today nobody coordinates them. {{headline.step1}}
- Hidden cost: BESCOM's monthly **demand charge** is set by the campus's highest peak (at least 85 % of contract demand), so
  one bad 15-minute spike raises the whole month's bill.

## What Q-Grid does

Think of each building as a neighbour with its own small brain (a node):

1. **Each building plans for itself, exactly.** Every 15 minutes it solves its own 24-hour plan with an exact optimiser
   (a MILP, branch and bound). Exact means the best answer for that building, not a guess.
2. **Neighbours negotiate.** Cable flows between buildings are agreed by repeated offer and counter-offer until both sides
   match (consensus ADMM, which is guaranteed to converge for this convex part). Nobody in the middle gives orders.
3. **A safety layer checks every command** before it reaches equipment: battery limits, diesel minimum run time, water
   tanks, critical loads.
4. **If the network fails,** each building keeps optimising on its own and rejoins when the links return.

## Where quantum fits (be very clear on this)

- After branch and bound, some yes/no choices may be left open. We turn them into a **QUBO** (the format quantum
  optimisers take) and run **QAOA** on a simulator ({{live.qaoa.n_qubits}} qubits in the worked example).
- Every QAOA answer is checked against exact search, and it matched.
- **It saved no work:** across {{q3.qp.instances}} building problems the exact solver finished at its first node
  {{q3.qp.cold_root_node_pct|1}} % of the time, so a quantum head start didn't help. QAOA is **not in the control loop**.
- The line to say: "QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed."

## How we proved it (the benchmark)

- **Five campuses**: RVCE plus four public meter datasets (three Building Data Genome 2 campuses, one CU-BEMS building),
  {{hl.n_days|0}} days each.
- **Ten ways of running the campus**, all on the same data, days, forecasts and constraints: today's status quo, a
  rule-based controller, GA, PSO, per-building MPC, central MPC (with and without a network failure), Q-Grid (with and
  without a network failure), and the best possible plan (a central optimiser that knows the future: the yardstick, not a
  competitor).
- Measured: gap to the best possible plan, critical-load downtime, diesel litres, the electricity bill.

## The data ("is it real?")

- **Real:** solar (NASA POWER, Bengaluru); campus layout (OpenStreetMap); tariff (BESCOM HT-2(c)(ii), checked page by page
  in the KERC Tariff Orders 2022 and 2023: Rs 8.50/kWh and Rs 350/kVA a month from April 2023); CO₂ factor (CEA,
  0.727 t/MWh).
- **From RVCE's own documents:** 500 kWp of solar on 21 roofs, floor areas, two 490 kVA diesel sets.
- **Modelled or assumed, and labelled in the app:** building loads (floor area × typical energy use on real university load
  shapes, until RVCE meter data arrives); outages (simulated, seeded); contract demand ({{hl.contract_kva|0}} kVA assumed);
  batteries, EV chargers and cables (**proposed**, not on campus today).

## What the results say

**{{headline.sentence}}**

| RVCE, mean of {{hl.n_days|0}} days ({{hl.n_outage_days|0}} with an outage) | Today | Q-Grid | Best possible plan |
|---|---:|---:|---:|
| Critical loads dark, per outage | {{hl.sq_downtime_h|2}} h | {{hl.q_downtime_h|2}} h | {{hl.opt_downtime_h|2}} h |
| Diesel, per outage day | {{hl.sq_diesel_l|0}} L | {{hl.q_diesel_l|0}} L | {{hl.opt_diesel_l|0}} L |
| Gap to the best possible plan, all days | {{q3.b.rvce.status_quo.gap_pct|1}} % | {{q3.b.rvce.qgrid.gap_pct|1}} % | 0 % |
| Gap to the best possible plan, normal days | {{hl.ngap.status_quo|1}} % | {{hl.ngap.qgrid|1}} % | 0 % |

- Everyday bill: {{hl.normal_abs_pct|1}} % {{hl.normal_dir}} than today on normal days ({{hl.all_abs_pct|1}} % {{hl.all_dir}}
  over all days). Say it as measured.
- Network failure for 3 hours: central control loses {{q3.n.central_comms_penalty|2}} points of gap, Q-Grid
  {{q3.n.qgrid_comms_penalty|2}}.
- Lead with outages and diesel, then the gap to the best plan; report the bill exactly as it is.

## The demo (7 steps in the app)

1. The problem: today's downtime, diesel, bill. 2. The campus in 3D. 3. The decisions each building controls.
4. The quantum test: click **Measure the block** (QAOA vs exact, live). 5. Buildings agree: click **Take mechanical labs
offline** (its cables go dark, the others re-agree). 6. Storage and faculty rules: type a rule in plain English; it's checked
and priced, and an impossible rule is refused with a reason. 7. Results: scorecard, other campuses, network failure, cost,
bottom line. It runs fully offline. Click order and fallbacks: [demo_runbook.md](demo_runbook.md).

## Questions you'll almost certainly get

- **Why not one central optimiser?** We do use exact optimisation, inside each building. A central controller depends on
  one server and one network; when the network fails it falls back to simple rules while Q-Grid buildings keep optimising.
- **RVCE has one owner, so why decentralise?** One owner still means one server and one network to keep alive. Nodes can
  be installed one building at a time, and each department keeps its own rules.
- **Where's the quantum advantage?** There isn't one, and we tested for it properly. That is the finding.
- **Is the data real?** Real solar, map, tariff and CO₂; RVCE's own solar, diesel and floor-area figures; modelled loads
  and simulated outages, labelled as such.
- **What would you need to deploy?** One BESCOM bill, diesel logs, 30 days of meter data and one small node per building.
  Start in shadow mode: the node recommends, staff decide.

## Honest limits (say them before you're asked)

No quantum advantage. Outages are simulated. RVCE loads are modelled until meter data arrives. Batteries and cables are
proposals, and the outage gain depends on which buildings the two diesel sets can feed. There is no real bill saving: on
normal days the bill is {{hl.normal_abs_pct|1}} % {{hl.normal_dir}}, over all days {{hl.all_abs_pct|1}} % {{hl.all_dir}} (outage diesel). Contract demand is
assumed until RVCE's bill arrives.
