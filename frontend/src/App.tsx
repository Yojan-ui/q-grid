import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'

// Phase 0 placeholder scene. The four-act cinematic demo is built in Phase 7.
export default function App() {
  return (
    <>
      <Canvas camera={{ position: [6, 5, 8], fov: 45 }}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[5, 8, 3]} intensity={1.2} />
        <mesh position={[0, 0.5, 0]}>
          <boxGeometry args={[1.5, 1, 1.5]} />
          <meshStandardMaterial color="#3fb68b" />
        </mesh>
        <gridHelper args={[20, 20, '#1d2a44', '#111a2e']} />
        <OrbitControls />
      </Canvas>
      <div className="labels">
        <div>Real data: NASA POWER / Ausgrid / IEX / CEA</div>
        <div>QAOA on a local simulator: verified against exact solutions, no quantum advantage claimed</div>
      </div>
    </>
  )
}
