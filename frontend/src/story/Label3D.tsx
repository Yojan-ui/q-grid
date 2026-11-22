// A drei <Html> label that stays mounted and fades in/out with CSS. Mounting and unmounting Html roots on every
// step change races with React 19's commit (removeChild errors), and a fade reads better than a pop anyway.
import { Html } from '@react-three/drei'
import type { ComponentProps } from 'react'

type Props = ComponentProps<typeof Html> & { show: boolean }

export function Label3D({ show, style, children, ...rest }: Props) {
  return (
    <Html zIndexRange={[30, 0]} {...rest}
      style={{ ...style, pointerEvents: 'none', opacity: show ? 1 : 0, visibility: show ? 'visible' : 'hidden', transition: 'opacity .35s ease, visibility .35s' }}>
      {children}
    </Html>
  )
}
