# Pitch — 1 minute (elevator version)

_Rendered from `docs/templates/pitch_1min.md`; numbers from `results/`, headline locked in `results/headline.json`.
About 150 words; timing marks are targets._

**(0:00–0:15)** "Every building at RVCE runs its energy on its own. Today each building acts on its own: when BESCOM supply fails, critical loads go dark for 2.6 h per outage while the diesel sets burn 373 L; the electricity bill averages Rs 177,694 a day."

**(0:15–0:30)** "Q-Grid gives each building its own small controller. It plans its own next 24 hours exactly, and agrees cable
flows with its neighbours. No central computer, so no single point of failure."

**(0:30–0:45)** "On 30 modelled RVCE days: In a BESCOM outage Q-Grid cuts critical-load downtime from 2.6 h to 55 min per outage (41 L more diesel, 110 kg CO₂, to keep those loads up); on normal days the bill is 0.4% higher and the demand charge rises by Rs 16,685 a month at 1,300 kVA contract demand; with no central controller it averages 8.4% from the best possible plan against 9.2% for Per-building MPC, a lead made on the outage days (normal days: 7.4% against 0.3%)."

**(0:45–1:00)** "We tested quantum honestly: QAOA on a simulator, checked against exact search. It was correct, but no faster at
this size, so it isn't in the control loop. No quantum advantage claimed. About Rs 7.9 lakh of node hardware for 9 buildings. On the electricity bill alone it does not pay back on our assumed costs. The case today is reliability: fewer dark hours for critical loads when BESCOM fails. Next: one RVCE BESCOM bill and the
diesel logs, to replace our assumptions with campus data."
