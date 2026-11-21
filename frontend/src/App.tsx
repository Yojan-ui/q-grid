import { useCallback, useEffect, useRef, useState } from 'react'
import { getJSON, liveAvailable, missingReplayFiles, MissingReplay, type Index } from './lib/data'
import { reducedMotion } from './lib/theme'
import { STOPS, useStoryData } from './lib/story'
import { Stage } from './story/Stage'
import { Panel } from './story/Panel'
import { WhoDoesWhat } from './story/WhoDoesWhat'
import { ProvProvider } from './panels/Prov'
import { VerifyView, TryView, DataBadge } from './views/Views'

type Tab = 'story' | 'verify' | 'try'
const DAY_SECONDS = 18

export default function App() {
  const [idx, setIdx] = useState<Index | null>(null)
  const [missing, setMissing] = useState<string[] | null>(null)
  const [tab, setTab] = useState<Tab>('story')
  const [i, setI] = useState(() => { const s = new URLSearchParams(location.search).get('stop'); const k = STOPS.findIndex(x => x.id === s); return k >= 0 ? k : 0 })
  const [t, setT] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [zone, setZone] = useState<string | null>(null)
  const [killed, setKilled] = useState<string | null>(null)
  const [admmRound, setAdmmRound] = useState(0)
  const [pulseKey, setPulseKey] = useState(0)
  const [showMiss, setShowMiss] = useState(false)
  const [online, setOnline] = useState(false)

  useEffect(() => {
    getJSON<Index>('index.json').then(async x => {
      const miss = await missingReplayFiles([`scenario_${x.headline}.json`, `qaoa_${x.headline}.json`])
      if (miss.length) setMissing(miss); else setIdx(x)
    }).catch(e => setMissing(e instanceof MissingReplay ? e.files : [String(e)]))
    if (new URLSearchParams(location.search).has('live')) liveAvailable().then(setOnline)
  }, [])
  const { d, err } = useStoryData(idx?.headline ?? '')
  const stop = STOPS[i].id

  // each stop sets its clock: the day plays in steps 1, 6 and 7; otherwise it holds the slot being explained
  useEffect(() => {
    if (!d) return
    setShowMiss(false)
    const play = stop === '1' || stop === '6' || stop === '7a'
    if (play) { setT(0); setPlaying(!reducedMotion()); if (reducedMotion()) setT(95.99) }
    else {
      setPlaying(false)
      setT(stop === '2' ? 48 : stop === '5' ? d.admmSlot : stop === '7b' ? 95.99 : d.example.slot)
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
    const n = d.sc.admm.iterations[String(d.admmSlot)]?.length ?? 0
    if (admmRound >= n - 1 || reducedMotion()) { if (reducedMotion() && admmRound < n - 1) setAdmmRound(n - 1); return }
    const id = setTimeout(() => setAdmmRound(k => k + 1), admmRound === 0 ? 1400 : 700)
    return () => clearTimeout(id)
  }, [stop, admmRound, d])

  const go = useCallback((k: number) => setI(Math.max(0, Math.min(STOPS.length - 1, k))), [])
  const next = useCallback(() => setI(k => Math.min(STOPS.length - 1, k + 1)), [])
  const prev = useCallback(() => setI(k => Math.max(0, k - 1)), [])
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if (tab !== 'story' || (e.target as HTMLElement)?.closest('input,select,textarea')) return
      if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') { e.preventDefault(); next() }
      if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); prev() }
    }
    window.addEventListener('keydown', f)
    return () => window.removeEventListener('keydown', f)
  }, [tab, next, prev])
  const wheelLock = useRef(0)
  const onWheel = (e: React.WheelEvent) => {
    const now = performance.now()
    if (now < wheelLock.current || Math.abs(e.deltaY) < 24) return
    wheelLock.current = now + 1000
    if (e.deltaY > 0) next(); else prev()
  }
  useEffect(() => {
    const u = new URL(location.href); u.searchParams.set('stop', stop); history.replaceState(null, '', u)
  }, [stop])

  if (missing) return (
    <div className="empty"><div className="card">
      <h2>Replay data not generated yet</h2>
      <p>Run <code>make replay</code> after the benchmark (<code>make bench</code>). The demo only shows numbers produced by the pipeline.</p>
      <ul className="tn small">{missing.map(f => <li key={f}>{f}</li>)}</ul>
      <button className="btn" onClick={() => location.reload()}>Check again</button>
    </div></div>
  )
  if (err) return <div className="empty"><div className="card"><h2>Could not load the replay</h2><p className="small">{err}</p></div></div>
  if (!idx || !d) return <div className="empty"><p className="muted">Loading the campus…</p></div>

  return (
    <ProvProvider prov={idx.provenance}>
      <div className="app">
        <header className="top">
          <div className="brand"><b>Q-Grid</b><span className="muted">Decentralised, QAOA-verified scheduling for the RVCE microgrid</span></div>
          <nav className="tabs" role="tablist">
            {([['story', 'Story'], ['verify', 'Verify'], ['try', 'Try it']] as [Tab, string][]).map(([k, l]) =>
              <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>)}
          </nav>
          <div className="right"><DataBadge idx={idx} /></div>
        </header>
        {tab === 'story' ? (
          <main className="story">
            <div className="stage" onWheel={onWheel}>
              <Stage stop={stop} d={d} t={t} zone={zone} onZone={setZone} killed={killed} admmRound={admmRound} pulseKey={pulseKey} showMiss={showMiss} />
              {stop === '4g' && <WhoDoesWhat />}
              <div className="stage-foot">
                <span>{d.sc.label}</span>
              </div>
            </div>
            <Panel stop={stop} d={d} t={t} playing={playing} onPlay={() => { if (!playing && t >= 95.9) setT(0); setPlaying(x => !x) }}
              zone={zone} setZone={setZone} killed={killed} setKilled={setKilled} admmRound={admmRound} setAdmmRound={setAdmmRound}
              replayPulse={() => setPulseKey(k => k + 1)} showMiss={showMiss} setShowMiss={setShowMiss}
              onPrev={prev} onNext={next} go={go} index={i} />
          </main>
        ) : tab === 'verify' ? <VerifyView d={d} idx={idx} online={online} /> : <TryView d={d} online={online} />}
      </div>
    </ProvProvider>
  )
}
