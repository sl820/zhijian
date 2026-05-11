<template>
  <div id="app">
    <div class="app-layout">
      <!-- 顶部导航 -->
      <header class="app-header">
        <div class="header-inner">
          <!-- Logo -->
          <router-link to="/" class="logo">
            <div class="logo-mark">志</div>
            <div class="logo-text">
              <span class="logo-name">志鉴</span>
              <span class="logo-tagline">古籍方志智能整理</span>
            </div>
          </router-link>

          <!-- 主导航 -->
          <nav class="main-nav">
            <router-link
              v-for="item in navItems"
              :key="item.path"
              :to="item.path"
              class="nav-link"
              :class="{ active: activeRoute === item.path }"
            >
              <span class="nav-icon" v-html="item.icon"></span>
              <span class="nav-label">{{ item.name }}</span>
            </router-link>
          </nav>

          <!-- 状态 -->
          <div class="header-right">
            <button class="status-badge" :class="apiStatus" @click="checkApiStatus">
              <span class="status-dot"></span>
              <span class="status-label">{{ statusLabel }}</span>
            </button>
          </div>
        </div>
      </header>

      <!-- 主内容 -->
      <main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>

    <!-- 全局消息 -->
    <transition name="msg-slide">
      <div v-if="messages.length > 0" class="global-messages">
        <div v-for="msg in messages" :key="msg.id" :class="['msg-toast', msg.type]">
          <span class="msg-icon" v-html="getIcon(msg.type)"></span>
          <span class="msg-text">{{ msg.message }}</span>
          <button class="msg-close" @click="removeMessage(msg.id)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>
    </transition>

    <!-- 全局加载 -->
    <transition name="fade">
      <div v-if="globalLoading" class="global-loading">
        <div class="loading-spinner"></div>
        <span v-if="loadingMessage" class="loading-text">{{ loadingMessage }}</span>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAppStore } from '@/stores/app'

const route = useRoute()
const appStore = useAppStore()
const { apiStatus, messages, globalLoading, loadingMessage } = storeToRefs(appStore)

const activeRoute = computed(() => route.path)

const navItems = [
  {
    path: '/',
    name: '首页',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>'
  },
  {
    path: '/collation',
    name: '多版本校勘',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>'
  },
  {
    path: '/compilation',
    name: '多源辑佚',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>'
  },
  {
    path: '/knowledge',
    name: '知识图谱',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><circle cx="12" cy="12" r="3"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="5" r="2"/><line x1="12" y1="9" x2="12" y2="5"/></svg>'
  },
  {
    path: '/qa',
    name: '智能问答',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>'
  },
  {
    path: '/map',
    name: '舆图提取',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>'
  },
  {
    path: '/annotation',
    name: '批校提取',
    icon: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16"><path d="M12 19l7-7 3 3-7 7-3-3z"/><path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/></svg>'
  }
]

const statusLabel = computed(() => {
  switch (apiStatus.value) {
    case 'connected': return '系统就绪'
    case 'checking': return '连接中'
    default: return '等待连接'
  }
})

async function checkApiStatus() {
  await appStore.checkHealth()
}

function removeMessage(id) {
  appStore.removeMessage(id)
}

function getIcon(type) {
  const icons = {
    success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
    error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
  }
  return icons[type] || icons.info
}

let healthInterval = null

onMounted(async () => {
  await appStore.checkHealth()
  healthInterval = setInterval(() => appStore.checkHealth(), 30000)
})

onUnmounted(() => {
  if (healthInterval) clearInterval(healthInterval)
})
</script>

<style scoped>
.app-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}

/* ==================== 顶部导航 ==================== */
.app-header {
  height: 60px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: var(--shadow-xs);
}

.header-inner {
  max-width: 1400px;
  margin: 0 auto;
  height: 100%;
  display: flex;
  align-items: center;
  padding: 0 var(--space-xl);
  gap: var(--space-xl);
}

/* Logo - 印章风格 */
.logo {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-shrink: 0;
  text-decoration: none;
  transition: var(--transition-fast);
}

.logo:hover {
  opacity: 0.85;
}

.logo-mark {
  width: 38px;
  height: 38px;
  background: var(--accent);
  color: var(--text-inverse);
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 400;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  letter-spacing: 0;
}

.logo-text {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.logo-name {
  font-family: var(--font-display);
  font-size: 18px;
  color: var(--text-primary);
  line-height: 1.2;
  letter-spacing: 0.15em;
}

.logo-tagline {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.2;
  font-family: var(--font-serif);
}

/* 主导航 */
.main-nav {
  display: flex;
  align-items: center;
  gap: var(--space-xs);
  flex: 1;
  justify-content: center;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  text-decoration: none;
  color: var(--text-secondary);
  font-size: 14px;
  font-family: var(--font-serif);
  border-radius: var(--radius-md);
  transition: var(--transition-fast);
  white-space: nowrap;
  position: relative;
}

.nav-link:hover {
  color: var(--accent);
  background: var(--accent-bg);
}

.nav-link.active {
  color: var(--accent);
  background: var(--accent-bg);
}

.nav-link.active::after {
  content: '';
  position: absolute;
  bottom: 2px;
  left: 50%;
  transform: translateX(-50%);
  width: 16px;
  height: 2px;
  background: var(--accent);
  border-radius: 1px;
}

.nav-icon {
  display: flex;
  align-items: center;
  opacity: 0.65;
  transition: opacity var(--transition-fast);
}

.nav-link:hover .nav-icon,
.nav-link.active .nav-icon {
  opacity: 1;
}

/* 状态 */
.header-right {
  flex-shrink: 0;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: var(--transition-fast);
}

.status-badge:hover {
  border-color: var(--border-medium);
  background: var(--bg-card);
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-muted);
}

.status-badge.connected .status-dot {
  background: var(--success);
  box-shadow: 0 0 0 3px rgba(90, 138, 106, 0.15);
}

.status-badge.checking .status-dot {
  background: var(--warning);
  animation: pulse 1s ease infinite;
}

.status-label {
  font-size: 13px;
  color: var(--text-secondary);
  font-family: var(--font-serif);
}

/* ==================== 主内容 ==================== */
.app-main {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

/* ==================== 全局消息 ==================== */
.global-messages {
  position: fixed;
  bottom: var(--space-lg);
  right: var(--space-lg);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.msg-toast {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 12px 16px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  font-size: 14px;
  min-width: 280px;
  border-left: 3px solid var(--text-muted);
  animation: slideInRight 0.3s var(--ease-out);
}

.msg-toast.success { border-left-color: var(--success); }
.msg-toast.error { border-left-color: var(--danger); }
.msg-toast.warning { border-left-color: var(--warning); }
.msg-toast.info { border-left-color: var(--info); }

.msg-icon {
  display: flex;
  flex-shrink: 0;
}

.msg-toast.success .msg-icon { color: var(--success); }
.msg-toast.error .msg-icon { color: var(--danger); }
.msg-toast.warning .msg-icon { color: var(--warning); }
.msg-toast.info .msg-icon { color: var(--info); }

.msg-text {
  flex: 1;
  color: var(--text-primary);
  font-family: var(--font-serif);
}

.msg-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: var(--radius-sm);
  flex-shrink: 0;
  transition: var(--transition-fast);
}

.msg-close:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

/* ==================== 全局加载 ==================== */
.global-loading {
  position: fixed;
  inset: 0;
  background: rgba(244, 239, 230, 0.92);
  backdrop-filter: blur(8px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
  z-index: 99999;
}

.loading-spinner {
  width: 36px;
  height: 36px;
  border: 2.5px solid var(--border-light);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.loading-text {
  font-size: 14px;
  color: var(--text-secondary);
  font-family: var(--font-serif);
}

/* ==================== 过渡动画 ==================== */
.page-enter-active,
.page-leave-active {
  transition: opacity 0.25s ease, transform 0.25s var(--ease-out);
}

.page-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.page-leave-to {
  opacity: 0;
}

.msg-slide-enter-active,
.msg-slide-leave-active {
  transition: all 0.3s var(--ease-out);
}

.msg-slide-enter-from,
.msg-slide-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translateX(24px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* ==================== 响应式 ==================== */
@media (max-width: 1024px) {
  .logo-tagline {
    display: none;
  }

  .nav-label {
    display: none;
  }

  .nav-link {
    padding: 8px 12px;
  }

  .header-inner {
    padding: 0 var(--space-md);
    gap: var(--space-md);
  }
}

@media (max-width: 768px) {
  .app-header {
    height: 54px;
  }

  .status-label {
    display: none;
  }
}
</style>
