// Verify: every number traced to its file and script. The scorecard (results/bench_v3/summary.csv via replay/bench_v3.json)
// with click-to-provenance on each figure, the design history, a fresh check of the quantum block against exact search,
// what data is real and which files are still missing, and the SHA-256 of every source file.
import { useEffect, useRef, useState } from 'react'
import { getJSON, type Index } from '../lib/data'
import type { StoryData } from '../lib/story'
import { N } from '../panels/Prov'
import { LiveQaoa } from '../story/Live'

export type DataStatus = { checked_at: string; n_real: number; n_pending: number; how: string
  items: { key: string; label: string; status: string; real: boolean; files: { path: string; present: boolean }[]; missing: string[] }[] }

export function useDataStatus() {
  const [s, setS] = useState<DataStatus | null>(null)
  useEffect(() => { getJSON<DataStatus>('data_status.json').then(setS).catch(() => setS(null)) }, [])
  return s
}

export function DataBadge({ idx }: { idx: Index }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const ds = useDataStatus()
  useEffect(() => { const f = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }; document.addEventListener('click', f); return () => document.removeEventListener('click', f) }, [])
  const st = Object.entries(idx.data_status)
  const real = ds?.n_real ?? st.filter(([, v]) => v === 'REAL').length
  const pend = ds?.n_pending ?? st.length - real
  return (
    <div className="databadge" ref={ref}>
      <button className="btn ghost small" onClick={() => setOpen(o => !o)} aria-expanded={open}>Data: {real} real · <span className="pend">{pend} pending</span></button>
      {open && (
        <div className="pop" role="dialog" aria-label="data sources">
          {ds ? <ul className="dslist">{ds.items.map(i => <li key={i.key}><span>{i.label}</span><span className={i.real ? 'okc' : 'pend'}>{i.real ? 'Real' : i.status.charAt(0) + i.status.slice(1).toLowerCase()}</span>
            {!i.real && i.missing.length > 0 && <small className="muted">missing: {i.missing.join(' · ')}</small>}</li>)}</ul>
            : <table><tbody>{st.map(([k, v]) => <tr key={k}><td>{k}</td><td className={v === 'REAL' ? 'okc' : 'pend'}>{v}</td></tr>)}</tbody></table>}
          <p className="muted small">Pending items use labelled stand-ins and are never headline results. {ds ? `Checked ${ds.checked_at}. ` : ''}Map © OpenStreetMap contributors (ODbL).</p>
        </div>
      )}
    </div>
  )
}

const FORMULA: Record<string, string> = {
  gap_pct: '100 × (objective − best plan for the day) / best plan; objective = energy + diesel + battery wear + value of lost load + terminal value',
  certified_gap_pct: '100 × (objective − proven lower bound) / lower bound (LP relaxation, MILP dual bound, Lagrangian bound)',
  saving_pct: '100 × (status-quo bill − bill) / status-quo bill, same day; bill = energy + monthly demand charge (BESCOM HT-2(c)(ii), KERC Tariff Order 2023)',
  critical_downtime_h: '15-min slots with any unserved critical load × 0.25 h',
  critical_downtime_1pct_h: '15-min slots with more than 1 % of critical load unserved × 0.25 h',
  bill_rs: 'energy charges + the day’s share of the monthly demand charge (BESCOM HT-2(c)(ii), KERC Tariff Order 2023)',
  co2_kg: 'grid import kWh × CEA factor 0.727 t/MWh (verified) + diesel litres × 2.68 kg/L',
  runtime_per_decision_s: 'wall time of one 15-minute decision (planning + coordination)',
}
const COLS = ['gap_pct', 'certified_gap_pct', 'saving_pct', 'critical_downtime_h', 'bill_rs', 'co2_kg', 'runtime_per_decision_s']

export function VerifyView({ d, idx, online }: { d: StoryData; idx: Index; online: boolean }) {
  const B = d.bench
  const [ds, setDs] = useState('rvce')
  const status = useDataStatus()
  return (
    <main className="page">
      <section className="page-head">
        <h1 className="answer">Every number in this demo can be traced to the file and script that produced it.</h1>
        <p className="support">Click a figure to see its formula, source file, SHA-256 and git commit. Numbers come from <code>results/*.csv</code> written by this repository’s scripts; <code>make verify</code> recomputes the headline subset, and <code>docs/consistency.md</code> lists the checks every run must pass.</p>
      </section>
      {B && <section className="card">
        <div className="row"><h3>Scorecard</h3>
          <div className="seg">{B.datasets.map(x => <button key={x.key} className={ds === x.key ? 'on' : ''} onClick={() => setDs(x.key)}>{x.label.split(',')[0].split(' (')[0].replace("BDG2 university site ", '')}</button>)}</div></div>
        <div className="tablewrap"><table className="metrics">
          <thead><tr><th>Method</th>{COLS.map(k => { const m = B.metrics.find(x => x.key === k); return <th key={k}>{m?.label}{m?.unit ? ` (${m.unit})` : ''}</th> })}</tr></thead>
          <tbody>{[...B.methods, B.reference].map(me => (
            <tr key={me.key} className={me.key === 'qgrid' ? 'ours' : ''}><td>{me.name}</td>
              {COLS.map(k => {
                const m = B.metrics.find(x => x.key === k)!, s = B.table[ds]?.[me.key]?.[k]
                if (!s || s.mean === null) return <td key={k}>–</td>
                const v = s.mean.toLocaleString('en-IN', { maximumFractionDigits: m.digits, minimumFractionDigits: m.digits })
                return <td key={k}><N v={v} info={{ label: `${me.name} · ${m.label}`, unit: m.unit, formula: FORMULA[k] ?? m.label, file: 'results/bench_v3/summary.csv',
                  fn: 'scripts/run_bench_v3.py → scripts/write_bench_v3.py', row: `dataset=${ds}, method=${me.key}, mean of ${s.n} days, 95 % interval ${s.ci_lo?.toFixed(m.digits)} to ${s.ci_hi?.toFixed(m.digits)}` }} /></td>
              })}</tr>))}</tbody></table></div>
        <p className="muted small">Mean over {B.datasets.find(x => x.key === ds)?.n_days} days per method. Bill and saving use BESCOM HT-2(c)(ii) at KERC Tariff Order 2023 rates. Full tables with ± and Wilcoxon tests: docs/benchmark_v3.md.</p>
      </section>}
      {B && B.design_choices.length > 0 && <section className="card">
        <h3>How the design got here</h3>
        <p className="muted small">Earlier designs and the four-factor ablation, measured on RVCE days. The rows marked “battery wear not priced” predate that change and are history, not competitors.</p>
        <DesignTable rows={B.design_choices} />
      </section>}
      <section className="card">
        <h3>Check the quantum block yourself</h3>
        <p className="muted small">The worked example’s on/off block is measured again with QAOA (simulator) and compared with exact search over every setting.{online ? '' : ' Offline, precomputed measurements from the same code are shown.'}</p>
        <LiveQaoa d={d} online={online} />
      </section>
      <section className="card">
        <h3>Data: what is real, what is missing</h3>
        {status ? <table className="kv"><tbody>{status.items.map(i => <tr key={i.key}><td>{i.label}</td><td className={i.real ? 'okc' : 'pend'}>{i.real ? 'Real' : i.status}</td>
          <td className="small">{i.real ? i.files.filter(f => f.present).map(f => f.path).join(', ') : <>missing: {i.missing.map((m, j) => <span key={m}>{j ? ' · ' : ''}<code>{m}</code></span>)}</>}</td></tr>)}</tbody></table>
          : <p className="small warn">replay/data_status.json missing (python scripts/data_status.py).</p>}
        {status && <p className="muted small">Checked {status.checked_at}. {status.how}.</p>}
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
  const f = (x: number | null | undefined, dd = 2) => (x === null || x === undefined || Number.isNaN(x) ? '–' : x.toFixed(dd))
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
