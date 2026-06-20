/**
 * 志鉴·星野图考 交互状态真源（Single Source of Truth）
 *
 * Why：KnowledgeView / NebulaCanvas / interaction.js / PersonPanel 原本各自持有
 * selectedNode / hoveredNode / filterState 副本，导致：
 *   - 点击事件可能更新 A 但 B 没更新（"panel 有时不更新"）
 *   - GSAP tween 没集中管理，flyTo 冲突（"camera 与 selection 冲突"）
 *   - filter 切换时旧 selected 引用变成孤儿（"filter 后 scene 不同步"）
 *
 * 改造后所有交互状态集中在本 store，组件只读不写副作用。
 * Three.js 副作用由 nebulaMiddleware.js 集中处理。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useNebulaStore = defineStore('nebula', () => {
  // ==================== Hover / Select 状态 ====================
  const hoveredNodeId = ref(null)
  const hoveredNodeData = ref(null)

  const selectedNodeId = ref(null)
  const selectedNodeData = ref(null)

  // ==================== Filter / Timeline ====================
  const filterCategory = ref(null)  // null | 0 | 1 | 2 | 3
  const filterDynasty = ref('')     // 子串

  // null = 全激活；Set = 仅集合内朝代激活
  const activeDynasties = ref(null)

  // ==================== Layout 同步 ====================
  // 每次 loadLayout 完成时 +1，middleware watch 此变化做 reconciliation
  const layoutVersion = ref(0)

  // 当前 layout 的节点 id 集合（middleware 用作 O(1) 判断 id 是否还在可见集）
  const currentNodeIds = ref(new Set())

  // ==================== Fly Tween 句柄（用于 kill） ====================
  const flyTweenHandle = ref(null)
  const flyTargetId = ref(null)

  // ==================== UI 状态 ====================
  const searchToast = ref('')
  let searchToastTimer = null

  // ==================== Actions ====================

  function setHover(id, data) {
    if (hoveredNodeId.value === id) return
    hoveredNodeId.value = id
    hoveredNodeData.value = data
  }

  function clearHover() {
    if (hoveredNodeId.value === null) return
    hoveredNodeId.value = null
    hoveredNodeData.value = null
  }

  /**
   * 设置选中节点。自动 kill 旧 fly tween（避免连续 click 飞行动画冲突）。
   * data 必须是稳定的 userData 快照（不要传 mesh 引用，layout 切换会失效）。
   */
  function setSelected(id, data) {
    if (selectedNodeId.value === id && selectedNodeData.value?.id === id) {
      return  // 重复点击同一节点：no-op
    }
    killFlyTween()
    selectedNodeId.value = id
    selectedNodeData.value = data
  }

  function clearSelected() {
    killFlyTween()
    selectedNodeId.value = null
    selectedNodeData.value = null
  }

  function setFilterCategory(c) {
    filterCategory.value = c
  }

  function setFilterDynasty(d) {
    filterDynasty.value = d
  }

  function clearFilters() {
    filterCategory.value = null
    filterDynasty.value = ''
  }

  function setActiveDynasties(setOrNull) {
    activeDynasties.value = setOrNull
  }

  function bumpLayout(ids) {
    layoutVersion.value += 1
    currentNodeIds.value = ids instanceof Set ? ids : new Set(ids || [])
  }

  function setFlyTween(handle, targetId) {
    flyTweenHandle.value = handle
    flyTargetId.value = targetId
  }

  function killFlyTween() {
    if (flyTweenHandle.value) {
      try { flyTweenHandle.value.kill?.() } catch (e) { /* ignore */ }
      flyTweenHandle.value = null
      flyTargetId.value = null
    }
  }

  function showSearchToast(msg, ms = 3500) {
    searchToast.value = msg
    if (searchToastTimer) clearTimeout(searchToastTimer)
    searchToastTimer = setTimeout(() => { searchToast.value = '' }, ms)
  }

  return {
    // state
    hoveredNodeId, hoveredNodeData,
    selectedNodeId, selectedNodeData,
    filterCategory, filterDynasty,
    activeDynasties,
    layoutVersion, currentNodeIds,
    flyTweenHandle, flyTargetId,
    searchToast,
    // actions
    setHover, clearHover,
    setSelected, clearSelected,
    setFilterCategory, setFilterDynasty, clearFilters,
    setActiveDynasties,
    bumpLayout,
    setFlyTween, killFlyTween,
    showSearchToast,
  }
})
