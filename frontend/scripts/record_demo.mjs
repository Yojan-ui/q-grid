// 90-second backup demo video: the story plus the three live moments, scripted click by click.
//   node scripts/record_demo.mjs --url http://localhost:5173 --out ../docs/media [--size 1280x720] [--theme light] [--gif-frames dir]
// Screencast frames from headless Chrome are encoded to WebM inside the page (MediaRecorder, no extra packages).
// With a backend on :8000 the live moments compute on the spot; otherwise they show the precomputed results.
import { mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { evaluate, key, launch, sleep, waitFor } from './cdp.mjs'

const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d }
const URL0 = arg('url', 'http://localhost:5173')
const OUT = resolve(arg('out', '../docs/media'))
const [W, H] = arg('size', '1280x720').split('x').map(Number)
const THEME = arg('theme', 'light')
const GIF = arg('gif-frames', '')

const click = (cdp, js) => evaluate(cdp, `(() => { const b = ${js}; if (b) { b.scrollIntoView({ block: 'center' }); b.click(); return true } return false })()`)
const byText = (sel, re) => `[...document.querySelectorAll('${sel}')].find(b => ${re}.test(b.textContent))`

// [stop, seconds on it, optional action after `at` seconds]
const PLAN = [
  ['1', 11], ['2', 4], ['3', 5], ['4a', 3], ['4b', 3], ['4c', 4], ['4d', 3], ['4e', 3],
  ['4f', 8, { at: 1.2, js: byText('.card.live button', '/Measure/') }],
  ['4g', 2], ['5', 10, { at: 2.5, js: byText('.card.live button', '/offline/') }],
  ['5b', 2], ['6', 4],
  ['6b', 10, { at: 1.0, js: byText('.card.live .chip', '/^no DG$/') }, { at: 5.5, js: byText('.card.live .chip', '/EV charging/') }],
  ['7a', 4], ['7b', 3], ['7c', 3], ['7d', 4], ['7e', 4],
]

async function main() {
  mkdirSync(OUT, { recursive: true })
  const { cdp, close } = await launch(arg('chrome'))
  try {
    await cdp.send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false })
    await cdp.send('Page.navigate', { url: `${URL0}/?stop=1&theme=${THEME}&present` })
    await waitFor(cdp, `!!document.querySelector('.panel .answer') && !!document.querySelector('.stage canvas')`, 40000)
    await sleep(2500)
    const live = await evaluate(cdp, `document.querySelector('.livebadge')?.textContent`)
    console.log('backend:', live)
    const frames = []
    cdp.on('Page.screencastFrame', p => { frames.push({ t: p.metadata.timestamp, data: p.data }); cdp.send('Page.screencastFrameAck', { sessionId: p.sessionId }) })
    await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 72, maxWidth: W, maxHeight: H, everyNthFrame: 2 })
    const marks = []
    const t0 = Date.now()
    for (let i = 0; i < PLAN.length; i++) {
      const [stop, secs, ...acts] = PLAN[i]
      if (i > 0) await key(cdp, 'ArrowRight')
      marks.push({ stop, t: (Date.now() - t0) / 1000 })
      const start = Date.now()
      for (const a of acts) {
        const wait = a.at * 1000 - (Date.now() - start)
        if (wait > 0) await sleep(wait)
        const ok = await click(cdp, a.js)
        if (!ok) console.log(`  (no element for action on step ${stop})`)
      }
      const rest = secs * 1000 - (Date.now() - start)
      if (rest > 0) await sleep(rest)
    }
    await cdp.send('Page.stopScreencast')
    const dur = (Date.now() - t0) / 1000
    console.log(`captured ${frames.length} frames over ${dur.toFixed(1)} s`)
    if (GIF) {   // every 4th frame for the README GIF (assembled by scripts/make_gif.py)
      mkdirSync(GIF, { recursive: true })
      frames.forEach((f, k) => { if (k % 4 === 0) writeFileSync(join(GIF, `f${String(k).padStart(5, '0')}.jpg`), Buffer.from(f.data, 'base64')) })
      writeFileSync(join(GIF, 'marks.json'), JSON.stringify({ marks, t0: frames[0]?.t }))
    }
    const tStart = frames[0].t
    const enc = `(async () => {
      const times = ${JSON.stringify(frames.map(f => f.t - tStart))};
      const c = document.createElement('canvas'); c.width = ${W}; c.height = ${H}; const g = c.getContext('2d');
      const rec = new MediaRecorder(c.captureStream(30), { mimeType: 'video/webm;codecs=vp9', videoBitsPerSecond: 4_000_000 });
      const chunks = []; rec.ondataavailable = e => chunks.push(e.data);
      const imgs = await Promise.all(window.__frames.map(src => new Promise(r => { const i = new Image(); i.onload = () => r(i); i.src = src })));
      rec.start(); const start = performance.now();
      for (let k = 0; k < imgs.length; k++) {
        const due = times[k] * 1000; const now = performance.now() - start; if (due > now) await new Promise(r => setTimeout(r, due - now));
        g.drawImage(imgs[k], 0, 0, ${W}, ${H});
      }
      await new Promise(r => setTimeout(r, 400)); rec.stop(); await new Promise(r => rec.onstop = r);
      const buf = new Uint8Array(await new Blob(chunks, { type: 'video/webm' }).arrayBuffer());
      let s = ''; for (let k = 0; k < buf.length; k += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(k, k + 0x8000));
      return btoa(s);
    })()`
    await cdp.send('Page.navigate', { url: 'about:blank' })
    await sleep(500)
    await cdp.send('Runtime.evaluate', { expression: 'window.__frames = []' })
    for (let i = 0; i < frames.length; i += 40) {
      const batch = frames.slice(i, i + 40).map(f => `data:image/jpeg;base64,${f.data}`)
      await cdp.send('Runtime.evaluate', { expression: `window.__frames.push(...${JSON.stringify(batch)})` })
    }
    const res = await cdp.send('Runtime.evaluate', { expression: enc, awaitPromise: true, returnByValue: true }, 900000)
    if (res.exceptionDetails) throw new Error(JSON.stringify(res.exceptionDetails).slice(0, 400))
    const file = join(OUT, 'backup_demo.webm')
    writeFileSync(file, Buffer.from(res.result.value, 'base64'))
    writeFileSync(join(OUT, 'backup_demo_chapters.json'), JSON.stringify({ duration_s: dur, backend: live, chapters: marks }, null, 1))
    console.log('wrote', file)
  } finally { await close() }
}

main().catch(e => { console.error(e); process.exit(1) })
