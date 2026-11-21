// Story beats and the worked quantum example, all derived from replay data (no invented numbers).
import type { QaoaFile, Scenario } from '../lib/data'
import { bits as bitsOf, sample } from '../lib/qaoa'
import { zn } from '../lib/theme'

export const BEATS = ['1', '2', '3', '4a', '4b', '4c', '4d', '4e', '4f', '4g', '5', '6', '7'] as const
export type Beat = typeof BEATS[number]
export const stepOf = (b: Beat) => Number(b[0])

/** Plain-language label and action for one decision variable of the worked-example zone. */
export function varInfo(v: string, sc: Scenario, zone: string) {
  const F = sc.campus.line_step_kw
  const slotName = (k: string) => (k === '0' ? 'now' : `in ${Number(k) * 15} min`)
  const sn = (k: string) => (k === '0' ? 'now' : `+${Number(k) * 15} min`)
  if (/^c\d$/.test(v)) return { label: `Charge battery ${slotName(v[1])}`, short: `charge ${sn(v[1])}`, on: 'Charge', off: 'No charge', kind: 'battery' }
  if (/^d\d$/.test(v)) return { label: `Discharge battery ${slotName(v[1])}`, short: `discharge ${sn(v[1])}`, on: 'Discharge', off: 'No discharge', kind: 'battery' }
  if (v === 'g') return { label: 'Run diesel generator', short: 'diesel', on: 'Diesel ON', off: 'Diesel OFF', kind: 'dg' }
  if (v === 'w') return { label: 'Run borewell pump', short: 'pump', on: 'Pump ON', off: 'Pump OFF', kind: 'water' }
  if (v.startsWith('s:')) { const j = v.slice(2).replace(/_/g, ' '); return { label: `Start ${j} now`, short: j, on: `Start ${j}`, off: `Wait (${j})`, kind: 'flex' } }
  const m = v.match(/^([pn])(\d+)$/)
  if (m) {
    const [a, b] = sc.campus.lines[Number(m[2])]
    const other = a === zone ? b : a
    const send = (m[1] === 'p') === (a === zone)
    return { label: `${send ? 'Send' : 'Receive'} ${F} kW ${send ? 'to' : 'from'} ${zn(other)}`, short: `${send ? 'send to' : 'from'} ${zn(other).split(' ')[0].toLowerCase()}`,
      on: `${send ? 'Send' : 'Receive'} ${F} kW`, off: 'No transfer', kind: 'line' }
  }
  return { label: v, short: v, on: 'Yes', off: 'No', kind: 'other' }
}

/** Measurement: top-10 bitstrings by probability; winner = best feasible of 256 seeded shots (what the solver does). */
export function measure(q: QaoaFile) {
  const P = Float64Array.from(q.probs)
  const order = Array.from(P.keys()).sort((a, b) => P[b] - P[a])
  const top10 = order.slice(0, 10)
  const shots = sample(P, 256, 1234)
  // like the solver: keep the cheapest feasible sample by the true objective (Rs), not by QUBO energy
  const obj = q.objectives ?? q.energies
  let win = -1
  for (const z of shots) if (q.feasible[z] && (win < 0 || obj[z] < obj[win])) win = z
  const opt = parseInt(q.optimum.bits.split('').reverse().join(''), 2)
  if (win >= 0 && !top10.includes(win)) { top10.pop(); top10.push(win) }
  top10.sort((a, b) => P[b] - P[a])
  const gap = win < 0 ? null : (obj[win] - obj[opt]) / Math.max(Math.abs(obj[opt]), 1e-9)
  return { top10, win, opt, P, gap, winBits: win >= 0 ? bitsOf(win, q.n_qubits) : null }
}

/** Plain-English rules that connect qubits, derived from which QUBO term groups are present. */
export function rulesFor(q: QaoaFile) {
  const g = q.groups ?? {}
  const out: { text: string; kind: string }[] = []
  if (g.grid) out.push({ text: 'Buying grid power costs rupees; selling earns less', kind: 'grid' })
  if (g.battery_ctg) out.push({ text: 'Energy kept in the battery is worth money later today', kind: 'battery' })
  if (g.dg_fuel) out.push({ text: 'Running the diesel generator burns fuel', kind: 'dg' })
  if (g.water_value) out.push({ text: 'Water pumped now does not need pumping later', kind: 'water' })
  if (g.flex_timing) out.push({ text: 'A flexible load runs once, at its cheapest allowed time', kind: 'flex' })
  if (q.var_names.some(v => /^c\d$/.test(v))) out.push({ text: 'Cannot charge and discharge in the same slot', kind: 'penalty' })
  if (q.var_names.some(v => /^[pn]\d+$/.test(v))) out.push({ text: 'A tie-line carries one flow at a time', kind: 'penalty' })
  if (q.var_names.some(v => /^c\d$/.test(v))) out.push({ text: 'Battery must stay between 20% and 95%', kind: 'penalty' })
  Object.keys(g).filter(k => k.startsWith('rule:')).forEach(k => out.push({ text: `Operator rule: ${k.slice(5).replace(/_/g, ' ')}`, kind: 'rule' }))
  return out
}

/** Strongest pairwise couplings (|M_ij|) for drawing interaction lines. */
export function couplings(q: QaoaFile, k = 18) {
  const M = q.qubo_matrix, n = M.length, out: { i: number; j: number; w: number }[] = []
  for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) if (Math.abs(M[i][j]) > 1e-9) out.push({ i, j, w: M[i][j] })
  out.sort((a, b) => Math.abs(b.w) - Math.abs(a.w))
  const top = out.slice(0, k), mx = Math.max(...top.map(x => Math.abs(x.w)), 1e-9)
  return top.map(x => ({ ...x, s: Math.abs(x.w) / mx }))
}

/** A slot where the buildings needed several negotiation rounds (most instructive for step 5). */
export function admmSlot(sc: Scenario) {
  const it = sc.admm.iterations
  let best = 76, bestN = 0
  for (const [t, rounds] of Object.entries(it)) {
    const n = rounds.length, tt = Number(t)
    if (tt >= 36 && tt <= 84 && n > bestN && n <= 12) { best = tt; bestN = n }
  }
  return best
}

export function campusSoc(sc: Scenario, run: 'qgrid' | 'status_quo') {
  const r = sc.runs[run]!, z = sc.campus.zones
  const tot = z.reduce((a, b) => a + b.battery_kwh, 0)
  return r.soc[0].map((_, t) => (100 * z.reduce((a, b, i) => a + b.battery_kwh * r.soc[i][t], 0)) / Math.max(tot, 1))
}
