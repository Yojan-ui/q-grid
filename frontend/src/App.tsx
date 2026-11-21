import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import gsap from 'gsap'
import * as THREE from 'three'
import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { API, getCSV, getJSON, liveAvailable, MissingReplay, missingReplayFiles, type Index, type QaoaFile, type Scenario } from './lib/data'
import { C, rs } from './lib/theme'
import { CampusScene, type Anchors } from './scene/CampusScene'
import { ProvProvider, N, FORMULA } from './panels/Prov'
import { MetricsTable, RuleBox, SolveLive, Stress } from './panels/Judge'
import { Sandbox } from './panels/Sandbox'
import { DataBadge, DayChart, Decisions, LabelLayer, Legend, NowCard, Timeline, fmtDate, scenarioName, zn } from './panels/Hud'

const QuboTerrain = lazy(() => import('./scene/QuboTerrain').then(m => ({ default: m.QuboTerrain })))
const QubitChips = lazy(() => import('./scene/QuboTerrain').then(m => ({ default: m.QubitChips })))
const QaoaPanel = lazy(() => import('./panels/Circuit').then(m => ({ default: m.QaoaPanel })))
const BarRace = lazy(() => import('./scene/BarRace').then(m => ({ default: m.BarRace })))

type Mode = 'story' | 'explore' | 'judge' | 'sandbox'
const MODES: [Mode, string][] = [['story', 'Story'], ['explore', 'Explore'], ['judge', 'Judge'], ['sandbox', 'What-if']]
const CH = ['The problem', 'Decisions become qubits', 'The cost landscape', 'Quantum solve', 'Agreement without a centre', 'Result']
const reduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
const HOME: [number, number, number] = [260, 300, 380]

function CameraRig({ pos, target, free }: { pos: [number, number, number]; target: [number, number, number]; free: boolean }) {
  const { camera } = useThree()
  const tgt = useRef(new THREE.Vector3(...target))
  const ctl = useRef<any>(null)
  useEffect(() => {
    const d = reduced ? 0 : 0.8
    gsap.to(camera.position, { x: pos[0], y: pos[1], z: pos[2], duration: d, ease: 'power2.inOut' })
    gsap.to(tgt.current, { x: target[0], y: target[1], z: target[2], duration: d, ease: 'power2.inOut',
      onUpdate: () => { ctl.current?.target.copy(tgt.current); ctl.current?.update() } })
  }, [pos.join(), target.join()])
  return <OrbitControls ref={ctl} enabled={free} enableDamping dampingFactor={0.08} makeDefault
    minDistance={90} maxDistance={1100} maxPolarAngle={Math.PI / 2 - 0.12} minPolarAngle={0.15} />
}

export default function App() {
  const [idx, setIdx] = useState<Index | null>(null)
  const [key, setKey] = useState('')
  const [sc, setSc] = useState<Scenario | null>(null)
  const [q, setQ] = useState<QaoaFile | null>(null)
  const [extra, setExtra] = useState<{ sandbox: any; rules: any[]; robust: Record<string, string>[] }>({ sandbox: null, rules: [], robust: [] })
  const [mode, setMode] = useState<Mode>('story')
  const [ch, setCh] = useState(0)
  const [t, setT] = useState(0)
  const [playing, setPlaying] = useState(!reduced)
  const [speed, setSpeed] = useState(1)
  const [narrate, setNarrate] = useState(false)
  const [killed, setKilled] = useState<string | null>(null)
  const [online, setOnline] = useState(false)
  const [probs, setProbs] = useState<Float64Array | null>(null)
  const [price, setPrice] = useState('A')
  const [focus, setFocus] = useState<string | null>(null)
  const [liveLog, setLiveLog] = useState<string[]>([])
  const [rec, setRec] = useState<MediaRecorder | null>(null)
  const [missing, setMissing] = useState<string[] | null>(null)
  const anchors = useRef<Anchors>({ pts: {}, dist: 0, w: 0, h: 0 })

  useEffect(() => {
    getJSON<Index>('index.json').then(async i => {
      const miss = await missingReplayFiles(i.scenarios.flatMap(s => [`scenario_${s.key}.json`, `qaoa_${s.key}.json`]))
      if (miss.length) { setMissing(miss); return }
      setIdx(i); setKey(i.headline)
    }).catch(async e => {
      if (e instanceof MissingReplay) setMissing([...e.files, ...(await missingReplayFiles(['sandbox.json', 'rules.json']))])
      else setMissing([String(e)])
    })
    getJSON<any>('sandbox.json').then(s => setExtra(x => ({ ...x, sandbox: s }))).catch(() => {})
    getJSON<any[]>('rules.json').then(r => setExtra(x => ({ ...x, rules: r }))).catch(() => {})
    getCSV('robustness.csv').then(r => setExtra(x => ({ ...x, robust: r })))
    if (new URLSearchParams(location.search).has('live')) liveAvailable().then(setOnline)
  }, [])
  useEffect(() => {
    if (!key) return
    setSc(null); setQ(null)
    getJSON<Scenario>(`scenario_${key}.json`).then(s => { setSc(s); getJSON<QaoaFile>(s.qaoa_file).then(setQ).catch(() => {}) })
      .catch(e => setMissing(e instanceof MissingReplay ? e.files : [String(e)]))
  }, [key])

  const outageSlot = useMemo(() => { const i = sc?.slots.grid_up.indexOf(0) ?? -1; return i >= 0 ? i + 2 : 76 }, [sc])
  useEffect(() => {
    if (!sc || mode !== 'story') return
    if (ch === 0) setT(0)
    if (ch >= 1 && ch <= 3) setT(q?.slot ?? 76)
    if (ch === 4) setT(outageSlot)
  }, [ch, mode, sc, q, outageSlot])
  useEffect(() => {
    if (!playing || !(mode === 'explore' || (mode === 'story' && (ch === 0 || ch === 5)))) return
    let raf = 0, last = performance.now()
    const tick = (now: number) => {
      const dt = (now - last) / 1000; last = now
      setT(x => {
        const nx = x + dt * 4 * speed
        if (nx >= 95.99) { if (mode === 'story' && ch === 0) setCh(1); return mode === 'story' ? 95.99 : 0 }
        return nx
      })
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing, mode, ch, speed])
  useEffect(() => {
    if (mode !== 'story' || !playing || ch === 0 || ch === 5) return
    const id = setTimeout(() => setCh(c => Math.min(5, c + 1)), (ch === 3 ? 9000 : 8000) / speed)
    return () => clearTimeout(id)
  }, [ch, mode, playing, speed])

  const caption = useMemo(() => {
    if (!sc) return ''
    const sq = sc.runs.status_quo?.metrics ?? {}, qg = sc.runs.qgrid.metrics
    const out = sc.scenario.outage ? `BESCOM supply fails from ${sc.scenario.outage[0]} to ${sc.scenario.outage[1]}.` : 'Grid supply is available all day.'
    return [
      `${out} Without coordination, noon solar is sold cheaply, the evening is bought expensively, and each building rides out the outage alone: ${rs(sq.cost_rs)} for the day and ${sq.critical_downtime_h?.toFixed(2)} h with critical loads unserved.`,
      `Every 15 minutes each building chooses: charge or discharge, diesel on or off, pump, flexible loads, and how much to share with neighbours. For ${zn(q?.zone ?? 'hostels')} at ${sc.slots.t[q?.slot ?? 76]} that is ${q?.n_qubits ?? '…'} on/off variables — one qubit each.`,
      `Every combination gets a cost: rupees plus penalties for broken rules. Low ground is a cheap, valid schedule; red ridges break a constraint. The white cell is the exact optimum, found by checking all ${(2 ** (q?.n_qubits ?? 0)).toLocaleString('en-IN')} combinations.`,
      `QAOA, simulated, shifts probability towards low cost one layer at a time. The best of 256 samples is checked against the exact optimum; if it misses, the solve falls back to QIEA, then annealing, then exact search.`,
      `There is no central computer. Each building agrees tie-line flows with its neighbours only. ${Math.round(100 * (sc.admm.summary.admm_convergence_rate ?? 0))}% of slots reached full agreement; the rest were settled pairwise or set to zero, which is always safe.`,
      `With coordination: ${rs(qg.cost_rs)} and ${qg.critical_downtime_h?.toFixed(2)} h of critical downtime, against ${rs(sq.cost_rs)} and ${sq.critical_downtime_h?.toFixed(2)} h before.${sc.price_status === 'REAL' ? '' : ' Prices are stand-ins until the official tariff arrives.'}`,
    ][ch]
  }, [sc, q, ch])
  useEffect(() => {
    if (!narrate || mode !== 'story' || !caption || !('speechSynthesis' in window)) return
    speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(caption))
  }, [caption, narrate, mode])

  const onLayer = useCallback((p: Float64Array) => setProbs(p), [])
  const zonePos = (name?: string | null): [number, number, number] => {
    const z = sc?.campus.zones.find(x => x.name === name)
    return z ? [z.cx, 0, -z.cy] : [0, 0, 0]
  }
  const story = mode === 'story'
  const scene: 'campus' | 'terrain' | 'result' = story && (ch === 2 || ch === 3) ? 'terrain' : story && ch === 5 ? 'result' : 'campus'
  const zp = zonePos(story && ch === 1 ? q?.zone : focus)
  const cams: [number, number, number][][] = [[HOME, [0, 0, 0]], [[zp[0] + 110, 120, zp[2] + 140], zp], [[120, 130, 160], [0, 10, 0]],
    [[100, 115, 145], [0, 20, 0]], [[200, 360, 300], [0, 0, 0]], [[0, 40, 80], [0, 18, 0]]]
  const [camPos, camTgt] = story ? cams[ch] : focus && mode === 'explore' ? [[zp[0] + 140, 160, zp[2] + 180] as [number, number, number], zp] : [HOME, [0, 0, 0] as [number, number, number]]

  const startLive = (kill: string | null) => {
    setKilled(kill)
    if (!online) return
    setLiveLog([])
    const ws = new WebSocket(API.replace('http', 'ws') + '/live')
    ws.onopen = () => ws.send(JSON.stringify({ scenario: key, kill_zone: kill, kill_slot: Math.floor(t) }))
    ws.onmessage = e => { const d = JSON.parse(e.data); setLiveLog(l => [...l.slice(-10), `${d.t}: ${d.iters} rounds, ${d.converged ? 'agreed' : 'settled'} in ${(d.time_s * 1000).toFixed(0)} ms`]) }
  }
  const record = () => {
    if (rec) { rec.stop(); setRec(null); return }
    const c = document.querySelector('canvas') as HTMLCanvasElement | null
    if (!c) return
    const r = new MediaRecorder(c.captureStream(30), { mimeType: 'video/webm' })
    const chunks: Blob[] = []
    r.ondataavailable = e => chunks.push(e.data)
    r.onstop = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob(chunks, { type: 'video/webm' })); a.download = 'qgrid-demo.webm'; a.click() }
    r.start(); setRec(r)
  }

  if (missing) return (
    <div className="empty"><div className="box">
      <h2>Replay data not generated yet</h2>
      <p>Run <code>make replay</code> after the benchmark finishes (<code>make bench</code>). The demo only shows numbers produced by the pipeline and never substitutes placeholder data.</p>
      <p className="muted">Missing or not JSON:</p>
      <ul className="tn">{missing.map(f => <li key={f}>{f}</li>)}</ul>
      <button onClick={() => location.reload()}>Check again</button>
    </div></div>
  )
  if (!sc || !idx) return <div className="empty"><p className="muted">Loading replay…</p></div>
  const kill = extra.robust.find(r => r.mode === 'in-process' && r.scenario === key)
  const slot = Math.min(95, Math.floor(t))
  const run = story && ch === 0 ? 'status_quo' : 'qgrid'
  const showLabels = scene === 'campus' && !(story && ch === 1)

  return (
    <ProvProvider prov={idx.provenance}>
      <div className="app">
        <header className="top">
          <div className="brand"><b>Q-Grid</b><span className="muted">{sc.campus.name} microgrid</span></div>
          <div className="seg" role="tablist" aria-label="mode">
            {MODES.map(([m, l]) => <button key={m} role="tab" aria-selected={mode === m} className={mode === m ? 'on' : ''} onClick={() => setMode(m)}>{l}</button>)}
          </div>
          <div className="right">
            <select value={key} onChange={e => setKey(e.target.value)} aria-label="scenario">
              {idx.scenarios.map(s => <option key={s.key} value={s.key}>{scenarioName(s.key)}, {fmtDate(s.date)}</option>)}
            </select>
            <button className={`pill ${online ? 'live' : ''}`} onClick={() => !online && liveAvailable().then(ok => { setOnline(ok); if (!ok) alert(`No backend at ${API}. Start it with: make backend`) })}
              title={online ? 'Connected to the live backend' : 'Click to connect to a running backend'}>{online ? 'Live' : 'Offline replay'}</button>
            <button className={`rec ${rec ? 'on' : ''}`} onClick={record} aria-label={rec ? 'stop recording' : 'record demo'}><i />{rec ? 'Stop' : 'Record'}</button>
          </div>
        </header>

        <main className={scene === 'result' ? 'split' : ''}>
          <div className="stage">
            {scene === 'result' ? (
              <div className="result">
                {(['status_quo', 'qgrid'] as const).map(rk => (
                  <div className="half" key={rk}>
                    <span className={`tag ${rk}`}>{rk === 'qgrid' ? 'With Q-Grid' : 'Status quo'}</span>
                    <Canvas camera={{ position: HOME, fov: 38 }} dpr={[1, 1.5]}>
                      <CameraRig pos={HOME} target={[0, 0, 0]} free={false} />
                      <CampusScene sc={sc} t={t} run={rk} />
                    </Canvas>
                    <span className="counter tn">{rs((rk === 'qgrid' ? sc.runs.qgrid : sc.runs.status_quo)?.cum_cost_rs[slot] ?? 0)} so far</span>
                  </div>
                ))}
                <div className="race">
                  <span className="tag">Daily cost including unserved load, all methods (lower is better; band = central optimum)</span>
                  <Canvas camera={{ position: [0, 38, 70], fov: 45 }} dpr={[1, 1.5]}>
                    <ambientLight intensity={0.6} /><directionalLight position={[50, 100, 50]} />
                    <Suspense fallback={null}><BarRace rows={sc.benchmark.filter(r => r.price_scenario === 'A')} progress={1} /></Suspense>
                  </Canvas>
                </div>
              </div>
            ) : (
              <>
                <Canvas camera={{ position: HOME, fov: 38, far: 5000 }} dpr={[1, 1.75]} gl={{ preserveDrawingBuffer: true, antialias: true }}>
                  <CameraRig pos={camPos} target={camTgt} free={!story || ch === 0 || ch === 4} />
                  {scene === 'campus' && <CampusScene sc={sc} t={t} run={run} killed={killed} focus={story && ch === 1 ? q?.zone : focus}
                    onZone={z => setFocus(z)} anchors={anchors} />}
                  {scene === 'campus' && story && ch === 1 && q && <Suspense fallback={null}><QubitChips names={q.var_names} bitsOn={q.optimum.bits} at={zonePos(q.zone)} /></Suspense>}
                  {scene === 'terrain' && q && <><ambientLight intensity={0.5} /><directionalLight position={[80, 160, 60]} intensity={1.2} /><color attach="background" args={[C.bg]} />
                    <Suspense fallback={null}><QuboTerrain q={q} probs={probs} showProbs={ch === 3} /></Suspense></>}
                </Canvas>
                <LabelLayer sc={sc} slot={slot} anchors={anchors} focus={focus} onZone={setFocus} hidden={!showLabels} />
              </>
            )}
          </div>

          <aside className="panel">
            {(story || mode === 'explore') && <NowCard sc={sc} slot={slot} />}
            {story && (
              <section className="chapter">
                <nav className="steps" aria-label="chapters">{CH.map((c, i) => <button key={c} aria-current={i === ch} className={i === ch ? 'on' : ''} onClick={() => setCh(i)} title={c}>{i + 1}</button>)}</nav>
                <h2>{CH[ch]}</h2>
                <p className="caption" aria-live="polite">{caption}</p>
                {ch === 3 && q && <Suspense fallback={null}><QaoaPanel q={q} onLayer={onLayer} playing={playing} /></Suspense>}
                {ch === 4 && <AdmmPanel sc={sc} slot={slot} kill={kill} killed={killed} onKill={startLive} liveLog={liveLog} online={online} />}
                {ch === 5 && sc.headline && <Headline h={sc.headline} />}
              </section>
            )}
            {(mode === 'explore' || (story && (ch === 0 || ch === 5))) && <Decisions sc={sc} slot={slot} />}
            {(mode === 'explore' || (story && ch === 0)) && <DayChart sc={sc} slot={slot} />}
            {mode === 'judge' && (
              <>
                <section><h2>Review the numbers</h2>
                  <div className="row"><span className="muted">Price scenario</span>
                    <div className="seg small">{['A', 'B'].map(p => <button key={p} className={price === p ? 'on' : ''} onClick={() => setPrice(p)}>{p}</button>)}</div></div>
                  <p className="muted small">Select any figure to see its formula, source file, hash and commit.</p>
                  <MetricsTable sc={sc} price={price} /></section>
                <section><h3>Solve one building live</h3>
                  {sc.live_solve ? <SolveLive live={sc.live_solve} online={online} scenario={key} params={[q?.gammas ?? [], q?.betas ?? []]} />
                    : <p className="muted small">Live-solve instances are exported for the headline scenario.</p>}</section>
                <section><h3>Stress tests</h3><Stress online={online} sandbox={extra.sandbox} scenario={key} onKill={setKilled} /></section>
                <section><h3>Add an operator rule</h3><RuleBox online={online} rules={extra.rules} /></section>
              </>
            )}
            {mode === 'sandbox' && <section><h2>What if…</h2><Sandbox online={online} sandbox={extra.sandbox} scenario={key} /></section>}
          </aside>
        </main>

        <div className="bottom">
          <div className="transport">
            <button onClick={() => setPlaying(p => !p)} aria-label={playing ? 'Pause' : 'Play'} className="icon">{playing ? '❚❚' : '▶'}</button>
            {story && <><button onClick={() => setCh(c => Math.max(0, c - 1))} aria-label="Previous chapter" className="icon">‹</button>
              <button onClick={() => setCh(c => Math.min(5, c + 1))} aria-label="Next chapter" className="icon">›</button></>}
            <select value={speed} onChange={e => setSpeed(+e.target.value)} aria-label="speed">{[0.5, 1, 2, 4].map(s => <option key={s} value={s}>{s}×</option>)}</select>
            {story && <label className="muted small"><input type="checkbox" checked={narrate} onChange={e => setNarrate(e.target.checked)} /> Narrate</label>}
            {story && <button className="link small" onClick={() => { setMode('explore'); setPlaying(false) }}>Explore freely</button>}
          </div>
          <Timeline sc={sc} t={t} setT={v => { setT(v); setPlaying(false) }} />
        </div>

        <footer>
          <Legend />
          <div className="foot-right">
            <DataBadge idx={idx} />
            <span className="qlabel">QAOA simulated locally, verified against exact solutions; no quantum advantage claimed. QIEA is quantum-inspired and runs on a classical CPU.</span>
          </div>
        </footer>
      </div>
    </ProvProvider>
  )
}

function Headline({ h }: { h: any }) {
  const row = `method in {B0, OURS}, scenario=${h.scenario}, price_scenario=A`
  const cell = (k: string, label: string, unit: string, fmt: (v: number) => string) => (
    <div><span className="muted">{label}</span>
      <b className="tn"><N v={fmt(h.before[k])} info={{ label: `Status quo · ${k}`, unit, formula: FORMULA[k] ?? k, file: 'results/benchmark.csv', fn: 'scripts/run_benchmark.py', row }} />
        <span className="muted"> → </span><N v={fmt(h.after[k])} info={{ label: `Q-Grid · ${k}`, unit, formula: FORMULA[k] ?? k, file: 'results/benchmark.csv', fn: 'scripts/run_benchmark.py', row }} /></b></div>)
  return (
    <div className="headline">
      <div className="kpis">
        {cell('critical_downtime_h', 'Critical downtime', 'h', v => `${v.toFixed(2)} h`)}
        {cell('critical_unserved_kwh', 'Critical energy unserved', 'kWh', v => `${Math.round(v)} kWh`)}
        {cell('dg_hours', 'Diesel hours', 'h', v => `${v.toFixed(1)} h`)}
        {cell('cost_rs', 'Cost for the day', 'Rs', rs)}
      </div>
      <p className="muted small">Central optimum: {h.optimum_B4.critical_downtime_h.toFixed(2)} h downtime, {rs(h.optimum_B4.cost_rs)}. Re-planning takes {(h.after.replan_time_s * 1000).toFixed(0)} ms per 15-minute slot.{h.price_status === 'REAL' ? '' : ' Stand-in prices.'}</p>
    </div>
  )
}

function AdmmPanel({ sc, slot, kill, killed, onKill, liveLog, online }: { sc: Scenario; slot: number; kill?: Record<string, string>; killed: string | null;
  onKill: (z: string | null) => void; liveLog: string[]; online: boolean }) {
  const its = sc.admm.iterations[String(slot)] ?? []
  const data = its.map(r => ({ k: r.k + 1, r: r.r_primal }))
  return (
    <div className="admm">
      <p className="muted small">At {sc.slots.t[slot]}: {its.length} negotiation rounds, {its.at(-1)?.agreed ? 'every tie-line agreed' : 'settled pairwise'}.</p>
      <div style={{ height: 104 }}><ResponsiveContainer><LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -24 }}>
        <XAxis dataKey="k" stroke={C.muted} fontSize={11} tickLine={false} /><YAxis stroke={C.muted} fontSize={11} tickLine={false} />
        <Tooltip contentStyle={{ background: C.surface, border: `1px solid ${C.border}`, fontSize: 12 }} />
        <Line type="monotone" dataKey="r" stroke={C.quantum} dot={{ r: 2 }} isAnimationActive={!reduced} name="disagreement (kW)" /></LineChart></ResponsiveContainer></div>
      <button onClick={() => onKill(killed ? null : 'heavy_labs')}>{killed ? 'Bring mechanical labs back' : 'Take mechanical labs offline'}</button>
      {killed && kill && <p className="small">Its neighbours stop hearing from it within 3 s and island its lines. Replay of this failure: schedule feasible ({kill.feasible}), full agreement again after {kill.slots_to_reconverge || '–'} slots.</p>}
      {killed && online && <ul className="small tn">{liveLog.map((l, i) => <li key={i}>{l}</li>)}</ul>}
    </div>
  )
}
