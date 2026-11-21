// Light editorial palette (the only colours used). Architectural scale model photographed in daylight.
export const C = {
  bg: '#FAFAF7', text: '#1A1A1A', muted: '#6B6B6B', hair: '#E5E5E0', accent: '#2F6BFF',
  solar: '#1E9E5A', grid: '#D64545', battery: '#D99A1E', quantum: '#6C4CF5', water: '#3A8DDE',
  clay: '#F2F1EC', ground: '#E9E8E2', road: '#D9D8D1', panel: '#3A6FB0', offline: '#B9B8B1',
}
export const rs = (v: number) => `${v < 0 ? '−' : ''}Rs ${Math.abs(Math.round(v)).toLocaleString('en-IN')}`
export const num = (v: number, d = 0) => v.toLocaleString('en-IN', { maximumFractionDigits: d, minimumFractionDigits: d })
export const kw = (v: number) => `${Math.round(v).toLocaleString('en-IN')} kW`
export const pct = (v: number) => `${Math.round(v)}%`
export const signed = (v: number, unit = 'kW') => `${v >= 0 ? '+' : '−'}${Math.abs(Math.round(v)).toLocaleString('en-IN')} ${unit}`
export const ZONE: Record<string, string> = {
  academic: 'Academic blocks', heavy_labs: 'Mechanical labs', hostels: 'Hostels', library: 'Library', canteen: 'Food court',
  admin: 'Admin block', server_room: 'Server room', health_centre: 'Health centre', pumping_station: 'Pump house',
}
export const zn = (z: string) => ZONE[z] ?? z
export const SCEN: Record<string, string> = { teaching: 'Teaching day', exam_week: 'Exam week', vacation: 'Vacation day', fest: 'Fest day',
  monsoon: 'Monsoon day', outage_fest: 'Outage during the fest' }
export const fmtDate = (d: string) => new Date(d + 'T00:00').toLocaleDateString('en-IN', { day: 'numeric', month: 'long', year: 'numeric' })
