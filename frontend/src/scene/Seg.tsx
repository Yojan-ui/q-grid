import { useMemo } from 'react'
import * as THREE from 'three'

/** A polyline as a THREE.Line primitive (avoids the JSX <line> / SVG name clash). */
export function Seg({ points, color, opacity = 1 }: { points: THREE.Vector3[]; color: string; opacity?: number }) {
  const obj = useMemo(() => {
    const g = new THREE.BufferGeometry().setFromPoints(points)
    return new THREE.Line(g, new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity }))
  }, [points, color, opacity])
  return <primitive object={obj} />
}
