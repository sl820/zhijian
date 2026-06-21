/**
 * 装饰星系（背景）：DUST + STARS + BULGE
 *
 * 不用与 PersonStars 抢戏，所以粒子数控制在 4k~16k（按 quality）。
 * 全部 Points + ShaderMaterial + AdditiveBlending。
 *
 * 推进唯一时钟 galaxySpin.angle（共享给所有 useFrame 组件）。
 */
import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { AdditiveBlending, BufferAttribute, BufferGeometry, Group, Points, ShaderMaterial } from 'three'
import { advanceSpin, decorStarCount, galaxySpin } from './galaxyParams'
import { detectQuality } from './detectQuality'

const VERT = /* glsl */ `
  attribute float aSize;
  attribute float aBright;
  uniform float uTime;
  varying float vBright;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mv;
    float breathe = 0.7 + 0.3 * sin(uTime * 0.5 + aBright * 6.28);
    vBright = breathe * aBright;
    gl_PointSize = aSize * breathe * (25000.0 / -mv.z);
  }
`

const FRAG = /* glsl */ `
  varying float vBright;
  void main() {
    vec2 c = gl_PointCoord - 0.5;
    float d = length(c);
    if (d > 0.5) discard;
    float a = smoothstep(0.5, 0.0, d);
    gl_FragColor = vec4(vec3(0.85, 0.88, 0.95) * vBright, a * vBright);
  }
`

interface GalaxyParams {
  count: number
  innerR: number
  outerR: number
  sizeBase: number
  brightBase: number
}

function makeLayer(params: GalaxyParams): BufferGeometry {
  const { count, innerR, outerR, sizeBase, brightBase } = params
  const positions = new Float32Array(count * 3)
  const sizes = new Float32Array(count)
  const brights = new Float32Array(count)
  for (let i = 0; i < count; i++) {
    const r = innerR + Math.pow(Math.random(), 1.5) * (outerR - innerR)
    const theta = Math.random() * Math.PI * 2
    // 与 PersonStars 数据一致：disc 在 XY 平面，z 仅做微小高度抖动
    const z = (Math.random() - 0.5) * 30
    positions[i * 3] = r * Math.cos(theta)
    positions[i * 3 + 1] = r * Math.sin(theta)
    positions[i * 3 + 2] = z
    sizes[i] = sizeBase * (0.5 + Math.random() * 1.0)
    brights[i] = brightBase * (0.3 + Math.random() * 0.7)
  }
  const g = new BufferGeometry()
  g.setAttribute('position', new BufferAttribute(positions, 3))
  g.setAttribute('aSize', new BufferAttribute(sizes, 1))
  g.setAttribute('aBright', new BufferAttribute(brights, 1))
  return g
}

export function Galaxy() {
  const quality = useMemo(() => detectQuality(), [])
  const total = decorStarCount(quality)

  const matRef = useRef<ShaderMaterial>(null)
  const groupRef = useRef<Group>(null)

  const layers = useMemo(() => {
    // DUST 60% + STARS 25% + BULGE 15%
    const dustN = Math.floor(total * 0.6)
    const starsN = Math.floor(total * 0.25)
    const bulgeN = total - dustN - starsN
    return {
      dust: makeLayer({ count: dustN, innerR: 200, outerR: 1700, sizeBase: 1.2, brightBase: 0.4 }),
      stars: makeLayer({ count: starsN, innerR: 400, outerR: 1600, sizeBase: 2.0, brightBase: 0.8 }),
      bulge: makeLayer({ count: bulgeN, innerR: 0, outerR: 250, sizeBase: 3.0, brightBase: 1.2 }),
    }
  }, [total])

  useFrame((_, dt) => {
    advanceSpin(dt)
    if (matRef.current && matRef.current.uniforms.uTime) {
      matRef.current.uniforms.uTime.value += dt
    }
    if (groupRef.current) groupRef.current.rotation.z = galaxySpin.angle
  })

  const sharedMat = useMemo(() => {
    return new ShaderMaterial({
      uniforms: { uTime: { value: 0 } },
      vertexShader: VERT,
      fragmentShader: FRAG,
      transparent: true,
      depthWrite: false,
      blending: AdditiveBlending,
    })
  }, [])

  return (
    <group ref={groupRef}>
      <points geometry={layers.dust} material={sharedMat} />
      <points geometry={layers.stars} material={sharedMat} />
      <points geometry={layers.bulge} material={sharedMat} />
    </group>
  )
}
