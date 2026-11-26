// Secondary tabs after the story: Verify (provenance, live solve) and Try it (labelled what-if sandbox).
import { useEffect, useRef, useState } from 'react'
import type { Index } from '../lib/data'
import type { StoryData } from '../lib/story'
import { MetricsTable, RuleBox, SolveLive, Stress } from '../panels/Judge'
import { Sandbox } from '../panels/Sandbox'
import { getJSON } from '../lib/data'

const SOURCE_LABEL: Record<string, string> = {
  nasa_power: 'NASA POWER irradiance', ausgrid_hostel_shape: 'Ausgrid household shapes (hostels)', bdg2_load_shapes: 'BDG2 education-building meters (load shapes)', osm_layout: 'OpenStreetMap layout',
  iex: 'IEX day-ahead prices', tariff_A: 'KERC / BESCOM tariff', cea: 'CEA CO₂ factor', calendar: 'RVCE academic calendar',
  campus_loads: 'Campus meter data', lab_schedule: 'Lab schedule',
}

export function DataBadge({ idx }: { idx: Index }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { const f = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }; document.addEventListener('click', f); return () => document.removeEventListener('click', f) }, [])
  const st = Object.entries(idx.data_status)
  const pend = st.filter(([, v]) => v !== 'REAL').length
  return (
    <div className="databadge" ref={ref}>
      <button className="btn ghost small" onClick={() => setOpen(o => !o)} aria-expanded={open}>Data: {st.length - pend} real · <span className="pend">{pend} pending</span></button>
      {open && (
        <div className="pop" role="dialog" aria-label="data sources">
          <table><tbody>{st.map(([k, v]) => <tr key={k}><td>{SOURCE_LABEL[k] ?? k}</td><td className={v === 'REAL' ? 'okc' : 'pend'}>{v === 'REAL' ? 'Real' : v.charAt(0) + v.slice(1).toLowerCase()}</td></tr>)}</tbody></table>
          <p className="muted small">Pending items use labelled stand-ins and are never headline results. Map © OpenStreetMap contributors (ODbL).</p>
        </div>
      )}
    </div>
  )
}

export function VerifyView({ d, idx, online }: { d: StoryData; idx: Index; online: boolean }) {
  const [price, setPrice] = useState('A')
  return (
    <main className="page">
      <section className="page-head">
        <h1 className="answer">Check any number.</h1>
        <p className="support">Click a figure to see its formula, source file, SHA-256, script and git commit. Every figure comes from <code>results/*.csv</code> produced by this repository’s scripts; <code>make verify</code> recomputes the headline numbers.</p>
      </section>
      <section className="card">
        <div className="row"><h3>Benchmark: {d.sc.scenario.key.replace(/_/g, ' ')} day</h3>
          <div className="seg">{['A', 'B'].map(p => <button key={p} className={price === p ? 'on' : ''} onClick={() => setPrice(p)}>Prices {p}</button>)}</div></div>
        <MetricsTable sc={d.sc} price={price} />
      </section>
      {d.bench && d.bench.design_choices.length > 0 && <section className="card">
        <h3>Design choices (ablation)</h3>
        <p className="muted small">How each change to the design moved the gap to the best possible plan. Q-Grid uses the combination with the smallest gap that works without a central controller.</p>
        <DesignTable rows={d.bench.design_choices} />
      </section>}
      <section className="card">
        <h3>Solve a slot live</h3>
        <p className="muted small">Pick a zone and slot: the QUBO, QAOA’s best-of-256 plan, and the exact optimum. With <code>?live</code> and a running backend, it re-solves on the server.</p>
        {d.sc.live_solve && <SolveLive live={d.sc.live_solve} online={online} scenario={d.sc.scenario.key} />}
      </section>
      <section className="card">
        <h3>Provenance</h3>
        <table className="kv"><tbody>
          <tr><td>git commit</td><td><code>{idx.provenance.git_commit}</code></td></tr>
          {Object.entries(idx.provenance.files).map(([f, h]) => <tr key={f}><td><code>{f}</code></td><td><code className="sha">{h}</code></td></tr>)}
          <tr><td>replay matches benchmark</td><td>{String(d.sc.replay_matches_benchmark)}</td></tr>
        </tbody></table>
      </section>
    </main>
  )
}

function DesignTable({ rows }: { rows: NonNullable<StoryData['bench']>['design_choices'] }) {
  const f = (x: number | null | undefined, d = 2) => (x === null || x === undefined || Number.isNaN(x) ? '–' : x.toFixed(d))
  const sorted = [...rows].sort((a, b) => (a.gap_pct ?? 1e9) - (b.gap_pct ?? 1e9))
  return (
    <div className="tablewrap"><table className="tbl">
      <thead><tr><th>Design</th><th>Where measured</th><th>Gap %</th><th>Certified gap %</th><th>Critical downtime h</th><th>Time per decision s</th></tr></thead>
      <tbody>{sorted.map(r => (
        <tr key={r.key}><td>{r.name}</td><td className="muted small">{r.what_changed}</td><td className="tn">{f(r.gap_pct)}</td>
          <td className="tn">{f(r.certified_gap_pct)}</td><td className="tn">{f(r.critical_downtime_h)}</td><td className="tn">{f(r.runtime_per_decision_s)}</td></tr>))}</tbody>
    </table></div>
  )
}

export function TryView({ d, online }: { d: StoryData; online: boolean }) {
  const [extra, setExtra] = useState<{ sandbox: any; rules: any[] }>({ sandbox: null, rules: [] })
  useEffect(() => {
    getJSON<any>('sandbox.json').then(s => setExtra(x => ({ ...x, sandbox: s }))).catch(() => {})
    getJSON<any[]>('rules.json').then(r => setExtra(x => ({ ...x, rules: r }))).catch(() => {})
  }, [])
  return (
    <main className="page">
      <section className="page-head">
        <h1 className="answer">Try it: what if…</h1>
        <p className="support"><span className="pending">sandbox</span> What-ifs use the quantum-inspired classical solver (C-QIEA) and are never headline results. Offline, the nearest precomputed case is shown.</p>
      </section>
      <section className="card"><h3>Change one thing</h3><Sandbox online={online} sandbox={extra.sandbox} scenario={d.sc.scenario.key} /></section>
      <section className="card"><h3>Stress tests</h3><Stress online={online} sandbox={extra.sandbox} scenario={d.sc.scenario.key} onKill={() => {}} /></section>
      <section className="card"><h3>Add an operator rule</h3><RuleBox online={online} rules={extra.rules} /></section>
    </main>
  )
}
