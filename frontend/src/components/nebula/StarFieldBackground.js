/**
 * 志鉴·星野图考 星空背景
 *
 * 设计：
 * - 底层：5000+ 颗留白星点（Points + 自定义 shader），缓慢呼吸亮度
 * - 中层：视差旋转（相机转动时背景反向旋转 0.3x）
 * - 上层：可选真实古天文图碑纹理（用户后续提供素材，目前用程序生成纹理占位）
 *
 * Why：星空背景是"星野图考"视觉的核心差异化 — 没有它就是普通 3D 力导向图。
 */

import * as THREE from 'three'
import { PALETTE } from '../../constants/palette.js'

/**
 * 创建星空 Points 对象
 * @param {number} starCount - 星点数量（默认 5000）
 * @returns {THREE.Points
 */
export function createStarField(starCount = 5000) {
  const geometry = new THREE.BufferGeometry()

  const positions = new Float32Array(starCount * 3)
  const sizes = new Float32Array(starCount)
  const phases = new Float32Array(starCount)

  for (let i = 0; i < starCount; i++) {
    // 球壳分布（半径 100-200，避免太近穿模）
    const radius = 100 + Math.random() * 100
    const theta = Math.random() * Math.PI * 2
    const phi = Math.acos(2 * Math.random() - 1)

    positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta)
    positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta)
    positions[i * 3 + 2] = radius * Math.cos(phi)

    // 星点大小分级（90% 小星 + 8% 中星 + 2% 大星）
    const r = Math.random()
    sizes[i] = r < 0.9 ? 0.3 : r < 0.98 ? 0.7 : 1.4

    phases[i] = Math.random() * Math.PI * 2
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1))
  geometry.setAttribute('phase', new THREE.BufferAttribute(phases, 1))

  // 自定义 shader：圆点 + 呼吸亮度 + 米白色
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uColor: { value: new THREE.Color(PALETTE.rice.main) },
      uBrightColor: { value: new THREE.Color(PALETTE.rice.bright) },
    },
    vertexShader: `
      attribute float size;
      attribute float phase;
      uniform float uTime;
      varying float vBrightness;
      void main() {
        vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
        gl_PointSize = size * (300.0 / -mvPosition.z);
        gl_Position = projectionMatrix * mvPosition;
        // 呼吸亮度（周期 3-7 秒，随机 phase）
        float breath = sin(uTime * 0.6 + phase) * 0.5 + 0.5;
        vBrightness = 0.4 + breath * 0.6;
      }
    `,
    fragmentShader: `
      uniform vec3 uColor;
      uniform vec3 uBrightColor;
      varying float vBrightness;
      void main() {
        // 圆形 mask（避免方形星点）
        vec2 coord = gl_PointCoord - vec2(0.5);
        float dist = length(coord);
        if (dist > 0.5) discard;
        float alpha = (1.0 - dist * 2.0) * vBrightness;
        vec3 color = mix(uColor, uBrightColor, vBrightness);
        gl_FragColor = vec4(color, alpha * 0.85);
      }
    `,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  })

  const points = new THREE.Points(geometry, material)
  points.userData.type = 'starfield'
  points.userData.material = material  // 给主循环更新 uTime
  return points
}

/**
 * 程序生成的"古天文图碑"纹理占位（CircleGeometry + 文字 + 网格）
 * 后续用户如有真实公版素材可替换。
 */
export function createCelestialMapTexture(size = 1024) {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')

  // 靛蓝底
  ctx.fillStyle = PALETTE.indigo.deep
  ctx.fillRect(0, 0, size, size)

  // 同心圆（古天文图的"规"）
  ctx.strokeStyle = 'rgba(212, 176, 112, 0.25)'
  ctx.lineWidth = 1.5
  const cx = size / 2
  const cy = size / 2
  for (let i = 1; i <= 4; i++) {
    ctx.beginPath()
    ctx.arc(cx, cy, (size / 2) * (i / 4.5), 0, Math.PI * 2)
    ctx.stroke()
  }

  // 经纬线（横竖各 8 条）
  ctx.strokeStyle = 'rgba(168, 144, 96, 0.15)'
  ctx.lineWidth = 0.8
  for (let i = 0; i <= 8; i++) {
    ctx.beginPath()
    ctx.moveTo(0, (size / 8) * i)
    ctx.lineTo(size, (size / 8) * i)
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo((size / 8) * i, 0)
    ctx.lineTo((size / 8) * i, size)
    ctx.stroke()
  }

  // 中点（北极 / 天枢）
  ctx.fillStyle = PALETTE.vermilion.bright
  ctx.shadowColor = PALETTE.vermilion.bright
  ctx.shadowBlur = 8
  ctx.beginPath()
  ctx.arc(cx, cy, 4, 0, Math.PI * 2)
  ctx.fill()

  // 二十八宿位点（简化）
  for (let i = 0; i < 28; i++) {
    const angle = (i / 28) * Math.PI * 2
    const r = (size / 2) * 0.7
    const x = cx + r * Math.cos(angle)
    const y = cy + r * Math.sin(angle)
    ctx.fillStyle = 'rgba(240, 208, 144, 0.55)'
    ctx.shadowBlur = 4
    ctx.beginPath()
    ctx.arc(x, y, 2.5, 0, Math.PI * 2)
    ctx.fill()
  }

  // 中心标字
  ctx.shadowBlur = 0
  ctx.fillStyle = PALETTE.gold.pale
  ctx.font = '32px "LXGW WenKai TC", "STKaiti", serif'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText('星野图考', cx, cy + 60)
  ctx.font = '14px serif'
  ctx.fillStyle = 'rgba(240, 232, 212, 0.6)'
  ctx.fillText('XINGYE TUKAO', cx, cy + 90)

  const texture = new THREE.CanvasTexture(canvas)
  texture.needsUpdate = true
  return texture
}

/**
 * 创建古天文图碑背景平面（贴在背景天空盒）
 */
export function createCelestialMapPlane(size = 200) {
  const texture = createCelestialMapTexture()
  const geom = new THREE.PlaneGeometry(size, size)
  const mat = new THREE.MeshBasicMaterial({
    map: texture,
    transparent: true,
    opacity: 0.4,
    depthWrite: false,
    depthTest: false,
  })
  const plane = new THREE.Mesh(geom, mat)
  plane.position.z = -50
  plane.userData.type = 'celestial-map'
  return plane
}

export default {
  createStarField,
  createCelestialMapTexture,
  createCelestialMapPlane,
}