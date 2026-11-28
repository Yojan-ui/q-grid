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
- Today each building acts on its own: when BESCOM supply fails, critical loads go dark for 2.6 h per outage while the diesel sets burn 373 L; the electricity bill averages Rs 177,694 a day.
- Mean of 30 modelled RVCE days; 3 have a (synthetic, seeded) BESCOM outage.
- Per outage today: critical loads dark 2.6 h; diesel 373 L (1,000 kg CO₂).
- Bill today: Rs 177,694 a day (energy + share of the monthly demand charge, KERC HT-2(c)(ii)).
- Screenshot: `deck/01_problem.png` (Step 1).

### 3 · The idea
- One small node per building plans its own next 24 hours, every 15 minutes, exactly (branch and bound).
- Neighbours agree cable flows by trading proposals (consensus ADMM). No central computer, no single point of failure.
- A safety layer clamps every command (battery limits, diesel minimum run time, tanks, critical loads).
- Screenshot: `deck/03_decisions.png` (Step 3).

### 4 · How quantum fits (and where it doesn't)
- The on/off choices branch and bound leaves open become a QUBO (10 qubits in the worked example); QAOA
  runs on a simulator and every answer is checked against exact search.
- Placement test: 1,080 building problems; exact search finished at its first node 99.9 %
  of the time, so the quantum start saved no work. **Not in the control loop.** When QAOA is switched on, any miss falls
  back to annealing, then exact.
- Screenshot: `deck/04_verify.png` (Step 4f).

### 5 · Decentralised coordination
- Live: take a building offline. Its 3 cables go dark; the others re-agree in
  46 rounds; every critical load in the other buildings is still served.
- 3-hour network failure: central control loses 2.68 points of gap, Q-Grid 0.01.
- Screenshot: `deck/05_agree.png` (Step 5).

### 6 · Demo (switch to the app)
- Three live moments: **solve a slot** (Step 4f), **remove a building** (Step 5), **type a rule** (Step 6b:
  "no DG" is checked, then priced; an impossible rule is refused with a reason).
- Runs offline from replay files; with the backend it computes live.
- Screenshot: `deck/06_rules.png` (Step 6b). Backup video: `docs/media/demo_backup.webm`.

### 7 · Results
- **In a BESCOM outage Q-Grid cuts critical-load downtime from 2.6 h to 20 min per outage (45 L more diesel, 122 kg CO₂, to keep those loads up); on normal days the bill is 0.1% lower and the demand charge falls by Rs 5,278 a month at 1,300 kVA contract demand; with no central controller it averages 1.1% from the best possible plan against 9.2% for Per-building MPC, a lead made on the outage days (normal days: 0.6% against 0.3%).**
- Same days, data, forecasts and constraints for every method; five campuses (RVCE + four public meter datasets).

| On RVCE (30 days) | Today | Q-Grid | Best possible plan |
|---|---:|---:|---:|
| Critical loads dark, per outage | 2.58 h | 0.33 h | 0.00 h |
| Diesel, per outage day | 373 L | 418 L | 389 L |
| Gap to best plan, all days | 16.8 % | 1.1 % | 0 % |
| Gap to best plan, normal days | 2.4 % | 0.6 % | 0 % |

- Closest method without a central controller on 3 of 5 campuses; on RVCE the lead
  over per-building MPC is made on the outage days (normal days: 0.6 % vs 0.3 %).
- Screenshot: `deck/07_bottom_line.png` (Step 7e); backup `deck/07_scorecard.png` (Step 7a).

### 8 · Cost and impact
- Everyday bill: 0.1 % lower on normal days, 0.4 % higher over all days.
- Monthly demand charge at 1,300 kVA contract demand (assumed): falls by Rs 5,278
  (1,000 kVA: Rs -21,882; 1,600 kVA: Rs 0; negative = Q-Grid pays less).
- About Rs 7.9 lakh of node hardware for 9 buildings. On the electricity bill alone it does not pay back on our assumed costs. The case today is reliability: fewer dark hours for critical loads when BESCOM fails.
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
