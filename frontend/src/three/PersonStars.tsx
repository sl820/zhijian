/**
 * PersonStars — 165k 族人 Points
 *
 * 共享 geometry：
 *   position (x,y,z from jiapu_v2.json)
 *   aColor (3 floats, 按 dynastyId)
 *   aSize (按 generation: 0=2.0, 1=1.5, 2=1.0)
 *
 * 朝代过滤（store.filters.dynasty）：
 *   useEffect 写 aSize = 0（不重建 geometry）
 *
 * 拾取：JS 端 raycaster（Three.js Points 的 intersect 用 e.index 拿顶点 index）
 *       直接挂 onClick/onPointerMove 到同一组 points，不另开 pick shader
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { useFrame } from '@react-three/fiber'
import {
  AdditiveBlending,
  BufferAttribute,
  BufferGeometry,
  Group,
  Points,
  ShaderMaterial,
} from 'three'
import { loadScenePositions, allScenePositions } from './positions'
import { DYNASTY_COLOR_MAP, galaxySpin } from './galaxyParams'
import { useZhijianStore } from '@/state/store'

const VERT = /* glsl */ `
  attribute vec3 aColor;
  attribute float aSize;
  uniform float uSelected;     // 0/1 是否选中
  uniform float uHovered;      // 0/1 是否 hover
  varying vec3 vColor;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mv;
    float scale = aSize * (1.0 + uSelected * 0.8 + uHovered * 0.3);
    gl_PointSize = scale * (25000.0 / -mv.z);
    vColor = aColor;
  }
`

const FRAG = /* glsl */ `
  varying vec3 vColor;
  void main() {
    vec2 c = gl_PointCoord - 0.5;
    float d = length(c);
    if (d > 0.5) discard;
    float a = smoothstep(0.5, 0.1, d);
    gl_FragColor = vec4(vColor * (0.7 + 0.3 * (1.0 - d * 2.0)), a);
  }
`

export function PersonStars() {
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    loadScenePositions().then(() => setLoaded(true))
  }, [])

  if (!loaded) return null
  return <PersonStarsInner />
}

function PersonStarsInner() {
  const groupRef = useRef<Group>(null)
  const pointsRef = useRef<Points>(null)
  const sizeAttrRef = useRef<BufferAttribute | null>(null)
  const filter = useZhijianStore((s) => s.filters)
  const setHover = useZhijianStore((s) => s.setHover)
  const setPerson = useZhijianStore((s) => s.setPerson)

  const { geometry, scene } = useMemo(() => {
    const scene = allScenePositions()
    const n = scene.length
    const positions = new Float32Array(n * 3)
    const colors = new Float32Array(n * 3)
    const sizes = new Float32Array(n)
    for (let i = 0; i < n; i++) {
      const s = scene[i]!
      positions[i * 3] = s.x
      positions[i * 3 + 1] = s.y
      positions[i * 3 + 2] = s.z
      const c = DYNASTY_COLOR_MAP.get(s.dynasty)
      const cr = c?.r ?? 0.5
      const cg = c?.g ?? 0.5
      const cb = c?.b ?? 0.5
      colors[i * 3] = cr
      colors[i * 3 + 1] = cg
      colors[i * 3 + 2] = cb
      // size: gen 0=2.0, gen 1=1.5, gen 2=1.0
      sizes[i] = s.generation === 0 ? 2.0 : s.generation === 1 ? 1.5 : 1.0
    }
    const g = new BufferGeometry()
    g.setAttribute('position', new BufferAttribute(positions, 3))
    g.setAttribute('aColor', new BufferAttribute(colors, 3))
    g.setAttribute('aSize', new BufferAttribute(sizes, 1))

    return { geometry: g, scene }
  }, [])

  useEffect(() => {
    sizeAttrRef.current = geometry.getAttribute('aSize') as BufferAttribute
  }, [geometry])

  // 朝代过滤
  useEffect(() => {
    if (!sizeAttrRef.current) return
    const sizes = sizeAttrRef.current.array as Float32Array
    const target = filter.dynasty
    for (let i = 0; i < scene.length; i++) {
      const s = scene[i]!
      if (target && s.dynasty !== target) sizes[i] = 0
      else sizes[i] = s.generation === 0 ? 2.0 : s.generation === 1 ? 1.5 : 1.0
    }
    sizeAttrRef.current.needsUpdate = true
  }, [filter.dynasty, scene])

  const displayMat = useMemo(
    () =>
      new ShaderMaterial({
        uniforms: { uSelected: { value: 0 }, uHovered: { value: 0 } },
        vertexShader: VERT,
        fragmentShader: FRAG,
        transparent: true,
        depthWrite: false,
        blending: AdditiveBlending,
      }),
    [],
  )

  useFrame(() => {
    if (groupRef.current) groupRef.current.rotation.z = galaxySpin.angle
  })

  return (
    <group ref={groupRef}>
      <points
        ref={pointsRef}
        geometry={geometry}
        material={displayMat}
        onPointerMove={(e) => {
          e.stopPropagation()
          // Points（非 InstancedMesh）用 e.index 拿顶点 index
          const id = e.index
          if (id !== undefined && id < scene.length && scene[id]) {
            setHover(scene[id].pid)
            if (displayMat.uniforms.uHovered) {
              displayMat.uniforms.uHovered.value = 1
            }
          }
        }}
        onPointerOut={() => {
          setHover(null)
          if (displayMat.uniforms.uHovered) {
            displayMat.uniforms.uHovered.value = 0
          }
        }}
        onClick={(e) => {
          e.stopPropagation()
          const id = e.index
          if (id !== undefined && id < scene.length && scene[id]) {
            setPerson(scene[id].pid)
          }
        }}
      />
    </group>
  )
}
