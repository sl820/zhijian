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
import { bindInteractions, SimpleOrbitControls } from './interaction.js'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  edges: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
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

// 坐标归一化参数（FA2 输出通常在 [-1, 1]，需映射到合理的世界坐标）
const WORLD_SCALE = 18

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
    nodesGroup.add(group)
    nodePositions.set(node.id, group.position)
  }

  // Edges
  const edgesObj = createRelationEdges(props.edges, nodePositions)
  // 把 edgesGroup 替换为新 group 的内容（保留原 group 给交互引用）
  for (const child of edgesObj.children) {
    edgesGroup.add(child)
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
  renderer.render(scene, camera)
}

watch(() => props.nodes, () => buildScene(), { deep: false })

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