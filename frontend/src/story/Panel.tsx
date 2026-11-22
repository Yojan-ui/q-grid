// Right-hand explanation: "Step X of 7", one sentence, a few lines of support, key numbers, Back / Next.
// Every figure is read from the replay (StoryData); this file only words and formats them.
import { useMemo } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { C, num, pct, reducedMotion, rs } from '../lib/theme'
import { devices, fmtDate, hourLabel, METHOD, varLabel, zn } from '../lib/labels'
import { campusSoc, STEP_COUNT, STOPS, subOf, type StopId, type StoryData } from '../lib/story'
import { BoundsChart, CountUp, DayChart, GapBars, outageSpan, ResidualChart, SocChart } from './charts'
import { FORMULA, N } from '../panels/Prov'

export type PanelProps = {
  stop: StopId; d: StoryData; t: number; playing: boolean; onPlay: () => void
  zone: string | null; setZone: (z: string | null) => void
  killed: string | null; setKilled: (z: string | null) => void
  admmRound: number; setAdmmRound: (k: number) => void
  replayPulse: () => void; showMiss: boolean; setShowMiss: (v: boolean) => void
  onPrev: () => void; onNext: () => void; go: (i: number) => void; index: number
}

const Pending = ({ what }: { what: string }) => <span className="pending" title={`${what} is a labelled stand-in until the official data arrives`}>stand-in</span>

function Key({ label, children, pending, note }: { label: string; children: React.ReactNode; pending?: string; note?: string }) {
  return <div className="key"><span className="kl">{label}{pending && <Pending what={pending} />}</span><b className="kv">{children}</b>{note && <span className="kn">{note}</span>}</div>
}

export function Panel(p: PanelProps) {
  const s = STOPS[p.index]
  const subs = subOf(p.stop)
  const subIdx = subs.findIndex(x => x.id === p.stop)
  const body = useMemo(() => content(p), [p.stop, p.t, p.zone, p.killed, p.admmRound, p.showMiss, p.playing, p.d])
  const fade = reducedMotion() ? { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 } }
    : { initial: { opacity: 0, y: 14 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: -10 } }
  return (
    <aside className="panel" aria-live="polite">
      <div className="stepnums" role="tablist" aria-label="steps">
        {Array.from({ length: STEP_COUNT }, (_, k) => k + 1).map(n => (
          <button key={n} role="tab" aria-selected={s.step === n} className={s.step === n ? 'on' : n < s.step ? 'done' : ''}
            onClick={() => p.go(STOPS.findIndex(x => x.step === n))} title={STOPS.find(x => x.step === n)!.title}>{n}</button>))}
        <div className="stepno"><span>Step {s.step} of {STEP_COUNT}</span><span className="muted">· {s.title}</span>
          {subs.length > 1 && <span className="subdots" aria-label={`part ${subIdx + 1} of ${subs.length}`}>{subs.map((x, i) => <i key={x.id} className={i === subIdx ? 'on' : i < subIdx ? 'done' : ''} />)}</span>}
        </div>
      </div>
      <div className="panel-scroll">
        <AnimatePresence mode="wait">
          <motion.section key={p.stop} {...fade} transition={{ duration: reducedMotion() ? 0.15 : 0.45, ease: [0.65, 0, 0.35, 1] }}>
            <h1 className="answer">{body.answer}</h1>
            {body.support && <div className="support">{body.support}</div>}
            {body.keys && <div className={`keys-row ${p.stop === '7a' ? 'k4' : ''}`}>{body.keys}</div>}
            {body.extra}
          </motion.section>
        </AnimatePresence>
      </div>
      <nav className="pager" aria-label="story navigation">
        <div className="progress" role="progressbar" aria-valuemin={1} aria-valuemax={STOPS.length} aria-valuenow={p.index + 1}>
          {STOPS.map((x, i) => <button key={x.id} className={`${i === p.index ? 'on' : ''} ${i < p.index ? 'done' : ''} ${x.step !== STOPS[i - 1]?.step ? 'first' : ''}`}
            onClick={() => p.go(i)} aria-label={`Step ${x.step}: ${x.title}`} title={`${x.step} · ${x.title}`} />)}
        </div>
        <div className="pager-row">
          <button className="btn ghost" onClick={p.onPrev} disabled={p.index === 0}>← Back</button>
          <span className="muted small">← → keys or scroll</span>
          <button className="btn primary" onClick={p.onNext} disabled={p.index === STOPS.length - 1}>Next →</button>
        </div>
      </nav>
    </aside>
  )
}

type Body = { answer: React.ReactNode; support?: React.ReactNode; keys?: React.ReactNode; extra?: React.ReactNode }

function content(p: PanelProps): Body {
  const { d } = p
  const { sc, example: ex, q } = d
  const out = outageSpan(sc)
  const slotT = (i: number) => sc.slots.t[Math.min(95, i)]
  const zi = sc.campus.zones.findIndex(z => z.name === ex.zone)
  const priceStatus = sc.price_status !== 'REAL'
  const cea = sc.data_status?.cea !== 'REAL'
  const v2body = contentV2(p)
  if (v2body) return v2body
  switch (p.stop) {
    case '1': {
      const pr = d.problem
      const noonPrice = sc.slots.price_export[48], evePrice = Math.max(...sc.slots.price_import)
      return {
        answer: out ? <>Today the campus sells noon solar cheaply, buys power back expensively in the evening, and runs diesel when the grid fails.</>
          : <>Today the campus sells noon solar cheaply and buys power back expensively in the evening.</>,
        support: <>
          <p>A modelled {SCENARIO(sc)} day ({fmtDate(sc.scenario.date)}){out ? `, with BESCOM supply down ${slotT(out[0])}–${slotT(out[1])}` : ''}. Every building acts on its own.</p>
          {pr && <p>Around noon it exported <b className="tn">{num(Number(pr.noon_export_kwh))} kWh</b> at Rs {noonPrice}/kWh; in the evening it imported <b className="tn">{num(Number(pr.evening_import_kwh))} kWh</b> at up to Rs {evePrice}/kWh.</p>}
        </>,
        keys: sc.problem && <>
          <Key label="Value lost per day" pending={priceStatus ? 'Tariff' : undefined}><CountUp value={sc.problem.rs_lost} format={rs} /></Key>
          <Key label="CO₂ per day" pending={cea ? 'CEA CO₂ factor' : undefined}><CountUp value={sc.problem.co2_kg} format={v => `${num(v)} kg`} delay={0.1} /></Key>
          <Key label="Diesel running" note={`critical loads unserved ${sc.problem.critical_downtime_h.toFixed(1)} h`}><CountUp value={sc.problem.dg_hours} format={v => `${v.toFixed(1)} h`} delay={0.2} /></Key>
        </>,
        extra: <>
          <DayChart sc={sc} t={p.t} />
          {sc.problem && <p className="muted small defn">Value lost = Σ over zones of min(kWh exported by day, kWh bought back later) × (average later import price − average export price). {num(sc.problem.reusable_kwh)} kWh qualify on this day.</p>}
          <div className="row"><button className="btn ghost small" onClick={p.onPlay}>{p.playing ? 'Pause the day' : 'Replay the day'}</button></div>
        </>,
      }
    }
    case '2': {
      const zs = sc.campus.zones
      const sel = zs.find(z => z.name === p.zone)
      return {
        answer: <>Every 15 minutes we decide what each of these does.</>,
        support: <p>RVCE as {zs.length} zones traced from OpenStreetMap, joined by {sc.campus.lines.length} cables. Click a building to see what it can control.</p>,
        keys: <>
          <Key label="Rooftop solar">{num(zs.reduce((a, z) => a + z.pv_kwp, 0))} kWp</Key>
          <Key label="Batteries">{num(zs.reduce((a, z) => a + z.battery_kwh, 0))} kWh</Key>
          <Key label="Diesel sets">{num(zs.reduce((a, z) => a + z.dg_kw, 0))} kW</Key>
        </>,
        extra: <>
          <div className="chips">{zs.map(z => <button key={z.name} className={`chip ${p.zone === z.name ? 'on' : ''}`} onClick={() => p.setZone(p.zone === z.name ? null : z.name)}>{zn(z.name)}</button>)}</div>
          {sel ? (
            <div className="card">
              <h3>{zn(sel.name)}</h3>
              <ul className="devlist">{devices(sel, sc).map(dv => <li key={dv.id ?? dv.key}><i className={`dot ${dv.key}`} /><span>{dv.label}</span><span className="muted tn">{dv.detail}</span></li>)}</ul>
              <p className="muted small">Loads are area-based estimates until RVCE meter data arrives.</p>
            </div>
          ) : <p className="muted small">Tip: hover lifts a building; click focuses it.</p>}
        </>,
      }
    }
    case '3': {
      const n = ex.n_qubits
      const ss = d.search?.centralised_full_day
      return {
        answer: <>Each choice is a yes/no question, and the questions multiply fast.</>,
        support: <p>The {zn(ex.zone).toLowerCase()} at {ex.time}{out && ex.slot >= out[0] && ex.slot < out[1] ? ', during the outage' : ''}: its battery over the next 45 minutes and its {ex.var_names.filter(v => v[0] === 'p').length} cables. Each tile is one decision.</p>,
        extra: <Multiply n={n} N={ss?.N_binary} log10={ss?.log10_states} zones={sc.campus.zones.length} slots={ss?.slots ?? 96} />,
      }
    }
    case '4a': {
      const maxQ = d.search ? Math.max(...Object.values(d.search.local_qubo_qubits)) : null
      return {
        answer: <>Each yes/no decision becomes one qubit.</>,
        support: <>
          <p>{ex.n_qubits} decisions, {ex.n_qubits} qubits. A qubit can be 0 and 1 at once, so the circuit works on all {num(2 ** ex.n_qubits)} plans together.</p>
          <p>We never need more than 16 qubits per building{maxQ ? ` (the largest on this campus is ${maxQ})` : ''}, because each building only solves its own problem.</p>
        </>,
        keys: <><Key label="Qubits here">{ex.n_qubits}</Key><Key label="Plans held at once">{num(2 ** ex.n_qubits)}</Key></>,
      }
    }
    case '4b': {
      const rules = rulesFor(d)
      const tex = katex.renderToString(String.raw`E(\mathbf{x}) = \sum_i Q_{ii}\,x_i + \sum_{i<j} 2\,Q_{ij}\,x_i x_j + c,\qquad x_i \in \{0,1\}`, { throwOnError: false, displayMode: true })
      return {
        answer: <>The building’s goals and rules become one cost. Lower is better.</>,
        support: <p>A line joins two qubits whose choices affect each other. Thicker means a stronger effect.</p>,
        extra: <>
          <ul className="rules">{rules.map(r => <li key={r.text}><i style={{ background: r.kind === 'rule' ? C.grid : C.quantum }} />{r.text}</li>)}</ul>
          <div className="legend-row small muted"><span><i style={{ background: C.grid }} />can’t do both (penalty)</span><span><i style={{ background: C.quantum }} />costs that interact</span></div>
          <div className="formula" dangerouslySetInnerHTML={{ __html: tex }} />
          <p className="muted small">This is a QUBO. Breaking a rule adds a large penalty, so plans that break rules are never the cheapest.</p>
        </>,
      }
    }
    case '4c': return {
      answer: <>QAOA turns that cost into a circuit that makes cheap plans more likely.</>,
      support: <ol className="steps">
        <li><b>H</b>: start with every plan equally likely.</li>
        <li><b>Cost layer γ</b>: give each plan a phase set by its cost.</li>
        <li><b>Mixer β</b>: move probability towards the cheaper plans.</li>
        <li>Repeat (p = {q.gammas.length}), then <b>measure</b>.</li>
      </ol>,
      keys: <>
        <Key label="Layers (p)">{q.gammas.length}</Key>
        <Key label="γ" note="trained once, reused"><span className="tn small-kv">{q.gammas.map(g => g.toFixed(2)).join(' · ')}</span></Key>
        <Key label="β"><span className="tn small-kv">{q.betas.map(b => b.toFixed(2)).join(' · ')}</span></Key>
      </>,
      extra: <div className="row"><button className="btn ghost small" onClick={p.replayPulse}>Run the circuit again</button>
        <span className="muted small">{q.simulator}</span></div>,
    }
    case '4d': {
      const shots = ex.qaoa.shots ?? []
      const total = shots.reduce((a, s) => a + s.count, 0)
      const win = shots.find(s => s.bits === ex.qaoa.best_bits)
      const valid = shots.filter(s => s.feasible).reduce((a, s) => a + s.count, 0)
      return {
        answer: <>We measure the circuit {total} times and keep the cheapest plan that breaks no rule.</>,
        support: <p>Each bar is a plan that came up in the measurements; taller means it came up more often. Grey bars break a rule, for example charging and discharging together, and are thrown away. The cheapest valid plan wins even if it is not the tallest bar.</p>,
        extra: <>
          <div className="legend-row"><span><i style={{ background: C.quantum }} />chosen plan</span><span><i style={{ background: '#C9BFFB' }} />other valid plans</span><span><i style={{ background: '#E2E1DB' }} />✕ breaks a rule</span><span><i style={{ background: C.muted, height: 2 }} />random guess</span></div>
          <p className="muted small">Shots measured by the pipeline: {ex.qaoa.backend ?? 'replay'}. Nothing here is re-sampled in the browser.</p>
        </>,
        keys: <>
          <Key label="Chosen plan came up">{win ? `${win.count} of ${total}` : 'not measured'}</Key>
          <Key label="Valid measurements">{valid} of {total}</Key>
          <Key label="Distinct plans seen">{shots.length}</Key>
        </>,
      }
    }
    case '4e': {
      const best = ex.qaoa.best_bits ?? ex.exact.bits
      const yes = ex.var_names.map((v, i) => ({ v, on: best[i] === '1', l: varLabel(v, ex.zone, ex.slot, sc) }))
      const bat = yes.filter(y => y.l.device === 'battery')
      const soc = sc.runs.qgrid.soc[zi]?.[ex.slot]
      return {
        answer: <>The winning bitstring decodes back into what each device does.</>,
        support: <>
          <ul className="actions">
            {yes.filter(y => y.on).map(y => <li key={y.v}><code>q{ex.var_names.indexOf(y.v)}=1</code>{y.l.short}</li>)}
            {bat.length > 0 && bat.every(b => !b.on) && <li><code>battery 0s</code>Battery holds{soc !== undefined ? ` (${Math.round(100 * soc)}% full)` : ''}</li>}
          </ul>
          <p className="muted small">Then the tiles drop back into the {zn(ex.zone).toLowerCase()}: on the map, its cables now carry the agreed flows.</p>
        </>,
        keys: <Key label={`Plan, q0 → q${ex.n_qubits - 1}`}><code className="bits">{best}</code></Key>,
      }
    }
    case '4f': {
      const show = p.showMiss && d.miss ? d.miss : ex
      const ok = show.qaoa.best_bits === show.exact.bits
      const tiers = sc.admm.summary.tiers as Record<string, number> | undefined
      const total = sc.admm.summary.n_local_solves as number | undefined
      return {
        answer: <>Every QAOA answer is checked against an exact search of all {num(2 ** ex.n_qubits)} plans.</>,
        support: <p>If QAOA’s plan isn’t the exact optimum, the next solver takes over: QIEA, then annealing, then exact search. A safety layer checks every command before it reaches a device.</p>,
        extra: <>
          <div className={`card verify ${ok ? 'ok' : 'gap'}`}>
            <div className="vrow head"><span>{zn(show.zone)} · {show.time}</span><span className={`badge ${ok ? 'ok' : 'gap'}`}>{ok ? '✓ match' : 'miss → fallback'}</span></div>
            <div className="vrow"><span className="muted">QAOA plan (cheapest valid of {(show.qaoa.shots ?? []).reduce((a, x) => a + x.count, 0) || 256} shots)</span><code className="bits">{show.qaoa.best_bits ?? 'none feasible'}</code></div>
            <div className="vrow"><span className="muted">Exact optimum</span><code className="bits">{show.exact.bits}</code></div>
            <div className="vrow"><span className="muted">Cost vs optimum</span><span className="tn">{ok ? 'equal' : `${(100 * Math.abs(1 - show.qaoa.approx_ratio)).toFixed(1)}% off`}</span></div>
            <div className="vrow"><span className="muted">Time (Qiskit Aer simulation / exact)</span><span className="tn">{(show.qaoa.time_s * 1000).toFixed(1)} ms / {(show.exact.time_s * 1000).toFixed(1)} ms</span></div>
          </div>
          {d.miss && <button className="btn ghost small" onClick={() => p.setShowMiss(!p.showMiss)}>{p.showMiss ? 'Back to the matching example' : 'Show a case where QAOA misses'}</button>}
          {tiers && total && <p className="small">On this day, whose answer was used: QAOA <b className="tn">{num(tiers.qaoa ?? 0)}</b>, QIEA <b className="tn">{num(tiers.qiea ?? 0)}</b>, annealing <b className="tn">{num(tiers.anneal ?? 0)}</b>, exact <b className="tn">{num(tiers.exact ?? 0)}</b>, out of {num(total)} local solves.</p>}
          <p className="muted small">{show.exact.time_s <= show.qaoa.time_s ? `At ${show.n_qubits} qubits exact search on a laptop is faster than simulating the circuit` : `At ${show.n_qubits} qubits both take milliseconds`}. We claim correctness, not speed.</p>
        </>,
      }
    }
    case '4g': return {
      answer: <>Quantum picks each building’s yes/no plan. Everything around it is classical.</>,
      support: <>
        <p><b style={{ color: C.quantum }}>Quantum (QAOA):</b> choosing the plan inside each building, up to 16 qubits.</p>
        <p><b>Classical:</b> agreement between buildings, checking each answer, fallback solvers and the safety layer.</p>
      </>,
      extra: <div className="honest">{sc.label}. {sc.qiea_label}.</div>,
    }
    case '5': {
      const rounds = sc.admm.iterations[String(d.admmSlot)] ?? []
      const r = rounds[Math.min(p.admmRound, rounds.length - 1)]
      const agreed = r ? Object.values(r.proposals).filter(([a, b]) => Math.abs(a - b) < 1).length : 0
      const sm = sc.admm.summary
      const kill = d.robust.find(x => x.mode === 'in-process' && x.scenario === sc.scenario.key)
      const net = d.robust.find(x => x.mode === 'networked' && x.scenario === sc.scenario.key && x.method === 'OURS')
      return {
        answer: <>Buildings agree on what each cable carries by talking only to their neighbours.</>,
        support: <p>At {slotT(d.admmSlot)}, both ends of each cable propose a flow every round. Red means they disagree; blue means they agree. There is no central computer.</p>,
        keys: <>
          <Key label="Round"><span className="tn">{(r?.k ?? 0) + 1} / {rounds.length}</span></Key>
          <Key label="Cables agreed"><span className="tn">{agreed} / {sc.campus.lines.length}</span></Key>
        </>,
        extra: <>
          <ResidualChart rounds={rounds} k={p.admmRound} />
          <div className="row">
            <button className="btn ghost small" onClick={() => p.setAdmmRound(Math.max(0, p.admmRound - 1))} disabled={p.admmRound === 0}>‹ round</button>
            <button className="btn ghost small" onClick={() => p.setAdmmRound(Math.min(rounds.length - 1, p.admmRound + 1))} disabled={p.admmRound >= rounds.length - 1}>round ›</button>
            <button className="btn ghost small" onClick={() => p.setAdmmRound(0)}>replay</button>
          </div>
          <p className="small muted">Disagreement (kW) per round. Over the whole day, all cables agreed in {Math.round(96 * (sm.admm_convergence_rate ?? 0))} of 96 slots. In the rest, each remaining cable was settled between its two buildings ({num(sm.resolved_bilateral ?? 0)} times), which is always safe.</p>
          <div className="card">
            <div className="row"><b>Remove a building</b><button className={`btn small ${p.killed ? 'primary' : 'ghost'}`} onClick={() => p.setKilled(p.killed ? null : 'heavy_labs')}>{p.killed ? `Bring ${zn('heavy_labs').toLowerCase()} back` : `Take ${zn('heavy_labs').toLowerCase()} offline`}</button></div>
            {p.killed && <p className="small">Its cables go dark and the others carry on. Measured in the replay: the schedule stayed {kill?.feasible === 'True' ? 'feasible' : kill ? 'infeasible' : 'untested'}{net?.recovery_time_s ? `, neighbours noticed in ${Number(net.recovery_time_s).toFixed(1)} s (networked run)` : ''}{kill?.slots_to_reconverge ? `, and full agreement returned after ${Math.round(Number(kill.slots_to_reconverge))} slots` : ''}.</p>}
          </div>
        </>,
      }
    }
    case '6': {
      const qg = campusSoc(sc, 'qgrid'), sq = campusSoc(sc, 'status_quo')
      const o = out?.[0] ?? 72
      return {
        answer: <>Q-Grid fills the batteries before the evening outage and uses them while the grid is down.</>,
        support: <p>Batteries next to each building fill and empty through the day. The chart shows the campus battery level, status quo against Q-Grid, with diesel and the pump on the same time axis.</p>,
        keys: <>
          <Key label={`Battery at ${slotT(o)}`}><span className="tn">{pct(100 * qg[o])}</span><span className="vs tn"> vs {sq.length ? pct(100 * sq[o]) : '–'}</span></Key>
          {(() => { const o6 = sc.benchmark.find(r => r.method === 'OURS' && r.price_scenario === 'A'), z6 = sc.benchmark.find(r => r.method === 'B0' && r.price_scenario === 'A'); return o6 && z6 && <Key label="Diesel hours"><span className="tn">{o6.dg_hours.toFixed(2)}</span><span className="vs tn"> vs {z6.dg_hours.toFixed(2)}</span></Key> })()}
        </>,
        extra: <>
          <SocChart sc={sc} t={p.t} />
          <div className="row"><button className="btn ghost small" onClick={p.onPlay}>{p.playing ? 'Pause' : 'Replay the day'}</button><span className="muted small tn">{slotT(Math.floor(p.t))}</span></div>
        </>,
      }
    }
    case '7a': {
      const rows = d.summary.filter(r => r.day_set === 'eval30_mean' && r.price_scenario === 'A')
      const get = (m: string) => rows.find(r => r.method === m)
      const ours30 = get('OURS')
      const order = ['B0', 'B1', 'B3', 'B5', 'OURS', 'OURS-QIEA']
      const bars = order.map(m => get(m)).filter(Boolean).map(r => ({ method: r!.method, name: METHOD[r!.method] ?? r!.method, gap: Number(r!.gap_to_B4_pct), ours: r!.method.startsWith('OURS') }))
      const bm = (m: string) => sc.benchmark.find(r => r.method === m && r.price_scenario === 'A')
      const B0 = bm('B0'), OU = bm('OURS'), B4 = bm('B4')
      const tiers = sc.admm.summary.tiers as Record<string, number> | undefined
      const solves = sc.admm.summary.n_local_solves as number | undefined
      const src = `results/benchmark.csv: scenario=${sc.scenario.key}, price_scenario=A`
      const prov = (m: string, k: string) => ({ label: `${METHOD[m] ?? m} · ${k}`, unit: '', formula: FORMULA[k] ?? k, file: 'results/benchmark.csv', fn: 'scripts/run_benchmark.py', row: `${src}, method=${m}` })
      if (!B0 || !OU || !B4) return { answer: <>Results for this day are in the Verify tab.</> }
      const dCost = 100 * (OU.cost_rs / B0.cost_rs - 1)
      const outage = B0.critical_downtime_h > 0 || OU.critical_downtime_h > 0
      return {
        answer: outage
          ? <>{out ? 'In the outage' : 'On this day'}, critical loads go without power for {OU.critical_downtime_h.toFixed(1)} h instead of {B0.critical_downtime_h.toFixed(1)} h.</>
          : <>No critical load is lost on this day{B0.dg_hours > 0 || OU.dg_hours > 0 ? `; Q-Grid runs diesel ${OU.dg_hours.toFixed(1)} h instead of ${B0.dg_hours.toFixed(1)} h` : ''}, and Q-Grid lands {Number(OU.gap_to_B4_pct).toFixed(1)}% from the best possible plan.</>,
        support: <p>Every method ran on the same day, data and constraints ({fmtDate(sc.scenario.date)}{out ? `, BESCOM down ${slotT(out[0])}–${slotT(out[1])}` : ''}).</p>,
        keys: <>
          <Key label="Critical-load downtime" note={`optimum ${B4.critical_downtime_h.toFixed(1)} h`}><N v={`${B0.critical_downtime_h.toFixed(1)} → ${OU.critical_downtime_h.toFixed(1)} h`} info={prov('OURS', 'critical_downtime_h')} /></Key>
          <Key label="Diesel running"><N v={`${B0.dg_hours.toFixed(2)} → ${OU.dg_hours.toFixed(2)} h`} info={prov('OURS', 'dg_hours')} /></Key>
          <Key label="Gap to optimum" note="this day"><N v={`${Number(OU.gap_to_B4_pct).toFixed(1)}%`} info={prov('OURS', 'gap_to_B4_pct')} /></Key>
          {tiers && solves && <Key label="QAOA answer used" note={`all ${num(solves)} checked vs exact`}>{pct(100 * (tiers.qaoa ?? 0) / solves)}</Key>}
        </>,
        extra: <>
          <p className="secondary small">Cost of the day {priceStatus && <Pending what="Tariff" />}: <span className="tn"><N v={rs(B0.cost_rs)} info={prov('B0', 'cost_rs')} /> → <N v={rs(OU.cost_rs)} info={prov('OURS', 'cost_rs')} /> ({dCost >= 0 ? '+' : ''}{dCost.toFixed(1)}%)</span>{dCost > 0 && outage ? ', because diesel and batteries are spent keeping critical loads on' : ''}. Final once the official BESCOM/KERC tariff is added.</p>
          <h3 className="sub">Gap to the central optimum, 30-day mean {priceStatus && <Pending what="Tariff" />}</h3>
          <GapBars rows={bars} />
          <p className="muted small">Q-Grid {ours30 ? `${Number(ours30.gap_to_B4_pct).toFixed(1)}%` : '–'} above optimum over 30 modelled days. GA/PSO, CO₂ and run times are in the Verify tab; click any figure for its source.</p>
        </>,
      }
    }
    case '7b': {
      const qs = d.search ? Object.values(d.search.local_qubo_qubits) : []
      return {
        answer: <>As the network grows, each building’s problem stays the same size.</>,
        support: <>
          <p>More buildings means more neighbours to agree with, not more qubits per building. On this campus each zone needs {qs.length ? `${Math.min(...qs)}–${Math.max(...qs)}` : '≤16'} qubits.</p>
          <ul className="levels">
            <li><b>RVCE</b> {sc.campus.zones.length} zones, {sc.campus.lines.length} cables: the modelled campus.</li>
            <li><b>Cluster of campuses</b>: more zones, the same per-zone qubit count.</li>
            <li><b>City feeder</b>: campuses agree flows over the feeder the way zones agree over cables.</li>
          </ul>
        </>,
        extra: <p className="honest">The cluster and feeder views are an illustration, not results. New campuses can be modelled with <code>scripts/new_campus.py</code>.</p>,
      }
    }
  }
  return { answer: <>{STOPS.find(x => x.id === p.stop)?.title}</> }
}

const SCENARIO = (sc: StoryData['sc']) => ({ outage_fest: 'fest', fest: 'fest', teaching: 'teaching', exam_week: 'exam-week', vacation: 'vacation', monsoon: 'monsoon' } as Record<string, string>)[sc.scenario.key] ?? sc.scenario.key

/** Plain-English rules present in the worked example's QUBO (from the variable structure in qgrid/qubo.py). */
function rulesFor(d: StoryData): { text: string; kind: 'rule' | 'cost' }[] {
  const { sc, example: ex } = d
  const names = ex.var_names
  const zone = sc.campus.zones.find(z => z.name === ex.zone)!
  const up = sc.slots.grid_up[ex.slot] === 1
  const out: { text: string; kind: 'rule' | 'cost' }[] = []
  if (up) out.push({ text: `Buying grid power costs Rs ${sc.slots.price_import[ex.slot]}/kWh; selling earns Rs ${sc.slots.price_export[ex.slot]}/kWh`, kind: 'cost' })
  else out.push({ text: zone.critical_frac > 0 ? 'Grid is down: critical load must be served' : 'Grid is down: unserved load costs the most', kind: 'rule' })
  if (names.some(v => /^c\d$/.test(v))) {
    out.push({ text: 'Battery can’t charge and discharge in the same slot', kind: 'rule' })
    out.push({ text: 'Battery stays between its minimum and maximum charge', kind: 'rule' })
    out.push({ text: 'Energy kept in the battery is worth money later today', kind: 'cost' })
  }
  if (names.some(v => /^p\d+$/.test(v))) {
    out.push({ text: 'A cable can’t send and receive at once', kind: 'rule' })
    out.push({ text: 'Stay close to what the neighbours proposed', kind: 'cost' })
  }
  if (names.includes('g')) out.push({ text: 'Running diesel costs fuel', kind: 'cost' })
  if (names.includes('w')) out.push({ text: 'Keep the tank within its levels', kind: 'rule' })
  return out
}

/** Step 3 counter: decisions -> plans for one building -> plans for the campus day. */
function Multiply({ n, N: Nb, log10, zones, slots }: { n: number; N?: number; log10?: number; zones: number; slots: number }) {
  const r = reducedMotion()
  const item = (k: number) => ({ initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 }, transition: { delay: r ? 0 : 0.5 + k * 0.7, duration: r ? 0 : 0.5 } })
  return (
    <div className="multiply">
      <motion.div {...item(0)} className="mrow"><b className="big tn">{n}</b><span>yes/no decisions for one building, one slot</span></motion.div>
      <motion.div {...item(1)} className="mrow"><b className="big tn">2<sup>{n}</sup> = {num(2 ** n)}</b><span>possible plans for that building</span></motion.div>
      {Nb && log10 && <motion.div {...item(2)} className="mrow"><b className="big tn">2<sup>{num(Nb)}</sup> ≈ 10<sup>{num(Math.floor(log10))}</sup></b>
        <span>plans for the whole campus over one day ({zones} zones × {slots} slots, solved together)</span></motion.div>}
      <motion.p {...item(3)} className="muted small">Checking them one by one is impossible, so each building solves only its own {num(2 ** n)} and then agrees with its neighbours.</motion.p>
    </div>
  )
}


/* ----------------------------------------------------------------------------------------------- optimiser v2 */
const V2NAME: Record<string, string> = { B0: 'Status quo', V1: 'Old Q-Grid (v1)', 'V2-QAOA': 'Q-Grid v2 (QAOA master)',
  'V2-QIEA': 'Q-Grid v2 (QIEA master)', 'V2-EXACT': 'Q-Grid v2 (exact master)', 'B4-DC': 'Best possible (central)',
  'V2-QAOA-FC': 'v2, solar forecast', B3: 'Per-zone MILP', B1: 'Rule-based' }

/** Story text when optimiser v2 results are in the replay; null falls back to the v1 text. */
function contentV2(p: PanelProps): Body | null {
  const { d } = p
  const { sc, example: ex } = d
  const v2 = d.v2, X = d.v2ex
  const row = (m: string) => v2?.rows.find(r => r.method === m)
  if (p.stop === '7a' && v2 && row('V2-QAOA') && row('B4-DC')) return results7(p)
  if (p.stop === '5b' && !X) return { answer: <>The two halves exchange prices and plans until their bounds meet.</>,
    support: <p>Run the v2 benchmark (<code>scripts/run_benchmark_v2.py</code>) and <code>make replay</code> to see the worked example.</p> }
  if (!X || !v2) return null
  const B = X.block
  const hrs = B.hours
  const span = `${hourLabel(hrs[0])}–${hourLabel(hrs[hrs.length - 1] + 1)}`
  const nb = Object.values(X.binaries).reduce((a, b) => a + b, 0)
  const nz = X.binaries[ex.zone]
  const shots = B.qaoa.shots ?? []
  const total = shots.reduce((a, s) => a + s.count, 0)
  switch (p.stop) {
    case '3': return {
      answer: <>Each hour of the next 24 h is a set of yes/no choices, and they multiply fast.</>,
      support: <p>At {X.time}, the {zn(ex.zone).toLowerCase()} decides for every clock hour: is the pump on? Other buildings decide diesel on/off, whether the battery may charge or discharge, and when flexible jobs start.</p>,
      extra: <div className="multiply">
        <div className="mrow"><b className="big tn">{nz}</b><span>yes/no choices for the {zn(ex.zone).toLowerCase()} over the next 24 h</span></div>
        <div className="mrow"><b className="big tn">{nb}</b><span>for the whole campus ({sc.campus.zones.length} buildings)</span></div>
        <div className="mrow"><b className="big tn">2<sup>{nb}</sup> ≈ 10<sup>{Math.floor(nb * Math.log10(2))}</sup></b><span>possible on/off plans for the campus day</span></div>
        <p className="muted small">The tiles show one block: {B.n_qubits} hours of {zn(ex.zone).toLowerCase()} pumping, {span}.</p>
      </div>,
    }
    case '4a': return {
      answer: <>A block of {B.n_qubits} hourly choices becomes {B.n_qubits} qubits.</>,
      support: <>
        <p>Quantum solves the on/off commitment, one block of up to 16 qubits at a time: here, pumping {span}. The circuit holds all {num(2 ** B.n_qubits)} plans for the block at once.</p>
        <p>Battery power, diesel output and cable flows are not on/off choices; they stay with classical solvers (step 5).</p>
      </>,
      keys: <><Key label="Qubits in this block">{B.n_qubits}</Key><Key label="Largest block allowed">16</Key></>,
    }
    case '4b': return {
      answer: <>The block’s costs and rules become one cost. Lower is better.</>,
      support: <p>Each pumping hour has a price, taken from the continuous half’s latest Benders cut. Lines join hours that affect each other: the tank level after every hour depends on all the pumping before it.</p>,
      extra: <>
        <ul className="rules">
          <li><i style={{ background: C.quantum }} />Energy for pumping, priced by the latest cut from the LP</li>
          <li><i style={{ background: C.quantum }} />Water kept in the tank at the end is worth money later</li>
          <li><i style={{ background: C.grid }} />Keep the tank between its minimum and maximum (penalty)</li>
        </ul>
        <p className="muted small">This is a QUBO. Plans that break a rule get a large penalty, and every candidate is re-scored with the true master objective.</p>
      </>,
    }
    case '4d': {
      const win = shots.find(s => s.bits === B.qaoa.best_bits)
      const valid = shots.filter(s => s.feasible).reduce((a, s) => a + s.count, 0)
      return {
        answer: <>We measure the circuit {total} times and keep the cheapest plan that keeps the tank in range.</>,
        support: <p>Taller bars came up more often. Grey bars would let the tank overflow or run dry and are thrown away. The cheapest valid plan wins even if it is not the tallest bar.</p>,
        extra: <>
          <div className="legend-row"><span><i style={{ background: C.quantum }} />chosen plan</span><span><i style={{ background: '#C9BFFB' }} />other valid plans</span><span><i style={{ background: '#E2E1DB' }} />✕ breaks a rule</span><span><i style={{ background: C.muted, height: 2 }} />random guess</span></div>
          <p className="muted small">Shots measured by the pipeline: {B.qaoa.backend}. Nothing here is re-sampled in the browser.</p>
        </>,
        keys: <>
          <Key label="Chosen plan came up">{win ? `${win.count} of ${total}` : 'not measured'}</Key>
          <Key label="Valid measurements">{valid} of {total}</Key>
          <Key label="Distinct plans seen">{shots.length}</Key>
        </>,
      }
    }
    case '4e': {
      const best = B.qaoa.best_bits ?? B.exact.bits
      const on = B.var_names.filter((_, i) => best[i] === '1').map(v => Number(v.split('@')[1]))
      return {
        answer: <>The winning bitstring decodes into an hour-by-hour plan.</>,
        support: <>
          <p>Pump on at: {on.length ? on.map(h => hourLabel(h)).join(', ') : 'no hour in this block'}.</p>
          <p className="muted small">All buildings’ blocks together make the 24 h commitment. Only the current slot is carried out; 15 minutes later the plan is made again with new data.</p>
        </>,
        keys: <Key label={`Plan, ${hourLabel(hrs[0])} →`}><code className="bits">{best}</code></Key>,
      }
    }
    case '4f': {
      const ok = B.qaoa.best_bits === B.exact.bits
      const qa = row('V2-QAOA')
      return {
        answer: <>Every QAOA block is checked against an exact search, and every master against an exact MILP.</>,
        support: <p>QAOA proposes; a proposal is kept only if it lowers the true master cost. The exact master runs every time: it gives the lower bound and the reference. A safety layer checks every command before it reaches a device.</p>,
        extra: <>
          <div className={`card verify ${ok ? 'ok' : 'gap'}`}>
            <div className="vrow head"><span>{zn(ex.zone)} · {X.time} · {span}</span><span className={`badge ${ok ? 'ok' : 'gap'}`}>{ok ? '✓ match' : 'differs'}</span></div>
            <div className="vrow"><span className="muted">QAOA plan (cheapest valid of {total} shots)</span><code className="bits">{B.qaoa.best_bits ?? 'none valid'}</code></div>
            <div className="vrow"><span className="muted">Exact optimum of the block</span><code className="bits">{B.exact.bits}</code></div>
          </div>
          {qa && <p className="small">On this day: QAOA’s best measured block = exact block optimum in <b className="tn">{pct(100 * Number(qa.qaoa_block_opt_share ?? 0), 1)}</b> of {num(Number(qa.qaoa_block_solves ?? 0))} blocks; QAOA-driven masters reached the exact master in <b className="tn">{pct(100 * Number(qa.master_opt_share ?? 0), 1)}</b>.</p>}
          <p className="muted small">At these sizes exact search is faster. We claim correctness, not speed.</p>
        </>,
      }
    }
    case '4g': return {
      answer: <>Quantum picks the hourly on/off commitment. Everything continuous is classical.</>,
      support: <>
        <p><b style={{ color: C.quantum }}>Quantum (QAOA, simulated):</b> diesel on/off, battery charge-or-discharge mode, pump hours, job start times — blocks of up to 16 qubits per building.</p>
        <p><b>Classical:</b> battery kW, diesel kW, cable flows, grid import and peak (an LP, agreed by neighbours with ADMM), Benders cuts, exact checks, the safety layer.</p>
      </>,
      extra: <div className="honest">{sc.label}. {sc.qiea_label}.</div>,
    }
    case '5': {
      const rounds = d.admmRounds
      const r = rounds[Math.min(p.admmRound, rounds.length - 1)]
      const agreed = r ? Object.values(r.proposals).filter(([a, b]) => Math.abs(a - b) < 1).length : 0
      const qa = row('V2-QAOA'), v1 = row('V1')
      return {
        answer: <>Neighbours agree on every cable’s flow by trading proposals. This half is convex, so the trading is guaranteed to converge given enough rounds.</>,
        support: <p>At {X.time}, with the on/off plan fixed, each building solves its own LP for battery, diesel and grid, and both ends of each cable propose a flow. Red means they still disagree. There is no central computer.</p>,
        keys: <>
          <Key label="Round" note={X.benders[0]?.admm_converged ? 'reached tolerance' : 'stopped at the round cap'}><span className="tn">{(r?.k ?? 0) + 1} / {X.benders[0]?.admm_iters ?? rounds.length}</span></Key>
          <Key label="Cables agreed"><span className="tn">{agreed} / {sc.campus.lines.length}</span></Key>
        </>,
        extra: <>
          <ResidualChart rounds={rounds} k={p.admmRound} />
          <div className="row">
            <button className="btn ghost small" onClick={() => p.setAdmmRound(Math.max(0, p.admmRound - 1))} disabled={p.admmRound === 0}>‹ round</button>
            <button className="btn ghost small" onClick={() => p.setAdmmRound(Math.min(rounds.length - 1, p.admmRound + 1))} disabled={p.admmRound >= rounds.length - 1}>round ›</button>
            <button className="btn ghost small" onClick={() => p.setAdmmRound(0)}>replay</button>
          </div>
          <p className="small muted">Largest disagreement on any cable (kW) per round{rounds.length > 40 ? ', sampled' : ''}. Over this day, v2’s ADMM reached tolerance in {qa ? pct(100 * Number(qa.admm_converged_rate ?? 0)) : '–'} of runs; the old binary negotiation fully agreed in {v1 ? pct(100 * Number(v1.admm_converged_rate ?? 0)) : '–'} of slots. When the round cap is hit, each building fixes the agreed flows and re-solves its own LP, so the plan it applies always balances.</p>
        </>,
      }
    }
    case '5b': {
      const it = X.benders
      const last = it[it.length - 1]
      return {
        answer: <>The two halves talk through Benders cuts until the cost bounds nearly meet.</>,
        support: <>
          <p>The quantum half proposes an on/off plan. The classical half prices it: each building’s LP says what that plan costs and, from its duals, how the cost would change if any hour flipped. That price list is a <b>cut</b>; it goes back to the building’s master, which then avoids plans the cuts show are expensive.</p>
          <p className="muted small">Upper bound: the best plan found so far, priced by the LPs. Lower bound: the exact master with all cuts — no plan can be cheaper.</p>
        </>,
        keys: <>
          <Key label="Benders rounds">{it.length}</Key>
          <Key label="Gap between bounds">{last ? pct(last.gap_pct, 2) : '–'}</Key>
          <Key label="Cuts per building">{last?.cuts_per_building ?? '–'}</Key>
        </>,
        extra: <>
          <BoundsChart iters={it} />
          <p className="muted small">The run stops at a 0.5 % gap or after {it.length >= 6 ? 6 : it.length} rounds. {X.note.charAt(0).toUpperCase() + X.note.slice(1)}.</p>
        </>,
      }
    }
  }
  return null
}

function results7(p: PanelProps): Body {
  const { d } = p
  const sc = d.sc, v2 = d.v2!
  const row = (m: string) => v2.rows.find(r => r.method === m)
  const B0 = row('B0'), V1 = row('V1'), QA = row('V2-QAOA'), EX = row('V2-EXACT'), OPT = row('B4-DC')!
  const priceStatus = sc.price_status !== 'REAL' || v2.tariff_status !== 'REAL'
  const prov = (m: string, k: string) => ({ label: `${V2NAME[m] ?? m} · ${k}`, unit: '', formula: k, file: 'results/v2/benchmark_v2.csv',
    fn: 'scripts/run_benchmark_v2.py', row: `scenario=${sc.scenario.key}, method=${m}` })
  const bars = ['B0', 'V1', 'V2-QAOA', 'V2-EXACT'].map(row).filter(Boolean).map(r => ({ method: r!.method, name: V2NAME[r!.method] ?? r!.method,
    gap: Number(r!.gap_to_opt_pct), ours: r!.method.startsWith('V2') }))
  const dc = QA && B0 ? Number(B0.demand_charge_rs) - Number(QA.demand_charge_rs) : null
  return {
    answer: QA && V1 ? <>v2 lands {Number(QA.gap_to_opt_pct).toFixed(1)}% from the best possible plan, against {Number(V1.gap_to_opt_pct).toFixed(1)}% for v1.</> : <>v1 vs v2 vs the best possible plan.</>,
    support: <p>Same day, data and constraints for every method ({fmtDate(sc.scenario.date)}). “Best possible” is a central MILP that sees everything; v2 gets close while staying decentralised.</p>,
    keys: <>
      {QA && B0 && <Key label="Critical-load downtime" note={`v1 ${Number(V1?.critical_downtime_h ?? NaN).toFixed(1)} h · best ${Number(OPT.critical_downtime_h).toFixed(1)} h`}><N v={`${Number(B0.critical_downtime_h).toFixed(1)} → ${Number(QA.critical_downtime_h).toFixed(1)} h`} info={prov('V2-QAOA', 'critical_downtime_h')} /></Key>}
      {QA && B0 && <Key label="Diesel running"><N v={`${Number(B0.dg_hours).toFixed(2)} → ${Number(QA.dg_hours).toFixed(2)} h`} info={prov('V2-QAOA', 'dg_hours')} /></Key>}
      {QA && B0 && <Key label="Peak demand" note={`best ${num(Number(OPT.peak_kva))} kVA`}><N v={`${num(Number(B0.peak_kva))} → ${num(Number(QA.peak_kva))} kVA`} info={prov('V2-QAOA', 'peak_kva')} /></Key>}
      {QA && <Key label="Masters solved optimally by QAOA" note="each checked vs exact">{pct(100 * Number(QA.master_opt_share ?? 0))}</Key>}
    </>,
    extra: <>
      <p className="secondary small">Cost of the day incl. demand charge {priceStatus && <Pending what="Tariff and demand charge" />}: <span className="tn">{B0 && QA ? <><N v={rs(Number(B0.cost_incl_demand_rs))} info={prov('B0', 'cost_incl_demand_rs')} /> → <N v={rs(Number(QA.cost_incl_demand_rs))} info={prov('V2-QAOA', 'cost_incl_demand_rs')} /></> : '–'}</span>{dc !== null ? `; demand charge ${dc >= 0 ? 'down' : 'up'} ${rs(Math.abs(dc))}/day` : ''}. Final once the official BESCOM/KERC tariff is added.</p>
      <h3 className="sub">Gap to the best possible plan, this day</h3>
      <GapBars rows={bars} />
      <p className="muted small">Gap includes the value of lost load and the demand charge. {EX ? `With an exact master v2 lands ${Number(EX.gap_to_opt_pct).toFixed(1)}%.` : ''} Full tables in Verify and docs/results_v2.md.</p>
    </>,
  }
}
