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
from the best plan. Q-Grid moves by {{q3.n.qgrid_comms_penalty|2}}, because each building keeps optimising on its own."

### 7e — the bottom line (3:55–4:15)

*[Progress dot past 7d, to 7e.]*

"So Q-Grid buys reliability, not savings. On normal days the bill is {{hl.normal_abs_pct|1}} % {{hl.normal_dir}} and the
demand charge {{hl.dc.base.verb}} by Rs {{hl.dc.base.abs_change_rs|0}} a month; with no central computer it lands
{{q3.b.rvce.qgrid.gap_pct|1}} % from the best possible plan. The tariff is BESCOM's official HT rate. Shoumik will show
how we'd deploy it."

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
  {{hl.ngap.status_quo|1}} %. Day by day, Q-Grid is closer than per-building MPC on {{q3.rv.qgrid_closer_days|0}} of
  {{q3.rv.n_days|0}} days (Wilcoxon p = {{q3.rv.p|3}}: not significant at 5 %).
- Bill: {{hl.normal_abs_pct|1}} % {{hl.normal_dir}} on normal days, {{hl.all_abs_pct|1}} % {{hl.all_dir}} over all days.
  Demand charge per month: {{hl.dc.base.verb}} by Rs {{hl.dc.base.abs_change_rs|0}} at 1,300 kVA (Rs
  {{hl.dc.1000.change_rs|0}} at 1,000 kVA, Rs {{hl.dc.1600.change_rs|0}} at 1,600 kVA).
- Network failure: central MPC {{q3.b.rvce.central_mpc.gap_pct|2}} → {{q3.b.rvce.central_mpc_comms_fail.gap_pct|2}} %,
  Q-Grid {{q3.b.rvce.qgrid.gap_pct|2}} → {{q3.b.rvce.qgrid_comms_fail.gap_pct|2}} %.
- Payback: {{imp.sentence}}

## If a judge pushes on the weak spots

**"Does it save money?"** "Barely. On normal days the bill is {{hl.normal_abs_pct|1}} % {{hl.normal_dir}}; over all
days it's {{hl.all_abs_pct|1}} % {{hl.all_dir}}, because in an outage it burns diesel to keep critical loads up. It
doesn't pay back the nodes on the bill alone. The value is {{hl.downtime_cut_min|0}} fewer minutes of blackout for
critical loads per outage. We report the bill exactly as measured."

**"Did you tune it until it won?"** "We fixed one defect the full run showed, and re-ran every Q-Grid row with the
same data and seeds. Each building got a share of the campus peak allowance that followed its own plan, so a building
that planned no import in some slot got almost no allowance there. On 24 February two buildings then charged their
batteries at the 18:00 peak. Now a building keeps what it planned plus a fixed share of the spare allowance. Both runs
and the change are in the repo."

**"Then why not use per-building MPC?"** "It's slightly closer on normal days ({{hl.ngap.per_building_mpc|1}} %
against {{hl.ngap.qgrid|1}} %), but it leaves critical loads dark for
{{hl.sq_downtime_h|1}} hours in an outage, the same as today. Only two buildings have diesel; Q-Grid shares that power
with the others to keep their critical loads up."

**"How does diesel power reach the other buildings?"** "In the model, over the proposed links between buildings. On
campus it depends on which buildings the two diesel sets can actually feed. That's one of the questions we've sent the
estate office. If they back only their own buildings, this gain shrinks."

**"Is it the best on other campuses?"** "Not everywhere: closest on {{q3.best_on_n|0}} of {{q3.n_campuses|0}}. We name the method
that wins on each one, in Verify."
