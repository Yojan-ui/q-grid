// Operate mode data: live (backend WebSocket /operate/ws + actions) or recorded (replay/operate_session.json played
// back with the same time controls). Nothing here invents values: live shows the engine's state, recorded shows frames
// the same engine wrote (scripts/record_operate.py).
import { useEffect, useMemo, useRef, useState } from 'react'
import { API, getJSON, post } from './data'

export type OpZone = { name: string; pv_kw: number; load_kw: number; battery_kw: number; soc: number | null; dg_kw: number; pump: boolean
  net_kw: number; state: 'import' | 'export' | 'balanced' | 'island' | 'shedding'; next_action: string; reason: string
  source: 'hardware' | 'simulated'; has: { battery: boolean; diesel: boolean; pump: boolean } }
export type OpPlan = { t0: number; made_at: string; reason: string; time_s: number; pv_forecast: number[]; import_plan: number[]
  zones: { battery_kw: number[]; dg_kw: number[]; pump: number[]; flex: Record<string, number | null> }[] }
export type OpAdmm = { rounds: number; converged: boolean; messages: number; isolated: boolean; time_s: number; made_at: string
  residuals: number[]; cables: { line: number; a: string; b: string; proposals: number[] | null }[] }
export type OpEvent = { t: number; time: string; kind: string; sev: 'info' | 'warn' | 'alarm'; text: string; zone: string | null }
export type OpAudit = { wall: string; sim: string; who: string; action: string; detail: string }
export type Flows = { links: { source: string; target: string; kind: 'zone' | 'sink'; kwh: number }[]; unserved_kwh: number; sources_kwh: Record<string, number>; method: string }
export type OpReport = { date: string; profile_day?: string; final: boolean; slots: number; source: string; labels: Record<string, string>
  qgrid: Record<string, number>; status_quo: Record<string, number>; saving_rs: number; flows?: Flows; note: string }
export type OpSeries = { pv_actual: number[]; load_actual: number[]; import_actual: number[]; minutes: number[]; plan_t0: number
  grid_up: number[]; soc_campus: (number | null)[] }
export type OpSnapshot = {
  clock: { sim_s: number; time: string; date: string; speed: number; slot: number; day_over: boolean }
  source: string; labels: Record<string, string>
  forecast: { label: string; source: string; fetched_at_ist: string | null; error: string | null; available: boolean } | null
  hardware: { broker_connected: boolean; error: string | null; zones_live: string[] } | null
  grid_up_now: boolean; comms_ok: boolean; zones: OpZone[]; plan: OpPlan | null; admm: OpAdmm | null; series: OpSeries
  events: OpEvent[]; audit: OpAudit[]; overrides: { id: number; zone: string; device: string; state: string; until: number; who: string }[]
  rules: string[]; reports: OpReport[]; lines: [string, string][]; mpc_busy: boolean
  devices?: { zone: string; source: string; online: boolean; latency_ms: number | null; last_reading: string; rssi: number | null }[]
}
type Recorded = { kind: 'recorded'; date: string; labels: Record<string, string>; recorded_at: string
  frames: { t: number; time: string; zones: OpZone[]; plan: number; grid_up_now: boolean; comms_ok: boolean; overrides: OpSnapshot['overrides']; rules: string[] }[]
  plans: (OpPlan & { made_at_s: number })[]; admm: OpAdmm[]; series: OpSeries; events: OpEvent[]; audit: OpAudit[]; report: OpReport; lines: [string, string][] }

const hhmmToS = (s: string) => { const [h, m] = s.split(':').map(Number); return h * 3600 + m * 60 }

/** Build a snapshot from the recording at simulated time t (seconds since midnight). */
function frameAt(r: Recorded, t: number, speed: number): OpSnapshot {
  let k = 0
  while (k + 1 < r.frames.length && r.frames[k + 1].t <= t) k++
  const f = r.frames[k]
  const slot = Math.min(95, Math.floor(f.t / 900))
  const cut = <T,>(a: T[]) => a.map((v, i) => (i <= slot ? v : (null as unknown as T)))
  const end = k === r.frames.length - 1
  return {
    clock: { sim_s: f.t, time: f.time, date: new Date(r.date + 'T00:00').toLocaleDateString('en-IN', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' }), speed, slot, day_over: end },
    source: 'recorded', labels: r.labels, forecast: null, hardware: null,
    grid_up_now: f.grid_up_now, comms_ok: f.comms_ok, zones: f.zones, plan: r.plans[f.plan] ?? null, admm: r.admm[f.plan] ?? null,
    series: { ...r.series, pv_actual: cut(r.series.pv_actual), load_actual: cut(r.series.load_actual), import_actual: cut(r.series.import_actual),
      soc_campus: cut(r.series.soc_campus), grid_up: r.series.grid_up.map((g, i) => (i <= slot ? g : 1)) },
    events: r.events.filter(e => e.t <= f.t), audit: r.audit.filter(a => hhmmToS(a.sim) <= f.t),
    overrides: f.overrides, rules: f.rules, reports: end ? [r.report] : [], lines: r.lines, mpc_busy: false,
  }
}

export function useOperate(online: boolean) {
  const [snap, setSnap] = useState<OpSnapshot | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [rec, setRec] = useState<Recorded | null>(null)
  const [t, setT] = useState(0)
  const [speed, setSpeedLocal] = useState(0)
  const ws = useRef<WebSocket | null>(null)

  // live: WebSocket stream (reconnects every 3 s while the backend is reachable)
  useEffect(() => {
    if (!online) return
    let stop = false, timer = 0
    const open = () => {
      const u = API.replace(/^http/, 'ws') + '/operate/ws'
      const s = new WebSocket(u); ws.current = s
      s.onmessage = e => { try { setSnap(JSON.parse(e.data)); setErr(null) } catch { /* ignore a malformed frame */ } }
      s.onclose = () => { if (!stop) timer = window.setTimeout(open, 3000) }
      s.onerror = () => setErr('The operate stream dropped; reconnecting…')
    }
    open()
    return () => { stop = true; clearTimeout(timer); ws.current?.close() }
  }, [online])

  // recorded: load once, then play back on a local clock
  useEffect(() => {
    if (online || rec) return
    getJSON<Recorded>('operate_session.json').then(r => { setRec(r); setT(6 * 3600) })
      .catch(() => setErr('Recorded session missing: replay/operate_session.json (run python scripts/record_operate.py).'))
  }, [online, rec])
  useEffect(() => {
    if (online || !rec || speed === 0) return
    let raf = 0, last = performance.now()
    const tick = (now: number) => { const dt = (now - last) / 1000; last = now; setT(x => Math.min(x + dt * speed, 86399)); raf = requestAnimationFrame(tick) }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [online, rec, speed])
  const recorded = useMemo(() => (!online && rec ? frameAt(rec, t, speed) : null), [online, rec, t, speed])

  const act = async (path: string, body: any) => {
    if (!online) throw new Error('needs the live backend')
    const r = await post<any>(path, body)
    return r
  }
  return {
    snap: online ? snap : recorded, err, mode: online ? 'live' as const : 'recorded' as const,
    recordedAt: rec?.recorded_at ?? null,
    setSpeed: async (v: number) => { if (online) { const s = await act('/operate/control', { speed: v }); setSnap(s) } else setSpeedLocal(v) },
    seek: (s: number) => { if (!online) setT(s) },
    setSource: async (source: string, hist_day?: string) => { const s = await act('/operate/control', { source, hist_day }); setSnap(s) },
    inject: (kind: string, minutes: number) => act('/operate/event', { kind, minutes }),
    override: (o: { zone: string; device: string; state: string; minutes: number }) => act('/operate/override', { ...o, confirm: true }),
    clearOverride: (id: number) => fetch(`${API}/operate/override/${id}`, { method: 'DELETE' }),
    rule: (text: string) => act('/operate/rule', { text }),
    report: async (): Promise<OpReport | null> => (online ? (await fetch(`${API}/operate/report`)).json() : rec?.report ?? null),
  }
}
