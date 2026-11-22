// One continuous 3D thread for the whole story: the camera and the objects move between stops; nothing cuts.
import { useEffect, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { Canvas, useThree } from '@react-three/fiber'
import { RoundedBox } from '@react-three/drei'
import { Label3D } from './Label3D'
import gsap from 'gsap'
import type { Scenario } from '../lib/data'
import { C, reducedMotion } from '../lib/theme'
import { devices } from '../lib/labels'
import type { StopId, StoryData } from '../lib/story'
import { Battery, Campus, Ground, Sun, Tank, useZoneGeo, type LineView, type ZoneGeo } from './Campus'
import { Lab } from './Lab'

type V3 = [number, number, number]
const YAW = 0.62
const rotY = (v: V3, a = YAW): V3 => [v[0] * Math.cos(a) + v[2] * Math.sin(a), v[1], -v[0] * Math.sin(a) + v[2] * Math.cos(a)]
const add = (a: V3, b: V3): V3 => [a[0] + b[0], a[1] + b[1], a[2] + b[2]]

function CameraRig({ pos, target, fov = 38 }: { pos: V3; target: V3; fov?: number }) {
  const { camera } = useThree()
  const tgt = useRef(new THREE.Vector3(...target))
  const first = useRef(true)
  useEffect(() => {
    const cam = camera as THREE.PerspectiveCamera
    const d = reducedMotion() || first.current ? 0 : 1.1
    first.current = false
    gsap.killTweensOf(cam.position); gsap.killTweensOf(tgt.current); gsap.killTweensOf(cam)
    const look = () => cam.lookAt(tgt.current)
    gsap.to(cam.position, { x: pos[0], y: pos[1], z: pos[2], duration: d, ease: 'power3.inOut', onUpdate: look })
    gsap.to(tgt.current, { x: target[0], y: target[1], z: target[2], duration: d, ease: 'power3.inOut', onUpdate: look, onComplete: look })
    gsap.to(cam, { fov, duration: d, ease: 'power2.inOut', onUpdate: () => cam.updateProjectionMatrix() })
    if (d === 0) { cam.position.set(...pos); tgt.current.set(...target); cam.fov = fov; cam.updateProjectionMatrix(); look() }
  }, [pos.join(), target.join(), fov])
  return null
}

export type StageProps = {
  stop: StopId; d: StoryData; t: number
  zone: string | null; onZone: (z: string | null) => void
  killed: string | null; admmRound: number; pulseKey: number
  showMiss: boolean
}

export function Stage(p: StageProps) {
  return (
    <Canvas shadows="percentage" flat camera={{ position: [380, 360, 520], fov: 38, near: 2, far: 9000 }} dpr={[1, 1.75]}
      gl={{ antialias: true, preserveDrawingBuffer: true }} onPointerMissed={() => p.stop === '2' && p.onZone(null)}>
      <color attach="background" args={[C.bg]} />
      <fog attach="fog" args={[C.bg, p.stop === '7b' ? 3200 : 1300, p.stop === '7b' ? 8000 : 3200]} />
      <Scene {...p} />
    </Canvas>
  )
}

function Scene({ stop, d, t, zone, onZone, killed, admmRound, pulseKey }: StageProps) {
  const { sc, example } = d
  const zones = useZoneGeo(sc)
  const ex = example
  const exZone = zones.find(z => z.name === ex.zone)!
  const A: V3 = [exZone.pos.x, 0, exZone.pos.z]
  const labStops: StopId[] = ['3', '4a', '4b', '4c', '4d', '4e']

  const cam = useMemo((): { pos: V3; target: V3; fov?: number } => {
    const zg = zone ? zones.find(z => z.name === zone) : null
    switch (stop) {
      case '1': return { pos: [280, 430, 720], target: [-70, 0, 70] }
      case '2': return zg ? { pos: [zg.pos.x + 130, 170, zg.pos.z + 200], target: [zg.pos.x, 22, zg.pos.z] } : { pos: [300, 440, 620], target: [-20, 0, 0] }
      case '3': return { pos: add(A, rotY([0, 74, 104])), target: add(A, rotY([0, 50, 0])) }
      case '4a': case '4b': return { pos: add(A, rotY([0, 62, 104])), target: add(A, rotY([0, 50, 0])) }
      case '4c': return { pos: add(A, rotY([0, 60, 100])), target: add(A, rotY([0, 50, 0])) }
      case '4d': return { pos: add(A, rotY([0, 60, 100])), target: add(A, rotY([0, 47, 0])) }
      case '4e': return { pos: add(A, rotY([0, 76, 116])), target: add(A, rotY([0, 40, 0])) }
      case '4f': return { pos: add(A, rotY([50, 90, 180])), target: add(A, [0, 8, 0]) }
      case '4g': return { pos: [380, 600, 820], target: [-60, 0, 0] }
      case '5': case '5b': return { pos: [-20, 1120, 170], target: [-20, 0, 0] }
      case '6': return { pos: [150, 250, 400], target: [-40, 0, 0] }
      case '7a': return { pos: [0, 760, 1060], target: [0, 0, 60] }
      case '7b': return { pos: [0, 1450, 1750], target: [0, 0, 60], fov: 36 }
    }
  }, [stop, zone, zones])

  // ADMM overlay (step 5): each cable shows both ends' proposals for the chosen round
  const lineViews = useMemo((): LineView[] | null => {
    if (stop !== '5') return null
    const rounds = d.admmRounds
    const r = rounds[Math.min(admmRound, rounds.length - 1)]
    if (!r) return null
    // label only the three largest disagreements so the numbers stay readable; colour shows every cable
    const gaps = sc.campus.lines.map((_, i) => { const [a, b] = r.proposals[String(i)] ?? [0, 0]; return Math.abs(a - b) })
    const top = new Set(gaps.map((g, i) => [g, i]).filter(([g]) => g >= 1).sort((x, y) => y[0] - x[0]).slice(0, 3).map(([, i]) => i))
    return sc.campus.lines.map((_, i) => {
      const [a, b] = r.proposals[String(i)] ?? [0, 0]
      const ok = Math.abs(a - b) < 1
      return { color: ok ? C.accent : C.grid, w: ok ? 3.2 : 1.6, label: ok || !top.has(i) ? undefined : `${Math.round(a)} ≠ ${Math.round(b)}` }
    })
  }, [stop, admmRound, d.admmRounds, sc])

  // primary campus: splits right for the side-by-side result (7a/7b)
  const primary = useRef<THREE.Group>(null!)
  const secondary = useRef<THREE.Group>(null!)
  useEffect(() => {
    const duo = stop === '7a'
    const D = reducedMotion() ? 0 : 1.0
    gsap.to(primary.current.position, { x: duo ? 235 : 0, duration: D, ease: 'power3.inOut' })
    gsap.to(primary.current.scale, { x: duo ? 0.6 : 1, y: duo ? 0.6 : 1, z: duo ? 0.6 : 1, duration: D, ease: 'power3.inOut' })
    gsap.to(secondary.current.position, { x: duo ? -235 : 0, duration: D, ease: 'power3.inOut' })
    gsap.to(secondary.current.scale, { x: duo ? 0.6 : 0.001, y: duo ? 0.6 : 0.001, z: duo ? 0.6 : 0.001, duration: D, ease: 'power3.inOut' })
  }, [stop])

  const slot = Math.min(95, Math.floor(t))
  const run = stop === '1' ? 'status_quo' : 'qgrid'
  const inLab = labStops.includes(stop)
  const flows = stop === '1' ? 'both' : stop === '2' ? 'none' : inLab ? (stop === '4e' ? 'ties' : 'none') : stop === '5' ? 'none' : 'both'
  const lift: Record<string, number> = {}
  if (stop === '2') zones.forEach(z => { lift[z.name] = z.name === zone ? 6 : 3 })
  const dim = inLab || stop === '4f' || (stop === '2' && !!zone)
  const focus = inLab || stop === '4f' ? ex.zone : stop === '2' ? zone : null

  return (
    <>
      <CameraRig {...cam} />
      <Sun sc={sc} t={t} />
      <Ground sc={sc} outline={stop !== '7a'} />
      <group ref={primary}>
        <Campus sc={sc} t={t} run={run} zones={zones} flows={flows} lift={lift} liftStagger={stop === '2' ? 0.07 : 0}
          focus={focus} dimOthers={dim} killed={stop === '5' ? killed : null} labels={stop === '2' && !zone ? 'names' : 'none'}
          lineViews={lineViews} onZone={onZone} interactive={stop === '2'} storage={stop !== '5'}
          subLabel={stop !== '7a' && stop !== '7b' && stop !== '4g'} batteryScale={stop === '6' ? 1.7 : 1} socLabels={stop === '6'} />
        {zones.map(z => <DeviceIcons key={z.name} sc={sc} z={z} slot={slot} show={stop === '2' && zone === z.name} />)}
        <Label3D show={stop === '7a'} position={[0, 90, -300]} center><div className="duotag q">With Q-Grid</div></Label3D>
        <Label3D show={stop === '7b'} position={[0, 70, 0]} center><div className="duotag q">RVCE · {sc.campus.zones.length} zones</div></Label3D>
      </group>
      <group ref={secondary} scale={0.001}>
        <Campus sc={sc} t={t} run="status_quo" zones={zones} flows={stop === '7a' ? 'both' : 'none'} subLabel={false} />
        <Label3D show={stop === '7a'} position={[0, 90, -300]} center><div className="duotag">Status quo</div></Label3D>
      </group>
      <Lab stop={stop} ex={ex} sc={sc} anchor={new THREE.Vector3(...A)} yaw={YAW} buildingH={exZone.h} pulseKey={pulseKey} />
      <Label3D show={stop === '4f'} position={[A[0], exZone.h + 22, A[2]]} center>
        <div className={`verifytag ${ex.qaoa.best_bits === ex.exact.bits ? 'ok' : 'gap'}`}>
          {ex.qaoa.best_bits === ex.exact.bits ? '✓ QAOA plan = exact optimum' : '≠ exact optimum → fallback tier'}
        </div>
      </Label3D>
      <Cluster zones={zones} show={stop === '7b'} />
    </>
  )
}

/** Step 2: the selected zone's devices as small 3D icons above the building (from the campus model). */
function DeviceIcons({ sc, z, slot, show }: { sc: Scenario; z: ZoneGeo; slot: number; show: boolean }) {
  const zi = sc.campus.zones.findIndex(q => q.name === z.name)
  const zone = sc.campus.zones[zi]
  // one 3D icon per device type; the panel lists each flexible load with its power and run length
  const all = devices(zone, sc), flex = all.filter(x => x.key === 'flex')
  const list = [...all.filter(x => x.key !== 'flex'), ...(flex.length ? [{ key: 'flex' as const, label: flex.length > 1 ? `${flex.length} flexible loads` : flex[0].label, detail: flex.map(f => f.detail.split(',')[0]).join(' + ') }] : [])]
  const ref = useRef<(THREE.Group | null)[]>([])
  useEffect(() => {
    ref.current.forEach((g, i) => {
      if (!g) return
      gsap.killTweensOf(g.scale)
      if (show) g.scale.setScalar(0.001)
      const s = show ? 1 : 0.001
      gsap.to(g.scale, { x: s, y: s, z: s, duration: reducedMotion() ? 0 : show ? 0.6 : 0.3, ease: 'power3.out', delay: reducedMotion() || !show ? 0 : 0.2 + i * 0.06 })
    })
  }, [show])
  const w = 24
  const x0 = -((list.length - 1) * w) / 2
  const soc = sc.runs.qgrid.soc[zi]?.[slot + 1] ?? 0.5
  const tank = sc.runs.qgrid.tank_m3[z.name]?.[slot]
  return (
    <group position={[z.pos.x, z.h + 34, z.pos.z]} rotation-y={0.57} scale={1.5}>
      {list.map((dv, i) => (
        <group key={dv.key} position={[x0 + i * w, 0, 0]} ref={g => { ref.current[i] = g }} scale={0.001}>
          {dv.key === 'pv' && <mesh rotation-x={-0.5}><boxGeometry args={[8, 0.5, 5]} /><meshStandardMaterial color={C.pv} roughness={0.4} /></mesh>}
          {dv.key === 'battery' && <group position-y={-3}><Battery soc={soc} scale={0.6} /></group>}
          {dv.key === 'dg' && <mesh><boxGeometry args={[7, 4.5, 4]} /><meshStandardMaterial color={C.diesel} roughness={0.9} /></mesh>}
          {dv.key === 'tank' && <group position-y={-4} scale={0.5}><Tank level={(tank ?? 0) / Math.max(zone.tank_m3, 1)} /></group>}
          {dv.key === 'critical' && <RoundedBox args={[5, 5, 5]} radius={0.6}><meshStandardMaterial color="#FFFFFF" emissive={C.grid} emissiveIntensity={0.12} roughness={0.7} /></RoundedBox>}
          {dv.key === 'flex' && <RoundedBox args={[6, 3.6, 4]} radius={0.5}><meshStandardMaterial color="#FFFFFF" roughness={0.7} /></RoundedBox>}
          <Label3D show={show} position={[0, 8, 0]} center>
            <div className="devlabel">{dv.label}</div>
          </Label3D>
        </group>
      ))}
    </group>
  )
}

/** Step 7b (illustration only, not a result): the same per-zone pattern repeated across a cluster of campuses. */
function Cluster({ zones, show }: { zones: ZoneGeo[]; show: boolean }) {
  const spots: V3[] = [[-760, 0, -330], [760, 0, -330], [-760, 0, 420], [760, 0, 420], [0, 0, -760]]
  const ref = useRef<THREE.Group>(null!)
  useEffect(() => {
    gsap.killTweensOf(ref.current.scale)
    const s = show ? 1 : 0.001
    gsap.to(ref.current.scale, { x: s, y: s, z: s, duration: reducedMotion() ? 0 : show ? 1.2 : 0.4, ease: 'power3.out', delay: reducedMotion() || !show ? 0 : 0.5 })
  }, [show])
  const mat = useMemo(() => new THREE.MeshStandardMaterial({ color: '#E9E8E2', roughness: 1 }), [])
  return (
    <group ref={ref} scale={0.001}>
      {spots.map((s, i) => (
        <group key={i} position={s} scale={0.55} rotation-y={i * 1.1}>
          {zones.map(z => z.geo && <mesh key={z.name} geometry={z.geo} material={mat} castShadow />)}
        </group>
      ))}
      {spots.map((s, i) => {
        const a = new THREE.Vector3(...s), b = new THREE.Vector3(-385, 0, 40)
        const dd = new THREE.Vector3().subVectors(b, a)
        return (
          <mesh key={`f${i}`} position={a.clone().add(b).multiplyScalar(0.5).setY(1)} rotation={[-Math.PI / 2, 0, Math.atan2(-dd.z, dd.x)]} scale={[dd.length(), 9, 1]}>
            <planeGeometry /><meshBasicMaterial color={C.faint} transparent opacity={0.55} />
          </mesh>
        )
      })}
      <Label3D show={show} position={[0, 160, -1050]} center><div className="duotag ill">Illustration — not a result</div></Label3D>
      <Label3D show={show} position={[0, 110, -760]} center><div className="duotag">another campus</div></Label3D>
      <Label3D show={show} position={[-560, 30, 230]} center><div className="duotag">city feeder</div></Label3D>
    </group>
  )
}
