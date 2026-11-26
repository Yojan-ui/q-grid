// Screenshots of the three modes (Explain step 7f Sankey, Operate live / recorded, Deploy), both themes.
//   node scripts/capture_modes.mjs --url http://localhost:5173 --out DIR [--size 1440x900]
import { mkdirSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { evaluate, launch, sleep, waitFor } from './cdp.mjs'

const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d }
const URL0 = arg('url', 'http://localhost:5173'), OUT = resolve(arg('out', 'shots-modes'))
const [W, H] = arg('size', '1440x900').split('x').map(Number)
const VIEWS = [
  ['explain-7f', '?stop=7f', '.panel .answer', 3500],
  ['operate-live', '?mode=operate', '.op-grid', 6000],
  ['operate-recorded', '?mode=operate&offline', '.op-grid', 3000],
  ['deploy', '?mode=deploy', '.arch', 2500],
]
mkdirSync(OUT, { recursive: true })
const { cdp, close } = await launch(arg('chrome'))
const errs = []
cdp.on('Runtime.exceptionThrown', p => errs.push(p.exceptionDetails?.exception?.description?.slice(0, 200)))
try {
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false })
  for (const theme of (arg('themes', 'light,dark')).split(',')) for (const [name, qs, sel, wait] of VIEWS) {
    await cdp.send('Page.navigate', { url: `${URL0}/${qs}&theme=${theme}` })
    try { await waitFor(cdp, `!!document.querySelector('${sel}')`, 40000) } catch { console.log('timeout', name, theme) }
    await sleep(wait)
    if (name === 'operate-recorded') {   // jump the recorded day to the evening outage, show the report tab
      await evaluate(cdp, `(() => { const r = document.querySelector('.op-seek'); if (!r) return; const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set; s.call(r, 19 * 3600); r.dispatchEvent(new Event('input', { bubbles: true })) })()`)
      await sleep(800)
    }
    writeFileSync(join(OUT, `${theme}_${name}.png`), Buffer.from((await cdp.send('Page.captureScreenshot', { format: 'png' })).data, 'base64'))
    const over = await evaluate(cdp, `[...document.querySelectorAll('.op-col, .op-panel, main')].filter(e => e.scrollWidth > e.clientWidth + 2).map(e => e.className).slice(0, 4)`)
    console.log(theme, name, 'h-overflow:', JSON.stringify(over))
  }
  console.log('errors:', [...new Set(errs)])
} finally { await close() }
