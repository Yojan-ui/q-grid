# Pitch (3 minutes, follows the six story chapters) — numbers from results/*.csv

> **Superseded.** This is the earlier v1 pitch (one headline day, v1 pipeline). Use [pitch_3min.md](pitch_3min.md) and the
> locked headline in [headline.md](headline.md): In a BESCOM outage Q-Grid cuts critical-load downtime from 2.6 h to 20 min per outage (45 L more diesel, 122 kg CO₂, to keep those loads up); on normal days the bill is 0.1% lower and the demand charge falls by Rs 5,278 a month at 1,300 kVA contract demand; with no central controller it averages 1.1% from the best possible plan against 9.2% for Per-building MPC, a lead made on the outage days (normal days: 0.6% against 0.3%).

**1 · Problem (30 s).** "This is RVCE from OpenStreetMap — nine zones, rooftop PV from NASA data. Watch a fest evening: at
18:00 BESCOM goes down. Today the campus runs diesel zone by zone and the server room loses power: 3.00
hours of critical-load downtime."

**2 · Decisions (20 s).** "Every 15 minutes each building decides: battery, diesel, pump, flexible loads, how much to share with
neighbours. Those on/off choices are qubits — at most 14 per building."

**3 · QUBO (25 s).** "We turn cost, fuel and every constraint into one energy landscape. Valleys are cheap schedules, ridges are
broken rules. The white cell is the true optimum — we compute it exactly every time."

**4 · Quantum solve (35 s).** "QAOA, simulated on a laptop, pours probability into the valley layer by layer. We check its answer
against the exact optimum: 65.7 % of the time it is verified optimal; otherwise we fall back automatically. No
quantum advantage claimed — the point is a verified, hardware-sized formulation."

**5 · Decentralised (35 s).** "No central computer. Buildings negotiate power on the tie-lines with their neighbours only. Kill the
mechanical labs: neighbours notice in 3 seconds and the rest re-plan; recovery 3.2 s, schedule still feasible."

**6 · Result (35 s).** "Same outage with Q-Grid: diesel and battery power routed to the server room — critical downtime
0.00 h instead of 3.00 h. Across 30 days we're within
5.5 % of the centralised optimum while staying decentralised and private. Prices are stand-ins
until we get the KERC/BESCOM documents — every number on screen is clickable to its source."

## 1-minute version
"RVCE, nine zones, real solar data. In a BESCOM outage during the fest, the status quo loses critical power for
3.00 h. Q-Grid turns each building's decisions into a ≤14-qubit QUBO, solves it
with a QAOA block tested on a simulator against the exact optimum (not in the control loop), and lets buildings negotiate power with neighbours — no central server. Result:
0.00 h downtime, 5.5 % from the global optimum, survives a
building going offline. Honest labels: simulated QAOA, no quantum advantage, prices pending official tariffs."
