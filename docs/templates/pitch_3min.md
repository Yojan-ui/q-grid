# Pitch — 3 minutes (spoken script, follows the explainer steps)

_Rendered by `scripts/write_results_md.py` from `docs/templates/pitch_3min.md`. Every number comes from `results/`; the
headline sentence is the locked one in `results/headline.json` ([docs/headline.md](headline.md)). Re-render after any re-run;
never edit numbers by hand. Timings are targets at about 150 words a minute; total 3:00. Press **P** for presenter mode first._

**Step 1 · The problem (0:00–0:30)** · screen: Step 1, the problem cards
"{{headline.step1}}
That's the average of {{hl.n_days|0}} modelled RVCE days, {{hl.n_outage_days|0}} of them with a BESCOM outage. Each building
decides on its own, and when the grid fails, only diesel stands between the labs and a blackout.
Everything you'll see is modelled on RVCE with real solar, map and tariff data. The outages are simulated, the batteries and
cables are proposals, and the quantum part runs on a simulator: verified against exact solutions, no quantum advantage claimed."

**Step 2 · The campus (0:30–0:45)** · Step 2, the 3D campus
"This is RVCE from OpenStreetMap: nine building groups, about 500 kWp of rooftop solar on 21 roofs, two 490 kVA diesel sets,
and, proposed, batteries and cables between buildings. Every fifteen minutes, each of them needs a decision."

**Step 3 · The decisions (0:45–1:00)** · Step 3
"Diesel on or off, battery charge or discharge, pump hours, when the laundry runs, for the next 24 hours. For the whole campus
that's too many combinations for one computer to check, so each building solves only its own."

**Step 4 · The quantum test (1:00–1:35)** · Step 4, then 4f
"We asked an honest question: does a quantum circuit help with these on/off choices? Branch and bound leaves a few undecided,
here {{live.qaoa.n_qubits}}. We turn them into a QUBO and run QAOA on a simulator. *[Click **Measure the block**: live moment 1.]*
It matches exact search. But across {{q3.qp.instances}} building problems the exact solver already finished at its first node
{{q3.qp.cold_root_node_pct|1}} % of the time, so the quantum start saved no work. Q-Grid doesn't use it in the loop. We tested
it, verified it, and we're telling you it didn't help."

**Step 5 · Buildings agree (1:35–2:05)** · Step 5
"Between buildings there is no central computer. Neighbours trade proposals for each cable's flow until they agree.
*[Click **Take mechanical labs offline**: live moment 2.]* Its {{live.remove.lines}} cables go dark; the others re-agree in
{{live.remove.rounds_after}} rounds, and {{live.remove.crit_text}}."

**Step 6 · Storage and rules (2:05–2:25)** · Step 6, then 6b
"The proposed batteries fill before the evening outage and carry critical loads through it. Faculty can add rules in plain
English. *[Click the chip **{{live.rule0.text}}**: live moment 3.]* It's checked, then priced: diesel goes from
{{live.rule0.before.dg_hours|1}} to {{live.rule0.after.dg_hours|1}} hours, and you see what that costs. An impossible rule is
refused with a reason."

**Step 7 · Results (2:25–3:00)** · 7a scorecard, then 7e
"Same days, same data, same forecasts for every method. {{headline.sentence}}
{{q3.story.comms}}
{{imp.spoken}} Every number on screen opens to the file it came from."

**Close (one line).** "Decentralised, verified against exact solutions, honest about quantum, and ready for RVCE's own bill
and meter data."
