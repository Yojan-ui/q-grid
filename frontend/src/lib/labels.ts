// Plain-English names for zones, QUBO variables and benchmark methods. Text only: no numbers are made here.
import type { Scenario, Zone } from './data'

export const ZONE_NAME: Record<string, string> = {
  academic: 'Academic blocks', heavy_labs: 'Mechanical labs', hostels: 'Hostels', library: 'Library', canteen: 'Food court',
  admin: 'Admin block', server_room: 'Server room', health_centre: 'Health centre', pumping_station: 'Pump house',
}
export const zn = (z: string) => ZONE_NAME[z] ?? z.replace(/_/g, ' ')

export const METHOD: Record<string, string> = {
  B0: 'Status quo (today)', B1: 'Rule-based controller', 'B2-GA': 'Genetic algorithm', 'B2-PSO': 'Particle swarm',
  B3: 'Per-zone MPC (MILP)', B4: 'Central optimum (MILP)', B5: 'ADMM + exact local solver', 'B5-nobattery': 'ADMM, no batteries',
  'C-QIEA': 'Central QUBO + QIEA', OURS: 'Q-Grid (QAOA tiers)', 'OURS-QIEA': 'Q-Grid with QIEA tier',
}

export const SCENARIO_NAME: Record<string, string> = {
  teaching: 'Teaching day', exam_week: 'Exam week', vacation: 'Vacation', fest: 'Fest day', monsoon: 'Monsoon day',
  outage_fest: 'Outage during the fest',
}
export const fmtDate = (d: string) => new Date(d + 'T00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })

export type Device = { key: 'pv' | 'battery' | 'dg' | 'tank' | 'critical' | 'flex'; id?: string; label: string; detail: string }

/** Devices of a zone, straight from the campus model in the replay. */
const cap = (x: string) => x.charAt(0).toUpperCase() + x.slice(1)
const num0 = (v: number) => Math.round(v).toLocaleString('en-IN')

export function devices(z: Zone, sc: Scenario): Device[] {
  const out: Device[] = []
  if (z.pv_kwp > 0) out.push({ key: 'pv', label: 'Rooftop solar', detail: `${Math.round(z.pv_kwp).toLocaleString('en-IN')} kWp` })
  if (z.battery_kwh > 0) out.push({ key: 'battery', label: 'Battery', detail: `${z.battery_kwh} kWh · ${z.battery_kw} kW` })
  if (z.dg_kw > 0) out.push({ key: 'dg', label: 'Diesel generator', detail: `${z.dg_kw} kW` })
  if (z.tank_m3 > 0) out.push({ key: 'tank', label: 'Borewell pump + tank', detail: `${z.tank_m3} m³` })
  if (z.critical_frac > 0) out.push({ key: 'critical', label: 'Critical load', detail: `${Math.round(z.critical_frac * 100)}% of demand` })
  if (z.flex?.length) {
    // per flexible load: power and run length (one 15-min slot each), from the replay's zone export
    for (const f of z.flex) out.push({ key: 'flex', id: `flex-${f.name}`, label: cap(f.name.replace(/_/g, ' ')) + ' (flexible)', detail: `${num0(f.kw)} kW · ${f.slots * 15} min, start time chosen` })
  } else {
    const zi = sc.campus.zones.indexOf(z)
    const fs = sc.runs.qgrid.flex_start?.[zi]
    if (fs && Object.keys(fs).length) out.push({ key: 'flex', label: 'Flexible loads', detail: Object.keys(fs).map(k => k.replace(/_/g, ' ')).join(', ') })
  }
  return out
}

const hhmm = (sc: Scenario, slot: number) => sc.slots.t[Math.min(95, slot)]

/** One QUBO variable as a yes/no question a person understands. */
export function varLabel(v: string, zone: string, slot: number, sc: Scenario): { short: string; device: string; yes: string; no: string } {
  const step = sc.campus.line_step_kw
  const k = Number(v.slice(1))
  if (/^c\d$/.test(v)) return { short: k === 0 ? 'Charge battery now' : `Charge at ${hhmm(sc, slot + k)}`, device: 'battery', yes: 'charge', no: 'no charge' }
  if (/^d\d$/.test(v)) return { short: k === 0 ? 'Discharge battery now' : `Discharge at ${hhmm(sc, slot + k)}`, device: 'battery', yes: 'discharge', no: 'no discharge' }
  if (/^[pn]\d+$/.test(v)) {
    const [a, b] = sc.campus.lines[k]
    const other = zone === a ? b : a
    // p = flow a -> b on line k; n = flow b -> a (same sign convention as the replay flows)
    const send = (v[0] === 'p') === (zone === a)
    return send
      ? { short: `Send ${step} kW to ${zn(other)}`, device: 'cable', yes: `send ${step} kW`, no: 'no send' }
      : { short: `Take ${step} kW from ${zn(other)}`, device: 'cable', yes: `take ${step} kW`, no: 'no take' }
  }
  if (v === 'g') return { short: 'Run diesel generator', device: 'dg', yes: 'diesel ON', no: 'diesel OFF' }
  if (v === 'w') return { short: 'Run borewell pump', device: 'tank', yes: 'pump ON', no: 'pump OFF' }
  if (v.startsWith('s:')) return { short: `Start ${v.slice(2).replace(/_/g, ' ')} now`, device: 'flex', yes: 'start now', no: 'later' }
  return { short: v, device: 'other', yes: '1', no: '0' }
}

/** Structural rule that couples two variables (from qgrid/qubo.py penalty construction). */
export function pairRule(a: string, b: string): string | null {
  const s = [a, b].sort().join(' ')
  if (/^c(\d) d\1$/.test(s)) return 'battery can’t charge and discharge in the same slot'
  const m = s.match(/^n(\d+) p(\d+)$/)
  if (m && m[1] === m[2]) return 'a cable can’t send and receive at once'
  return null
}
