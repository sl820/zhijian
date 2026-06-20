/**
 * 志鉴·星野图考 节点注册中心（NodeRegistry）
 *
 * R7 升级：typed-array 池 + 零分配遍历
 * 目标：33k 节点 stable 60FPS，render loop 零 array allocation
 *
 * 数据架构（双层）：
 *   - 业务层（id-based）：_map<id, mesh>  ← interaction/store/middleware 用
 *   - 渲染层（index-based）：
 *       _idToIndex: Map<id, idx>      // id → 索引
 *       _meshArray: Array<Mesh>       // 稠密，swap-remove 维护
 *       _visible: Uint8Array          // 0/1
 *       _bucket:  Uint8Array          // 0-3 distance bucket
 *       _rank:    Uint16Array         // 重要度
 *       _sphereCx/Cy/Cz/R: Float32Array  // bounding sphere
 *
 * 渲染热路径只读 typed array + 写 typed array，
 * 零 string key lookup，零中间 array allocation。
 *
 * 关键不变量：
 *   - _meshArray 是稠密的（swap-remove 维护，无 null）
 *   - _idToIndex[id] 永远等于 _meshArray 中该 mesh 的位置
 *   - cullCache 容量 ≥ _meshArray.length
 */
export class NodeRegistry {
  constructor() {
    // ===== 业务层 =====
    this._map = new Map()           // id -> mesh
    this._idToIndex = new Map()     // id -> index
    this._version = 0
    this._dirty = true

    // ===== 渲染层（typed-array pool） =====
    this._meshArray = []            // index -> mesh（稠密）
    this._capacity = 0              // typed array 当前容量

    this._visible = new Uint8Array(0)
    this._bucket  = new Uint8Array(0)
    this._rank    = new Uint16Array(0)
    this._sphereCx = new Float32Array(0)
    this._sphereCy = new Float32Array(0)
    this._sphereCz = new Float32Array(0)
    this._sphereR  = new Float32Array(0)
  }

  // ============================================================
  // 内部：typed array 容量按 2× 增长
  // ============================================================
  _ensureCapacity(needed) {
    if (needed <= this._capacity) return
    const newCap = Math.max(needed, this._capacity === 0 ? 4096 : this._capacity * 2)
    const grow = (arr, ctor) => {
      const next = new ctor(newCap)
      if (arr.length > 0) next.set(arr)
      return next
    }
    this._visible   = grow(this._visible,   Uint8Array)
    this._bucket    = grow(this._bucket,    Uint8Array)
    this._rank      = grow(this._rank,      Uint16Array)
    this._sphereCx  = grow(this._sphereCx,  Float32Array)
    this._sphereCy  = grow(this._sphereCy,  Float32Array)
    this._sphereCz  = grow(this._sphereCz,  Float32Array)
    this._sphereR   = grow(this._sphereR,   Float32Array)
    this._capacity  = newCap
  }

  // ============================================================
  // 业务层 CRUD
  // ============================================================

  add(nodeId, mesh) {
    if (!nodeId || !mesh) return
    if (this._map.has(nodeId)) {
      console.warn(`[NodeRegistry] duplicate add for id=${nodeId}, overwriting`)
      this.remove(nodeId)
    }
    this._map.set(nodeId, mesh)

    const idx = this._meshArray.length
    this._meshArray.push(mesh)
    this._idToIndex.set(nodeId, idx)
    this._ensureCapacity(idx + 1)

    // 初始化渲染层槽位
    this._visible[idx] = 1
    this._bucket[idx]  = 255
    this._rank[idx]    = 0
    this._sphereCx[idx] = 0
    this._sphereCy[idx] = 0
    this._sphereCz[idx] = 0
    this._sphereR[idx]  = 0

    this._dirty = true
  }

  get(nodeId) {
    if (!nodeId) return null
    return this._map.get(nodeId) || null
  }

  has(nodeId) {
    return this._map.has(nodeId)
  }

  /**
   * Swap-remove：保持 _meshArray 稠密（无 null 槽位）
   * 同时更新 idToIndex 映射（被 swap 进来的 mesh 的 idx 会变）
   */
  remove(nodeId) {
    const mesh = this._map.get(nodeId)
    if (!mesh) return null
    this._map.delete(nodeId)

    const idx = this._idToIndex.get(nodeId)
    if (idx === undefined) return mesh
    this._idToIndex.delete(nodeId)

    const lastIdx = this._meshArray.length - 1
    if (idx === lastIdx) {
      this._meshArray.pop()
    } else {
      // swap-remove: 把 last 移到 gap，pop
      const lastMesh = this._meshArray[lastIdx]
      const lastId = lastMesh?.userData?.id || lastMesh?.userData?.uri
      this._meshArray[idx] = lastMesh
      this._meshArray.pop()
      // 复制 last 的渲染数据到 idx
      this._visible[idx]   = this._visible[lastIdx]
      this._bucket[idx]    = this._bucket[lastIdx]
      this._rank[idx]      = this._rank[lastIdx]
      this._sphereCx[idx]  = this._sphereCx[lastIdx]
      this._sphereCy[idx]  = this._sphereCy[lastIdx]
      this._sphereCz[idx]  = this._sphereCz[lastIdx]
      this._sphereR[idx]   = this._sphereR[lastIdx]
      // 更新被 swap 的 mesh 的 id 映射
      if (lastId) this._idToIndex.set(lastId, idx)
    }
    // 清空 last 槽位
    this._visible[lastIdx]   = 0
    this._bucket[lastIdx]    = 0
    this._rank[lastIdx]      = 0
    this._sphereCx[lastIdx]  = 0
    this._sphereCy[lastIdx]  = 0
    this._sphereCz[lastIdx]  = 0
    this._sphereR[lastIdx]   = 0

    this._dirty = true
    return mesh
  }

  clear() {
    const oldSize = this._map.size
    this._map.clear()
    this._idToIndex.clear()
    this._meshArray.length = 0
    if (this._capacity > 0) {
      this._visible.fill(0)
      this._bucket.fill(0)
      this._rank.fill(0)
      this._sphereCx.fill(0)
      this._sphereCy.fill(0)
      this._sphereCz.fill(0)
      this._sphereR.fill(0)
    }
    this._version++
    this._dirty = true
    return oldSize
  }

  // ============================================================
  // 业务层迭代（保留供 interaction.js 用，注意会触发 array spread）
  // ============================================================
  values() { return this._map.values() }
  keys() { return this._map.keys() }
  entries() { return this._map.entries() }
  get size() { return this._map.size }
  get version() { return this._version }

  // ============================================================
  // 脏标记
  // ============================================================
  markDirty() { this._dirty = true }
  isDirty() { return this._dirty }
  clearDirty() { this._dirty = false }

  // ============================================================
  // 渲染层热路径 API（零分配，typed array 访问）
  // ============================================================

  /**
   * 零分配遍历稠密 meshArray。
   * 回调签名: (mesh, index) => void
   * 性能：33k 次回调无 array allocation，无 string lookup。
   */
  forEach(callback) {
    const arr = this._meshArray
    for (let i = 0, n = arr.length; i < n; i++) {
      callback(arr[i], i)
    }
  }

  /**
   * id → index 查询（O(1) Map.get）。
   * 找不到返回 -1。
   */
  indexOf(nodeId) {
    const idx = this._idToIndex.get(nodeId)
    return idx === undefined ? -1 : idx
  }

  getMeshAt(index) {
    return this._meshArray[index] ?? null
  }

  get meshArray() { return this._meshArray }
  get idToIndex() { return this._idToIndex }

  /**
   * Cull cache：所有渲染层 typed array 集合。
   * 用法：
   *   const cache = registry.cullCache
   *   const rank = cache.rank[i]              // Uint16Array 读
   *   cache.visible[i] = 1                    // Uint8Array 写
   *   _sphere.center.set(cache.sphereCx[i], …)
   */
  get cullCache() {
    return {
      visible: this._visible,
      bucket: this._bucket,
      rank: this._rank,
      sphereCx: this._sphereCx,
      sphereCy: this._sphereCy,
      sphereCz: this._sphereCz,
      sphereR: this._sphereR,
      capacity: this._capacity,
    }
  }

  /**
   * 渲染层写入：buildImportanceAndSpheres 调用
   */
  setRank(index, rank) {
    if (index >= 0 && index < this._meshArray.length) {
      this._rank[index] = rank
    }
  }

  setSphere(index, x, y, z, r) {
    if (index >= 0 && index < this._meshArray.length) {
      this._sphereCx[index] = x
      this._sphereCy[index] = y
      this._sphereCz[index] = z
      this._sphereR[index]  = r
    }
  }

  // ============================================================
  // 调试
  // ============================================================
  integrityCheck(scene) {
    const orphans = []
    for (const [id, mesh] of this._map) {
      if (!mesh.parent) { orphans.push(id); continue }
      let p = mesh.parent, inScene = false
      while (p) {
        if (p === scene) { inScene = true; break }
        p = p.parent
      }
      if (!inScene) orphans.push(id)
    }
    return { ok: orphans.length === 0, orphans }
  }
}

export default NodeRegistry
