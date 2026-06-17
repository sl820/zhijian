<!--
  志鉴·星野图考 NebulaCanvas
  three.js 3D 容器 + 服务端 FA2 预布局坐标 + 视锥裁剪 + 视差星空背景

  Props:
    - nodes: [{ id, name, x, y, z, category, dynasty, ... }]
    - edges: [{ source, target, type, confidence }]
    - loading: 是否显示加载动画
-->
<template>
  <div ref="wrapperRef" class="nebula-canvas-wrapper">
    <div ref="containerRef" class="nebula-canvas-inner"></div>
    <div
      v-if="hoveredNode"
      class="nebula-tooltip"
      :style="{ left: `${tooltipPos.x}px`, top: `${tooltipPos.y}px` }"
    >
      <div>{{ hoveredNode.userData.name }}</div>
      <div v-if="hoveredNode.userData.dynasty" class="nebula-tooltip-dynasty">
        {{ hoveredNode.userData.dynasty }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import * as THREE from 'three'
import { PALETTE } from '../../constants/palette.js'
import { createPersonNode, setNodeState, createNameLabel } from './PersonNode.js'
import { createRelationEdges, highlightEdgesForNode } from './RelationEdge.js'
import { createStarField, createCelestialMapPlane } from './StarFieldBackground.js'
import { bindInteractions, SimpleOrbitControls, flyToNode } from './interaction.js'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  // M6 时间轴：当前激活的朝代 id 集合；null/undefined = 全部激活
  activeDynasties: { type: [Set, Array, null], default: null },
})

const emit = defineEmits(['node-click', 'background-click'])

const wrapperRef = ref(null)
const containerRef = ref(null)
const hoveredNode = ref(null)
const tooltipPos = ref({ x: 0, y: 0 })

let scene, camera, renderer, controls, animationId
let nodesGroup, edgesGroup, starField, celestialMap
let interactions
const nodePositions = new Map()
let resizeObserver

// ============================================================
// M6 性能优化：视锥裁剪 + zoom-level 密度过滤
// ============================================================
// 视锥对象（每帧从相机投影矩阵构建）
const _frustum = new THREE.Frustum()
const _projMatrix = new THREE.Matrix4()

// 相机距离变化检测：只在显著移动时才重算（避免每帧扫描所有节点）
let _lastCullCamPos = new THREE.Vector3(NaN, NaN, NaN)
let _lastCullTarget = new THREE.Vector3(NaN, NaN, NaN)
const CULL_DIST_THRESHOLD = 0.5  // 相机移动超过 0.5 单位才重算

// 节点 importance rank（节点数 > 阈值时按 degree 排序，仅渲染前 N）
const DENSITY_THRESHOLD = 800    // < 800 节点全部渲染
const DENSITY_FAR_PCT = 0.35     // 远距离时只保留 35% 节点（按 importance）

// 坐标归一化参数（FA2 输出通常在 [-1, 1]，需映射到合理的世界坐标）
const WORLD_SCALE = 18

// M6 时间轴：按 birth_year 映射到朝代 id
// 与后端 layout_service 解析的 int year 配套
const DYNASTY_BUCKETS = [
  { id: 'pre_han',   label: '汉前/汉',  start: -9999, end: 220  },
  { id: 'three_jin', label: '三国/晋',  start: 220,  end: 420  },
  { id: 'north_sou', label: '南北朝',    start: 420,  end: 589  },
  { id: 'sui',       label: '隋',        start: 589,  end: 618  },
  { id: 'tang',      label: '唐',        start: 618,  end: 907  },
  { id: 'five_dyn',  label: '五代',      start: 907,  end: 960  },
  { id: 'song',      label: '宋',        start: 960,  end: 1279 },
  { id: 'yuan',      label: '元',        start: 1279, end: 1368 },
  { id: 'ming',      label: '明',        start: 1368, end: 1644 },
  { id: 'qing',      label: '清',        start: 1644, end: 1912 },
  { id: 'modern',    label: '民国+',     start: 1912, end: 9999 },
]
function yearToDynasty(year) {
  if (year == null || isNaN(year)) return null
  const y = Number(year)
  for (const b of DYNASTY_BUCKETS) {
    if (y >= b.start && y < b.end) return b.id
  }
  return null
}

function normalizeCoords(nodes) {
  if (!nodes.length) return nodes
  let minX = Infinity, minY = Infinity, minZ = Infinity
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity
  for (const n of nodes) {
    const x = n.x ?? 0, y = n.y ?? 0, z = n.z ?? 0
    if (x < minX) minX = x; if (x > maxX) maxX = x
    if (y < minY) minY = y; if (y > maxY) maxY = y
    if (z < minZ) minZ = z; if (z > maxZ) maxZ = z
  }
  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2
  const cz = (minZ + maxZ) / 2
  const range = Math.max(maxX - minX, maxY - minY, maxZ - minZ) || 1

  for (const n of nodes) {
    n._wx = ((n.x ?? 0) - cx) / range * WORLD_SCALE
    n._wy = ((n.y ?? 0) - cy) / range * WORLD_SCALE
    n._wz = ((n.z ?? 0) - cz) / range * WORLD_SCALE * 0.4  // z 压扁，避免立体感过头
    n._dynasty = yearToDynasty(n.birth_year)
  }
  return nodes
}

function initThree() {
  const container = containerRef.value
  const width = container.clientWidth
  const height = container.clientHeight

  // Scene
  scene = new THREE.Scene()
  scene.background = new THREE.Color(PALETTE.indigo.deep)
  scene.fog = new THREE.FogExp2(PALETTE.indigo.deep, 0.018)

  // Camera
  camera = new THREE.PerspectiveCamera(55, width / height, 0.1, 500)
  camera.position.set(0, 8, 30)

  // Renderer
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(width, height)
  renderer.domElement.style.cursor = 'grab'
  container.appendChild(renderer.domElement)

  // Controls
  controls = new SimpleOrbitControls(camera, renderer.domElement)
  controls.minDistance = 4
  controls.maxDistance = 80

  // Star field background
  starField = createStarField(4000)
  scene.add(starField)

  // Celestial map plane
  celestialMap = createCelestialMapPlane(220)
  celestialMap.position.z = -80
  scene.add(celestialMap)

  // Groups for nodes / edges
  nodesGroup = new THREE.Group()
  nodesGroup.userData.type = 'nodes'
  scene.add(nodesGroup)

  edgesGroup = new THREE.Group()
  edgesGroup.userData.type = 'edges'
  scene.add(edgesGroup)

  // Interactions
  interactions = bindInteractions({
    scene, camera, renderer, controls,
    nodesGroup, edgesGroup,
    onNodeHover: (node) => {
      hoveredNode.value = node
      if (node) updateTooltipPosition(node)
    },
    onNodeClick: (node) => emit('node-click', node.userData),
    onBackgroundClick: () => emit('background-click'),
  })

  // Tooltip position via raycaster
  function updateTooltipPosition(node) {
    const vector = new THREE.Vector3()
    vector.setFromMatrixPosition(node.matrixWorld)
    vector.project(camera)
    const rect = renderer.domElement.getBoundingClientRect()
    const x = (vector.x * 0.5 + 0.5) * rect.width + rect.left
    const y = (-vector.y * 0.5 + 0.5) * rect.height + rect.top
    tooltipPos.value = { x, y }
  }

  // Hover → tooltip 跟随
  setInterval(() => {
    if (hoveredNode.value) updateTooltipPosition(hoveredNode.value)
  }, 50)

  // Resize
  resizeObserver = new ResizeObserver(handleResize)
  resizeObserver.observe(container)
}

function handleResize() {
  if (!containerRef.value || !renderer) return
  const w = containerRef.value.clientWidth
  const h = containerRef.value.clientHeight
  camera.aspect = w / h
  camera.updateProjectionMatrix()
  renderer.setSize(w, h)
}

function buildScene() {
  if (!scene) return
  // Clear
  while (nodesGroup.children.length) {
    const c = nodesGroup.children.pop()
    c.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose()
      if (obj.material) {
        if (obj.material.map) obj.material.map.dispose?.()
        obj.material.dispose?.()
      }
    })
  }
  while (edgesGroup.children.length) {
    const c = edgesGroup.children.pop()
    c.geometry?.dispose?.()
    c.material?.dispose?.()
  }
  nodePositions.clear()

  if (!props.nodes.length) return

  const normalized = normalizeCoords([...props.nodes])

  for (const node of normalized) {
    const group = createPersonNode(node)
    group.position.set(node._wx, node._wy, node._wz)
    // M6 时间轴：朝代淡化乘子（每帧 lerp 到 _dynMulTarget）
    group.userData._dynMul = 1.0
    group.userData._dynMulTarget = 1.0
    nodesGroup.add(group)
    nodePositions.set(node.id, group.position)
  }

  // Edges
  const edgesObj = createRelationEdges(props.edges, nodePositions)
  // 把 edgesGroup 替换为新 group 的内容（保留原 group 给交互引用）
  for (const child of edgesObj.children) {
    edgesGroup.add(child)
  }

  // M6: 计算节点 importance 排名 + 包围球（视锥裁剪用）
  buildImportanceAndSpheres()

  // 重置 cull 状态，强制下一帧重算
  _lastCullCamPos.set(NaN, NaN, NaN)
  _lastCullTarget.set(NaN, NaN, NaN)
}

/**
 * M6 性能优化：
 * - importance: 节点 degree（被多少条边连接）
 * - _rank: 排序后位置（0 = 最重要）
 * - _sphere: 节点包围球（视锥裁剪用，避免每帧 allocate）
 */
function buildImportanceAndSpheres() {
  const degree = new Map()
  for (const e of props.edges) {
    degree.set(e.source, (degree.get(e.source) || 0) + 1)
    degree.set(e.target, (degree.get(e.target) || 0) + 1)
  }
  // 也算 self-loop（节点的"重要度"至少 = 边数）
  for (const child of nodesGroup.children) {
    if (child.userData?.type !== 'person') continue
    const id = child.userData.id || child.userData.uri
    if (!degree.has(id)) degree.set(id, 0)
  }
  // 排序（按 degree 降序）
  const sorted = [...nodesGroup.children].sort((a, b) => {
    const ai = degree.get(a.userData.id || a.userData.uri) || 0
    const bi = degree.get(b.userData.id || b.userData.uri) || 0
    return bi - ai
  })
  // 写 rank + sphere
  sorted.forEach((n, i) => {
    n.userData._rank = i
    const cat = n.userData.category ?? 2
    const r = cat === 0 ? 1.2 : 0.7  // category 0（氏族）大节点，半径更大
    n.userData._sphere = new THREE.Sphere(n.position.clone(), r)
  })
}

/**
 * M6 视锥裁剪 + zoom-level 密度过滤。
 *
 * 算法：
 * 1. 节点数 < DENSITY_THRESHOLD (800) → 全部候选
 * 2. 否则按相机距离插值：近 = 100%、远 = 35%
 * 3. 候选节点再做视锥裁剪：不在视锥内的 visible=false
 *
 * 性能：仅当相机移动 > CULL_DIST_THRESHOLD 时重算（其它帧沿用上次的可见性）
 */
function applyCulling() {
  if (!nodesGroup || !nodesGroup.children.length) return
  if (!camera || !controls) return

  const camPos = camera.position
  const target = controls.target || new THREE.Vector3()
  // 仅当相机显著移动时才重算
  if (
    camPos.distanceTo(_lastCullCamPos) < CULL_DIST_THRESHOLD &&
    target.distanceTo(_lastCullTarget) < CULL_DIST_THRESHOLD
  ) {
    return  // 沿用上次的 visible 状态
  }
  _lastCullCamPos.copy(camPos)
  _lastCullTarget.copy(target)

  // 1. 密度过滤：按相机距离决定保留多少节点
  const total = nodesGroup.children.length
  let visibleCount = total
  if (total > DENSITY_THRESHOLD) {
    const camDist = camPos.distanceTo(target)
    // camDist ∈ [4, 80] → t ∈ [0, 1]
    const t = Math.max(0, Math.min(1, (camDist - 4) / 50))
    // 远 = DENSITY_FAR_PCT，近 = 100%
    const pct = 1 - t * (1 - DENSITY_FAR_PCT)
    visibleCount = Math.max(100, Math.floor(total * pct))
  }

  // 2. 视锥裁剪
  _projMatrix.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse)
  _frustum.setFromProjectionMatrix(_projMatrix)

  for (const n of nodesGroup.children) {
    if (n.userData?._rank >= visibleCount) {
      n.visible = false
      continue
    }
    const sphere = n.userData?._sphere
    if (!sphere) {
      n.visible = true
      continue
    }
    n.visible = _frustum.intersectsSphere(sphere)
  }
}

/**
 * M6 时间轴朝代淡化
 * - activeDynasties 为 null/undefined → 全部 1.0
 * - activeDynasties 为空 Set → 全部 0.15（视觉上"全部关闭"的状态）
 * - 否则：节点的 _dynasty 在集合内 → 1.0；不在 → 0.15
 * - 每年帧 lerp 到 target（dampening factor 0.18，避免突变）
 * - 每帧重写 material.opacity = _baseOpacity * _dynMul（依赖 setNodeState 写入 _baseOpacity）
 */
const _activeSetCache = { ref: null, set: null }
function getActiveSet() {
  const ad = props.activeDynasties
  if (ad == null) return null  // 全激活语义
  if (ad === _activeSetCache.ref) return _activeSetCache.set
  const s = ad instanceof Set ? ad : new Set(ad)
  _activeSetCache.ref = ad
  _activeSetCache.set = s
  return s
}
const DYNASTY_DIM = 0.15  // 非活跃朝代的乘子（"褪色"而非"消失"）
const DYNASTY_LERP = 0.18  // 每帧 lerp 系数（越接近 1 越快）

function applyDynastyDim() {
  if (!nodesGroup || !nodesGroup.children.length) return
  const activeSet = getActiveSet()
  for (const n of nodesGroup.children) {
    if (n.userData?.type !== 'person') continue
    const dy = n.userData._dynasty
    // null dynasty（无生年）一律按活跃处理，避免误淡
    const isActive = activeSet == null
      ? true
      : (dy == null ? true : activeSet.has(dy))
    n.userData._dynMulTarget = isActive ? 1.0 : DYNASTY_DIM
    // lerp 平滑过渡
    const cur = n.userData._dynMul ?? 1.0
    const next = cur + (n.userData._dynMulTarget - cur) * DYNASTY_LERP
    if (Math.abs(next - cur) < 0.001) continue  // 已接近目标，跳过
    n.userData._dynMul = next
    // 应用到所有有 _baseOpacity 的子材质
    for (const child of n.children) {
      if (child.material && child.userData?._baseOpacity !== undefined) {
        child.material.opacity = child.userData._baseOpacity * next
      }
    }
  }
}

/**
 * M6 字号自适应：按相机距离控制 nameLabel 可见性 + 字号
 * - 距离 > LABEL_FAR：全部隐藏（避免远景文字噪声）
 * - 距离 ∈ [LABEL_NEAR, LABEL_FAR]：top 30% by rank（最多 60）
 * - 距离 < LABEL_NEAR：top 60% by rank（最多 80）
 * - 朝代淡化（_dynMul < 0.5）→ 隐藏对应标签
 * - 字号：linear lerp 0.5（远）→ 1.2（近）
 * - 硬上限 80 标签（避免近景 500 节点全部 label 互相遮挡）
 */
const LABEL_NEAR = 15
const LABEL_FAR = 35
const LABEL_SCALE_FAR = 0.5
const LABEL_SCALE_NEAR = 1.2
const LABEL_MAX = 80

function applyLabelVisibility() {
  if (!nodesGroup || !nodesGroup.children.length || !camera || !controls) return
  const camPos = camera.position
  const target = controls.target || new THREE.Vector3()
  const dist = camPos.distanceTo(target)
  const total = nodesGroup.children.length

  // 区间分段 → 决定哪些 rank 可见
  let rankCutoff = 0
  if (dist <= LABEL_FAR) {
    if (dist > LABEL_NEAR) {
      // 中距离：top 30%
      rankCutoff = Math.min(LABEL_MAX, Math.max(0, Math.floor(total * 0.3)))
    } else {
      // 近距离：top 60% (但硬上限 80)
      rankCutoff = Math.min(LABEL_MAX, Math.max(0, Math.floor(total * 0.6)))
    }
  }

  // 字号随距离缩放（远小近大）
  const t = Math.max(0, Math.min(1, (LABEL_FAR - dist) / (LABEL_FAR - LABEL_NEAR)))
  const scale = LABEL_SCALE_FAR + (LABEL_SCALE_NEAR - LABEL_SCALE_FAR) * t
  // 平滑 lerp 避免字号突变
  const prevScale = applyLabelVisibility._prevScale ?? scale
  const curScale = prevScale + (scale - prevScale) * 0.18
  applyLabelVisibility._prevScale = curScale

  for (const n of nodesGroup.children) {
    const label = n.userData?._nameLabel
    if (!label) continue
    const dynMul = n.userData._dynMul ?? 1.0
    const passesRank = (n.userData._rank ?? 0) < rankCutoff
    label.visible = passesRank && dynMul > 0.5
    if (label.visible) {
      label.scale.set(2.4 * curScale, 0.6 * curScale, 1)
    }
  }
}

function animate() {
  animationId = requestAnimationFrame(animate)
  if (!renderer || !scene || !camera) return

  // Star field 呼吸
  if (starField?.userData.material) {
    starField.userData.material.uniforms.uTime.value = performance.now() * 0.001
  }

  // 视差：相机转动时背景轻微反向旋转（"深空感"）
  if (celestialMap && camera) {
    const t = performance.now() * 0.00005
    celestialMap.rotation.z = t
  }

  controls?.update?.()

  // M6 视锥裁剪 + 密度过滤（在 render 前应用）
  applyCulling()

  // M6 时间轴朝代淡化（每帧 lerp）
  applyDynastyDim()

  // M6 字号自适应（按相机距离控制 label 可见性 + 字号）
  applyLabelVisibility()

  renderer.render(scene, camera)
}

watch(() => props.nodes, () => buildScene(), { deep: false })
// M6 时间轴：activeDynasties 引用变化时清缓存，确保下一帧重新评估 _dynMulTarget
watch(() => props.activeDynasties, () => {
  _activeSetCache.ref = null
  _activeSetCache.set = null
})

onMounted(() => {
  initThree()
  buildScene()
  animate()
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animationId)
  interactions?.dispose()
  controls?.dispose?.()
  resizeObserver?.disconnect()
  renderer?.dispose?.()
  renderer?.domElement?.parentNode?.removeChild(renderer.domElement)
})

// ============================================================
// M7 联动：子图节点双击 → 主画布相机飞向
// ============================================================
function findNodeById(id) {
  if (!nodesGroup || !id) return null
  for (const child of nodesGroup.children) {
    if (child.userData?.type !== 'person') continue
    const u = child.userData
    if (u.id === id || u.uri === id) return child
  }
  return null
}

function flyToNodeById(id) {
  const mesh = findNodeById(id)
  if (!mesh) return false
  // 还原所有 selected 状态
  for (const child of nodesGroup.children) {
    if (child.userData?.type === 'person' && child.userData.state === 'selected') {
      setNodeState(child, 'idle')
    }
  }
  flyToNode(camera, controls, mesh, () => {
    setNodeState(mesh, 'selected')
  })
  return true
}

defineExpose({ flyToNode: flyToNodeById })
</script>

<style scoped>
.nebula-canvas-wrapper {
  position: absolute;
  inset: 0;
  z-index: 1;
}
.nebula-canvas-inner {
  width: 100%;
  height: 100%;
  position: relative;
}
</style>