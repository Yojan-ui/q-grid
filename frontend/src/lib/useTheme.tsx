// Theme mode (light / dark / system): the attribute on <html> is set before first paint by the inline script that
// vite.config.ts injects; this hook keeps React in sync, follows the OS while in "system", and remembers the choice.
import { useCallback, useEffect, useState } from 'react'
import { PALETTES, reducedMotion, type ThemeMode, type ThemeName } from './theme'

const KEY = 'qgrid-theme'
const sysDark = () => !!window.matchMedia?.('(prefers-color-scheme: dark)').matches
const resolve = (m: ThemeMode): ThemeName => (m === 'system' ? (sysDark() ? 'dark' : 'light') : m)
const initialMode = (): ThemeMode => {
  const m = document.documentElement.getAttribute('data-mode')
  return m === 'light' || m === 'dark' || m === 'system' ? m : 'system'
}

export function useTheme() {
  const [mode, setModeState] = useState<ThemeMode>(initialMode)
  const [name, setName] = useState<ThemeName>(() => resolve(initialMode()))

  const apply = useCallback((n: ThemeName, animate: boolean) => {
    const h = document.documentElement
    if (h.getAttribute('data-theme') === n) return
    if (animate && !reducedMotion()) {
      h.classList.add('theme-anim')
      window.setTimeout(() => h.classList.remove('theme-anim'), 260)
    }
    h.setAttribute('data-theme', n)
  }, [])

  const setMode = useCallback((m: ThemeMode) => {
    try { localStorage.setItem(KEY, m) } catch { /* private mode or storage disabled: keep it for this visit only */ }
    document.documentElement.setAttribute('data-mode', m)
    setModeState(m)
    const n = resolve(m)
    apply(n, true)
    setName(n)
  }, [apply])

  // follow the OS while in "system"
  useEffect(() => {
    if (mode !== 'system' || !window.matchMedia) return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const f = () => { const n = mq.matches ? 'dark' : 'light'; apply(n, true); setName(n) }
    mq.addEventListener?.('change', f)
    return () => mq.removeEventListener?.('change', f)
  }, [mode, apply])

  const cycle = useCallback(() => setMode(mode === 'light' ? 'dark' : mode === 'dark' ? 'system' : 'light'), [mode, setMode])
  return { mode, name, C: PALETTES[name], setMode, cycle }
}
