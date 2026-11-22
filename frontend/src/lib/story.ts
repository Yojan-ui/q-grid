// The guided story: stops, and the facts each stop shows. Every number is read from replay files produced by
// scripts/make_replay.py (results/*.csv / *.json); this module only selects and formats them.
import { useEffect, useState } from 'react'
import { getCSV, getJSON, type LiveSolve, type QaoaFile, type Scenario, type V2Data, type V2Example } from './data'

export type StopId = '1' | '2' | '3' | '4a' | '4b' | '4c' | '4d' | '4e' | '4f' | '4g' | '5' | '5b' | '6' | '7a' | '7b'
export const STOPS: { id: StopId; step: number; title: string }[] = [
  { id: '1', step: 1, title: 'The problem' },
  { id: '2', step: 2, title: 'The campus' },
  { id: '3', step: 3, title: 'The decisions' },
  { id: '4a', step: 4, title: 'Decisions become qubits' },
  { id: '4b', step: 4, title: 'Rules become one cost' },
  { id: '4c', step: 4, title: 'The QAOA circuit' },
  { id: '4d', step: 4, title: 'Measure' },
  { id: '4e', step: 4, title: 'Decode the plan' },
  { id: '4f', step: 4, title: 'Verify' },
  { id: '4g', step: 4, title: 'Who does what' },
  { id: '5', step: 5, title: 'Buildings agree' },
  { id: '5b', step: 5, title: 'How the two halves talk' },
  { id: '6', step: 6, title: 'Storage behaviour' },
  { id: '7a', step: 7, title: 'Results' },
  { id: '7b', step: 7, title: 'Scale' },
]
export const STEP_COUNT = 7
export const subOf = (id: StopId) => STOPS.filter(s => s.step === STOPS.find(x => x.id === id)!.step)

export type SummaryRow = Record<string, string>
export type ProblemDay = { scenarios: Record<string, Record<string, number | string>> }
export type SearchSpace = { centralised_full_day: { N_binary: number; log10_states: number; slots: number; formula: string; vars_per_slot: Record<string, number> };
  local_qubo_qubits: Record<string, number>; note: string }

export type StoryData = {
  sc: Scenario
  q: QaoaFile
  example: LiveSolve
  miss: LiveSolve | null
  summary: SummaryRow[]
  problem: Record<string, number | string> | null
  search: SearchSpace | null
  robust: Record<string, string>[]
  admmSlot: number
  admmRounds: { k: number; r_primal: number; agreed: boolean; proposals: Record<string, number[]> }[]
  v2: V2Data | null                 // optimiser v2 results for this day (null if the v2 benchmark has not been run)
  v2ex: V2Example | null            // v2 worked example (headline day only)
}

/** The worked example: the headline day's server room at the outage evening slot (a live_solve record);
 *  falls back to the first live_solve record whose QAOA answer matched the exact one. */
function pickExample(live: LiveSolve[]) {
  return live.find(l => l.zone === 'server_room' && l.slot === 76) ?? live.find(l => l.qaoa.best_bits === l.exact.bits) ?? live[0]
}
function pickMiss(live: LiveSolve[]) {
  return live.find(l => l.zone === 'hostels' && l.slot === 76 && l.qaoa.best_bits !== l.exact.bits) ?? live.find(l => l.qaoa.best_bits !== l.exact.bits) ?? null
}
/** ADMM slot to replay: among slots whose rounds ended in full agreement with energy moving, the one where the
 *  number of agreed cables grows most steadily round by round (the clearest picture of a negotiation). */
function pickAdmmSlot(sc: Scenario) {
  const it = sc.admm.iterations
  let best = -1, score = -1
  for (const k of Object.keys(it).map(Number).sort((a, b) => a - b)) {
    const rounds = it[String(k)]
    const last = rounds?.[rounds.length - 1]
    if (!last?.agreed || !Object.values(last.proposals).some(p => Math.abs(p[0]) > 1) || rounds.length < 5) continue
    const agreed = rounds.map(r => Object.values(r.proposals).filter(([a, b]) => Math.abs(a - b) < 1).length)
    const s = agreed.slice(1).filter((v, i) => v > agreed[i]).length
    if (s > score) { score = s; best = k }
  }
  return best >= 0 ? best : 76
}

export function useStoryData(key: string) {
  const [d, setD] = useState<StoryData | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => {
    if (!key) return
    let off = false
    ;(async () => {
      try {
        const sc = await getJSON<Scenario>(`scenario_${key}.json`)
        const q = await getJSON<QaoaFile>(sc.qaoa_file)
        const [summary, robust] = await Promise.all([getCSV('benchmark_summary.csv'), getCSV('robustness.csv')])
        const problem = await getJSON<{ scenarios: Record<string, Record<string, number | string>> }>('problem_day.json').then(p => p.scenarios[key] ?? null).catch(() => null)
        const search = await getJSON<SearchSpace>('search_space.json').catch(() => null)
        const live = sc.live_solve ?? []
        if (!live.length) throw new Error('scenario has no live_solve records (worked example)')
        // optimiser v2: when its run exists, "Q-Grid" in the story is the v2 run (v1 kept as qgrid_v1 for comparison)
        if (sc.runs.qgrid_v2) { (sc.runs as any).qgrid_v1 = sc.runs.qgrid; sc.runs.qgrid = sc.runs.qgrid_v2 }
        const v2ex = sc.v2?.example ?? null
        const example: LiveSolve = v2ex ? { ...v2ex.block, explanation: [] } : pickExample(live)
        const admmSlot = v2ex ? v2ex.slot : pickAdmmSlot(sc)
        const admmRounds = v2ex ? v2ex.admm_rounds : (sc.admm.iterations[String(admmSlot)] ?? [])
        if (!off) setD({ sc, q, example, miss: v2ex ? null : pickMiss(live), summary, problem, search, robust, admmSlot, admmRounds,
          v2: sc.v2 ?? null, v2ex })
      } catch (e) { if (!off) setErr(String(e)) }
    })()
    return () => { off = true }
  }, [key])
  return { d, err }
}

/** Campus-wide state of charge (energy-weighted) for one run, per slot boundary (97 values). */
export function campusSoc(sc: Scenario, run: 'qgrid' | 'status_quo') {
  const r = sc.runs[run]
  if (!r) return []
  const kwh = sc.campus.zones.map(z => z.battery_kwh), tot = kwh.reduce((a, b) => a + b, 0) || 1
  return r.soc[0].map((_, t) => kwh.reduce((a, k, i) => a + k * (r.soc[i][t] ?? 0), 0) / tot)
}

export const sumZones = (m: number[][], t: number) => m.reduce((a, z) => a + (z[t] ?? 0), 0)
