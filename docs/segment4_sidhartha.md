# Segment 4 — Results (Sidhartha, 3:00–4:15)

_Rendered from `docs/templates/segment4_sidhartha.md`; every number from `results/` (locked headline:
`results/headline.json`). This version matches the **`real-data`** build (verified KERC tariff, RVCE's 500 kWp). If the
team presents the old portal, use Shoumik's PDF script instead: its numbers match that screen. About 190 words, 75 s._

**In:** Harshith ends with "Sidhartha has the numbers across all days."

---

### 7a — the scorecard (3:00–3:25)

*[Step button 7. Pause 3 s on the table.]*

"That was one day. Here are all 30: ten ways of running the campus on the same data, forecasts and BESCOM
tariff, against a central optimiser that knows the future. In a grid outage, Q-Grid cuts critical-load downtime from
2.6 hours to 20 minutes. Today's practice, and a controller that runs each
building separately, leave those loads dark the whole time. It costs diesel to do that: 45 litres
more per outage."

### 7f — energy flows (pass)

*[Next. Don't stop.]*

### 7b — other campuses (3:25–3:40) · drop if 15 s late

*[Next to 7b.]*

"Is it the best everywhere? No. Among methods without a central computer it's closest on 3 of
5 campuses. On the others, a simpler per-building controller is closer, and we show that."

### 7c — network failure (3:40–3:55)

*[Next to 7c.]*

"When the campus network fails for three hours, central control falls 2.7 points further
from the best plan. Q-Grid moves by 0.01, because each building keeps optimising on its own."

### 7e — the bottom line (3:55–4:15)

*[Progress dot past 7d, to 7e.]*

"So Q-Grid buys reliability, not savings. On normal days the bill is 0.1 % lower and the
demand charge falls by Rs 5,278 a month; with no central computer it lands
1.1 % from the best possible plan. The tariff is BESCOM's official HT rate. Shoumik will show
how we'd deploy it."

**Out:** hand to Shoumik (Deploy tab).

---

## The numbers behind each line (if asked "show me")

- Critical downtime per outage (3 outage days): today 2.58 h · Q-Grid
  0.33 h · best possible plan 0.00 h.
- Diesel per outage day: today 373 L · Q-Grid 418 L (122 kg CO₂ more).
- Gap to the best plan, all days: Q-Grid 1.1 % · per-building MPC
  9.2 % · today 16.8 % · central MPC
  1.4 %.
- Gap on normal days only: Q-Grid 0.6 % · per-building MPC 0.3 % · today
  2.4 %. Day by day, Q-Grid is closer than per-building MPC on 18 of
  30 days (Wilcoxon p = 0.070: not significant at 5 %).
- Bill: 0.1 % lower on normal days, 0.4 % higher over all days.
  Demand charge per month: falls by Rs 5,278 at 1,300 kVA (Rs
  -21,882 at 1,000 kVA, Rs 0 at 1,600 kVA).
- Network failure: central MPC 1.37 → 4.06 %,
  Q-Grid 1.06 → 1.08 %.
- Payback: Node hardware ≈ Rs 7.9 lakh for 9 buildings (assumed costs); the bill rises by ≈ Rs 3.2 lakh/year; extra battery wear ≈ Rs 3.3 lakh/year (every optimiser prices wear in its objective). On these assumptions the nodes do not pay back on the electricity bill alone (10-year NPV Rs -56.4 lakh) (Monte Carlo P5–P95: Rs -90.5 to -18.7 lakh; P(NPV > 0) = 0 %).

## If a judge pushes on the weak spots

**"Does it save money?"** "Barely. On normal days the bill is 0.1 % lower; over all
days it's 0.4 % higher, because in an outage it burns diesel to keep critical loads up. It
doesn't pay back the nodes on the bill alone. The value is 135 fewer minutes of blackout for
critical loads per outage. We report the bill exactly as measured."

**"Did you tune it until it won?"** "We fixed one defect the full run showed, and re-ran every Q-Grid row with the
same data and seeds. Each building got a share of the campus peak allowance that followed its own plan, so a building
that planned no import in some slot got almost no allowance there. On 24 February two buildings then charged their
batteries at the 18:00 peak. Now a building keeps what it planned plus a fixed share of the spare allowance. Both runs
and the change are in the repo."

**"Then why not use per-building MPC?"** "It's slightly closer on normal days (0.3 %
against 0.6 %), but it leaves critical loads dark for
2.6 hours in an outage, the same as today. Only two buildings have diesel; Q-Grid shares that power
with the others to keep their critical loads up."

**"How does diesel power reach the other buildings?"** "In the model, over the proposed links between buildings. On
campus it depends on which buildings the two diesel sets can actually feed. That's one of the questions we've sent the
estate office. If they back only their own buildings, this gain shrinks."

**"Is it the best on other campuses?"** "Not everywhere: closest on 3 of 5. We name the method
that wins on each one, in Verify."
