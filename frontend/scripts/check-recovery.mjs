// Robustness: the app survives the backend going away and coming back (live moments fall back to precomputed results,
// the badge says so, and live mode returns by itself). Needs: vite on --url, and a backend start command.
//   node scripts/check-recovery.mjs --url http://localhost:5173 --restart "cd ../backend && python -m uvicorn qgrid.api:app --port 8000"
import { execSync, spawn } from 'node:child_process'
import { evaluate, launch, sleep, waitFor } from './cdp.mjs'
const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d }
const URL0 = arg('url', 'http://localhost:5173'), RESTART = arg('restart', '')
const badge = cdp => evaluate(cdp, `document.querySelector('.livebadge')?.textContent`)
const results = []
const ok = (name, cond, detail = '') => { results.push([name, cond]); console.log(`${cond ? '✓' : '✗'} ${name}${detail ? ' — ' + detail : ''}`) }
const { cdp, close } = await launch()
const errs = []
cdp.on('Runtime.exceptionThrown', p => errs.push(p.exceptionDetails?.exception?.description?.slice(0, 160)))
try {
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false })
  await cdp.send('Page.navigate', { url: `${URL0}/?stop=4f` })
  await waitFor(cdp, `!!document.querySelector('.panel .answer')`, 40000); await sleep(3000)
  ok('starts in live mode', (await badge(cdp)) === 'Live backend', await badge(cdp))
  execSync(`pkill -f "uvicorn qgrid.api:app" || true`)
  await sleep(17000)
  ok('notices the backend is gone (within 15 s)', (await badge(cdp)) === 'Offline replay', await badge(cdp))
  await evaluate(cdp, `[...document.querySelectorAll('.card.live button')].find(b => /Measure/.test(b.textContent))?.click()`)
  await sleep(2500)
  const src = await evaluate(cdp, `document.querySelector('.card.live .livesrc')?.textContent || ''`)
  ok('live moment falls back to the precomputed result, labelled', /Precomputed/.test(src), src.slice(0, 70))
  if (RESTART) {
    const p = spawn('bash', ['-lc', RESTART], { stdio: 'ignore', detached: true }); p.unref()
    await sleep(22000)
    ok('returns to live mode by itself', (await badge(cdp)) === 'Live backend', await badge(cdp))
  }
  ok('no uncaught errors', errs.length === 0, errs.join(' | '))
} finally { await close() }
process.exit(results.every(r => r[1]) ? 0 : 1)
