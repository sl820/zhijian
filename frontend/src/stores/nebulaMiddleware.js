/**
 * 志鉴·星野图考 副作用中间层（Middleware）
 *
 * 集中处理 store 变化 → Three.js / Vue 副作用
 * 不允许组件内 onClick 直接 setNodeState / flyTo / highlight（已通过 interaction.js 改 emit 阻断）
 *
 * 调用方式：
 *   NebulaCanvas onMounted 时调用 installNebulaMiddleware(store, () => canvasRef.value)
 *   store 是 useNebulaStore() 实例
 *   getCanvas 返回 NebulaCanvas 的 expose 引用
 *
 * Why：
 *   - 旧版 onClick 在 interaction.js 内部 setNodeState + flyTo + setSelectedEdges
 *     三个副作用直接改 scene，与 Vue 状态不同步。
 *   - 旧版 filter 变化只触发 loadLayout，layout 切换后旧 selectedNode 引用变孤儿。
 *   - 旧版搜索命中调 onNodeClick(target)，target 不是 mesh，flyTo 不触发。
 *
 * 改造后所有副作用经此层，行为可预测：
 *   store.selectedNodeId 变 → middleware 找 mesh → setNodeState + highlight + flyTo
 *   store.layoutVersion 变 → middleware 检查 id 是否还在 → 在则重高亮，不在则 clearSelected
 *   store.hoveredNodeId 变 → middleware 设 hover state
 *   store.filter* 变 → middleware 触发 loadLayout
 */
import { watch } from 'vue'
import { setNodeState } from '../components/nebula/PersonNode.js'
import { highlightEdgesForNode } from '../components/nebula/RelationEdge.js'

export function installNebulaMiddleware(store, getCanvas) {
  // getCanvas: () => NebulaCanvas vm | null
  // NebulaCanvas 必须 expose: findNodeById, highlightEdges, clearEdgeHighlight, flyToNode, loadLayout

  let dynastyDebounceTimer = null

  // ============================================================
  // 1. selectedNodeId 变化 → 触发 highlight + flyTo
  // ============================================================
  watch(
    () => store.selectedNodeId,
    async (newId, oldId) => {
      const canvas = getCanvas()
      if (!canvas) return

      // 还原旧节点 idle（不在 setTimeout 异步中，因为 layout 可能已重建）
      if (oldId && oldId !== newId) {
        const oldMesh = canvas.findNodeById(oldId)
        if (oldMesh && oldMesh.userData?.state !== 'idle') {
          setNodeState(oldMesh, 'idle')
        }
        // 清旧关联边高亮
        if (canvas.edgesGroup) {
          highlightEdgesForNode(canvas.edgesGroup, oldId, false, 0)
        }
      }

      // 设置新节点
      if (newId) {
        // 容错：等 layout 同步（搜索触发的选择可能 layout 还没切完）
        let newMesh = canvas.findNodeById(newId)
        let attempts = 0
        while (!newMesh && attempts < 8) {
          await new Promise((r) => setTimeout(r, 25))
          newMesh = canvas.findNodeById(newId)
          attempts++
        }

        if (newMesh) {
          setNodeState(newMesh, 'selected')
          if (canvas.edgesGroup) {
            highlightEdgesForNode(canvas.edgesGroup, newId, true, performance.now() * 0.001)
          }
          canvas.flyToNode(newId, true)
        } else {
          // 节点不在当前可见集（被 filter 掉了 或 layout 还没准备好）
          // 清空 selection，防止 panel 显示一个看不见的节点的脏数据
          store.clearSelected()
        }
      }
    },
  )

  // ============================================================
  // 2. hoveredNodeId 变化 → hover state + tooltip
  // ============================================================
  watch(
    () => store.hoveredNodeId,
    (newId, oldId) => {
      const canvas = getCanvas()
      if (!canvas) return

      if (oldId && oldId !== newId) {
        const oldMesh = canvas.findNodeById(oldId)
        if (oldMesh && oldMesh.userData?.state !== 'selected') {
          setNodeState(oldMesh, 'idle')
        }
        if (canvas.edgesGroup) {
          highlightEdgesForNode(canvas.edgesGroup, oldId, false, 0)
        }
      }
      if (newId) {
        const newMesh = canvas.findNodeById(newId)
        if (newMesh && newMesh.userData?.state !== 'selected') {
          setNodeState(newMesh, 'hover')
          if (canvas.edgesGroup) {
            highlightEdgesForNode(canvas.edgesGroup, newId, true, performance.now() * 0.001)
          }
        }
      }
    },
  )

  // ============================================================
  // 3. filter 变化 → 触发 loadLayout（带防抖）
  // ============================================================
  // category 是 dropdown，变化立即触发
  watch(
    () => store.filterCategory,
    (newCat) => {
      if (newCat !== null) {
        const canvas = getCanvas()
        canvas?.loadLayout?.()
      }
    },
  )

  // dynasty 是输入框，debounce 400ms
  watch(
    () => store.filterDynasty,
    () => {
      if (dynastyDebounceTimer) clearTimeout(dynastyDebounceTimer)
      dynastyDebounceTimer = setTimeout(() => {
        const canvas = getCanvas()
        canvas?.loadLayout?.()
      }, 400)
    },
  )

  // ============================================================
  // 4. layoutVersion 变化 → reconciliation
  //    关键修复：filter 切换后旧 selectedNode 引用孤儿问题
  // ============================================================
  watch(
    () => store.layoutVersion,
    () => {
      const canvas = getCanvas()
      if (!canvas) return

      if (store.selectedNodeId) {
        // 检查 selected id 是否还在新 layout 的可见集
        if (!store.currentNodeIds.has(store.selectedNodeId)) {
          // 节点已被 filter 排除 → 清空 selection
          store.clearSelected()
        } else {
          // 节点还在 → 重新 highlight（不重 flyTo，避免用户切换 filter 后相机乱跳）
          const mesh = canvas.findNodeById(store.selectedNodeId)
          if (mesh) {
            setNodeState(mesh, 'selected')
            if (canvas.edgesGroup) {
              highlightEdgesForNode(canvas.edgesGroup, store.selectedNodeId, true, performance.now() * 0.001)
            }
          }
        }
      }
    },
  )

  // ============================================================
  // 5. activeDynasties 变化由 NebulaCanvas 的 prop 监听处理
  //    （无副作用在 middleware 中需要做，但保留注释说明分流）
  // ============================================================

  // 卸载钩子（页面 unmount 时调用）
  return function uninstall() {
    if (dynastyDebounceTimer) clearTimeout(dynastyDebounceTimer)
  }
}
