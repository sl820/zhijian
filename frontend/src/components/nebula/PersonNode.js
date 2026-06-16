/**
 * 志鉴·星野图考 节点几何（朱砂篆书/印章）
 *
 * 设计：
 * - 不用 SphereGeometry（球太现代）
 * - 姓氏族（category 0）：大朱砂方框 + 姓氏文字（印章风）
 * - 妻妾（category 1）：朱红圆点 + 「女」字符
 * - 官吏/文人（category 3）：朱红圆点 + 名字标签
 * - 其它（category 2）：纯朱红圆点
 *
 * Why：节点几何是星野图考美学的核心 — 不同身份用不同符号，
 * 比统一圆点更有"古方志"质感（参考《星宿图考》星点分级）。
 */

import * as THREE from 'three'
import { PALETTE, CATEGORY_COLORS } from '../../constants/palette.js'

// 节点材质缓存（共享，减少 GPU 切换）
const _materialCache = new Map()

function getMaterial(color, emissive = 0x000000, emissiveIntensity = 0) {
  const key = `${color}_${emissive}_${emissiveIntensity}`
  if (!_materialCache.has(key)) {
    _materialCache.set(key, new THREE.MeshBasicMaterial({
      color: new THREE.Color(color),
      transparent: true,
      opacity: 0.92,
    }))
  }
  return _materialCache.get(key)
}

/**
 * 创建一个 PersonNode Group
 * @param {Object} node - { id, name, category, dynasty, ... }
 * @returns {THREE.Group}
 */
export function createPersonNode(node) {
  const group = new THREE.Group()
  group.userData = { ...node, type: 'person' }

  const category = node.category ?? 2
  const color = CATEGORY_COLORS[category] || PALETTE.other

  // 不同 category 用不同几何
  if (category === 0) {
    // 姓氏族：朱砂方框（印章风）+ 姓氏标签
    const size = 1.4
    const geom = new THREE.PlaneGeometry(size, size)
    const mat = getMaterial(PALETTE.vermilion.main)
    const mesh = new THREE.Mesh(geom, mat)

    // 边框（4 条边线）
    const edges = new THREE.LineSegments(
      new THREE.EdgesGeometry(geom),
      new THREE.LineBasicMaterial({ color: PALETTE.vermilion.bright, linewidth: 2 }),
    )
    group.add(mesh, edges)
  } else {
    // 其它类别：朱红圆点
    const radius = category === 1 ? 0.6 : category === 3 ? 0.55 : 0.45
    const geom = new THREE.CircleGeometry(radius, 16)
    const mat = getMaterial(color)
    const mesh = new THREE.Mesh(geom, mat)
    group.add(mesh)
  }

  // 光晕（半透明大圆，用于远距离辨识）
  const haloGeom = new THREE.CircleGeometry(1.5, 24)
  const haloMat = new THREE.MeshBasicMaterial({
    color: color,
    transparent: true,
    opacity: 0.18,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })
  const halo = new THREE.Mesh(haloGeom, haloMat)
  halo.position.z = -0.01
  group.add(halo)

  // 让节点正对相机（billboard）
  group.userData.billboard = true

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

  nodeGroup.children.forEach((child) => {
    if (child.material && child.material.opacity !== undefined) {
      if (child.material.blending === THREE.AdditiveBlending) {
        // 光晕：hover/selected 时变大变亮
        child.material.opacity = isHover ? 0.45 : isSelected ? 0.6 : 0.18
      } else {
        child.material.opacity = isHover ? 1.0 : isSelected ? 1.0 : 0.92
      }
    }
    if (child.material && child.material.color) {
      const baseColor = child.userData.baseColor
      if (!baseColor) {
        child.userData.baseColor = child.material.color.clone()
      }
      if (state === 'hover') {
        child.material.color.copy(child.userData.baseColor).lerp(new THREE.Color(PALETTE.vermilion.bright), 0.4)
      } else if (state === 'selected') {
        child.material.color.copy(child.userData.baseColor).lerp(new THREE.Color(PALETTE.gold.bright), 0.5)
      } else {
        child.material.color.copy(child.userData.baseColor)
      }
    }
  })

  // 整体放大
  const scale = isHover ? 1.4 : isSelected ? 1.6 : 1.0
  nodeGroup.scale.setScalar(scale)
}

/**
 * 节点名字标签（Sprite 形式，跟随相机）
 */
export function createNameLabel(name, dynasty = '') {
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  canvas.width = 256
  canvas.height = 64

  ctx.font = '24px "LXGW WenKai TC", "霞鹜文楷", "STKaiti", serif'
  ctx.fillStyle = '#f0e8d4'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.shadowColor = 'rgba(194, 54, 42, 0.8)'
  ctx.shadowBlur = 6
  ctx.fillText(name, 128, 24)

  if (dynasty) {
    ctx.font = '14px "LXGW WenKai TC", serif'
    ctx.fillStyle = '#d4b070'
    ctx.shadowBlur = 4
    ctx.fillText(dynasty, 128, 50)
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
  sprite.scale.set(2.4, 0.6, 1)
  sprite.userData.baseScale = sprite.scale.clone()
  return sprite
}

export default {
  createPersonNode,
  setNodeState,
  createNameLabel,
}