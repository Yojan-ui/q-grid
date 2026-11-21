// The only colours used anywhere in the demo (art direction: architectural model at night).
export const C = {
  bg: '#0B0F14', surface: '#121821', border: '#1F2733', text: '#E6EAF0', muted: '#8A94A6',
  solar: '#3DDC97', grid: '#FF5A5F', battery: '#F5B544', quantum: '#8B7CFF', water: '#4FB3FF', offline: '#4A5263',
  road: '#1C2430', clayDay: '#C9CED6', clayNight: '#3A4250',
}
export const rs = (v: number) => `${v < 0 ? '−' : ''}Rs ${Math.abs(Math.round(v)).toLocaleString('en-IN')}`
export const kw = (v: number) => `${Math.round(v).toLocaleString('en-IN')} kW`
export const pct = (v: number) => `${Math.round(v)}%`
export const signed = (v: number, unit = 'kW') => `${v >= 0 ? '+' : '−'}${Math.abs(Math.round(v)).toLocaleString('en-IN')} ${unit}`
