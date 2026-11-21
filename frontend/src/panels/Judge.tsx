import { useMemo, useState } from 'react'
import type { LiveSolve, Scenario } from '../lib/data'
import { fmt, post } from '../lib/data'
import { bits, energies, isingNormalised, qaoaLayers, sample } from '../lib/qaoa'
import { FORMULA, N } from './Prov'

const METRICS: [string, string, number][] = [['cost_rs', 'Rs/day', 0], ['objective_rs', 'Rs/day', 0], ['critical_downtime_h', 'h', 2],
  ['critical_unserved_kwh', 'kWh', 1], ['dg_hours', 'h', 2], ['dg_litres', 'L', 0], ['co2_kg', 'kg', 0], ['gap_to_B4_pct', '%', 2],
  ['replan_time_s', 's/slot', 3], ['qaoa_p_opt', '', 4], ['admm_convergence_rate', '', 2]]

export function MetricsTable({ sc, price }: { sc: Scenario; price: string }) {
  const rows = sc.benchmark.filter(r => r.price_scenario === price)
  const order = ['B0', 'B1', 'B2-GA', 'B2-PSO', 'B3', 'C-QIEA', 'B5', 'OURS-QIEA', 'OURS', 'B4']
  return (
    <div className="tablewrap">
      <table className="metrics">
        <thead><tr><th>method</th>{METRICS.map(([k, u]) => <th key={k}>{k.replace(/_/g, ' ')}{u ? ` (${u})` : ''}</th>)}</tr></thead>
        <tbody>{order.map(m => rows.find(r => r.method === m)).filter(Boolean).map((r: any) => (
          <tr key={r.method} className={r.method === 'OURS' ? 'ours' : ''}>
            <td>{r.method}</td>
            {METRICS.map(([k, u, d]) => <td key={k}>{r[k] === undefined || r[k] === null || Number.isNaN(Number(r[k])) ? '–' :
              <N v={fmt(Number(r[k]), d)} info={{ label: `${r.method} · ${k}`, unit: u, formula: FORMULA[k] ?? k, file: 'results/benchmark.csv',
                fn: 'scripts/run_benchmark.py -> qgrid.model.settle', row: `method=${r.method}, scenario=${r.scenario}, price_scenario=${r.price_scenario}, day=${r.day}` }} />}</td>)}
          </tr>))}</tbody>
      </table>
      <div className="small muted">Prices: {sc.price_status === 'REAL' ? 'REAL' : 'STAND-IN (PENDING) — not headline results'}. QIEA rows = quantum-inspired, classical CPU.</div>
    </div>
  )
}

function Heatmap({ M, names }: { M: number[][]; names: string[] }) {
  const n = M.length, mx = Math.max(...M.flat().map(Math.abs)) || 1, c = Math.min(22, 300 / n)
  return (
    <svg width={c * n + 70} height={c * n + 10} aria-label="QUBO heatmap">
      {M.map((row, i) => row.map((v, j) => (
        <rect key={`${i}-${j}`} x={70 + j * c} y={i * c} width={c - 1} height={c - 1}
          fill={v >= 0 ? `rgba(255,90,95,${Math.sqrt(Math.abs(v) / mx)})` : `rgba(61,220,151,${Math.sqrt(Math.abs(v) / mx)})`}>
          <title>{`${names[i]} × ${names[j]} = ${v.toFixed(3)}`}</title></rect>)))}
      {names.map((nm, i) => <text key={nm} x={66} y={i * c + c * 0.7} fontSize={Math.min(10, c * 0.7)} fill="#8A94A6" textAnchor="end">{nm}</text>)}
    </svg>
  )
}

export function SolveLive({ live, online, scenario, params }: { live: LiveSolve[]; online: boolean; scenario: string; params: [number[], number[]] }) {
  const [i, setI] = useState(0)
  const [res, setRes] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const L = live[i]
  const browser = useMemo(() => {
    if (!L || L.n_qubits > 14) return null
    const t0 = performance.now()
    const E = energies({ M: L.qubo_matrix }); const En = isingNormalised({ M: L.qubo_matrix }, E)
    let z0 = 0; for (let z = 1; z < E.length; z++) if (E[z] < E[z0]) z0 = z
    const P = qaoaLayers(En, params[0], params[1])
    const fin = P[P.length - 1]
    const s = sample(fin, 256)
    const best = s.reduce((b, z) => (E[z] < E[b] ? z : b), s[0])
    return { exact: bits(z0, L.n_qubits), best: bits(best, L.n_qubits), pOpt: fin[z0], verified: best === z0, ms: performance.now() - t0 }
  }, [L, params])
  if (!L) return <div className="small">No live-solve instances in this replay.</div>
  const run = async () => {
    setBusy(true)
    try { setRes(await post('/solve', { scenario, zone: L.zone, slot: L.slot, backend: 'aer' })) } catch (e) { setRes({ error: String(e) }) }
    setBusy(false)
  }
  const q = res?.qaoa ?? L.qaoa, ex = res?.exact ?? L.exact
  return (
    <div className="solve">
      <div className="row wrap">
        <select value={i} onChange={e => { setI(+e.target.value); setRes(null) }} aria-label="zone and slot" style={{ flex: 1 }}>
          {live.map((x, k) => <option key={k} value={k}>{x.zone} @ {x.time} ({x.n_qubits} qubits)</option>)}
        </select>
        <button onClick={run} disabled={!online || busy}>{online ? (busy ? 'Solving…' : 'Solve on backend') : 'Precomputed (offline)'}</button>
      </div>
      <div className="grid2">
        <div><Heatmap M={res?.qubo_matrix ?? L.qubo_matrix} names={L.var_names} /></div>
        <div>
          <table className="kv"><tbody>
            <tr><th></th><th>QAOA (p=2)</th><th>Exact</th></tr>
            <tr><td>bitstring</td><td><code>{q.best_bits ?? '—'}</code></td><td><code>{ex.bits}</code></td></tr>
            <tr><td>cost</td><td>{q.best_objective?.toFixed?.(2) ?? (q.best_bits ? '' : '—')}</td><td>{ex.objective.toFixed(2)}</td></tr>
            <tr><td>feasible</td><td>{String(q.feasible)}</td><td>true</td></tr>
            <tr><td>approx ratio</td><td>{q.approx_ratio.toFixed(4)}</td><td>1</td></tr>
            <tr><td>P(optimum)</td><td>{(q.p_opt * 100).toFixed(3)}%</td><td>—</td></tr>
            <tr><td>time</td><td>{(q.time_s * 1000).toFixed(1)} ms</td><td>{(ex.time_s * 1000).toFixed(1)} ms</td></tr>
          </tbody></table>
          <div className="small muted">{res ? 'live backend result' : 'precomputed in replay'} · simulated QAOA, verified vs exact, no quantum advantage claimed</div>
          {browser && <div className="small">In-browser re-run: exact {browser.exact}, QAOA best-of-256 {browser.best} → {browser.verified ? 'verified = exact optimum' : 'not optimal → fallback tier'}, P(opt) {(browser.pOpt * 100).toFixed(3)}% ({browser.ms.toFixed(0)} ms)</div>}
          <ul className="small">{L.explanation.map((t, k) => <li key={k}>{t}</li>)}</ul>
        </div>
      </div>
    </div>
  )
}

export function Stress({ online, sandbox, scenario, onKill }: { online: boolean; sandbox: any; scenario: string; onKill: (z: string | null) => void }) {
  const [out, setOut] = useState<any>(null)
  const tests: Record<string, { params: any; offline: string }> = {
    'kill zone (heavy labs)': { params: { kill_zone: 'heavy_labs' }, offline: 'kill_heavy_labs' },
    'cloud burst (PV x0.3)': { params: { pv_scale: 0.3 }, offline: 'pv_0.5' },
    'BESCOM outage 3 h': { params: { outage_hours: 3 }, offline: 'outage_3' },
    'tariff spike (evening x2)': { params: { tariff_scale: 2 }, offline: 'tariff_spike' },
    'fest peak': { params: { scenario: 'fest' }, offline: 'fest' },
  }
  const go = async (name: string) => {
    const t = tests[name]
    if (name.startsWith('kill')) onKill('heavy_labs')
    if (online) {
      setOut({ name, busy: true })
      try { const r = await post<Record<string, any>>("/whatif", { scenario, ...t.params }); setOut({ name, ...r }) } catch (e) { setOut({ name, error: String(e) }) }
    } else setOut({ name, offline: true, ...(sandbox?.cases?.[t.offline] ?? { error: 'not precomputed' }) })
  }
  return (
    <div>
      <div className="row wrap">{Object.keys(tests).map(k => <button key={k} onClick={() => go(k)}>{k}</button>)}
        <button onClick={() => { onKill(null); setOut(null) }}>reset</button></div>
      {out && <div className="card small">
        <b>{out.name}</b> {out.busy ? 'running…' : ''} {out.offline ? '(precomputed what-if, offline)' : ''}
        {out.qgrid && <table className="kv"><tbody>
          <tr><th></th><th>status quo</th><th>Q-Grid (C-QIEA what-if)</th></tr>
          {['cost_rs', 'critical_downtime_h', 'dg_hours'].map(k => <tr key={k}><td>{k}</td><td>{fmt(out.status_quo[k], 2)}</td><td>{fmt(out.qgrid[k], 2)}</td></tr>)}
        </tbody></table>}
        {out.error && <div className="warn">{out.error}</div>}
        <div className="muted">{out.label ?? sandbox?.label}. Fallback tiers per solve are shown in the ADMM chapter.</div>
      </div>}
    </div>
  )
}

export function RuleBox({ online, rules }: { online: boolean; rules: any[] }) {
  const [text, setText] = useState('no DG during exams unless outage')
  const [res, setRes] = useState<any>(null)
  const submit = async () => {
    if (online) { try { setRes(await post('/rules/parse', { text })) } catch (e) { setRes({ error: String(e) }) } }
    else setRes({ results: rules.filter(r => r.text.toLowerCase() === text.trim().toLowerCase()), offline: true })
  }
  return (
    <div>
      <div className="row"><input value={text} onChange={e => setText(e.target.value)} aria-label="operator rule" style={{ flex: 1 }} />
        <button onClick={submit}>parse rule</button></div>
      {res && <div className="card small">
        {res.offline && <div className="muted">backend offline: showing precomputed parse of rules/*.txt (start the backend for new rules)</div>}
        {(res.results ?? []).map((r: any, k: number) => <div key={k}>
          <b className={r.ok ? 'okc' : 'warn'}>{r.ok ? 'ACCEPTED' : 'REJECTED'}</b> ({r.parser}) {r.reason}
          {r.rule && <pre>{JSON.stringify(r.rule, null, 1)}</pre>}</div>)}
        {res.effect && <div>effect (what-if): cost {fmt(res.effect.before.cost_rs)} → {fmt(res.effect.after.cost_rs)} Rs, DG h {res.effect.before.dg_hours} → {res.effect.after.dg_hours}</div>}
        {res.error && <div className="warn">{res.error}</div>}
        <div className="muted">The LLM (optional) only turns text into JSON constraints; it never produces schedules.</div>
      </div>}
    </div>
  )
}
