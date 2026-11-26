// Numbers test: every number shown on every screen must come from the data the page loaded.
//   node scripts/check-numbers.mjs --url http://localhost:5173 [--verbose]
// For each screen (all Explain steps, Operate recorded session, Deploy, Verify) it collects the replay JSON the page
// fetched (the one shared data layer, lib/data.ts getJSON) and every number token in visible text. A token passes if
// (a) it equals, at its displayed precision, a scalar from those files (time series of > 40 values are not candidates,
//     so a figure cannot match a series by accident), allowing the display conversions the UI uses (fraction -> %,
//     hours -> minutes, Rs -> lakh, kW -> k), or
// (b) the page registered it as derived (lib/numcheck.ts reg(): a formula over loaded data, with a reason), or
// (c) it is a structural constant on the documented list below (step numbers, clock times, units of the design).
// Also: no card shows more than three numbers. Exit code 1 on any failure.
import { evaluate, key, launch, sleep, waitFor } from './cdp.mjs'

const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d }
const URL0 = arg('url', 'http://localhost:5173')
const VERBOSE = process.argv.includes('--verbose')
const STOPS = ['1', '2', '3', '4a', '4b', '4c', '4d', '4e', '4f', '4g', '5', '5b', '6', '6b', '7a', '7f', '7b', '7c', '7d', '7e']

// structural constants of the design and the UI, with why they are not data
const STRUCTURAL = new Map([
  [15, '15-minute decision slot (config.yaml v2 / model.DT)'], [24, '24-hour horizon / hours in a day'], [96, '96 slots per day'],
  [16, 'at most 16 qubits per block (config.yaml v2.master.max_block_qubits)'], [3, 'three-hour network failure in the benchmark protocol (run_bench_v3.comms_window); three cards'],
  [7, 'seven steps of the story'], [1, 'ordinal / one'], [2, 'ordinal / two'], [4, 'ordinal'], [5, 'ordinal'], [6, 'ordinal'], [0, 'zero / axis'],
  [10, '10-year NPV horizon (config impact.years)'], [60, 'fast-forward 60x'], [95, '95 % interval'], [100, 'per cent scale'],
  [256, 'QAOA shots (config.yaml v2.qaoa.shots)'],
])

const SCAN_JS = `(() => {
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && +s.opacity > 0.05 }
  const skip = e => e.closest('.summary-doc, .opreport-doc, .sr-only, [aria-hidden=true], script, style, .recharts-cartesian-axis, .stepnums, .progress, kbd, .clock, .op-clock, .sha, code, .bits, select, option, .tile, .qlabel, .blockhead, .colhead, .barlab, .barref, .bitch, .devlabel, .zlabel, .linelabel, .soclabel, .verifytag, .barbest, .evlist .tn, .minihist em')
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  const out = []
  let n
  while ((n = walker.nextNode())) {
    const t = n.textContent; if (!t || !/\\d/.test(t)) continue
    const el = n.parentElement; if (!el || skip(el) || !vis(el)) continue
    out.push({ t: t.trim().slice(0, 300), card: (el.closest('.key, .bcard, .ib-card .scale, .phase, .card.live, .sm') || {}).className || null, cardId: el.closest('.key, .bcard, .phase, .sm') ? [...document.querySelectorAll('.key, .bcard, .phase, .sm')].indexOf(el.closest('.key, .bcard, .phase, .sm')) : -1, table: !!el.closest('table, svg') })
  }
  return { texts: out, derived: (window.__qgDerived || []).map(d => d.v) }
})()`

// numbers in a text: strips times, dates, years, version-like ids
function tokens(t) {
  const s = t.replace(/\b\d{1,2}:\d{2}\b/g, ' ').replace(/\b(19|20)\d{2}-\d{2}-\d{2}\b/g, ' ').replace(/\b\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (19|20)\d{2}\b/g, ' ')
    .replace(/\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? (19|20)\d{2}\b/g, ' ').replace(/\b(19|20)\d{2}\b/g, ' ')
    .replace(/\b[qpP]\d+\b/g, ' ').replace(/[γβ][₁₂]/g, ' ').replace(/CO₂|10\^?|²/g, ' ').replace(/\bv\d+(\.\d+)*\b/g, ' ').replace(/\bstep \d+\b/gi, ' ').replace(/\b\d+(st|nd|rd|th)\b/g, ' ')
  const re = /[−-]?\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|[−-]?\d+(?:\.\d+)?/g
  const out = []
  let m
  while ((m = re.exec(s))) {
    const raw = m[0]; const v = parseFloat(raw.replace(/[,]/g, '').replace('−', '-'))
    const dec = (raw.split('.')[1] || '').length
    if (!Number.isNaN(v)) out.push({ raw, v, dec })
  }
  return out
}

function scalars(obj, acc, depth = 0) {
  if (obj === null || obj === undefined) return
  if (typeof obj === 'number') { acc.add(obj); return }
  if (Array.isArray(obj)) {
    acc.add(obj.length)
    if (obj.length > 40 && obj.every(x => typeof x === 'number' || x === null)) return    // time series: not candidates
    obj.forEach(x => scalars(x, acc, depth + 1)); return
  }
  if (typeof obj === 'object') { const ks = Object.keys(obj); acc.add(ks.length); ks.forEach(k => scalars(obj[k], acc, depth + 1)) }
}

function matches(tok, cands) {
  const tol = 0.5 * 10 ** -tok.dec + 1e-9
  const t = Math.abs(tok.v)
  for (const c0 of cands) {
    const c = Math.abs(c0)
    for (const f of [1, 100, 60, 1e-5, 1e-3, 1 / 4]) if (Math.abs(c * f - t) <= tol * (f === 1e-5 ? 1 : 1)) return true
  }
  return false
}

const { cdp, close } = await launch(arg('chrome'))
const failures = [], cardFails = []
try {
  await cdp.send('Network.enable', { maxResourceBufferSize: 50e6, maxTotalBufferSize: 400e6 })
  const bodies = new Map()
  cdp.on('Network.loadingFinished', async p => { const r = reqs.get(p.requestId); if (!r) return
    try { const b = await cdp.send('Network.getResponseBody', { requestId: p.requestId }); bodies.set(r, JSON.parse(b.body)) } catch { /* not JSON */ } })
  const reqs = new Map()
  cdp.on('Network.responseReceived', p => { if (/\/replay\/[^?]+\.json/.test(p.response.url)) reqs.set(p.requestId, p.response.url.split('/replay/')[1]) })
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false })
  const screens = []
  await cdp.send('Page.navigate', { url: `${URL0}/?stop=1&offline` })
  await waitFor(cdp, `!!document.querySelector('.panel .answer')`, 40000); await sleep(3000)
  for (let k = 0; k < STOPS.length; k++) {
    if (k) { await key(cdp, 'ArrowRight'); await sleep(STOPS[k] === '3' ? 4200 : 1800) }
    screens.push(['explain ' + STOPS[k], await evaluate(cdp, SCAN_JS)])
  }
  for (const [name, qs, sel] of [['operate (recorded)', '?mode=operate&offline', '.op-grid'], ['deploy', '?mode=deploy&offline', '.arch'], ['verify', '?mode=verify&offline', '.metrics']]) {
    await cdp.send('Page.navigate', { url: `${URL0}/${qs}` }); await waitFor(cdp, `!!document.querySelector('${sel}')`, 40000); await sleep(2500)
    screens.push([name, await evaluate(cdp, SCAN_JS)])
  }
  await sleep(500)
  const cands = new Set()
  for (const b of bodies.values()) scalars(b, cands)
  console.log(`replay files seen: ${bodies.size}; scalar candidates: ${cands.size}`)
  for (const [name, { texts, derived }] of screens) {
    const all = new Set([...cands, ...derived])
    const perCard = new Map()
    for (const x of texts) {
      for (const tok of tokens(x.t)) {
        const ok = matches(tok, all) || STRUCTURAL.has(Math.abs(tok.v))
        if (!ok) failures.push({ screen: name, token: tok.raw, text: x.t.slice(0, 90) })
        if (x.cardId >= 0 && !x.table) perCard.set(x.cardId, [...(perCard.get(x.cardId) || []), tok.raw])
      }
    }
    for (const [id, toks] of perCard) if (toks.length > 3) cardFails.push({ screen: name, card: id, numbers: toks.join(' | ') })
  }
} finally { await close() }
const uniq = [...new Map(failures.map(f => [f.screen + f.token + f.text, f])).values()]
console.log(`numbers not traced to loaded data: ${uniq.length}`)
for (const f of uniq.slice(0, VERBOSE ? 500 : 60)) console.log(`  ✗ [${f.screen}] ${f.token}  ← “${f.text}”`)
console.log(`cards with more than three numbers: ${cardFails.length}`)
for (const c of cardFails) console.log(`  ✗ [${c.screen}] card ${c.card}: ${c.numbers}`)
process.exit(uniq.length || cardFails.length ? 1 : 0)
