/**
 * 志鉴·星野图考 节点几何（北宋方志博物 · 3D 球体 + 朱砂印章框）
 *
 * 设计（2026-06-18 重构 v2）：
 * - 节点 = 真实 3D 球体（SphereGeometry），受光有体积感
 * - 材质 = MeshStandardMaterial + emissive
 * - 大小 = 连接数 degree 决定（连通性 → 视觉权重），最小 0.25 远距离可见
 * - 姓氏族（category 0）：朱砂印章方框（RingGeometry 4 段）— 视觉锚点
 * - 移除常驻光晕（5000 节点叠加白环）；hover/selected 时由 setNodeState 临时显示
 * - 配色用北宋方志博物 PALETTE（青瓷 / 绛紫 / 金 / 淡墨）
 *
 * Why：
 *   旧版 CircleGeometry 是 billboard，永远正对相机，看起来像 2D 平面。
 *   3D 球体 + 灯光才能让"星野图考"有真 3D 视差。
 */

import * as THREE from 'three'
import { PALETTE, CATEGORY_COLORS, DYNASTY_COLORS } from '../../constants/palette.js'

const _materialCache = new Map()

function getStandardMaterial(color, emissiveIntensity = 0.45) {
  const c = new THREE.Color(color)
  const key = `${color}_${emissiveIntensity.toFixed(2)}`
  if (!_materialCache.has(key)) {
    const mat = new THREE.MeshStandardMaterial({
      color: c,
      emissive: c,
      emissiveIntensity,
      metalness: 0.15,
      roughness: 0.55,
      transparent: true,
      opacity: 0.95,
    })
    _materialCache.set(key, mat)
  }
  return _materialCache.get(key)
}

/**
 * 由节点 degree 计算球体半径（连通性 → 视觉权重）
 * degree=1 (孤星) → r=0.25
 * degree=10 → r=0.45
 * degree=30+ → r=0.7 (上限)
 *
 * 比 v1 整体放大 ~30%：远距离（distBucket=3）下也要能看见
 */
function radiusFromDegree(degree) {
  const d = Math.max(1, degree ?? 1)
  return Math.min(0.7, 0.22 + Math.log(d + 1) * 0.11)
}

/**
 * 创建一个 PersonNode Group
 * @param {Object} node - { id, name, category, dynasty, degree, ... }
 * @returns {THREE.Group}
 */
export function createPersonNode(node) {
  const group = new THREE.Group()
  group.userData = { ...node, type: 'person' }

  const category = node.category ?? 2
  // 优先级：朝代色 > 类别色（朝代优先因为视觉传达时间分布更直接）
  const dynasty = node.dynasty ?? node._dynasty
  const baseColor = (dynasty && DYNASTY_COLORS[dynasty])
    || CATEGORY_COLORS[category]
    || PALETTE.other
  const radius = radiusFromDegree(node.degree)
  const isImportant = (node.degree ?? 0) >= 5

  // ============================================================
  // 主体：3D 球体（受光、有体积感）
  // ============================================================
  const sphereGeom = new THREE.SphereGeometry(radius, 14, 12)
  // 重要节点 emissive 更强（提高 hover/选中辨识度）
  const emissiveIntensity = isImportant ? 0.7 : 0.45
  const sphereMat = getStandardMaterial(baseColor, emissiveIntensity)
  const sphere = new THREE.Mesh(sphereGeom, sphereMat)
  sphere.userData._baseOpacity = 0.95
  sphere.userData._baseColor = new THREE.Color(baseColor)
  group.add(sphere)

  // ============================================================
  // 姓氏族：朱砂印章方框（RingGeometry 4 段 → 印章方块感）
  // 重要家族节点用 4 段方框环绕，旋转 -45° 看起来像印章方章
  // ============================================================
  if (category === 0) {
    const sealGeom = new THREE.RingGeometry(radius * 1.55, radius * 1.85, 4, 1)
    const sealMat = new THREE.MeshBasicMaterial({
      color: PALETTE.vermilion.seal,
      transparent: true,
      opacity: 0.85,
      side: THREE.DoubleSide,
      depthWrite: false,
    })
    const seal = new THREE.Mesh(sealGeom, sealMat)
    seal.lookAt(0, 0, 1)  // 默认面对 +Z
    seal.userData._isSeal = true
    seal.userData._baseOpacity = 0.85
    group.add(seal)
  }

  // ============================================================
  // 名字标签（沿用 Sprite 标签，跟随相机）
  // 平时 hidden，hover/selected 时由 setNodeState 显示
  // ============================================================
  const label = createNameLabel(node.name || '?', node.dynasty || '')
  label.position.set(0, radius + 0.8, 0)
  label.userData.isLabel = true
  label.visible = false
  group.add(label)
  group.userData._nameLabel = label

  return group
}

/**
 * 更新节点 hover/选中状态
 * @param {THREE.Group} nodeGroup
 * @param {string} state - 'idle' | 'hover' | 'selected'
 */
export function setNodeState(nodeGroup, state) {
  const isHover = state === 'hover'
  const isSelected = state === 'selected'
  const dynMul = nodeGroup.userData._dynMul ?? 1.0

  nodeGroup.children.forEach((child) => {
    if (!child.material) return

    // ============================================================
    // opacity（按类型分别处理）
    // ============================================================
    if (child.material.opacity !== undefined) {
      let baseOpacity
      if (child.userData._isSeal) {
        baseOpacity = isHover ? 1.0 : isSelected ? 1.0 : 0.85
      } else {
        baseOpacity = isHover ? 1.0 : isSelected ? 1.0 : 0.95
      }
      child.userData._baseOpacity = baseOpacity
      child.material.opacity = baseOpacity * dynMul
    }

    // ============================================================
    // color（hover/selected → 高亮色调）
    // ============================================================
    if (child.material.color) {
      const baseColor = child.userData._baseColor
      if (!baseColor) {
        child.userData._baseColor = child.material.color.clone()
      }
      if (state === 'hover') {
        child.material.color.copy(child.userData._baseColor)
          .lerp(new THREE.Color(PALETTE.gold.bright), 0.35)
      } else if (state === 'selected') {
        child.material.color.copy(child.userData._baseColor)
          .lerp(new THREE.Color(PALETTE.vermilion.bright), 0.5)
      } else {
        child.material.color.copy(child.userData._baseColor)
      }
    }

    // ============================================================
    // emissiveIntensity（仅 sphere 主体）
    // ============================================================
    if (child.material.emissiveIntensity !== undefined) {
      const baseEI = child.userData._baseEmissiveIntensity
        ?? child.material.emissiveIntensity
      child.userData._baseEmissiveIntensity = baseEI
      child.material.emissiveIntensity = isHover
        ? baseEI * 1.6
        : isSelected
          ? baseEI * 1.9
          : baseEI
    }
  })

  // ============================================================
  // 整体放大（hover/selected 时尺寸突出）
  // ============================================================
  const scale = isHover ? 1.35 : isSelected ? 1.55 : 1.0
  nodeGroup.scale.setScalar(scale)

  // ============================================================
  // hover/selected 时显示名字标签（北宋方志博物 · 卷上有名）
  // ============================================================
  const label = nodeGroup.userData._nameLabel
  if (label) {
    label.visible = isHover || isSelected
  }
}

/**
 * 节点名字标签（Sprite 形式，跟随相机）
 */
export function createNameLabel(name, dynasty = '') {
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  canvas.width = 256
  canvas.height = 80

  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // 名字（米白 + 金粉阴影）
  ctx.font = '28px "LXGW WenKai TC", "霞鹜文楷", "STKaiti", serif'
  ctx.fillStyle = PALETTE.indigo.near
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.shadowColor = PALETTE.gold.faint
  ctx.shadowBlur = 8
  ctx.fillText(name, 128, 30)

  if (dynasty) {
    ctx.font = '14px "LXGW WenKai TC", serif'
    ctx.fillStyle = PALETTE.gold.main
    ctx.shadowColor = PALETTE.vermilion.faint
    ctx.shadowBlur = 4
    ctx.fillText(dynasty, 128, 60)
  }

  const texture = new THREE.CanvasTexture(canvas)
  texture.minFilter = THREE.LinearFilter
  texture.magFilter = THREE.LinearFilter

  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
  })
  const sprite = new THREE.Sprite(material)
  sprite.scale.set(2.6, 0.8, 1)
  sprite.userData.baseScale = sprite.scale.clone()
  return sprite
}

export default {
  createPersonNode,
  setNodeState,
  createNameLabel,
}