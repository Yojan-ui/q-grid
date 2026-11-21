import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { EffectComposer, N8AO } from '@react-three/postprocessing'
import * as THREE from 'three'
import { motion } from 'framer-motion'
import { getCSV, getJSON, liveAvailable, MissingReplay, missingReplayFiles, type Index, type QaoaFile, type Scenario } from './lib/data'
import { C, fmtDate, SCEN } from './lib/theme'
import { ProvProvider } from './panels/Prov'
import { MetricsTable, RuleBox, SolveLive, Stress } from './panels/Judge'
import { Sandbox } from './panels/Sandbox'
import { AdmmLabels, CameraRig, Campus, DeviceIcons, QuantumRig, ScaleOut, useZoneGeo } from './story/World'
import { StoryText } from './story/Panel'
import { BEATS, type Beat, admmSlot, stepOf } from './story/model'

type Tab = 'story' | 'verify' | 'try'
type V3 = [number, number, number]
const reduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
const TIME_BEATS: Beat[] = ['1', '6', '7']

function Sun({ sc, t }: { sc: Scenario; t: number }) {
  const s = Math.min(95, Math.floor(t))
  const el = THREE.MathUtils.degToRad(Math.max(28, sc.slots.sun.elevation_deg[s])), az = THREE.MathUtils.degToRad(sc.slots.sun.azimuth_deg[s])
  const p: V3 = [Math.sin(az) * Math.cos(el) * 600, Math.sin(el) * 600, -Math.cos(az) * Math.cos(el) * 600]
  const ref = useRef<THREE.DirectionalLight>(null!)
  useEffect(() => { const c = ref.current.shadow.camera as THREE.OrthographicCamera; c.left = -450; c.right = 450; c.top = 450; c.bottom = -450; c.far = 1800; c.updateProjectionMatrix(); (ref.current.shadow as any).intensity = 0.5 }, [])
  return <directionalLight ref={ref} position={p} intensity={1.9} color="#FFF8EC" castShadow shadow-mapSize={[2048, 2048]} shadow-bias={-0.0004} shadow-normalBias={0.6} />
}

function Scene({ sc, q, beat, t, focus, setFocus, removed, round, admmT, scaleOut, dropped }: {
  sc: Scenario; q: QaoaFile; beat: Beat; t: number; focus: string; setFocus: (z: string) => void; removed: string | null; round: number; admmT: number; scaleOut: boolean; dropped: boolean }) {
  const [hover, setHover] = useState<string | null>(null)
  const zg = useZoneGeo(sc)
  const fz = sc.campus.zones.find(z => z.name === q.zone)!
  const fh = zg.find(g => g.z.name === q.zone)?.h ?? 12
  const F: V3 = [fz.cx, 0, -fz.cy]
  const O: V3 = [F[0], 150, F[2]]
  const step = stepOf(beat)
  const run = beat === '1' ? sc.runs.status_quo! : sc.runs.qgrid
  const its = sc.admm.iterations[String(admmT)] ?? []
  const flows5 = beat === '5' && its.length ? sc.campus.lines.map((_, l) => { const pr = its[Math.min(round, its.length - 1)].proposals[String(l)]; return pr ? (pr[0] + pr[1]) / 2 : 0 }) : null
  const fzone = sc.campus.zones.find(z => z.name === focus)!
  const cam: Record<string, [V3, V3]> = {
    '1': [[300, 250, 360], [0, 0, 0]], '2': [[fzone.cx + 170, 210, -fzone.cy + 230], [fzone.cx * 0.5, 0, -fzone.cy * 0.5]],
    '3': [[O[0], O[1] + 4, O[2] + 185], [O[0], O[1] - 2, O[2]]], '4a': [[O[0], O[1] + 4, O[2] + 185], [O[0], O[1] - 2, O[2]]],
    '4b': [[O[0], O[1] + 2, O[2] + 175], [O[0], O[1] - 2, O[2]]],
    '4c': [[O[0] - 30, O[1] + 2, O[2] + 200], [O[0] - 30, O[1], O[2]]], '4d': [[O[0] + 6, O[1] - 4, O[2] + 310], [O[0] + 6, O[1] - 6, O[2]]],
    '4e': dropped ? [[F[0] + 110, 95, F[2] + 150], [F[0], 14, F[2]]] : [[O[0], O[1] + 4, O[2] + 185], [O[0], O[1] - 2, O[2]]], '4f': [[F[0] + 90, 95, F[2] + 120], [F[0], 10, F[2]]],
    '4g': [[F[0] + 160, 190, F[2] + 230], [F[0] * 0.5, 0, F[2] * 0.5]], '5': [[0, 860, 90], [0, 0, 0]], '6': [[260, 230, 330], [0, 0, 0]],
    '7': scaleOut ? [[-300, 2900, 2600], [-300, 0, 0]] : [[-290, 470, 640], [-290, 0, 0]],
  }
  const [cp, ct] = cam[beat]
  const showRibbons = ['1', '5', '6', '7', '4e'].includes(beat)
  const inc = new Set(sc.campus.lines.map((l, k) => (l.includes(q.zone) ? k : -1)).filter(k => k >= 0))
  const flows4e = beat === '4e' ? sc.campus.lines.map((_, l) => (inc.has(l) ? sc.runs.qgrid.flows[l][q.slot] : 0)) : null
  return (
    <>
      <color attach="background" args={[C.bg]} />
      <fog attach="fog" args={beat === '7' && scaleOut ? [C.bg, 5000, 16000] : step >= 3 && step <= 4 ? [C.bg, 360, 2100] : [C.bg, 1400, 6000]} />
      <hemisphereLight args={['#FFFFFF', '#E3E1D9', 1.0]} />
      <ambientLight intensity={0.55} />
      <Sun sc={sc} t={t} />
      <mesh rotation-x={-Math.PI / 2} receiveShadow position-y={-0.02}><planeGeometry args={[9000, 9000]} /><meshStandardMaterial color={C.ground} roughness={1} /></mesh>
      <CameraRig pos={cp} target={ct} free={beat === '2' || beat === '5' || beat === '6'} />
      <Campus sc={sc} run={run} t={t} beat={beat} focus={beat === '2' ? focus : q.zone} removed={beat === '5' ? removed : null} hover={hover}
        flows={flows5 ?? flows4e} showRibbons={showRibbons} onZone={z => z && setFocus(z)} onHover={setHover} liftAll={beat === '2'} />
      {beat === '2' && <DeviceIcons key={focus} sc={sc} zone={focus} h={zg.find(g => g.z.name === focus)?.h ?? 12} />}
      {beat === '7' && <Campus sc={sc} run={sc.runs.status_quo!} t={t} beat={beat} focus="" offset={[-580, 0, 0]} showRibbons />}
      {step >= 3 && step <= 4 && <QuantumRig sc={sc} q={q} beat={beat} origin={O} buildingTop={[F[0], fh + 2, F[2]]} dropped={dropped} />}
      {beat === '5' && <AdmmLabels sc={sc} round={round} slot={admmT} removed={removed} />}
      {beat === '7' && <ScaleOut show={scaleOut} />}
    </>
  )
}

export default function App() {
  const [idx, setIdx] = useState<Index | null>(null)
  const [key, setKey] = useState('')
  const [sc, setSc] = useState<Scenario | null>(null)
  const [q, setQ] = useState<QaoaFile | null>(null)
  const [extra, setExtra] = useState<{ sandbox: any; rules: any[]; robust: Record<string, string>[]; search: any }>({ sandbox: null, rules: [], robust: [], search: null })
  const [tab, setTab] = useState<Tab>('story')
  const [bi, setBi] = useState(0)
  const [t, setT] = useState(0)
  const [focus, setFocus] = useState('hostels')
  const [removed, setRemoved] = useState<string | null>(null)
  const [round, setRound] = useState(0)
  const [scaleOut, setScaleOut] = useState(false)
  const [dropped, setDropped] = useState(false)
  const [online, setOnline] = useState(false)
  const [missing, setMissing] = useState<string[] | null>(null)
  const beat = BEATS[bi]

  useEffect(() => {
    getJSON<Index>('index.json').then(async i => {
      const miss = await missingReplayFiles(i.scenarios.flatMap(s => [`scenario_${s.key}.json`, `qaoa_${s.key}.json`]))
      if (miss.length) { setMissing(miss); return }
      setIdx(i); setKey(i.headline)
    }).catch(async e => setMissing(e instanceof MissingReplay ? [...e.files, ...(await missingReplayFiles(['sandbox.json', 'rules.json']))] : [String(e)]))
    getJSON<any>('sandbox.json').then(s => setExtra(x => ({ ...x, sandbox: s }))).catch(() => {})
    getJSON<any[]>('rules.json').then(r => setExtra(x => ({ ...x, rules: r }))).catch(() => {})
    getJSON<any>('search_space.json').then(s => setExtra(x => ({ ...x, search: s }))).catch(() => {})
    getCSV('robustness.csv').then(r => setExtra(x => ({ ...x, robust: r })))
    if (new URLSearchParams(location.search).has('live')) liveAvailable().then(setOnline)
  }, [])
  useEffect(() => {
    if (!key) return
    getJSON<Scenario>(`scenario_${key}.json`).then(s => { setSc(s); return getJSON<QaoaFile>(s.qaoa_file).then(qq => { setQ(qq); setFocus(qq.zone) }) })
      .catch(e => setMissing(e instanceof MissingReplay ? e.files : [String(e)]))
  }, [key])

  const admmT = useMemo(() => (sc ? admmSlot(sc) : 76), [sc])
  // time of day per beat: steps 1, 6 and 7 replay the day once; the quantum example holds its slot
  useEffect(() => {
    if (!sc || !q) return
    setScaleOut(false)
    if (beat === '5') { setT(admmT); return }
    if (!TIME_BEATS.includes(beat)) { setT(q.slot); return }
    if (reduced) { setT(beat === '7' ? 95.9 : 76); return }
    setT(0)
    let raf = 0, start = performance.now()
    const dur = beat === '7' ? 9000 : 14000
    const tick = (now: number) => {
      const f = Math.min(1, (now - start) / dur)
      setT(f * 95.9)
      if (f < 1) raf = requestAnimationFrame(tick)
      else if (beat === '7') setTimeout(() => setScaleOut(true), 600)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [beat, sc, q, admmT])
  useEffect(() => { if (beat !== '5') setRemoved(null) }, [beat])
  useEffect(() => {   // 4e: tiles show their actions, then drop back into the building (camera follows)
    setDropped(false)
    if (beat !== '4e') return
    const id = setTimeout(() => setDropped(true), reduced ? 0 : 3600)
    return () => clearTimeout(id)
  }, [beat])

  const next = useCallback(() => setBi(i => Math.min(BEATS.length - 1, i + 1)), [])
  const back = useCallback(() => setBi(i => Math.max(0, i - 1)), [])
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if (tab !== 'story' || (e.target as HTMLElement)?.tagName === 'INPUT') return
      if (e.key === 'ArrowRight' || e.key === 'PageDown') next()
      if (e.key === 'ArrowLeft' || e.key === 'PageUp') back()
    }
    window.addEventListener('keydown', f); return () => window.removeEventListener('keydown', f)
  }, [tab, next, back])

  if (missing) return (
    <div className="empty"><div className="box">
      <h2>Replay data not generated yet</h2>
      <p>Run <code>make replay</code> after the benchmark finishes (<code>make bench</code>). This page only shows numbers produced by the pipeline and never substitutes placeholder data.</p>
      <p className="muted">Missing or not JSON:</p><ul>{missing.map(f => <li key={f}><code>{f}</code></li>)}</ul>
      <button onClick={() => location.reload()}>Check again</button>
    </div></div>
  )
  if (!sc || !idx || !q) return <div className="empty"><p className="muted">Loading the RVCE replay…</p></div>
  const step = stepOf(beat)
  const pend = Object.values(idx.data_status).filter(v => v !== 'REAL').length

  return (
    <ProvProvider prov={idx.provenance}>
      <div className="app">
        <header className="top">
          <div className="brand"><b>Q-Grid</b><span className="muted">Coordinating RVCE’s solar, batteries and diesel, building by building</span></div>
          <nav className="tabs" aria-label="sections">
            {([['story', 'Story'], ['verify', 'Verify'], ['try', 'Try it']] as [Tab, string][]).map(([k, l]) =>
              <button key={k} className={tab === k ? 'on' : ''} aria-current={tab === k} onClick={() => setTab(k)}>{l}</button>)}
          </nav>
          <div className="right">
            <select value={key} onChange={e => { setKey(e.target.value); setBi(0) }} aria-label="day">
              {idx.scenarios.map(s => <option key={s.key} value={s.key}>{SCEN[s.key]}, {fmtDate(s.date)}</option>)}
            </select>
          </div>
        </header>

        {tab === 'story' && (
          <main className="guided">
            <section className="visual">
              <Canvas flat shadows camera={{ position: [300, 250, 360], fov: 34, near: 1, far: 9000 }} dpr={[1, 1.6]} gl={{ antialias: true, preserveDrawingBuffer: true }}>
                <Suspense fallback={null}>
                  <Scene sc={sc} q={q} beat={beat} t={t} focus={focus} setFocus={setFocus} removed={removed} round={round} admmT={admmT} scaleOut={scaleOut} dropped={dropped} />
                  {!reduced && <EffectComposer multisampling={0}><N8AO halfRes aoRadius={5} intensity={0.9} distanceFalloff={0.6} color={'#000000'} /></EffectComposer>}
                </Suspense>
              </Canvas>
              {TIME_BEATS.includes(beat) && <div className="clock tn">{sc.slots.t[Math.min(95, Math.floor(t))]}{sc.slots.grid_up[Math.min(95, Math.floor(t))] ? '' : ' · grid down'}</div>}
              {beat === '7' && !scaleOut && <div className="vlabels"><span>Status quo</span><span>Q-Grid</span></div>}
              {beat === '7' && scaleOut && <div className="illus">Illustrative: eight campuses on one city feeder. More buildings means more neighbours to agree with; each building's plan stays at most 16 qubits.</div>}
            </section>
            <aside className="explain">
              <div className="progress"><motion.div className="bar" animate={{ width: `${((bi + 1) / BEATS.length) * 100}%` }} transition={{ duration: reduced ? 0 : 0.5 }} /></div>
              <div className="steps" aria-label="steps">{[1, 2, 3, 4, 5, 6, 7].map(s => (
                <button key={s} className={s === step ? 'on' : s < step ? 'done' : ''} onClick={() => setBi(BEATS.findIndex(b => stepOf(b) === s))} aria-label={`Step ${s}`}>{s}</button>))}
              </div>
              <div className="scroll">
                <StoryText beat={beat} sc={sc} q={q} idx={idx} t={t} focus={focus} round={round} setRound={setRound} admmT={admmT}
                  removed={removed} setRemoved={setRemoved} robust={extra.robust} search={extra.search} />
              </div>
              <div className="nav">
                <button onClick={back} disabled={bi === 0}>Back</button>
                <span className="muted small">← → keys</span>
                <button className="primary" onClick={next} disabled={bi === BEATS.length - 1}>{bi === BEATS.length - 1 ? 'Done' : 'Next'}</button>
              </div>
            </aside>
          </main>
        )}
        {tab === 'verify' && (
          <main className="page">
            <h1>Check any number</h1>
            <p className="support">Select a figure to see its formula, the file it comes from, that file’s SHA-256, the script that produced it and the git commit.</p>
            <MetricsTable sc={sc} price="A" />
            <h2>Solve one building’s slot live</h2>
            {sc.live_solve ? <SolveLive live={sc.live_solve} online={online} scenario={key} params={[q.gammas, q.betas]} />
              : <p className="muted">Live-solve examples are exported for the outage-during-fest day. Choose it in the menu above.</p>}
          </main>
        )}
        {tab === 'try' && (
          <main className="page">
            <h1>Try it</h1>
            <p className="support">What-if results come from a fast quantum-inspired classical solver. They are a sandbox, never part of the headline results.</p>
            <div className="two"><section><h2>What if…</h2><Sandbox online={online} sandbox={extra.sandbox} scenario={key} /></section>
              <section><h2>Stress tests</h2><Stress online={online} sandbox={extra.sandbox} scenario={key} onKill={() => {}} />
                <h2>Add an operator rule</h2><RuleBox online={online} rules={extra.rules} /></section></div>
            {!online && <p className="muted small">Offline: showing precomputed cases. Start the backend (<code>make backend</code>) and open with <code>?live=1</code> to recompute.</p>}
          </main>
        )}

        <footer>
          <span className="muted">Data: NASA POWER, Ausgrid, OpenStreetMap (© OpenStreetMap contributors) · {pend} items pending official data</span>
          <span className="muted">QAOA simulated locally and verified against exact solutions; no quantum advantage claimed. QIEA is quantum-inspired, classical CPU.</span>
        </footer>
      </div>
    </ProvProvider>
  )
}
