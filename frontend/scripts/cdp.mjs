// Minimal headless-Chrome driver over the DevTools protocol (no extra packages: Node >= 22, an installed Chrome).
import { spawn } from 'node:child_process'
import { existsSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'

export const sleep = ms => new Promise(r => setTimeout(r, ms))
export const findChrome = p => p ?? [
  'C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/usr/bin/google-chrome', '/usr/bin/chromium',
].find(x => existsSync(x))

/** Launch headless Chrome and open one page target; returns { cdp, close }. */
export async function launch(chromePath) {
  const CHROME = findChrome(chromePath)
  if (!CHROME) throw new Error('Chrome not found; pass --chrome <path>')
  const port = 9300 + Math.floor(Math.random() * 500)
  const prof = join(tmpdir(), `qgrid-cdp-${port}`)
  const chrome = spawn(CHROME, [`--remote-debugging-port=${port}`, `--user-data-dir=${prof}`, '--headless=new', '--hide-scrollbars',
    '--no-first-run', '--no-default-browser-check', '--force-device-scale-factor=1', '--ignore-gpu-blocklist', '--enable-gpu-rasterization', 'about:blank'], { stdio: 'ignore' })
  let ver
  for (let i = 0; i < 60 && !ver; i++) { try { ver = await (await fetch(`http://127.0.0.1:${port}/json/version`)).json() } catch { await sleep(250) } }
  const tgt = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json()
  const cdp = await connect(tgt.webSocketDebuggerUrl)
  await cdp.send('Page.enable'); await cdp.send('Runtime.enable')
  return {
    cdp,
    close: async () => {
      try { cdp.close() } catch { /* already closed */ }
      chrome.kill()
      await sleep(500)
      try { rmSync(prof, { recursive: true, force: true }) } catch { /* profile still locked */ }
    },
  }
}

export async function key(cdp, k) {
  const code = { ArrowRight: 39, ArrowLeft: 37, p: 80, d: 68, Tab: 9 }[k] ?? 0
  await cdp.send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: k, code: k.length === 1 ? `Key${k.toUpperCase()}` : k, windowsVirtualKeyCode: code })
  if (k.length === 1) await cdp.send('Input.dispatchKeyEvent', { type: 'char', text: k, key: k })
  await cdp.send('Input.dispatchKeyEvent', { type: 'keyUp', key: k, code: k.length === 1 ? `Key${k.toUpperCase()}` : k, windowsVirtualKeyCode: code })
}

export async function evaluate(cdp, expression, awaitPromise = false) {
  const r = await cdp.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? r.exceptionDetails.text)
  return r.result?.value
}

export async function waitFor(cdp, expr, ms) {
  const t = Date.now()
  while (Date.now() - t < ms) {
    const r = await cdp.send('Runtime.evaluate', { expression: expr, returnByValue: true })
    if (r.result?.value) return
    await sleep(300)
  }
  throw new Error(`timeout waiting for ${expr}`)
}

export function connect(url) {
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
