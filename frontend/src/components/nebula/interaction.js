/**
 * 志鉴·星野图考 交互（射线拾取 + 相机飞向）
 *
 * 改造（v2 - 2026-06-17）：
 *   - 移除内部 selectedNodeId / hoveredNode 状态（改由 store 持有）
 *   - onClick / onPointerMove 不再直接 setNodeState / highlightEdges / setSelectedEdges
 *   - 改为只 emit 事件：onPick(id, data) / onHover(id, data) / onBackgroundPick()
 *   - 副作用由 nebulaMiddleware.js 集中处理
 *   - flyToNode 返回 GSAP tween 句柄，由 store.killFlyTween() 统一 kill（防连续 click 飞行动画冲突）
 *
 * Why：
 *   旧版 onClick 同时改 scene（setNodeState + highlightEdges + flyTo）又 emit 给 Vue，
 *   导致状态在 4 个组件副本里漂移。改造后 interaction.js 只做"事件采集"。
 */

import * as THREE from 'three'
import gsap from 'gsap'

// 显式标注：本文件不再 import setNodeState / highlightEdgesForNode，
// 这两个副作用在 nebulaMiddleware.js 集中处理。raycast 与 fly 也不再
// 直接持有 mesh 引用——全部走 NodeRegistry。

/**
 * 在容器上绑定交互（raycaster + OrbitControls 替代品）
 *
 * 关键改造（v3 - 2026-06-17，NodeRegistry 化）：
 *   - raycast 目标来源是 NodeRegistry.values()，不再是 nodesGroup.children
 *   - 这样保证 raycast 永远不会命中"已 dispose 但 group 引用还在"的 mesh
 *   - layout rebuild 时 registry.clear() 后 raycast 立刻收手，不会击中旧 mesh
 *
 * @param {Object} ctx - {
 *   scene, camera, renderer, controls,
 *   registry,                       // NodeRegistry（raycast 唯一来源）
 *   onPick,                          // (id, userData) => void   节点点击
 *   onHover,                         // (id, userData) => void   节点 hover
 *   onBackgroundPick,                // () => void               空白点击
 *   store,                           // nebula store（用于 tween handle 跟踪）
 * }
 */
export function bindInteractions(ctx) {
  const {
    scene, camera, renderer, controls,
    registry,
    onPick, onHover, onBackgroundPick,
    store,
  } = ctx

  const raycaster = new THREE.Raycaster()
  const mouse = new THREE.Vector2()

  function updateMouseFromEvent(event) {
    const rect = renderer.domElement.getBoundingClientRect()
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
  }

  /**
   * 拾取：raycast 仅作用于 registry 中的 mesh
   * - 不命中 scene 中其他 group（背景、星点、天文图）
   * - 不命中已 dispose 的旧 mesh（registry 不包含就不会被拾取）
   * - 不命中被 cull 的节点（_culled=true，由 NebulaCanvas 标记；
   *   这是 click 修复的核心 — culling 之前用 m.visible=false，
   *   副作用是 Three.js Raycaster 跳过 visible=false 节点，
   *   改为 _culled 自定义 flag 后，raycast 仍命中，再手动过滤）
   * - intersectObjects 第二个参数 recursive=true：Group 内子 mesh（CircleGeometry 等）也算
   */
  function pickNode() {
    if (!registry || registry.size === 0) return null
    // spread Map iterator → array
    const targets = [...registry.values()]
    // raycaster 需 camera 才能 hit sprite；person node 包含 name label sprite
    raycaster.camera = camera
    const intersects = raycaster.intersectObjects(targets, true)
    for (const hit of intersects) {
      // 跳过 sprite（name label、二十八宿刻度）— 它们是装饰，不参与交互
      if (hit.object.isSprite) continue
      // 沿 parent 链找 userData.type === 'person'（命中的是子 mesh）
      let obj = hit.object
      while (obj && obj.userData?.type !== 'person') {
        obj = obj.parent
      }
      if (obj) {
        // 防御性检查：返回的 person Group 必须仍在 registry 中
        const id = obj.userData.id || obj.userData.uri
        if (!id || !registry.has(id)) continue
        // ★ soft-cull 过滤：被 NebulaCanvas 标记的 culled 节点不参与交互
        //   （rank 超出当前可见预算 / 视锥外 / 朝代禁用）
        if (obj.userData._culled) continue
        return obj
      }
    }
    return null
  }

  function onPointerMove(event) {
    updateMouseFromEvent(event)
    const node = pickNode()

    if (node) {
      // hover 命中：emit（middleware 会对比旧 id 决定是否真更新）
      const id = node.userData.id || node.userData.uri
      const data = node.userData
      onHover?.(id, data)
      renderer.domElement.style.cursor = 'pointer'
    } else {
      // hover 离开：emit null
      onHover?.(null, null)
      renderer.domElement.style.cursor = 'grab'
    }
  }

  function onPointerDown(event) {
    renderer.domElement.style.cursor = 'grabbing'
  }

  function onPointerUp(event) {
    // cursor 由 hover 状态决定（onPointerMove 下一帧会刷新）
    renderer.domElement.style.cursor = 'grab'
  }

  function onClick(event) {
    updateMouseFromEvent(event)
    const node = pickNode()
    if (node) {
      const id = node.userData.id || node.userData.uri
      const data = node.userData
      onPick?.(id, data)
    } else {
      onBackgroundPick?.()
    }
  }

  renderer.domElement.addEventListener('pointermove', onPointerMove)
  renderer.domElement.addEventListener('pointerdown', onPointerDown)
  renderer.domElement.addEventListener('pointerup', onPointerUp)
  renderer.domElement.addEventListener('click', onClick)

  return {
    dispose: () => {
      renderer.domElement.removeEventListener('pointermove', onPointerMove)
      renderer.domElement.removeEventListener('pointerdown', onPointerDown)
      renderer.domElement.removeEventListener('pointerup', onPointerUp)
      renderer.domElement.removeEventListener('click', onClick)
    },
  }
}

/**
 * 相机飞向节点（GSAP tween on spherical 坐标）
 *
 * 改造（v3 - NodeRegistry 化）：
 *   - 接受 nodeId + registry，不直接持 mesh 引用
 *   - mesh 在 tween 启动时按 id 查 registry 拿一次，之后 tween 只用 position
 *     （position 已 clone 成 Vector3，不持有 mesh 引用）
 *   - 即使 tween 跑的过程中 layout rebuild，mesh 引用消失，tween 也只动
 *     camera spherical，**不会触碰已销毁 mesh**
 *
 * 改造（v2）：
 *   - 创建 tween 后立即注册到 store（store.setFlyTween），用于 kill 旧 tween
 *   - 切换 selected 时 store 自动 kill 旧 tween（连续 click 不再相机抖）
 *
 * @param {THREE.PerspectiveCamera} camera
 * @param {Object} controls - SimpleOrbitControls
 * @param {Object} registry - NodeRegistry
 * @param {string} nodeId
 * @param {Object} store - nebula store（用于 tween 句柄注册）
 * @param {Object} opts - { distance: 相机距节点距离 (默认 12), duration: 动画时长 (默认 1.0s) }
 * @returns {gsap.core.Tween|null} tween 句柄（外部可 kill）；nodeId 不存在则返 null
 */
export function flyToNode(camera, controls, registry, nodeId, store, opts = {}) {
  if (!controls) return null
  if (!registry || !nodeId) return null

  // 按 id 查 mesh（不持有外部引用，clone position）
  const mesh = registry.get(nodeId)
  if (!mesh) {
    // 节点不在 registry（被 filter 排除 / rebuild 还没完成）—— silent no-op
    return null
  }

  const distance = opts.distance ?? 12
  const duration = opts.duration ?? 1.0
  // 关键：clone 一次 position 到独立 Vector3，tween 不再依赖 mesh
  const target = mesh.position.clone()

  // Kill 旧 tween（连续 click 防抖）
  if (store?.flyTweenHandle) {
    try { store.flyTweenHandle.kill?.() } catch (e) { /* ignore */ }
  }

  // fly 模式：直接 teleport + GSAP 插值位置与朝向，不走 spherical tween
  if (controls._flyMode) {
    // 选个新 camera 位置：保留当前 look 方向，把 position 平移到 target + dir*distance
    const dir = new THREE.Vector3().subVectors(camera.position, controls.target).normalize()
    if (!isFinite(dir.x) || dir.lengthSq() < 1e-6) dir.set(0, 0, 1)
    const newCamPos = target.clone().addScaledVector(dir, distance)
    const tweenPos = { x: camera.position.x, y: camera.position.y, z: camera.position.z }
    const tw = gsap.to(tweenPos, {
      x: newCamPos.x,
      y: newCamPos.y,
      z: newCamPos.z,
      duration,
      ease: 'power2.inOut',
      onUpdate: () => {
        camera.position.set(tweenPos.x, tweenPos.y, tweenPos.z)
        controls.target.copy(target)
        camera.lookAt(target)
      },
      onComplete: () => {
        if (store?.flyTweenHandle === tw) store.setFlyTween(null, null)
      },
    })
    if (store) store.setFlyTween(tw, nodeId)
    return tw
  }

  // orbit 模式：原 GSAP tween on spherical
  const newCamPos = target.clone().add(new THREE.Vector3(0, 0, distance))
  const offset = newCamPos.clone().sub(target)
  const radius = offset.length()
  const phi = Math.acos(Math.max(-1, Math.min(1, offset.y / radius)))
  const theta = Math.atan2(offset.x, offset.z)

  controls.target.copy(target)

  const tween = { r: controls._targetSpherical.radius, t: controls._targetSpherical.theta, p: controls._targetSpherical.phi }
  const tw = gsap.to(tween, {
    r: radius,
    t: theta,
    p: phi,
    duration,
    ease: 'power2.inOut',
    onUpdate: () => {
      controls._targetSpherical.radius = tween.r
      controls._targetSpherical.theta = tween.t
      controls._targetSpherical.phi = tween.p
    },
    onComplete: () => {
      if (store?.flyTweenHandle === tw) {
        store.setFlyTween(null, null)
      }
    },
  })

  if (store) {
    store.setFlyTween(tw, nodeId)
  }

  return tw
}

/**
 * 简单 OrbitControls 实现（避免引入 three/examples/jsm/OrbitControls
 * —— Vite tree-shaking 时路径不稳定）
 *
 * 2026-06-18 升级：加 fly 模式（Tab 切换）
 *   - orbit 模式：原行为，绕 target 旋转
 *   - fly 模式：自由飞行
 *     - WASD = 前后左右（相机本地坐标系）
 *     - QE = 上下（世界 y 轴）
 *     - Shift = 加速 ×3
 *     - 鼠标拖拽 = 偏航/俯仰（改 look 方向）
 *     - 滚轮 = 调速（0.9× / 1.1×）
 *   - LOD / flyToNode 仍能用：fly 模式下 controls.target 同步到 camera 前方 80
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

    // ===== fly 模式状态 =====
    this._flyMode = false
    this._flyKeys = { w: false, a: false, s: false, d: false, q: false, e: false, shift: false }
    this._flySpeed = 12.0           // 世界单位/秒（基础）
    this._flySpeedMin = 1.0
    this._flySpeedMax = 80.0
    this._flySensitivity = 0.0035   // 鼠标 → yaw/pitch 系数
    this._flyYaw = 0                // 偏航（绕 y）
    this._flyPitch = 0              // 俯仰（相对水平，[-π/2, π/2]）
    this._onFlyModeChange = null    // (enabled) => void 回调（NebulaCanvas 切 UI 提示）

    // ===== 碰撞（fly mode）：限制最大前进距离 =====
    //   provider(cameraPos, forward, maxDist) → number
    //   返回"最近阻挡点沿 forward 的距离"，callers 把 speed * k 限制到不超过这个距离
    this._collisionProvider = null
    this._lastHitInfo = null        // { distance, nodeId, nodeName } 给 UI 提示

    this._updateCameraFromSpherical()
    this._bindEvents()
  }

  /**
   * 切换 fly / orbit 模式。同步 yaw/pitch 与当前 spherical 避免跳变。
   */
  setFlyMode(enabled) {
    if (this._flyMode === enabled) return
    this._flyMode = enabled
    if (enabled) {
      // 同步 yaw/pitch：从当前 camera 实际朝向反推（不是从 _spherical，否则
      //   spherical 初始值 (30, 0, π/2) 与真实 camera.position 不一致会导致
      //   look direction 偏离 target，用户看不见图谱）
      const offset = _tmpCamOffset.subVectors(this.camera.position, this.target)
      const len = offset.length()
      if (len > 1e-4) {
        // 当前 look direction = -offset / len（target → position 是反方向）
        // yaw (绕 y): 水平角，从 +z 顺时针
        // pitch: 垂直角，向上为正
        const fx = -offset.x / len
        const fy = -offset.y / len
        const fz = -offset.z / len
        this._flyYaw = Math.atan2(fx, fz)
        this._flyPitch = Math.asin(Math.max(-1, Math.min(1, fy)))
      }
    } else {
      // fly → orbit 切换：从当前 camera.position + target 反推 spherical
      //   否则下一帧 update() 用 _spherical 初始值 (30, 0, π/2) 把相机 teleport 走
      //   同样 target 留在 fly 期间的 camera.position + forward*80，需要复位
      const offset = _tmpCamOffset.subVectors(this.camera.position, this.target)
      const len = offset.length()
      if (len > 1e-4) {
        this._spherical.radius = this._targetSpherical.radius = len
        this._spherical.phi = this._targetSpherical.phi =
          Math.acos(Math.max(-1, Math.min(1, offset.y / len)))
        this._spherical.theta = this._targetSpherical.theta = Math.atan2(offset.x, offset.z)
      }
      // target 复位为相机前方 spherical.radius 单位（避免 fly 留下的 80 单位前瞻）
      this.target.copy(this.camera.position).add(
        _tmpFwd.set(0, 0, -this._spherical.radius),
      )
    }
    this._onFlyModeChange?.(enabled)
  }

  /**
   * 注册碰撞检测 provider（fly mode 限制前进距离）
   * 形参：provider(cameraPos: THREE.Vector3, forward: THREE.Vector3, maxDist: number) → { distance, nodeId, nodeName } | null
   */
  setCollisionProvider(provider) {
    this._collisionProvider = provider
  }

  /**
   * 获取最近阻挡信息（外部 UI 显示"前方 X 米有 Y"）
   */
  getNearestHit() {
    return this._lastHitInfo
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

      if (this._flyMode) {
        // fly 模式：拖拽 = 改 yaw/pitch
        this._flyYaw -= dx * this._flySensitivity * 60
        this._flyPitch -= dy * this._flySensitivity * 60
        this._flyPitch = Math.max(-Math.PI / 2 + 0.05, Math.min(Math.PI / 2 - 0.05, this._flyPitch))
      } else if (e.button === 2 || e.shiftKey) {
        this.camera.updateMatrixWorld()
        const right = new THREE.Vector3()
        const up = new THREE.Vector3()
        const forward = new THREE.Vector3()
        this.camera.matrixWorld.extractBasis(right, up, forward)
        right.multiplyScalar(-dx * this.panSpeed * 0.02)
        up.multiplyScalar(dy * this.panSpeed * 0.02)
        this.target.add(right).add(up)
      } else {
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
      if (this._flyMode) {
        // fly 模式：滚轮调速
        const factor = e.deltaY > 0 ? 0.9 : 1.1
        this._flySpeed = Math.max(this._flySpeedMin, Math.min(this._flySpeedMax, this._flySpeed * factor))
      } else {
        const factor = e.deltaY > 0 ? 1.1 : 0.9
        this._targetSpherical.radius = Math.max(
          this.minDistance,
          Math.min(this.maxDistance, this._targetSpherical.radius * factor),
        )
      }
    }
    this._onContextMenu = (e) => e.preventDefault()

    // ===== 键盘（window 级，Tab 切模式 / WASD/QE/Shift 飞行）=====
    this._onKeyDown = (e) => {
      // 输入框聚焦时不抢键（搜索框打字、PersonPanel 编辑等）
      const tag = (e.target?.tagName || '').toUpperCase()
      if (tag === 'INPUT' || tag === 'TEXTAREA' || e.target?.isContentEditable) return
      if (e.key === 'Tab') {
        e.preventDefault()
        this.setFlyMode(!this._flyMode)
        return
      }
      if (!this._flyMode) return
      const k = e.key.toLowerCase()
      if ('wasdqe'.includes(k)) {
        this._flyKeys[k] = true
        e.preventDefault()
      } else if (e.key === 'Shift') {
        this._flyKeys.shift = true
      }
    }
    this._onKeyUp = (e) => {
      const k = e.key.toLowerCase()
      if ('wasdqe'.includes(k)) this._flyKeys[k] = false
      else if (e.key === 'Shift') this._flyKeys.shift = false
    }

    dom.addEventListener('pointerdown', this._onPointerDown)
    dom.addEventListener('pointermove', this._onPointerMove)
    dom.addEventListener('pointerup', this._onPointerUp)
    dom.addEventListener('wheel', this._onWheel, { passive: false })
    dom.addEventListener('contextmenu', this._onContextMenu)
    window.addEventListener('keydown', this._onKeyDown)
    window.addEventListener('keyup', this._onKeyUp)
  }

  update(dt = 1 / 60) {
    if (this._flyMode) {
      this._updateFly(dt)
    } else {
      if (this.enableDamping) {
        this._spherical.radius += (this._targetSpherical.radius - this._spherical.radius) * this.dampingFactor
        this._spherical.theta += (this._targetSpherical.theta - this._spherical.theta) * this.dampingFactor
        this._spherical.phi += (this._targetSpherical.phi - this._spherical.phi) * this.dampingFactor
      } else {
        Object.assign(this._spherical, this._targetSpherical)
      }
      this._updateCameraFromSpherical()
    }
  }

  _updateFly(dt) {
    const speed = this._flySpeed * (this._flyKeys.shift ? 3 : 1) * dt
    // 方向：yaw=0 时朝 +z；pitch=0 时水平
    const yaw = this._flyYaw
    const pitch = this._flyPitch
    const cosP = Math.cos(pitch)
    const forward = _tmpFwd.set(Math.sin(yaw) * cosP, Math.sin(pitch), Math.cos(yaw) * cosP)
    const right = _tmpRight.set(Math.cos(yaw), 0, -Math.sin(yaw))
    const up = _tmpUp.set(0, 1, 0)

    let mx = 0, my = 0, mz = 0
    if (this._flyKeys.w) { mx += forward.x; my += forward.y; mz += forward.z }
    if (this._flyKeys.s) { mx -= forward.x; my -= forward.y; mz -= forward.z }
    if (this._flyKeys.d) { mx += right.x; mz += right.z }
    if (this._flyKeys.a) { mx -= right.x; mz -= right.z }
    if (this._flyKeys.e) my += 1
    if (this._flyKeys.q) my -= 1

    const len = Math.hypot(mx, my, mz)
    if (len > 0) {
      let k = speed / len
      // ★ 碰撞检测：只在向前（W）方向限制最大步长
      //   横向 / 上下移动不限制（用户可以绕开节点）
      if (this._flyKeys.w && this._collisionProvider) {
        // 把 desired movement 投影到 forward 上（前进分量 = dot(move_dir, forward)）
        const fwdComp = (mx * forward.x + my * forward.y + mz * forward.z) / len
        if (fwdComp > 0) {
          const desiredForward = speed * fwdComp
          const hit = this._collisionProvider(this.camera.position, forward, desiredForward)
          this._lastHitInfo = hit
          if (hit && hit.distance < desiredForward) {
            // 限制前进分量不超过 (hit.distance - 1.0) 留 1 单位缓冲
            const maxForward = Math.max(0, hit.distance - 1.0)
            // 重新分配：原 wanted step 比例 = maxForward / desiredForward
            const scale = maxForward / desiredForward
            k *= scale
          }
        }
      } else if (!this._flyKeys.w) {
        this._lastHitInfo = null
      }
      this.camera.position.x += mx * k
      this.camera.position.y += my * k
      this.camera.position.z += mz * k
    }
    // target 同步到相机前方 80（供 LOD 用 + lookAt）
    this.target.copy(this.camera.position).addScaledVector(forward, 80)
    this.camera.lookAt(this.target)
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
    window.removeEventListener('keydown', this._onKeyDown)
    window.removeEventListener('keyup', this._onKeyUp)
  }
}

// 模块级临时向量（避免每帧 new Vector3）
const _tmpFwd = new THREE.Vector3()
const _tmpRight = new THREE.Vector3()
const _tmpUp = new THREE.Vector3()
const _tmpCamOffset = new THREE.Vector3()

export default {
  bindInteractions,
  flyToNode,
  SimpleOrbitControls,
}
