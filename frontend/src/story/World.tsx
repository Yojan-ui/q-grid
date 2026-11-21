import { forwardRef, useLayoutEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useFrame, useThree } from '@react-three/fiber'
import { Billboard, Edges, OrbitControls, Text } from '@react-three/drei'
import gsap from 'gsap'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import type { QaoaFile, Run, Scenario } from '../lib/data'
import { C, signed, zn } from '../lib/theme'
import { type Beat, couplings, measure, varInfo } from './model'

const FONT = `${(import.meta as any).env?.BASE_URL ?? '/'}fonts/Inter-600.woff`
const reduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
const D_OBJ = reduced ? 0 : 0.75, D_CAM = reduced ? 0 : 1.1, STAG = reduced ? 0 : 0.05
const at = (a: number[], t: number) => a[Math.min(Math.floor(t), a.length - 1)]
export const SUB = new THREE.Vector3(-250, 0, 40)

/* ----------------------------------------------------------------------------- tween helpers */
type V3 = [number, number, number]
// keep scene in step with the text even when frames are slow (otherwise GSAP stretches time)
gsap.ticker.lagSmoothing(0)

function useTween(ref: React.RefObject<THREE.Object3D | null>, pos: V3, scale: number, rotY = 0, delay = 0, dur = D_OBJ) {
  useLayoutEffect(() => {
    const o = ref.current; if (!o) return
    const tl = gsap.timeline()
    tl.to(o.position, { x: pos[0], y: pos[1], z: pos[2], duration: dur, delay, ease: 'power3.inOut' }, 0)
    tl.to(o.scale, { x: scale, y: scale, z: scale, duration: dur, delay, ease: 'power3.inOut' }, 0)
    tl.to(o.rotation, { y: rotY, duration: dur, delay, ease: 'power3.inOut' }, 0)
    return () => { tl.kill() }
  }, [pos[0], pos[1], pos[2], scale, rotY, delay])
}

function Label({ text, position, size = 4, color = C.text, anchorY = 'middle' as any, maxWidth }: {
  text: string; position: V3; size?: number; color?: string; anchorY?: any; maxWidth?: number }) {
  return (
    <Billboard position={position}>
      <Text font={FONT} fontSize={size} color={color} anchorX="center" anchorY={anchorY} maxWidth={maxWidth} textAlign="center"
        outlineWidth={size * 0.1} outlineColor={C.bg}>{text}</Text>
    </Billboard>
  )
}

/* ----------------------------------------------------------------------------- campus model */
function inPoly(x: number, y: number, p: [number, number][]) {
  let c = false
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) {
    const [xi, yi] = p[i], [xj, yj] = p[j]
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c
  }
  return c
}

export function useZoneGeo(sc: Scenario) {
  return useMemo(() => sc.campus.zones.map(z => {
    const geos: THREE.BufferGeometry[] = [], panels: THREE.Matrix4[] = []
    let h = 6
    const roof = z.buildings.reduce((a, b) => a + Math.abs(THREE.ShapeUtils.area(b.polygon.map(([x, y]) => new THREE.Vector2(x, y)))), 0)
    for (const b of z.buildings) {
      if (b.polygon.length < 3) continue
      const bh = Math.max(1, b.levels) * 3.6
      h = Math.max(h, bh)
      const shape = new THREE.Shape(b.polygon.map(([x, y]) => new THREE.Vector2(x, y)))
      const g = new THREE.ExtrudeGeometry(shape, { depth: bh, bevelEnabled: true, bevelThickness: 0.3, bevelSize: 0.3, bevelSegments: 1 })
      g.rotateX(-Math.PI / 2)
      geos.push(g)
      const area = Math.abs(THREE.ShapeUtils.area(shape.getPoints()))
      const target = (z.pv_kwp / 0.18) * (area / Math.max(roof, 1)) / 4   // tiles of 4 m2; kWp / 0.18 kWp/m2 (config ASSUMPTION)
      const xs = b.polygon.map(q => q[0]), ys = b.polygon.map(q => q[1])
      let n = 0
      for (let y = Math.min(...ys) + 2; y < Math.max(...ys) - 1 && n < target; y += 2.2)
        for (let x = Math.min(...xs) + 2; x < Math.max(...xs) - 1.5 && n < target; x += 3.7)
          if (inPoly(x, y, b.polygon) && inPoly(x + 1.6, y + 0.7, b.polygon) && inPoly(x - 1.6, y - 0.7, b.polygon)) {
            panels.push(new THREE.Matrix4().compose(new THREE.Vector3(x, bh + 0.75, -y), new THREE.Quaternion().setFromEuler(new THREE.Euler(-0.2, 0, 0)), new THREE.Vector3(3.3, 0.1, 1.3)))
            n++
          }
    }
    return { z, geo: geos.length ? mergeGeometries(geos, false) : null, h, panels }
  }), [sc])
}

function Panels({ mats }: { mats: THREE.Matrix4[] }) {
  const ref = useRef<THREE.InstancedMesh>(null!)
  useLayoutEffect(() => { mats.forEach((m, i) => ref.current.setMatrixAt(i, m)); ref.current.instanceMatrix.needsUpdate = true }, [mats])
  return (
    <instancedMesh ref={ref} args={[undefined, undefined, mats.length]} castShadow>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color={C.panel} roughness={0.45} metalness={0.1} />
    </instancedMesh>
  )
}

function dashTex() {
  const c = document.createElement('canvas'); c.width = 4; c.height = 64
  const g = c.getContext('2d')!; g.fillStyle = '#fff'; g.fillRect(0, 0, 4, 40)
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; return t
}
const UP = new THREE.Vector3(0, 1, 0)
/** Thin solid ribbon along a line, slow dashes moving in the flow direction, width proportional to kW. */
export function Ribbon({ a, b, kw, color, max = 400 }: { a: THREE.Vector3; b: THREE.Vector3; kw: number; color: string; max?: number }) {
  const { len, mid, quat, tex } = useMemo(() => {
    const d = new THREE.Vector3().subVectors(b, a), len = d.length(), tex = dashTex()
    tex.repeat.set(1, Math.max(1, len / 12))
    return { len, mid: new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5), quat: new THREE.Quaternion().setFromUnitVectors(UP, d.normalize()), tex }
  }, [a.x, a.y, a.z, b.x, b.y, b.z])
  const mag = Math.min(1, Math.abs(kw) / max)
  useFrame((_, dt) => { if (!reduced) tex.offset.y -= Math.sign(kw) * dt * (0.25 + 0.6 * mag) })
  if (Math.abs(kw) < 1) return null
  const w = 0.35 + 1.4 * mag
  return (
    <group>
      <mesh position={mid} quaternion={quat} scale={[w * 0.55, len, w * 0.55]}>
        <cylinderGeometry args={[1, 1, 1, 8, 1, true]} />
        <meshBasicMaterial color={color} transparent opacity={0.28} />
      </mesh>
      <mesh position={mid} quaternion={quat} scale={[w, len, w]}>
        <cylinderGeometry args={[1, 1, 1, 8, 1, true]} />
        <meshBasicMaterial map={tex} color={color} transparent alphaTest={0.5} side={THREE.DoubleSide} />
      </mesh>
    </group>
  )
}

type CampusProps = { sc: Scenario; run: Run; t: number; offset?: V3; beat: Beat; focus: string; removed?: string | null; hover?: string | null;
  flows?: number[] | null; showRibbons: boolean; onZone?: (z: string | null) => void; onHover?: (z: string | null) => void; liftAll?: boolean; ghost?: boolean }

function ZoneGroup({ i, z, geo, panels, lifted, removed, ghost, onZone, onHover, children }: any) {
  const ref = useRef<THREE.Group>(null!)
  useTween(ref, [0, removed ? -7 : lifted ? 3 : 0, 0], 1, 0, lifted ? i * STAG * 2 : 0)
  return (
    <group ref={ref} onClick={(e: any) => { e.stopPropagation(); onZone?.(z.name) }}
      onPointerOver={(e: any) => { e.stopPropagation(); onHover?.(z.name) }} onPointerOut={() => onHover?.(null)}>
      {geo && (
        <mesh geometry={geo} castShadow receiveShadow>
          <meshStandardMaterial color={removed ? C.offline : C.clay} roughness={0.95} transparent={ghost} opacity={ghost ? 0.55 : 1} />
          {lifted && <Edges threshold={30} color={C.hair} />}
        </mesh>
      )}
      {!removed && panels.length > 0 && <Panels mats={panels} />}
      {children}
    </group>
  )
}

export function Campus({ sc, run, t, offset = [0, 0, 0], beat, focus, removed, hover, flows, showRibbons, onZone, onHover, liftAll, ghost }: CampusProps) {
  const zg = useZoneGeo(sc)
  const slot = Math.min(95, Math.floor(t))
  const gridUp = sc.slots.grid_up[slot] === 1
  const P = useMemo(() => Object.fromEntries(sc.campus.zones.map(z => [z.name, [z.cx, -z.cy]])), [sc])
  const pos = (n: string, y = 1.2) => new THREE.Vector3(P[n][0], y, P[n][1])
  const tank = sc.campus.zones.find(z => z.tank_m3 > 0)
  return (
    <group position={offset}>
      {zg.map(({ z, geo, h, panels }, i) => {
        const soc = run.soc[i][Math.min(96, slot + 1)]
        const cap: V3 = [z.cx + 15, 0, -z.cy + 12]
        const dgOn = run.dg_kw[i][slot] > 0
        return (
          <ZoneGroup key={z.name} i={i} z={z} geo={geo} h={h} panels={panels} lifted={liftAll || hover === z.name || (beat === '2' && focus === z.name)}
            removed={removed === z.name} ghost={ghost} onZone={onZone} onHover={onHover}>
            {z.battery_kwh > 0 && (
              <group position={cap}>
                <mesh position-y={4.6} castShadow><capsuleGeometry args={[2.1, 5.4, 6, 14]} /><meshStandardMaterial color="#FFFFFF" transparent opacity={0.55} roughness={0.3} /></mesh>
                <mesh position-y={1.9 + 2.7 * soc} scale={[1, Math.max(0.04, soc), 1]}><capsuleGeometry args={[1.7, 5.4, 6, 14]} /><meshStandardMaterial color={C.battery} roughness={0.6} /></mesh>
              </group>
            )}
            {z.dg_kw > 0 && <DG at={[z.cx - 17, 0, -z.cy - 10]} on={dgOn} />}
            {(hover === z.name || (beat === '2' && (focus === z.name || liftAll))) && <Label text={zn(z.name)} position={[z.cx, h + 12, -z.cy]} size={hover === z.name || focus === z.name ? 6 : 4.5} />}
          </ZoneGroup>
        )
      })}
      {tank && (
        <group position={[tank.cx, 0, -tank.cy]}>
          <mesh position-y={8}><cylinderGeometry args={[6.5, 6.5, 16, 32, 1, true]} /><meshStandardMaterial color="#FFFFFF" transparent opacity={0.5} side={THREE.DoubleSide} /></mesh>
          <Water level={at(run.tank_m3[tank.name] ?? [0], t) / tank.tank_m3} />
        </group>
      )}
      {sc.campus.lines.map(([a, b], i) => {
        const dead = removed && (a === removed || b === removed)
        const f = flows ? flows[i] : run.flows[i][slot]
        return (
          <group key={i}>
            <Line_ a={pos(a, 0.35)} b={pos(b, 0.35)} color={dead ? C.hair : C.road} />
            {showRibbons && !dead && <Ribbon a={pos(a)} b={pos(b)} kw={f} color={C.solar} max={160} />}
          </group>
        )
      })}
      <mesh position={[SUB.x, 5, SUB.z]} castShadow receiveShadow>
        <boxGeometry args={[14, 10, 14]} />
        <meshStandardMaterial color={gridUp ? '#EDEBE4' : C.offline} roughness={0.9} />
      </mesh>
      {sc.campus.zones.map((z, i) => {
        const net = run.net_kw[i][slot]
        return (
          <group key={`f${z.name}`}>
            <Line_ a={new THREE.Vector3(SUB.x, 0.3, SUB.z)} b={pos(z.name, 0.3)} color={gridUp ? C.road : C.hair} />
            {showRibbons && gridUp && <Ribbon a={new THREE.Vector3(SUB.x, 1, SUB.z)} b={pos(z.name, 1)} kw={net} color={net > 0 ? C.grid : C.solar} max={900} />}
          </group>
        )
      })}
    </group>
  )
}

export function Line_({ a, b, color }: { a: THREE.Vector3; b: THREE.Vector3; color: string }) {
  const obj = useMemo(() => new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]), new THREE.LineBasicMaterial({ color })), [a.x, a.y, a.z, b.x, b.y, b.z, color])
  return <primitive object={obj} />
}

function DG({ at: p, on }: { at: V3; on: boolean }) {
  const fan = useRef<THREE.Mesh>(null!)
  useFrame((_, dt) => { if (on && !reduced) fan.current.rotation.y += dt * 6 })
  return (
    <group position={p}>
      <mesh position-y={2.5} castShadow><boxGeometry args={[7, 5, 4.5]} /><meshStandardMaterial color={on ? '#E7E3D6' : '#DAD9D2'} roughness={0.9} /></mesh>
      <mesh ref={fan} position-y={5.2}><cylinderGeometry args={[1.6, 1.6, 0.4, 3]} /><meshStandardMaterial color={on ? C.battery : C.offline} /></mesh>
    </group>
  )
}

function Water({ level }: { level: number }) {
  const ref = useRef<THREE.Mesh>(null!)
  const cur = useRef(level)
  useFrame((_, dt) => { cur.current += (level - cur.current) * Math.min(1, dt * 3); const l = Math.max(0.02, cur.current); ref.current.scale.y = l; ref.current.position.y = 8 * l })
  return <mesh ref={ref}><cylinderGeometry args={[6.1, 6.1, 16, 32]} /><meshStandardMaterial color={C.water} roughness={0.4} transparent opacity={0.85} /></mesh>
}

/* ----------------------------------------------------------------------------- the quantum rig (steps 3-4) */
function Tile({ i, info, value, target, scale, rotY, delay, showValue }: { i: number; info: ReturnType<typeof varInfo>; value: number | null; target: V3; scale: number; rotY: number; delay: number; showValue: boolean }) {
  const ref = useRef<THREE.Group>(null!)
  useTween(ref, target, scale, rotY, delay)
  const col = { battery: C.battery, dg: C.offline, water: C.water, flex: C.accent, line: C.solar, other: C.muted }[info.kind] ?? C.muted
  return (
    <group ref={ref} scale={0}>
      <mesh castShadow><boxGeometry args={[15, 7.5, 0.8]} /><meshStandardMaterial color="#FFFFFF" emissive="#FFFFFF" emissiveIntensity={0.45} roughness={0.6} /><Edges color={C.hair} /></mesh>
      <mesh position={[-6.2, 2.4, 0.45]}><circleGeometry args={[0.7, 20]} /><meshBasicMaterial color={col} /></mesh>
      <Text font={FONT} position={[-5.2, 2.4, 0.5]} fontSize={1.25} color={C.muted} anchorX="left" anchorY="middle">{`decision ${i + 1}`}</Text>
      <Text font={FONT} position={[0, -0.6, 0.5]} fontSize={1.55} maxWidth={13.5} color={C.text} anchorX="center" anchorY="middle" textAlign="center">
        {showValue && value !== null ? (value ? info.on : info.off) : info.label}
      </Text>
      {showValue && value !== null && <mesh position={[6.2, 2.4, 0.45]}><circleGeometry args={[0.8, 20]} /><meshBasicMaterial color={value ? C.quantum : C.hair} /></mesh>}
    </group>
  )
}

function Qubit({ i, name, target, scale, delay, compact }: { i: number; name: string; target: V3; scale: number; delay: number; compact?: boolean }) {
  const ref = useRef<THREE.Group>(null!)
  useTween(ref, target, scale, 0, delay)
  return (
    <group ref={ref} scale={0}>
      <mesh castShadow><sphereGeometry args={[2.3, 32, 32]} /><meshStandardMaterial color={C.quantum} roughness={0.55} /></mesh>
      {compact ? (
        <Text font={FONT} position={[-3.6, 0, 0]} fontSize={2.6} color={C.text} anchorX="right" anchorY="middle" outlineWidth={0.3} outlineColor={C.bg}>{`q${i}  ${name}`}</Text>
      ) : (<>
        <Text font={FONT} position={[0, -4.0, 0]} fontSize={1.9} color={C.text} anchorX="center" outlineWidth={0.25} outlineColor={C.bg}>{`q${i}`}</Text>
        <Text font={FONT} position={[0, -6.3, 0]} fontSize={1.55} color={C.muted} anchorX="center" maxWidth={16} textAlign="center" outlineWidth={0.25} outlineColor={C.bg}>{name}</Text>
      </>)}
    </group>
  )
}

function Bar({ k, x, h, win, delay, bitsLabel, base }: { k: number; x: number; h: number; win: boolean; delay: number; bitsLabel: string; base: V3 }) {
  const ref = useRef<THREE.Mesh>(null!)
  useLayoutEffect(() => {
    const m = ref.current
    const tl = gsap.timeline()
    tl.fromTo(m.scale, { y: 0.001 }, { y: Math.max(0.001, h), duration: D_OBJ, delay, ease: 'power3.out' })
    tl.fromTo(m.position, { y: base[1] }, { y: base[1] + h / 2, duration: D_OBJ, delay, ease: 'power3.out' }, 0)
    return () => { tl.kill() }
  }, [h, delay])
  return (
    <group>
      <mesh ref={ref} position={[base[0] + x, base[1], base[2]]} castShadow>
        <boxGeometry args={[3.4, 1, 3.4]} />
        <meshStandardMaterial color={C.quantum} roughness={0.6} transparent opacity={win ? 1 : 0.35} />
      </mesh>
      {win && <Text font={FONT} position={[base[0] + x - 1.7, base[1] + h + 3.5, base[2]]} fontSize={2.2} color={C.quantum} anchorX="left" outlineWidth={0.3} outlineColor={C.bg}>{`winner  ${bitsLabel}`}</Text>}
      {k === 0 && null}
    </group>
  )
}

function FlyingBit({ from, to, value, delay, show }: { from: V3; to: V3; value: string; delay: number; show: boolean }) {
  const ref = useRef<THREE.Group>(null!)
  useLayoutEffect(() => {
    const g = ref.current
    if (!show) { gsap.set(g.scale, { x: 0, y: 0, z: 0 }); return }
    gsap.set(g.position, { x: from[0], y: from[1], z: from[2] }); gsap.set(g.scale, { x: 1, y: 1, z: 1 })
    const tl = gsap.timeline()
    tl.to(g.position, { x: to[0], y: to[1] + 6, z: to[2], duration: reduced ? 0 : 0.9, delay, ease: 'power3.inOut' })
    tl.to(g.scale, { x: 0, y: 0, z: 0, duration: reduced ? 0 : 0.3 }, '+=0.15')
    return () => { tl.kill() }
  }, [show])
  return (
    <group ref={ref} scale={0}>
      <mesh><boxGeometry args={[2.4, 2.4, 2.4]} /><meshStandardMaterial color={value === '1' ? C.quantum : '#FFFFFF'} /><Edges color={C.quantum} /></mesh>
      <Text font={FONT} position={[0, 0, 1.3]} fontSize={1.6} color={value === '1' ? '#FFFFFF' : C.quantum} anchorX="center" anchorY="middle">{value}</Text>
    </group>
  )
}

export function QuantumRig({ sc, q, beat, origin, buildingTop, dropped }: { sc: Scenario; q: QaoaFile; beat: Beat; origin: V3; buildingTop: V3; dropped: boolean }) {
  const n = q.n_qubits
  const infos = useMemo(() => q.var_names.map(v => varInfo(v, sc, q.zone)), [q, sc])
  const meas = useMemo(() => measure(q), [q])
  const cpl = useMemo(() => couplings(q), [q])
  const [ox, oy, oz] = origin
  const cols = Math.min(5, n), rows = Math.ceil(n / cols)
  const grid = (i: number): V3 => [ox + ((i % cols) - (cols - 1) / 2) * 17, oy + ((rows - 1) / 2 - Math.floor(i / cols)) * 10, oz]
  const ring = (i: number): V3 => [ox + Math.cos((i / n) * Math.PI * 2 + Math.PI / 2) * 40, oy + Math.sin((i / n) * Math.PI * 2 + Math.PI / 2) * 30, oz]
  const wireY = (i: number) => oy + ((n - 1) / 2 - i) * 5.4
  const wireX0 = ox - 62, wireX1 = ox + 6
  const wire = (i: number): V3 => [wireX0, wireY(i), oz]
  const tileIn = ['3', '4e'].includes(beat), qubitIn = ['4a', '4b', '4c', '4d'].includes(beat)
  const winBits = meas.winBits ?? q.optimum.bits
  // 4e sequence: bits fly (0-1.4 s), tiles appear with actions (1.4 s), tiles drop back into the building (3.6 s)
  const tilesShow = (beat === '3') || (beat === '4e')
  const histBase: V3 = [ox + 52, oy - 24, oz]
  const P = meas.P, pmax = P[meas.top10[0]] || 1
  return (
    <group>
      {infos.map((info, i) => {
        const target: V3 = beat === '4e' && dropped ? buildingTop : grid(i)
        const scale = tilesShow ? (beat === '4e' && dropped ? 0.001 : 1) : 0.001
        return <Tile key={`t${i}`} i={i} info={info} value={beat === '4e' ? Number(winBits[i]) : null} showValue={beat === '4e'}
          target={!tileIn && !qubitIn && beat !== '4f' && beat !== '4g' ? buildingTop : target} scale={scale}
          rotY={beat === '4a' ? Math.PI / 2 : 0} delay={beat === '4e' ? (dropped ? i * STAG : 1.4 + i * STAG) : i * STAG} />
      })}
      {infos.map((info, i) => {
        const tgt: V3 = beat === '4a' ? grid(i) : beat === '4b' ? ring(i) : beat === '4c' || beat === '4d' ? wire(i) : grid(i)
        const onWire = beat === '4c' || beat === '4d'
        return <Qubit key={`q${i}`} i={i} name={(info as any).short ?? info.label} target={tgt} compact={onWire} scale={qubitIn ? (onWire ? 0.7 : 1) : 0.001} delay={beat === '4a' ? 0.3 + i * STAG : i * STAG} />
      })}
      {beat === '4b' && cpl.map((c, k) => <CouplingLine key={k} a={ring(c.i)} b={ring(c.j)} s={c.s} delay={0.6 + k * 0.03} />)}
      {(beat === '4c' || beat === '4d') && <Circuit n={n} q={q} wireY={wireY} x0={wireX0} x1={wireX1} z={oz} active={beat === '4c'} />}
      {beat === '4d' && meas.top10.map((z, k) => (
        <Bar key={z} k={k} x={k * 4.6} h={Math.max(0.5, 30 * P[z] / pmax)} win={z === meas.win} delay={0.3 + k * STAG}
          bitsLabel={meas.winBits ?? ''} base={histBase} />
      ))}
      {beat === '4d' && <Text font={FONT} position={[histBase[0] + 21, histBase[1] - 4, oz]} fontSize={2} color={C.muted} anchorX="center">10 most frequent results of 256 measurements</Text>}
      {beat === '4e' && dropped && <Label position={[buildingTop[0], buildingTop[1] + 22, buildingTop[2]]} size={3.2} color={C.quantum}
        text={`${zn(q.zone)}: ${infos.map((inf, i) => ({ inf, b: Number(winBits[i]) })).filter(x => x.b === 1 || ['dg', 'water'].includes(x.inf.kind)).map(x => (x.b ? x.inf.on : x.inf.off)).join(' · ') || 'hold'}`} />}
      {beat === '4e' && infos.map((_, i) => {
        const k = meas.top10.indexOf(meas.win)
        const from: V3 = [histBase[0] + k * 4.6, histBase[1] + 30 * (P[meas.win] / pmax) + 2, oz]
        return <FlyingBit key={`b${i}`} from={from} to={grid(i)} value={winBits[i]} delay={i * STAG} show />
      })}
    </group>
  )
}

function CouplingLine({ a, b, s, delay }: { a: V3; b: V3; s: number; delay: number }) {
  const ref = useRef<THREE.Mesh>(null!)
  const { mid, quat, len } = useMemo(() => {
    const A = new THREE.Vector3(...a), B = new THREE.Vector3(...b), d = new THREE.Vector3().subVectors(B, A)
    return { mid: new THREE.Vector3().addVectors(A, B).multiplyScalar(0.5), quat: new THREE.Quaternion().setFromUnitVectors(UP, d.clone().normalize()), len: d.length() }
  }, [a, b])
  useLayoutEffect(() => { const t = gsap.fromTo(ref.current.scale, { y: 0.001 }, { y: len, duration: D_OBJ, delay, ease: 'power2.out' }); return () => { t.kill() } }, [len])
  const w = 0.12 + 0.6 * s
  return <mesh ref={ref} position={mid} quaternion={quat} scale={[w, 0.001, w]}><cylinderGeometry args={[1, 1, 1, 6]} /><meshStandardMaterial color={C.quantum} transparent opacity={0.25 + 0.5 * s} /></mesh>
}

function Circuit({ n, q, wireY, x0, x1, z, active }: { n: number; q: QaoaFile; wireY: (i: number) => number; x0: number; x1: number; z: number; active: boolean }) {
  const pulse = useRef<THREE.Mesh>(null!)
  const top = wireY(0) + 3, bot = wireY(n - 1) - 3, hgt = top - bot, mid = (top + bot) / 2
  const p = q.gammas.length
  const span = (x1 - x0 - 10) / p
  useLayoutEffect(() => {
    if (!active || reduced) return
    const tl = gsap.timeline({ delay: 0.9 })
    tl.fromTo(pulse.current.position, { x: x0 + 4 }, { x: x1, duration: 2.6, ease: 'power1.inOut', repeat: 1, repeatDelay: 0.4 })
    return () => { tl.kill() }
  }, [active])
  return (
    <group>
      {Array.from({ length: n }, (_, i) => <Line_ key={i} a={new THREE.Vector3(x0, wireY(i), z - 0.5)} b={new THREE.Vector3(x1 + 40, wireY(i), z - 0.5)} color={C.hair} />)}
      <mesh position={[x0 + 5, mid, z]}><boxGeometry args={[3, hgt, 1]} /><meshStandardMaterial color="#FFFFFF" /><Edges color={C.muted} /></mesh>
      <Text font={FONT} position={[x0 + 5, top + 2.2, z]} fontSize={1.4} color={C.muted} anchorX="center">start</Text>
      {q.gammas.map((_g, l) => (
        <group key={l}>
          <mesh position={[x0 + 10 + l * span + span * 0.3, mid, z]}><boxGeometry args={[span * 0.42, hgt, 1]} /><meshStandardMaterial color={C.quantum} transparent opacity={0.16} /><Edges color={C.quantum} /></mesh>
          <Text font={FONT} position={[x0 + 10 + l * span + span * 0.3, top + 2.2, z]} fontSize={1.4} color={C.quantum} anchorX="center">{`cost ${l + 1}`}</Text>
          <mesh position={[x0 + 10 + l * span + span * 0.75, mid, z]}><boxGeometry args={[span * 0.26, hgt, 1]} /><meshStandardMaterial color={C.accent} transparent opacity={0.14} /><Edges color={C.accent} /></mesh>
          <Text font={FONT} position={[x0 + 10 + l * span + span * 0.75, top + 2.2, z]} fontSize={1.4} color={C.accent} anchorX="center">{`mix ${l + 1}`}</Text>
        </group>
      ))}
      <mesh position={[x1 + 2, mid, z]}><boxGeometry args={[3, hgt, 1]} /><meshStandardMaterial color="#FFFFFF" /><Edges color={C.muted} /></mesh>
      <Text font={FONT} position={[x1 + 2, top + 2.2, z]} fontSize={1.4} color={C.muted} anchorX="center">measure</Text>
      <mesh ref={pulse} position={[x0 + 4, mid, z + 0.8]}><boxGeometry args={[1.2, hgt + 2, 0.2]} /><meshBasicMaterial color={C.accent} transparent opacity={active ? 0.35 : 0} /></mesh>
    </group>
  )
}

/* ----------------------------------------------------------------------------- device icons (step 2) */
function Pop({ children, position, i }: { children: React.ReactNode; position: V3; i: number }) {
  const ref = useRef<THREE.Group>(null!)
  useLayoutEffect(() => { const t = gsap.fromTo(ref.current.scale, { x: 0.001, y: 0.001, z: 0.001 }, { x: 1, y: 1, z: 1, duration: D_OBJ, delay: 0.2 + i * STAG, ease: 'back.out(1.6)' }); return () => { t.kill() } }, [])
  return <group ref={ref} position={position}>{children}</group>
}
export function DeviceIcons({ sc, zone, h }: { sc: Scenario; zone: string; h: number }) {
  const z = sc.campus.zones.find(x => x.name === zone)!
  const items: { label: string; node: React.ReactNode }[] = [{ label: `Solar ${Math.round(z.pv_kwp)} kWp`, node: <mesh rotation-x={-0.4}><boxGeometry args={[7, 0.5, 4]} /><meshStandardMaterial color={C.panel} /></mesh> }]
  if (z.battery_kwh) items.push({ label: `Battery ${z.battery_kwh} kWh`, node: <mesh><capsuleGeometry args={[1.6, 4, 6, 12]} /><meshStandardMaterial color={C.battery} /></mesh> })
  if (z.tank_m3) items.push({ label: `Pump + tank ${z.tank_m3} m³`, node: <mesh><cylinderGeometry args={[2.4, 2.4, 5, 24]} /><meshStandardMaterial color={C.water} /></mesh> })
  if (z.dg_kw) items.push({ label: `Diesel ${z.dg_kw} kW`, node: <mesh><boxGeometry args={[5, 3.5, 3]} /><meshStandardMaterial color="#C9C8C1" /></mesh> })
  for (const f of z.flex ?? []) items.push({ label: f.name.replace(/_/g, ' '), node: <mesh><boxGeometry args={[3.6, 3.6, 3.6]} /><meshStandardMaterial color="#FFFFFF" /><Edges color={C.accent} /></mesh> })
  items.push({ label: `Critical load ${Math.round(100 * z.critical_frac)}%`, node: <mesh><boxGeometry args={[3.6, 3.6, 3.6]} /><meshStandardMaterial color="#FFFFFF" /><Edges color={C.grid} /></mesh> })
  const n = items.length
  return (
    <group position={[z.cx - 20, h + 62, -z.cy]} scale={1.6}>
      {items.map((it, i) => {
        const x = (i - (n - 1) / 2) * 16
        return (
          <Pop key={it.label} i={i} position={[x, 0, 0]}>
            {it.node}
            <Billboard position={[0, -5.5, 0]}><Text font={FONT} fontSize={2.3} color={C.text} anchorX="center" outlineWidth={0.3} outlineColor={C.bg} maxWidth={14} textAlign="center">{it.label}</Text></Billboard>
          </Pop>
        )
      })}
    </group>
  )
}

/* ----------------------------------------------------------------------------- ADMM labels (step 5) */
export function AdmmLabels({ sc, round, slot, removed }: { sc: Scenario; round: number; slot: number; removed?: string | null }) {
  const its = sc.admm.iterations[String(slot)] ?? []
  const r = its[Math.min(round, its.length - 1)]
  if (!r) return null
  return (
    <group>
      {sc.campus.lines.map(([a, b], l) => {
        const pr = r.proposals[String(l)]
        if (!pr || (removed && (a === removed || b === removed))) return null
        const A = sc.campus.zones.find(z => z.name === a)!, B = sc.campus.zones.find(z => z.name === b)!
        const mid: V3 = [(A.cx + B.cx) / 2, 9, -(A.cy + B.cy) / 2]
        const agree = pr[0] === pr[1]
        return <Label key={l} position={mid} size={8} color={agree ? C.solar : C.text}
          text={agree ? `${signed(pr[0])} agreed` : `${signed(pr[0])} vs ${signed(pr[1])}`} />
      })}
    </group>
  )
}

/* ----------------------------------------------------------------------------- scale-out illustration (step 7) */
export function ScaleOut({ show }: { show: boolean }) {
  const ref = useRef<THREE.Group>(null!)
  useTween(ref, [0, 0, 0], show ? 1 : 0.001, 0, show ? 0.4 : 0)
  const blocks = useMemo(() => {
    const out: { p: V3; s: V3 }[] = []
    let seed = 7
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647
    for (let c = 0; c < 8; c++) {
      const ang = (c / 8) * Math.PI * 2, R = 1500
      const cx = Math.cos(ang) * R, cz = Math.sin(ang) * R
      for (let k = 0; k < 14; k++) out.push({ p: [cx + (rnd() - 0.5) * 380, 0, cz + (rnd() - 0.5) * 380], s: [30 + rnd() * 60, 8 + rnd() * 18, 30 + rnd() * 60] })
    }
    return out
  }, [])
  return (
    <group ref={ref} scale={0.001}>
      {blocks.map((b, i) => <mesh key={i} position={[b.p[0], b.s[1] / 2, b.p[2]]} castShadow><boxGeometry args={b.s} /><meshStandardMaterial color={C.clay} roughness={0.95} /></mesh>)}
      {Array.from({ length: 8 }, (_, c) => {
        const ang = (c / 8) * Math.PI * 2
        return <Line_ key={c} a={new THREE.Vector3(0, 1, 0)} b={new THREE.Vector3(Math.cos(ang) * 1500, 1, Math.sin(ang) * 1500)} color={C.muted} />
      })}
    </group>
  )
}

/* ----------------------------------------------------------------------------- camera */
export function CameraRig({ pos, target, free }: { pos: V3; target: V3; free: boolean }) {
  const { camera } = useThree()
  const tgt = useRef(new THREE.Vector3(...target))
  const ctl = useRef<any>(null)
  useLayoutEffect(() => {
    const tl = gsap.timeline()
    tl.to(camera.position, { x: pos[0], y: pos[1], z: pos[2], duration: D_CAM, ease: 'power3.inOut' }, 0)
    tl.to(tgt.current, { x: target[0], y: target[1], z: target[2], duration: D_CAM, ease: 'power3.inOut',
      onUpdate: () => { camera.lookAt(tgt.current); ctl.current?.target.copy(tgt.current) } }, 0)
    return () => { tl.kill() }
  }, [pos.join(), target.join()])
  return <OrbitCtl ref={ctl} free={free} />
}
const OrbitCtl = forwardRef<any, { free: boolean }>(({ free }, ref) =>
  <OrbitControls ref={ref} enabled={free} enableDamping makeDefault minDistance={60} maxDistance={4000} maxPolarAngle={Math.PI / 2 - 0.1} />)
