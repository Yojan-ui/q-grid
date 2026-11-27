// One-page summary for print / "Save as PDF": problem, method, scorecard, data provenance. Always printed in the
// light palette. Every figure is read from the same replay files as the story (scenario_*.json, bench_v3.json,
// index.json); this file only selects and formats them. Missing inputs are named, never filled in.
import { Fragment } from 'react'
import type { Index } from '../lib/data'
import { fmtDate, zn } from '../lib/labels'
import type { StoryData } from '../lib/story'
import { num, rs } from '../lib/theme'
import { GROUP_ORDER } from './Scorecard'

const COLS = ['bill_rs', 'saving_pct', 'critical_downtime_h', 'co2_kg', 'gap_pct', 'certified_gap_pct', 'runtime_per_decision_s']
const PRICE_METRICS = new Set(['bill_rs', 'saving_pct', 'npv10_rs_lakh', 'battery_degradation_rs'])
const SOURCE_LABEL: Record<string, string> = {
  nasa_power: 'NASA POWER irradiance', ausgrid_hostel_shape: 'Ausgrid household shapes (hostels)', bdg2_load_shapes: 'BDG2 education-building meters',
  osm_layout: 'OpenStreetMap layout', iex: 'IEX day-ahead prices', tariff_A: 'KERC / BESCOM tariff', cea: 'CEA CO₂ factor',
  calendar: 'RVCE academic calendar', campus_loads: 'Campus meter data', lab_schedule: 'Lab schedule',
}

export function SummaryDoc({ d, idx, ds }: { d: StoryData; idx: Index; ds: string }) {
  const { sc } = d
  const B = d.bench
  const pr = sc.problem
  const tariffPending = sc.price_status !== 'REAL' || (B?.tariff_status ?? 'PENDING') !== 'REAL'
  const ceaPending = sc.data_status?.cea !== 'REAL'
  const pl = d.qs?.placement
  const dsl = B?.datasets.find(x => x.key === ds)
  const metrics = B ? COLS.map(k => B.metrics.find(m => m.key === k)).filter(Boolean) as NonNullable<typeof B>['metrics'] : []
  const f = (v: number | undefined, digits: number) => (v === undefined || v === null || Number.isNaN(v) ? '–' : v.toLocaleString('en-IN', { maximumFractionDigits: digits, minimumFractionDigits: digits }))
  const missing = [!pr && `problem figures (scenario_${sc.scenario.key}.json has no "problem")`, !B && 'benchmark scorecard (replay/bench_v3.json)'].filter(Boolean)
  return (
    <article className="summary-doc" aria-hidden="true">
      <h1>Q-Grid: decentralised scheduling for a campus solar + battery microgrid</h1>
      <p className="sd-sub">One-page summary · EUREKA Track 3 · headline day {sc.scenario.key.replace(/_/g, ' ')}, {fmtDate(sc.scenario.date)} · generated {new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })} from the replay files</p>

      <h2>The problem</h2>
      <p>{B?.headline.story ? <>{B.headline.story.step1.text}{tariffPending ? ' (tariff not fully verified)' : ''} </> : <>Today every building at RVCE acts on its own: it sells noon solar cheaply, buys power back at the evening peak and runs diesel when the BESCOM supply fails. </>}On the modelled headline day:</p>
      {pr ? (
        <div className="sd-keys">
          <div><span>Value lost per day {tariffPending && <i className="sd-pend">tariff not fully verified</i>}</span><b>{rs(pr.rs_lost)}</b></div>
          <div><span>CO₂ per day {ceaPending && <i className="sd-pend">stand-in factor</i>}</span><b>{num(pr.co2_kg)} kg</b></div>
          <div><span>Diesel running · critical loads unserved</span><b>{pr.dg_hours.toFixed(1)} h · {pr.critical_downtime_h.toFixed(1)} h</b></div>
        </div>
      ) : <p>Not in this replay.</p>}
      {pr && <p className="sd-foot" style={{ marginTop: 0 }}>{pr.definition}.</p>}

      <h2>The method</h2>
      {d.qs ? (
        <div className="sd-two">
          <div>
            <p><b>Inside each building</b>: an exact branch-and-bound solve of its own 24 h on/off plan at the prices the neighbours agreed.</p>
            <p><b>Between buildings</b>: battery, diesel, cable and grid power as a linear programme, agreed by neighbours trading proposals (consensus ADMM). No central computer.</p>
          </div>
          <div>
            <p><b>Quantum</b>: QAOA was tested as a starting plan for the on/off choices{pl?.instances ? ` on ${num(pl.instances)} building problems` : ''}; it did not make the exact solver faster, so it is not in the loop.</p>
            <p className="sd-honest">{idx.label}.</p>
          </div>
        </div>
      ) : (
        <div className="sd-two">
          <div>
            <p><b>Inside each building</b>: its yes/no decisions for the next slots become a QUBO; QAOA (≤ 16 qubits, simulated) proposes a plan, which is checked against exact search. Fallback if it misses: QIEA, then annealing, then exact. A safety layer clamps every command.</p>
          </div>
          <div>
            <p><b>Between buildings</b>: neighbours agree on each cable's flow by trading proposals (consensus ADMM), classical, with no central computer.</p>
            <p className="sd-honest">{idx.label}.</p>
          </div>
        </div>
      )}

      <h2>Scorecard{dsl ? `: ${dsl.label}, mean of ${dsl.n_days} days` : ''}</h2>
      {B ? <>
        <p>{B.headline.story ? <><b>{B.headline.story.step7.text}</b> {B.headline.story.step7.comms} </> : null}{B.headline.text}</p>
        <table>
          <thead><tr><th>Method</th>{metrics.map(m => <th key={m.key}>{m.label}{m.unit ? ` (${m.unit})` : ''}{PRICE_METRICS.has(m.key) && tariffPending ? ' *' : ''}</th>)}</tr></thead>
          <tbody>
            {GROUP_ORDER.map(g => {
              const rows = B.methods.filter(m => m.group === g)
              if (!rows.length) return null
              return <Fragment key={g}>
                <tr className="gr"><td colSpan={metrics.length + 1}>{g}</td></tr>
                {rows.map(me => <tr key={me.key} className={me.key === 'qgrid' ? 'ours' : ''}><td>{me.name}{me.without_coordinator ? '' : ' (central)'}</td>
                  {metrics.map(m => <td key={m.key}>{f(B.table[ds]?.[me.key]?.[m.key]?.mean, m.digits)}</td>)}</tr>)}
              </Fragment>
            })}
            {B.table[ds]?.[B.reference.key] && <tr className="ref"><td>{B.reference.name}</td>{metrics.map(m => <td key={m.key}>{f(B.table[ds][B.reference.key][m.key]?.mean, m.digits)}</td>)}</tr>}
          </tbody>
        </table>
        <p className="sd-foot">{tariffPending ? '* Tariffs and demand charge are labelled stand-ins (PENDING) until the official BESCOM/KERC tariff is added. ' : ''}Full tables with ± and 95 % intervals: docs/benchmark_v3.md. All methods run on identical data, days, constraints and horizon.</p>
      </> : <p>The benchmark results are not in this replay (replay/bench_v3.json missing).</p>}

      <h2>Data provenance</h2>
      {(() => {
        const st = Object.entries(idx.data_status)
        const real = st.filter(([, v]) => v === 'REAL').map(([k]) => SOURCE_LABEL[k] ?? k)
        const pend = st.filter(([, v]) => v !== 'REAL')
        return <p><b>Real:</b> {real.join(', ')}. <b>Pending (labelled stand-ins):</b> {pend.map(([k, v], i) => <Fragment key={k}>{i ? ', ' : ''}{SOURCE_LABEL[k] ?? k} <i className="sd-pend">{v.toLowerCase()}</i></Fragment>)}.</p>
      })()}
      <p className="sd-foot">Pending items use labelled stand-ins and are never headline results. Worked example: {zn(d.example.zone).toLowerCase()} at {d.example.time ?? sc.slots.t[d.example.slot]}.
        Git commit {idx.provenance.git_commit.slice(0, 12)} · {Object.keys(idx.provenance.files).length} source files hashed (SHA-256) in replay/index.json · map © OpenStreetMap contributors (ODbL).
        {missing.length ? ` Missing from this replay: ${missing.join('; ')}.` : ''}</p>
    </article>
  )
}
