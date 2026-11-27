# Segment 4 — Results (Sidhartha, 3:00–4:15)

_Rendered from `docs/templates/segment4_sidhartha.md`; every number from `results/` (locked headline:
`results/headline.json`). This version matches the **`real-data`** build (verified KERC tariff, RVCE's 500 kWp). If the
team presents the old portal, use Shoumik's PDF script instead: its numbers match that screen. About 190 words, 75 s._

**In:** Harshith ends with "Sidhartha has the numbers across all days."

---

### 7a — the scorecard (3:00–3:25)

*[Step button 7. Pause 3 s on the table.]*

"That was one day. Here are all {{hl.n_days|0}}: ten ways of running the campus on the same data, forecasts and BESCOM
tariff, against a central optimiser that knows the future. In a grid outage, Q-Grid cuts critical-load downtime from
{{hl.sq_downtime_h|1}} hours to {{hl.q_downtime_min|0}} minutes. Today's practice, and a controller that runs each
building separately, leave those loads dark the whole time. It costs diesel to do that: {{hl.diesel_abs_l|0}} litres
more per outage."

### 7f — energy flows (pass)

*[Next. Don't stop.]*

### 7b — other campuses (3:25–3:40) · drop if 15 s late

*[Next to 7b.]*

"Is it the best everywhere? No. Among methods without a central computer it's closest on {{q3.best_on_n|0}} of
{{q3.n_campuses|0}} campuses. On the others, a simpler per-building controller is closer, and we show that."

### 7c — network failure (3:40–3:55)

*[Next to 7c.]*

"When the campus network fails for three hours, central control falls {{q3.n.central_comms_penalty|1}} points further
from the best plan. Q-Grid falls only {{q3.n.qgrid_comms_penalty|1}}, because each building keeps optimising on its own."

### 7e — the bottom line (3:55–4:15)

*[Progress dot past 7d, to 7e.]*

"So Q-Grid buys reliability, not savings. On normal days the bill is {{hl.normal_abs_pct|1}} % {{hl.normal_dir}}; one
reason is a defect we found, charging batteries at the evening peak, and we're tracing it. The tariff is BESCOM's
official HT rate. Shoumik will show how we'd deploy it."

**Out:** hand to Shoumik (Deploy tab).

---

## The numbers behind each line (if asked "show me")

- Critical downtime per outage ({{hl.n_outage_days|0}} outage days): today {{hl.sq_downtime_h|2}} h · Q-Grid
  {{hl.q_downtime_h|2}} h · best possible plan {{hl.opt_downtime_h|2}} h.
- Diesel per outage day: today {{hl.sq_diesel_l|0}} L · Q-Grid {{hl.q_diesel_l|0}} L ({{hl.co2_abs_kg|0}} kg CO₂ more).
- Gap to the best plan, all days: Q-Grid {{q3.b.rvce.qgrid.gap_pct|1}} % · per-building MPC
  {{q3.b.rvce.per_building_mpc.gap_pct|1}} % · today {{q3.b.rvce.status_quo.gap_pct|1}} % · central MPC
  {{q3.b.rvce.central_mpc.gap_pct|1}} %.
- Gap on normal days only: Q-Grid {{hl.ngap.qgrid|1}} % · per-building MPC {{hl.ngap.per_building_mpc|1}} % · today
  {{hl.ngap.status_quo|1}} %. Day by day, per-building MPC is closer on {{q3.rv.alt_closer_days|0}} of
  {{q3.rv.n_days|0}} days (Wilcoxon p = {{q3.rv.p|3}}).
- Bill: {{hl.normal_abs_pct|1}} % {{hl.normal_dir}} on normal days, {{hl.all_abs_pct|1}} % {{hl.all_dir}} over all days.
  Demand charge per month: {{hl.dc.base.verb}} by Rs {{hl.dc.base.abs_change_rs|0}} at 1,300 kVA (Rs
  {{hl.dc.1000.change_rs|0}} at 1,000 kVA, Rs {{hl.dc.1600.change_rs|0}} at 1,600 kVA).
- Network failure: central MPC {{q3.b.rvce.central_mpc.gap_pct|2}} → {{q3.b.rvce.central_mpc_comms_fail.gap_pct|2}} %,
  Q-Grid {{q3.b.rvce.qgrid.gap_pct|2}} → {{q3.b.rvce.qgrid_comms_fail.gap_pct|2}} %.
- Payback: {{imp.sentence}}

## If a judge pushes on the weak spots

**"So it costs more money?"** "On normal days, yes, {{hl.normal_abs_pct|1}} % on the bill. The value is
{{hl.downtime_cut_min|0}} fewer minutes of blackout for critical loads per outage. We report the bill exactly as
measured."

**"Why does it charge batteries at the peak?"** "That's a defect we found in the full run: on 24 February it charged
the batteries at about 369 kW between 18:00 and 18:45 and set the month's peak. It's reproducible and we're tracing it
in the planner. We report it rather than hide it."

**"Then why not use per-building MPC?"** "It's cheaper on normal days, but it leaves critical loads dark for
{{hl.sq_downtime_h|1}} hours in an outage, the same as today. Only two buildings have diesel; Q-Grid shares that power
with the others to keep their critical loads up."

**"How does diesel power reach the other buildings?"** "In the model, over the proposed links between buildings. On
campus it depends on which buildings the two diesel sets can actually feed. That's one of the questions we've sent the
estate office. If they back only their own buildings, this gain shrinks."

**"Is it the best on other campuses?"** "No: closest on {{q3.best_on_n|0}} of {{q3.n_campuses|0}}. We name the method
that wins on each one, in Verify."
