# Pitch — 3 minutes (spoken script, follows the explainer steps)

_Rendered by `scripts/write_results_md.py` from `docs/templates/pitch_3min.md`; every number comes from `results/`. Re-render
after any re-run; never edit numbers by hand. Timings are targets; total ≈ 3:00. Press **P** for presenter mode before you start._

> Say once, early: "QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed. Tariffs are
> labelled stand-ins until the official BESCOM/KERC order arrives."

**Step 1 · The problem (0:00–0:25).**
"{{q3.story.step1}}
That's thirty modelled days at RVCE. Every building decides on its own — sells noon solar cheaply, buys back at the evening
peak, starts diesel when BESCOM fails."

**Step 2 · The campus (0:25–0:40).**
"This is RVCE from OpenStreetMap: nine buildings, rooftop solar, batteries, two diesel sets, a pump house — joined by ten
cables. Every fifteen minutes, each of them needs a decision."

**Step 3 · The decisions (0:40–0:55).**
"Diesel on or off, battery may charge, pump hours, when the laundry runs — for the next 24 hours. For the whole campus that's
too many combinations for any one computer to check, so each building solves only its own."

**Step 4 · The quantum test (0:55–1:30).**
"We asked an honest question: does a quantum circuit help with these on/off choices? Branch and bound leaves a few undecided
— here {{live.qaoa.n_qubits}} — we turn them into a QUBO and run QAOA on a simulator. *[Click **Measure the block** — live moment 1.]*
It matches exact search. But across {{q3.qp.instances}} building problems, the exact solver already finished at its first node
{{q3.qp.cold_root_node_pct|1}} % of the time, so the quantum start saved no work. Verdict: Q-Grid doesn't use it. We tested it,
verified it, and we tell you it didn't help."

**Step 5 · Buildings agree (1:30–2:00).**
"Between buildings there is no central computer. Neighbours trade proposals for each cable's flow until they agree.
*[Click **Take mechanical labs offline** — live moment 2.]* Its {{live.remove.lines}} cables go dark; the others re-agree in
{{live.remove.rounds_after}} rounds and every critical load is still served."

**Step 6 · Storage and rules (2:00–2:20).**
"Batteries fill before the evening outage and carry the campus through it. And faculty can add rules in plain English.
*[Type or click **{{live.rule0.text}}** — live moment 3.]* It's checked, then priced: diesel goes from
{{live.rule0.before.dg_hours|1}} hours to {{live.rule0.after.dg_hours|1}}, and you see exactly what that costs in shed load.
An impossible rule is refused with a reason."

**Step 7 · Results (2:20–3:00).**
"Same days, same data, same forecasts for every method. {{q3.story.step7}}
{{q3.story.comms}}
Is it worth it? About Rs {{imp.hardware_rs_lakh|1}} lakh of hardware for nine buildings; with battery wear counted it pays back
in about {{imp.payback_net_years|1}} years on assumed costs, and the Monte Carlo range is on screen. Every number opens to its source file."

**Close (one line).** "Decentralised, verified, honest about quantum — ready for RVCE's real meter data."
