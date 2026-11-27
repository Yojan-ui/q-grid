// First-screen time on a build: navigation start -> story headline visible, and -> 3D canvas painted. Cold profile each run.
//   node scripts/check-speed.mjs --url http://localhost:4173 [--runs 3]
import { evaluate, launch, sleep, waitFor } from './cdp.mjs'
const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d }
const URL0 = arg('url', 'http://localhost:4173'), RUNS = +arg('runs', '3')
const res = []
for (let r = 0; r < RUNS; r++) {
  const { cdp, close } = await launch()
  try {
    await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false })
    const t0 = Date.now()
    await cdp.send('Page.navigate', { url: `${URL0}/?stop=1&offline` })
    await waitFor(cdp, `!!document.querySelector('.panel .answer')`, 30000); const t1 = Date.now() - t0
    await waitFor(cdp, `!!document.querySelector('.stage canvas')`, 30000); const t2 = Date.now() - t0
    const kb = await evaluate(cdp, `Math.round(performance.getEntriesByType('resource').reduce((a, e) => a + (e.transferSize || 0), 0) / 1024)`)
    res.push({ t1, t2, kb }); console.log(`run ${r + 1}: headline ${t1} ms, 3D ${t2} ms, ${kb} kB transferred`)
  } finally { await close() }
  await sleep(300)
}
const worst = Math.max(...res.map(x => x.t1))
console.log(`first screen (worst of ${RUNS}): ${worst} ms ${worst < 3000 ? '< 3 s ✓' : '≥ 3 s ✗'}`)
process.exit(worst < 3000 ? 0 : 1)
