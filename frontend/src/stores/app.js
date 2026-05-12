/**
 * 志鉴系统全局状态管理
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { healthAPI } from '@/services/api'

export const useAppStore = defineStore('app', () => {
  // ==================== 状态定义 ====================

  // API连接状态
  const apiStatus = ref('disconnected') // 'connected' | 'disconnected' | 'checking'
  const lastHealthCheck = ref(null)

  // 模块就绪状态
  const moduleStatus = ref({
    ocr: { ready: false, loading: false, error: null },
    normalize: { ready: false, loading: false, error: null },
    collation: { ready: false, loading: false, error: null },
    rag: { ready: false, loading: false, error: null }
  })

  // 全局加载状态
  const globalLoading = ref(false)
  const loadingMessage = ref('')

  // 全局消息
  const messages = ref([])

  // 当前项目信息
  const projectInfo = ref({
    name: '志鉴',
    subtitle: '古籍方志智能化整理与知识服务平台',
    version: 'v1.0'
  })

  // ==================== 计算属性 ====================

  const isApiConnected = computed(() => apiStatus.value === 'connected')

  const allModulesReady = computed(() => {
    return Object.values(moduleStatus.value).every(m => m.ready)
  })

  const readyModulesCount = computed(() => {
    return Object.values(moduleStatus.value).filter(m => m.ready).length
  })

  // ==================== Actions ====================

  /**
   * 检查API健康状态
   */
  async function checkHealth() {
    apiStatus.value = 'checking'
    try {
      const res = await healthAPI.check()
      apiStatus.value = 'connected'
      lastHealthCheck.value = new Date()
      console.log('[Store] API健康检查成功', res)
      return true
    } catch (error) {
      apiStatus.value = 'disconnected'
      console.error('[Store] API健康检查失败', error)
      return false
    }
  }

  /**
   * 更新模块状态
   */
  function setModuleStatus(moduleName, status) {
    if (moduleStatus.value[moduleName]) {
      moduleStatus.value[moduleName] = { ...moduleStatus.value[moduleName], ...status }
    }
  }

  /**
   * 设置全局加载状态
   */
  function setGlobalLoading(loading, message = '') {
    globalLoading.value = loading
    loadingMessage.value = message
  }

  /**
   * 添加消息
   */
  function addMessage(message, type = 'info') {
    const msg = {
      id: Date.now(),
      message,
      type, // 'success' | 'warning' | 'error' | 'info'
      timestamp: new Date()
    }
    messages.value.push(msg)

    // 5秒后自动移除
    setTimeout(() => {
      removeMessage(msg.id)
    }, 5000)

    return msg
  }

  /**
   * 移除消息
   */
  function removeMessage(id) {
    const index = messages.value.findIndex(m => m.id === id)
    if (index !== -1) {
      messages.value.splice(index, 1)
    }
  }

  /**
   * 显示成功消息
   */
  function showSuccess(message) {
    return addMessage(message, 'success')
  }

  /**
   * 显示警告消息
   */
  function showWarning(message) {
    return addMessage(message, 'warning')
  }

  /**
   * 显示错误消息
   */
  function showError(message) {
    return addMessage(message, 'error')
  }

  /**
   * 显示信息消息
   */
  function showInfo(message) {
    return addMessage(message, 'info')
  }

  return {
    // 状态
    apiStatus,
    lastHealthCheck,
    moduleStatus,
    globalLoading,
    loadingMessage,
    messages,
    projectInfo,

    // 计算属性
    isApiConnected,
    allModulesReady,
    readyModulesCount,

    // Actions
    checkHealth,
    setModuleStatus,
    setGlobalLoading,
    addMessage,
    removeMessage,
    showSuccess,
    showWarning,
    showError,
    showInfo
  }
})
