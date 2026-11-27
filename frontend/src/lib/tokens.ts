// Theme tokens: the single source of truth for both themes (pure data, no React / DOM, so vite.config.ts can import
// it). CSS variables (--kebab-case) are generated from these objects at build time and injected into index.html before
// first paint; JS-drawn colours (charts, SVG, three.js) read the same objects through useC() in theme.ts.
//   *Ink tokens are the text versions of semantic colours (>= 4.5:1 on bg and surface); the plain tokens are marks
//   (>= 3:1). scripts/check-contrast.mjs enforces both, in both themes.
export type Palette = {
  // surfaces and text
  bg: string; surface: string; raised: string; sunken: string
  text: string; text2: string; muted: string; faint: string; hair: string
  onInverse: string; inverseHover: string
  // semantic marks and their text inks
  accent: string; solar: string; grid: string; battery: string; quantum: string; water: string
  accentInk: string; solarInk: string; gridInk: string; batteryInk: string; quantumInk: string; waterInk: string
  quantumSoft: string; quantumLine: string; quantumMid: string
  pendFg: string; pendBg: string; pendLine: string
  okBg: string; okLine: string; gridSoft: string; gridLine: string
  diesel: string; offline: string; barMuted: string; neutralMark: string; refLine: string
  labelBg: string; veil: string; overlay: string; shadow: string
  // 3D scene
  ground: string; plot: string; road: string; clay: string; batteryFill: string
  pv: string; pvGlow: string; pvGlowMax: number
  dieselIdle: string; substation: string; substationDown: string
  tile: string; tileOn: string; glass: string; glassOpacity: number; wire: string; critical: string
  hemiSky: string; hemiGround: string; hemiI: number
  keyDay: string; keyNight: string; keyBase: number; keyGain: number
  shadowI: number; shadowRadius: number; fogNear: number; fogFar: number
}

export const LIGHT: Palette = {
  bg: '#FAFAF7', surface: '#FFFFFF', raised: '#FFFFFF', sunken: '#EFEEE8',
  text: '#1A1A1A', text2: '#3A3A3A', muted: '#6B6B6B', faint: '#A3A39C', hair: '#E5E5E0',
  onInverse: '#FFFFFF', inverseHover: '#000000',
  accent: '#2F6BFF', solar: '#1E9E5A', grid: '#D64545', battery: '#B8841A', quantum: '#6C4CF5', water: '#3A8DDE',
  accentInk: '#2A5FE6', solarInk: '#157843', gridInk: '#C23B3B', batteryInk: '#8A5A00', quantumInk: '#6445F0', waterInk: '#2471B8',
  quantumSoft: '#F1EEFF', quantumLine: '#D9D1FD', quantumMid: '#C9BFFB',
  pendFg: '#8A5A00', pendBg: '#FFF4DC', pendLine: '#F2DDA8',
  okBg: '#E6F5EC', okLine: '#BFE3CD', gridSoft: '#F6E3E3', gridLine: '#F1C9C9',
  diesel: '#7A7A74', offline: '#B9B8B1', barMuted: '#E2E1DB', neutralMark: '#C9C8C1', refLine: '#B9B8B1',
  labelBg: 'rgba(255,255,255,.92)', veil: 'rgba(250,250,247,.86)', overlay: 'rgba(26,26,26,.18)', shadow: 'rgba(26,26,26,.08)',
  ground: '#F1F0EB', plot: '#F7F6F2', road: '#DAD9D2', clay: '#F2F1EC', batteryFill: '#D99A1E',
  pv: '#5674C6', pvGlow: '#000000', pvGlowMax: 0,
  dieselIdle: '#D9D8D2', substation: '#E9E8E2', substationDown: '#CFCEC8',
  tile: '#FFFFFF', tileOn: '#EEEAFF', glass: '#FFFFFF', glassOpacity: 0.45, wire: '#BDBCB5', critical: '#FFFFFF',
  hemiSky: '#FFFFFF', hemiGround: '#DEDBD2', hemiI: 2.35,
  keyDay: '#FFFDF6', keyNight: '#FFEBD2', keyBase: 1.1, keyGain: 1.5,
  shadowI: 1, shadowRadius: 6, fogNear: 1300, fogFar: 3200,
}

export const DARK: Palette = {
  bg: '#111315', surface: '#181B1F', raised: '#1F2328', sunken: '#23272D',
  text: '#ECEDEE', text2: '#C9CDD1', muted: '#9BA1A6', faint: '#5A6068', hair: '#2A2F35',
  onInverse: '#111315', inverseHover: '#FFFFFF',
  accent: '#6E9BFF', solar: '#3FBF7F', grid: '#F06A6A', battery: '#E8B04A', quantum: '#9A86FF', water: '#5AA9F0',
  accentInk: '#6E9BFF', solarInk: '#3FBF7F', gridInk: '#F06A6A', batteryInk: '#E8B04A', quantumInk: '#9A86FF', waterInk: '#5AA9F0',
  quantumSoft: '#231F38', quantumLine: '#4A3F80', quantumMid: '#6A5DB8',
  pendFg: '#E8B04A', pendBg: '#2B2416', pendLine: '#5C4A1F',
  okBg: '#15281E', okLine: '#2A5A3E', gridSoft: '#331D20', gridLine: '#6A3036',
  diesel: '#8A9096', offline: '#4A5058', barMuted: '#555B63', neutralMark: '#4A5058', refLine: '#5A6068',
  labelBg: 'rgba(24,27,31,.92)', veil: 'rgba(17,19,21,.84)', overlay: 'rgba(0,0,0,.5)', shadow: 'rgba(0,0,0,.35)',
  ground: '#1A1D21', plot: '#1F2328', road: '#2E333A', clay: '#3A3F46', batteryFill: '#E8B04A',
  pv: '#22365E', pvGlow: '#3A5FC0', pvGlowMax: 0.22,
  dieselIdle: '#2E333A', substation: '#3A3F46', substationDown: '#2A2F35',
  tile: '#1F2328', tileOn: '#2C2650', glass: '#9FB4D6', glassOpacity: 0.22, wire: '#4A5058', critical: '#3A3F46',
  hemiSky: '#A9B8D6', hemiGround: '#2A2F35', hemiI: 1.45,
  keyDay: '#E6EAF2', keyNight: '#C9D6F2', keyBase: 1.05, keyGain: 0.7,
  shadowI: 0.5, shadowRadius: 10, fogNear: 1100, fogFar: 3000,
}

export const PALETTES = { light: LIGHT, dark: DARK } as const
export type ThemeName = keyof typeof PALETTES
export type ThemeMode = ThemeName | 'system'

/** CSS custom properties for one palette (strings only; numbers are 3D-only). */
export function cssVars(p: Palette): string {
  return Object.entries(p).filter(([, v]) => typeof v === 'string')
    .map(([k, v]) => `--${k.replace(/[A-Z]/g, m => '-' + m.toLowerCase())}:${v}`).join(';')
}
/** The <style> block injected into index.html: both themes, keyed on <html data-theme>. */
export const themeStyle = () =>
  `:root,:root[data-theme=light]{${cssVars(LIGHT)};color-scheme:light}:root[data-theme=dark]{${cssVars(DARK)};color-scheme:dark}`

