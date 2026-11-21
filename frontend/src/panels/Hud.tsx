import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { Area, ComposedChart, Line, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import type { Index, Scenario } from '../lib/data'
import { C, kw, pct, rs, signed } from '../lib/theme'
import type { Anchors } from '../scene/CampusScene'

export const ZONE_NAME: Record<string, string> = {
  academic: 'Academic blocks', heavy_labs: 'Mechanical labs', hostels: 'Hostels', library: 'Library', canteen: 'Food court',
  admin: 'Admin', server_room: 'Server room', health_centre: 'Health centre', pumping_station: 'Pump house',
}
export const zn = (z: string) => ZONE_NAME[z] ?? z

/* ------------------------------------------------------------------ zone labels (HTML, collision-avoided) */
export function LabelLayer({ sc, slot, anchors, focus, onZone, hidden }: {
  sc: Scenario; slot: number; anchors: React.MutableRefObject<Anchors>; focus: string | null; onZone: (z: string) => void; hidden?: boolean }) {
  const [snap, setSnap] = useState<Anchors | null>(null)
  useEffect(() => { const id = setInterval(() => setSnap({ ...anchors.current }), 120); return () => clearInterval(id) }, [anchors])
  if (!snap || hidden) return null
  const far = snap.dist > 760
  const items = sc.campus.zones.map((z, i) => ({ z: z.name, net: sc.runs.qgrid.net_kw[i][slot], a: snap.pts[z.name] }))
    .filter(it => it.a?.vis && (!far || it.z === focus))
    .sort((p, q) => (p.z === focus ? -1 : q.z === focus ? 1 : Math.abs(q.net) - Math.abs(p.net)))
  const placed: { x: number; y: number; w: number; h: number }[] = []
  const out: { it: typeof items[0]; x: number; y: number; w: number }[] = []
  for (const it of items) {
    const text = `${zn(it.z)} · ${signed(it.net)}`
    const w = text.length * 6.6 + 16, h = 24
    let y = it.a.y - 40, ok = false
    for (let k = 0; k < 5 && !ok; k++, y -= 28) {
      const r = { x: it.a.x - w / 2, y, w, h }
      ok = r.x > 4 && r.x + w < snap.w - 4 && y > 4 && !placed.some(p => r.x < p.x + p.w + 4 && r.x + r.w + 4 > p.x && r.y < p.y + p.h + 2 && r.y + r.h + 2 > p.y)
      if (ok) { placed.push(r); out.push({ it, x: r.x, y, w }) }
    }
  }
  return (
    <div className="labels" aria-hidden={false}>
      <svg className="leaders" width={snap.w} height={snap.h}>
        {out.map(o => <line key={o.it.z} x1={o.it.a.x} y1={o.it.a.y} x2={o.it.a.x} y2={o.y + 24} stroke={C.muted} strokeWidth={1} opacity={0.6} />)}
      </svg>
      {out.map(o => (
        <button key={o.it.z} className={`zl ${o.it.z === focus ? 'sel' : ''}`} style={{ left: o.x, top: o.y, width: o.w }} onClick={() => onZone(o.it.z)}>
          {zn(o.it.z)} <span className="tn" style={{ color: o.it.net > 0 ? C.grid : C.solar }}>· {signed(o.it.net)}</span>
        </button>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ Now card */
export function NowCard({ sc, slot }: { sc: Scenario; slot: number }) {
  const q = sc.runs.qgrid, s = sc.runs.status_quo
  const h0 = slot - (slot % 4)
  const thisHour = q.cum_cost_rs[slot] - (h0 > 0 ? q.cum_cost_rs[h0 - 1] : 0)
  const saved = s ? s.cum_cost_rs[slot] - q.cum_cost_rs[slot] : 0
  let crit = 0, miss = 0
  for (let z = 0; z < sc.slots.crit_kw.length; z++) for (let t = 0; t <= slot; t++) { crit += sc.slots.crit_kw[z][t]; miss += (q as any).crit_unserved_kw?.[z]?.[t] ?? 0 }
  const served = crit > 0 ? 100 * (1 - miss / crit) : 100
  const up = sc.slots.grid_up[slot] === 1
  return (
    <section className="now" aria-label="now">
      <header>
        <span className="tn big-time">{sc.slots.t[slot]}</span>
        <span className="muted">{scenarioName(sc.scenario.key)}, {fmtDate(sc.scenario.date)}{up ? '' : ' — grid down'}</span>
      </header>
      <div className="kpis">
        <div><span className="muted">Grid import</span><b className="tn">{up ? kw(q.grid_import_kw[slot]) : 'islanded'}</b></div>
        <div><span className="muted">Cost this hour</span><b className="tn">{rs(thisHour)}</b></div>
        <div><span className="muted">Saved vs status quo</span><b className="tn" style={{ color: saved >= 0 ? C.solar : C.grid }}>{rs(saved)}</b></div>
        <div><span className="muted">Critical load served</span><b className="tn" style={{ color: served >= 99.95 ? C.text : C.grid }}>{served >= 99.95 ? '100%' : `${served.toFixed(1)}%`}</b></div>
      </div>
    </section>
  )
}

export const scenarioName = (k: string) => ({ teaching: 'Teaching day', exam_week: 'Exam week', vacation: 'Vacation', fest: 'Fest day',
  monsoon: 'Monsoon day', outage_fest: 'Outage during fest' } as Record<string, string>)[k] ?? k
export const fmtDate = (d: string) => new Date(d + 'T00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

/* ------------------------------------------------------------------ decisions */
const REASON: Record<string, string> = {
  grid: 'grid price makes this the cheaper choice', battery_ctg: 'keeps battery energy for later today',
  water_value: 'stores water while energy is cheap', dg_fuel: 'diesel would cost more than it saves',
  flex_timing: 'best remaining time to run this load', admm: 'matches what neighbours agreed',
}
const reason = (g: string | null) => !g ? 'no cost difference' : g.startsWith('rule:') ? 'required by an operator rule' : REASON[g] ?? g

function action(sc: Scenario, i: number, t: number) {
  const r = sc.runs.qgrid, z = sc.campus.zones[i]
  if (z.dg_kw > 0 && r.dg_kw[i][t] > 0) return { label: 'Diesel on', icon: 'dg', color: C.offline }
  if (z.tank_m3 > 0) return r.pump_on[i][t] ? { label: 'Pump on', icon: 'pump', color: C.water } : { label: 'Pump off', icon: 'pump', color: C.muted }
  const p = r.p_bat[i][t]
  if (p > 1) return { label: 'Charge', icon: 'bat', color: C.battery }
  if (p < -1) return { label: 'Discharge', icon: 'bat', color: C.battery }
  return { label: 'Hold', icon: 'bat', color: C.muted }
}

function Icon({ k, color }: { k: string; color: string }) {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" aria-hidden>
      {k === 'bat' && <><rect x={2} y={4} width={11} height={8} rx={2} fill="none" stroke={color} strokeWidth={1.5} /><rect x={13} y={6.5} width={1.5} height={3} fill={color} /></>}
      {k === 'pump' && <><circle cx={8} cy={8} r={5} fill="none" stroke={color} strokeWidth={1.5} /><path d="M8 4v8M4 8h8" stroke={color} strokeWidth={1.2} /></>}
      {k === 'dg' && <><rect x={2} y={5} width={12} height={8} rx={1.5} fill="none" stroke={color} strokeWidth={1.5} /><path d="M5 5V3h3v2" stroke={color} strokeWidth={1.2} fill="none" /></>}
    </svg>
  )
}

export function Decisions({ sc, slot }: { sc: Scenario; slot: number }) {
  const [all, setAll] = useState(false)
  const [open, setOpen] = useState<string | null>(null)
  const hour = String(slot - (slot % 4))
  const dec = (sc as any).decisions?.[hour] ?? {}
  const rows = sc.campus.zones.map((z, i) => {
    const a = action(sc, i, slot), prev = slot > 0 ? action(sc, i, slot - 1).label : a.label
    const ds = (dec[z.name] ?? []) as { var: string; impact_rs: number; top_group: string | null; text: string }[]
    const top = ds.reduce((b: any, d) => (!b || Math.abs(d.impact_rs) > Math.abs(b.impact_rs) ? d : b), null)
    return { z: z.name, a, changed: prev !== a.label, top }
  })
  const ranked = [...rows].sort((p, q) => Math.abs(q.top?.impact_rs ?? 0) - Math.abs(p.top?.impact_rs ?? 0))
  const shown = all ? rows : rows.filter(r => r.changed).concat(ranked.filter(r => !r.changed).slice(0, Math.max(0, 3 - rows.filter(r => r.changed).length)))
  return (
    <section className="decisions" aria-label="decisions">
      <h3>Decisions at {sc.slots.t[slot]}</h3>
      <table>
        <tbody>
          {shown.map(r => (
            <Fragment key={r.z}>
              <tr className={open === r.z ? 'open' : ''} onClick={() => setOpen(open === r.z ? null : r.z)} tabIndex={0}>
                <td className="act"><Icon k={r.a.icon} color={r.a.color} /></td>
                <td className="main">
                  <div className="l1"><span>{zn(r.z)}</span><span className="muted">{r.a.label}</span>{r.changed ? <span className="dot" title="changed this slot" /> : null}</div>
                  <div className="why muted">{reason(r.top?.top_group ?? null)}</div>
                  {open === r.z && r.top && <div className="full muted">{r.top.text}</div>}
                </td>
                <td className="rsv tn">{r.top ? rs(Math.abs(r.top.impact_rs)) : '–'}</td>
              </tr>
            </Fragment>
          ))}
        </tbody>
      </table>
      <button className="link" onClick={() => setAll(a => !a)}>{all ? 'Show fewer' : `Show all ${rows.length} zones`}</button>
      <p className="muted small">Rs = cost avoided versus the opposite choice this hour (from the QUBO terms).</p>
    </section>
  )
}

/* ------------------------------------------------------------------ 24h chart */
export function DayChart({ sc, slot }: { sc: Scenario; slot: number }) {
  const data = useMemo(() => sc.slots.t.map((_, t) => ({
    t, price: sc.slots.price_import[t], pv: sc.slots.pv_kw.reduce((a, z) => a + z[t], 0), imp: sc.runs.qgrid.grid_import_kw[t],
  })), [sc])
  return (
    <section className="daychart" aria-label="24 hour chart">
      <h3>Today</h3>
      <div style={{ height: 112 }}>
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
            <XAxis dataKey="t" hide /><YAxis yAxisId="kw" hide /><YAxis yAxisId="rs" hide orientation="right" />
            <Area yAxisId="kw" dataKey="pv" stroke="none" fill={C.solar} fillOpacity={0.18} isAnimationActive={false} />
            <Line yAxisId="kw" dataKey="imp" stroke={C.grid} dot={false} strokeWidth={1.5} isAnimationActive={false} />
            <Line yAxisId="rs" dataKey="price" stroke={C.muted} dot={false} strokeWidth={1} strokeDasharray="3 3" isAnimationActive={false} type="stepAfter" />
            <ReferenceLine yAxisId="kw" x={slot} stroke={C.text} strokeWidth={1} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="keys small muted"><span><i style={{ background: C.solar }} />Solar</span><span><i style={{ background: C.grid }} />Grid import</span><span><i className="dash" />Import price</span></div>
    </section>
  )
}

/* ------------------------------------------------------------------ timeline */
export function Timeline({ sc, t, setT }: { sc: Scenario; t: number; setT: (v: number) => void }) {
  const W = 1000, H = 40
  const pv = sc.slots.pv_kw[0].map((_, i) => sc.slots.pv_kw.reduce((a, z) => a + z[i], 0))
  const pmax = Math.max(...pv, 1), cmax = Math.max(...sc.slots.price_import), cmin = Math.min(...sc.slots.price_import)
  const path = (v: number[], lo: number, hi: number) => v.map((x, i) => `${i ? 'L' : 'M'}${(i / 95) * W},${H - 4 - ((x - lo) / Math.max(hi - lo, 1e-9)) * (H - 8)}`).join('')
  const chips: { at: number; to: number; label: string; cls: string }[] = []
  const dt = sc.scenario.day_type
  if (dt === 'teaching' || dt === 'exam') chips.push({ at: 36, to: 68, label: dt === 'exam' ? 'Exams' : 'Classes', cls: 'solar' })
  if (dt === 'fest') chips.push({ at: 68, to: 90, label: 'Fest evening', cls: 'battery' })
  const o = sc.slots.grid_up.indexOf(0)
  if (o >= 0) chips.push({ at: o, to: sc.slots.grid_up.lastIndexOf(0) + 1, label: 'Outage', cls: 'grid' })
  const slot = Math.min(95, Math.floor(t))
  const rows: number[] = []   // two rows: a chip that overlaps an earlier one drops to the second row
  chips.forEach((c, i) => { rows[i] = chips.slice(0, i).some((d, j) => rows[j] === 0 && c.at < d.to && d.at < c.to) ? 1 : 0 })
  return (
    <div className="timeline">
      <div className="track">
        <div className="chips">{chips.map((c, i) => <span key={c.label} className={`chip ${c.cls}`} style={{ left: `${(c.at / 96) * 100}%`, width: `${((c.to - c.at) / 96) * 100}%`, top: rows[i] * 13 }}>{c.label}</span>)}</div>
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="spark" aria-hidden>
          <path d={path(pv, 0, pmax) + `L${W},${H}L0,${H}Z`} fill={C.solar} opacity={0.12} />
          <path d={path(sc.slots.price_import, cmin - 0.5, cmax + 0.5)} stroke={C.muted} strokeWidth={1} fill="none" strokeDasharray="4 3" vectorEffect="non-scaling-stroke" />
        </svg>
        <input type="range" min={0} max={95.99} step={0.25} value={t} onChange={e => setT(+e.target.value)} aria-label="time of day" />
        <div className="hours">{[0, 6, 12, 18, 24].map(h => <span key={h} style={{ left: `${(h / 24) * 100}%` }}>{String(h).padStart(2, '0')}:00</span>)}</div>
      </div>
      <div className="readout tn"><b>{sc.slots.t[slot]}</b><span className="muted">{sc.slots.grid_up[slot] ? 'Grid up' : 'Grid down'} · Rs {sc.slots.price_import[slot].toFixed(2)}/kWh</span></div>
    </div>
  )
}

/* ------------------------------------------------------------------ footer */
const SOURCE_LABEL: Record<string, string> = {
  nasa_power: 'NASA POWER irradiance', ausgrid_hostel_shape: 'Ausgrid household shapes (hostels)', osm_layout: 'OpenStreetMap layout',
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
      <button onClick={() => setOpen(o => !o)} aria-expanded={open}>Data: {st.length} sources · {pend} pending</button>
      {open && (
        <div className="pop" role="dialog" aria-label="data sources">
          <table><tbody>{st.map(([k, v]) => <tr key={k}><td>{SOURCE_LABEL[k] ?? k}</td><td className={v === 'REAL' ? 'okc' : 'pend'}>{v === 'REAL' ? 'Real' : v.charAt(0) + v.slice(1).toLowerCase()}</td></tr>)}</tbody></table>
          <p className="muted small">Pending items use labelled stand-ins and are never headline results. Map © OpenStreetMap contributors (ODbL).</p>
        </div>
      )}
    </div>
  )
}

export function Legend() {
  const items: [string, string][] = [['Solar / shared', C.solar], ['Grid import', C.grid], ['Battery', C.battery], ['Water', C.water],
    ['Quantum', C.quantum], ['Offline / diesel', C.offline]]
  return <div className="legend">{items.map(([l, c]) => <span key={l} className="lchip"><i style={{ background: c }} />{l}</span>)}</div>
}

export { pct }
