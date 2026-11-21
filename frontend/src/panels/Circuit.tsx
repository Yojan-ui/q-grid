import { useEffect, useMemo, useState } from 'react'
import type { QaoaFile } from '../lib/data'
import { bits, energies, isingNormalised, qaoaLayers, sample } from '../lib/qaoa'

/** Animated QAOA circuit (cost / mixer layers) + amplitude bars per layer, computed in the browser from the
 *  scenario's QUBO and the trained (gamma, beta). Badge compares the best sampled bitstring to the exact optimum. */
export function QaoaPanel({ q, onLayer, playing }: { q: QaoaFile; onLayer: (p: Float64Array) => void; playing: boolean }) {
  const layers = useMemo(() => {
    const E = energies({ M: q.qubo_matrix, c: q.qubo_const })
    return { E, P: qaoaLayers(isingNormalised({ M: q.qubo_matrix, c: q.qubo_const }, E), q.gammas, q.betas) }
  }, [q])
  const [k, setK] = useState(0)
  useEffect(() => { setK(0) }, [q])
  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => setK(x => Math.min(layers.P.length - 1, x + 1)), 1600)
    return () => clearInterval(id)
  }, [playing, layers])
  useEffect(() => { onLayer(layers.P[k]) }, [k, layers, onLayer])
  const n = q.n_qubits, P = layers.P[k]
  const opt = parseInt(q.optimum.bits.split('').reverse().join(''), 2)
  const top = useMemo(() => Array.from(P.keys()).sort((a, b) => P[b] - P[a]).slice(0, 18), [P])
  const pmax = P[top[0]] || 1
  const final = layers.P[layers.P.length - 1]
  const shots = useMemo(() => sample(final, 256, 1234), [final])
  const best = shots.reduce((b, z) => (q.feasible[z] && (b < 0 || q.energies[z] < q.energies[b]) ? z : b), -1)
  const gap = best < 0 ? null : (q.energies[best] - q.energies[opt]) / Math.max(Math.abs(q.energies[opt]), 1e-9)
  const W = 520, rowH = 15
  return (
    <div className="qpanel">
      <svg width={W} height={n * rowH + 30} role="img" aria-label="QAOA circuit">
        {Array.from({ length: n }, (_, i) => (
          <g key={i}>
            <line x1={30} x2={W - 10} y1={20 + i * rowH} y2={20 + i * rowH} stroke="#1F2733" />
            <text x={2} y={24 + i * rowH} fontSize={9} fill="#8A94A6">q{i}</text>
          </g>
        ))}
        <rect x={34} y={10} width={18} height={n * rowH} fill="#1F2733" rx={3} />
        <text x={36} y={n * rowH + 26} fontSize={9} fill="#8A94A6">H</text>
        {q.gammas.map((g, l) => (
          <g key={l} opacity={k > l ? 1 : 0.25}>
            <rect x={70 + l * 150} y={10} width={70} height={n * rowH} fill="#8B7CFF" fillOpacity={0.35} rx={4} />
            <text x={74 + l * 150} y={n * rowH + 26} fontSize={9} fill="#8B7CFF">cost γ={g.toFixed(2)}</text>
            <rect x={150 + l * 150} y={10} width={50} height={n * rowH} fill="#4FB3FF" fillOpacity={0.25} rx={4} />
            <text x={150 + l * 150} y={n * rowH + 26} fontSize={9} fill="#4FB3FF">mix β={q.betas[l].toFixed(2)}</text>
          </g>
        ))}
      </svg>
      <div className="bars" aria-label="amplitude bars">
        {top.map(z => (
          <div key={z} className="bar" title={`${bits(z, n)} p=${P[z].toFixed(4)}`}>
            <div className={`fill ${z === opt ? 'opt' : q.feasible[z] ? '' : 'inf'}`} style={{ height: `${100 * P[z] / pmax}%` }} />
          </div>
        ))}
      </div>
      <div className="row small">
        layer {k}/{layers.P.length - 1} · P(optimum) = {(P[opt] * 100).toFixed(3)}% (uniform {(100 / (1 << n)).toFixed(3)}%)
        <span className={`badge ${gap !== null && gap <= 1e-9 ? 'ok' : 'warn'}`}>
          {gap === null ? 'no feasible sample → fallback tier' : gap <= 1e-9 ? 'verified = exact optimum' : `gap ${(100 * gap).toFixed(2)}% → fallback tier`}
        </span>
      </div>
      <div className="small muted">Amplitudes computed in your browser from the same circuit; reference run: {q.simulator}.</div>
    </div>
  )
}
