/**
 * 系统健康状态管理（systemHealth）
 *
 * Why：竞赛交付阶段前端必须感知后端健康状态。
 *   - PASS：全绿
 *   - WARN：可继续，但显示提示条（如 RAG 走 fallback）
 *   - FAIL：触发 SAFE MODE（隐藏 OCR / 智能问答入口、限 5000 节点）
 *
 * 接入：
 *   - App.vue onMounted 调 checkHealth() + setInterval 30s 轮询
 *   - KnowledgeView.vue 读 demoMode / demoNodeLimit / safeMode
 *   - 任意组件可读 overall 判断是否走降级路径
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { systemHealthAPI, demoAPI } from '@/services/api'

export const useSystemHealthStore = defineStore('systemHealth', () => {
  // ==================== 状态 ====================
  const overall = ref('UNKNOWN')         // 'PASS' | 'WARN' | 'FAIL' | 'UNKNOWN'
  const demoMode = ref(false)            // 后端 ZHIJIAN_DEMO_MODE 开关
  const demoNodeLimit = ref(5000)
  const checks = ref([])                 // 后端返回的明细
  const summary = ref({ pass: 0, warn: 0, fail: 0, total: 0 })
  const lastCheckedAt = ref(null)
  const loading = ref(false)
  const lastError = ref(null)

  // ==================== R9 研究叙事模式 ====================
  const narrativeMode = ref(true)   // ZHIJIAN_NARRATIVE_MODE（默认开）
  const juryPack = ref(null)         // 一键评委包缓存
  const juryPackLoading = ref(false)
  const juryPackError = ref(null)
  const juryPackFetchedAt = ref(null)

  // ==================== 计算属性 ====================
  const safeMode = computed(() => overall.value === 'FAIL')
  const isDegraded = computed(() => overall.value === 'WARN' || overall.value === 'FAIL')
  const failedChecks = computed(() => checks.value.filter((c) => c.status === 'FAIL'))
  const warnedChecks = computed(() => checks.value.filter((c) => c.status === 'WARN'))
  const hasRag = computed(() => {
    const rag = checks.value.filter((c) => c.name && c.name.startsWith('rag_'))
    return rag.length > 0 && rag.every((c) => c.status === 'PASS')
  })

  // ==================== Actions ====================
  async function checkHealth() {
    loading.value = true
    lastError.value = null
    try {
      const res = await systemHealthAPI.check()
      overall.value = res.overall || 'UNKNOWN'
      demoMode.value = !!res.demo_mode
      demoNodeLimit.value = res.demo_node_limit || 5000
      checks.value = res.checks || []
      summary.value = res.summary || { pass: 0, warn: 0, fail: 0, total: 0 }
      lastCheckedAt.value = res.checked_at ? new Date(res.checked_at * 1000) : new Date()
      return res
    } catch (e) {
      overall.value = 'FAIL'
      lastError.value = e.response?.data?.message || e.message || '健康检查失败'
      console.warn('[systemHealth] check failed:', e)
      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取某项检查的简明状态（用于 UI 展示）
   */
  function getCheck(name) {
    return checks.value.find((c) => c.name === name) || null
  }

  /**
   * R9: 拉取一键评委包（demo/jury_pack）。
   * 失败 → 缓存为 null + 记录 error，不抛。
   */
  async function fetchJuryPack(force = false) {
    if (juryPack.value && !force && juryPackFetchedAt.value &&
        (Date.now() - juryPackFetchedAt.value) < 5 * 60 * 1000) {
      return juryPack.value
    }
    juryPackLoading.value = true
    juryPackError.value = null
    try {
      const res = await demoAPI.getJuryPack()
      juryPack.value = res
      juryPackFetchedAt.value = Date.now()
      return res
    } catch (e) {
      juryPackError.value = e.response?.data?.message || e.message || '评委包拉取失败'
      console.warn('[systemHealth] jury pack fetch failed:', e)
      return null
    } finally {
      juryPackLoading.value = false
    }
  }

  function setNarrativeMode(v) {
    narrativeMode.value = !!v
  }

  /**
   * 强制重置（手动清除后重新拉）
   */
  function reset() {
    overall.value = 'UNKNOWN'
    checks.value = []
    summary.value = { pass: 0, warn: 0, fail: 0, total: 0 }
    lastCheckedAt.value = null
    lastError.value = null
  }

  return {
    // 状态
    overall,
    demoMode,
    demoNodeLimit,
    checks,
    summary,
    lastCheckedAt,
    loading,
    lastError,

    // 计算
    safeMode,
    isDegraded,
    failedChecks,
    warnedChecks,
    hasRag,

    // R9 叙事模式
    narrativeMode,
    juryPack,
    juryPackLoading,
    juryPackError,
    juryPackFetchedAt,

    // Actions
    checkHealth,
    getCheck,
    fetchJuryPack,
    setNarrativeMode,
    reset,
  }
})
