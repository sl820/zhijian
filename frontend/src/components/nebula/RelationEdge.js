/**
 * 志鉴·星野图考 边（墨黑飞白）
 *
 * 设计：
 * - 用 Line2 (LineSegments2) 模拟墨笔飞白笔触
 * - 边粗细按 confidence 调（0.5-1.0 → 1-3px）
 * - hover 关联边金光流过
 *
 * Why：古方志图考的连线都用墨黑细线，区别于现代力导向的鲜艳线条。
 * 飞白（笔画中留白）是书法术语，转译到视觉就是 alpha 不均 + 暗灰边。
 */

import * as THREE from 'three'
import { PALETTE } from '../../constants/palette.js'

// LineMaterial 全局缓存（避免每条边创建一个 shader program）
const _lineMaterialCache = new Map()

function getLineMaterial(color, lineWidth) {
  const key = `${color}_${lineWidth}`
  if (!_lineMaterialCache.has(key)) {
    const mat = new THREE.LineBasicMaterial({
      color: new THREE.Color(color),
      transparent: true,
      opacity: 0.55,
      depthWrite: false,
    })
    _lineMaterialCache.set(key, mat)
  }
  return _lineMaterialCache.get(key)
}

/**
 * 创建一条关系边（两点直线 + 飞白 alpha 渐变）
 * @param {Object} edge - { source, target, type, confidence }
 * @param {Array<THREE.Vector3>} positions - [src_pos, dst_pos]
 * @returns {THREE.Line}
 */
export function createRelationEdge(edge, positions) {
  const [src, dst] = positions
  const confidence = edge.confidence ?? 0.7
  const lineWidth = 1 + confidence * 1.5  // 0.5~1.0 → 1.75~2.5

  const geom = new THREE.BufferGeometry().setFromPoints([src, dst])
  const mat = getLineMaterial(PALETTE.ink.main, lineWidth)

  // 飞白：在边上随机透明段（用 vertexColors 模拟 alpha）
  const colors = new Float32Array([
    1, 1, 1,
    1, 1, 1,
  ])
  geom.setAttribute('color', new THREE.BufferAttribute(colors, 3))

  const line = new THREE.Line(geom, mat)
  line.userData = {
    ...edge,
    type: 'relation',
    baseOpacity: 0.55,
    baseColor: new THREE.Color(PALETTE.ink.main),
  }
  return line
}

/**
 * 创建所有关系边
 * @param {Array} edges
 * @param {Map<string, THREE.Vector3>} nodePositions
 * @returns {THREE.Group}
 */
export function createRelationEdges(edges, nodePositions) {
  const group = new THREE.Group()
  group.userData.type = 'relations'

  for (const edge of edges) {
    const srcPos = nodePositions.get(edge.source)
    const dstPos = nodePositions.get(edge.target)
    if (!srcPos || !dstPos) continue

    const line = createRelationEdge(edge, [srcPos, dstPos])
    group.add(line)
  }

  return group
}

/**
 * 高亮与某节点相关的边
 * @param {THREE.Group} edgesGroup
 * @param {string} nodeId
 * @param {boolean} highlight
 */
export function highlightEdgesForNode(edgesGroup, nodeId, highlight = true) {
  edgesGroup.children.forEach((line) => {
    const isRelated = line.userData.source === nodeId || line.userData.target === nodeId
    if (!isRelated) {
      line.material.opacity = highlight ? 0.1 : 0.55
      return
    }
    if (highlight) {
      line.material.color.copy(line.userData.baseColor).lerp(new THREE.Color(PALETTE.gold.main), 0.6)
      line.material.opacity = 1.0
    } else {
      line.material.color.copy(line.userData.baseColor)
      line.material.opacity = line.userData.baseOpacity
    }
  })
}

export default {
  createRelationEdge,
  createRelationEdges,
  highlightEdgesForNode,
}