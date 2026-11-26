// The three live demo moments. Each one runs on the backend when it is reachable (one decision or one solve,
// under 5 s) and otherwise shows the precomputed result written by the same code (scripts/make_live.py -> live.json).
// Every result says which it is, how long it took, and that it is a what-if.
import { useEffect, useRef, useState } from 'react'
import { post, type QaoaResult, type RemoveResult, type RuleResult } from '../lib/data'
import { zn } from '../lib/labels'
import type { StoryData } from '../lib/story'
import { num } from '../lib/theme'

type Src = 'live' | 'precomputed'
type Call<T> = { busy: boolean; res: T | null; err: string | null; src: Src | null; ms: number | null }

function useCall<T>() {
  const [st, setSt] = useState<Call<T>>({ busy: false, res: null, err: null, src: null, ms: null })
  const run = async (online: boolean, live: () => Promise<T>, offline: () => T | null, missing: string) => {
    setSt(s => ({ ...s, busy: true, err: null }))
    const t0 = performance.now()
    if (online) {
      try { const r = await live(); setSt({ busy: false, res: r, err: null, src: 'live', ms: performance.now() - t0 }); return }
      catch { /* backend went away mid-demo: fall back to the precomputed answer below */ }
    }
    const r = offline()
    setSt({ busy: false, res: r, err: r ? null : missing, src: r ? 'precomputed' : null, ms: null })
  }
  const reset = () => setSt({ busy: false, res: null, err: null, src: null, ms: null })
  return { st, run, reset }
}

/** Keep a live card's result on screen (presenter mode on a 720p projector has little room). */
function useReveal(dep: unknown) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { if (dep) ref.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }) }, [dep])
  return ref
}

function SrcLine({ src, ms, compute }: { src: Src | null; ms: number | null; compute?: number }) {
  if (!src) return null
  return <p className="muted small livesrc">{src === 'live'
    ? <><span className="dotlive" aria-hidden="true" />Computed live on the backend in {((ms ?? 0) / 1000).toFixed(1)} s{compute !== undefined ? ` (solver ${compute.toFixed(1)} s)` : ''}.</>
    : <>Precomputed with the same code (<code>scripts/make_live.py</code>){compute !== undefined ? `; it took ${compute.toFixed(1)} s` : ''}. Start the backend to compute it live.</>}</p>
}

const kwh = (v: number) => `${v < 0.0005 ? '0' : v.toFixed(v < 1 ? 3 : 1)} kWh`

/** Step 5: take a building offline for one decision; its cables go dark and the others re-agree. */
export function RemoveBuilding({ d, online, killed, setKilled }: { d: StoryData; online: boolean; killed: string | null; setKilled: (z: string | null) => void }) {
  const { st, run, reset } = useCall<RemoveResult>()
  const zones = d.sc.campus.zones.map(z => z.name)
  const [zone, setZone] = useState(killed ?? 'heavy_labs')
  const go = (z: string) => {
    setZone(z); setKilled(z)
    run(online, () => post<RemoveResult>('/live/remove', { scenario: d.sc.scenario.key, zone: z, slot: d.qs?.slot ?? null }),
      () => d.live?.remove?.[z] ?? null, 'Precomputed result missing: replay/live.json (run python scripts/make_live.py).')
  }
  const r = st.res
  const k = r ? zones.indexOf(r.zone) : -1
  const ref = useReveal(r)
  return (
    <div className="card live" aria-live="polite" ref={ref}>
      <div className="row"><b>Live: remove a building</b>
        {!killed && <select className="scenpick" value={zone} onChange={e => setZone(e.target.value)} aria-label="building to take offline">{zones.map(z => <option key={z} value={z}>{zn(z)}</option>)}</select>}
        {killed ? <button className="btn small primary" onClick={() => { setKilled(null); reset() }}>Bring {zn(killed).toLowerCase()} back</button>
          : <button className="btn small ghost" onClick={() => go(zone)} disabled={st.busy}>{st.busy ? 'Re-planning…' : 'Take it offline'}</button>}
      </div>
      {st.err && <p className="small warn">{st.err}</p>}
      {r && killed && <>
        <ul className="liveres small">
          <li>Its {r.lines_dark.length} cable{r.lines_dark.length === 1 ? '' : 's'} go dark. The other {r.others.n} buildings re-agreed in <b className="tn">{r.after.admm_rounds}</b> trading rounds{r.after.converged ? '' : ' (not fully converged; settled pairwise)'} — with it: {r.before.admm_rounds}.</li>
          <li>Critical load unserved over the next 24 h, other buildings: <b className="tn">{kwh(r.others.crit_shed_after_kwh)}</b> (with it: {kwh(r.others.crit_shed_before_kwh)}).</li>
          {k >= 0 && <li>{zn(r.zone)} keeps running on its own controller: critical shortfall <b className="tn">{kwh(r.after.buildings[k].crit_shed_kwh)}</b>.</li>}
        </ul>
        <SrcLine src={st.src} ms={st.ms} compute={r.compute_s} />
        <p className="muted small">{r.label}. Decision at {r.time}{r.grid_up_now ? '' : ', grid down'}.</p>
      </>}
    </div>
  )
}

/** Step 4f: re-measure the worked example's QAOA block and check it against exact search. */
export function LiveQaoa({ d, online }: { d: StoryData; online: boolean }) {
  const { st, run } = useCall<QaoaResult>()
  const [k, setK] = useState(0)
  const go = () => {
    const pre = d.live?.qaoa ?? []
    run(online, () => post<QaoaResult>('/live/qaoa', { scenario: d.sc.scenario.key, seed: Date.now() % 1000000 }),
      () => { const r = pre[k % Math.max(pre.length, 1)] ?? null; setK(x => x + 1); return r }, 'Precomputed measurements missing: replay/live.json (run python scripts/make_live.py).')
  }
  const r = st.res
  const top = r ? r.qaoa.shots.slice(0, 5) : []
  const mx = Math.max(...top.map(s => s.count), 1)
  const ref = useReveal(r)
  return (
    <div className="card live" aria-live="polite" ref={ref}>
      <div className="row"><b>Live: solve a slot</b>
        <button className="btn small ghost" onClick={go} disabled={st.busy}>{st.busy ? 'Measuring…' : r ? 'Measure again (new seed)' : `Measure the ${d.example.n_qubits}-qubit block`}</button></div>
      {st.err && <p className="small warn">{st.err}</p>}
      {r && <>
        <div className="vrow"><span className="muted">QAOA's best of {r.shots_total} shots</span><code className="bits">{r.qaoa.best_bits}</code></div>
        <div className="vrow"><span className="muted">Exact search over {num(2 ** r.n_qubits)} settings</span><code className="bits">{r.exact.bits}</code></div>
        <div className="vrow"><span className="muted">Verdict</span><span className={`badge ${r.qaoa.matches_exact ? 'ok' : 'gap'}`}>{r.qaoa.matches_exact ? '✓ same cost as exact' : '≠ exact → exact plan used'}</span></div>
        <div className="vrow"><span className="muted">Shots on the optimum · time (simulator / exact)</span><span className="tn">{(100 * r.qaoa.p_opt).toFixed(1)} % · {(r.qaoa.time_s * 1000).toFixed(0)} / {(r.exact.time_s * 1000).toFixed(0)} ms</span></div>
        <div className="minihist" role="img" aria-label={`five most frequent results: ${top.map(s => `${s.bits} ${s.count} times`).join(', ')}`}>
          {top.map(s => <span key={s.bits} className={s.optimal ? 'opt' : ''}><i style={{ height: `${(s.count / mx) * 100}%` }} /><em className="tn">{s.count}</em></span>)}
        </div>
        <SrcLine src={st.src} ms={st.ms} />
        <p className="muted small">{r.backend}. {r.label}.</p>
      </>}
    </div>
  )
}

const PRESETS = ['no DG', 'keep hostel tanks above 90% by 6 am', 'EV charging only after 10 pm']
const rs0 = (v?: number) => (v === undefined ? '–' : `Rs ${Math.round(v).toLocaleString('en-IN')}`)

/** Step 6b: a faculty member types a rule; it is validated, then priced (best plan with vs without it). */
export function RuleCard({ d, online }: { d: StoryData; online: boolean }) {
  const { st, run } = useCall<RuleResult>()
  const presets = d.live?.rules?.map(r => r.text) ?? PRESETS
  const [text, setText] = useState(presets[0])
  const go = (t = text) => {
    setText(t)
    run(online, () => post<RuleResult>('/live/rule', { text: t, scenario: d.sc.scenario.key }),
      () => d.live?.rules?.find(r => r.text.trim().toLowerCase() === t.trim().toLowerCase()) ?? null,
      'Offline, only the three examples are precomputed. Start the backend to check any rule.')
  }
  const r = st.res
  const ok = r?.results.every(x => x.ok)
  const e = r?.effect
  const ref = useReveal(r)
  return (
    <div className="card live" aria-live="polite" ref={ref}>
      <b>Live: type a rule</b>
      <div className="chips sm" aria-label="example rules">{presets.map(t => <button key={t} className={`chip ${text === t ? 'on' : ''}`} onClick={() => go(t)}>{t}</button>)}</div>
      <form className="row" onSubmit={ev => { ev.preventDefault(); go() }}>
        <input type="text" value={text} onChange={ev => setText(ev.target.value)} aria-label="faculty rule" style={{ flex: 1 }} />
        <button className="btn small primary" type="submit" disabled={st.busy}>{st.busy ? 'Checking…' : 'Check rule'}</button>
      </form>
      {st.err && <p className="small warn">{st.err}</p>}
      {r && <>
        <div className="vrow"><span>{r.text}</span><span className={`badge ${ok ? 'ok' : 'gap'}`}>{ok ? '✓ accepted' : '✕ rejected'}</span></div>
        {r.results.map((x, i) => <p key={i} className="small">{x.ok ? <>Understood as <code>{x.rule ? Object.entries(x.rule).filter(([k2]) => k2 !== 'id').map(([k2, v]) => `${k2}=${Array.isArray(v) ? v.join('/') : v}`).join(', ') : ''}</code> ({x.parser}).</> : <>Reason: {x.reason}</>}</p>)}
        {e && e.before.status === 'Optimal' && (e.after.status === 'Optimal' ? <table className="kv small"><tbody>
          <tr><th /><th>without the rule</th><th>with the rule</th></tr>
          <tr><td>Energy + diesel cost</td><td className="tn">{rs0(e.before.cost_rs)}</td><td className="tn">{rs0(e.after.cost_rs)}</td></tr>
          <tr><td>Cost incl. value of lost load</td><td className="tn">{rs0(e.before.objective_rs)}</td><td className="tn">{rs0(e.after.objective_rs)}</td></tr>
          <tr><td>Diesel running</td><td className="tn">{e.before.dg_hours?.toFixed(1)} h</td><td className="tn">{e.after.dg_hours?.toFixed(1)} h</td></tr>
          <tr><td>Non-critical load shed</td><td className="tn">{kwh(e.before.shed_noncritical_kwh ?? 0)}</td><td className="tn">{kwh(e.after.shed_noncritical_kwh ?? 0)}</td></tr>
          <tr><td>Critical downtime</td><td className="tn">{e.before.critical_downtime_h?.toFixed(2)} h</td><td className="tn">{e.after.critical_downtime_h?.toFixed(2)} h</td></tr>
        </tbody></table> : <p className="small warn">With this rule there is no feasible plan ({e.after.status}); it would be refused.</p>)}
        <SrcLine src={st.src} ms={st.ms} compute={r.time_s} />
        {e && <p className="muted small">{e.label}. Day: {r.day} ({r.day_type}). Rules are parsed by templates; an optional language model only turns text into these fields and never makes schedules.</p>}
      </>}
    </div>
  )
}
