import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useFrame, useThree } from '@react-three/fiber'
import { Edges } from '@react-three/drei'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import type { Run, Scenario } from '../lib/data'
import { C } from '../lib/theme'
import { Seg } from './Seg'

export const COLORS = C

export type Anchors = { pts: Record<string, { x: number; y: number; vis: boolean }>; dist: number; w: number; h: number }

type Props = {
  sc: Scenario; t: number; run: 'qgrid' | 'status_quo'; killed?: string | null; focus?: string | null
  onZone?: (z: string | null) => void; anchors?: React.MutableRefObject<Anchors>
}

const at = (arr: number[], t: number) => arr[Math.min(Math.floor(t), arr.length - 1)]
const xz = (x: number, y: number) => new THREE.Vector3(x, 0, -y)

function inPoly(x: number, y: number, poly: [number, number][]) {
  let c = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j]
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c
  }
  return c
}

/** Per-zone merged clay geometry with baked base darkening (fake ambient occlusion) and PV panel placements. */
function useZones(sc: Scenario) {
  return useMemo(() => sc.campus.zones.map(z => {
    const geos: THREE.BufferGeometry[] = []
    const panels: THREE.Matrix4[] = []
    let maxH = 6
    const roof = z.buildings.reduce((a, b) => a + Math.abs(THREE.ShapeUtils.area(b.polygon.map(([x, y]) => new THREE.Vector2(x, y)))), 0)
    const tileArea = 4.0  // m2 per drawn tile; tiles per roof = kWp / 0.18 kWp per m2 (config ASSUMPTION) / tileArea
    for (const b of z.buildings) {
      if (b.polygon.length < 3) continue
      const h = Math.max(1, b.levels) * 3.6
      maxH = Math.max(maxH, h)
      const shape = new THREE.Shape(b.polygon.map(([x, y]) => new THREE.Vector2(x, y)))
      const g = new THREE.ExtrudeGeometry(shape, { depth: h, bevelEnabled: true, bevelThickness: 0.35, bevelSize: 0.35, bevelSegments: 1 })
      g.rotateX(-Math.PI / 2)
      const p = g.attributes.position, col = new Float32Array(p.count * 3)
      for (let i = 0; i < p.count; i++) {
        const k = 0.55 + 0.45 * THREE.MathUtils.smoothstep(p.getY(i), 0, 7)   // darker towards the ground
        col[i * 3] = col[i * 3 + 1] = col[i * 3 + 2] = k
      }
      g.setAttribute('color', new THREE.BufferAttribute(col, 3))
      geos.push(g)
      const area = Math.abs(THREE.ShapeUtils.area(shape.getPoints()))
      const target = (z.pv_kwp / 0.18) * (area / Math.max(roof, 1)) / tileArea
      const xs = b.polygon.map(q => q[0]), ys = b.polygon.map(q => q[1])
      let placed = 0
      for (let y = Math.min(...ys) + 2; y < Math.max(...ys) - 1 && placed < target; y += 2.1)
        for (let x = Math.min(...xs) + 2; x < Math.max(...xs) - 1.5 && placed < target; x += 3.6)
          if (inPoly(x, y, b.polygon) && inPoly(x + 1.5, y + 0.7, b.polygon) && inPoly(x - 1.5, y - 0.7, b.polygon)) {
            panels.push(new THREE.Matrix4().compose(new THREE.Vector3(x, h + 0.9, -y),
              new THREE.Quaternion().setFromEuler(new THREE.Euler(-0.18, 0, 0)), new THREE.Vector3(3.2, 0.12, 1.25)))
            placed++
          }
    }
    return { zone: z, geo: geos.length ? mergeGeometries(geos, false) : null, h: maxH, panels }
  }), [sc])
}

function dashTexture() {
  const c = document.createElement('canvas'); c.width = 4; c.height = 64
  const g = c.getContext('2d')!
  g.fillStyle = '#ffffff'; g.fillRect(0, 0, 4, 34)
  const t = new THREE.CanvasTexture(c)
  t.wrapS = t.wrapT = THREE.RepeatWrapping
  return t
}

const Y = new THREE.Vector3(0, 1, 0)

/** A flow ribbon between two points: width ~ kW, dashes move in the flow direction at a speed ~ kW. */
function Ribbon({ a, b, kw, color, max = 300 }: { a: THREE.Vector3; b: THREE.Vector3; kw: number; color: string; max?: number }) {
  const { len, mid, quat, tex } = useMemo(() => {
    const d = new THREE.Vector3().subVectors(b, a)
    const len = d.length()
    const tex = dashTexture()
    tex.repeat.set(1, Math.max(1, len / 9))
    return { len, mid: new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5), quat: new THREE.Quaternion().setFromUnitVectors(Y, d.normalize()), tex }
  }, [a.x, a.y, a.z, b.x, b.y, b.z])
  const mag = Math.min(1, Math.abs(kw) / max)
  useFrame((_, dt) => { tex.offset.y -= Math.sign(kw) * dt * (0.4 + 2.2 * mag) })
  if (Math.abs(kw) < 1) return null
  const w = 0.5 + 2.6 * mag
  return (
    <mesh position={mid} quaternion={quat} scale={[w, len, w]}>
      <cylinderGeometry args={[1, 1, 1, 10, 1, true]} />
      <meshBasicMaterial map={tex} color={color} transparent alphaTest={0.4} toneMapped={false} side={THREE.DoubleSide} />
    </mesh>
  )
}

function Smoke({ on }: { on: boolean }) {
  const ref = useRef<THREE.InstancedMesh>(null!)
  const m = useMemo(() => new THREE.Matrix4(), [])
  const N = 18
  useFrame(({ clock }) => {
    for (let i = 0; i < N; i++) {
      const f = (clock.elapsedTime * 0.22 + i / N) % 1
      const s = on ? 1.4 + f * 4 : 0
      m.makeScale(s, s, s).setPosition(Math.sin(i * 7.1) * 2 * f, 9 + f * 26, Math.cos(i * 3.3) * 2 * f)
      ref.current.setMatrixAt(i, m)
    }
    ref.current.instanceMatrix.needsUpdate = true
  })
  return (
    <instancedMesh ref={ref} args={[undefined, undefined, N]} frustumCulled={false}>
      <sphereGeometry args={[1, 8, 8]} />
      <meshBasicMaterial color={C.offline} transparent opacity={0.45} depthWrite={false} />
    </instancedMesh>
  )
}

/** Projects zone anchors to screen space for the HTML label layer (outside the canvas). */
function AnchorTracker({ sc, zh, anchors }: { sc: Scenario; zh: Record<string, number>; anchors: React.MutableRefObject<Anchors> }) {
  const { camera, size } = useThree()
  const v = useMemo(() => new THREE.Vector3(), [])
  useFrame(() => {
    const pts: Anchors['pts'] = {}
    for (const z of sc.campus.zones) {
      v.set(z.cx, (zh[z.name] ?? 8) + 2, -z.cy).project(camera)
      pts[z.name] = { x: (v.x * 0.5 + 0.5) * size.width, y: (-v.y * 0.5 + 0.5) * size.height, vis: v.z < 1 }
    }
    anchors.current = { pts, dist: camera.position.length(), w: size.width, h: size.height }
  })
  return null
}

export const SUBSTATION = new THREE.Vector3(-250, 0, 40)

export function CampusScene({ sc, t, run, killed, focus, onZone, anchors }: Props) {
  const zones = useZones(sc)
  const r: Run = (run === 'status_quo' ? sc.runs.status_quo : sc.runs.qgrid) ?? sc.runs.qgrid
  const slot = Math.min(95, Math.floor(t))
  const gridUp = sc.slots.grid_up[slot] === 1
  const el = at(sc.slots.sun.elevation_deg, t), az = at(sc.slots.sun.azimuth_deg, t)
  const day = THREE.MathUtils.clamp((el + 4) / 26, 0, 1)
  const clay = useMemo(() => new THREE.Color(C.clayNight).lerp(new THREE.Color(C.clayDay), day), [day])
  const key = useMemo(() => {
    const e = THREE.MathUtils.degToRad(Math.max(el, 6)), a = THREE.MathUtils.degToRad(az)
    return new THREE.Vector3(Math.sin(a) * Math.cos(e), Math.sin(e), -Math.cos(a) * Math.cos(e)).multiplyScalar(500)
  }, [el, az])
  const keyCol = useMemo(() => new THREE.Color(C.text).lerp(new THREE.Color(C.battery), 0.35 * (1 - day)), [day])
  const anchorH = useMemo(() => Object.fromEntries(zones.map(z => [z.zone.name, z.h])), [zones])
  const posCache = useMemo(() => Object.fromEntries(sc.campus.zones.map(z => [z.name, [z.cx, -z.cy]])), [sc])
  const pos = (n: string, y = 1.5) => new THREE.Vector3(posCache[n][0], y, posCache[n][1])
  const sel = focus ?? null
  const tank = sc.campus.zones.find(z => z.tank_m3 > 0)
  const ti = tank ? sc.campus.zones.indexOf(tank) : -1
  return (
    <group onPointerMissed={() => onZone?.(null)}>
      <color attach="background" args={[C.bg]} />
      <hemisphereLight args={[C.muted, C.bg, 0.9 + 0.3 * (1 - day)]} />
      <ambientLight intensity={0.35} color={C.text} />
      <directionalLight position={key} intensity={0.6 + 1.4 * day} color={keyCol} />
      <mesh rotation-x={-Math.PI / 2} position-y={-0.05}>
        <planeGeometry args={[2400, 2400]} />
        <meshStandardMaterial color={C.bg} roughness={1} />
      </mesh>
      {sc.campus.outline && <Seg points={sc.campus.outline.map(([x, y]) => xz(x, y).setY(0.15))} color={C.road} />}
      {(sc.campus as any).roads?.map((rd: [number, number][], i: number) => <Seg key={i} points={rd.map(([x, y]) => xz(x, y).setY(0.1))} color={C.road} />)}
      {zones.map(({ zone, geo, panels }, zi) => {
        const off = killed === zone.name
        const dim = !!sel && sel !== zone.name
        const pv = sc.slots.pv_kw[zi][slot] / Math.max(zone.pv_kwp, 1)
        const soc = r.soc[zi][Math.min(96, slot + 1)]
        const p = r.p_bat[zi][slot]
        const cap = new THREE.Vector3(zone.cx + 16, 0, -zone.cy + 12)
        return (
          <group key={zone.name}>
            {geo && (
              <mesh geometry={geo} onClick={e => { e.stopPropagation(); onZone?.(zone.name) }}>
                <meshStandardMaterial key={dim ? 'dim' : 'solid'} vertexColors color={off ? C.offline : clay} roughness={0.92} metalness={0}
                  emissive={off ? C.offline : clay} emissiveIntensity={0.06 + 0.32 * (1 - day)} transparent={dim} opacity={dim ? 0.4 : 1} depthWrite={!dim} />
                {sel === zone.name && <Edges threshold={30} color={C.text} />}
              </mesh>
            )}
            {panels.length > 0 && <Panels mats={panels} glow={off ? 0 : pv} dim={dim} />}
            {zone.battery_kwh > 0 && (
              <group position={cap}>
                <mesh position-y={5}><capsuleGeometry args={[2.2, 6, 6, 12]} /><meshStandardMaterial color={C.border} transparent opacity={0.6} /></mesh>
                <mesh position-y={1.9 + 3.2 * soc} scale={[1, Math.max(0.05, soc), 1]}>
                  <capsuleGeometry args={[1.8, 6, 6, 12]} />
                  <meshStandardMaterial color={C.battery} emissive={C.battery} emissiveIntensity={0.25 + 0.9 * soc} />
                </mesh>
              </group>
            )}
            {zone.battery_kwh > 0 && !off && <Ribbon a={cap.clone().setY(2)} b={pos(zone.name, 2)} kw={-p} color={C.battery} max={200} />}
            {zone.dg_kw > 0 && (
              <group position={[zone.cx - 18, 0, -zone.cy - 10]}>
                <mesh position-y={2.5}><boxGeometry args={[7, 5, 4]} /><meshStandardMaterial color={C.offline} roughness={0.9} /></mesh>
                <Smoke on={!off && r.dg_kw[zi][slot] > 0} />
              </group>
            )}
          </group>
        )
      })}
      {tank && (
        <group position={[tank.cx, 0, -tank.cy]}>
          <mesh position-y={9}><cylinderGeometry args={[7, 7, 18, 32, 1, true]} /><meshStandardMaterial color={C.muted} transparent opacity={0.22} side={THREE.DoubleSide} /></mesh>
          <Tank level={at(r.tank_m3[tank.name] ?? [0], t) / tank.tank_m3} pumping={r.pump_on[ti][slot] === 1} />
        </group>
      )}
      {sc.campus.lines.map(([a, b], i) => {
        const dead = !!killed && (a === killed || b === killed)
        return (
          <group key={i}>
            <Seg points={[pos(a, 0.6), pos(b, 0.6)]} color={dead ? C.offline : C.road} />
            {!dead && <Ribbon a={pos(a)} b={pos(b)} kw={r.flows[i][slot]} color={C.solar} />}
          </group>
        )
      })}
      <mesh position={SUBSTATION.clone().setY(5)}>
        <boxGeometry args={[14, 10, 14]} />
        <meshStandardMaterial color={gridUp ? C.border : C.bg} emissive={C.grid} emissiveIntensity={gridUp ? 0.12 : 0} />
      </mesh>
      {sc.campus.zones.map((z, i) => {
        const net = r.net_kw[i][slot]
        return (
          <group key={`f${z.name}`}>
            <Seg points={[SUBSTATION.clone().setY(0.4), pos(z.name, 0.4)]} color={gridUp ? C.road : C.bg} />
            {gridUp && <Ribbon a={SUBSTATION.clone().setY(1.2)} b={pos(z.name, 1.2)} kw={net} color={net > 0 ? C.grid : C.solar} max={600} />}
          </group>
        )
      })}
      {anchors && <AnchorTracker sc={sc} zh={anchorH} anchors={anchors} />}
    </group>
  )
}

const PANEL = new THREE.Color(C.bg).lerp(new THREE.Color(C.water), 0.35)   // dark blue tile, lit by live PV output

function Panels({ mats, glow, dim }: { mats: THREE.Matrix4[]; glow: number; dim: boolean }) {
  const ref = useRef<THREE.InstancedMesh>(null!)
  const done = useRef<THREE.Matrix4[] | null>(null)
  useFrame(() => {
    if (done.current === mats || !ref.current) return
    mats.forEach((m, i) => ref.current.setMatrixAt(i, m))
    ref.current.instanceMatrix.needsUpdate = true
    done.current = mats
  })
  return (
    <instancedMesh ref={ref} args={[undefined, undefined, mats.length]}>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial key={dim ? 'dim' : 'solid'} color={PANEL} roughness={0.5} metalness={0.1} emissive={C.water} emissiveIntensity={0.02 + 0.5 * glow}
        transparent={dim} opacity={dim ? 0.4 : 1} depthWrite={!dim} />
    </instancedMesh>
  )
}

function Tank({ level, pumping }: { level: number; pumping: boolean }) {
  const ref = useRef<THREE.Mesh>(null!)
  const cur = useRef(level)
  useFrame((_, dt) => {
    cur.current += (level - cur.current) * Math.min(1, dt * 3)
    const l = Math.max(0.02, cur.current)
    ref.current.scale.y = l
    ref.current.position.y = 9 * l
  })
  return (
    <mesh ref={ref}>
      <cylinderGeometry args={[6.6, 6.6, 18, 32]} />
      <meshStandardMaterial color={C.water} emissive={C.water} emissiveIntensity={pumping ? 0.55 : 0.15} />
    </mesh>
  )
}
