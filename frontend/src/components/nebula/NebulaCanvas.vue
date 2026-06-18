<!--
  志鉴·星野图考 NebulaCanvas（v4 - 北宋方志博物重构）

  改造（2026-06-18 v4）：
    - 点击修复（soft-cull）：m.visible=false → m.userData._culled=true，raycast 手动过滤
    - 5000 节点分簇 LOD：远景 InstancedMesh blob（~50 个），中景混合，近景纯个体
    - 移除 auto-rotate（用户投诉"内容堆叠"主因）
    - 移除 UnrealBloomPass（5000 节点 bloom 全糊）
    - 背景：靛蓝 → 米黄纸；雾：深蓝 → 暗纸
    - 灯光：金粉/朱砂/米白 → 米白/金粉/淡墨
    - 配色统一用新 PALETTE token
    - 朝代 z 维度保留（立体感来源）
    - 宋代天文图规保留 4 重同心圆 + 二十八宿，移除天枢光晕 + 12 放射线
-->
<template>
  <div ref="wrapperRef" class="nebula-canvas-wrapper">
    <div ref="containerRef" class="nebula-canvas-inner"></div>
    <div
      v-if="tooltipVisible"
      class="nebula-tooltip"
      :style="{ left: `${tooltipPos.x}px`, top: `${tooltipPos.y}px` }"
    >
      <div class="nebula-tooltip-name">{{ tooltipText.name }}</div>
      <div v-if="tooltipText.dynasty" class="nebula-tooltip-dynasty">
        {{ tooltipText.dynasty }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import * as THREE from 'three'
import { PALETTE } from '../../constants/palette.js'
import { createPersonNode, createNameLabel, setNodeState } from './PersonNode.js'
import { createRelationEdges, highlightEdgesForNode, setLineMaterialsResolution, tickEdgeHighlight, disposeLineMaterials, filterEdgesByLOD } from './RelationEdge.js'
import { createStarField } from './StarFieldBackground.js'
import { createCoordinateRings } from './CoordinateRings.js'
import {
  clusterNodes, createClusterMesh, createClusterHaloMesh,
  computeLOD, disposeClusterMesh,
} from './ClusterRenderer.js'
import { bindInteractions, SimpleOrbitControls, flyToNode } from './interaction.js'
import { NodeRegistry } from './NodeRegistry.js'
import { useNebulaStore } from '../../stores/nebula.js'
import { installNebulaMiddleware } from '../../stores/nebulaMiddleware.js'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  activeDynasties: { type: [Set, Array, null], default: null },
})

const emit = defineEmits(['node-click', 'background-click'])

const wrapperRef = ref(null)
const containerRef = ref(null)

const store = useNebulaStore()

// ============================================================
// Tooltip
// ============================================================
const tooltipVisible = computed(() => !!store.hoveredNodeData)
const tooltipText = computed(() => ({
  name: store.hoveredNodeData?.name || store.hoveredNodeData?.id?.split('/').pop() || '?',
  dynasty: store.hoveredNodeData?.dynasty || '',
}))
const tooltipPos = ref({ x: 0, y: 0 })
const _tooltipVec = new THREE.Vector3()

let scene, camera, renderer, controls, animationId
let nodesGroup, edgesGroup, starField, coordRings
let clusterGroup  // ★ 新增：5000 节点的聚合 blob（InstancedMesh）
let clusterHaloGroup
let interactions
const nodePositions = new Map()
const registry = new NodeRegistry()
let resizeObserver
let uninstallMiddleware = null

const _frustum = new THREE.Frustum()
const _projMatrix = new THREE.Matrix4()

let _lastCullCamPos = new THREE.Vector3(NaN, NaN, NaN)
let _lastCullTarget = new THREE.Vector3(NaN, NaN, NaN)
const CULL_DIST_THRESHOLD = 0.5

// LOD 配置（基于相机距离）
// 2026-06-18 v5：原 LOD_FAR=38 太激进，远景只画 cluster blob → 用户看不见图谱。
// fly mode 需求 = 始终能看到节点。新阈值：只在极远（>60）才退化 cluster，近景全部个体。
const LOD_FAR = 60    // > 60: 退化到 cluster blob（远景）
const LOD_MID = 35    // 35-60: 混合淡出
// < 35: 纯个体

// 视距 LOD（基于 controls.target 距离 · per-node 0/1/2）
//   0 = near (<25)：满显 + 名字
//   1 = far  (25-70)：暗 0.35 + 无名字
//   2 = culled (>70)：不可见，不参与 raycast
const NODE_LOD_NEAR = 25
const NODE_LOD_FAR = 70
const NODE_LOD_NEAR_SQ = NODE_LOD_NEAR * NODE_LOD_NEAR
const NODE_LOD_FAR_SQ = NODE_LOD_FAR * NODE_LOD_FAR
const _visibleNodeIds = new Set()  // 视距内（nodeLod < 2）节点 ID

// 密度阈值（5000 节点时限制远景可视个体数）
// 2026-06-18 v5：放宽到 3000（原来 1500 太严），远景保留 8%（400 颗，够看清密度）
const DENSITY_THRESHOLD = 3000
const DENSITY_FAR_PCT = 0.08

// ============================================================
// 世界尺度（3D 视差的关键 — z 必须有足够范围才能看出深度）
// ============================================================
const WORLD_SCALE_XY = 16   // FA2 x,y → celestial plane
const WORLD_SCALE_Z = 9     // 朝代层间距（每朝代 2-3 个单位）
const Z_LAYER_RANGE = 4     // 每层内部 jitter

// ============================================================
// 朝代 z 深度映射（宋 = 0 中间层；越早越负，越晚越正）
// ============================================================
const DYNASTY_Z_LAYER = {
  pre_han: -3.0,   // 汉前/汉
  three_jin: -2.2, // 三国/晋
  north_sou: -1.5, // 南北朝
  sui: -1.0,       // 隋
  tang: -0.6,      // 唐
  five_dyn: -0.3,  // 五代
  song: 0.0,       // 宋（中层）
  yuan: 0.6,       // 元
  ming: 1.4,       // 明
  qing: 2.4,       // 清
  modern: 3.0,     // 民国+
}

let _frameCounter = 0
let _lastCullVersion = -1
let _lastLabelBucket = -1
let _lastLabelVersion = -1
let _lastFrameCamPos = new THREE.Vector3(NaN, NaN, NaN)
let _lastFrameTarget = new THREE.Vector3(NaN, NaN, NaN)

const DIST_BUCKETS = [12, 30, 60, Infinity]
function computeDistBucket(d) {
  if (d < DIST_BUCKETS[0]) return 0
  if (d < DIST_BUCKETS[1]) return 1
  if (d < DIST_BUCKETS[2]) return 2
  return 3
}

const DIM_FRAME_INTERVAL = 2
const _sphere = new THREE.Sphere()
let _lastActiveSetRef = null

// ============================================================
// 朝代 → bucket 映射
// ============================================================
function yearToDynasty(year) {
  if (year == null || isNaN(year)) return null
  const y = Number(year)
  if (y < 220) return 'pre_han'
  if (y < 420) return 'three_jin'
  if (y < 589) return 'north_sou'
  if (y < 618) return 'sui'
  if (y < 907) return 'tang'
  if (y < 960) return 'five_dyn'
  if (y < 1279) return 'song'
  if (y < 1368) return 'yuan'
  if (y < 1644) return 'ming'
  if (y < 1912) return 'qing'
  return 'modern'
}

/**
 * 3D 深度投影（宋代天文图式）：
 *   FA2 x, y → celestial plane (X, Y)
 *   birth_year → z 深度层（朝代分层）+ jitter
 */
function normalizeCoords(nodes) {
  if (!nodes.length) return nodes
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const n of nodes) {
    const x = n.x ?? 0, y = n.y ?? 0
    if (x < minX) minX = x; if (x > maxX) maxX = x
    if (y < minY) minY = y; if (y > maxY) maxY = y
  }
  const cx = (minX + maxX) / 2
  const cy = (minY + maxY) / 2
  const range = Math.max(maxX - minX, maxY - minY) || 1

  for (const n of nodes) {
    n._wx = ((n.x ?? 0) - cx) / range * WORLD_SCALE_XY
    n._wy = ((n.y ?? 0) - cy) / range * WORLD_SCALE_XY

    const dy = yearToDynasty(n.birth_year)
    const layerZ = DYNASTY_Z_LAYER[dy] ?? 0
    // 每层内部 jitter（z 维度 ± Z_LAYER_RANGE）
    n._wz = layerZ * WORLD_SCALE_Z + (Math.random() - 0.5) * Z_LAYER_RANGE
    n._dynasty = dy
  }
  return nodes
}

function initThree() {
  const container = containerRef.value
  const width = container.clientWidth
  const height = container.clientHeight

  scene = new THREE.Scene()
  // ★ 靛蓝夜底（星野图考 · 苏州石刻天文图式）
  scene.background = new THREE.Color(PALETTE.indigo.deep)
  // 雾用中层靛蓝，密度调低（之前 0.018 把颜色洗成白色）
  scene.fog = new THREE.FogExp2(PALETTE.indigo.mid, 0.008)

  // ============================================================
  // 三点光照（靛蓝夜底 · 冷月光 + 金粉边光）
  // ============================================================
  // 环境光：冷月白，给整体氛围
  scene.add(new THREE.AmbientLight(0xd8e0f0, 0.55))

  // 主光：冷月白，从右上斜射（key light）
  const keyLight = new THREE.DirectionalLight(0xe8eef8, 0.9)
  keyLight.position.set(20, 25, 15)
  scene.add(keyLight)

  // 边光：金粉，从背后射入（rim light — 给节点金边）
  const rimLight = new THREE.DirectionalLight(0xd4a830, 0.55)
  rimLight.position.set(-15, -8, -20)
  scene.add(rimLight)

  // 填充光：靛蓝冷色，从左侧补光
  const fillLight = new THREE.DirectionalLight(0x8090a8, 0.4)
  fillLight.position.set(-15, 10, 8)
  scene.add(fillLight)

  // 中心点光（冷月白，给场景中心加氛围）
  const centerLight = new THREE.PointLight(0xe0e8f8, 0.4, 35, 1.5)
  centerLight.position.set(0, 0, 0)
  scene.add(centerLight)

  // ============================================================
  // 相机（北宋方志博物：非正面，斜角看进去有真 3D 视差）
  // 2026-06-18 v5：fly mode 默认 view — 站远一点看整个图谱，方便用户飞向感兴趣节点
  //   世界坐标 layout 范围 ≈ ±8（normalize 后），相机距离 28 ≈ 视角 30° 看到全部
  // ============================================================
  camera = new THREE.PerspectiveCamera(55, width / height, 0.1, 500)
  camera.position.set(14, 10, 22)  // 距离 √(14²+10²+22²) ≈ 28
  camera.lookAt(0, 0, 0)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(width, height)
  renderer.domElement.style.cursor = 'grab'
  // 真实光照需要 tone mapping
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.0
  renderer.outputColorSpace = THREE.SRGBColorSpace
  container.appendChild(renderer.domElement)

  controls = new SimpleOrbitControls(camera, renderer.domElement)
  controls.minDistance = 3
  controls.maxDistance = 90
  controls.rotateSpeed = 0.5
  controls.zoomSpeed = 0.9

  // ============================================================
  // 星空 / 纸纹点（远景背景）
  // ============================================================
  starField = createStarField(4000)
  scene.add(starField)

  // ============================================================
  // 宋代天文图规（4 重同心圆 + 二十八宿）
  // ============================================================
  coordRings = createCoordinateRings({ radius: 22, innerRadius: 3 })
  scene.add(coordRings)

  nodesGroup = new THREE.Group()
  nodesGroup.userData.type = 'nodes'
  scene.add(nodesGroup)

  edgesGroup = new THREE.Group()
  edgesGroup.userData.type = 'edges'
  scene.add(edgesGroup)

  // ============================================================
  // ★ 聚合 blob 组（InstancedMesh，5000 节点 → ~50 个 blob）
  // ============================================================
  clusterGroup = new THREE.Group()
  clusterGroup.userData.type = 'cluster-blob'
  scene.add(clusterGroup)

  clusterHaloGroup = new THREE.Group()
  clusterHaloGroup.userData.type = 'cluster-halo'
  scene.add(clusterHaloGroup)

  // 移除：后处理 EffectComposer / UnrealBloomPass / OutputPass
  // 原因：5000 节点 bloom 全糊，米黄纸底不需 bloom 装饰

  // ============================================================
  // 交互绑定
  // ============================================================
  interactions = bindInteractions({
    scene, camera, renderer, controls,
    registry,
    store,
    onPick: (id, data) => store.setSelected(id, data),
    onHover: (id, data) => {
      if (id) store.setHover(id, data)
      else store.clearHover()
    },
    onBackgroundPick: () => store.clearSelected(),
  })

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
  setLineMaterialsResolution(w, h)
}

function buildScene() {
  if (!scene) return

  // 清空 nodesGroup / edgesGroup
  while (nodesGroup.children.length) {
    const c = nodesGroup.children.pop()
    c.traverse((obj) => {
      if (obj.geometry) obj.geometry.dispose()
      if (obj.material) {
        if (obj.material.map) obj.material.map?.dispose?.()
        obj.material.dispose?.()
      }
    })
  }
  while (edgesGroup.children.length) {
    const c = edgesGroup.children.pop()
    c.geometry?.dispose?.()
    c.material?.dispose?.()
  }
  // ★ 清空 clusterGroup / clusterHaloGroup
  while (clusterGroup.children.length) {
    const m = clusterGroup.children.pop()
    disposeClusterMesh(m)
  }
  while (clusterHaloGroup.children.length) {
    const m = clusterHaloGroup.children.pop()
    disposeClusterMesh(m)
  }

  nodePositions.clear()
  registry.clear()

  if (!props.nodes.length) {
    store.bumpLayout([])
    return
  }

  const normalized = normalizeCoords([...props.nodes])

  // 从 edges 计算每个节点的 degree（决定 3D 球体半径）
  const degreeMap = new Map()
  for (const e of props.edges) {
    degreeMap.set(e.source, (degreeMap.get(e.source) || 0) + 1)
    degreeMap.set(e.target, (degreeMap.get(e.target) || 0) + 1)
  }
  for (const node of normalized) {
    node.degree = degreeMap.get(node.id) || 0
  }

  // ★ 创建聚合 blob（5000 节点 → ~50 个 InstancedMesh 球）
  const clusters = clusterNodes(normalized)
  if (clusters.length) {
    const blobMesh = createClusterMesh(clusters)
    clusterGroup.add(blobMesh)
    const haloMesh = createClusterHaloMesh(clusters)
    clusterHaloGroup.add(haloMesh)
  }

  for (const node of normalized) {
    const group = createPersonNode(node)
    group.position.set(node._wx, node._wy, node._wz)
    group.userData._dynMul = 1.0
    group.userData._dynMulTarget = 1.0
    group.userData.state = 'idle'
    group.userData._culled = true  // 初始：被 cull（远景只看 blob）

    nodesGroup.add(group)
    registry.add(node.id, group)
    nodePositions.set(node.id, group.position)
  }

  const edgesObj = createRelationEdges(props.edges, nodePositions)
  for (const child of edgesObj.children) {
    edgesGroup.add(child)
  }

  buildImportanceAndSpheres()

  _lastCullCamPos.set(NaN, NaN, NaN)
  _lastCullTarget.set(NaN, NaN, NaN)

  store.bumpLayout(normalized.map((n) => n.id))

  if (import.meta.env?.DEV) {
    const check = registry.integrityCheck(scene)
    if (!check.ok) console.warn('[NodeRegistry] integrity check failed:', check.orphans)
  }
}

function buildImportanceAndSpheres() {
  const degree = new Map()
  for (const e of props.edges) {
    degree.set(e.source, (degree.get(e.source) || 0) + 1)
    degree.set(e.target, (degree.get(e.target) || 0) + 1)
  }
  registry.forEach((m) => {
    if (m.userData?.type !== 'person') return
    const id = m.userData.id || m.userData.uri
    if (id && !degree.has(id)) degree.set(id, 0)
  })
  const rankList = []
  registry.forEach((m, i) => {
    if (m.userData?.type !== 'person') return
    const id = m.userData.id || m.userData.uri
    rankList.push([i, degree.get(id) || 0])
  })
  rankList.sort((a, b) => b[1] - a[1])
  for (let i = 0; i < rankList.length; i++) {
    const [idx] = rankList[i]
    const m = registry.getMeshAt(idx)
    if (!m) continue
    registry.setRank(idx, i)
    const cat = m.category ?? m.userData?.category ?? 2
    // bounding sphere 半径用节点的几何半径（不是固定 1.2/0.7）
    const geom = m.children?.[0]?.geometry
    const r = geom?.parameters?.radius ?? (cat === 0 ? 0.5 : 0.3)
    registry.setSphere(idx, m.position.x, m.position.y, m.position.z, r)
  }
}

function updateCulling(camDist, distBucket, camMoved) {
  if (!camMoved && !registry.isDirty() && registry.version === _lastCullVersion) return
  _lastCullVersion = registry.version
  registry.clearDirty()

  if (registry.size === 0 || !camera || !controls) return

  const total = registry.size
  let visibleCount = total
  if (total > DENSITY_THRESHOLD) {
    const t = Math.max(0, Math.min(1, (camDist - 4) / 50))
    const pct = 1 - t * (1 - DENSITY_FAR_PCT)
    visibleCount = Math.max(100, Math.floor(total * pct))
  }

  _projMatrix.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse)
  _frustum.setFromProjectionMatrix(_projMatrix)

  const cache = registry.cullCache
  const rankArr = cache.rank
  const sphereR = cache.sphereR
  const sphereCx = cache.sphereCx
  const sphereCy = cache.sphereCy
  const sphereCz = cache.sphereCz
  const visArr = cache.visible
  const bucketArr = cache.bucket

  // 视距 LOD：基于 controls.target 距离（pan/flyToNode 都改 target）
  const tgt = controls.target
  const tx = tgt.x, ty = tgt.y, tz = tgt.z
  _visibleNodeIds.clear()

  registry.forEach((m, i) => {
    let visible
    if (rankArr[i] >= visibleCount) {
      visible = 0
    } else {
      const r = sphereR[i]
      if (r <= 0) {
        visible = 1
      } else {
        _sphere.center.set(sphereCx[i], sphereCy[i], sphereCz[i])
        _sphere.radius = r
        visible = _frustum.intersectsSphere(_sphere) ? 1 : 0
      }
    }
    // ★ soft-cull（点击修复关键）
    //   旧版用 m.visible = visible === 1，副作用是 Three.js Raycaster 跳过 invisible 节点
    //   改为 _culled 自定义 flag：mesh 仍 visible=true（render 正常），
    //   interaction.pickNode 手动过滤 _culled=true 节点。
    //   性能：5000 个小球的 frustumCulled 由 Three.js 自动处理，无需手动设 visible
    m.userData._culled = visible !== 1
    m.userData._culledReason = rankArr[i] >= visibleCount ? 'rank' : 'frustum'
    visArr[i] = visible
    bucketArr[i] = distBucket

    // 视距 LOD：per-node 距离 controls.target
    const dx = sphereCx[i] - tx
    const dy = sphereCy[i] - ty
    const dz = sphereCz[i] - tz
    const d2 = dx*dx + dy*dy + dz*dz
    let nodeLod
    if (d2 < NODE_LOD_NEAR_SQ) nodeLod = 0
    else if (d2 < NODE_LOD_FAR_SQ) nodeLod = 1
    else nodeLod = 2
    m.userData._lod = nodeLod

    // 边过滤集：在视距内（nodeLod<2）且未 cull
    if (visible === 1 && nodeLod < 2) {
      const id = m.userData.id || m.userData.uri
      if (id) _visibleNodeIds.add(id)
    }
  })

  // 边按端点可见性过滤（每帧 O(31620)，Set 查找亚毫秒）
  filterEdgesByLOD(edgesGroup, _visibleNodeIds)
}

const _activeSetCache = { ref: null, set: null }
function getActiveSet() {
  const ad = props.activeDynasties
  if (ad == null) return null
  if (ad === _activeSetCache.ref) return _activeSetCache.set
  const s = ad instanceof Set ? ad : new Set(ad)
  _activeSetCache.ref = ad
  _activeSetCache.set = s
  return s
}
const DYNASTY_DIM = 0.15
const DYNASTY_LERP = 0.18

function updateDynastyDim(frame) {
  if (frame % DIM_FRAME_INTERVAL !== 0) return
  if (registry.size === 0) return
  const activeSet = getActiveSet()

  if (activeSet !== _lastActiveSetRef) {
    _lastActiveSetRef = activeSet
    registry.forEach((m) => {
      const dy = m.userData?._dynasty
      const isActive = activeSet == null
        ? true
        : (dy == null ? true : activeSet.has(dy))
      m.userData._dynMulTarget = isActive ? 1.0 : DYNASTY_DIM
    })
  }

  registry.forEach((m) => {
    const cur = m.userData._dynMul ?? 1.0
    const tgt = m.userData._dynMulTarget ?? 1.0
    const next = cur + (tgt - cur) * DYNASTY_LERP
    if (Math.abs(next - cur) < 0.001) return
    m.userData._dynMul = next
    for (const child of m.children) {
      if (child.material && child.userData?._baseOpacity !== undefined) {
        child.material.opacity = child.userData._baseOpacity * next
      }
    }
  })
}

const LABEL_NEAR = 15
const LABEL_FAR = 35
const LABEL_SCALE_FAR = 0.5
const LABEL_SCALE_NEAR = 1.2
const LABEL_MAX = 80

function updateLabels(camDist, distBucket) {
  if (distBucket === _lastLabelBucket && registry.version === _lastLabelVersion) return
  _lastLabelBucket = distBucket
  _lastLabelVersion = registry.version

  if (registry.size === 0 || !camera || !controls) return
  const total = registry.size

  let rankCutoff = 0
  if (camDist <= LABEL_FAR) {
    if (camDist > LABEL_NEAR) {
      rankCutoff = Math.min(LABEL_MAX, Math.max(0, Math.floor(total * 0.3)))
    } else {
      rankCutoff = Math.min(LABEL_MAX, Math.max(0, Math.floor(total * 0.6)))
    }
  }

  const t = Math.max(0, Math.min(1, (LABEL_FAR - camDist) / (LABEL_FAR - LABEL_NEAR)))
  const scale = LABEL_SCALE_FAR + (LABEL_SCALE_NEAR - LABEL_SCALE_FAR) * t

  const rankArr = registry.cullCache.rank
  registry.forEach((m, i) => {
    const label = m.userData?._nameLabel
    if (!label) return
    const dynMul = m.userData._dynMul ?? 1.0
    const passesRank = rankArr[i] < rankCutoff
    label.visible = passesRank && dynMul > 0.5
    if (label.visible) {
      label.scale.set(2.6 * scale, 0.8 * scale, 1)
    }
  })
}

function updateTooltipPosition(node) {
  if (!wrapperRef.value) return
  const v = _tooltipVec
  v.setFromMatrixPosition(node.matrixWorld)
  v.project(camera)
  const wrapperRect = wrapperRef.value.getBoundingClientRect()
  const x = (v.x * 0.5 + 0.5) * wrapperRect.width
  const y = (-v.y * 0.5 + 0.5) * wrapperRect.height
  tooltipPos.value = { x, y }
}

/**
 * 移除自动旋转（v4）— 用户投诉"内容堆叠"主因
 * 保留用户手动旋转（拖动）+ flyToNode（搜索时飞向）
 */
let _lastFrameTime = 0

function animate() {
  animationId = requestAnimationFrame(animate)
  if (!renderer || !scene || !camera) return
  renderFrame()
}

function renderFrame() {
  _frameCounter++
  const now = performance.now()
  const dt = _lastFrameTime ? (now - _lastFrameTime) / 1000 : 0.016
  _lastFrameTime = now

  const camPos = camera.position
  const target = controls.target || new THREE.Vector3()
  const camDist = camPos.distanceTo(target)
  const distBucket = computeDistBucket(camDist)

  // ★ LOD 切换：远景只显示 cluster blob，近景显示个体节点
  const lod = computeLOD(camDist)
  if (clusterGroup) {
    clusterGroup.visible = lod === 0
    clusterHaloGroup.visible = lod === 0
  }
  if (nodesGroup) {
    // 视距 LOD per-node + cluster LOD 合成
    //   nodeLod 2 (>45): 不可见，不参与 raycast
    //   nodeLod 1 (18-45): 暗 0.3
    //   nodeLod 0 (<18): 满显
    //   cluster lod 0 (远): 全部 0；lod 1 (中): 0.3-0.5 fade；lod 2 (近): 满
    registry.forEach((m) => {
      if (m.userData._culled) return
      const nodeLod = m.userData._lod ?? 0
      if (nodeLod === 2) {
        m.visible = false
        return
      }
      m.visible = true
      const dimMul = nodeLod === 1 ? 0.3 : 1.0
      m.children.forEach((child) => {
        if (child.userData?._baseOpacity !== undefined) {
          const baseOp = child.userData._baseOpacity
          if (lod === 0) {
            child.material.opacity = 0
          } else if (lod === 1) {
            // 中景：opacity 在 0.3-0.5 之间（fade in）
            const fade = (camDist - LOD_MID) / (LOD_FAR - LOD_MID)
            child.material.opacity = baseOp * (0.3 + 0.2 * (1 - fade)) * dimMul
          } else {
            child.material.opacity = baseOp * dimMul
          }
        }
      })
    })
  }

  const camMoved =
    camPos.distanceTo(_lastFrameCamPos) >= CULL_DIST_THRESHOLD ||
    target.distanceTo(_lastFrameTarget) >= CULL_DIST_THRESHOLD
  if (camMoved) {
    _lastFrameCamPos.copy(camPos)
    _lastFrameTarget.copy(target)
  }

  updateCulling(camDist, distBucket, camMoved)
  updateDynastyDim(_frameCounter)
  updateLabels(camDist, distBucket)

  // 天文图规缓慢自转（保留 — 古代仪器运转感，幅度更小）
  if (coordRings) {
    coordRings.rotation.z = _frameCounter * 0.00015
  }

  // 星空 uTime
  if (starField?.userData.material) {
    starField.userData.material.uniforms.uTime.value = now * 0.001
  }

  // 边流光
  if (edgesGroup) tickEdgeHighlight(edgesGroup, now * 0.001)

  // Tooltip 跟随
  if (store.hoveredNodeId) {
    const mesh = findNodeById(store.hoveredNodeId)
    if (mesh) updateTooltipPosition(mesh)
  }

  controls?.update?.(dt)
  renderer.render(scene, camera)
}

function findNodeById(id) {
  return registry.get(id)
}

function flyToNodeById(id, animate = true) {
  const mesh = registry.get(id)
  if (!mesh) return false
  if (!animate) {
    const target = mesh.position.clone()
    controls.target.copy(target)
    const newCamPos = target.clone().add(new THREE.Vector3(0, 0, 12))
    const offset = newCamPos.clone().sub(target)
    const radius = offset.length()
    const phi = Math.acos(Math.max(-1, Math.min(1, offset.y / radius)))
    const theta = Math.atan2(offset.x, offset.z)
    controls._spherical = { radius, theta, phi }
    controls._targetSpherical = { radius, theta, phi }
    return true
  }
  flyToNode(camera, controls, registry, id, store, { distance: 12, duration: 1.0 })
  return true
}

function highlightEdgesForNodeExternally(id, on = true) {
  if (!edgesGroup) return
  highlightEdgesForNode(edgesGroup, id, on, performance.now() * 0.001)
}

async function loadLayoutTrigger() {
  const evt = new CustomEvent('nebula:load-layout', { bubbles: true })
  wrapperRef.value?.dispatchEvent(evt)
}

watch(() => props.nodes, () => buildScene(), { deep: false })
watch(() => props.activeDynasties, () => {
  _activeSetCache.ref = null
  _activeSetCache.set = null
})

onMounted(() => {
  initThree()
  buildScene()
  // ★ 移除 setupAutoRotateDetection() — v4 已移除自动旋转
  animate()

  uninstallMiddleware = installNebulaMiddleware(store, () => canvasExpose)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animationId)
  interactions?.dispose()
  controls?.dispose?.()
  resizeObserver?.disconnect()
  renderer?.dispose?.()
  renderer?.domElement?.parentNode?.removeChild(renderer.domElement)
  disposeLineMaterials()
  uninstallMiddleware?.()
  store.killFlyTween()
})

const canvasExpose = {
  findNodeById,
  flyToNode: flyToNodeById,
  highlightEdges: highlightEdgesForNodeExternally,
  clearEdgeHighlight: () => {
    if (!edgesGroup) return
    for (const line of edgesGroup.children) {
      if (line.userData?._highlighted) {
        highlightEdgesForNode(edgesGroup, line.userData.source || line.userData.target, false, 0)
      }
    }
  },
  edgesGroup,
  registry,
  loadLayout: loadLayoutTrigger,
}

defineExpose({
  flyToNode: flyToNodeById,
  findNodeById,
  edgesGroup,
  registry,
})
</script>

<style scoped>
.nebula-canvas-wrapper {
  position: relative;
  flex: 1;
  min-height: 0;
}
.nebula-canvas-inner {
  width: 100%;
  height: 100%;
  position: relative;
}

.nebula-tooltip {
  position: absolute;
  pointer-events: none;
  padding: 6px 12px;
  background: rgba(13, 13, 18, 0.92);
  border: 1px solid var(--xingye-vermilion-seal);
  border-radius: 3px;
  color: var(--xingye-rice-bright);
  font-family: var(--xingye-font-display);
  font-size: 13px;
  letter-spacing: 0.1em;
  white-space: nowrap;
  z-index: 100;
  box-shadow: 0 0 12px rgba(194, 54, 42, 0.4);
  transform: translate(12px, -50%);
}
.nebula-tooltip-name {
  color: var(--xingye-gold-bright);
  font-size: 14px;
}
.nebula-tooltip-dynasty {
  color: var(--xingye-rice-dim);
  font-size: 11px;
  margin-top: 2px;
  letter-spacing: 0.2em;
}
</style>