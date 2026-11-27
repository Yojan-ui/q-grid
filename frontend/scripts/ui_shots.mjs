// Screenshots of every screen in both themes (1440x900, JPEG q72), offline replay. Also reports, per screen, whether the
// explanation panel scrolls and whether any top-bar control is clipped or overlaps another.
//   node scripts/ui_shots.mjs --url http://localhost:5281 --out ../docs/media/agent-ui [--prefix fixture-] [--only plan,explain-1]
import { mkdirSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { evaluate, launch, sleep, waitFor } from './cdp.mjs'

const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d }
const URL0 = arg('url', 'http://localhost:5281'), OUT = resolve(arg('out', '../docs/media/agent-ui')), PREFIX = arg('prefix', '')
const ONLY = arg('only', '') ? arg('only', '').split(',') : null
const [W, H] = arg('size', '1440x900').split('x').map(Number)
const STOPS = ['1', '2', '3', '4a', '4b', '4c', '4d', '4e', '4f', '4g', '5', '5b', '6', '6b', '7a', '7f', '7b', '7c', '7d', '7e']
const SHOTS = [
  ...STOPS.map(s => [`explain-${s}`, `?stop=${s}`, '.panel .answer', s === '1' || s === '3' || s === '5' ? 6000 : 3200]),
  ['explain-2-zone', '?stop=2', '.panel .answer', 3000, `[...document.querySelectorAll('.chip')].find(b => b.textContent === 'Hostels')?.click()`],
  ['sources', '?stop=2', '.panel .answer', 3000, `document.querySelector('.infobtn')?.click()`],
  ['operate', '?mode=operate', '.op-grid', 3000],
  ['deploy', '?mode=deploy', '.arch', 2500],
  ['plan', '?mode=plan', '.plan .answer', 2500],
  ['verify', '?mode=verify', '.page .answer', 2500],
]
const CHECK = `(() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 }
  const bar = [...document.querySelectorAll('.top > *, .top .right > *')].filter(vis).map(e => ({ s: e.className || e.tagName, r: e.getBoundingClientRect() }))
  const bad = bar.filter(b => b.r.right > innerWidth + 1 || b.r.left < -1).map(b => 'clipped ' + b.s)
  for (let i = 0; i < bar.length; i++) for (let j = i + 1; j < bar.length; j++) { const a = bar[i].r, b = bar[j].r
    const inside = (x, y) => x.left <= y.left && x.right >= y.right && x.top <= y.top && x.bottom >= y.bottom
    if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1 && !inside(a, b) && !inside(b, a)) bad.push('overlap ' + bar[i].s + ' x ' + bar[j].s) }
  // text spilling out of a shrunk top-bar box (e.g. the brand running into the tabs)
  for (const e of document.querySelectorAll('.top > *, .top .right > *, .top .tabs button')) if (vis(e) && e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflow !== 'hidden') bad.push('text overflow ' + (e.className || e.tagName))
  const brand = document.querySelector('.brand b')?.getBoundingClientRect(), tabs = document.querySelector('.top .tabs')?.getBoundingClientRect()
  if (brand && tabs && brand.right > tabs.left + 1) bad.push('brand overlaps tabs')
  const p = document.querySelector('.panel-scroll')
  return { panelScroll: p ? Math.max(0, p.scrollHeight - p.clientHeight) : null, bar: bad, hscroll: document.documentElement.scrollWidth > innerWidth + 1 }
})()`

mkdirSync(OUT, { recursive: true })
const { cdp, close } = await launch(arg('chrome'))
const errs = []
cdp.on('Runtime.exceptionThrown', p => errs.push(p.exceptionDetails?.exception?.description?.slice(0, 200)))
const problems = []
try {
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false })
  for (const theme of ['light', 'dark']) for (const [name, qs, sel, wait, act] of SHOTS) {
    if (ONLY && !ONLY.includes(name)) continue
    await cdp.send('Page.navigate', { url: `${URL0}/${qs}&offline&theme=${theme}` })
    try { await waitFor(cdp, `!!document.querySelector('${sel}')`, 40000) } catch { problems.push(`${theme} ${name}: timeout`) }
    await sleep(wait)
    if (act) { await evaluate(cdp, act); await sleep(1500) }
    const c = await evaluate(cdp, CHECK)
    if (c.panelScroll > 4 || c.bar.length || c.hscroll) problems.push(`${theme} ${name}: ${JSON.stringify(c)}`)
    const shot = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 72 })
    writeFileSync(join(OUT, `${PREFIX}${theme}-${name}.jpg`), Buffer.from(shot.data, 'base64'))
    console.log('✓', theme, name)
  }
} finally { await close() }
console.log(`layout problems: ${problems.length}`); problems.forEach(p => console.log('  ✗', p))
console.log(`uncaught errors: ${errs.length}`); [...new Set(errs)].forEach(e => console.log('  ✗', e))
process.exit(problems.length || errs.length ? 1 : 0)
