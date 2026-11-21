// Light, quiet charts synced to the story's clock. Data straight from the replay.
import { useEffect, useMemo, useRef, useState } from 'react'
import { animate, motion } from 'framer-motion'
import { Area, ComposedChart, Line, ReferenceArea, ReferenceDot, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import type { Scenario } from '../lib/data'
import { C, reducedMotion } from '../lib/theme'
import { campusSoc, sumZones } from '../lib/story'

const hourTicks = [0, 24, 48, 72, 96]
const hourFmt = (v: number) => `${String(Math.round(v / 4)).padStart(2, '0')}:00`
const axis = { stroke: C.faint, fontSize: 11, tickLine: false, axisLine: false } as const

export function outageSpan(sc: Scenario): [number, number] | null {
  const a = sc.slots.grid_up.indexOf(0)
  return a < 0 ? null : [a, sc.slots.grid_up.lastIndexOf(0) + 1]
}

/** Step 1: solar, load and price through the status-quo day, with the two loss areas shaded. */
export function DayChart({ sc, t }: { sc: Scenario; t: number }) {
  const r = sc.runs.status_quo ?? sc.runs.qgrid
  const pmax = Math.max(...sc.slots.price_import)
  const data = useMemo(() => sc.slots.t.map((_, i) => ({
    i, solar: sumZones(sc.slots.pv_kw, i), load: sumZones(sc.slots.load_kw, i), price: sc.slots.price_import[i],
    sold: r.grid_export_kw[i] > 0.5 ? r.grid_export_kw[i] : null,
    bought: sc.slots.price_import[i] >= pmax && r.grid_import_kw[i] > 0.5 ? r.grid_import_kw[i] : null,
  })), [sc])
  const out = outageSpan(sc)
  return (
    <figure className="chart">
      <div style={{ height: 150 }}>
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 6, right: 4, bottom: 0, left: 0 }}>
            <XAxis dataKey="i" type="number" domain={[0, 96]} ticks={hourTicks} tickFormatter={hourFmt} {...axis} />
            <YAxis yAxisId="kw" {...axis} tickFormatter={v => `${Math.round(v / 100) / 10}k`} width={40} />
            <YAxis yAxisId="rs" orientation="right" domain={[0, Math.ceil(pmax + 1)]} {...axis} width={28} />
            {out && <ReferenceArea yAxisId="kw" x1={out[0]} x2={out[1]} fill={C.hair} fillOpacity={0.8} />}
            <Area yAxisId="kw" dataKey="solar" stroke="none" fill={C.solar} fillOpacity={0.12} isAnimationActive={false} />
            <Area yAxisId="kw" dataKey="sold" stroke={C.solar} strokeWidth={1} fill={C.solar} fillOpacity={0.45} isAnimationActive={false} connectNulls={false} />
            <Area yAxisId="kw" dataKey="bought" stroke={C.grid} strokeWidth={1} fill={C.grid} fillOpacity={0.4} isAnimationActive={false} connectNulls={false} />
            <Line yAxisId="kw" dataKey="load" stroke={C.text} strokeWidth={1.4} dot={false} isAnimationActive={false} />
            <Line yAxisId="rs" dataKey="price" stroke={C.muted} strokeWidth={1} strokeDasharray="3 3" dot={false} type="stepAfter" isAnimationActive={false} />
            <ReferenceLine yAxisId="kw" x={t} stroke={C.accent} strokeWidth={1.2} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="keys">
        <span><i style={{ background: C.solar, opacity: 0.35 }} />Solar</span><span><i style={{ background: C.text }} />Campus load</span>
        <span><i style={{ background: C.solar }} />Sold to grid</span><span><i style={{ background: C.grid }} />Bought at peak price</span>
        <span><i className="dash" />Price (Rs/kWh, right)</span>{out && <span><i style={{ background: C.hair }} />Outage</span>}
      </figcaption>
    </figure>
  )
}

/** Step 6: campus state of charge, status quo vs Q-Grid, with data-checked annotations. */
export function SocChart({ sc, t }: { sc: Scenario; t: number }) {
  const qg = campusSoc(sc, 'qgrid'), sq = campusSoc(sc, 'status_quo')
  const data = qg.map((v, i) => ({ i, qg: 100 * v, sq: sq.length ? 100 * sq[i] : null }))
  const out = outageSpan(sc)
  const notes: { x: number; y: number; text: string }[] = []
  // each note is shown only if the replay data shows it
  if (qg[68] - qg[44] > 0.1) notes.push({ x: 56, y: 100 * qg[56], text: 'Charged through the afternoon while solar was strong' })
  if (out) {
    const before = out[0], after = out[1]
    if (qg[before] > (sq[before] ?? 0) + 0.05) notes.push({ x: before, y: 100 * qg[before], text: `${Math.round(100 * qg[before])}% full as the outage starts (status quo ${Math.round(100 * (sq[before] ?? 0))}%)` })
    if (qg[after] < qg[before] - 0.1) notes.push({ x: after, y: 100 * qg[after], text: `Drawn down to ${Math.round(100 * qg[after])}% while the grid was down` })
  }
  const dg = (run: 'qgrid' | 'status_quo') => sc.runs[run]?.dg_kw ? sc.slots.t.map((_, i) => sumZones(sc.runs[run]!.dg_kw, i) > 0) : []
  const tankZ = sc.campus.zones.find(z => z.tank_m3 > 0)
  return (
    <figure className="chart">
      <div style={{ height: 160 }}>
        <ResponsiveContainer>
          <ComposedChart data={data} margin={{ top: 14, right: 8, bottom: 0, left: 0 }}>
            <XAxis dataKey="i" type="number" domain={[0, 96]} ticks={hourTicks} tickFormatter={hourFmt} {...axis} />
            <YAxis domain={[0, 100]} ticks={[0, 50, 100]} tickFormatter={v => `${v}%`} {...axis} width={38} />
            {out && <ReferenceArea x1={out[0]} x2={out[1]} fill={C.hair} fillOpacity={0.8} />}
            <Line dataKey="sq" stroke={C.faint} strokeWidth={1.4} strokeDasharray="4 3" dot={false} isAnimationActive={false} />
            <Line dataKey="qg" stroke={C.battery} strokeWidth={2} dot={false} isAnimationActive={false} />
            {notes.map((n, k) => <ReferenceDot key={n.text} x={n.x} y={n.y} r={8} fill="#fff" stroke={C.battery} strokeWidth={1.5}
              label={{ value: String(k + 1), position: 'center', fontSize: 10, fontWeight: 600, fill: C.text }} />)}
            <ReferenceLine x={t} stroke={C.accent} strokeWidth={1.2} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <Strip label="Diesel · status quo" on={dg('status_quo')} color={C.diesel} t={t} />
      <Strip label="Diesel · Q-Grid" on={dg('qgrid')} color={C.diesel} t={t} />
      {tankZ && <Strip label="Pump · Q-Grid" on={sc.runs.qgrid.pump_on[sc.campus.zones.indexOf(tankZ)].map(v => v === 1)} color={C.water} t={t} />}
      <figcaption className="keys">
        <span><i style={{ background: C.battery }} />Q-Grid battery level</span><span><i className="dash" />Status quo</span>
        {out && <span><i style={{ background: C.hair }} />Outage</span>}
      </figcaption>
      {notes.length > 0 && <ol className="notes">{notes.map(n => <li key={n.text}>{n.text}</li>)}</ol>}
    </figure>
  )
}

function Strip({ label, on, color, t }: { label: string; on: boolean[]; color: string; t: number }) {
  return (
    <div className="strip">
      <span>{label}</span>
      <svg viewBox="0 0 96 6" preserveAspectRatio="none">
        <rect x={0} y={2.5} width={96} height={1} fill={C.hair} />
        {on.map((v, i) => v ? <rect key={i} x={i} y={0.5} width={1.02} height={5} fill={color} /> : null)}
        <rect x={t} y={0} width={0.3} height={6} fill={C.accent} />
      </svg>
    </div>
  )
}

/** Step 5: disagreement (primal residual, kW) per ADMM round. */
export function ResidualChart({ rounds, k }: { rounds: { k: number; r_primal: number }[]; k: number }) {
  const data = rounds.map(r => ({ k: r.k + 1, gap: r.r_primal }))   // not "r": Recharts passes row fields to the SVG dot
  return (
    <div style={{ height: 110 }}>
      <ResponsiveContainer>
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
          <XAxis dataKey="k" {...axis} />
          <YAxis {...axis} width={40} />
          <Line dataKey="gap" stroke={C.grid} strokeWidth={1.6} isAnimationActive={false} type="linear" dot={{ r: 2.5, fill: C.grid, stroke: C.grid }} />
          <ReferenceLine x={k + 1} stroke={C.accent} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Count-up number (crossfade when reduced motion is preferred). */
export function CountUp({ value, format, delay = 0 }: { value: number; format: (v: number) => string; delay?: number }) {
  const [v, setV] = useState(reducedMotion() ? value : 0)
  const from = useRef(0)
  useEffect(() => {
    if (reducedMotion()) { setV(value); return }
    const c = animate(from.current, value, { duration: 1.1, delay, ease: [0.33, 1, 0.68, 1], onUpdate: x => { from.current = x; setV(x) } })
    return () => c.stop()
  }, [value])
  return <span className="tn">{format(v)}</span>
}

/** Step 7: % above the central optimum (B4) for each method, B4 = 0 line. */
export function GapBars({ rows }: { rows: { method: string; name: string; gap: number; ours?: boolean }[] }) {
  const mx = Math.max(...rows.map(r => r.gap), 1)
  return (
    <div className="gapbars" role="img" aria-label="cost above central optimum by method">
      {rows.map((r, i) => (
        <div key={r.method} className={`gb ${r.ours ? 'ours' : ''}`}>
          <span className="n">{r.name}</span>
          <span className="track">
            <motion.i initial={{ width: 0 }} animate={{ width: `${(r.gap / mx) * 100}%` }}
              transition={{ duration: reducedMotion() ? 0 : 0.8, delay: reducedMotion() ? 0 : 0.2 + i * 0.05, ease: [0.65, 0, 0.35, 1] }} />
          </span>
          <span className="v tn">{r.gap.toFixed(1)}%</span>
        </div>
      ))}
      <div className="gb axis"><span className="n" /><span className="track"><b>0% = central optimum (B4)</b></span><span className="v" /></div>
    </div>
  )
}
