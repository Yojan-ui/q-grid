import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { Label } from './Label'
import type { QaoaFile } from '../lib/data'
import { C as COLORS } from '../lib/theme'

const gray = (i: number) => i ^ (i >> 1)

/** Energy terrain: every bitstring is a cell on a 2D Gray-code grid (rows = first half of the bits, columns =
 *  second half), so neighbouring cells differ by one bit flip. Height = QUBO energy (low = valley); infeasible
 *  states (penalised) rise as ridges; violet columns = QAOA probability of the current layer. */
export function QuboTerrain({ q, probs, showProbs, pref: pScale }: { q: QaoaFile; probs: Float64Array | null; showProbs: boolean; pref?: number }) {
  const n = q.n_qubits, nr = Math.floor(n / 2), nc = n - nr, R = 1 << nr, C = 1 << nc
  const cell = 120 / Math.max(R, C)
  const { idx, hs, emin } = useMemo(() => {
    const E = q.energies
    const fe = E.filter((_, z) => q.feasible[z])
    const lo = Math.min(...fe), hi = Math.max(...fe)
    const idx: number[] = [], hs: number[] = []
    for (let r = 0; r < R; r++) for (let c = 0; c < C; c++) {
      const z = gray(r) | (gray(c) << nr)
      idx.push(z)
      const h = q.feasible[z] ? 2 + 28 * (E[z] - lo) / Math.max(hi - lo, 1e-9) : 34
      hs.push(h)
    }
    return { idx, hs, emin: lo }
  }, [q])
  const ref = useRef<THREE.InstancedMesh>(null!)
  const iref = useRef<THREE.InstancedMesh>(null!)
  const pref = useRef<THREE.InstancedMesh>(null!)
  const m = useMemo(() => new THREE.Matrix4(), [])
  const col = useMemo(() => new THREE.Color(), [])
  const lowC = useMemo(() => new THREE.Color(COLORS.border), [])
  const optZ = parseInt(q.optimum.bits.split('').reverse().join(''), 2)
  const pmax = pScale ?? Math.max(...(q.probs as number[]))   // fixed scale (final layer) so columns grow layer by layer
  const top = useMemo(() => {
    if (!probs) return new Set<number>()
    let lo = Infinity, hi = 0
    for (const v of probs) { if (v < lo) lo = v; if (v > hi) hi = v }
    if (hi <= lo * 1.01) return new Set<number>()   // uniform superposition (layer 0): nothing to highlight yet
    return new Set(Array.from(probs.keys()).sort((a, b) => probs[b] - probs[a]).slice(0, 64))
  }, [probs])
  useFrame(() => {
    idx.forEach((z, k) => {
      const r = Math.floor(k / C), c = k % C
      const h = hs[k]
      const feas = !!q.feasible[z]
      m.makeScale(cell * 0.92, h, cell * 0.92).setPosition((c - C / 2) * cell, h / 2, (r - R / 2) * cell)
      // feasible cells: opaque terrain; infeasible (penalised) cells: translucent ridges so valleys stay visible
      ref.current.setMatrixAt(k, feas ? m : m.clone().makeScale(0, 0, 0))
      iref.current.setMatrixAt(k, feas ? m.clone().makeScale(0, 0, 0) : m.clone().makeScale(cell * 0.08, h, cell * 0.08).setPosition((c - C / 2) * cell, h / 2, (r - R / 2) * cell))
      const t = Math.min(1, (h - 2) / 28)
      ref.current.setColorAt(k, z === optZ ? col.set(COLORS.text) : col.set(COLORS.quantum).lerp(lowC, t))
      const p = showProbs && probs && top.has(z) ? probs[z] / pmax : 0
      const ph = Math.min(60, 45 * p)
      if (ph < 0.05) m.makeScale(0, 0, 0)
      else m.makeScale(cell * 0.5, ph, cell * 0.5).setPosition((c - C / 2) * cell, h + ph / 2, (r - R / 2) * cell)
      pref.current.setMatrixAt(k, m)
    })
    ref.current.instanceMatrix.needsUpdate = true
    iref.current.instanceMatrix.needsUpdate = true
    if (ref.current.instanceColor) ref.current.instanceColor.needsUpdate = true
    pref.current.instanceMatrix.needsUpdate = true
  })
  const k0 = idx.indexOf(optZ)
  const optPos: [number, number, number] = [((k0 % C) - C / 2) * cell, hs[k0] + 14, (Math.floor(k0 / C) - R / 2) * cell]
  void emin
  return (
    <group position={[0, 0, 0]}>
      <instancedMesh ref={ref} args={[undefined, undefined, idx.length]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial />
      </instancedMesh>
      <instancedMesh ref={iref} args={[undefined, undefined, idx.length]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial color={COLORS.grid} transparent opacity={0.22} depthWrite={false} />
      </instancedMesh>
      <instancedMesh ref={pref} args={[undefined, undefined, idx.length]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshBasicMaterial color={COLORS.quantum} toneMapped={false} />
      </instancedMesh>
      <Label position={optPos} size={4} color={COLORS.quantum} text={`exact optimum · energy ${q.energies[optZ].toFixed(0)}`} />
    </group>
  )
}

/** Decision variables of the zone as glowing qubit chips above it. */
export function QubitChips({ names, bitsOn, at }: { names: string[]; bitsOn: string; at: [number, number, number] }) {
  const label = (v: string) => v.startsWith('s:') ? v.slice(2).replace(/_/g, ' ') : v === 'g' ? 'diesel gen' : v === 'w' ? 'pump'
    : v[0] === 'c' ? `charge t+${v.slice(1)}` : v[0] === 'd' ? `discharge t+${v.slice(1)}` : v[0] === 'p' ? `line ${v.slice(1)} +` : v[0] === 'n' ? `line ${v.slice(1)} −` : v
  return (
    <group position={at}>
      {names.map((v, i) => {
        const a = (i / names.length) * Math.PI * 2, on = bitsOn[i] === '1'
        return (
          <group key={v} position={[Math.cos(a) * 45, 30 + (i % 2) * 8, Math.sin(a) * 45]}>
            <mesh>
              <sphereGeometry args={[3.2, 20, 20]} />
              <meshStandardMaterial color={COLORS.quantum} emissive={COLORS.quantum} emissiveIntensity={on ? 2.2 : 0.35} toneMapped={false} />
            </mesh>
            <Label position={[0, 7, 0]} size={3.2} color={on ? COLORS.text : COLORS.muted} text={`q${i} · ${label(v)} = ${on ? 1 : 0}`} />
          </group>
        )
      })}
    </group>
  )
}
