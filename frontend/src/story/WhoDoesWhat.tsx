// Step 4g: where quantum is used and where it is not. Structure only (from the README architecture), no numbers.
import { motion } from 'framer-motion'
import { reducedMotion, useC } from '../lib/theme'

const box = (k: number) => ({ initial: { opacity: 0, y: 10 }, animate: { opacity: 1, y: 0 },
  transition: { delay: reducedMotion() ? 0 : 0.15 + k * 0.06, duration: reducedMotion() ? 0 : 0.5, ease: [0.65, 0, 0.35, 1] as const } })

export function WhoDoesWhat() {
  const C = useC()
  return (
    <div className="wdw" role="img" aria-label="Who does what: quantum inside each building, classical around it">
      <motion.div className="wdw-card" {...box(0)}>
        <svg viewBox="0 0 640 380" width="100%">
          <defs>
            <marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M0,0 L10,5 L0,10 z" fill={C.muted} />
            </marker>
          </defs>
          {/* inside one building */}
          <rect x="16" y="16" width="608" height="232" rx="14" fill="none" stroke={C.hair} />
          <text x="32" y="40" className="wl">Inside each building, every 15 minutes</text>
          <g>
            <rect x="32" y="60" width="132" height="64" rx="10" fill={C.surface} stroke={C.hair} />
            <text x="98" y="88" textAnchor="middle" className="wt">Yes/no decisions</text>
            <text x="98" y="106" textAnchor="middle" className="ws">→ QUBO cost</text>
          </g>
          <g>
            <rect x="188" y="52" width="168" height="80" rx="10" fill={C.quantumSoft} stroke={C.quantum} strokeWidth="1.5" />
            <text x="272" y="78" textAnchor="middle" className="wt" fill={C.quantumInk}>QUANTUM</text>
            <text x="272" y="97" textAnchor="middle" className="ws">QAOA circuit, ≤16 qubits</text>
            <text x="272" y="114" textAnchor="middle" className="ws">measure 256× → best plan</text>
          </g>
          <g>
            <rect x="380" y="60" width="112" height="64" rx="10" fill={C.surface} stroke={C.hair} />
            <text x="436" y="88" textAnchor="middle" className="wt">Verify</text>
            <text x="436" y="106" textAnchor="middle" className="ws">vs exact search</text>
          </g>
          <g>
            <rect x="516" y="60" width="92" height="64" rx="10" fill={C.surface} stroke={C.hair} />
            <text x="562" y="88" textAnchor="middle" className="wt">Safety</text>
            <text x="562" y="106" textAnchor="middle" className="ws">clamp, then act</text>
          </g>
          <g>
            <rect x="380" y="160" width="228" height="64" rx="10" fill={C.surface} stroke={C.hair} strokeDasharray="4 3" />
            <text x="494" y="188" textAnchor="middle" className="wt">Fallback if it misses</text>
            <text x="494" y="206" textAnchor="middle" className="ws">QIEA → annealing → exact</text>
          </g>
          <line x1="164" y1="92" x2="186" y2="92" stroke={C.muted} markerEnd="url(#ar)" />
          <line x1="356" y1="92" x2="378" y2="92" stroke={C.muted} markerEnd="url(#ar)" />
          <line x1="492" y1="92" x2="514" y2="92" stroke={C.muted} markerEnd="url(#ar)" />
          <path d="M436 124 L436 158" stroke={C.muted} markerEnd="url(#ar)" fill="none" />
          <path d="M562 158 L562 126" stroke={C.muted} markerEnd="url(#ar)" fill="none" />
          <text x="444" y="146" className="ws">miss</text>
          {/* between buildings */}
          <rect x="16" y="266" width="608" height="98" rx="14" fill="none" stroke={C.hair} />
          <text x="32" y="290" className="wl">Between buildings</text>
          <g>
            <rect x="32" y="304" width="120" height="44" rx="10" fill={C.surface} stroke={C.hair} />
            <text x="92" y="331" textAnchor="middle" className="wt">Building A</text>
            <rect x="488" y="304" width="120" height="44" rx="10" fill={C.surface} stroke={C.hair} />
            <text x="548" y="331" textAnchor="middle" className="wt">Building B</text>
            <path d="M156 318 L484 318" stroke={C.accent} markerEnd="url(#ar)" markerStart="url(#ar)" />
            <text x="320" y="310" textAnchor="middle" className="ws">propose cable flow ↔ agree (ADMM, classical)</text>
            <text x="320" y="340" textAnchor="middle" className="ws">neighbours only · no central computer</text>
          </g>
          <path d="M98 248 L98 300" stroke={C.hair} strokeDasharray="3 3" />
        </svg>
      </motion.div>
      <motion.div className="wdw-legend" {...box(3)}>
        <span><i style={{ background: C.quantum }} />Quantum (simulated)</span><span><i style={{ background: C.surface, border: `1px solid ${C.muted}` }} />Classical</span>
        <span className="muted">QIEA is quantum-inspired and runs on a classical CPU.</span>
      </motion.div>
    </div>
  )
}
