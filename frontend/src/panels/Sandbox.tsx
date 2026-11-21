import { useState } from 'react'
import { fmt, post } from '../lib/data'

const OAT: Record<string, number[]> = { battery_scale: [0, 0.5, 1, 1.5, 2], pv_scale: [0.5, 0.75, 1, 1.25, 1.5], outage_hours: [0, 1, 3, 5], dg_cost_scale: [1, 1.5, 2] }

/** What-if sandbox: live recompute via the backend (C-QIEA, <2 s) or nearest precomputed one-at-a-time case. */
export function Sandbox({ online, sandbox, scenario }: { online: boolean; sandbox: any; scenario: string }) {
  const [p, setP] = useState({ battery_scale: 1, pv_scale: 1, outage_hours: 3, dg_cost_scale: 1, price: 'A' })
  const [out, setOut] = useState<any>(null)
  const run = async () => {
    if (online) {
      setOut({ busy: true })
      try { setOut(await post('/whatif', { scenario, ...p })) } catch (e) { setOut({ error: String(e) }) }
      return
    }
    const base = { battery_scale: 1, pv_scale: 1, outage_hours: 3, dg_cost_scale: 1 } as any
    const changed = Object.keys(OAT).filter(k => (p as any)[k] !== base[k])
    const k = changed[0] ?? 'base'
    const near = k === 'base' ? 'base' : `${k}_${OAT[k].reduce((a, b) => Math.abs(b - (p as any)[k]) < Math.abs(a - (p as any)[k]) ? b : a)}`
    setOut({ ...(sandbox?.cases?.[near] ?? { error: 'not precomputed' }), offline: true, used: near,
      note: changed.length > 1 ? 'offline mode varies one factor at a time; start the backend for combined what-ifs' : '' })
  }
  return (
    <div className="sandbox">
      {Object.entries(OAT).map(([k, vals]) => (
        <label key={k} className="row">{k.replace(/_/g, ' ')}
          <input type="range" min={vals[0]} max={vals[vals.length - 1]} step={k === 'outage_hours' ? 0.5 : 0.05} value={(p as any)[k]}
            onChange={e => setP({ ...p, [k]: +e.target.value })} aria-label={k} />
          <span>{(p as any)[k]}</span></label>
      ))}
      <label className="row">tariff <select value={p.price} onChange={e => setP({ ...p, price: e.target.value })}><option>A</option><option>B</option></select></label>
      <button onClick={run}>{online ? 'recompute (backend)' : 'show nearest precomputed'}</button>
      {out && <div className="card small">
        <b className="warn">WHAT-IF — not a headline result</b> {out.busy ? 'running…' : ''} {out.offline ? `(offline: ${out.used})` : ''} {out.note}
        {out.qgrid && <table className="kv"><tbody><tr><th></th><th>status quo</th><th>Q-Grid (C-QIEA)</th></tr>
          {['cost_rs', 'critical_downtime_h', 'dg_hours', 'dg_litres', 'co2_kg'].map(k => <tr key={k}><td>{k}</td><td>{fmt(out.status_quo[k], 2)}</td><td>{fmt(out.qgrid[k], 2)}</td></tr>)}
        </tbody></table>}
        {out.time_s !== undefined && <div className="muted">recomputed in {out.time_s.toFixed(2)} s</div>}
        {out.error && <div className="warn">{out.error}</div>}
      </div>}
    </div>
  )
}
