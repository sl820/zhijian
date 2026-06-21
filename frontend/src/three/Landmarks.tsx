/**
 * 16 朝代壳"地标"：每朝代在大圈上立一个发光柱 + 朝代名
 *
 * 与 CoordinateRings 同步：铺在 XY 平面（z=0），不与 PersonStars 的数据 z 冲突。
 * rotation.z 跟 galaxySpin 让整圈跟星系一起转。
 */
import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Color, Group } from 'three'
import { Text } from '@react-three/drei'
import { DYNASTY_COLORS, DYNASTY_COLOR_MAP, galaxySpin, THEME } from './galaxyParams'

const SHELL_R = 100

function LandMark({ dynastyId, label }: { dynastyId: number; label: string }) {
  const r = (dynastyId + 1) * SHELL_R
  const angle = (dynastyId * 0.4) % (Math.PI * 2)
  const x = r * Math.cos(angle)
  const y = r * Math.sin(angle)
  const color = DYNASTY_COLOR_MAP.get(label) ?? new Color(THEME.gold)

  return (
    <group position={[x, 0, y]}>
      {/* 旋转 π/2 让 cylinder 沿 Z 方向（垂直 disc），从俯视相机看是干净的圆形 marker */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[4, 4, 60, 16]} />
        <meshBasicMaterial color={color} transparent opacity={0.35} />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[1.5, 1.5, 60, 8]} />
        <meshBasicMaterial color={color} />
      </mesh>
      <Text
        position={[0, 0, 35]}
        fontSize={16}
        color={color}
        anchorX="center"
        anchorY="middle"
        outlineWidth={1}
        outlineColor={THEME.indigoDeep}
      >
        {label}
      </Text>
    </group>
  )
}

export function Landmarks() {
  const groupRef = useRef<Group>(null)
  useFrame(() => {
    if (groupRef.current) groupRef.current.rotation.z = galaxySpin.angle
  })

  return (
    <group ref={groupRef}>
      {DYNASTY_COLORS.map(([key], i) => (
        <LandMark key={key} dynastyId={i} label={key} />
      ))}
    </group>
  )
}
