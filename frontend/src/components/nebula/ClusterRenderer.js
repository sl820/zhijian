/**
 * 志鉴·星野图考 5000 节点分簇渲染（ClusterRenderer）
 *
 * Why：
 *   5000 节点在紧凑 FA2 布局下会全糊在一起。
 *   旧方案：全部画个体 + bloom + 自动旋转 → 视觉灾难。
 *   新方案（LOD）：
 *     - 远景（camDist > 40）：只渲染 ~50 个聚合 blob（InstancedMesh）
 *     - 中景（camDist 20-40）：blob 渐变 + 个体节点渐变
 *     - 近景（camDist < 20）：纯个体节点（label 出现，可点击）
 *
 * 算法：FA2 layout 的 (x, y) 投影到 10×5 网格（50 桶），每桶：
 *   - 中心 = 节点位置平均
 *   - 计数 = 节点数
 *   - 类别色 = 主类别（最多节点数）
 *
 * 三层 LOD 的 InstancedMesh：
 *   - clusterMesh: ~50 个 blob（每桶 1 个）
 *   - haloMesh: ~50 个浅色光晕（hover/selected 强化用）
 *   - 个体 mesh: 不变，仍由 NebulaCanvas 渲染
 */

import * as THREE from 'three'
import { PALETTE, CATEGORY_COLORS, DYNASTY_COLORS } from '../../constants/palette.js'

const GRID_X = 10
const GRID_Y = 5
const MAX_BUCKETS = GRID_X * GRID_Y  // 50

/**
 * 把节点分桶（10×5 网格 + 平均中心）
 * @param {Array} nodes - 节点列表 [{ x, y, z, category, ... }]
 * @returns {Array<{cx, cy, cz, count, category, ids: string[]}>
 */
export function clusterNodes(nodes) {
  if (!nodes.length) return []

  // 1. 找 x/y 范围
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const n of nodes) {
    const x = n._wx ?? n.x ?? 0
    const y = n._wy ?? n.y ?? 0
    if (x < minX) minX = x; if (x > maxX) maxX = x
    if (y < minY) minY = y; if (y > maxY) maxY = y
  }
  const rangeX = (maxX - minX) || 1
  const rangeY = (maxY - minY) || 1

  // 2. 分桶
  const buckets = new Array(GRID_X * GRID_Y).fill(null).map(() => ({
    sumX: 0, sumY: 0, sumZ: 0, count: 0,
    catCount: { 0: 0, 1: 0, 2: 0, 3: 0 },
    ids: [],
  }))

  for (const n of nodes) {
    const x = n._wx ?? n.x ?? 0
    const y = n._wy ?? n.y ?? 0
    const z = n._wz ?? 0
    const gx = Math.min(GRID_X - 1, Math.max(0, Math.floor((x - minX) / rangeX * GRID_X)))
    const gy = Math.min(GRID_Y - 1, Math.max(0, Math.floor((y - minY) / rangeY * GRID_Y)))
    const idx = gy * GRID_X + gx
    const b = buckets[idx]
    b.sumX += x
    b.sumY += y
    b.sumZ += z
    b.count += 1
    b.ids.push(n.id || n.uri)
    const cat = n.category ?? 2
    b.catCount[cat] = (b.catCount[cat] || 0) + 1
  }

  // 3. 计算每桶中心 + 主类别
  const clusters = []
  for (const b of buckets) {
    if (b.count === 0) continue
    // 主类别（最多节点数）
    let dominantCat = 2
    let maxCount = -1
    for (const [c, n] of Object.entries(b.catCount)) {
      if (n > maxCount) { maxCount = n; dominantCat = Number(c) }
    }
    clusters.push({
      cx: b.sumX / b.count,
      cy: b.sumY / b.count,
      cz: b.sumZ / b.count,
      count: b.count,
      category: dominantCat,
      ids: b.ids,
    })
  }
  return clusters
}

/**
 * 创建聚合 blob InstancedMesh
 * @param {Array} clusters - clusterNodes() 输出
 * @returns {THREE.InstancedMesh}
 */
export function createClusterMesh(clusters) {
  const baseGeom = new THREE.SphereGeometry(1, 14, 12)
  // 不缓存 material — clusters 数量可能变化
  const material = new THREE.MeshStandardMaterial({
    color: 0xffffff,  // 用 instanceColor 覆盖
    metalness: 0.1,
    roughness: 0.6,
    transparent: true,
    opacity: 0.6,
  })

  const mesh = new THREE.InstancedMesh(baseGeom, material, clusters.length)
  mesh.userData.type = 'cluster-blob'

  const dummy = new THREE.Object3D()
  const color = new THREE.Color()

  clusters.forEach((c, i) => {
    dummy.position.set(c.cx, c.cy, c.cz)
    // 半径 = sqrt(count) × 0.4 + 0.6（10 节点 → 1.86，100 节点 → 4.6）
    const r = Math.sqrt(c.count) * 0.4 + 0.6
    dummy.scale.setScalar(r)
    dummy.updateMatrix()
    mesh.setMatrixAt(i, dummy.matrix)

    color.set(CATEGORY_COLORS[c.category] || PALETTE.other)
    mesh.setColorAt(i, color)
  })

  mesh.instanceMatrix.needsUpdate = true
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true

  return mesh
}

/**
 * 创建聚合 blob 光晕 InstancedMesh（半透明加性，远景看像星云）
 */
export function createClusterHaloMesh(clusters) {
  const baseGeom = new THREE.SphereGeometry(1, 10, 8)
  const material = new THREE.MeshBasicMaterial({
    color: 0xffffff,
    transparent: true,
    opacity: 0.18,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })

  const mesh = new THREE.InstancedMesh(baseGeom, material, clusters.length)
  mesh.userData.type = 'cluster-halo'

  const dummy = new THREE.Object3D()
  const color = new THREE.Color()

  clusters.forEach((c, i) => {
    dummy.position.set(c.cx, c.cy, c.cz)
    // 光晕半径比 blob 大 1.4x
    const r = (Math.sqrt(c.count) * 0.4 + 0.6) * 1.4
    dummy.scale.setScalar(r)
    dummy.updateMatrix()
    mesh.setMatrixAt(i, dummy.matrix)

    color.set(CATEGORY_COLORS[c.category] || PALETTE.other)
    mesh.setColorAt(i, color)
  })

  mesh.instanceMatrix.needsUpdate = true
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true

  return mesh
}

/**
 * 计算 LOD level（基于相机距离）
 * 0 = 远景（只 blob）
 * 1 = 中景（blob + 个体淡出）
 * 2 = 近景（只个体）
 * @param {number} camDist
 * @returns {number} LOD 0/1/2
 */
export function computeLOD(camDist) {
  if (camDist > 38) return 0
  if (camDist > 18) return 1
  return 2
}

/**
 * 释放 cluster mesh 资源
 */
export function disposeClusterMesh(mesh) {
  if (!mesh) return
  if (mesh.geometry) mesh.geometry.dispose()
  if (mesh.material) {
    if (mesh.material.map) mesh.material.map.dispose()
    mesh.material.dispose()
  }
}

export default {
  clusterNodes,
  createClusterMesh,
  createClusterHaloMesh,
  computeLOD,
  disposeClusterMesh,
  GRID_X,
  GRID_Y,
  MAX_BUCKETS,
}
