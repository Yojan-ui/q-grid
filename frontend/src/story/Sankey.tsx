// Daily energy Sankey: sources (solar, battery, grid, diesel) on the left, sinks (each zone, critical loads, battery
// charging, export) on the right; link width = kWh. Data from qgrid/operate/flows.py (replay or the live report).
import type { Flows } from '../lib/operate'
import { zn } from '../lib/labels'
import { useC } from '../lib/theme'
import { reg } from '../lib/numcheck'

const SRC_ORDER = ['Solar', 'Battery', 'Grid', 'Diesel']

export function Sankey({ flows, height = 360, title }: { flows: Flows; height?: number; title?: string }) {
  const C = useC()
  const col: Record<string, string> = { Solar: C.solar, Battery: C.battery, Grid: C.grid, Diesel: C.diesel }
  // zones below 3 % of the day's energy are grouped so their labels stay readable
  const raw = flows.links.filter(l => l.kwh > 0)
  const totAll = raw.reduce((a, l) => a + l.kwh, 0) || 1
  const zoneTot: Record<string, number> = {}
  raw.forEach(l => { if (l.kind === 'zone') zoneTot[l.target] = (zoneTot[l.target] ?? 0) + l.kwh })
  const small = new Set(Object.keys(zoneTot).filter(z => zoneTot[z] < 0.03 * totAll))
  const merged: Record<string, typeof raw[0]> = {}
  raw.forEach(l => { const t = small.has(l.target) ? 'Other zones' : l.target; const k = `${l.source}|${t}`; merged[k] = merged[k] ? { ...merged[k], kwh: merged[k].kwh + l.kwh } : { ...l, target: t } })
  const links = Object.values(merged)
  const srcs = SRC_ORDER.filter(s => links.some(l => l.source === s))
  const sinkTot: Record<string, number> = {}
  links.forEach(l => { sinkTot[l.target] = (sinkTot[l.target] ?? 0) + l.kwh })
  Object.values(sinkTot).forEach(v => reg(v, 'Sankey: sum of the flows into a sink'))
  const special = ['Other zones', 'Critical loads', 'Battery charging', 'Export']
  const sinks = [...Object.keys(sinkTot).filter(k => !special.includes(k)).sort((a, b) => sinkTot[b] - sinkTot[a]), ...special.filter(k => sinkTot[k])]
  const srcTot: Record<string, number> = {}
  links.forEach(l => { srcTot[l.source] = (srcTot[l.source] ?? 0) + l.kwh })
  Object.values(srcTot).forEach(v => reg(v, 'Sankey: sum of the flows out of a source'))
  const total = Object.values(srcTot).reduce((a, b) => a + b, 0) || 1
  const W = 660, H = height, padT = 8, gapS = 10, gapK = 6, x0 = 112, x1 = W - 206, nw = 10
  const scaleS = (H - padT * 2 - gapS * (srcs.length - 1)) / total
  const scaleK = (H - padT * 2 - gapK * (sinks.length - 1)) / total
  const sc = Math.min(scaleS, scaleK)
  // node positions
  const ys: Record<string, number> = {}, yk: Record<string, number> = {}
  let y = padT
  srcs.forEach(s => { ys[s] = y; y += srcTot[s] * sc + gapS })
  y = padT
  sinks.forEach(k => { yk[k] = y; y += sinkTot[k] * sc + gapK })
  const offS: Record<string, number> = {}, offK: Record<string, number> = {}
  const paths = SRC_ORDER.flatMap(s => sinks.map(k => links.find(l => l.source === s && l.target === k)).filter(Boolean)).map(l => {
    const w = l!.kwh * sc
    const sy = ys[l!.source] + (offS[l!.source] ?? 0) + w / 2; offS[l!.source] = (offS[l!.source] ?? 0) + w
    const ky = yk[l!.target] + (offK[l!.target] ?? 0) + w / 2; offK[l!.target] = (offK[l!.target] ?? 0) + w
    const mx = (x0 + nw + x1) / 2
    return { d: `M${x0 + nw},${sy} C${mx},${sy} ${mx},${ky} ${x1},${ky}`, w: Math.max(w, 0.6), col: col[l!.source], l: l! }
  })
  const kwh = (v: number) => `${Math.round(v).toLocaleString('en-IN')} kWh`
  const label = (k: string) => (special.includes(k) ? (k === 'Other zones' ? `Other zones (${small.size})` : k) : zn(k))
  const summary = `${title ?? 'Daily energy flows'}: ${srcs.map(s => `${s} ${kwh(srcTot[s])}`).join(', ')}; to ${sinks.map(k => `${label(k)} ${kwh(sinkTot[k])}`).join(', ')}.`
  return (
    <figure className="sankey">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={summary}>
        {paths.map((p, i) => <path key={i} d={p.d} fill="none" stroke={p.col} strokeOpacity={0.35} strokeWidth={p.w}>
          <title>{`${p.l.source} → ${label(p.l.target)}: ${kwh(p.l.kwh)}`}</title></path>)}
        {srcs.map(s => <g key={s}>
          <rect x={x0} y={ys[s]} width={nw} height={Math.max(srcTot[s] * sc, 1)} fill={col[s]} rx={2} />
          <text x={x0 - 8} y={ys[s] + srcTot[s] * sc / 2 - 2} textAnchor="end" fontSize={12} fontWeight={600} fill={C.text}>{s}</text>
          <text x={x0 - 8} y={ys[s] + srcTot[s] * sc / 2 + 12} textAnchor="end" fontSize={11} fill={C.muted} className="tn">{kwh(srcTot[s])}</text>
        </g>)}
        {sinks.map(k => <g key={k}>
          <rect x={x1} y={yk[k]} width={nw} height={Math.max(sinkTot[k] * sc, 1)} fill={special.includes(k) && k !== 'Other zones' ? C.text : C.neutralMark} rx={2} />
          <text x={x1 + nw + 6} y={yk[k] + sinkTot[k] * sc / 2 + 4} fontSize={11} fill={C.text}>{label(k)} <tspan fill={C.muted} className="tn">{kwh(sinkTot[k])}</tspan></text>
        </g>)}
      </svg>
      <figcaption className="muted small">{flows.method}.{flows.unserved_kwh > 0.5 ? ` Unserved load: ${kwh(flows.unserved_kwh)}.` : ''}</figcaption>
    </figure>
  )
}
