// Screenshots for docs/audit.md: one per audited item (1440x900, JPEG), offline unless noted.
//   node scripts/audit_shots.mjs --url http://localhost:4173 --out ../docs/media/audit [--live]   (--live: backend on :8000)
import { mkdirSync, writeFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { evaluate, launch, sleep, waitFor } from './cdp.mjs'

const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d }
const URL0 = arg('url', 'http://localhost:4173'), OUT = resolve(arg('out', '../docs/media/audit'))
const LIVE = process.argv.includes('--live')
const click = (sel, re) => `(() => { const b = [...document.querySelectorAll('${sel}')].find(x => ${re}.test(x.textContent)); if (b) { b.scrollIntoView({ block: 'center' }); b.click(); return true } return false })()`
const seek = s => `(() => { const r = document.querySelector('.op-seek'); if (!r) return; Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(r, ${s}); r.dispatchEvent(new Event('input', { bubbles: true })) })()`
// [file, query, wait-for selector, settle ms, optional actions]
const SHOTS = [
  ...['1', '2', '3', '4a', '4b', '4c', '4d', '4e', '4f', '4g', '5', '5b', '6', '6b', '7a', '7f', '7b', '7c', '7d', '7e'].map(s => [`explain-${s}`, `?stop=${s}`, '.panel .answer', s === '1' || s === '3' ? 6000 : 3200]),
  ['live-qaoa', '?stop=4f', '.card.live', 2500, [click('.card.live button', '/Measure/')], 2500],
  ['live-remove', '?stop=5', '.card.live', 2500, [click('.card.live button', '/offline/')], 3500],
  ['live-rule', '?stop=6b', '.card.live', 2000, [click('.card.live .chip', '/^no DG$/')], 2500],
  ['live-rule-rejected', '?stop=6b', '.card.live', 2000, [click('.card.live .chip', '/EV charging/')], 2500],
  ['verify', '?mode=verify', '.metrics', 2500],
  ['verify-provenance', '?mode=verify', '.metrics', 2500, ["document.querySelector('.metrics tr.ours .num')?.click()"], 800],
  ['operate', '?mode=operate', '.op-grid', 3000, [seek(19 * 3600)], 1200],
  ['operate-messages', '?mode=operate', '.op-grid', 2500, [seek(13 * 3600 + 1800), click('.op-tabs button', '/^Messages$/')], 1000],
  ['operate-devices', '?mode=operate', '.op-grid', 2500, [click('.op-tabs button', '/^Devices$/')], 800],
  ['operate-override', '?mode=operate', '.op-grid', 2500, [seek(12 * 3600), click('.op-tabs button', '/^Override$/')], 800],
  ['operate-rules', '?mode=operate', '.op-grid', 2500, [seek(12 * 3600), click('.op-tabs button', '/^Rules$/')], 800],
  ['operate-report', '?mode=operate', '.op-grid', 2500, [seek(86399), click('.op-tabs button', '/^Report$/'), click('.opreport button', '/report/i')], 2500],
  ['deploy', '?mode=deploy', '.arch', 2500],
  ['deploy-rollout', '?mode=deploy', '.arch', 2000, ["document.querySelector('.phases')?.scrollIntoView({block:'start'})"], 800],
  ['deploy-economics', '?mode=deploy', '.arch', 2000, ["document.querySelector('.keys-row')?.scrollIntoView({block:'center'})"], 800],
  ['deploy-safety', '?mode=deploy', '.arch', 2000, ["document.querySelector('.safety')?.scrollIntoView({block:'center'})"], 800],
  ['deploy-shadow', '?mode=deploy', '.arch', 2000, ["document.querySelector('.mailreport')?.scrollIntoView({block:'start'})"], 800],
  ['dark-explain-1', '?stop=1&theme=dark', '.panel .answer', 6000],
  ['dark-explain-4d', '?stop=4d&theme=dark', '.panel .answer', 3500],
  ['dark-operate', '?mode=operate&theme=dark', '.op-grid', 3000, [seek(19 * 3600)], 1200],
  ['dark-deploy', '?mode=deploy&theme=dark', '.arch', 2500],
  ['theme-menu', '?stop=2', '.panel .answer', 3000, ["document.querySelector('.iconbtn')?.click()"], 600],
  ['data-badge', '?stop=2', '.panel .answer', 3000, ["document.querySelector('.databadge button')?.click()"], 600],
  ['presenter', '?stop=7a&present', '.panel .answer', 3000],
  ['demo-preset', '?demo', '.panel .answer', 5000],
]
mkdirSync(OUT, { recursive: true })
const { cdp, close } = await launch(arg('chrome'))
try {
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false })
  for (const [name, qs, sel, wait, acts = [], after = 0] of SHOTS) {
    const url = `${URL0}/${qs}${LIVE || name === 'demo-preset' ? '' : '&offline'}`
    await cdp.send('Page.navigate', { url })
    try { await waitFor(cdp, `!!document.querySelector('${sel}')`, 40000) } catch { console.log('timeout', name) }
    await sleep(wait)
    for (const a of acts) { await evaluate(cdp, a); await sleep(300) }
    if (after) await sleep(after)
    const shot = await cdp.send('Page.captureScreenshot', { format: 'jpeg', quality: 72 }, 120000)
    writeFileSync(join(OUT, `${name}.jpg`), Buffer.from(shot.data, 'base64'))
    console.log('✓', name)
  }
} finally { await close() }
