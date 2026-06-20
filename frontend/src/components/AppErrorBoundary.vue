<!--
  志鉴 全局错误边界（AppErrorBoundary）

  Why：竞赛答辩时最忌讳白屏 / 控制台红字。
    - 任何子组件抛错（Three.js crash / store undefined / Promise 异常）
      都被 errorCaptured 钩子拦截 → 渲染降级 UI
    - 用户可点"重新加载星图"或"返回首页"
    - 不丢失原错误堆栈（开发模式 console.group 折叠展示）

  How to apply：App.vue 模板里 <AppErrorBoundary> 包裹 <router-view>
                main.js 安装 app.config.errorHandler
-->
<template>
  <div v-if="!hasError" class="error-boundary-wrapper">
    <slot />
  </div>

  <div v-else class="error-boundary-fallback">
    <div class="error-boundary-card">
      <div class="error-boundary-seal">星</div>
      <h2 class="error-boundary-title">星图结构正在恢复</h2>
      <p class="error-boundary-hint">
        渲染过程中遇到异常（常见原因：节点引用失效、视图层 resize 抖动、临时网络问题）。
        可尝试以下恢复方式：
      </p>
      <div class="error-boundary-actions">
        <button class="error-boundary-btn error-boundary-btn-primary" @click="onRetry">
          重新加载星图
        </button>
        <button class="error-boundary-btn" @click="onHome">返回首页</button>
      </div>
      <details v-if="errorInfo" class="error-boundary-details">
        <summary>技术细节（仅开发）</summary>
        <pre>{{ errorInfo }}</pre>
      </details>
    </div>
  </div>
</template>

<script setup>
import { ref, onErrorCaptured } from 'vue'
import { useRouter } from 'vue-router'

const hasError = ref(false)
const errorInfo = ref('')
const router = useRouter()

/**
 * 拦截子组件抛错
 * - 上报父级 chain 不阻断 → errorCaptured 返回 false
 * - 触发降级 UI
 * - 兜底 console.group（不污染生产 console）
 */
onErrorCaptured((err, instance, info) => {
  hasError.value = true
  errorInfo.value = `${err?.message || err}\n${err?.stack || ''}\n[Vue info] ${info}`
  // 仅在开发环境分组打印
  if (import.meta.env.DEV) {
    console.groupCollapsed('[AppErrorBoundary] caught error')
    console.error(err)
    console.error('Vue info:', info)
    console.error('Component:', instance)
    console.groupEnd()
  }
  return false  // 不阻断 → 降级 UI 接管
})

function onRetry() {
  hasError.value = false
  errorInfo.value = ''
  router.go(0)  // 强制 reload 当前路由
}

function onHome() {
  hasError.value = false
  errorInfo.value = ''
  router.push('/')
}
</script>

<style scoped>
.error-boundary-wrapper {
  display: contents;
}

.error-boundary-fallback {
  position: fixed;
  inset: 0;
  background: rgba(13, 13, 18, 0.96);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  font-family: var(--font-display, 'LXGW WenKai TC', serif);
}

.error-boundary-card {
  max-width: 480px;
  padding: 32px 36px;
  background: var(--ink-main);
  border: 1px solid var(--cinnabar-seal);
  border-radius: 6px;
  text-align: center;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
}

.error-boundary-seal {
  width: 56px;
  height: 56px;
  margin: 0 auto 16px;
  background: var(--cinnabar-seal);
  color: var(--paper-hi);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  border-radius: 4px;
  box-shadow: 0 0 18px rgba(168, 48, 42, 0.4);
  font-weight: 500;
  letter-spacing: 0;
}

.error-boundary-title {
  margin: 0 0 12px;
  color: var(--paper-hi);
  font-size: 20px;
  font-weight: 500;
  letter-spacing: 0.3em;
}

.error-boundary-hint {
  margin: 0 0 24px;
  color: var(--ink-wash);
  font-size: 13px;
  line-height: 1.7;
  letter-spacing: 0.05em;
}

.error-boundary-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}

.error-boundary-btn {
  padding: 8px 20px;
  background: transparent;
  border: 1px solid var(--ink-mid);
  color: var(--ink-wash);
  font-family: inherit;
  font-size: 14px;
  letter-spacing: 0.15em;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.2s;
}

.error-boundary-btn:hover {
  border-color: var(--cinnabar-seal);
  color: var(--paper-hi);
}

.error-boundary-btn-primary {
  background: var(--cinnabar-faint);
  border-color: var(--cinnabar-seal);
  color: var(--paper-hi);
}

.error-boundary-btn-primary:hover {
  background: rgba(168, 48, 42, 0.3);
  box-shadow: 0 0 12px rgba(168, 48, 42, 0.4);
}

.error-boundary-details {
  margin-top: 20px;
  text-align: left;
  color: var(--ink-pale);
  font-size: 11px;
}

.error-boundary-details summary {
  cursor: pointer;
  padding: 4px 0;
  letter-spacing: 0.1em;
}

.error-boundary-details pre {
  background: rgba(0, 0, 0, 0.4);
  padding: 10px 12px;
  border-radius: 3px;
  font-size: 11px;
  max-height: 160px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 8px 0 0;
  font-family: 'Cascadia Code', 'Consolas', monospace;
}
</style>
