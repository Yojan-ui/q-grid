# Pitch (3 minutes, follows the six story chapters) — numbers from results/*.csv

**1 · Problem (30 s).** "This is RVCE from OpenStreetMap — nine zones, rooftop PV from NASA data. Watch a fest evening: at
18:00 BESCOM goes down. Today the campus runs diesel zone by zone and the server room loses power: {{headline.before.critical_downtime_h|2}}
hours of critical-load downtime."

**2 · Decisions (20 s).** "Every 15 minutes each building decides: battery, diesel, pump, flexible loads, how much to share with
neighbours. Those on/off choices are qubits — at most {{search.max_qubits}} per building."

**3 · QUBO (25 s).** "We turn cost, fuel and every constraint into one energy landscape. Valleys are cheap schedules, ridges are
broken rules. The white cell is the true optimum — we compute it exactly every time."

**4 · Quantum solve (35 s).** "QAOA, simulated on a laptop, pours probability into the valley layer by layer. We check its answer
against the exact optimum: {{tiers.qaoa_pct|1}} % of the time it is verified optimal; otherwise we fall back automatically. No
quantum advantage claimed — the point is a verified, hardware-sized formulation."

**5 · Decentralised (35 s).** "No central computer. Buildings negotiate power on the tie-lines with their neighbours only. Kill the
mechanical labs: neighbours notice in 3 seconds and the rest re-plan; recovery {{robust.recovery_s|1}} s, schedule still feasible."

**6 · Result (35 s).** "Same outage with Q-Grid: diesel and battery power routed to the server room — critical downtime
{{headline.after.critical_downtime_h|2}} h instead of {{headline.before.critical_downtime_h|2}} h. Across 30 days we're within
{{OURS.eval30_mean.A.gap_to_B4_pct|1}} % of the centralised optimum while staying decentralised and private. Prices are stand-ins
until we get the KERC/BESCOM documents — every number on screen is clickable to its source."

## 1-minute version
"RVCE, nine zones, real solar data. In a BESCOM outage during the fest, the status quo loses critical power for
{{headline.before.critical_downtime_h|2}} h. Q-Grid turns each building's decisions into a ≤{{search.max_qubits}}-qubit QUBO, solves it
with QAOA verified against the exact optimum, and lets buildings negotiate power with neighbours — no central server. Result:
{{headline.after.critical_downtime_h|2}} h downtime, {{OURS.eval30_mean.A.gap_to_B4_pct|1}} % from the global optimum, survives a
building going offline. Honest labels: simulated QAOA, no quantum advantage, prices pending official tariffs."
