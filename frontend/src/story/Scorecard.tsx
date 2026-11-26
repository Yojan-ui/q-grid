// Step 7: the scorecard (7a), across campuses (7b), comms failure (7c). Every number comes from the replay file
// bench_v3.json written by scripts/write_bench_v3.py from results/bench_v3/*.csv.
import { Fragment } from 'react'
import type { Bench, BenchMetric } from '../lib/data'
import { C } from '../lib/theme'

export const GROUP_ORDER = ['Today', 'Research methods', 'Smart control', 'Central control', 'Ours']

const fmt = (v: number | undefined, m: BenchMetric) =>
  v === undefined || v === null || Number.isNaN(v) ? '–' : v.toLocaleString('en-IN', { maximumFractionDigits: m.digits, minimumFractionDigits: m.digits })

/** Best value per metric among methods that work without a central controller (the reference excluded). */
function bestDecentralised(b: Bench, ds: string) {
  const out: Record<string, string> = {}
  for (const m of b.metrics) {
    let best: string | null = null, bv = 0
    for (const me of b.methods) {
      if (!me.without_coordinator) continue
      const v = b.table[ds]?.[me.key]?.[m.key]?.mean
      if (v === undefined || v === null || Number.isNaN(v)) continue
      if (best === null || (m.better === 'lower' ? v < bv : v > bv)) { best = me.key; bv = v }
    }
    if (best) out[m.key] = best
  }
  return out
}

export function Scorecard({ b, ds }: { b: Bench; ds: string }) {
  const groups = [...new Set(b.metrics.map(m => m.group))]
  const best = bestDecentralised(b, ds)
  const ref = b.table[ds]?.[b.reference.key]
  const dsl = b.datasets.find(d => d.key === ds)
  return (
    <div className="scorecard" role="table" aria-label="scorecard">
      <div className="sc-head"><b>{dsl?.label}</b><span className="muted"> · mean of {dsl?.n_days} days · ▲ best among methods without a central controller</span></div>
      <div className="sc-scroll">
        <table>
          <thead>
            <tr><th />{groups.map(g => <th key={g} colSpan={b.metrics.filter(m => m.group === g).length} className="grp">{g}</th>)}</tr>
            <tr><th className="mcol">Method</th>{b.metrics.map(m => <th key={m.key} title={`${m.label} (${m.better} is better)`}>{m.label}<span className="u">{m.unit}</span></th>)}</tr>
          </thead>
          <tbody>
            {GROUP_ORDER.map(g => {
              const rows = b.methods.filter(m => m.group === g)
              if (!rows.length) return null
              return (
                <Fragment key={g}>
                  <tr className="gr"><td colSpan={b.metrics.length + 1}>{g}</td></tr>
                  {rows.map(me => (
                    <tr key={me.key} className={me.key === 'qgrid' ? 'ours' : ''}>
                      <td className="mcol">{me.name}{!me.without_coordinator && <span className="needs" title="needs a central controller">central</span>}</td>
                      {b.metrics.map(m => {
                        const s = b.table[ds]?.[me.key]?.[m.key]
                        return <td key={m.key} className={`tn ${best[m.key] === me.key ? 'best' : ''}`}>{best[m.key] === me.key && <span className="tri">▲</span>}{fmt(s?.mean, m)}</td>
                      })}
                    </tr>
                  ))}
                </Fragment>
              )
            })}
            {ref && <tr className="ref"><td className="mcol">{b.reference.name}</td>{b.metrics.map(m => <td key={m.key} className="tn">{fmt(ref[m.key]?.mean, m)}</td>)}</tr>}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/** 7b: Q-Grid vs the best alternatives on each dataset (gap to the best possible plan, mean and 95 % CI). */
export function SmallMultiples({ b, metric = 'gap_pct' }: { b: Bench; metric?: string }) {
  const show = ['qgrid', 'per_building_mpc', 'central_mpc', 'rule_based']
  const names = Object.fromEntries(b.methods.map(m => [m.key, m.name]))
  return (
    <div className="smallmult">
      {b.datasets.map(d => {
        const vals = show.map(k => ({ k, s: b.table[d.key]?.[k]?.[metric] })).filter(x => x.s)
        const mx = Math.max(...vals.map(x => x.s!.ci_hi), 0.5)
        return (
          <div key={d.key} className="sm">
            <div className="sm-t">{d.label}<span className="muted"> · {d.n_days} days</span></div>
            {vals.map(({ k, s }) => (
              <div key={k} className={`sm-r ${k === 'qgrid' ? 'ours' : ''}`}>
                <span className="n">{names[k]}</span>
                <span className="track">
                  <i className="bar" style={{ width: `${(Math.max(s!.mean, 0) / mx) * 100}%` }} />
                  <i className="ci" style={{ left: `${(Math.max(s!.ci_lo, 0) / mx) * 100}%`, width: `${((s!.ci_hi - Math.max(s!.ci_lo, 0)) / mx) * 100}%` }} />
                </span>
                <span className="v tn">{s!.mean.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}

/** 7c: cumulative cost over the day, central MPC with a comms failure vs Q-Grid (same failure window). */
export function CommsChart({ b }: { b: Bench }) {
  const cd = b.comms_day
  if (!cd) return null
  const W = 520, H = 200, padL = 44, padB = 22
  const keys: [string, string, string][] = [['central_mpc_comms_fail', 'Central MPC, comms fail', C.grid], ['qgrid_comms_fail', 'Q-Grid, comms fail', C.quantum],
    ['central_mpc', 'Central MPC, comms up', '#B9B8B1'], ['qgrid', 'Q-Grid, comms up', '#C9BFFB']]
  const all = keys.flatMap(([k]) => cd.series[k] ?? [])
  const mx = Math.max(...all, 1), mn = Math.min(...all, 0)
  const x = (i: number) => padL + (i / 95) * (W - padL - 8)
  const y = (v: number) => 8 + (1 - (v - mn) / (mx - mn)) * (H - padB - 8)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="commschart" role="img" aria-label="cumulative cost through the day">
      <rect x={x(cd.window[0])} y={8} width={x(cd.window[1] + 1) - x(cd.window[0])} height={H - padB - 8} fill="#F6E3E3" />
      <text x={x(cd.window[0]) + 4} y={20} fontSize={10} fill={C.grid}>network down</text>
      {keys.map(([k, , col]) => cd.series[k] && (
        <polyline key={k} fill="none" stroke={col} strokeWidth={k.endsWith('fail') ? 2 : 1.4} strokeDasharray={k.endsWith('fail') ? undefined : '4 3'}
          points={cd.series[k].map((v, i) => `${x(i)},${y(v)}`).join(' ')} />))}
      {[0, 24, 48, 72, 95].map(i => <text key={i} x={x(i)} y={H - 6} fontSize={10} fill={C.muted} textAnchor="middle">{cd.t[i]}</text>)}
      <text x={4} y={14} fontSize={10} fill={C.muted}>Rs</text>
      <g transform={`translate(${padL + 6}, ${H - padB - 62})`}>
        {keys.map(([k, lab, col], j) => <g key={k} transform={`translate(0, ${j * 13})`}><rect width={10} height={3} y={-4} fill={col} /><text x={14} fontSize={10} fill={C.text}>{lab}</text></g>)}
      </g>
    </svg>
  )
}
