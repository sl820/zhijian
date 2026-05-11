<template>
  <div class="home-view">
    <!-- Hero区域 -->
    <section class="hero">
      <div class="hero-inner">
        <div class="hero-content animate-fade-in-up">
          <div class="hero-eyebrow">古籍方志智能整理</div>
          <h1 class="hero-title">志鉴</h1>
          <p class="hero-subtitle">数字时代的古籍书房</p>
          <p class="hero-desc">
            融合 OCR 识别、深度学习与知识图谱技术，<br/>
            实现古籍方志的数字化采集、智能校勘与知识挖掘。
          </p>
          <div class="hero-actions">
            <el-button type="primary" size="large" @click="$router.push('/collation')">
              开始校勘
            </el-button>
            <el-button size="large" @click="$router.push('/qa')">
              智能问答
            </el-button>
            <el-button size="large" @click="$router.push('/knowledge')">
              知识图谱
            </el-button>
          </div>
        </div>

        <div class="hero-stats">
          <div class="stat-card animate-fade-in-up stagger-1" v-for="stat in heroStats" :key="stat.label">
            <span class="stat-value">{{ stat.value }}</span>
            <span class="stat-label">{{ stat.label }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 核心模块 -->
    <section class="section">
      <div class="section-inner">
        <div class="section-header">
          <div class="section-title-group">
            <h2 class="section-title">核心模块</h2>
            <p class="section-desc">完整覆盖古籍方志数字化的全流程处理</p>
          </div>
        </div>

        <div class="modules-grid">
          <div
            v-for="(mod, idx) in modules"
            :key="mod.id"
            class="module-card animate-fade-in-up"
            :class="[`stagger-${idx + 1}`, { completed: mod.status === 'completed' }]"
            @click="$router.push(mod.path)"
          >
            <div class="module-accent"></div>
            <div class="module-icon" :style="{ background: mod.color + '18', color: mod.color }">
              <span v-html="mod.icon"></span>
            </div>
            <div class="module-body">
              <h3 class="module-title">{{ mod.name }}</h3>
              <p class="module-desc">{{ mod.description }}</p>
            </div>
            <div class="module-badge">
              <span v-if="mod.status === 'completed'" class="badge badge-success">已完成</span>
              <span v-else class="badge badge-warning">开发中</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 县志数据 -->
    <section class="section section-alt">
      <div class="section-inner">
        <div class="section-header">
          <div class="section-title-group">
            <h2 class="section-title">县志数据</h2>
            <p class="section-desc">多个历史版本的方志文献资源</p>
          </div>
        </div>

        <div class="versions-grid">
          <div v-for="ver in versions" :key="ver.id" class="version-card animate-fade-in-up">
            <div class="version-seal"></div>
            <div class="version-year">{{ ver.year }}</div>
            <h4 class="version-name">{{ ver.name }}</h4>
            <p class="version-desc">{{ ver.description }}</p>
            <div class="version-footer">
              <span class="version-status" :class="ver.status">
                {{ ver.status === 'completed' ? '已完成' : ver.status === 'partial' ? '部分完成' : '待处理' }}
              </span>
              <span v-if="ver.characterCount" class="version-chars">
                {{ formatNumber(ver.characterCount) }} 字
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 技术架构 -->
    <section class="section">
      <div class="section-inner">
        <div class="section-header">
          <div class="section-title-group">
            <h2 class="section-title">技术架构</h2>
            <p class="section-desc">现代化 AI 技术栈支撑智能化处理</p>
          </div>
        </div>

        <div class="tech-grid">
          <div v-for="(techs, category) in techStack" :key="category" class="tech-card animate-fade-in-up">
            <h4 class="tech-category">{{ techLabels[category] }}</h4>
            <div class="tech-list">
              <div v-for="tech in techs" :key="tech.name" class="tech-item">
                <span class="tech-name">{{ tech.name }}</span>
                <span class="tech-version">{{ tech.version }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 系统状态 -->
    <section class="section">
      <div class="section-inner">
        <div class="section-header">
          <div class="section-title-group">
            <h2 class="section-title">系统状态</h2>
            <p class="section-desc">服务连接与模块运行状态</p>
          </div>
          <el-button size="small" @click="checkStatus" class="refresh-btn">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
              <polyline points="23 4 23 10 17 10"/>
              <polyline points="1 20 1 14 7 14"/>
              <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
            </svg>
            刷新
          </el-button>
        </div>

        <div class="status-grid">
          <div class="status-item" :class="apiStatus">
            <span class="status-indicator"></span>
            <span class="status-label">API 服务</span>
            <span class="status-tag" :class="apiStatus === 'connected' ? 'tag-success' : 'tag-danger'">
              {{ apiStatus === 'connected' ? '已连接' : '未连接' }}
            </span>
          </div>
          <div v-for="(mod, name) in moduleStatus" :key="name" class="status-item">
            <span class="status-indicator" :class="mod.ready ? 'ready' : 'pending'"></span>
            <span class="status-label">{{ moduleLabels[name] }}</span>
            <span class="status-tag" :class="mod.ready ? 'tag-success' : 'tag-muted'">
              {{ mod.ready ? '就绪' : '加载中' }}
            </span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useAppStore } from '@/stores/app'
import { MODULES, TECH_STACK, GAZETTEER_VERSIONS, PROJECT_STATS } from '@/constants'

const appStore = useAppStore()
const { apiStatus, moduleStatus } = storeToRefs(appStore)

const modules = ref(MODULES.map((m, i) => ({
  ...m,
  icon: getModuleIcon(m.id),
  status: m.status || (i < 4 ? 'completed' : 'dev')
})))

function getModuleIcon(id) {
  const icons = {
    ocr: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="22" height="22"><path d="M4 7V4h16v3M9 20h6M12 4v16"/></svg>',
    normalize: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="22" height="22"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>',
    collation: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="22" height="22"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
    map: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="22" height="22"><polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>',
    annotation: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="22" height="22"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
    kg: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="22" height="22"><circle cx="12" cy="12" r="3"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="5" r="2"/><line x1="12" y1="9" x2="12" y2="5"/></svg>',
    rag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="22" height="22"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
    compilation: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="22" height="22"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>'
  }
  return icons[id] || icons.ocr
}

const heroStats = [
  { value: String(PROJECT_STATS.totalVersions), label: '版本数据' },
  { value: formatNumber(PROJECT_STATS.totalCharacters), label: '已提取字符' },
  { value: '8', label: '核心模块' },
  { value: '5', label: '历史版本' }
]

const versions = ref(GAZETTEER_VERSIONS)

const techLabels = {
  backend: '后端技术',
  database: '数据库',
  frontend: '前端技术',
  infra: '基础设施'
}

const moduleLabels = {
  ocr: 'OCR 识别',
  normalize: '文本规范',
  collation: '多版本校勘',
  rag: 'RAG 问答'
}

function formatNumber(num) {
  if (!num) return '0'
  return num.toLocaleString()
}

async function checkStatus() {
  await appStore.checkHealth()
}
</script>

<style scoped>
.home-view {
  min-height: calc(100vh - 60px);
  background: var(--bg-primary);
}

/* ==================== Hero ==================== */
.hero {
  background: linear-gradient(180deg, var(--bg-card) 0%, var(--bg-secondary) 100%);
  border-bottom: 1px solid var(--border-light);
  padding: var(--space-4xl) var(--space-xl);
  position: relative;
  overflow: hidden;
}

.hero::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--border-medium), transparent);
}

.hero-inner {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4xl);
}

.hero-content {
  max-width: 520px;
}

.hero-eyebrow {
  font-family: var(--font-serif);
  font-size: 13px;
  color: var(--accent);
  letter-spacing: 0.2em;
  text-transform: uppercase;
  margin-bottom: var(--space-sm);
}

.hero-title {
  font-family: var(--font-display);
  font-size: 80px;
  font-weight: 400;
  color: var(--text-primary);
  margin: 0 0 8px;
  letter-spacing: 0.25em;
  line-height: 1;
}

.hero-subtitle {
  font-family: var(--font-serif);
  font-size: 18px;
  color: var(--text-secondary);
  margin: 0 0 var(--space-lg);
  font-weight: 400;
  letter-spacing: 0.1em;
}

.hero-desc {
  font-size: 15px;
  color: var(--text-secondary);
  line-height: 1.9;
  margin-bottom: var(--space-xl);
}

.hero-actions {
  display: flex;
  gap: var(--space-md);
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-md);
  width: 300px;
  opacity: 0;
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-lg);
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: var(--transition-normal);
}

.stat-card:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.stat-value {
  font-family: var(--font-mono);
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1;
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font-serif);
}

/* ==================== Section ==================== */
.section {
  padding: var(--space-3xl) var(--space-xl);
}

.section-alt {
  background: var(--bg-card);
  border-top: 1px solid var(--border-light);
  border-bottom: 1px solid var(--border-light);
}

.section-inner {
  max-width: 1200px;
  margin: 0 auto;
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-md);
  margin-bottom: var(--space-xl);
}

.section-title-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-xs);
}

.section-title {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 400;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: 0.05em;
}

.section-desc {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0;
  font-family: var(--font-serif);
}

.refresh-btn {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* ==================== 模块网格 ==================== */
.modules-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-lg);
}

.module-card {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-xl);
  cursor: pointer;
  transition: var(--transition-normal);
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  position: relative;
  overflow: hidden;
  opacity: 0;
}

.module-accent {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--accent);
  transform: scaleY(0);
  transform-origin: bottom;
  transition: transform 0.3s var(--ease-out);
}

.module-card:hover .module-accent {
  transform: scaleY(1);
}

.module-card:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-lg);
  transform: translateY(-4px);
}

.module-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.module-body {
  flex: 1;
}

.module-title {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 400;
  color: var(--text-primary);
  margin: 0 0 6px;
  letter-spacing: 0.05em;
}

.module-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.6;
  font-family: var(--font-serif);
}

.module-badge {
  margin-top: auto;
}

.badge {
  display: inline-block;
  padding: 3px 10px;
  font-size: 11px;
  font-weight: 500;
  border-radius: var(--radius-full);
  font-family: var(--font-serif);
}

.badge-success {
  background: var(--success-bg);
  color: var(--success);
}

.badge-warning {
  background: var(--warning-bg);
  color: var(--warning);
}

/* ==================== 版本网格 ==================== */
.versions-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--space-md);
}

.version-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-xl);
  transition: var(--transition-normal);
  position: relative;
  opacity: 0;
}

.version-card:hover {
  border-color: var(--border-medium);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.version-seal {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 20px;
  height: 20px;
  border: 2px solid var(--accent);
  border-radius: 50%;
  opacity: 0.3;
}

.version-year {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 400;
  color: var(--accent);
  margin-bottom: 8px;
  letter-spacing: 0.05em;
}

.version-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0 0 6px;
  font-family: var(--font-serif);
}

.version-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0 0 12px;
  line-height: 1.5;
  font-family: var(--font-serif);
}

.version-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.version-status {
  font-size: 12px;
  font-weight: 500;
  font-family: var(--font-serif);
}

.version-status.completed { color: var(--success); }
.version-status.partial { color: var(--warning); }
.version-status.pending { color: var(--text-muted); }

.version-chars {
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

/* ==================== 技术栈 ==================== */
.tech-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-lg);
}

.tech-card {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-xl);
  opacity: 0;
}

.tech-category {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0 0 var(--space-md);
  padding-bottom: var(--space-sm);
  border-bottom: 1px solid var(--border-light);
  font-family: var(--font-display);
  letter-spacing: 0.05em;
}

.tech-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tech-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.tech-name {
  color: var(--text-secondary);
  font-family: var(--font-serif);
}

.tech-version {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 11px;
}

/* ==================== 状态网格 ==================== */
.status-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-md);
}

.status-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  min-width: 160px;
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
  flex-shrink: 0;
}

.status-item.connected .status-indicator,
.status-indicator.ready {
  background: var(--success);
}

.status-item.checking .status-indicator,
.status-indicator.pending {
  background: var(--warning);
  animation: pulse 1s ease infinite;
}

.status-label {
  flex: 1;
  font-size: 13px;
  color: var(--text-secondary);
  font-family: var(--font-serif);
}

.status-tag {
  font-size: 11px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-family: var(--font-serif);
}

.tag-success {
  background: var(--success-bg);
  color: var(--success);
}

.tag-danger {
  background: var(--danger-bg);
  color: var(--danger);
}

.tag-muted {
  background: var(--bg-secondary);
  color: var(--text-muted);
}

/* ==================== 动画 ==================== */
.animate-fade-in-up {
  animation: fadeInUp 0.6s var(--ease-out) forwards;
}

.stagger-1 { animation-delay: 0.05s; }
.stagger-2 { animation-delay: 0.1s; }
.stagger-3 { animation-delay: 0.15s; }
.stagger-4 { animation-delay: 0.2s; }
.stagger-5 { animation-delay: 0.25s; }
.stagger-6 { animation-delay: 0.3s; }
.stagger-7 { animation-delay: 0.35s; }
.stagger-8 { animation-delay: 0.4s; }

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ==================== 响应式 ==================== */
@media (max-width: 1100px) {
  .hero-inner {
    flex-direction: column;
    gap: var(--space-2xl);
    text-align: center;
  }

  .hero-content {
    max-width: 100%;
  }

  .hero-eyebrow {
    justify-content: center;
    display: flex;
  }

  .hero-stats {
    width: 100%;
    max-width: 400px;
    opacity: 1;
  }

  .modules-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .versions-grid {
    grid-template-columns: repeat(3, 1fr);
  }

  .tech-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .hero {
    padding: var(--space-3xl) var(--space-md);
  }

  .hero-title {
    font-size: 56px;
  }

  .hero-actions {
    flex-wrap: wrap;
    justify-content: center;
  }

  .modules-grid,
  .versions-grid,
  .tech-grid {
    grid-template-columns: 1fr;
  }

  .section {
    padding: var(--space-2xl) var(--space-md);
  }
}
</style>
