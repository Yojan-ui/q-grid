import { useEffect, useMemo } from 'react'
import { animate, AnimatePresence, motion, useMotionValue, useTransform } from 'framer-motion'
import { Area, Bar, BarChart, Cell, ComposedChart, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from "recharts"
import katex from 'katex'
import 'katex/dist/katex.min.css'
import type { QaoaFile, Scenario } from '../lib/data'
import { C, fmtDate, num, pct, rs, SCEN, zn } from '../lib/theme'
import { type Beat, campusSoc, measure, rulesFor, stepOf, varInfo } from './model'

const reduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
const STEP_TITLE = ['', 'The problem', 'The campus', 'The decisions', 'How we use quantum', 'Buildings agree', 'Storage through the day', 'Results and scale']

export function CountUp({ to, fmt, dur = 1.2 }: { to: number; fmt: (v: number) => string; dur?: number }) {
  const mv = useMotionValue(0)
  const txt = useTransform(mv, v => fmt(v))
  useEffect(() => { const c = animate(mv, to, { duration: reduced ? 0 : dur, ease: [0.33, 1, 0.68, 1] }); return () => c.stop() }, [to])
  return <motion.span className="tn">{txt}</motion.span>
}

function Fig({ label, children, tone }: { label: string; children: React.ReactNode; tone?: string }) {
  return <div className="fig"><div className="fig-v" style={{ color: tone }}>{children}</div><div className="fig-l">{label}</div></div>
}

function Tex({ src }: { src: string }) {
  const html = useMemo(() => katex.renderToString(src, { throwOnError: false, displayMode: true }), [src])
  return <div className="tex" dangerouslySetInnerHTML={{ __html: html }} />
}

type Props = { beat: Beat; sc: Scenario; q: QaoaFile; idx: any; t: number; focus: string; round: number; setRound: (r: number) => void;
  admmT: number; removed: string | null; setRemoved: (z: string | null) => void; robust: Record<string, string>[]; search: any }

export function StoryText(p: Props) {
  const { beat, sc, q } = p
  const step = stepOf(beat)
  const meas = useMemo(() => measure(q), [q])
  const n = q.n_qubits
  const pending = sc.price_status !== 'REAL'
  const body = (() => {
    switch (beat) {
      case '1': {
        const pr = (sc as any).problem
        return {
          answer: 'On an ordinary day RVCE sells its noon solar cheaply and buys power back in the evening; in an outage every building fends for itself.',
          support: [`${SCEN[sc.scenario.key]}, ${fmtDate(sc.scenario.date)}. Watch the green ribbons leave for the BESCOM substation at noon and the red ones return after dark.`,
            sc.scenario.outage ? `BESCOM supply fails from ${sc.scenario.outage[0]} to ${sc.scenario.outage[1]}; only the hostels and admin block have diesel generators.` : 'Each building acts alone: no battery strategy, no sharing.'],
          figs: pr && <div className="figs">
            <Fig label="value lost per day" tone={C.grid}><CountUp to={pr.rs_lost} fmt={rs} /></Fig>
            <Fig label="CO₂ per day"><CountUp to={pr.co2_kg} fmt={v => `${num(v)} kg`} /></Fig>
            <Fig label="diesel hours"><CountUp to={pr.dg_hours} fmt={v => `${v.toFixed(1)} h`} /></Fig>
          </div>,
          extra: <DayProblem sc={sc} t={p.t} />,
          note: pending ? 'Prices are stand-ins until the official BESCOM/KERC tariff is added (PENDING).' : '',
        }
      }
      case '2': {
        const z = sc.campus.zones.find(x => x.name === p.focus)!
        return {
          answer: 'Every 15 minutes we decide what each of these devices does.',
          support: ['Nine zones, mapped from OpenStreetMap. Hover a zone to lift it; click to see its devices.'],
          extra: <Asset z={z} />,
        }
      }
      case '3': {
        const zones = p.search?.local_qubo_qubits ?? {}
        return {
          answer: `In the ${zn(q.zone)} at ${sc.slots.t[q.slot]} that is ${n} yes/no decisions.`,
          support: ['Each tile is one decision for the next 45 minutes: charge or not, diesel on or off, start a load or wait, share power or not.'],
          figs: <div className="figs">
            <Fig label="decisions in this building"><CountUp to={n} fmt={v => num(v)} /></Fig>
            <Fig label="possible plans for this building"><CountUp to={2 ** n} fmt={v => num(v)} /></Fig>
            <Fig label="plans for the whole campus, one day" tone={C.quantum}><span className="tn">2<sup>{num(p.search?.centralised_full_day?.N_binary ?? 0)}</sup></span></Fig>
          </div>,
          note: `Decisions per zone: ${Object.entries(zones).map(([k, v]) => `${zn(k)} ${v}`).join(', ')}.`,
        }
      }
      case '4a': return { answer: 'Each yes/no decision becomes one qubit.',
        support: [`${n} qubits can hold all ${num(2 ** n)} plans at once (a superposition), so the algorithm weighs them together instead of one by one.`] }
      case '4b': return { answer: 'The goals and rules become one cost formula that links the qubits.',
        support: ['Lines show which decisions affect each other; thicker means a stronger effect on cost.'],
        extra: <><ul className="rules">{rulesFor(q).map(r => <li key={r.text}><i className={`k-${r.kind}`} />{r.text}</li>)}</ul>
          <Tex src={'E(x)=\\sum_i Q_{ii}\\,x_i+\\sum_{i<j} Q_{ij}\\,x_i x_j,\\quad x_i\\in\\{0,1\\}'} />
          <p className="muted small">This is a QUBO: the cheapest valid plan has the lowest E. Broken rules add a large penalty.</p></> }
      case '4c': return { answer: `QAOA repeats two moves ${q.gammas.length} times: favour cheap plans, then mix.`,
        support: ['Start: every plan equally likely. Cost layer: plans are tilted by how much they cost. Mix layer: likelihood flows between neighbouring plans.'],
        extra: <p className="muted small">Angles learned on separate training days: γ = {q.gammas.map(g => g.toFixed(2)).join(', ')}; β = {q.betas.map(b => b.toFixed(2)).join(', ')}. Simulated on a laptop with qiskit-aer (ideal, noiseless).</p> }
      case '4d': return { answer: 'Measuring the circuit many times gives a histogram; the best plan seen wins.',
        support: ['We take 256 measurements and keep the cheapest valid plan among them.'],
        figs: <div className="figs">
          <Fig label="chance of the optimum per shot" tone={C.quantum}><span className="tn">{(100 * q.optimum.p_opt).toFixed(2)}%</span></Fig>
          <Fig label="by pure guessing"><span className="tn">{(100 * q.uniform_p).toFixed(3)}%</span></Fig>
        </div> }
      case '4e': {
        const acts = q.var_names.map((v, i) => ({ v, info: varInfo(v, sc, q.zone), b: Number((meas.winBits ?? q.optimum.bits)[i]) }))
          .filter(a => a.b === 1 || ['g', 'w', 'c0', 'd0'].includes(a.v))
        return { answer: 'The winning bits are turned back into device actions.',
          support: [`For the next 15 minutes the ${zn(q.zone)}:`],
          extra: <ul className="acts">{acts.map(a => <li key={a.v}><b>{a.b ? a.info.on : a.info.off}</b><span className="muted"> — {a.info.label.toLowerCase()}</span></li>)}</ul> }
      }
      case '4f': {
        const live = sc.live_solve?.find(l => l.zone === q.zone && l.slot === q.slot)
        const ours = sc.benchmark.find(r => r.method === 'OURS' && r.price_scenario === 'A')
        const tot = ours ? ['tier_qaoa', 'tier_qiea', 'tier_anneal', 'tier_exact'].reduce((a, k) => a + (ours[k] ?? 0), 0) : 0
        return { answer: `Every quantum answer is checked against an exact search of all ${num(2 ** n)} plans.`,
          support: ['If the quantum plan is not the true optimum, the building falls back to a quantum-inspired search, then annealing, then the exact answer — so no schedule ever depends on the quantum result being right.'],
          extra: <div className="verify">
            <div><span className="muted">Quantum (QAOA)</span><code>{meas.winBits ?? '—'}</code></div>
            <div><span className="muted">Exact search</span><code>{q.optimum.bits}</code></div>
            <div className={meas.gap !== null && meas.gap <= 1e-9 ? 'ok' : 'gap'}>{meas.gap === null ? 'no valid sample — fallback used' : meas.gap <= 1e-9 ? '✓ identical — verified optimal' : `gap ${(100 * meas.gap).toFixed(2)}% — fallback used`}</div>
            {live && <div className="muted small">Time on a laptop: simulated QAOA {(live.qaoa.time_s * 1000).toFixed(1)} ms, exact search {(live.exact.time_s * 1000).toFixed(1)} ms. At {n} qubits both are instant; simulation cost doubles with every extra qubit.</div>}
            {ours && tot > 0 && <div className="muted small">Across this whole day: QAOA's answer was verified optimal in {pct(100 * ours.tier_qaoa / tot)} of {num(tot)} building-level solves.</div>}
          </div> }
      }
      case '4g': return { answer: 'Quantum chooses the yes/no plan inside each building. Everything else is classical.',
        extra: <div className="who">
          <div className="col q"><h4>Quantum circuit (simulated)</h4><p>QAOA picks each building's on/off plan for the next 45 minutes.</p></div>
          <div className="col c"><h4>Classical</h4><p>Negotiation between buildings, battery cost-to-go, safety limits, exact verification, fallbacks.</p></div>
          <p className="muted small">QAOA runs on a local simulator and is verified against exact solutions; no quantum advantage is claimed. QIEA is quantum-inspired and runs on an ordinary CPU.</p>
        </div> }
      case '5': return { answer: 'Neighbouring buildings agree on how much power to share by trading proposals — there is no central computer.',
        support: ['Each round, both ends of a tie-line propose a flow; they move towards each other until they match.'], extra: <AdmmPanel {...p} /> }
      case '6': {
        const qs = campusSoc(sc, 'qgrid'), d = qs.slice(1).map((v, i) => v - qs[i])
        const mid = Math.max(...d.slice(36, 64)), eve = Math.min(...d.slice(68, 92))
        const answer = mid > 0.5 && eve < -0.5 ? 'Batteries now charge from noon solar and discharge at the evening peak.'
          : mid > 0.5 ? 'Batteries now charge from noon solar and hold that energy for later.'
          : 'Batteries follow the cost-to-go plan; on this day they move little.'
        return { answer, extra: <Storage sc={sc} t={p.t} /> }
      }
      case '7': {
        const g = (m: string) => sc.benchmark.find(r => r.method === m && r.price_scenario === 'A')
        const o = g('OURS'), b0 = g('B0')
        const cheaper = o && b0 && o.cost_rs < b0.cost_rs, safer = o && b0 && o.critical_downtime_h < b0.critical_downtime_h - 1e-9
        const answer = !o || !b0 ? 'The same day, coordinated.'
          : safer && cheaper ? `The same day, coordinated: cheaper and with less critical downtime, ${o.gap_to_B4_pct.toFixed(1)}% from the best possible plan.`
          : safer ? `The same day, coordinated: critical loads protected better (${b0.critical_downtime_h.toFixed(1)} h → ${o.critical_downtime_h.toFixed(1)} h of downtime), at a higher cost because diesel runs to cover them.`
          : cheaper ? `The same day, coordinated: ${rs(b0.cost_rs - o.cost_rs)} cheaper than today, ${o.gap_to_B4_pct.toFixed(1)}% from the best possible plan.`
          : 'The same day, coordinated: no cheaper than today on this day — see the table.'
        return { answer, extra: <Results sc={sc} /> }
      }
    }
  })()!
  return (
    <AnimatePresence mode="wait">
      <motion.div key={beat} className="story-text" initial={{ opacity: 0, y: reduced ? 0 : 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: reduced ? 0 : -8 }}
        transition={{ duration: reduced ? 0.15 : 0.45, ease: [0.65, 0, 0.35, 1] }}>
        <div className="kicker">Step {beat.length > 1 ? beat : step} of 7 · {STEP_TITLE[step]}</div>
        <h1>{body.answer}</h1>
        {body.support?.map((s, i) => <p key={i} className="support">{s}</p>)}
        {body.figs}
        {body.extra}
        {body.note && <p className="note">{body.note}</p>}
      </motion.div>
    </AnimatePresence>
  )
}

function DayProblem({ sc, t }: { sc: Scenario; t: number }) {
  const r = sc.runs.status_quo!
  const data = sc.slots.t.map((_, i) => ({ i, solar: sc.slots.pv_kw.reduce((a, z) => a + z[i], 0), load: (r as any).demand_kw ? (r as any).demand_kw.reduce((a: number, z: number[]) => a + z[i], 0) : 0,
    price: sc.slots.price_import[i], exp: r.grid_export_kw[i], imp: r.grid_import_kw[i] }))
  const expSpan = data.filter(d => d.exp > 1), impSpan = data.filter(d => d.imp > 1 && d.i >= 68)
  const out = sc.slots.grid_up.indexOf(0)
  return (
    <div className="chart">
      <div style={{ height: 120 }}>
        <ResponsiveContainer><ComposedChart data={data} margin={{ top: 6, right: 0, left: 0, bottom: 0 }}>
          <XAxis dataKey="i" ticks={[0, 24, 48, 72, 95]} tickFormatter={i => sc.slots.t[i]} stroke={C.muted} fontSize={11} tickLine={false} axisLine={{ stroke: C.hair }} />
          <YAxis yAxisId="kw" hide /><YAxis yAxisId="rs" hide orientation="right" />
          {expSpan.length > 0 && <ReferenceArea yAxisId="kw" x1={expSpan[0].i} x2={expSpan[expSpan.length - 1].i} fill={C.solar} fillOpacity={0.07} label={{ value: 'sold cheap', position: 'insideTop', fill: C.solar, fontSize: 11 }} />}
          {impSpan.length > 0 && <ReferenceArea yAxisId="kw" x1={impSpan[0].i} x2={impSpan[impSpan.length - 1].i} fill={C.grid} fillOpacity={0.07} label={{ value: 'bought expensive', position: 'insideTop', fill: C.grid, fontSize: 11 }} />}
          {out >= 0 && <ReferenceArea yAxisId="kw" x1={out} x2={sc.slots.grid_up.lastIndexOf(0)} fill={C.text} fillOpacity={0.06} />}
          <Area yAxisId="kw" dataKey="solar" stroke={C.solar} fill={C.solar} fillOpacity={0.12} strokeWidth={1.5} isAnimationActive={false} />
          <Line yAxisId="kw" dataKey="load" stroke={C.text} dot={false} strokeWidth={1.5} isAnimationActive={false} />
          <Line yAxisId="rs" dataKey="price" stroke={C.muted} dot={false} strokeWidth={1} strokeDasharray="4 3" type="stepAfter" isAnimationActive={false} />
          <ReferenceLine yAxisId="kw" x={Math.min(95, Math.floor(t))} stroke={C.accent} />
        </ComposedChart></ResponsiveContainer>
      </div>
      <div className="keys"><span><i style={{ background: C.solar }} />solar</span><span><i style={{ background: C.text }} />campus load</span><span><i className="dash" />import price</span>{out >= 0 && <span><i style={{ background: '#DDD' }} />outage</span>}</div>
    </div>
  )
}

function Asset({ z }: { z: any }) {
  const rows: [string, string][] = [['Rooftop solar', `${num(z.pv_kwp)} kWp`]]
  if (z.battery_kwh) rows.push(['Battery', `${num(z.battery_kwh)} kWh · ${num(z.battery_kw)} kW`])
  if (z.dg_kw) rows.push(['Diesel generator', `${num(z.dg_kw)} kW`])
  if (z.tank_m3) rows.push(['Borewell pump + tank', `${num(z.tank_m3)} m³`])
  for (const f of z.flex ?? []) rows.push([f.name.replace(/_/g, ' ').replace(/^\w/, (c: string) => c.toUpperCase()), `${num(f.kw)} kW · ${f.slots * 15} min`])
  rows.push(['Critical share of load', pct(100 * z.critical_frac)])
  return (
    <div className="asset">
      <h3>{zn(z.name)}</h3>
      <table><tbody>{rows.map(([a, b]) => <tr key={a}><td>{a}</td><td className="tn">{b}</td></tr>)}</tbody></table>
      <p className="muted small">Capacities are engineering assumptions until RVCE asset data arrives.</p>
    </div>
  )
}

function AdmmPanel({ sc, round, setRound, admmT, removed, setRemoved, robust }: Props) {
  const its = sc.admm.iterations[String(admmT)] ?? []
  useEffect(() => {
    setRound(0)
    if (reduced) { setRound(its.length - 1); return }
    let k = 0
    const id = setInterval(() => { k = Math.min(its.length - 1, k + 1); setRound(k); if (k >= its.length - 1) clearInterval(id) }, 900)
    return () => clearInterval(id)
  }, [admmT, sc])
  const data = its.map(r => ({ k: r.k + 1, r: r.r_primal }))
  const kill = robust.find(r => r.mode === 'in-process' && r.scenario === sc.scenario.key)
  return (
    <div>
      <div className="rounds">Round <b className="tn">{Math.min(round + 1, its.length)}</b> of {its.length} at {sc.slots.t[admmT]} {its[round]?.agreed ? <span className="ok">· all agreed</span> : null}</div>
      <Residual data={data} round={round} />
      <p className="muted small">Largest disagreement on any tie-line, in kW, per round.</p>
      <button className="ghost" onClick={() => setRemoved(removed ? null : 'heavy_labs')}>{removed ? 'Put the mechanical labs back' : 'Remove a building (mechanical labs)'}</button>
      {removed && kill && <p className="small">Its neighbours stop hearing from it within 3 seconds and cut their lines to it; the rest carry on. In the recorded failure run the schedule stayed feasible ({kill.feasible}) and full agreement returned after {kill.slots_to_reconverge || '–'} slots.</p>}
    </div>
  )
}

function Residual({ data, round }: { data: { k: number; r: number }[]; round: number }) {
  const W = 320, H = 96, mx = Math.max(...data.map(d => d.r), 1), n = Math.max(data.length - 1, 1)
  const x = (i: number) => 24 + (i / n) * (W - 32), y = (v: number) => 8 + (1 - v / mx) * (H - 28)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="residual" role="img" aria-label="disagreement per round">
      <line x1={24} x2={W - 8} y1={H - 20} y2={H - 20} stroke={C.hair} />
      <text x={20} y={y(mx) + 4} fontSize={10} fill={C.muted} textAnchor="end">{Math.round(mx)}</text>
      <text x={20} y={H - 16} fontSize={10} fill={C.muted} textAnchor="end">0</text>
      <polyline fill="none" stroke={C.quantum} strokeWidth={1.5} points={data.map((d, i) => `${x(i)},${y(d.r)}`).join(' ')} />
      {data.map((d, i) => <circle key={i} cx={x(i)} cy={y(d.r)} r={i === round ? 4 : 2.5} fill={i <= round ? C.quantum : '#fff'} stroke={C.quantum} />)}
      {data.map((d, i) => <text key={`t${i}`} x={x(i)} y={H - 4} fontSize={10} fill={C.muted} textAnchor="middle">{d.k}</text>)}
    </svg>
  )
}

function Storage({ sc, t }: { sc: Scenario; t: number }) {
  const q = campusSoc(sc, 'qgrid'), s = campusSoc(sc, 'status_quo')
  const data = q.slice(0, 96).map((v, i) => ({ i, q: v, s: s[i] }))
  const dq = q.slice(1).map((v, i) => v - q[i])
  const argmax = (lo: number, hi: number, f: (i: number) => number) => { let b = lo; for (let i = lo; i < hi; i++) if (f(i) > f(b)) b = i; return b }
  const ch = argmax(36, 64, i => dq[i]), dis = argmax(68, 92, i => -dq[i])
  const out = sc.slots.grid_up.indexOf(0)
  const ann = [{ i: ch, text: 'charged from noon solar' }, { i: dis, text: 'discharged at the evening peak' }]
  if (out > 0) ann.push({ i: out, text: `${Math.round(q[out])}% in reserve when the outage starts` })
  const tank = sc.campus.zones.find(z => z.tank_m3 > 0)
  const dg = sc.campus.zones.map((z, i) => ({ z, i })).filter(x => x.z.dg_kw > 0)
  return (
    <div className="chart">
      <div style={{ height: 150 }}><ResponsiveContainer><LineChart data={data} margin={{ top: 18, right: 4, left: -18, bottom: 0 }}>
        <XAxis dataKey="i" ticks={[0, 24, 48, 72, 95]} tickFormatter={i => sc.slots.t[i]} stroke={C.muted} fontSize={11} tickLine={false} axisLine={{ stroke: C.hair }} />
        <YAxis domain={[0, 100]} ticks={[20, 50, 95]} stroke={C.muted} fontSize={11} tickLine={false} axisLine={false} unit="%" />
        <Line dataKey="s" stroke={C.muted} strokeDasharray="4 3" dot={false} isAnimationActive={false} name="status quo" />
        <Line dataKey="q" stroke={C.battery} strokeWidth={2} dot={false} isAnimationActive={false} name="Q-Grid" />
        {ann.map((a, k) => <ReferenceLine key={a.text} x={a.i} stroke={C.muted} strokeDasharray="2 3" label={{ value: String(k + 1), position: 'top', fontSize: 11, fill: C.text }} />)}
        <ReferenceLine x={Math.min(95, Math.floor(t))} stroke={C.accent} />
      </LineChart></ResponsiveContainer></div>
      <div className="keys"><span><i style={{ background: C.battery }} />Q-Grid battery charge (campus)</span><span><i className="dash" />status quo</span></div>
      <ol className="anns">{ann.map(a => <li key={a.text}><span className="tn">{sc.slots.t[a.i]}</span> {a.text}</li>)}</ol>
      <div className="strip">
        {tank && <div><span className="muted small">Tank</span><Spark v={sc.runs.qgrid.tank_m3[tank.name].slice(0, 96).map(x => x / tank.tank_m3)} color={C.water} /></div>}
        {dg.map(({ z, i }) => <div key={z.name}><span className="muted small">Diesel · {zn(z.name)}</span><Strip on={sc.runs.qgrid.dg_kw[i].map(x => x > 0)} /></div>)}
      </div>
    </div>
  )
}
function Spark({ v, color }: { v: number[]; color: string }) {
  const d = v.map((x, i) => `${i ? 'L' : 'M'}${(i / 95) * 100},${20 - x * 18}`).join('')
  return <svg viewBox="0 0 100 20" preserveAspectRatio="none" className="spark"><path d={d} stroke={color} fill="none" strokeWidth={1.2} vectorEffect="non-scaling-stroke" /></svg>
}
function Strip({ on }: { on: boolean[] }) {
  return <svg viewBox="0 0 96 4" preserveAspectRatio="none" className="spark">{on.map((x, i) => x ? <rect key={i} x={i} y={0} width={1} height={4} fill={C.text} /> : null)}</svg>
}

const ORDER = ['B0', 'B1', 'B2-GA', 'B2-PSO', 'B3', 'B5', 'C-QIEA', 'OURS-QIEA', 'OURS', 'B4']
const LBL: Record<string, string> = { B0: 'Status quo', B1: 'Rule-based', 'B2-GA': 'Genetic alg.', 'B2-PSO': 'Particle swarm', B3: 'Per-building MILP',
  B5: 'ADMM + exact', 'C-QIEA': 'Central QIEA*', 'OURS-QIEA': 'ADMM + QIEA*', OURS: 'Q-Grid (ADMM + QAOA)', B4: 'Central optimum' }
function Results({ sc }: { sc: Scenario }) {
  const rows = ORDER.map(m => sc.benchmark.find(r => r.method === m && r.price_scenario === 'A')).filter(Boolean) as any[]
  const b4 = rows.find(r => r.method === 'B4')?.objective_rs ?? 0
  const h = sc.headline
  return (
    <div>
      <div style={{ height: 176 }}><ResponsiveContainer><BarChart data={rows} layout="vertical" margin={{ top: 0, right: 40, left: 10, bottom: 0 }}>
        <XAxis type="number" hide domain={[0, 'dataMax']} /><YAxis type="category" dataKey="method" interval={0} tickFormatter={m => LBL[m]} width={140} stroke={C.muted} fontSize={11} tickLine={false} axisLine={false} />
        <ReferenceLine x={b4} stroke={C.text} strokeDasharray="3 3" label={{ value: 'optimum', fontSize: 10, fill: C.muted, position: 'top' }} />
        <Bar dataKey="objective_rs" isAnimationActive={!reduced} animationDuration={900} label={{ position: 'right', fontSize: 10, fill: C.muted, formatter: (v: any) => `${Math.round(v / 1000)}k` }}>
          {rows.map(r => <Cell key={r.method} fill={r.method === 'OURS' ? C.quantum : r.method === 'B4' ? C.text : '#D7D6CF'} />)}
        </Bar>
      </BarChart></ResponsiveContainer></div>
      <p className="muted small">Daily cost in Rs thousands, including the value of unserved load (lower is better). *QIEA = quantum-inspired, classical CPU.</p>
      <table className="res"><thead><tr><th></th><th>Rs/day</th><th>CO₂ kg</th><th>Diesel h</th><th>Gap to optimum</th><th>Run time</th></tr></thead>
        <tbody>{rows.filter(r => ['B0', 'B3', 'B5', 'OURS', 'B4'].includes(r.method)).map(r => (
          <tr key={r.method} className={r.method === 'OURS' ? 'ours' : ''}><td>{LBL[r.method]}</td><td className="tn">{rs(r.cost_rs)}</td><td className="tn">{num(r.co2_kg)}</td>
            <td className="tn">{(r.dg_hours ?? 0).toFixed(1)}</td><td className="tn">{(r.gap_to_B4_pct ?? 0).toFixed(1)}%</td><td className="tn">{(r.runtime_s ?? 0).toFixed(0)} s</td></tr>))}</tbody></table>
      {h && <div className="headline-card"><h3>Outage during the fest</h3>
        <p>Critical-load downtime <b className="tn">{h.before.critical_downtime_h.toFixed(2)} h → {h.after.critical_downtime_h.toFixed(2)} h</b>; critical energy unserved <b className="tn">{Math.round(h.before.critical_unserved_kwh)} → {Math.round(h.after.critical_unserved_kwh)} kWh</b>; re-planning <b className="tn">{(h.after.replan_time_s * 1000).toFixed(0)} ms</b> per slot. The central optimum reaches {h.optimum_B4.critical_downtime_h.toFixed(2)} h.</p></div>}
    </div>
  )
}

export { STEP_TITLE }
