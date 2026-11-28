// UI TEST FIXTURE SERVER: fake data, for checking layouts only. Never copy its output into results/ or public/replay/.
// Proxies a running vite dev server and adds the replay fields the pipeline will generate later, so the UI can be
// checked with them present (scenario asset_status / cables_status / data_provenance / problem_points, planner.json).
// Every added value is visibly labelled FIXTURE in the UI (generated_by, sources, problem text).
//   node scripts/fixture-server.mjs --upstream http://localhost:5281 --port 5282 [--no-planner] [--no-scenario]
import http from 'node:http'
import net from 'node:net'

const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d }
const UP = new URL(arg('upstream', 'http://localhost:5281'))
const PORT = Number(arg('port', '5282'))
const NO_PLANNER = process.argv.includes('--no-planner'), NO_SCEN = process.argv.includes('--no-scenario')

function planner() {
  const groups = [
    { key: 'academic', label: 'Academic roofs', existing_kwp: 400, max_extra_kwp: 600, step_kwp: 100 },
    { key: 'hostels', label: 'Hostel roofs', existing_kwp: 300, max_extra_kwp: 400, step_kwp: 100 },
  ]
  const cases = []
  // deterministic made-up formulas: only the shape matters
  for (let a = 0; a <= 600; a += 100) for (let h = 0; h <= 400; h += 100) for (let b = 0; b <= 2000; b += 500) for (const cd of [1000, 1300, 1600]) {
    const pv = a + h
    const capex = pv * 45000 + b * 20000
    const save = pv * 1300 + b * 900 + (1600 - cd) * 600
    cases.push({ extra_kwp: { academic: a, hostels: h }, battery_kwh: b, contract_kva: cd, capex_rs: capex, annual_saving_rs: save,
      payback_years: capex > 0 && save > 0 ? Math.round((capex / save) * 10) / 10 : null, npv10_rs: Math.round(save * 6.1 - capex),
      peak_kva: Math.round(1450 - b * 0.12 - pv * 0.05), diesel_litres_year: Math.round(9000 - b * 2.1), co2_t_year: Math.round((1800 - pv * 1.2 - b * 0.05)) / 1 })
  }
  const opt = cases.reduce((x, y) => (y.npv10_rs > x.npv10_rs ? y : x))
  return { status: 'FIXTURE', generated_by: 'UI TEST FIXTURE (fake numbers)', labels: { tariff: 'FIXTURE tariff label', costs: 'FIXTURE cost label' },
    roof_groups: groups, battery: { max_kwh: 2000, step_kwh: 500 }, contract_demand_options: [1000, 1300, 1600], cases,
    optimum: { ...opt, note: 'FIXTURE: highest NPV case in the fake grid.' },
    assumptions: [{ name: 'FIXTURE solar cost', value: 45000, unit: 'Rs/kWp', source: 'fixture' }, { name: 'FIXTURE battery cost', value: [18000, 22000], unit: 'Rs/kWh', source: 'fixture' }] }
}

function scenario(sc) {
  const st = ['EXISTING', 'PROPOSED', 'PENDING']
  sc.campus.zones.forEach((z, i) => { z.asset_status = { pv: 'EXISTING', battery: z.battery_kwh > 0 ? st[i % 2] : 'PROPOSED', dg: 'EXISTING', ev: i % 3 === 0 ? 'PROPOSED' : 'EXISTING' } })
  sc.campus.cables_status = 'PROPOSED'
  sc.data_provenance = [
    { item: 'FIXTURE rooftop solar', value_label: 'fixture value', source: 'fixture source', page: 'p. fixture', status: 'REAL' },
    { item: 'FIXTURE tariff', value_label: 'fixture value', source: 'fixture source', page: null, status: 'PENDING' },
  ]
  sc.problem_points = [
    { key: 'outages', title: 'FIXTURE: outages', text: 'Fixture text for the outages card, about two lines long so the layout can be judged.' },
    { key: 'diesel', title: 'FIXTURE: diesel', text: 'Fixture text for the diesel card, about two lines long so the layout can be judged.' },
    { key: 'demand_charges', title: 'FIXTURE: demand charges', text: 'Fixture text for the demand-charge card, about two lines long.' },
    { key: 'roofs', title: 'FIXTURE: under-used roofs', text: 'Fixture text for the rooftop card, about two lines long so the layout can be judged.' },
  ]
  return sc
}

const send = (res, obj) => { const b = Buffer.from(JSON.stringify(obj)); res.writeHead(200, { 'content-type': 'application/json', 'content-length': b.length }); res.end(b) }

http.createServer((req, res) => {
  const path = req.url.split('?')[0]
  if (/\/replay\/planner\.json$/.test(path) && !NO_PLANNER) return send(res, planner())
  const opts = { hostname: UP.hostname, port: UP.port, path: req.url, method: req.method, headers: { ...req.headers, host: UP.host, 'accept-encoding': 'identity' } }
  const up = http.request(opts, r => {
    if (/\/replay\/scenario_[a-z_]+\.json$/.test(path) && !NO_SCEN && r.statusCode === 200 && (r.headers['content-type'] ?? '').includes('json')) {
      const chunks = []; r.on('data', c => chunks.push(c)); r.on('end', () => send(res, scenario(JSON.parse(Buffer.concat(chunks).toString()))))
      return
    }
    res.writeHead(r.statusCode, r.headers); r.pipe(res)
  })
  up.on('error', e => { res.writeHead(502); res.end(String(e)) })
  req.pipe(up)
}).on('upgrade', (req, sock, head) => {   // vite HMR websocket
  const u = net.connect(Number(UP.port), UP.hostname, () => {
    u.write(`${req.method} ${req.url} HTTP/1.1\r\n${Object.entries(req.headers).map(([k, v]) => `${k}: ${k === 'host' ? UP.host : v}`).join('\r\n')}\r\n\r\n`); u.write(head); u.pipe(sock); sock.pipe(u)
  })
  u.on('error', () => sock.destroy()); sock.on('error', () => u.destroy())
}).listen(PORT, () => console.log(`UI TEST FIXTURE server (fake data) on http://localhost:${PORT} -> ${UP.href}`))
