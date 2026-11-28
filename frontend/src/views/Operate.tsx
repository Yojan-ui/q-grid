// Operate: the control room for RVCE estate staff. Live: the backend runs the stack as services and streams a snapshot
// every second. Offline: a recorded day from the same engine plays back with the same controls; actions that need the
// backend say so. Every screen labels where its numbers come from.
import { useMemo, useState } from 'react'
import { ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import type { StoryData } from '../lib/story'
import { useOperate, type OpReport, type OpSnapshot, type OpZone } from '../lib/operate'
import { zn } from '../lib/labels'
import { useC, type Palette } from '../lib/theme'
import { Sankey } from '../story/Sankey'
import { StatusBadge } from '../story/Badges'
import type { Zone } from '../lib/data'

const kw = (v: number) => `${Math.round(v).toLocaleString('en-IN')} kW`
const rs = (v: number) => `${v < 0 ? '−' : ''}Rs ${Math.abs(Math.round(v)).toLocaleString('en-IN')}`
const hh = (slot: number) => `${String(Math.floor(slot / 4) % 24).padStart(2, '0')}:${String((slot % 4) * 15).padStart(2, '0')}`
const stateColor = (C: Palette, s: OpZone['state']) => ({ import: C.sunken, export: C.okBg, balanced: C.plot, island: C.pendBg, shedding: C.gridLine }[s])
const stateText = { import: 'importing', export: 'exporting', balanced: 'balanced', island: 'islanded', shedding: 'shedding load' }

export function OperateView({ d, online }: { d: StoryData; online: boolean }) {
  const op = useOperate(online)
  const s = op.snap
  const [tab, setTab] = useState<'events' | 'messages' | 'devices' | 'override' | 'rules' | 'report'>('events')
  if (!s) return <main className="page op"><div className="loading" role="status"><span className="bar"><i /></span><span>{op.err ?? (online ? 'Connecting to the control room…' : 'Loading the recorded session…')}</span></div></main>
  return (
    <main className="op" aria-label="Operate: control room">
      <h1 className="op-title">{headline(s)}</h1>
      <OpHeader s={s} op={op} online={online} />
      <div className="op-grid">
        <section className="op-col">
          <CampusMap d={d} s={s} />
          <div className="bcards">{s.zones.map(z => <BuildingCard key={z.name} z={z} asset={d.sc.campus.zones.find(x => x.name === z.name)} />)}</div>
        </section>
        <section className="op-col">
          <Gantt s={s} />
          <PlanVsActual s={s} />
        </section>
        <section className="op-col op-side">
          <div className="seg op-tabs" role="tablist" aria-label="control room panels">
            {(['events', 'messages', 'devices', 'override', 'rules', 'report'] as const).map(k =>
              <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{k[0].toUpperCase() + k.slice(1)}</button>)}
          </div>
          <div className="op-panel">
            {tab === 'events' && <Events s={s} />}
            {tab === 'messages' && <Messages s={s} />}
            {tab === 'devices' && <Devices s={s} />}
            {tab === 'override' && <Override s={s} op={op} online={online} />}
            {tab === 'rules' && <Rules s={s} op={op} online={online} />}
            {tab === 'report' && <Report s={s} op={op} />}
          </div>
        </section>
      </div>
    </main>
  )
}

/** One plain sentence about the campus right now, read from the snapshot. */
function headline(s: OpSnapshot): string {
  const n = s.zones.length
  const c = (st: OpZone['state']) => s.zones.filter(z => z.state === st).length
  if (!s.grid_up_now) return c('shedding') ? `The grid is down: ${c('shedding')} of ${n} buildings are shedding some load, critical loads first.` : `The grid is down and all ${n} buildings are running on their own batteries and diesel.`
  const next = s.zones.map(z => ({ z, a: z.next_action })).find(x => !x.a.startsWith('No change') && x.a !== '—')
  const now = c('export') ? `${c('export')} of ${n} buildings are sending solar to the grid` : `${c('import')} of ${n} buildings are drawing from the grid`
  return `${now}${next ? `; next planned change: ${zn(next.z.name).toLowerCase()}, ${next.a.charAt(0).toLowerCase()}${next.a.slice(1)}` : '; no changes planned in the next three hours'}${s.comms_ok ? '.' : ', with the campus network down.'}`
}

function OpHeader({ s, op, online }: { s: OpSnapshot; op: ReturnType<typeof useOperate>; online: boolean }) {
  const sp = s.clock.speed
  return (
    <div className="op-head">
      <div className="op-clock"><b className="tn">{s.clock.time}</b><span className="muted small">{s.clock.date}</span></div>
      <div className="seg" role="radiogroup" aria-label="clock">
        {[[0, 'Pause'], [1, 'Live 1×'], [60, 'Fast-forward 60×']].map(([v, l]) =>
          <button key={v} role="radio" aria-checked={sp === v} className={sp === v ? 'on' : ''} onClick={() => op.setSpeed(v as number)}>{l}</button>)}
      </div>
      {!online && <input type="range" min={0} max={86399} step={300} value={s.clock.sim_s} onChange={e => op.seek(+e.target.value)} aria-label="seek in the recorded day" className="op-seek" />}
      {online && <select className="scenpick" value={s.source} onChange={e => op.setSource(e.target.value)} aria-label="data source">
        <option value="today">Today · live Open-Meteo forecast</option><option value="historical">Historical day · real NASA POWER solar</option></select>}
      <span className={`pill ${s.grid_up_now ? 'ok' : 'alarm'}`}>{s.grid_up_now ? 'Grid up' : 'Grid down'}</span>
      <span className={`pill ${s.comms_ok ? 'ok' : 'warn'}`}>{s.comms_ok ? 'Links up' : 'Links down'}</span>
      <span className={`pill ${s.hardware?.zones_live.length ? 'ok' : ''}`} title={s.hardware?.error ?? ''}>{s.hardware?.zones_live.length ? `${s.hardware.zones_live.length} LIVE HARDWARE` : 'Hardware: simulated'}</span>
      <div className="op-labels small muted">
        <span className="pill src">{online ? (s.source === 'today' ? s.forecast?.label ?? 'Live forecast' : 'Historical day') : `Recorded session (offline) · ${op.recordedAt ?? ''}`}</span>
        {Object.entries(s.labels).map(([k, v]) => <span key={k} title={v}>{k}: {v.split(' — ')[0].split(';')[0]}</span>)}
      </div>
    </div>
  )
}

function CampusMap({ d, s }: { d: StoryData; s: OpSnapshot }) {
  const C = useC()
  const zs = d.sc.campus.zones
  const pts = zs.flatMap(z => z.buildings.flatMap(b => b.polygon))
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1])
  const [minx, maxx, miny, maxy] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)]
  const W = 420, H = 260, k = Math.min(W / (maxx - minx), H / (maxy - miny)) * 0.92
  const X = (x: number) => (x - minx) * k + (W - (maxx - minx) * k) / 2, Y = (y: number) => H - ((y - miny) * k + (H - (maxy - miny) * k) / 2)
  const byName = Object.fromEntries(s.zones.map(z => [z.name, z]))
  const pos = Object.fromEntries(zs.map(z => [z.name, [X(z.cx), Y(z.cy)]]))
  const agreed = (l: number) => { const c = s.admm?.cables?.[l]?.proposals; return c ? Math.abs(c[0] - c[1]) < 1 : true }
  return (
    <div className="card op-map">
      <div className="op-cardhead"><b>Campus</b><span className="muted small">zones coloured by state · cables: blue agreed, red still negotiating</span></div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`Campus map: ${s.zones.map(z => `${zn(z.name)} ${stateText[z.state]}`).join(', ')}`}>
        {s.lines.map(([a, b], l) => pos[a] && pos[b] && <line key={l} x1={pos[a][0]} y1={pos[a][1]} x2={pos[b][0]} y2={pos[b][1]} stroke={!s.comms_ok ? C.faint : agreed(l) ? C.accent : C.grid} strokeWidth={2} strokeDasharray={s.comms_ok ? undefined : '4 3'} />)}
        {zs.map(z => <g key={z.name}>
          {z.buildings.map((b, i) => <polygon key={i} points={b.polygon.map(p => `${X(p[0])},${Y(p[1])}`).join(' ')} fill={stateColor(C, byName[z.name]?.state ?? 'balanced')} stroke={C.hair} strokeWidth={0.6} />)}
        </g>)}
        {zs.map(z => <text key={z.name} x={X(z.cx)} y={Y(z.cy)} fontSize={9.5} textAnchor="middle" fill={C.text} style={{ paintOrder: 'stroke', stroke: C.surface, strokeWidth: 3 }}>{zn(z.name)}</text>)}
      </svg>
      <div className="legend-row small">{(['import', 'export', 'balanced', 'island', 'shedding'] as const).map(k => <span key={k}><i style={{ background: stateColor(C, k), border: `1px solid ${C.hair}` }} />{stateText[k]}</span>)}</div>
    </div>
  )
}

const ASSET_NAME: Record<string, string> = { pv: 'solar', battery: 'battery', dg: 'diesel set', ev: 'EV chargers' }
function BuildingCard({ z, asset }: { z: OpZone; asset?: Zone }) {
  // assets the replay marks as not on campus today (campus.zones[i].asset_status); nothing when the field is absent
  const prop = Object.entries(asset?.asset_status ?? {}).filter(([, v]) => v === 'PROPOSED').map(([k]) => ASSET_NAME[k] ?? k)
  return (
    <div className={`bcard st-${z.state}`}>
      <div className="bc-top"><b>{zn(z.name)}</b>{z.source === 'hardware' ? <span className="hwbadge">LIVE HARDWARE</span> : <span className="simbadge">simulated</span>}</div>
      <div className="bc-row tn"><span>Solar <b>{kw(z.pv_kw)}</b></span><span>Load <b>{kw(z.load_kw)}</b></span></div>
      {z.has.battery && <div className="bc-bat" title={`battery ${Math.round(100 * (z.soc ?? 0))}%, ${z.battery_kw > 1 ? `charging ${kw(z.battery_kw)}` : z.battery_kw < -1 ? `discharging ${kw(-z.battery_kw)}` : 'idle'}`}><i style={{ width: `${Math.round(100 * (z.soc ?? 0))}%` }} /><span className="tn">battery {Math.round(100 * (z.soc ?? 0))}% · {z.battery_kw > 1 ? 'charging' : z.battery_kw < -1 ? 'discharging' : 'idle'}</span></div>}
      <div className="bc-row small"><span>{stateText[z.state]}</span>{z.dg_kw > 0 && <span className="warn">diesel on</span>}{z.pump && <span>pump on</span>}</div>
      {prop.length > 0 && <div className="bc-prop small"><StatusBadge s="PROPOSED" what={zn(z.name)} /><span className="muted">{prop.join(', ')}</span></div>}
      <div className="bc-next small"><b>{z.next_action}</b><span className="muted"> — {z.reason}</span></div>
    </div>
  )
}

function Gantt({ s }: { s: OpSnapshot }) {
  const C = useC()
  const p = s.plan
  if (!p) return <div className="card"><b>24 h plan</b><p className="muted small">Waiting for the first plan…</p></div>
  const rows: { label: string; cells: (string | null)[]; title: (k: number) => string }[] = []
  s.zones.forEach((z, i) => {
    const pz = p.zones[i]
    if (z.has.battery) rows.push({ label: `${zn(z.name)} · battery`, cells: pz.battery_kw.map(v => (v > 1 ? C.solar : v < -1 ? C.battery : null)), title: k => `${pz.battery_kw[k] > 0 ? 'charge' : 'discharge'} ${Math.abs(pz.battery_kw[k]).toFixed(0)} kW` })
    if (z.has.diesel) rows.push({ label: `${zn(z.name)} · diesel`, cells: pz.dg_kw.map(v => (v > 1e-6 ? C.diesel : null)), title: k => `diesel ${pz.dg_kw[k].toFixed(0)} kW` })
    if (z.has.pump) rows.push({ label: `${zn(z.name)} · pump`, cells: pz.pump.map(v => (v ? C.water : null)), title: () => 'pump on' })
  })
  const H = p.zones[0]?.battery_kw.length ?? 96
  const W = 560, lw = 150, rh = 13, cw = (W - lw) / H
  const now = (s.clock.sim_s / 900 - p.t0) * cw + lw
  return (
    <div className="card op-gantt">
      <div className="op-cardhead"><b>24 h plan per device</b><span className="muted small">made at {p.made_at} ({p.reason}, {p.time_s.toFixed(1)} s)</span></div>
      <svg viewBox={`0 0 ${W} ${rows.length * rh + 22}`} width="100%" role="img" aria-label={`Plan from ${hh(p.t0)} for the next 24 hours, ${rows.length} device rows`}>
        {Array.from({ length: 7 }, (_, j) => j * 16).map(k => <g key={k}>
          <line x1={lw + k * cw} x2={lw + k * cw} y1={0} y2={rows.length * rh} stroke={C.hair} />
          <text x={lw + k * cw} y={rows.length * rh + 14} fontSize={10} fill={C.muted} textAnchor="middle">{hh(p.t0 + k)}</text></g>)}
        {rows.map((r, y) => <g key={r.label}>
          <text x={lw - 6} y={y * rh + 10} fontSize={10} fill={C.text} textAnchor="end">{r.label}</text>
          {r.cells.map((c, k) => c && <rect key={k} x={lw + k * cw} y={y * rh + 2} width={cw + 0.3} height={rh - 4} fill={c} rx={1}><title>{`${r.label} ${hh(p.t0 + k)}: ${r.title(k)}`}</title></rect>)}
        </g>)}
        <line x1={now} x2={now} y1={0} y2={rows.length * rh} stroke={C.accent} strokeWidth={1.5} />
      </svg>
      <div className="legend-row small"><span><i style={{ background: C.solar }} />battery charging</span><span><i style={{ background: C.battery }} />discharging</span><span><i style={{ background: C.diesel }} />diesel</span><span><i style={{ background: C.water }} />pump</span><span><i style={{ background: C.accent, height: 2 }} />now</span></div>
    </div>
  )
}

function PlanVsActual({ s }: { s: OpSnapshot }) {
  const C = useC()
  const p = s.plan
  const data = useMemo(() => Array.from({ length: 96 }, (_, i) => {
    const k = p ? i - p.t0 : -1
    return { i, pva: s.series.pv_actual[i] ?? null, pvp: p && k >= 0 && k < p.pv_forecast.length ? p.pv_forecast[k] : null,
      ima: s.series.import_actual[i] ?? null, imp: p && k >= 0 && k < p.import_plan.length ? p.import_plan[k] : null }
  }).map(r => ({ ...r, pva: (s.series.minutes[r.i] ?? 0) > 0 ? r.pva : null, ima: (s.series.minutes[r.i] ?? 0) > 0 ? r.ima : null })), [s, p])
  const down = s.series.grid_up.map((g, i) => (g ? -1 : i)).filter(i => i >= 0)
  const axis = { stroke: C.muted, fontSize: 11, tickLine: false, axisLine: false } as const
  return (
    <div className="card">
      <div className="op-cardhead"><b>Plan vs actual (campus)</b><span className="muted small">solar and grid import, kW</span></div>
      <div style={{ height: 180 }} role="img" aria-label="Campus solar and grid import: planned (dashed) against actual (solid) through the day">
        <ResponsiveContainer><ComposedChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: 0 }} accessibilityLayer={false}>
          <XAxis dataKey="i" type="number" domain={[0, 96]} ticks={[0, 24, 48, 72, 96]} tickFormatter={v => hh(v)} {...axis} />
          <YAxis {...axis} width={44} tickFormatter={v => `${Math.round(v)}`} />
          {down.length > 0 && <ReferenceArea x1={down[0]} x2={down[down.length - 1] + 1} fill={C.gridSoft} />}
          <Line dataKey="pvp" stroke={C.solar} strokeDasharray="4 3" dot={false} isAnimationActive={false} strokeWidth={1.4} />
          <Line dataKey="pva" stroke={C.solar} dot={false} isAnimationActive={false} strokeWidth={2} />
          <Line dataKey="imp" stroke={C.grid} strokeDasharray="4 3" dot={false} isAnimationActive={false} strokeWidth={1.4} />
          <Line dataKey="ima" stroke={C.grid} dot={false} isAnimationActive={false} strokeWidth={2} />
          <ReferenceLine x={s.clock.sim_s / 900} stroke={C.accent} />
        </ComposedChart></ResponsiveContainer>
      </div>
      <div className="legend-row small"><span><i style={{ background: C.solar }} />solar actual</span><span><i className="dash" style={{ background: `repeating-linear-gradient(90deg, ${C.solar} 0 3px, transparent 3px 6px)` }} />solar plan</span>
        <span><i style={{ background: C.grid }} />grid import actual</span><span><i className="dash" style={{ background: `repeating-linear-gradient(90deg, ${C.grid} 0 3px, transparent 3px 6px)` }} />import plan</span>{down.length > 0 && <span><i style={{ background: C.gridSoft }} />grid down</span>}</div>
    </div>
  )
}

function Events({ s }: { s: OpSnapshot }) {
  const [plans, setPlans] = useState(false)
  const ev = [...s.events].reverse().filter(e => plans || e.kind !== 'plan')
  return <><label className="small muted evfilter"><input type="checkbox" checked={plans} onChange={e => setPlans(e.target.checked)} /> show every 15-minute plan update</label>
    <ul className="evlist" aria-live="polite">{ev.length ? ev.map((e, i) => <li key={i} className={`ev ${e.sev}`}><span className="tn muted">{e.time}</span><span className={`evk ${e.kind}`}>{e.kind}</span><span>{e.text}</span></li>) : <li className="muted small">No events yet.</li>}</ul></>
}

function Messages({ s }: { s: OpSnapshot }) {
  const C = useC()
  const a = s.admm
  if (!a) return <p className="muted small">No coordination round yet.</p>
  const mx = Math.max(...a.residuals, 1)
  return (
    <div>
      <p className="small"><b>{a.isolated ? 'Links down: each building planned alone.' : `Neighbours agreed in ${a.rounds} rounds`}</b>{!a.isolated && <> · {a.converged ? 'converged' : 'settled pairwise'} · {a.messages.toLocaleString('en-IN')} messages · {a.time_s.toFixed(1)} s (plan at {a.made_at})</>}</p>
      {a.residuals.length > 1 && <svg viewBox="0 0 300 60" width="100%" role="img" aria-label={`Largest cable disagreement fell from ${a.residuals[0]} to ${a.residuals[a.residuals.length - 1]} kW`}>
        <polyline fill="none" stroke={C.grid} strokeWidth={1.5} points={a.residuals.map((r, i) => `${(i / (a.residuals.length - 1)) * 296 + 2},${56 - (r / mx) * 52}`).join(' ')} /></svg>}
      <table className="tbl small"><thead><tr><th>Cable</th><th>end A proposes</th><th>end B proposes</th><th>status</th></tr></thead>
        <tbody>{a.cables.map(c => <tr key={c.line}><td>{zn(c.a)} ↔ {zn(c.b)}</td><td className="tn">{c.proposals ? `${c.proposals[0].toFixed(0)} kW` : '–'}</td><td className="tn">{c.proposals ? `${c.proposals[1].toFixed(0)} kW` : '–'}</td>
          <td>{!c.proposals ? '–' : Math.abs(c.proposals[0] - c.proposals[1]) < 1 ? <span className="okc">agreed</span> : <span className="warn">negotiating</span>}</td></tr>)}</tbody></table>
      <p className="muted small">Messages go only between neighbouring buildings (consensus ADMM on each cable's flow). No central computer.</p>
    </div>
  )
}

function Devices({ s }: { s: OpSnapshot }) {
  return (
    <div>
      <p className="small">{s.hardware ? (s.hardware.broker_connected ? 'MQTT broker connected.' : `MQTT broker not reachable${s.hardware.error ? ` (${s.hardware.error})` : ''} — every building is simulated.`) : 'Recorded session: every building simulated.'}</p>
      <table className="tbl small"><thead><tr><th>Building</th><th>Source</th><th>Online</th><th>Latency</th><th>Last reading</th></tr></thead>
        <tbody>{(s.devices ?? s.zones.map(z => ({ zone: z.name, source: z.source, online: true, latency_ms: null, last_reading: `${s.clock.time} (recorded)`, rssi: null }))).map(dv =>
          <tr key={dv.zone}><td>{zn(dv.zone)}</td><td>{dv.source === 'hardware' ? <span className="hwbadge">LIVE HARDWARE</span> : 'simulated'}</td><td>{dv.online ? 'yes' : <span className="warn">no</span>}</td>
            <td className="tn">{dv.latency_ms !== null ? `${dv.latency_ms} ms` : '–'}</td><td className="tn">{dv.last_reading}</td></tr>)}</tbody></table>
      <p className="muted small">An ESP32 node publishing on <code>qgrid/&lt;zone&gt;/telemetry</code> replaces that building's simulated readings while it is online (docs/hardware.md).</p>
    </div>
  )
}

function Override({ s, op, online }: { s: OpSnapshot; op: ReturnType<typeof useOperate>; online: boolean }) {
  const [f, setF] = useState({ zone: 'server_room', device: 'battery', state: 'hold', minutes: 30 })
  const [confirm, setConfirm] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)
  const z = s.zones.find(x => x.name === f.zone)
  const devs = (['battery', 'diesel', 'pump'] as const).filter(dv => z?.has[dv])
  const states = f.device === 'battery' ? ['hold'] : ['on', 'off']
  return (
    <div>
      <b className="small">Manual override</b>
      <div className="ovform">
        <select value={f.zone} onChange={e => { const nz = s.zones.find(x => x.name === e.target.value)!; const dv = (['battery', 'diesel', 'pump'] as const).find(k => nz.has[k]) ?? 'battery'; setF({ ...f, zone: e.target.value, device: dv, state: dv === 'battery' ? 'hold' : 'on' }) }} aria-label="building">{s.zones.map(x => <option key={x.name} value={x.name}>{zn(x.name)}</option>)}</select>
        <select value={f.device} onChange={e => setF({ ...f, device: e.target.value, state: e.target.value === 'battery' ? 'hold' : 'on' })} aria-label="device">{devs.map(dv => <option key={dv}>{dv}</option>)}</select>
        <select value={f.state} onChange={e => setF({ ...f, state: e.target.value })} aria-label="state">{states.map(x => <option key={x}>{x}</option>)}</select>
        <select value={f.minutes} onChange={e => setF({ ...f, minutes: +e.target.value })} aria-label="duration">{[15, 30, 60, 120].map(m => <option key={m} value={m}>{m} min</option>)}</select>
        <button className="btn small primary" disabled={!online} title={online ? '' : 'Needs the live backend'} onClick={() => setConfirm(true)}>Apply…</button>
      </div>
      {confirm && <div className="confirm" role="alertdialog" aria-label="confirm override">
        <p className="small">Force <b>{zn(f.zone)} {f.device} {f.state}</b> for {f.minutes} min? The safety layer still applies (battery limits, diesel minimum run, tank levels) and the action is written to the audit trail.</p>
        <div className="row"><button className="btn small primary" onClick={async () => { setConfirm(false); try { await op.override(f); setMsg('Override applied and logged.') } catch (e) { setMsg(String(e)) } }}>Confirm</button><button className="btn small ghost" onClick={() => setConfirm(false)}>Cancel</button></div></div>}
      {msg && <p className="small">{msg}</p>}
      <b className="small">Simulate an event</b>
      <div className="row"><button className="btn small ghost" disabled={!online} onClick={() => op.inject('outage', 60)}>BESCOM outage, 60 min</button><button className="btn small ghost" disabled={!online} onClick={() => op.inject('comms_loss', 45)}>Network loss, 45 min</button></div>
      {!online && <p className="muted small">Recorded session: overrides and events need the live backend (make backend). The recording contains scripted ones.</p>}
      {s.overrides.length > 0 && <><b className="small">Active overrides</b><ul className="small">{s.overrides.map(o => <li key={o.id}>{zn(o.zone)} {o.device} {o.state} ({o.who}) {online && <button className="btn small ghost" onClick={() => op.clearOverride(o.id)}>clear</button>}</li>)}</ul></>}
      <b className="small">Audit trail</b>
      <ul className="evlist">{[...s.audit].reverse().map((a, i) => <li key={i} className="ev"><span className="tn muted">{a.sim}</span><span className="evk">{a.who}</span><span>{a.action}: {a.detail}</span></li>)}</ul>
    </div>
  )
}

function Rules({ s, op, online }: { s: OpSnapshot; op: ReturnType<typeof useOperate>; online: boolean }) {
  const [text, setText] = useState('keep hostel tanks above 90% by 6 am')
  const [res, setRes] = useState<any>(null)
  return (
    <div>
      <b className="small">Faculty and estate rules, in plain English</b>
      <form className="row" onSubmit={async e => { e.preventDefault(); try { setRes(await op.rule(text)) } catch (er) { setRes({ error: String(er) }) } }}>
        <input type="text" value={text} onChange={e => setText(e.target.value)} aria-label="rule" style={{ flex: 1 }} />
        <button className="btn small primary" type="submit" disabled={!online} title={online ? '' : 'Needs the live backend'}>Add rule</button></form>
      <div className="chips sm">{['no DG unless outage', 'keep hostel tanks above 90% by 6 am', 'EV charging only after 10 pm'].map(t => <button key={t} className="chip" onClick={() => setText(t)}>{t}</button>)}</div>
      {res?.results && <p className="small">{res.results.every((x: any) => x.ok) ? <span className="okc">Accepted — active from the next plan.</span> : <span className="warn">Refused: {res.results.filter((x: any) => !x.ok).map((x: any) => x.reason).join('; ')}</span>}</p>}
      {res?.error && <p className="small warn">{res.error}</p>}
      <b className="small">Active rules</b>
      <ul className="small">{s.rules.length ? s.rules.map(r => <li key={r}>{r}</li>) : <li className="muted">none</li>}</ul>
      <p className="muted small">Each rule is parsed into a precise constraint and validated against the campus; impossible rules are refused with a reason.</p>
    </div>
  )
}

function Report({ s, op }: { s: OpSnapshot; op: ReturnType<typeof useOperate> }) {
  const [r, setR] = useState<OpReport | null>(null)
  const [busy, setBusy] = useState(false)
  const get = async () => { setBusy(true); try { setR(await op.report()) } finally { setBusy(false) } }
  const rep = r ?? s.reports[s.reports.length - 1] ?? null
  return (
    <div className="opreport">
      <div className="row"><button className="btn small primary" onClick={get} disabled={busy}>{busy ? 'Settling…' : s.clock.day_over ? 'Daily report' : 'Report for the day so far'}</button>
        {rep && <button className="btn small ghost" onClick={() => { document.documentElement.setAttribute('data-print', 'opreport'); window.print(); setTimeout(() => document.documentElement.removeAttribute('data-print'), 500) }}>Export PDF</button>}</div>
      {rep && rep.slots > 0 && <ReportBody r={rep} />}
      {rep && <div className="opreport-doc"><h1>Q-Grid daily report · {rep.date}</h1><ReportBody r={rep} /></div>}
    </div>
  )
}

function ReportBody({ r }: { r: OpReport }) {
  const rows: [string, string, (v: number) => string][] = [['Bill (energy + demand charge)', 'cost_incl_demand_rs', rs], ['Cost incl. value of lost load', 'objective_rs', rs], ['Critical downtime', 'critical_downtime_h', v => `${v.toFixed(2)} h`],
    ['Load left unserved', 'unserved_kwh', v => `${Math.round(v).toLocaleString('en-IN')} kWh`],
    ['Diesel', 'dg_litres', v => `${v.toFixed(0)} L`], ['CO₂', 'co2_kg', v => `${Math.round(v).toLocaleString('en-IN')} kg`], ['Grid import', 'import_kwh', v => `${Math.round(v).toLocaleString('en-IN')} kWh`], ['Battery wear', 'wear_rs', rs]]
  return (
    <>
      <p className="small">Against the status quo on the same solar, loads and outages{r.final ? '' : ' (day so far)'}: bill <b>{r.saving_rs >= 0 ? `${rs(r.saving_rs)} lower` : `${rs(-r.saving_rs)} higher`}</b> (HT-2(c)(ii), KERC 2023 tariff);
        critical downtime <b className="tn">{(r.status_quo.critical_downtime_h ?? 0).toFixed(2)} h → {(r.qgrid.critical_downtime_h ?? 0).toFixed(2)} h</b>;
        load left unserved <b className="tn">{Math.round(r.status_quo.unserved_kwh ?? 0).toLocaleString('en-IN')} → {Math.round(r.qgrid.unserved_kwh ?? 0).toLocaleString('en-IN')} kWh</b>.
        {r.saving_rs < 0 && (r.qgrid.dg_litres ?? 0) > (r.status_quo.dg_litres ?? 0) ? ' The higher bill is diesel burned to keep loads on.' : ''}</p>
      <table className="tbl small"><thead><tr><th /><th>Status quo</th><th>Q-Grid</th></tr></thead>
        <tbody>{rows.map(([l, k, f]) => <tr key={k}><td>{l}</td><td className="tn">{r.status_quo[k] !== undefined ? f(r.status_quo[k]) : '–'}</td><td className="tn">{r.qgrid[k] !== undefined ? f(r.qgrid[k]) : '–'}</td></tr>)}</tbody></table>
      {r.flows && <Sankey flows={r.flows} height={300} title="Energy flows, Q-Grid as operated" />}
      <p className="muted small">{r.note} Solar: {r.labels?.solar} Loads: {r.labels?.loads}</p>
    </>
  )
}
