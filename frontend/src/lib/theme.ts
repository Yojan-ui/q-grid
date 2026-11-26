// Theme access for components (the tokens themselves live in tokens.ts) plus number formatting helpers.
import { createContext, useContext } from 'react'
import { LIGHT, type Palette, type ThemeName } from './tokens'
export * from './tokens'

export const ThemeCtx = createContext<{ name: ThemeName; C: Palette }>({ name: 'light', C: LIGHT })
/** The active palette for JS-drawn colours (charts, SVG, three.js). */
export const useC = () => useContext(ThemeCtx).C
export const useThemeName = () => useContext(ThemeCtx).name

/** Static light palette for code outside React (and for print). Prefer useC() in components. */
export const C = LIGHT

const MINUS = '−'
export const rs = (v: number) => `${v < 0 ? MINUS : ''}Rs ${Math.abs(Math.round(v)).toLocaleString('en-IN')}`
export const kw = (v: number) => `${Math.round(v).toLocaleString('en-IN')} kW`
export const pct = (v: number, d = 0) => `${v.toFixed(d)}%`
export const signed = (v: number, unit = 'kW') => `${v >= 0 ? '+' : MINUS}${Math.abs(Math.round(v)).toLocaleString('en-IN')} ${unit}`
export const num = (v: number, d = 0) => (v ?? 0).toLocaleString('en-IN', { maximumFractionDigits: d, minimumFractionDigits: d })

export const reducedMotion = () => typeof window !== 'undefined' && !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
