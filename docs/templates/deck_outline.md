# Deck outline — 10 slides (EUREKA Round 1: 7 min talk + 3 min Q&A)

_Rendered from `docs/templates/deck_outline.md`; every number from `results/` (locked headline: `results/headline.json`).
Screenshots: `docs/media/deck/` (1920×1080, presenter mode, light theme; regenerate with
`node frontend/scripts/capture.mjs --out docs/media/deck --sizes 1920x1080 --present --only 1,2,3,4f,5,6b,7a,7c,7d,7e`).
One idea per slide; the demo carries the detail._

**Footer on every slide:** "QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed."

---

### 1 · Title
- **Q-Grid: every building its own energy controller**
- Decentralised scheduling for a campus solar + diesel microgrid (batteries and cables proposed). RVCE case study.
- EUREKA 2026 · Track 3: Smart Decentralised Energy Systems · team, faculty guide.
- Screenshot: `deck/02_campus.png` (Step 2, the 3D campus).

### 2 · The problem
- {{headline.step1}}
- Mean of {{hl.n_days|0}} modelled RVCE days; {{hl.n_outage_days|0}} have a (synthetic, seeded) BESCOM outage.
- Per outage today: critical loads dark {{hl.sq_downtime_h|1}} h; diesel {{hl.sq_diesel_l|0}} L ({{hl.sq_diesel_co2_kg|0}} kg CO₂).
- Bill today: Rs {{hl.sq_bill_rs|0}} a day (energy + share of the monthly demand charge, KERC HT-2(c)(ii)).
- Screenshot: `deck/01_problem.png` (Step 1).

### 3 · The idea
- One small node per building plans its own next 24 hours, every 15 minutes, exactly (branch and bound).
- Neighbours agree cable flows by trading proposals (consensus ADMM). No central computer, no single point of failure.
- A safety layer clamps every command (battery limits, diesel minimum run time, tanks, critical loads).
- Screenshot: `deck/03_decisions.png` (Step 3).

### 4 · How quantum fits (and where it doesn't)
- The on/off choices branch and bound leaves open become a QUBO ({{live.qaoa.n_qubits}} qubits in the worked example); QAOA
  runs on a simulator and every answer is checked against exact search.
- Placement test: {{q3.qp.instances}} building problems; exact search finished at its first node {{q3.qp.cold_root_node_pct|1}} %
  of the time, so the quantum start saved no work. **Not in the control loop.** When QAOA is switched on, any miss falls
  back to annealing, then exact.
- Screenshot: `deck/04_verify.png` (Step 4f).

### 5 · Decentralised coordination
- Live: take a building offline. Its {{live.remove.lines|0}} cables go dark; the others re-agree in
  {{live.remove.rounds_after|0}} rounds; {{live.remove.crit_text}}.
- 3-hour network failure: central control loses {{q3.n.central_comms_penalty|2}} points of gap, Q-Grid {{q3.n.qgrid_comms_penalty|2}}.
- Screenshot: `deck/05_agree.png` (Step 5).

### 6 · Demo (switch to the app)
- Three live moments: **solve a slot** (Step 4f), **remove a building** (Step 5), **type a rule** (Step 6b:
  "{{live.rule0.text}}" is checked, then priced; an impossible rule is refused with a reason).
- Runs offline from replay files; with the backend it computes live.
- Screenshot: `deck/06_rules.png` (Step 6b). Backup video: `docs/media/demo_backup.webm`.

### 7 · Results
- **{{headline.sentence}}**
- Same days, data, forecasts and constraints for every method; five campuses (RVCE + four public meter datasets).

| On RVCE ({{hl.n_days|0}} days) | Today | Q-Grid | Best possible plan |
|---|---:|---:|---:|
| Critical loads dark, per outage | {{hl.sq_downtime_h|2}} h | {{hl.q_downtime_h|2}} h | {{hl.opt_downtime_h|2}} h |
| Diesel, per outage day | {{hl.sq_diesel_l|0}} L | {{hl.q_diesel_l|0}} L | {{hl.opt_diesel_l|0}} L |
| Gap to best plan, all days | {{q3.b.rvce.status_quo.gap_pct|1}} % | {{q3.b.rvce.qgrid.gap_pct|1}} % | 0 % |
| Gap to best plan, normal days | {{hl.ngap.status_quo|1}} % | {{hl.ngap.qgrid|1}} % | 0 % |

- Closest method without a central controller on {{q3.best_on_n|0}} of {{q3.n_campuses|0}} campuses; on RVCE the lead
  over per-building MPC is made on the outage days (normal days: {{hl.ngap.qgrid|1}} % vs {{hl.ngap.per_building_mpc|1}} %).
- Screenshot: `deck/07_bottom_line.png` (Step 7e); backup `deck/07_scorecard.png` (Step 7a).

### 8 · Cost and impact
- Everyday bill: {{hl.normal_abs_pct|1}} % {{hl.normal_dir}} on normal days, {{hl.all_abs_pct|1}} % {{hl.all_dir}} over all days.
- Monthly demand charge at {{hl.contract_kva|0}} kVA contract demand (assumed): {{hl.dc.base.verb}} by Rs {{hl.dc.base.abs_change_rs|0}}
  (1,000 kVA: Rs {{hl.dc.1000.change_rs|0}}; 1,600 kVA: Rs {{hl.dc.1600.change_rs|0}}; negative = Q-Grid pays less).
- {{imp.spoken}}
- Screenshot: `deck/08_worth_it.png` (Step 7d).

### 9 · Real-life rollout at RVCE
- Phase 0, shadow mode: the node recommends, staff decide, we compare (no control).
- Phase 1: one building with a diesel set; Phase 2: all nine nodes; batteries and cables only if the numbers justify them.
- Needed from RVCE: one BESCOM HT bill (contract demand, maximum demand), which buildings the two 490 kVA diesel sets back,
  diesel running hours and fuel logs, 30 days of meter data, permission to name RVCE
  (`docs/rvce_data_request_email.md`).
- Screenshot: `deck/09_comms.png` (Step 7c, network failure), or the app's Deploy tab.

### 10 · Team and honest limits
- Team lead Yashas; members ⟨add⟩; faculty guide ⟨add⟩.
- Limits: no quantum advantage; outages synthetic; RVCE loads modelled until meter data; batteries, EV chargers and cables
  proposed; contract demand assumed until the bill arrives.
- Repo and live demo link (README "Open the demo").
