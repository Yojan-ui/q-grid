// Clay architectural model of the campus (OpenStreetMap footprints from the replay), with energy ribbons,
// batteries, diesel sets and the water tank. Every flow, level and state is read from the replay run.
import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'
import gsap from 'gsap'
import { Label3D } from './Label3D'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import type { Run, Scenario } from '../lib/data'
import { reducedMotion, signed, useC } from '../lib/theme'
import { zn } from '../lib/labels'

// schematic grid connection point west of the campus (not a surveyed location)
export const SUBSTATION = new THREE.Vector3(-385, 0, 40)
const at = (arr: number[], t: number) => arr[Math.max(0, Math.min(Math.floor(t), arr.length - 1))] ?? 0

function inPoly(x: number, y: number, poly: [number, number][]) {
  let c = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i], [xj, yj] = poly[j]
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c
  }
  return c
}

export type ZoneGeo = { name: string; geo: THREE.BufferGeometry | null; h: number; panels: THREE.Matrix4[]; pos: THREE.Vector3 }

/** Merged extruded footprints per zone, plus rooftop PV tile placements sized from the zone's kWp. */
export function useZoneGeo(sc: Scenario): ZoneGeo[] {
  return useMemo(() => sc.campus.zones.map(z => {
    const geos: THREE.BufferGeometry[] = []
    const panels: THREE.Matrix4[] = []
    let maxH = 6
    const roof = z.buildings.reduce((a, b) => a + Math.abs(THREE.ShapeUtils.area(b.polygon.map(([x, y]) => new THREE.Vector2(x, y)))), 0)
    for (const b of z.buildings) {
      if (b.polygon.length < 3) continue
      const h = Math.max(1, b.levels) * 3.6
      maxH = Math.max(maxH, h)
      const shape = new THREE.Shape(b.polygon.map(([x, y]) => new THREE.Vector2(x, y)))
      const g = new THREE.ExtrudeGeometry(shape, { depth: h, bevelEnabled: true, bevelThickness: 0.3, bevelSize: 0.3, bevelSegments: 1 })
      g.rotateX(-Math.PI / 2)
      geos.push(g)
      // tiles per roof = kWp / 0.18 kWp per m2 (config ASSUMPTION) / 4 m2 per drawn tile
      const area = Math.abs(THREE.ShapeUtils.area(shape.getPoints()))
      const target = (z.pv_kwp / 0.18) * (area / Math.max(roof, 1)) / 4
      const xs = b.polygon.map(q => q[0]), ys = b.polygon.map(q => q[1])
      let placed = 0
      for (let y = Math.min(...ys) + 2; y < Math.max(...ys) - 1 && placed < target; y += 2.1)
        for (let x = Math.min(...xs) + 2; x < Math.max(...xs) - 1.5 && placed < target; x += 3.6)
          if (inPoly(x, y, b.polygon) && inPoly(x + 1.5, y + 0.7, b.polygon) && inPoly(x - 1.5, y - 0.7, b.polygon)) {
            panels.push(new THREE.Matrix4().compose(new THREE.Vector3(x, h + 0.75, -y),
              new THREE.Quaternion().setFromEuler(new THREE.Euler(-0.16, 0, 0)), new THREE.Vector3(3.1, 0.1, 1.2)))
            placed++
          }
    }
    return { name: z.name, geo: geos.length ? mergeGeometries(geos, false) : null, h: maxH, panels, pos: new THREE.Vector3(z.cx, 0, -z.cy) }
  }), [sc])
}

function dashTexture() {
  const c = document.createElement('canvas'); c.width = 64; c.height = 4
  const g = c.getContext('2d')!
  g.fillStyle = '#ffffff'; g.fillRect(0, 0, 30, 4)
  const t = new THREE.CanvasTexture(c)
  t.wrapS = t.wrapT = THREE.RepeatWrapping
  return t
}

/** A flat ribbon a -> b lying just above the ground: width ~ kW, dashes move in the flow direction. */
export function Ribbon({ a, b, kw, color, max = 300, y = 0.6 }: { a: THREE.Vector3; b: THREE.Vector3; kw: number; color: string; max?: number; y?: number }) {
  const { len, mid, rot, tex } = useMemo(() => {
    const d = new THREE.Vector3().subVectors(b, a)
    const tex = dashTexture()
    tex.repeat.set(Math.max(1, d.length() / 10), 1)
    return { len: d.length(), mid: new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5).setY(y), rot: Math.atan2(-d.z, d.x), tex }
  }, [a.x, a.z, b.x, b.z, y])
  const mag = Math.min(1, Math.abs(kw) / max)
  useFrame((_, dt) => { if (!reducedMotion()) tex.offset.x -= Math.sign(kw) * dt * (0.25 + 0.9 * mag) })
  if (Math.abs(kw) < 1) return null
  const w = 1.6 + 5.5 * mag
  return (
    <group position={mid} rotation={[0, rot, 0]}>
      <mesh rotation-x={-Math.PI / 2} scale={[len, w, 1]}>
        <planeGeometry /><meshBasicMaterial color={color} transparent opacity={0.22} depthWrite={false} toneMapped={false} />
      </mesh>
      <mesh rotation-x={-Math.PI / 2} position-y={0.05} scale={[len, w * 0.42, 1]}>
        <planeGeometry /><meshBasicMaterial color={color} map={tex} transparent alphaTest={0.5} toneMapped={false} />
      </mesh>
    </group>
  )
}

/** A plain flat strip a -> b (cables, ADMM line state). */
export function Strip({ a, b, color, w = 1.2, y = 0.3, opacity = 1 }: { a: THREE.Vector3; b: THREE.Vector3; color: string; w?: number; y?: number; opacity?: number }) {
  const d = new THREE.Vector3().subVectors(b, a)
  const mid = new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5).setY(y)
  return (
    <mesh position={mid} rotation={[-Math.PI / 2, 0, Math.atan2(-d.z, d.x)]} scale={[d.length(), w, 1]}>
      <planeGeometry /><meshBasicMaterial color={color} transparent={opacity < 1} opacity={opacity} toneMapped={false} />
    </mesh>
  )
}

/** Rooftop PV. At night (dark theme) the panels are deep blue and glow faintly only while the replay shows them producing. */
function Panels({ mats, opacity, glow = 0 }: { mats: THREE.Matrix4[]; opacity: number; glow?: number }) {
  const C = useC()
  const ref = useRef<THREE.InstancedMesh>(null!)
  useEffect(() => { mats.forEach((m, i) => ref.current.setMatrixAt(i, m)); ref.current.instanceMatrix.needsUpdate = true }, [mats])
  return (
    <instancedMesh ref={ref} args={[undefined, undefined, mats.length]} castShadow>
      <boxGeometry />
      <meshStandardMaterial color={C.pv} roughness={0.45} metalness={0.15} transparent={opacity < 1} opacity={opacity}
        emissive={C.pvGlow} emissiveIntensity={C.pvGlowMax * Math.max(0, Math.min(1, glow))} />
    </instancedMesh>
  )
}

/** Battery: a glass capsule with an amber fill at the state of charge. */
export function Battery({ soc, opacity = 1, scale = 1 }: { soc: number; opacity?: number; scale?: number }) {
  const C = useC()
  const fill = useRef<THREE.Mesh>(null!)
  const cur = useRef(soc)
  useFrame((_, dt) => {
    cur.current = reducedMotion() ? soc : THREE.MathUtils.damp(cur.current, soc, 6, dt)
    const l = Math.max(0.03, cur.current)
    fill.current.scale.y = l
    fill.current.position.y = 0.6 + 4.6 * l
  })
  return (
    <group scale={scale}>
      <mesh position-y={5.2} castShadow><cylinderGeometry args={[2.6, 2.6, 10.4, 24, 1, true]} />
        <meshStandardMaterial color={C.glass} transparent opacity={C.glassOpacity * opacity} roughness={0.2} side={THREE.DoubleSide} depthWrite={false} /></mesh>
      <mesh position-y={10.5}><cylinderGeometry args={[1.1, 1.1, 0.6, 16]} /><meshStandardMaterial color={C.faint} transparent opacity={opacity} /></mesh>
      <mesh ref={fill}><cylinderGeometry args={[2.25, 2.25, 9.2, 24]} />
        <meshStandardMaterial color={C.batteryFill} roughness={0.6} transparent={opacity < 1} opacity={opacity} /></mesh>
    </group>
  )
}

export function Tank({ level, opacity = 1 }: { level: number; opacity?: number }) {
  const C = useC()
  const ref = useRef<THREE.Mesh>(null!)
  const cur = useRef(level)
  useFrame((_, dt) => {
    cur.current = reducedMotion() ? level : THREE.MathUtils.damp(cur.current, level, 5, dt)
    const l = Math.max(0.03, Math.min(1, cur.current))
    ref.current.scale.y = l
    ref.current.position.y = 8 * l
  })
  return (
    <group>
      <mesh position-y={8}><cylinderGeometry args={[6.5, 6.5, 16, 32, 1, true]} />
        <meshStandardMaterial color={C.glass} transparent opacity={(C.glassOpacity + 0.05) * opacity} side={THREE.DoubleSide} depthWrite={false} /></mesh>
      <mesh ref={ref}><cylinderGeometry args={[6.1, 6.1, 16, 32]} /><meshStandardMaterial color={C.water} roughness={0.5} transparent={opacity < 1} opacity={opacity} /></mesh>
    </group>
  )
}

export type LineView = { color: string; ink?: string; label?: string; w?: number }

type Props = {
  sc: Scenario; t: number; run: 'qgrid' | 'status_quo'
  zones: ZoneGeo[]
  flows?: 'grid' | 'ties' | 'both' | 'none'
  lift?: Record<string, number>; liftStagger?: number
  focus?: string | null; dimOthers?: boolean
  killed?: string | null
  storage?: boolean
  labels?: 'none' | 'names' | 'net'
  lineViews?: LineView[] | null
  onZone?: (z: string | null) => void
  interactive?: boolean
  opacity?: number
  subLabel?: boolean
  batteryScale?: number
  socLabels?: boolean
}

export function Campus({ sc, t, run, zones, flows = 'both', lift = {}, liftStagger = 0, focus, dimOthers, killed, storage = true, labels = 'none',
  lineViews, onZone, interactive = false, opacity = 1, subLabel = true, batteryScale = 1, socLabels = false }: Props) {
  const C = useC()
  // the substation label opens to the right of its anchor; show it only while the anchor (and room for the
  // label) is inside the stage, so it never sits clipped at the stage edge
  const [subOnStage, setSubOnStage] = useState(true)
  const subPt = useMemo(() => SUBSTATION.clone().setY(16), [])
  const ndc = useMemo(() => new THREE.Vector3(), [])
  useFrame(({ camera }) => {
    ndc.copy(subPt).project(camera)
    const ok = ndc.z < 1 && ndc.x > -0.97 && ndc.x < 0.55 && ndc.y > -0.9 && ndc.y < 0.85
    if (ok !== subOnStage) setSubOnStage(ok)
  })
  const r: Run = (run === 'status_quo' ? sc.runs.status_quo : sc.runs.qgrid) ?? sc.runs.qgrid
  const slot = Math.max(0, Math.min(95, Math.floor(t)))
  const gridUp = sc.slots.grid_up[slot] === 1
  const [hover, setHover] = useState<string | null>(null)
  const groups = useRef<Record<string, THREE.Group | null>>({})
  const liftKey = zones.map(z => `${z.name}:${(lift[z.name] ?? 0) + (killed === z.name ? -40 : 0) + (hover === z.name ? 3 : 0)}`).join('|')
  useEffect(() => {
    zones.forEach((z, i) => {
      const g = groups.current[z.name]
      if (!g) return
      const y = (lift[z.name] ?? 0) + (killed === z.name ? -(z.h + 1) : 0) + (hover === z.name ? 3 : 0)
      gsap.killTweensOf(g.position)
      if (reducedMotion()) g.position.y = y
      else gsap.to(g.position, { y, duration: 0.7, ease: 'power3.inOut', delay: liftStagger * i })
    })
  }, [liftKey, liftStagger])

  const pos = (n: string, y = 0.6) => { const z = zones.find(q => q.name === n)!; return z.pos.clone().setY(y) }
  const tankZone = sc.campus.zones.find(z => z.tank_m3 > 0)
  const op = (n: string) => opacity * (killed === n ? 0.5 : dimOthers && focus && focus !== n ? 0.28 : 1)

  return (
    <group onPointerMissed={() => interactive && onZone?.(null)}>
      {zones.map((z, zi) => {
        const zone = sc.campus.zones[zi]
        const o = op(z.name)
        const off = killed === z.name
        return (
          <group key={z.name}>
            <group ref={g => { groups.current[z.name] = g }}>
              {z.geo && (
                <mesh geometry={z.geo} castShadow receiveShadow
                  onClick={interactive ? e => { e.stopPropagation(); onZone?.(z.name) } : undefined}
                  onPointerOver={interactive ? e => { e.stopPropagation(); setHover(z.name); document.body.style.cursor = 'pointer' } : undefined}
                  onPointerOut={interactive ? () => { setHover(h => (h === z.name ? null : h)); document.body.style.cursor = '' } : undefined}>
                  <meshStandardMaterial key={o < 1 ? 't' : 's'} color={off ? C.offline : C.clay} roughness={0.95} metalness={0}
                    transparent={o < 1} opacity={o} depthWrite={o >= 1} />
                </mesh>
              )}
              {z.panels.length > 0 && <Panels mats={z.panels} opacity={o} glow={off ? 0 : (sc.slots.pv_kw[zi]?.[slot] ?? 0) / Math.max(zone.pv_kwp, 1)} />}
              <Label3D show={labels !== 'none' || hover === z.name || focus === z.name} position={[z.pos.x, z.h + 8, z.pos.z]} center>
                <div className={`zlabel ${focus === z.name ? 'on' : ''} ${off ? 'off' : ''} ${labels === 'names' && !interactive ? 'sm' : ''}`}>
                  {zn(z.name)}{labels === 'net' && !off ? <span className="tn"> · {signed(r.net_kw[zi][slot])}</span> : null}
                </div>
              </Label3D>
            </group>
            {/* hidden rather than unmounted when storage is off: its <Html> label must not unmount mid-render */}
            {zone.battery_kwh > 0 && (
              <group position={[z.pos.x + 17, 0, z.pos.z + 12]} visible={storage}>
                <Battery soc={off ? 0 : r.soc[zi][Math.min(96, slot + 1)]} opacity={o} scale={batteryScale} />
                <Label3D show={storage && socLabels && !off} position={[0, 12 * batteryScale + 4, 0]} center>
                  <div className="soclabel tn">{Math.round(100 * r.soc[zi][Math.min(96, slot + 1)])}%</div>
                </Label3D>
              </group>
            )}
            {storage && zone.battery_kwh > 0 && !off && flows !== 'none' && (
              <Ribbon a={new THREE.Vector3(z.pos.x + 17, 0, z.pos.z + 12)} b={z.pos} kw={-r.p_bat[zi][slot]} color={C.battery} max={200} y={0.8} />
            )}
            {zone.dg_kw > 0 && (
              <group position={[z.pos.x - 18, 0, z.pos.z - 12]}>
                <mesh position-y={2.6} castShadow><boxGeometry args={[8, 5.2, 4.6]} />
                  <meshStandardMaterial color={r.dg_kw[zi][slot] > 0 && !off ? C.diesel : C.dieselIdle} roughness={0.9} transparent={o < 1} opacity={o} /></mesh>
                {r.dg_kw[zi][slot] > 0 && !off && flows !== 'none' &&
                  <Ribbon a={new THREE.Vector3(z.pos.x - 18, 0, z.pos.z - 12)} b={z.pos} kw={r.dg_kw[zi][slot]} color={C.diesel} max={300} y={0.9} />}
              </group>
            )}
          </group>
        )
      })}
      {tankZone && (
        <group position={[tankZone.cx, 0, -tankZone.cy]}>
          <Tank level={at(r.tank_m3[tankZone.name] ?? [0], t) / tankZone.tank_m3} opacity={op(tankZone.name)} />
        </group>
      )}
      {sc.campus.lines.map(([a, b], i) => {
        const dead = !!killed && (a === killed || b === killed)
        const v = lineViews?.[i]
        const pa = pos(a, 0.3), pb = pos(b, 0.3)
        return (
          <group key={i}>
            <Strip a={pa} b={pb} color={dead ? C.offline : v?.color ?? C.road} w={v?.w ?? 1} opacity={opacity} />
            {!dead && !v && (flows === 'ties' || flows === 'both') && <Ribbon a={pa} b={pb} kw={r.flows[i][slot]} color={C.solar} max={240} />}
            <Label3D show={!!v?.label && !dead} position={pa.clone().add(pb).multiplyScalar(0.5).setY(4)} center>
              <div className="linelabel tn" style={{ borderColor: v?.color, color: v?.ink ?? v?.color }}>{v?.label ?? ''}</div>
            </Label3D>
          </group>
        )
      })}
      <group position={SUBSTATION}>
        <mesh position-y={4} castShadow receiveShadow><boxGeometry args={[18, 8, 14]} />
          <meshStandardMaterial color={gridUp ? C.substation : C.substationDown} roughness={0.9} transparent={opacity < 1} opacity={opacity} /></mesh>
        <mesh position={[0, 8.2, 0]}><boxGeometry args={[18.4, 0.5, 14.4]} /><meshStandardMaterial color={gridUp ? C.grid : C.offline} transparent={opacity < 1} opacity={opacity} /></mesh>
        {/* anchored at its left end and opening towards the campus, so it never runs off the stage's left edge */}
        <Label3D show={subLabel && subOnStage} position={[-6, 16, 0]} style={{ transform: 'translateY(-50%)' }}>
          <div className={`zlabel sub ${gridUp ? '' : 'off'}`}>BESCOM substation{gridUp ? '' : ' · outage'}</div>
        </Label3D>
      </group>
      {(flows === 'grid' || flows === 'both') && gridUp && sc.campus.zones.map((z, i) => {
        if (killed === z.name) return null
        const net = r.net_kw[i][slot]
        return <Ribbon key={`g${z.name}`} a={SUBSTATION.clone().setY(0.4)} b={pos(z.name, 0.4)} kw={net} color={net > 0 ? C.grid : C.solar} max={500} y={0.4} />
      })}
    </group>
  )
}

/** Soft daylight that follows the sun's real azimuth / elevation for the slot (NASA POWER geometry). */
export function Sun({ sc, t }: { sc: Scenario; t: number }) {
  const C = useC()
  const el = at(sc.slots.sun.elevation_deg, t), az = at(sc.slots.sun.azimuth_deg, t)
  const day = THREE.MathUtils.clamp((el + 2) / 30, 0, 1)
  const light = useRef<THREE.DirectionalLight>(null!)
  const target = useMemo(() => new THREE.Object3D(), [])
  useFrame((_, dt) => {
    const e = THREE.MathUtils.degToRad(Math.max(el, 12)), a = THREE.MathUtils.degToRad(az)
    const p = new THREE.Vector3(Math.sin(a) * Math.cos(e), Math.sin(e), -Math.cos(a) * Math.cos(e)).multiplyScalar(600)
    if (reducedMotion()) light.current.position.copy(p)
    else light.current.position.lerp(p, 1 - Math.exp(-dt * 4))
    // physically based lights: intensity ~ pi gives full albedo; hemisphere keeps the model bright at any hour
    // dark theme: the same sun path, but a cool moonlight key with low ambient so the model reads as a campus at night
    light.current.intensity = THREE.MathUtils.damp(light.current.intensity, C.keyBase + C.keyGain * day, 4, dt)
  })
  return (
    <>
      <hemisphereLight args={[C.hemiSky, C.hemiGround, C.hemiI]} />
      <primitive object={target} />
      <directionalLight ref={light} castShadow target={target} color={day > 0.25 ? C.keyDay : C.keyNight} intensity={2.2}
        shadow-mapSize={[2048, 2048]} shadow-bias={-0.0004} shadow-normalBias={0.6} shadow-radius={C.shadowRadius} shadow-intensity={C.shadowI}
        shadow-camera-left={-460} shadow-camera-right={460} shadow-camera-top={360} shadow-camera-bottom={-360} shadow-camera-near={10} shadow-camera-far={1500} />
    </>
  )
}

export function Ground({ sc, opacity = 1, outline: showOutline = true }: { sc: Scenario; opacity?: number; outline?: boolean }) {
  const C = useC()
  const outline = useMemo(() => {
    if (!sc.campus.outline) return null
    return new THREE.Shape(sc.campus.outline.map(([x, y]) => new THREE.Vector2(x, y)))
  }, [sc])
  const roads = (sc.campus as any).roads as [number, number][][] | undefined
  return (
    <group>
      <mesh rotation-x={-Math.PI / 2} position-y={-0.1} receiveShadow>
        <planeGeometry args={[5000, 5000]} /><meshStandardMaterial color={C.ground} roughness={1} />
      </mesh>
      {outline && showOutline && (
        <mesh rotation-x={-Math.PI / 2} position-y={0.02} receiveShadow>
          <shapeGeometry args={[outline]} /><meshStandardMaterial color={C.plot} roughness={1} transparent={opacity < 1} opacity={opacity} />
        </mesh>
      )}
      {roads?.map((rd, i) => <RoadLine key={i} pts={rd} color={C.road} />)}
    </group>
  )
}

function RoadLine({ pts, color }: { pts: [number, number][]; color: string }) {
  const obj = useMemo(() => {
    const g = new THREE.BufferGeometry().setFromPoints(pts.map(([x, y]) => new THREE.Vector3(x, 0.08, -y)))
    return new THREE.Line(g, new THREE.LineBasicMaterial({ color }))
  }, [pts, color])
  return <primitive object={obj} />
}
