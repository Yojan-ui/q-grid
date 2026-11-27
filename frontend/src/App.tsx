import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'
import { getJSON, liveAvailable, missingReplayFiles, MissingReplay, post, type Index } from './lib/data'
import { reducedMotion, ThemeCtx } from './lib/theme'
import { useTheme } from './lib/useTheme'
import { fmtDate } from './lib/labels'
import { STOPS, useStoryData } from './lib/story'
import { Panel } from './story/Panel'
import { ThemeToggle } from './story/ThemeToggle'
import { SummaryDoc } from './story/Summary'
import { ImpactBoard } from './story/Impact'
import { WhoDoesWhat } from './story/WhoDoesWhat'
import { Scorecard } from './story/Scorecard'
import { ProvProvider } from './panels/Prov'
import { DataBadge } from './views/Views'
// secondary modes load on first use, so the first screen ships only the story
const VerifyView = lazy(() => import('./views/Views').then(m => ({ default: m.VerifyView })))
const OperateView = lazy(() => import('./views/Operate').then(m => ({ default: m.OperateView })))
const DeployView = lazy(() => import('./views/Deploy').then(m => ({ default: m.DeployView })))
import { Sankey } from './story/Sankey'

// the 3D stack (three, react-three-fiber, drei) is its own chunk: the panel renders first, the campus streams in
const loadStage = () => import('./story/Stage')
const Stage = lazy(loadStage)

type Tab = 'story' | 'operate' | 'deploy' | 'verify'
const SCEN_NAME: Record<string, string> = { outage_fest: 'Outage during the fest', fest: 'Fest', teaching: 'Teaching day', exam_week: 'Exam week', vacation: 'Vacation', monsoon: 'Monsoon' }
const DAY_SECONDS = 18
// static deployment (npm run build:static, Vercel): replay only, never probes for a backend
const OFFLINE_BUILD = (import.meta as any).env?.VITE_QGRID_OFFLINE === '1'

function Loading({ text }: { text: string }) {
  return <div className="loading" role="status"><span className="bar"><i /></span><span>{text}</span></div>
}

function Empty({ title, children, files }: { title: string; children: React.ReactNode; files?: string[] }) {
  return (
    <div className="empty"><div className="card" role="alert">
      <h2>{title}</h2>
      {children}
      {files && files.length > 0 && <><p className="small">Missing or unreadable:</p><ul className="tn small">{files.map(f => <li key={f}><code>{f}</code></li>)}</ul></>}
      <p className="muted small">The demo only shows numbers produced by the pipeline; it never falls back to sample data.</p>
      <button className="btn" onClick={() => location.reload()}>Check again</button>
    </div></div>
  )
}

const fmtClock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`

/** Presenter timer: time on the current stop and since presenter mode began. */
function PresenterTimer({ stopKey }: { stopKey: string }) {
  const [t0, setT0] = useState(() => performance.now())
  const [s0, setS0] = useState(() => performance.now())
  const [, tick] = useState(0)
  useEffect(() => { setS0(performance.now()) }, [stopKey])
  useEffect(() => { const id = setInterval(() => tick(k => k + 1), 500); return () => clearInterval(id) }, [])
  const now = performance.now()
  return (
    <div className="ptimer" role="timer" aria-label="presenter timer">
      <span>this step <b>{fmtClock((now - s0) / 1000)}</b></span>
      <span>total <b>{fmtClock((now - t0) / 1000)}</b></span>
      <button onClick={() => { setT0(performance.now()); setS0(performance.now()) }} aria-label="reset timer">reset</button>
    </div>
  )
}

export default function App() {
  const theme = useTheme()
  const cycleTheme = theme.cycle
  const demo = new URLSearchParams(location.search).has('demo')
  const [present, setPresent] = useState(() => demo || document.documentElement.hasAttribute('data-present'))
  const [warm, setWarm] = useState<'idle' | 'warming' | 'ready' | 'offline'>('idle')
  const [idx, setIdx] = useState<Index | null>(null)
  const [missing, setMissing] = useState<string[] | null>(null)
  const [tab, setTab] = useState<Tab>(() => { const m = new URLSearchParams(location.search).get('mode'); return m === 'operate' || m === 'deploy' || m === 'verify' ? m : 'story' })
  const [i, setI] = useState(() => { const s = new URLSearchParams(location.search).get('stop'); const k = STOPS.findIndex(x => x.id === s); return k >= 0 ? k : 0 })
  const [t, setT] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [zone, setZone] = useState<string | null>(null)
  const [killed, setKilled] = useState<string | null>(null)
  const [admmRound, setAdmmRound] = useState(0)
  const [pulseKey, setPulseKey] = useState(0)
  const [showMiss, setShowMiss] = useState(false)
  const [online, setOnline] = useState(false)
  const [benchDs, setBenchDs] = useState('rvce')
  const [scen, setScen] = useState<string>(() => new URLSearchParams(location.search).get('scenario') ?? '')

  useEffect(() => {
    getJSON<Index>('index.json').then(async x => {
      const miss = await missingReplayFiles([`scenario_${x.headline}.json`, `qaoa_${x.headline}.json`])
      if (miss.length) setMissing(miss); else setIdx(x)
    }).catch(e => setMissing(e instanceof MissingReplay ? e.files : [String(e)]))
    // the live backend is optional: detected at start and every 15 s; offline replay otherwise (?offline forces it)
    const probe = () => { if (!OFFLINE_BUILD && !new URLSearchParams(location.search).has('offline')) liveAvailable().then(setOnline) }
    probe(); const id = setInterval(probe, 15000)
    loadStage()   // fetch the 3D chunk while the replay JSON loads
    return () => clearInterval(id)
  }, [])
  const key = scen && idx?.scenarios.some(x => x.key === scen) ? scen : idx?.headline ?? ''
  const { d, err, missing: storyMissing, loading } = useStoryData(key)
  // demo preset: warm the backend once it is reachable so the first live moment answers fast
  useEffect(() => {
    if (!demo || warm !== 'idle') return
    if (!online) { const id = setTimeout(() => setWarm(w => (w === 'idle' ? 'offline' : w)), 2500); return () => clearTimeout(id) }
    setWarm('warming')
    post<{ ok: boolean }>(`/live/warm?scenario=${key || 'outage_fest'}`, {}).then(() => setWarm('ready')).catch(() => setWarm('offline'))
  }, [demo, online, warm, key])
  const stop = STOPS[i].id

  // each stop sets its clock: the day plays in steps 1, 6 and 7; otherwise it holds the slot being explained
  useEffect(() => {
    if (!d) return
    setShowMiss(false)
    const play = stop === '1' || stop === '6'
    if (play) { setT(0); setPlaying(!reducedMotion()); if (reducedMotion()) setT(95.99) }
    else {
      setPlaying(false)
      setT(stop === '2' ? 48 : stop === '5' || stop === '5b' ? d.admmSlot : stop.startsWith('7') ? 95.99 : d.example.slot)
    }
    if (stop === '5') setAdmmRound(0)
    if (stop !== '5') setKilled(null)
    if (stop !== '2') setZone(null)
  }, [stop, d])
  useEffect(() => {
    if (!playing) return
    let raf = 0, last = performance.now()
    const tick = (now: number) => {
      const dt = (now - last) / 1000; last = now
      let done = false
      setT(x => { const nx = x + (dt * 96) / DAY_SECONDS; if (nx >= 95.99) { done = true; return 95.99 } return nx })
      if (done) setPlaying(false); else raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing])
  // step 5: negotiation rounds advance on their own once, then hold
  useEffect(() => {
    if (stop !== '5' || !d) return
    const n = d.admmRounds.length
    if (admmRound >= n - 1 || reducedMotion()) { if (reducedMotion() && admmRound < n - 1) setAdmmRound(n - 1); return }
    const id = setTimeout(() => setAdmmRound(k => k + 1), admmRound === 0 ? 1400 : 700)
    return () => clearTimeout(id)
  }, [stop, admmRound, d])

  const go = useCallback((k: number) => setI(Math.max(0, Math.min(STOPS.length - 1, k))), [])
  const next = useCallback(() => setI(k => Math.min(STOPS.length - 1, k + 1)), [])
  const prev = useCallback(() => setI(k => Math.max(0, k - 1)), [])
  // presenter mode: projector sizing, dev controls hidden, step timer
  useEffect(() => {
    const h = document.documentElement
    if (present) { h.setAttribute('data-present', ''); setTab('story') } else h.removeAttribute('data-present')
  }, [present])
  // keyboard: arrows / PageUp / PageDown / space (presentation clickers send PageUp / PageDown), D theme, P presenter
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement
      if (el?.closest('input,select,textarea,[contenteditable=true]') || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'd' || e.key === 'D') { e.preventDefault(); cycleTheme(); return }
      if (e.key === 'p' || e.key === 'P') { e.preventDefault(); setPresent(x => !x); return }
      if (tab !== 'story' || el?.closest('[role=menu]')) return
      // space and enter keep their normal meaning on a focused control
      if (e.key === ' ' && el?.closest('button,a,[role=button],[tabindex]:not(body)')) return
      if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') { e.preventDefault(); next() }
      if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); prev() }
      if (e.key === 'Home') { e.preventDefault(); go(0) }
      if (e.key === 'End') { e.preventDefault(); go(STOPS.length - 1) }
    }
    window.addEventListener('keydown', f)
    return () => window.removeEventListener('keydown', f)
  }, [tab, next, prev, go, cycleTheme])
  const printSummary = () => {
    const title = document.title
    document.title = `Q-Grid summary ${new Date().toISOString().slice(0, 10)}`
    const restore = () => { document.title = title; window.removeEventListener('afterprint', restore) }
    window.addEventListener('afterprint', restore)
    window.print()
  }
  const wheelLock = useRef(0)
  const onWheel = (e: React.WheelEvent) => {
    const now = performance.now()
    if (now < wheelLock.current || Math.abs(e.deltaY) < 24) return
    wheelLock.current = now + 1000
    if (e.deltaY > 0) next(); else prev()
  }
  useEffect(() => {
    const u = new URL(location.href); u.searchParams.set('stop', stop); if (key) u.searchParams.set('scenario', key)
    if (tab !== 'story') u.searchParams.set('mode', tab); else u.searchParams.delete('mode')
    history.replaceState(null, '', u)
  }, [stop, key, tab])

  const wrap = (node: React.ReactNode) => <ThemeCtx.Provider value={{ name: theme.name, C: theme.C }}>{node}</ThemeCtx.Provider>
  if (missing) return wrap(
    <Empty title="The replay data isn’t generated yet" files={missing}>
      <p>Run <code>make bench</code>, then <code>make replay</code>. That writes <code>results/replay/</code> and copies it to <code>frontend/public/replay/</code>.</p>
    </Empty>)
  if (storyMissing) return wrap(
    <Empty title={`The ${SCEN_NAME[key] ?? key} day can’t be shown yet`} files={storyMissing}>
      <p>Its replay files are missing. Run <code>make replay</code>, or pick another day from the index.</p>
    </Empty>)
  if (err) return wrap(
    <Empty title="The replay couldn’t be read">
      <p className="small">{err}</p>
    </Empty>)
  if (!idx) return wrap(<Loading text="Loading the replay index…" />)
  if (!d) return wrap(<Loading text={`Loading ${loading || 'the campus'}…`} />)

  return wrap(
    <ProvProvider prov={idx.provenance}>
      <div className="app">
        <a className="skip" href="#panel">Skip to the explanation</a>
        <header className="top">
          <div className="brand"><b>Q-Grid</b><span className="muted">Decentralised, QAOA-verified scheduling for the RVCE microgrid</span></div>
          <nav className="tabs modes" role="tablist" aria-label="modes">
            {([['story', 'Explain'], ['operate', 'Operate'], ['deploy', 'Deploy'], ['verify', 'Verify']] as [Tab, string][]).map(([k, l]) =>
              <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>)}
          </nav>
          <div className="right">
            <span className={`livebadge ${online ? 'on' : ''}`} title={online ? 'Live demo moments run on the backend (localhost:8000)' : OFFLINE_BUILD ? 'Static demo: every result is precomputed by the pipeline' : 'No backend found: live moments show precomputed results'}>{online ? 'Live backend' : 'Offline replay'}</span>
            {present && <PresenterTimer stopKey={stop} />}
            {demo && <span className={`pill ${warm === 'ready' ? 'ok' : warm === 'offline' ? '' : 'warn'}`} title="Demo preset: presenter mode, step 1, live moments warmed on the backend (or precomputed offline)">
              {warm === 'ready' ? 'Demo ready · live' : warm === 'offline' ? `Demo ready · offline${d.live ? '' : ' (no precomputed live moments!)'}` : 'Demo: warming up…'}</span>}
            <select className="scenpick devonly" value={key} onChange={e => setScen(e.target.value)} aria-label="scenario day">
              {idx.scenarios.map(x => <option key={x.key} value={x.key}>{SCEN_NAME[x.key] ?? x.key}, {fmtDate(x.date)}</option>)}
            </select>
            <span className="devonly"><DataBadge idx={idx} /></span>
            <button className="btn ghost small devonly" onClick={printSummary} title="Opens the print dialog: choose “Save as PDF”. Printed in the light theme.">Download summary (PDF)</button>
            {!demo && <a className="btn ghost small devonly" href="?demo&stop=1" title="Demo preset: Explain step 1, presenter mode, live moments ready">Demo</a>}
            <button className={`btn small ${present ? 'primary' : 'ghost'}`} onClick={() => setPresent(x => !x)} aria-pressed={present} title="Presenter mode (P)" style={{ marginLeft: 8 }}>
              {present ? 'Exit presenter' : 'Present'}</button>
            <ThemeToggle mode={theme.mode} name={theme.name} setMode={theme.setMode} />
          </div>
        </header>
        {tab === 'story' ? (
          <main className="story">
            <div className="stage" onWheel={onWheel} role="img" aria-label={`3D model of the campus, ${STOPS[i].title.toLowerCase()}. The explanation panel describes what is shown.`}>
              <Suspense fallback={<div className="stage-loading"><Loading text="Loading the 3D campus…" /></div>}>
                <Stage stop={stop} d={d} t={t} zone={zone} onZone={setZone} killed={killed} admmRound={admmRound} pulseKey={pulseKey} showMiss={showMiss} />
              </Suspense>
              {stop === '4g' && !d.qs && <WhoDoesWhat />}
              {stop === '7a' && d.bench && <Scorecard b={d.bench} ds={benchDs} />}
              {stop === '7d' && d.impact && <ImpactBoard m={d.impact} />}
              {stop === '7f' && d.sankey && <div className="impactboard"><div className="ib-card"><div className="sc-head"><b>Where the energy went · {d.sankey.label}</b><span className="muted"> · Q-Grid, kWh over the day</span></div><Sankey flows={d.sankey.qgrid} height={420} title={`Energy flows, ${d.sankey.label}`} /></div></div>}
              <div className="clock tn" aria-live="off">{d.sc.slots.t[Math.min(95, Math.floor(t))]}{d.sc.slots.grid_up[Math.min(95, Math.floor(t))] ? '' : <span className="down"> · grid down</span>}</div>
              <div className="stage-foot">
                <span>{d.sc.label}</span>
              </div>
            </div>
            <Panel stop={stop} d={d} t={t} playing={playing} onPlay={() => { if (!playing && t >= 95.9) setT(0); setPlaying(x => !x) }}
              zone={zone} setZone={setZone} killed={killed} setKilled={setKilled} admmRound={admmRound} setAdmmRound={setAdmmRound}
              replayPulse={() => setPulseKey(k => k + 1)} showMiss={showMiss} setShowMiss={setShowMiss}
              onPrev={prev} onNext={next} go={go} index={i} benchDs={benchDs} setBenchDs={setBenchDs} online={online} />
          </main>
        ) : <Suspense fallback={<Loading text={`Loading ${tab}…`} />}>{tab === 'verify' ? <VerifyView d={d} idx={idx} online={online} /> : tab === 'operate' ? <OperateView d={d} online={online} /> : <DeployView d={d} />}</Suspense>}
      </div>
      <SummaryDoc d={d} idx={idx} ds={benchDs} />
    </ProvProvider>
  )
}
