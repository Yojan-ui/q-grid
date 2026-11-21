// Light editorial palette: an architectural scale model photographed in daylight.
// Semantic colours are used sparingly: solar, grid, battery, quantum, water.
export const C = {
  bg: '#FAFAF7', surface: '#FFFFFF', text: '#1A1A1A', muted: '#6B6B6B', faint: '#A3A39C', hair: '#E5E5E0',
  accent: '#2F6BFF', solar: '#1E9E5A', grid: '#D64545', battery: '#D99A1E', quantum: '#6C4CF5', water: '#3A8DDE',
  clay: '#F2F1EC', ground: '#F1F0EB', road: '#DAD9D2', pv: '#5674C6', offline: '#B9B8B1', diesel: '#7A7A74',
}

const MINUS = '−'
export const rs = (v: number) => `${v < 0 ? MINUS : ''}Rs ${Math.abs(Math.round(v)).toLocaleString('en-IN')}`
export const kw = (v: number) => `${Math.round(v).toLocaleString('en-IN')} kW`
export const pct = (v: number, d = 0) => `${v.toFixed(d)}%`
export const signed = (v: number, unit = 'kW') => `${v >= 0 ? '+' : MINUS}${Math.abs(Math.round(v)).toLocaleString('en-IN')} ${unit}`
export const num = (v: number, d = 0) => (v ?? 0).toLocaleString('en-IN', { maximumFractionDigits: d, minimumFractionDigits: d })

export const reducedMotion = () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
