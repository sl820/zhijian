/**
 * 4 重同心圆 + 28 宿刻度
 *
 * 数据布局：x,y 是 disc 2D 平面（r*cos θ, r*sin θ），z 是世代高度。
 * ring/mansion 都铺在 XY 平面（z=0）。
 * Text 默认 face +Z，从俯视相机读得清；Z 轴旋转 -angle 让字沿径向切线。
 */
import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { BufferAttribute, BufferGeometry, Group } from 'three'
import { Text } from '@react-three/drei'
import { galaxySpin, THEME } from './galaxyParams'
import { TWENTY_EIGHT_MANSIONS } from './xingye'

const RING_RADII = [400, 800, 1200, 1600] as const
const RING_COLORS = [THEME.ink, THEME.gold, THEME.ink, THEME.gold] as const

function Ring({ radius, color, segments = 256 }: { radius: number; color: string; segments?: number }) {
  const points = useMemo(() => {
    const pts: [number, number, number][] = []
    for (let i = 0; i <= segments; i++) {
      const theta = (i / segments) * Math.PI * 2
      pts.push([radius * Math.cos(theta), radius * Math.sin(theta), 0])
    }
    return pts
  }, [radius, segments])

  const geom = useMemo(() => {
    const buf = new Float32Array(points.length * 3)
    points.forEach((p, i) => {
      buf[i * 3] = p[0]
      buf[i * 3 + 1] = p[1]
      buf[i * 3 + 2] = p[2]
    })
    const g = new BufferGeometry()
    g.setAttribute('position', new BufferAttribute(buf, 3))
    return g
  }, [points])

  return (
    <line>
      <primitive object={geom} attach="geometry" />
      <lineBasicMaterial color={color} transparent opacity={0.5} />
    </line>
  )
}

function MansionMark({ angle, radius, label }: { angle: number; radius: number; label: string }) {
  const x = radius * Math.cos(angle)
  const y = radius * Math.sin(angle)
  return (
    <Text
      position={[x, y, 0]}
      rotation={[0, 0, -angle]}
      fontSize={18}
      color={THEME.gold}
      anchorX="center"
      anchorY="middle"
    >
      {label}
    </Text>
  )
}

export function CoordinateRings() {
  const groupRef = useRef<Group>(null)
  useFrame(() => {
    if (groupRef.current) groupRef.current.rotation.z = galaxySpin.angle
  })

  return (
    <group ref={groupRef}>
      {RING_RADII.map((r, i) => (
        <Ring key={r} radius={r} color={RING_COLORS[i]!} />
      ))}
      {TWENTY_EIGHT_MANSIONS.map((m) => (
        <MansionMark key={m.key} angle={m.angle} radius={1700} label={m.cn} />
      ))}
    </group>
  )
}
