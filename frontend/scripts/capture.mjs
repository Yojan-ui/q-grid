// Screenshots of every story stop (and an optional screen recording) via headless Chrome + the DevTools protocol.
// No extra packages: Node >= 22 (global WebSocket/fetch) and an installed Chrome.
//   node scripts/capture.mjs --url http://localhost:5173 --out ../docs/media/shots [--sizes 1440x900,1920x1080] [--only 1,4c]
//   node scripts/capture.mjs --url http://localhost:5173 --out ../docs/media --video 1-4g --seconds 60
//   --theme light|dark (default: light)   --present (presenter mode: projector sizing, dev controls hidden)
// Also reports console errors and overlapping on-screen labels for each stop.
import { spawn } from 'node:child_process'
import { mkdirSync, writeFileSync, existsSync, rmSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { tmpdir } from 'node:os'

const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d }
const URL0 = arg('url', 'http://localhost:5173')
const QS = (arg('scenario', '') ? `&scenario=${arg('scenario', '')}` : '') + `&theme=${arg('theme', 'light')}` + (process.argv.includes('--present') ? '&present' : '')
const TAG = `${arg('theme', 'light')}${process.argv.includes('--present') ? '-present' : ''}`
const OUT = resolve(arg('out', 'shots'))
const SIZES = arg('sizes', '1440x900,1920x1080').split(',').map(s => s.split('x').map(Number))
const ONLY = arg('only', '')
const VIDEO = arg('video', '')
const SECONDS = Number(arg('seconds', '60'))
const CHROME = arg('chrome', [
  'C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome',
].find(p => existsSync(p)))
const STOPS = ['1', '2', '3', '4a', '4b', '4c', '4d', '4e', '4f', '4g', '5', '5b', '6', '7a', '7b', '7c', '7d']
// how long to let each stop's motion play before the screenshot (ms)
const WAIT = { '1': 9000, '3': 4200, '4c': 4200, '4d': 2600, '4e': 2200, '5': 9000, '6': 12000, '7a': 6000, '7b': 3000 }
const sleep = ms => new Promise(r => setTimeout(r, ms))

const OVERLAP_JS = `(() => {
  const sel = ['.zlabel', '.linelabel', '.devlabel', '.tile', '.qlabel', '.rulechip', '.barlab', '.colhead', '.verifytag', '.duotag', '.blockhead', '.clock', '.stage-foot'];
  const vis = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && +s.opacity > 0.05 && r.right > 0 && r.left < innerWidth };
  const els = sel.flatMap(s => [...document.querySelectorAll(s)].filter(vis).map(e => ({ s, r: e.getBoundingClientRect(), t: (e.textContent || '').trim().slice(0, 28) })));
  const out = [];
  for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
    const a = els[i].r, b = els[j].r;
    const ov = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
    if (ov > 0.15 * Math.min(a.width * a.height, b.width * b.height)) out.push(els[i].s + ' "' + els[i].t + '" x ' + els[j].s + ' "' + els[j].t + '"');
  }
  const panel = document.querySelector('.panel-scroll');
  // anything in the top bar or pager clipped / overlapping (projector check)
  const bar = [...document.querySelectorAll('.top > *, .top .right > *, .pager-row > *')].filter(vis).map(e => ({ s: e.className || e.tagName, r: e.getBoundingClientRect() }));
  const clipped = bar.filter(b => b.r.right > innerWidth + 1 || b.r.left < -1).map(b => 'clipped: ' + b.s);
  for (let i = 0; i < bar.length; i++) for (let j = i + 1; j < bar.length; j++) { const a = bar[i].r, b = bar[j].r; if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1 && !(a.left <= b.left && a.right >= b.right && a.top <= b.top && a.bottom >= b.bottom) && !(b.left <= a.left && b.right >= a.right && b.top <= a.top && b.bottom >= a.bottom)) clipped.push('overlap: ' + bar[i].s + ' x ' + bar[j].s) }
  const stage = document.querySelector('.stage')?.getBoundingClientRect();
  const offStage = stage ? els.filter(e => e.r.left < stage.left - 2 || e.r.right > stage.right + 2 || e.r.top < stage.top - 2).map(e => e.s + ' "' + e.t + '"') : [];
  return { overlaps: out, panelScrolls: panel ? panel.scrollHeight > panel.clientHeight + 4 : false, offStage, chrome: clipped };
})()`

async function main() {
  if (!CHROME) throw new Error('Chrome not found; pass --chrome <path>')
  const port = 9300 + Math.floor(Math.random() * 500)
  const prof = join(tmpdir(), `qgrid-cap-${port}`)
  const chrome = spawn(CHROME, [`--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, '--headless=new', '--hide-scrollbars',
    '--no-first-run', '--no-default-browser-check', '--force-device-scale-factor=1', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', 'about:blank'], { stdio: 'ignore' })
  try {
    let ver
    for (let i = 0; i < 60 && !ver; i++) { try { ver = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json() } catch { await sleep(250) } }
    const tgt = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json()
    const cdp = await connect(tgt.webSocketDebuggerUrl)
    await cdp.send('Page.enable'); await cdp.send('Runtime.enable')
    mkdirSync(OUT, { recursive: true })
    const report = {}
    if (VIDEO) await record(cdp)
    else for (const [w, h] of SIZES) {
      await cdp.send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: false })
      const errs = []
      cdp.on('Runtime.exceptionThrown', p => errs.push(p.exceptionDetails?.exception?.description ?? p.exceptionDetails?.text))
      cdp.on('Runtime.consoleAPICalled', p => { if (p.type === 'error') errs.push(p.args.map(a => a.value ?? a.description).join(' ').slice(0, 200)) })
      await cdp.send('Page.navigate', { url: `${URL0}/?stop=1${QS}` })
      await waitFor(cdp, `!!document.querySelector('.panel .answer')`, 30000)
      const list = ONLY ? STOPS.filter(s => ONLY.split(',').includes(s)) : STOPS
      let cur = 0
      for (const s of list) {
        const target = STOPS.indexOf(s)
        while (cur < target) { await key(cdp, 'ArrowRight'); cur++; await sleep(cur === target ? 0 : 350) }
        await sleep(WAIT[s] ?? 2200)
        const shot = await cdp.send('Page.captureScreenshot', { format: 'png' })
        const f = join(OUT, `${TAG}_${w}x${h}_step${s}.png`)
        writeFileSync(f, Buffer.from(shot.data, 'base64'))
        const chk = (await cdp.send('Runtime.evaluate', { expression: OVERLAP_JS, returnByValue: true })).result.value
        report[`${w}x${h} ${s}`] = chk
        if (s === '4e') {   // second frame after the tiles drop back into the building
          await sleep(3200)
          writeFileSync(join(OUT, `${TAG}_${w}x${h}_step4e-after.png`), Buffer.from((await cdp.send('Page.captureScreenshot', { format: 'png' })).data, 'base64'))
        }
        if (s === '2') {    // click a building via the chip list to show its devices
          await cdp.send('Runtime.evaluate', { expression: `[...document.querySelectorAll('.chip')].find(b => b.textContent === 'Hostels')?.click()` })
          await sleep(2400)
          writeFileSync(join(OUT, `${TAG}_${w}x${h}_step2-zone.png`), Buffer.from((await cdp.send('Page.captureScreenshot', { format: 'png' })).data, 'base64'))
          report[`${w}x${h} 2-zone`] = (await cdp.send('Runtime.evaluate', { expression: OVERLAP_JS, returnByValue: true })).result.value
        }
        if (s === '5') {
          await cdp.send('Runtime.evaluate', { expression: `[...document.querySelectorAll('.card .btn')].find(b => /offline/.test(b.textContent))?.click()` })
          await sleep(2200)
          writeFileSync(join(OUT, `${TAG}_${w}x${h}_step5-removed.png`), Buffer.from((await cdp.send('Page.captureScreenshot', { format: 'png' })).data, 'base64'))
        }
      }
      report[`${w}x${h} console errors`] = [...new Set(errs)]
      const fps = (await cdp.send('Runtime.evaluate', { expression: `new Promise(r => { let n = 0; const t0 = performance.now(); const f = () => { n++; performance.now() - t0 < 2000 ? requestAnimationFrame(f) : r(n / 2) }; requestAnimationFrame(f) })`, awaitPromise: true, returnByValue: true })).result.value
      report[`${w}x${h} fps (headless, last stop)`] = fps
    }
    writeFileSync(join(OUT, VIDEO ? 'record_report.json' : `shots_report_${TAG}.json`), JSON.stringify(report, null, 1))
    for (const [k, v] of Object.entries(report)) {
      if (Array.isArray(v)) { if (v.length) console.log(k, v.slice(0, 5)) ; continue }
      if (typeof v !== 'object') { console.log(k, v); continue }
      if (v.overlaps?.length || v.panelScrolls || v.offStage?.length || v.chrome?.length) console.log(k, JSON.stringify({ overlaps: v.overlaps.slice(0, 6), panelScrolls: v.panelScrolls, offStage: v.offStage.slice(0, 4), chrome: v.chrome }))
    }
    cdp.close()
  } finally {
    chrome.kill()
    await sleep(500)
    try { rmSync(prof, { recursive: true, force: true }) } catch { /* profile still locked */ }
  }
}

/** Screencast frames while the story advances on a schedule, then encode them to WebM inside Chrome (MediaRecorder). */
async function record(cdp) {
  const [w, h] = SIZES[0]
  await cdp.send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: false })
  const [a, b] = VIDEO.split('-')
  const list = STOPS.slice(STOPS.indexOf(a), STOPS.indexOf(b) + 1)
  await cdp.send('Page.navigate', { url: `${URL0}/?stop=${a}${QS}` })
  await waitFor(cdp, `!!document.querySelector('.panel .answer')`, 30000)
  await sleep(1500)
  const frames = []
  cdp.on('Page.screencastFrame', p => { frames.push({ t: p.metadata.timestamp, data: p.data }); cdp.send('Page.screencastFrameAck', { sessionId: p.sessionId }) })
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 82, maxWidth: w, maxHeight: h, everyNthFrame: 1 })
  // time budget per stop, weighted: the day-long and circuit stops get more
  const weight = { '1': 2.2, '2': 1.2, '3': 1.5, '4c': 1.5, '4d': 1.2, '4e': 1.6 }
  const tot = list.reduce((s, x) => s + (weight[x] ?? 1), 0)
  for (let i = 0; i < list.length; i++) {
    if (i > 0) await key(cdp, 'ArrowRight')
    if (list[i] === '2') { await sleep(1800); await cdp.send('Runtime.evaluate', { expression: `[...document.querySelectorAll('.chip')].find(b => b.textContent === 'Hostels')?.click()` }) }
    await sleep((SECONDS * 1000 * (weight[list[i]] ?? 1)) / tot - (list[i] === '2' ? 1800 : 0))
  }
  await cdp.send('Page.stopScreencast')
  console.log(`captured ${frames.length} frames`)
  const dir = join(OUT, 'frames')
  mkdirSync(dir, { recursive: true })
  frames.forEach((f, i) => writeFileSync(join(dir, `f${String(i).padStart(5, '0')}.jpg`), Buffer.from(f.data, 'base64')))
  writeFileSync(join(OUT, 'frames.json'), JSON.stringify(frames.map(f => f.t)))
  // encode in the page: draw each frame on a canvas at its real timestamp, MediaRecorder -> WebM
  const t0 = frames[0].t
  const enc = `(async () => {
    const times = ${JSON.stringify(frames.map(f => f.t - t0))};
    const c = document.createElement('canvas'); c.width = ${w}; c.height = ${h}; const g = c.getContext('2d');
    const rec = new MediaRecorder(c.captureStream(30), { mimeType: 'video/webm;codecs=vp9', videoBitsPerSecond: 6_000_000 });
    const chunks = []; rec.ondataavailable = e => chunks.push(e.data);
    const imgs = await Promise.all(window.__frames.map(src => new Promise(r => { const i = new Image(); i.onload = () => r(i); i.src = src })));
    rec.start(); const start = performance.now();
    for (let k = 0; k < imgs.length; k++) {
      const due = times[k] * 1000; const now = performance.now() - start; if (due > now) await new Promise(r => setTimeout(r, due - now));
      g.drawImage(imgs[k], 0, 0, ${w}, ${h});
    }
    await new Promise(r => setTimeout(r, 300)); rec.stop(); await new Promise(r => rec.onstop = r);
    const buf = new Uint8Array(await new Blob(chunks, { type: 'video/webm' }).arrayBuffer());
    let s = ''; for (let k = 0; k < buf.length; k += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(k, k + 0x8000));
    return btoa(s);
  })()`
  await cdp.send('Page.navigate', { url: 'about:blank' })
  await sleep(500)
  // ship frames to the page in batches
  await cdp.send('Runtime.evaluate', { expression: 'window.__frames = []' })
  for (let i = 0; i < frames.length; i += 40) {
    const batch = frames.slice(i, i + 40).map(f => `data:image/jpeg;base64,${f.data}`)
    await cdp.send('Runtime.evaluate', { expression: `window.__frames.push(...${JSON.stringify(batch)})` })
  }
  const res = await cdp.send('Runtime.evaluate', { expression: enc, awaitPromise: true, returnByValue: true }, 600000)
  if (res.exceptionDetails) throw new Error(JSON.stringify(res.exceptionDetails).slice(0, 400))
  const file = join(OUT, `qgrid-steps-${a}-${b}.webm`)
  writeFileSync(file, Buffer.from(res.result.value, 'base64'))
  rmSync(dir, { recursive: true, force: true })
  console.log('wrote', file)
}

async function key(cdp, k) {
  const code = { ArrowRight: 39, ArrowLeft: 37 }[k]
  await cdp.send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: k, code: k, windowsVirtualKeyCode: code })
  await cdp.send('Input.dispatchKeyEvent', { type: 'keyUp', key: k, code: k, windowsVirtualKeyCode: code })
}
async function waitFor(cdp, expr, ms) {
  const t = Date.now()
  while (Date.now() - t < ms) {
    const r = await cdp.send('Runtime.evaluate', { expression: expr, returnByValue: true })
    if (r.result?.value) return
    await sleep(300)
  }
  throw new Error(`timeout waiting for ${expr}`)
}
function connect(url) {
  return new Promise((res, rej) => {
    const ws = new WebSocket(url)
    let id = 0
    const pending = new Map(), handlers = {}
    ws.onmessage = ev => {
      const m = JSON.parse(ev.data)
      if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(m.error.message)) : p.res(m.result) }
      else if (m.method) (handlers[m.method] ?? []).forEach(f => f(m.params))
    }
    ws.onerror = rej
    ws.onopen = () => res({
      send: (method, params = {}, timeout = 60000) => new Promise((r2, j2) => {
        const i = ++id; pending.set(i, { res: r2, rej: j2 }); ws.send(JSON.stringify({ id: i, method, params }))
        setTimeout(() => { if (pending.has(i)) { pending.delete(i); j2(new Error(`${method} timed out`)) } }, timeout)
      }),
      on: (m, f) => { (handlers[m] ??= []).push(f) },
      close: () => ws.close(),
    })
  })
}

main().catch(e => { console.error(e); process.exit(1) })
