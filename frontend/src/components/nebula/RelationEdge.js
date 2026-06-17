/**
 * 志鉴·星野图考 边（墨黑飞白）
 *
 * 设计：
 * - 用 Line2 (LineSegments2 之类) 模拟墨笔飞白笔触
 * - 边粗细按 confidence 调（0.5-1.0 → 1.5-3.0 世界单位）
 * - 飞白靠 LineMaterial 的 dashed (dashSize=1.0, gapSize=0.4) 实现：
 *   像笔尖拖过干墨时墨色浓淡不均 + 自然断口
 * - hover 关联边：颜色 → 金粉 + opacity 1.0 + dashOffset 动画流光
 *   （不重编译 shader，靠每帧改 dashOffset）
 *
 * Why：古方志图考的连线都用墨黑细线，区别于现代力导向的鲜艳线条。
 * 飞白（笔画中留白）是书法术语，转译到视觉就是断续 + 暗灰边。
 *
 * 重要：每条边用独立 LineMaterial（不缓存），否则 hover 改 opacity/color
 * 会同时影响所有共享材质的边——原版有 bug，现修。
 */

import * as THREE from 'three'
import { Line2 } from 'three/addons/lines/Line2.js'
import { LineGeometry } from 'three/addons/lines/LineGeometry.js'
import { LineMaterial } from 'three/addons/lines/LineMaterial.js'
import { PALETTE } from '../../constants/palette.js'

// 所有 LineMaterial 实例（用于 resize 时统一更新 resolution）
const _allMaterials = new Set()

export function setLineMaterialsResolution(w, h) {
  for (const mat of _allMaterials) {
    mat.resolution.set(w, h)
  }
}

export function disposeLineMaterials() {
  for (const mat of _allMaterials) {
    mat.dispose()
  }
  _allMaterials.clear()
}

function makeLineMaterial(colorHex, width) {
  const mat = new LineMaterial({
    color: new THREE.Color(colorHex),
    linewidth: width,           // 世界单位宽度（worldUnits: true）
    worldUnits: true,
    transparent: true,
    opacity: 0.55,
    dashed: true,
    dashSize: 1.0,
    gapSize: 0.4,
    depthWrite: false,
  })
  // 初始 resolution 兜底（init/initResize 后会再设一次）
  mat.resolution.set(window.innerWidth, window.innerHeight)
  _allMaterials.add(mat)
  return mat
}

/**
 * 创建一条关系边
 * @param {Object} edge - { source, target, type, confidence }
 * @param {Array<THREE.Vector3>} positions - [src_pos, dst_pos]
 * @returns {Line2}
 */
export function createRelationEdge(edge, positions) {
  const [src, dst] = positions
  const confidence = edge.confidence ?? 0.7
  const lineWidth = 1.5 + confidence * 1.5  // 0.5~1.0 → 2.25~3.0

  const geom = new LineGeometry()
  geom.setPositions([src.x, src.y, src.z, dst.x, dst.y, dst.z])
  const mat = makeLineMaterial(PALETTE.ink.main, lineWidth)

  const line = new Line2(geom, mat)
  line.computeLineDistances()
  line.userData = {
    ...edge,
    type: 'relation',
    baseOpacity: 0.55,
    baseColor: new THREE.Color(PALETTE.ink.main),
    baseWidth: lineWidth,
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
 * @param {number} time - performance.now() / 1000，用于 dashOffset 动画
 */
export function highlightEdgesForNode(edgesGroup, nodeId, highlight = true, time = 0) {
  edgesGroup.children.forEach((line) => {
    const isRelated = line.userData.source === nodeId || line.userData.target === nodeId
    if (!isRelated) {
      // 非关联边：降透明
      line.material.opacity = highlight ? 0.08 : line.userData.baseOpacity
      return
    }
    if (highlight) {
      // 关联边：金粉 + opacity 1.0 + 段流光（负 dashOffset 让 dash 向 src 滚动）
      line.material.color.copy(line.userData.baseColor).lerp(new THREE.Color(PALETTE.gold.main), 0.65)
      line.material.opacity = 1.0
      line.material.dashOffset = -time * 2.0
      line.userData._highlighted = true
    } else {
      line.material.color.copy(line.userData.baseColor)
      line.material.opacity = line.userData.baseOpacity
      line.material.dashOffset = 0
      line.userData._highlighted = false
    }
  })
}

/**
 * 每帧更新 hover 态边的 dashOffset（流光动画）
 * 不更新则 dash 静止，hover 效果仍有但少了「金光流过」感
 */
export function tickEdgeHighlight(edgesGroup, time) {
  edgesGroup.children.forEach((line) => {
    if (line.userData._highlighted) {
      line.material.dashOffset = -time * 2.0
    }
  })
}

export default {
  createRelationEdge,
  createRelationEdges,
  highlightEdgesForNode,
  setLineMaterialsResolution,
  disposeLineMaterials,
  tickEdgeHighlight,
}
