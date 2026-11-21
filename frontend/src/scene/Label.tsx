import { Billboard, Text } from '@react-three/drei'

const FONT = `${(import.meta as any).env?.BASE_URL ?? '/'}fonts/Inter-600.woff`   // bundled locally: works offline

/** Camera-facing SDF text label rendered inside the WebGL canvas (no DOM roots, cheap at 60 fps). */
export function Label({ position, text, color = '#E6EAF0', size = 6, onClick }: {
  position: [number, number, number]; text: string; color?: string; size?: number; onClick?: () => void }) {
  return (
    <Billboard position={position}>
      <Text font={FONT} fontSize={size} color={color} anchorX="center" anchorY="middle" outlineWidth={size * 0.12}
        outlineColor="#0B0F14" onClick={onClick ? e => { e.stopPropagation(); onClick() } : undefined}>
        {text}
      </Text>
    </Billboard>
  )
}
