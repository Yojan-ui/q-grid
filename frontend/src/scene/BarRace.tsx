import { useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { Label } from './Label'

const ORDER = ['B0', 'B1', 'B2-GA', 'B2-PSO', 'B3', 'C-QIEA', 'B5', 'OURS-QIEA', 'OURS', 'B4']
import { C } from '../lib/theme'
const COL: Record<string, string> = { OURS: C.quantum, 'OURS-QIEA': C.muted, B5: C.muted, B4: C.text, 'C-QIEA': C.muted }

/** 3D benchmark bar race (objective Rs incl. VOLL, lower is better) with the B4 optimum as a reference plane. */
export function BarRace({ rows, progress }: { rows: Record<string, any>[]; progress: number }) {
  const data = ORDER.map(m => rows.find(r => r.method === m)).filter(Boolean) as Record<string, any>[]
  const vmax = Math.max(...data.map(r => r.objective_rs))
  const b4 = data.find(r => r.method === 'B4')?.objective_rs ?? 0
  const refs = useRef<(THREE.Mesh | null)[]>([])
  useFrame(() => data.forEach((r, i) => {
    const m = refs.current[i]; if (!m) return
    const h = Math.max(0.5, 60 * (r.objective_rs / vmax) * progress)
    m.scale.y = h; m.position.y = h / 2
  }))
  return (
    <group position={[-(data.length * 9) / 2, 0, 0]}>
      {data.map((r, i) => (
        <group key={r.method} position={[i * 9, 0, 0]}>
          <mesh ref={el => { refs.current[i] = el }}>
            <boxGeometry args={[6, 1, 6]} />
            <meshStandardMaterial color={COL[r.method] ?? C.offline} emissive={COL[r.method] ?? C.offline} emissiveIntensity={0.15} />
          </mesh>
          <Label position={[0, -4, 4]} size={2.4} text={r.method} />
          <Label position={[0, 60 * (r.objective_rs / vmax) * progress + 4, 0]} size={2} text={`Rs ${Math.round(r.objective_rs).toLocaleString('en-IN')}`} />
        </group>
      ))}
      <mesh position={[(data.length * 9) / 2 - 4.5, 60 * (b4 / vmax), 0]}>
        <boxGeometry args={[data.length * 9, 0.3, 10]} />
        <meshBasicMaterial color={C.text} transparent opacity={0.18} />
      </mesh>
    </group>
  )
}
