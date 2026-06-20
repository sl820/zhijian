/**
 * 志鉴·星野图考 宋代天文图规（CoordinateRings · 北宋方志博物）
 *
 * 设计简化（v2 - 2026-06-18）：
 * - 4 重同心圆（规）保留
 * - 28 颗二十八宿刻度点 + 中文标签保留
 * - 移除 12 放射线（与朝代 z 维度投影冲突，造成视觉干扰）
 * - 移除"天枢朱砂实心圆 + 光晕"（抢节点戏）
 * - 配色改用墨黑（淡）+ 金粉（亮），匹配纸底
 *
 * Why 简化：
 *   旧版装饰元素过多（圆环+放射+天枢+光晕+二十八宿），5000 节点场景下
 *   装饰与节点信息密度冲突。简化为"规 + 宿 + 标签"三层。
 */

import * as THREE from 'three'
import { PALETTE } from '../../constants/palette.js'

/**
 * 二十八宿（按传统顺序，黄道带 28 段）
 */
const LUNAR_MANSIONS = [
  '角', '亢', '氐', '房', '心', '尾', '箕',  // 东方青龙
  '斗', '牛', '女', '虚', '危', '室', '壁',  // 北方玄武
  '奎', '娄', '胃', '昴', '毕', '觜', '参',  // 西方白虎
  '井', '鬼', '柳', '星', '张', '翼', '轸',  // 南方朱雀
]

/**
 * 创建宋代天文图规装饰
 * @param {Object} opts - { radius: 外规半径, innerRadius: 内规半径 }
 * @returns {THREE.Group}
 */
export function createCoordinateRings(opts = {}) {
  const outerR = opts.radius ?? 28
  const innerR = opts.innerRadius ?? 4
  const group = new THREE.Group()
  group.userData.type = 'coordinate-rings'

  // ============================================================
  // 材质：墨黑细线（淡） + 金粉（亮），normal blending（不再 additive — 避免远处变白）
  // ============================================================
  const ringMat = new THREE.LineBasicMaterial({
    color: PALETTE.ink.pale,
    transparent: true,
    opacity: 0.25,
    depthWrite: false,
  })

  const ringMatBright = new THREE.LineBasicMaterial({
    color: PALETTE.gold.main,
    transparent: true,
    opacity: 0.4,
    depthWrite: false,
  })

  // ============================================================
  // 4 重同心圆（规）
  // ============================================================
  const rings = [
    { r: outerR, mat: ringMat, segments: 128 },
    { r: outerR * 0.82, mat: ringMat, segments: 128 },
    { r: outerR * 0.62, mat: ringMatBright, segments: 128 },
    { r: innerR, mat: ringMatBright, segments: 64 },
  ]

  for (const { r, mat, segments } of rings) {
    const points = []
    for (let i = 0; i <= segments; i++) {
      const a = (i / segments) * Math.PI * 2
      points.push(new THREE.Vector3(Math.cos(a) * r, Math.sin(a) * r, 0))
    }
    const geom = new THREE.BufferGeometry().setFromPoints(points)
    const line = new THREE.Line(geom, mat)
    group.add(line)
  }

  // 移除：12 条放射线（与朝代 z 维度冲突）
  // 移除：天枢朱砂实心圆 + 光晕（抢戏）

  // ============================================================
  // 二十八宿刻度点（金粉小点，normal blending）
  // ============================================================
  const mansionGeom = new THREE.BufferGeometry()
  const mansionPositions = new Float32Array(LUNAR_MANSIONS.length * 3)
  for (let i = 0; i < LUNAR_MANSIONS.length; i++) {
    const a = (i / LUNAR_MANSIONS.length) * Math.PI * 2 - Math.PI / 2
    mansionPositions[i * 3] = Math.cos(a) * outerR * 1.04
    mansionPositions[i * 3 + 1] = Math.sin(a) * outerR * 1.04
    mansionPositions[i * 3 + 2] = 0
  }
  mansionGeom.setAttribute('position', new THREE.BufferAttribute(mansionPositions, 3))

  const mansionMat = new THREE.PointsMaterial({
    color: PALETTE.gold.main,
    size: 0.6,
    sizeAttenuation: true,
    transparent: true,
    opacity: 0.85,
    depthWrite: false,
    map: createMansionDotTexture(),
  })

  const mansions = new THREE.Points(mansionGeom, mansionMat)
  group.add(mansions)

  // ============================================================
  // 二十八宿中文标签（Sprite，跟随相机，淡墨色）
  // ============================================================
  for (let i = 0; i < LUNAR_MANSIONS.length; i++) {
    const a = (i / LUNAR_MANSIONS.length) * Math.PI * 2 - Math.PI / 2
    const r = outerR * 1.18
    const label = createMansionLabel(LUNAR_MANSIONS[i])
    label.position.set(Math.cos(a) * r, Math.sin(a) * r, 0)
    label.scale.set(1.4, 1.4, 1)
    label.userData.isLabel = true
    group.add(label)
  }

  return group
}

/**
 * 二十八宿圆点纹理（程序生成 · 北宋方志博物金粉）
 */
function createMansionDotTexture() {
  const size = 64
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')

  // 中心金粉 → 边缘透明（径向渐变）
  const grad = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  grad.addColorStop(0, 'rgba(184, 148, 31, 1.0)')
  grad.addColorStop(0.4, 'rgba(160, 130, 58, 0.7)')
  grad.addColorStop(1, 'rgba(160, 130, 58, 0)')
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, size, size)

  const tex = new THREE.CanvasTexture(canvas)
  tex.minFilter = THREE.LinearFilter
  return tex
}

/**
 * 二十八宿单字标签（Sprite · 淡墨色）
 */
function createMansionLabel(char) {
  const canvas = document.createElement('canvas')
  canvas.width = 64
  canvas.height = 64
  const ctx = canvas.getContext('2d')

  ctx.font = '44px "LXGW WenKai TC", "霞鹜文楷", serif'
  ctx.fillStyle = 'rgba(58, 58, 54, 0.7)'  // 淡墨
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.shadowColor = 'rgba(184, 148, 31, 0.4)'  // 金粉微光
  ctx.shadowBlur = 4
  ctx.fillText(char, 32, 32)

  const tex = new THREE.CanvasTexture(canvas)
  tex.minFilter = THREE.LinearFilter

  const mat = new THREE.SpriteMaterial({
    map: tex,
    transparent: true,
    depthTest: false,
  })
  return new THREE.Sprite(mat)
}

export default {
  createCoordinateRings,
  LUNAR_MANSIONS,
}