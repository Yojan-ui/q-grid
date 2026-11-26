// Top-bar theme control: sun / moon button, menu with Light / Dark / System. Shortcut "D" cycles (handled in App).
import { useEffect, useRef, useState } from 'react'
import type { ThemeMode, ThemeName } from '../lib/theme'

const Sun = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
const Moon = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z" /></svg>
const Screen = () => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" /></svg>

const OPTS: [ThemeMode, string, () => React.ReactElement][] = [['light', 'Light', Sun], ['dark', 'Dark', Moon], ['system', 'System', Screen]]

export function ThemeToggle({ mode, name, setMode }: { mode: ThemeMode; name: ThemeName; setMode: (m: ThemeMode) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const items = useRef<(HTMLButtonElement | null)[]>([])
  useEffect(() => {
    if (!open) return
    const f = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('click', f)
    items.current[OPTS.findIndex(o => o[0] === mode)]?.focus()
    return () => document.removeEventListener('click', f)
  }, [open])
  const onKey = (e: React.KeyboardEvent) => {
    const k = items.current.findIndex(b => b === document.activeElement)
    if (e.key === 'Escape') { setOpen(false); (ref.current?.querySelector('.iconbtn') as HTMLElement)?.focus() }
    if (e.key === 'ArrowDown') { e.preventDefault(); e.stopPropagation(); items.current[(k + 1) % OPTS.length]?.focus() }
    if (e.key === 'ArrowUp') { e.preventDefault(); e.stopPropagation(); items.current[(k + OPTS.length - 1) % OPTS.length]?.focus() }
  }
  const label = `Theme: ${OPTS.find(o => o[0] === mode)![1]}${mode === 'system' ? ` (${name})` : ''}. Press D to cycle.`
  return (
    <div className="themebtn" ref={ref} onKeyDown={onKey}>
      <button className="iconbtn" aria-haspopup="menu" aria-expanded={open} aria-label={label} title={label} onClick={() => setOpen(o => !o)}>
        {name === 'dark' ? <Moon /> : <Sun />}
      </button>
      {open && (
        <div className="thememenu" role="menu" aria-label="Colour theme">
          {OPTS.map(([m, l, Icon], i) => (
            <button key={m} role="menuitemradio" aria-checked={mode === m} ref={b => { items.current[i] = b }}
              onClick={() => { setMode(m); setOpen(false) }}>
              <Icon />{l}{m === 'system' && <span className="muted small">({name})</span>}<span className="chk" aria-hidden="true">✓</span>
            </button>
          ))}
          <div className="kbd small muted">Press <kbd>D</kbd> to cycle</div>
        </div>
      )}
    </div>
  )
}
