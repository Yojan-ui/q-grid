// Plan: the investment planner. Pick extra rooftop solar per roof group, a battery size and a contract demand; the
// outcome (payback, 10-year NPV, peak demand, diesel, CO2) is read from the matching case in replay/planner.json,
// a grid of cases computed by scripts/plan_investment.py. Nothing is interpolated or computed here: off-grid choices
// show the nearest computed case and say so.
import { useEffect, useMemo, useState } from 'react'
import { loadPlanner, type PlanOutcome, type Planner } from '../lib/data'
import type { StoryData } from '../lib/story'
import { reg, regText } from '../lib/numcheck'
import { lakh } from '../story/Impact'
import { SourcesButton } from '../panels/Sources'

const n0 = (v: number) => Math.round(v).toLocaleString('en-IN')
const snap = (v: number, step: number, max: number) => Math.max(0, Math.min(max, step > 0 ? Math.round(v / step) * step : v))

type Sel = { extra: Record<string, number>; battery: number; contract: number }

/** The computed case closest to the selection (each input measured in its own grid steps). */
function nearest(p: Planner, s: Sel): { c: PlanOutcome; exact: boolean } | null {
  if (!p.cases.length) return null
  const opts = p.contract_demand_options ?? []
  const ci = (v: number) => { const i = opts.indexOf(v); return i >= 0 ? i : v / 100 }
  let best: PlanOutcome | null = null, bd = Infinity
  for (const c of p.cases) {
    let dd = 0
    for (const g of p.roof_groups) dd += (((c.extra_kwp?.[g.key] ?? 0) - (s.extra[g.key] ?? 0)) / (g.step_kwp || 1)) ** 2
    dd += ((c.battery_kwh - s.battery) / (p.battery.step_kwh || 1)) ** 2
    dd += (ci(c.contract_kva) - ci(s.contract)) ** 2
    if (dd < bd) { bd = dd; best = c }
  }
  return best ? { c: best, exact: bd < 1e-9 } : null
}

export function PlanView({ d }: { d: StoryData }) {
  const [p, setP] = useState<Planner | null | undefined>(undefined)
  useEffect(() => { let off = false; loadPlanner().then(x => { if (!off) setP(x) }); return () => { off = true } }, [])
  if (p === undefined) return <main className="page plan"><div className="loading" role="status"><span className="bar"><i /></span><span>Loading the investment planner…</span></div></main>
  if (p === null) return <PlanMissing />
  return <PlanBody p={p} d={d} />
}

function PlanMissing() {
  return (
    <main className="page plan" aria-label="Plan: investment planner">
      <section className="page-head"><h1 className="answer">The investment planner is not generated yet.</h1>
        <p className="support">This tab shows what adding rooftop solar, a battery or a different contract demand would do to payback, the 10-year value, peak demand, diesel and CO₂. Its cases come from the pipeline, never from the browser.</p></section>
      <section className="card plan-missing" role="status">
        <h3>To generate it</h3>
        <p className="small">Run <code>python scripts/plan_investment.py</code>. It writes <code>results/replay/planner.json</code>; <code>make replay</code> copies it to <code>frontend/public/replay/planner.json</code>.</p>
        <p className="muted small">Until then nothing is shown: the demo never falls back to sample numbers.</p>
        <button className="btn small" onClick={() => location.reload()}>Check again</button>
      </section>
    </main>
  )
}

function PlanBody({ p, d }: { p: Planner; d: StoryData }) {
  const start: Sel = useMemo(() => ({ extra: Object.fromEntries(p.roof_groups.map(g => [g.key, 0])), battery: 0, contract: p.contract_demand_options?.[0] ?? p.cases[0]?.contract_kva ?? 0 }), [p])
  const [sel, setSel] = useState<Sel>(start)
  const [showOpt, setShowOpt] = useState(false)
  const hit = useMemo(() => nearest(p, sel), [p, sel])
  const c = hit?.c ?? null
  const set = (f: (s: Sel) => Sel) => { setShowOpt(false); setSel(f) }
  const toOptimum = () => {
    const o = p.optimum
    setSel({ extra: Object.fromEntries(p.roof_groups.map(g => [g.key, o.extra_kwp?.[g.key] ?? 0])), battery: o.battery_kwh, contract: o.contract_kva })
    setShowOpt(true)
  }
  const tariff = p.labels?.tariff, costs = p.labels?.costs
  return (
    <main className="page plan" aria-label="Plan: investment planner">
      <section className="page-head">
        <h1 className="answer">What should RVCE add next? Pick solar, a battery and a contract demand to see what each choice pays back.</h1>
        <p className="support">Every outcome is a case computed by the pipeline over the modelled RVCE year; the planner only looks it up. <SourcesButton rows={d.sc.data_provenance} label="Where the planner's inputs come from" /></p>
        <div className="plan-labels small">
          <span className="pill src">{regText(p.generated_by, 'planner generated_by (replay text)')}</span>
          {p.status && <span className={`pill ${p.status === 'REAL' || p.status === 'FINAL' ? 'ok' : 'warn'}`}>{p.status.toLowerCase()}</span>}
          {tariff && <span title={tariff}><span className="pending">FY24 tariff carried over</span> {regText(tariff, 'planner tariff label (replay text)')}</span>}
          {costs && <span title={costs}><span className="pending">assumed costs</span> {regText(costs, 'planner cost label (replay text)')}</span>}
        </div>
      </section>

      <div className="plan-grid">
        <section className="card plan-inputs" aria-label="choices">
          <h3>What to add</h3>
          {p.roof_groups.map(g => {
            const v = sel.extra[g.key] ?? 0
            return (
              <div key={g.key} className="plan-in">
                <label htmlFor={`pv-${g.key}`}><span>{g.label}</span><b className="tn">+{n0(v)} kWp</b></label>
                <input id={`pv-${g.key}`} type="range" min={0} max={g.max_extra_kwp} step={g.step_kwp || 1} value={v}
                  onChange={e => { const x = snap(+e.target.value, g.step_kwp, g.max_extra_kwp); set(s => ({ ...s, extra: { ...s.extra, [g.key]: x } })) }} />
                <span className="muted small tn">today {n0(g.existing_kwp)} kWp · after {n0(reg(g.existing_kwp + v, `planner: existing + chosen extra kWp, ${g.key}`))} kWp</span>
              </div>
            )
          })}
          <div className="plan-in">
            <label htmlFor="pl-bat"><span>Battery storage</span><b className="tn">+{n0(sel.battery)} kWh</b></label>
            <input id="pl-bat" type="range" min={0} max={p.battery.max_kwh} step={p.battery.step_kwh || 1} value={sel.battery}
              onChange={e => { const x = snap(+e.target.value, p.battery.step_kwh, p.battery.max_kwh); set(s => ({ ...s, battery: x })) }} />
          </div>
          {(p.contract_demand_options ?? []).length > 0 && <div className="plan-in">
            <span id="pl-cd" className="plan-inlabel">Contract demand with BESCOM</span>
            <div className="seg" role="radiogroup" aria-labelledby="pl-cd">{p.contract_demand_options.map(o =>
              <button key={o} role="radio" aria-checked={sel.contract === o} className={sel.contract === o ? 'on' : ''} onClick={() => set(s => ({ ...s, contract: o }))}>{n0(o)} kVA</button>)}</div>
          </div>}
          <div className="row">
            <button className={`btn small ${showOpt ? 'primary' : ''}`} onClick={toOptimum} aria-pressed={showOpt}>Show the optimum</button>
            <button className="btn ghost small" onClick={() => set(() => start)}>Reset</button>
          </div>
        </section>

        <section className="card plan-out" aria-label="outcome" aria-live="polite">
          <div className="plan-outhead"><h3>{showOpt ? 'The optimum' : 'What it would do'}</h3>
            {c && <span className={`pill ${hit?.exact ? 'ok' : 'warn'}`}>{hit?.exact ? 'computed case' : 'nearest computed case'}</span>}</div>
          {!c ? <p className="muted small">planner.json has no cases.</p> : <>
            {!hit?.exact && <p className="small muted">No case was computed for exactly this choice; showing the closest one: {p.roof_groups.map(g => `+${n0(c.extra_kwp?.[g.key] ?? 0)} kWp ${g.label.toLowerCase()}`).join(', ')}, +{n0(c.battery_kwh)} kWh battery, {n0(c.contract_kva)} kVA.</p>}
            <div className="keys-row k2">
              <div className="key"><span className="kl">Payback{tariff && <span className="pending">FY24 tariff carried over</span>}</span><b className="kv">{c.payback_years !== null && c.payback_years !== undefined ? `${c.payback_years.toFixed(1)} y` : c.capex_rs > 0 ? 'not reached' : 'nothing added'}</b></div>
              <div className="key"><span className="kl">10-year NPV</span><b className="kv">{lakh(c.npv10_rs)}</b></div>
              <div className="key"><span className="kl">Investment{costs && <span className="pending">assumed</span>}</span><b className="kv">{lakh(c.capex_rs)}</b><span className="kn">saves {lakh(c.annual_saving_rs)} a year</span></div>
              <div className="key"><span className="kl">Peak demand</span><b className="kv">{n0(c.peak_kva)} kVA</b><span className="kn">contract {n0(c.contract_kva)} kVA</span></div>
              <div className="key"><span className="kl">Diesel</span><b className="kv">{n0(c.diesel_litres_year)} L</b><span className="kn">per year</span></div>
              <div className="key"><span className="kl">CO₂</span><b className="kv">{c.co2_t_year.toLocaleString('en-IN', { maximumFractionDigits: 1 })} t</b><span className="kn">per year</span></div>
            </div>
            {showOpt && p.optimum.note && <p className="small">{regText(p.optimum.note, 'planner optimum note (replay text)')}</p>}
          </>}
          <p className="muted small">{p.cases.length} cases computed by {regText(p.generated_by, 'planner generated_by (replay text)')}. Choices snap to the grid the planner was run on.</p>
        </section>
      </div>

      {p.assumptions?.length > 0 && <section className="card">
        <h3>Assumptions <span className="pending">labelled</span></h3>
        <div className="tablewrap"><table className="tbl plan-assume"><thead><tr><th>Assumption</th><th>Value</th><th>Source</th></tr></thead>
          <tbody>{p.assumptions.map(a => <tr key={a.name}><td>{a.name}</td>
            <td className="tn">{a.value === null || a.value === undefined ? '–' : Array.isArray(a.value) ? `${a.value[0].toLocaleString('en-IN')}–${a.value[1].toLocaleString('en-IN')}` : typeof a.value === 'number' ? a.value.toLocaleString('en-IN') : regText(String(a.value), 'planner assumption value (replay text)')} {a.unit}</td>
            <td className="muted">{regText(a.source, 'planner assumption source (replay text)')}</td></tr>)}</tbody></table></div>
      </section>}
    </main>
  )
}
