// The worked example in 3D: one building's yes/no decisions lift out as tiles, flip into qubits, get wired into
// the QAOA circuit, are measured into a histogram, and the winning plan decodes back into the devices.
// Everything is from one live_solve record of the replay (QUBO matrix, QAOA top states, exact optimum).
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import { RoundedBox } from '@react-three/drei'
import { Label3D } from './Label3D'
import gsap from 'gsap'
import type { LiveSolve, Scenario } from '../lib/data'
import { C, reducedMotion } from '../lib/theme'
import { pairRule, varLabel, zn } from '../lib/labels'
import type { StopId } from '../lib/story'

type V3 = [number, number, number]
const TW = 10, TH = 5.2, GAP = 1.0, BLOCK = 3

/** Tile layout grouped by device: battery (charge row over discharge row), one column per cable, then others. */
export function tileLayout(names: string[]) {
  const blocks: { title: string; cols: string[][] }[] = []
  const c = names.filter(v => /^c\d$/.test(v)), d = names.filter(v => /^d\d$/.test(v))
  if (c.length) blocks.push({ title: 'battery', cols: c.map((v, k) => [v, d[k]].filter(Boolean) as string[]) })
  const lines = [...new Set(names.filter(v => /^[pn]\d+$/.test(v)).map(v => v.slice(1)))]
  for (const l of lines) blocks.push({ title: `cable ${l}`, cols: [[`p${l}`, `n${l}`].filter(v => names.includes(v))] })
  const rest = names.filter(v => !/^[cdpn]\d+$/.test(v))
  if (rest.length) blocks.push({ title: 'other', cols: rest.map(v => [v]) })
  const ncol = blocks.reduce((a, b) => a + b.cols.length, 0)
  const width = ncol * TW + (ncol - blocks.length) * GAP + (blocks.length - 1) * BLOCK
  const pos: Record<string, V3> = {}
  const heads: { title: string; x: number }[] = []
  let x = -width / 2
  for (const b of blocks) {
    const x0 = x
    b.cols.forEach(col => {
      col.forEach((v, r) => { pos[v] = [x + TW / 2, 57 - r * (TH + GAP), 0] })
      x += TW + GAP
    })
    x += BLOCK - GAP
    heads.push({ title: b.title, x: (x0 + x - BLOCK) / 2 })
  }
  return { pos, heads }
}

const ringPos = (i: number, n: number): V3 => {
  const a = Math.PI / 2 - (2 * Math.PI * i) / n
  return [Math.cos(a) * 20, 50 + Math.sin(a) * 15, 0]
}
const WIRE_X0 = -17, WIRE_X1 = 36
const wirePos = (i: number, n: number): V3 => [WIRE_X0, 50 + ((n - 1) / 2) * 2.5 - i * 2.5, 0]
const COLS = [{ x: -12, label: 'H' }, { x: -3.5, label: 'Cost γ₁', wide: true }, { x: 5, label: 'Mixer β₁' },
  { x: 13.5, label: 'Cost γ₂', wide: true }, { x: 22, label: 'Mixer β₂' }, { x: 30, label: 'Measure' }]

type Mode = 'hidden' | 'tiles' | 'ring' | 'wires' | 'decoded'
const modeOf = (s: StopId): Mode =>
  s === '3' ? 'tiles' : s === '4a' || s === '4b' ? 'ring' : s === '4c' || s === '4d' ? 'wires' : s === '4e' ? 'decoded' : 'hidden'

export function Lab({ stop, ex, sc, anchor, yaw, buildingH, pulseKey }: {
  stop: StopId; ex: LiveSolve; sc: Scenario; anchor: THREE.Vector3; yaw: number; buildingH: number; pulseKey: number
}) {
  const n = ex.n_qubits
  const names = ex.var_names
  const { pos: tpos, heads } = useMemo(() => tileLayout(names), [names])
  const labels = useMemo(() => names.map(v => varLabel(v, ex.zone, ex.slot, sc)), [names, ex, sc])
  const best = ex.qaoa.best_bits ?? ex.exact.bits
  const mode = modeOf(stop)
  const reduced = reducedMotion()
  const top = useMemo(() => ex.qaoa.top.slice(0, 10), [ex])

  const grp = useRef<(THREE.Group | null)[]>([])
  const tile = useRef<(THREE.Group | null)[]>([])
  const ball = useRef<(THREE.Mesh | null)[]>([])
  const bit = useRef<(THREE.Group | null)[]>([])
  const fade = useRef({ edges: 0, circuit: 0, hist: 0, bits: 0 })
  const [phase, setPhase] = useState<'a' | 'b'>('a')   // 4e: a = bits flying / actions shown, b = dropped into the building
  const home: V3 = [0, buildingH, 0]

  useEffect(() => {
    setPhase('a')
    const D = reduced ? 0 : 0.8, S = reduced ? 0 : 0.05
    names.forEach((_, i) => {
      const g = grp.current[i], tl = tile.current[i], b = ball.current[i], bt = bit.current[i]
      if (!g || !tl || !b || !bt) return
      ;[g.position, g.scale, tl.rotation, tl.scale, b.scale, bt.position, bt.scale].forEach(o => gsap.killTweensOf(o))
      const v = names[i]
      // 4d: the qubits step back with the circuit so the measured histogram has the stage
      const wp = wirePos(i, n)
      const target: V3 = mode === 'tiles' || mode === 'decoded' ? tpos[v] : mode === 'ring' ? ringPos(i, n)
        : mode === 'wires' ? (stop === '4d' ? [COLS[COLS.length - 1].x - 4, wp[1] + 6, -22] : wp) : home
      const vis = mode === 'hidden' ? 0.02 : stop === '4d' ? 0.001 : 1
      gsap.to(g.position, { x: target[0], y: target[1], z: target[2], duration: D, ease: 'power3.inOut', delay: S * i })
      gsap.to(g.scale, { x: vis, y: vis, z: vis, duration: D, ease: 'power3.inOut', delay: S * i })
      const asTile = mode === 'tiles' || mode === 'decoded' || mode === 'hidden'
      gsap.to(tl.rotation, { y: asTile ? 0 : Math.PI, duration: D * 0.8, ease: 'power2.inOut', delay: S * i })
      gsap.to(tl.scale, { x: asTile ? 1 : 0.001, y: asTile ? 1 : 0.001, z: asTile ? 1 : 0.001, duration: D * 0.8, ease: 'power2.inOut', delay: S * i })
      gsap.to(b.scale, { x: asTile ? 0.001 : 1, y: asTile ? 0.001 : 1, z: asTile ? 0.001 : 1, duration: D * 0.8, ease: 'power2.inOut', delay: S * i + D * 0.2 })
      // 4e: each bit of the winning plan flies from its histogram bar to its device tile
      if (mode === 'decoded') {
        const hb = histX(Math.max(0, top.findIndex(s => s.bits === best)))
        bt.position.set(hb - ((n - 1) / 2) * 1.6 + i * 1.6, 48, 2)
        bt.scale.setScalar(1)
        gsap.to(bt.position, { x: tpos[v][0] + TW / 2 - 1.6, y: tpos[v][1] + TH / 2 - 0.2, z: 1, duration: reduced ? 0 : 1.0, ease: 'power3.inOut', delay: (reduced ? 0 : 0.25) + S * i })
      } else bt.scale.setScalar(0.001)
    })
    const f = fade.current
    gsap.killTweensOf(f)
    gsap.to(f, { edges: stop === '4b' ? 1 : 0, circuit: stop === '4c' ? 1 : stop === '4d' ? 0.18 : 0, hist: stop === '4d' ? 1 : stop === '4e' ? 0.0 : 0,
      bits: mode === 'decoded' ? 1 : 0, duration: reduced ? 0 : 0.6, ease: 'power2.inOut' })
    if (mode === 'decoded') {
      const id = setTimeout(() => {
        setPhase('b')
        names.forEach((_, i) => {
          const g = grp.current[i], bt = bit.current[i]
          if (!g || !bt) return
          gsap.to(g.position, { x: home[0], y: home[1], z: home[2], duration: reduced ? 0 : 0.9, ease: 'power3.in', delay: (reduced ? 0 : 0.04) * i })
          gsap.to(g.scale, { x: 0.02, y: 0.02, z: 0.02, duration: reduced ? 0 : 0.9, ease: 'power3.in', delay: (reduced ? 0 : 0.04) * i })
          gsap.to(bt.scale, { x: 0.001, y: 0.001, z: 0.001, duration: reduced ? 0 : 0.5, delay: (reduced ? 0 : 0.04) * i })
        })
      }, reduced ? 1800 : 3600)
      return () => clearTimeout(id)
    }
  }, [stop])

  // shared materials whose opacity follows the fades
  const mats = useMemo(() => ({
    edgeRule: new THREE.MeshBasicMaterial({ color: C.grid, transparent: true, opacity: 0, depthWrite: false }),
    edgeCost: new THREE.MeshBasicMaterial({ color: C.quantum, transparent: true, opacity: 0, depthWrite: false }),
    wire: new THREE.MeshBasicMaterial({ color: '#BDBCB5', transparent: true, opacity: 0 }),
    slab: new THREE.MeshStandardMaterial({ color: C.quantum, transparent: true, opacity: 0, roughness: 0.6, depthWrite: false }),
    gate: new THREE.MeshStandardMaterial({ color: '#FFFFFF', transparent: true, opacity: 0, roughness: 0.6 }),
    meas: new THREE.MeshStandardMaterial({ color: C.text, transparent: true, opacity: 0, roughness: 0.6 }),
    pulse: new THREE.MeshBasicMaterial({ color: C.quantum, transparent: true, opacity: 0, depthWrite: false }),
  }), [])
  const pulse = useRef<THREE.Mesh>(null!)
  const pulseT = useRef(1)
  useEffect(() => { pulseT.current = stop === '4c' ? 0 : 1 }, [stop, pulseKey])
  const [circuitStage, setCircuitStage] = useState(-1)
  useFrame((_, dt) => {
    const f = fade.current
    mats.edgeRule.opacity = 0.85 * f.edges
    mats.edgeCost.opacity = 0.55 * f.edges
    mats.wire.opacity = f.circuit
    mats.slab.opacity = 0.16 * f.circuit
    mats.gate.opacity = f.circuit
    mats.meas.opacity = 0.9 * f.circuit
    if (pulseT.current < 1) {
      pulseT.current = Math.min(1, pulseT.current + dt / (reduced ? 0.01 : 6))
      const x = WIRE_X0 + 2 + (WIRE_X1 - WIRE_X0 - 2) * pulseT.current
      pulse.current.position.x = x
      mats.pulse.opacity = 0.5 * Math.sin(Math.PI * pulseT.current) ** 0.3
      const s = COLS.findIndex((c, k) => x < (COLS[k + 1]?.x ?? 99) - 3 && x >= c.x - 4)
      if (s !== circuitStage) setCircuitStage(s)
    } else {
      mats.pulse.opacity = 0
      if (stop === '4c' && circuitStage !== 99) setCircuitStage(99)
    }
  })

  // 4b: strongest interactions of the QUBO as lines between qubits on the ring
  const edges = useMemo(() => {
    const M = ex.qubo_matrix, out: { i: number; j: number; w: number; rule: string | null }[] = []
    for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) if (Math.abs(M[i][j]) > 1e-9) out.push({ i, j, w: Math.abs(M[i][j]), rule: pairRule(names[i], names[j]) })
    out.sort((a, b) => b.w - a.w)
    const keep = out.slice(0, 16)
    const mx = Math.max(...keep.map(e => e.w), 1e-9)
    return keep.map(e => ({ ...e, t: e.w / mx }))
  }, [ex])
  const ruleLabelAt = useMemo(() => { const seen = new Set<string>(); return edges.map(e => (e.rule && !seen.has(e.rule) ? (seen.add(e.rule), true) : false)) }, [edges])

  // 4d: QAOA output distribution, top states as bars (probabilities from the replay)
  const pmax = Math.max(...top.map(s => s.p), 1e-9)
  const bars = useRef<(THREE.Group | null)[]>([])
  useEffect(() => {
    top.forEach((s, k) => {
      const m = bars.current[k]
      if (!m) return
      gsap.killTweensOf(m.scale)
      const h = stop === '4d' ? Math.max(0.05, (s.p / pmax) * 24) : 0.001
      gsap.to(m.scale, { y: h, duration: reduced ? 0 : 0.8, ease: 'power3.out', delay: (reduced ? 0 : 0.06) * k + (stop === '4d' && !reduced ? 0.4 : 0) })
    })
  }, [stop])
  const uniform = 1 / 2 ** n
  const wireY = (i: number) => wirePos(i, n)[1]
  const spread = (n - 1) * 2.5

  return (
    <group position={anchor} rotation-y={yaw}>
      {/* device block headings (step 3 / 4e) */}
      {heads.map(h => (
        <Label3D key={h.title} show={mode === 'tiles' || (mode === 'decoded' && phase === 'a')} position={[h.x, 62.4, 0]} center>
          <div className="blockhead">{blockTitle(h.title, ex.zone, sc)}</div>
        </Label3D>
      ))}
      {names.map((v, i) => {
        const on = best[i] === '1'
        return (
          <group key={v} ref={g => { grp.current[i] = g }} position={home} scale={0.02}>
            <group ref={g => { tile.current[i] = g }}>
              <RoundedBox args={[TW, TH, 0.8]} radius={0.45} smoothness={3} castShadow>
                <meshStandardMaterial color={mode === 'decoded' && on ? '#EEEAFF' : '#FFFFFF'} emissive={mode === 'decoded' && on ? '#EEEAFF' : '#FFFFFF'} emissiveIntensity={0.25} roughness={0.8} />
              </RoundedBox>
              <Label3D show={mode === 'tiles' || (mode === 'decoded' && phase === 'a')} transform distanceFactor={18} position={[0, 0, 0.45]}>
                <div className={`tile ${labels[i].device} ${mode === 'decoded' ? (on ? 'yes' : 'no') : ''}`}>
                  <span className="q tn">q{i}</span>
                  <span className="t">{labels[i].short}</span>
                  {mode === 'decoded' && <span className="a">{on ? `YES · ${labels[i].yes}` : 'no'}</span>}
                </div>
              </Label3D>
            </group>
            <mesh ref={m => { ball.current[i] = m }} scale={0.001} castShadow>
              <sphereGeometry args={[1.25, 32, 24]} />
              <meshStandardMaterial color={C.quantum} roughness={0.35} />
            </mesh>
            <Label3D show={mode === 'ring'} position={ringLabelOffset(i, n)} center>
              <div className="qlabel"><b className="tn">q{i}</b> {labels[i].short}</div>
            </Label3D>
            <Label3D show={mode === 'wires' && stop !== '4d'} position={[-1.9, 0, 0]}>
              <div className="qlabel left"><b className="tn">q{i}</b> {labels[i].short}</div>
            </Label3D>
          </group>
        )
      })}
      {/* bits of the winning plan (4e) */}
      {names.map((v, i) => (
        <group key={`b${v}`} ref={g => { bit.current[i] = g }} scale={0.001}>
          <mesh><boxGeometry args={[1.5, 1.5, 1.5]} /><meshStandardMaterial color={best[i] === '1' ? C.quantum : '#FFFFFF'} roughness={0.5} /></mesh>
          <Label3D show={mode === 'decoded' && phase === 'a'} center zIndexRange={[31, 0]}><span className={`bitch tn ${best[i] === '1' ? 'one' : ''}`}>{best[i]}</span></Label3D>
        </group>
      ))}
      {/* 4b: interactions */}
      {edges.map((e, k) => {
        const a = new THREE.Vector3(...ringPos(e.i, n)), b = new THREE.Vector3(...ringPos(e.j, n))
        const d = new THREE.Vector3().subVectors(b, a), mid = a.clone().add(b).multiplyScalar(0.5)
        const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.clone().normalize())
        const r = 0.08 + 0.32 * e.t
        return (
          <group key={k}>
            <mesh position={mid} quaternion={q} scale={[r, d.length(), r]} material={e.rule ? mats.edgeRule : mats.edgeCost}>
              <cylinderGeometry args={[1, 1, 1, 8]} />
            </mesh>
            {ruleLabelAt[k] && (
              <Label3D show={stop === '4b'} position={mid.clone().lerp(new THREE.Vector3(0, 50, 0), 0.45).toArray()} center>
                <div className="rulechip">{e.rule}</div>
              </Label3D>
            )}
          </group>
        )
      })}
      {/* 4c: the QAOA circuit */}
      <group visible={stop === '4c' || stop === '4d'} position={stop === '4d' ? [-4, 6, -22] : [0, 0, 0]}>
        {names.map((_, i) => (
          <mesh key={i} position={[(WIRE_X0 + WIRE_X1) / 2 + 1, wireY(i), -0.4]} scale={[WIRE_X1 - WIRE_X0 - 2, 0.14, 0.14]} material={mats.wire}><boxGeometry /></mesh>
        ))}
        {COLS.map((c, k) => (
          <group key={c.label}>
            {c.wide
              ? <mesh position={[c.x, 50, -0.2]} scale={[7, spread + 2.6, 0.6]} material={mats.slab}><boxGeometry /></mesh>
              : names.map((_, i) => <mesh key={i} position={[c.x, wireY(i), 0]} scale={[1.6, 1.6, 0.6]} material={k === COLS.length - 1 ? mats.meas : mats.gate}><boxGeometry /></mesh>)}
            <Label3D show={stop === '4c'} position={[c.x, 50 + spread / 2 + 3.4, 0]} center>
              <div className={`colhead ${circuitStage === k ? 'on' : ''}`}>{c.label}</div>
            </Label3D>
          </group>
        ))}
        <mesh ref={pulse} position={[WIRE_X0, 50, 0.6]} scale={[0.7, spread + 3.4, 0.2]} material={mats.pulse}><boxGeometry /></mesh>
      </group>
      {/* 4d: histogram of measured plans */}
      <group visible={stop === '4d'}>
        {top.map((s, k) => {
          const isBest = s.bits === best
          const h = Math.max(0.05, (s.p / pmax) * 24)
          return (
            <group key={s.bits} position={[histX(k), 37, 4]}>
              <group ref={g => { bars.current[k] = g }} scale={[1, 0.001, 1]}>
                <mesh position-y={0.5} castShadow>
                  <boxGeometry args={[2.8, 1, 2.8]} />
                  <meshStandardMaterial color={isBest ? C.quantum : s.feasible ? '#C9BFFB' : '#E2E1DB'} roughness={0.7} />
                </mesh>
              </group>
              <Label3D show={stop === '4d'} position={[0, h + 1.4, 0]} center>
                <div className={`barlab tn ${isBest ? 'best' : ''} ${s.feasible ? '' : 'bad'}`}>{s.feasible ? '' : '✕ '}{(s.p * 100).toFixed(2)}%</div>
              </Label3D>
              {isBest && (
                <Label3D show={stop === '4d'} position={[0, -1.8, 0]} center>
                  <div className="barbest"><code>{s.bits}</code><span>cheapest plan that breaks no rule</span></div>
                </Label3D>
              )}
            </group>
          )
        })}
        <mesh position={[0, 37 + (uniform / pmax) * 24, 4]} scale={[56, 0.12, 0.12]}><boxGeometry /><meshBasicMaterial color={C.muted} /></mesh>
        <Label3D show={stop === '4d'} position={[29, 37 + (uniform / pmax) * 24 + 1.2, 4]}>
          <div className="barref">random guess ({(uniform * 100).toFixed(3)}%)</div>
        </Label3D>
      </group>
    </group>
  )
}

const histX = (k: number) => -24 + k * 5.3
const ringLabelOffset = (i: number, n: number): V3 => {
  const a = Math.PI / 2 - (2 * Math.PI * i) / n
  return [Math.cos(a) * 5.2, Math.sin(a) * 3.4, 0]
}
function blockTitle(t: string, zone: string, sc: Scenario) {
  if (t === 'battery') return 'Battery · next 45 min'
  if (t.startsWith('cable')) {
    const l = Number(t.split(' ')[1]); const [a, b] = sc.campus.lines[l]
    const o = zone === a ? b : a
    return `Cable to ${zn(o)}`
  }
  return 'Other'
}
