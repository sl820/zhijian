/**
 * 志鉴·星野图考 交互（射线拾取 + 相机飞向）
 *
 * 设计：
 * - raycaster 拾取节点 / 边
 * - hover：节点朱砂光晕、关联边金光、tooltip 显示姓名
 * - click：相机 GSAP 飞向 + 选中状态（高亮金粉）
 * - scroll / drag：OrbitControls 标准 3D 交互
 *
 * Why：3D 图谱的"活感"来自交互反馈。这套机制让用户能"触摸"星点。
 */

import * as THREE from 'three'
import gsap from 'gsap'
import { setNodeState } from './PersonNode.js'
import { highlightEdgesForNode } from './RelationEdge.js'

/**
 * 在容器上绑定交互（raycaster + OrbitControls 替代品）
 * @param {Object} ctx - { scene, camera, renderer, controls, nodesGroup, edgesGroup, onNodeHover, onNodeClick }
 */
export function bindInteractions(ctx) {
  const {
    scene, camera, renderer, controls,
    nodesGroup, edgesGroup,
    onNodeHover, onNodeClick, onBackgroundClick,
  } = ctx

  const raycaster = new THREE.Raycaster()
  const mouse = new THREE.Vector2()
  let hoveredNode = null

  function updateMouseFromEvent(event) {
    const rect = renderer.domElement.getBoundingClientRect()
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  }

  function pickNode() {
    raycaster.setFromCamera(mouse, camera)
    const intersects = raycaster.intersectObjects(nodesGroup.children, true)
    for (const hit of intersects) {
      // 沿 parent 链找 userData.type === 'person'
      let obj = hit.object
      while (obj && obj.userData?.type !== 'person') {
        obj = obj.parent
      }
      if (obj) return obj
    }
    return null
  }

  function onPointerMove(event) {
    updateMouseFromEvent(event)
    const node = pickNode()

    if (node !== hoveredNode) {
      // 还原上一个
      if (hoveredNode && hoveredNode.userData.state !== 'selected') {
        setNodeState(hoveredNode, 'idle')
        if (edgesGroup) highlightEdgesForNode(edgesGroup, hoveredNode.userData.id, false, performance.now() * 0.001)
      }
      hoveredNode = node
      if (hoveredNode) {
        setNodeState(hoveredNode, 'hover')
        if (edgesGroup) highlightEdgesForNode(edgesGroup, hoveredNode.userData.id, true, performance.now() * 0.001)
        renderer.domElement.style.cursor = 'pointer'
      } else {
        renderer.domElement.style.cursor = 'grab'
      }
      onNodeHover?.(node)
    }
  }

  function onPointerDown(event) {
    renderer.domElement.style.cursor = 'grabbing'
  }

  function onPointerUp(event) {
    renderer.domElement.style.cursor = hoveredNode ? 'pointer' : 'grab'
  }

  function onClick(event) {
    updateMouseFromEvent(event)
    const node = pickNode()
    if (node) {
      onNodeClick?.(node)
      flyToNode(camera, controls, node, () => {
        setNodeState(node, 'selected')
      })
    } else {
      onBackgroundClick?.()
    }
  }

  renderer.domElement.addEventListener('pointermove', onPointerMove)
  renderer.domElement.addEventListener('pointerdown', onPointerDown)
  renderer.domElement.addEventListener('pointerup', onPointerUp)
  renderer.domElement.addEventListener('click', onClick)

  return {
    getHoveredNode: () => hoveredNode,
    dispose: () => {
      renderer.domElement.removeEventListener('pointermove', onPointerMove)
      renderer.domElement.removeEventListener('pointerdown', onPointerDown)
      renderer.domElement.removeEventListener('pointerup', onPointerUp)
      renderer.domElement.removeEventListener('click', onClick)
    },
  }
}

/**
 * 相机飞向节点（GSAP tween）
 * @param {THREE.PerspectiveCamera} camera
 * @param {Object} controls - OrbitControls
 * @param {THREE.Object3D} node
 * @param {Function} onComplete
 */
export function flyToNode(camera, controls, node, onComplete) {
  const target = node.position.clone()
  // 相机停在节点前方 8 单位
  const cameraOffset = new THREE.Vector3(0, 0, 8)
  const newCamPos = target.clone().add(cameraOffset)

  const duration = 1.2
  gsap.to(camera.position, {
    x: newCamPos.x,
    y: newCamPos.y,
    z: newCamPos.z,
    duration,
    ease: 'power2.inOut',
    onUpdate: () => {
      if (controls) controls.update?.()
    },
    onComplete: () => {
      if (controls) {
        controls.target?.copy?.(target)
        controls.update?.()
      }
      onComplete?.()
    },
  })
}

/**
 * 简单 OrbitControls 实现（避免引入 three/examples/jsm/OrbitControls
 * —— Vite tree-shaking 时路径不稳定）
 *
 * 设计：
 * - 左键拖动：旋转（azimuth + polar）
 * - 右键 / 双指拖动：平移
 * - 滚轮：缩放
 */
export class SimpleOrbitControls {
  constructor(camera, domElement) {
    this.camera = camera
    this.domElement = domElement
    this.target = new THREE.Vector3(0, 0, 0)
    this.minDistance = 2
    this.maxDistance = 80
    this.rotateSpeed = 0.6
    this.zoomSpeed = 1.0
    this.panSpeed = 0.4
    this.enableDamping = true
    this.dampingFactor = 0.08

    this._spherical = { radius: 30, theta: 0, phi: Math.PI / 2 }
    this._targetSpherical = { radius: 30, theta: 0, phi: Math.PI / 2 }
    this._isDragging = false
    this._lastX = 0
    this._lastY = 0

    this._updateCameraFromSpherical()
    this._bindEvents()
  }

  _bindEvents() {
    const dom = this.domElement
    this._onPointerDown = (e) => {
      this._isDragging = true
      this._lastX = e.clientX
      this._lastY = e.clientY
      dom.setPointerCapture(e.pointerId)
    }
    this._onPointerMove = (e) => {
      if (!this._isDragging) return
      const dx = e.clientX - this._lastX
      const dy = e.clientY - this._lastY
      this._lastX = e.clientX
      this._lastY = e.clientY

      if (e.button === 2 || e.shiftKey) {
        // 平移
        const right = new THREE.Vector3()
        const up = new THREE.Vector3()
        this.camera.matrixWorld.extractBasis(right, up, new THREE.Vector3())
        right.multiplyScalar(-dx * this.panSpeed * 0.02)
        up.multiplyScalar(dy * this.panSpeed * 0.02)
        this.target.add(right).add(up)
      } else {
        // 旋转
        this._targetSpherical.theta -= dx * this.rotateSpeed * 0.01
        this._targetSpherical.phi -= dy * this.rotateSpeed * 0.01
        this._targetSpherical.phi = Math.max(0.1, Math.min(Math.PI - 0.1, this._targetSpherical.phi))
      }
    }
    this._onPointerUp = (e) => {
      this._isDragging = false
      dom.releasePointerCapture(e.pointerId)
    }
    this._onWheel = (e) => {
      e.preventDefault()
      const factor = e.deltaY > 0 ? 1.1 : 0.9
      this._targetSpherical.radius = Math.max(
        this.minDistance,
        Math.min(this.maxDistance, this._targetSpherical.radius * factor),
      )
    }
    this._onContextMenu = (e) => e.preventDefault()

    dom.addEventListener('pointerdown', this._onPointerDown)
    dom.addEventListener('pointermove', this._onPointerMove)
    dom.addEventListener('pointerup', this._onPointerUp)
    dom.addEventListener('wheel', this._onWheel, { passive: false })
    dom.addEventListener('contextmenu', this._onContextMenu)
  }

  update() {
    if (this.enableDamping) {
      this._spherical.radius += (this._targetSpherical.radius - this._spherical.radius) * this.dampingFactor
      this._spherical.theta += (this._targetSpherical.theta - this._spherical.theta) * this.dampingFactor
      this._spherical.phi += (this._targetSpherical.phi - this._spherical.phi) * this.dampingFactor
    } else {
      Object.assign(this._spherical, this._targetSpherical)
    }
    this._updateCameraFromSpherical()
  }

  _updateCameraFromSpherical() {
    const { radius, theta, phi } = this._spherical
    const sinPhi = Math.sin(phi)
    const x = radius * sinPhi * Math.sin(theta)
    const y = radius * Math.cos(phi)
    const z = radius * sinPhi * Math.cos(theta)
    this.camera.position.set(x, y, z).add(this.target)
    this.camera.lookAt(this.target)
  }

  dispose() {
    const dom = this.domElement
    dom.removeEventListener('pointerdown', this._onPointerDown)
    dom.removeEventListener('pointermove', this._onPointerMove)
    dom.removeEventListener('pointerup', this._onPointerUp)
    dom.removeEventListener('wheel', this._onWheel)
    dom.removeEventListener('contextmenu', this._onContextMenu)
  }
}

export default {
  bindInteractions,
  flyToNode,
  SimpleOrbitControls,
}