<template>
  <div class="knowledge-view">
    <!-- 顶部栏 -->
    <header class="page-header">
      <div class="header-left">
        <h1 class="page-title">知识图谱</h1>
        <p class="page-subtitle">人物关系 · 知识网络</p>
      </div>
      <div class="header-right">
        <div class="search-box">
          <input
            v-model="searchName"
            placeholder="搜索人物..."
            class="search-input"
            @input="onSearchInput"
            @keyup.enter="searchPerson"
          />
          <button class="search-btn" @click="searchPerson">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
          </button>
        </div>
        <button
          class="btn-primary"
          :disabled="initializing || kgInitialized"
          @click="initKG"
        >
          <svg v-if="!kgInitialized" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <polyline points="20 6 9 17 4 12"/>
          </svg>
          {{ kgInitialized ? '已初始化' : initializing ? '初始化中...' : '初始化图谱' }}
        </button>
      </div>
    </header>

    <!-- 主内容 -->
    <div class="main-content">
      <el-row :gutter="24">
        <!-- 图谱区域 -->
        <el-col :span="16">
          <div class="graph-card">
            <!-- 图例 -->
            <div class="graph-legend">
              <span class="legend-title">图例</span>
              <div class="legend-items">
                <div v-for="cat in categories" :key="cat.name" class="legend-item">
                  <span class="legend-dot" :style="{ backgroundColor: cat.color }"></span>
                  <span class="legend-name">{{ cat.name }}</span>
                </div>
              </div>
            </div>

            <!-- 图谱容器 -->
            <div ref="chartRef" class="graph-container" v-show="!kgEmpty"></div>

            <!-- 空状态 -->
            <div v-if="kgEmpty" class="empty-state">
              <p class="empty-title">知识图谱为空</p>
              <p class="empty-hint" v-if="initError">初始化失败，请重试</p>
              <p class="empty-hint" v-else-if="!kgInitialized">点击右上角「初始化图谱」按钮开始构建</p>
              <p class="empty-hint" v-else>暂无图谱数据</p>
              <button v-if="initError" class="btn-primary empty-retry" @click="initKG">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                  <polyline points="23 4 23 10 17 10"/>
                  <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                </svg>
                重试初始化
              </button>
            </div>

            <!-- 节点过多简化提示 -->
            <div v-if="graphSimplified" class="simplify-banner">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
              </svg>
              <span>节点数较多（{{ nodeCount }}），已自动简化力导向布局</span>
            </div>

            <!-- 统计 -->
            <div class="graph-stats" v-if="!kgEmpty">
              <span>{{ nodeCount }} 人物</span>
              <span class="stat-sep">／</span>
              <span>{{ linkCount }} 关系</span>
            </div>

            <!-- 缩放控制 -->
            <div class="zoom-controls" v-if="!kgEmpty">
              <button class="zoom-btn" @click="zoomIn" title="放大">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                  <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
              </button>
              <button class="zoom-btn" @click="zoomOut" title="缩小">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                  <line x1="5" y1="12" x2="19" y2="12"/>
                </svg>
              </button>
              <button class="zoom-btn" @click="fitView" title="适应画布">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                  <polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/>
                  <line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/>
                </svg>
              </button>
              <button class="zoom-btn" @click="refreshGraph" title="刷新">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                  <polyline points="23 4 23 10 17 10"/>
                  <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
                </svg>
              </button>
            </div>
          </div>
        </el-col>

        <!-- 详情面板 -->
        <el-col :span="8">
          <!-- 人物详情 -->
          <div v-if="personLoading" class="person-card person-loading">
            <el-skeleton :rows="6" animated />
          </div>
          <div v-else-if="selectedPerson" class="person-card">
            <div class="person-header">
              <div class="person-avatar" :style="{ borderColor: getCategoryColor(selectedPerson.category) }">
                <span class="avatar-char" :style="{ color: getCategoryColor(selectedPerson.category) }">
                  {{ selectedPerson.name?.[0] }}
                </span>
              </div>
              <div class="person-title">
                <h2 class="person-name">{{ selectedPerson.name }}</h2>
                <div class="person-tags">
                  <span v-if="selectedPerson.dynasty" class="tag">{{ selectedPerson.dynasty }}</span>
                  <span v-if="selectedPerson.title" class="tag tag-muted">{{ selectedPerson.title }}</span>
                </div>
              </div>
              <button class="close-btn" @click="selectedPerson = null">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                  <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </button>
            </div>

            <div v-if="personLoadError" class="person-warn">
              <span>详情加载失败，仅显示图谱节点信息</span>
              <button class="retry-btn" @click="searchPerson">重试</button>
            </div>

            <div class="person-info">
              <div class="info-row">
                <span class="info-label">生卒年</span>
                <span class="info-value">{{ selectedPerson.years || '不详' }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">籍贯</span>
                <span class="info-value">{{ selectedPerson.birthplace || '不详' }}</span>
              </div>
              <div class="info-row">
                <span class="info-label">出处</span>
                <span class="info-value">{{ selectedPerson.source || '不详' }}</span>
              </div>
            </div>

            <div v-if="selectedPerson.relations?.length" class="relations-section">
              <h4 class="section-title">关系网络</h4>
              <div class="relations-list">
                <div
                  v-for="rel in selectedPerson.relations"
                  :key="rel.type + rel.name"
                  class="relation-item"
                  @click="focusNode(rel.name)"
                >
                  <span class="rel-type">{{ rel.type }}</span>
                  <span class="rel-name">{{ rel.name }}</span>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" class="rel-arrow">
                    <polyline points="9 18 15 12 9 6"/>
                  </svg>
                </div>
              </div>
            </div>
          </div>

          <!-- 无选中 -->
          <div v-else class="person-card person-empty">
            <p>点击图谱中的人物节点查看详情</p>
          </div>

          <!-- 关联版本 -->
          <div class="detail-card">
            <h3 class="card-title">关联版本</h3>
            <div class="versions-list">
              <div v-for="ver in relatedVersions" :key="ver.id" class="version-item">
                <span class="version-dot" :class="ver.status"></span>
                <span class="version-name">{{ ver.name }}</span>
                <span class="version-count">{{ ver.count || 0 }} 处</span>
              </div>
            </div>
          </div>

          <!-- 差异统计 -->
          <div class="detail-card">
            <h3 class="card-title">校勘差异</h3>
            <div ref="statsChartRef" class="stats-chart"></div>
          </div>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { kgAPI } from '@/services/api'

const chartRef = ref(null)
const statsChartRef = ref(null)
const searchName = ref('')
const selectedPerson = ref(null)
const personLoading = ref(false)
const personLoadError = ref(false)
const initializing = ref(false)
const kgInitialized = ref(false)
const initError = ref(false)
const graphSimplified = ref(false)

let chart = null
let statsChart = null
let resizeHandler = null
let searchDebounceTimer = null

const categories = [
  { name: '苏氏家族', color: '#6b8f8a', symbol: '氏' },
  { name: '妻妾', color: '#b54a32', symbol: '姻' },
  { name: '其他人物', color: '#8a7a5a', symbol: '人' }
]

const nodeCount = ref(0)
const linkCount = ref(0)
const kgEmpty = computed(() => kgGraphData.value.nodes.length === 0)
const kgGraphData = ref({ nodes: [], links: [] })

const relatedVersions = ref([
  { id: 'kangxi', name: '康熙版', status: 'completed', count: 45 },
  { id: 'xianfeng', name: '咸丰版', status: 'pending', count: 123 },
  { id: '1998', name: '98年版', status: 'completed', count: 892 }
])

onMounted(() => {
  nextTick(() => {
    initChart()
    loadGraph()
    initStatsChart()
  })
})

onUnmounted(() => {
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
    resizeHandler = null
  }
  if (searchDebounceTimer) {
    clearTimeout(searchDebounceTimer)
    searchDebounceTimer = null
  }
  if (chart) chart.dispose()
  if (statsChart) statsChart.dispose()
  chart = null
  statsChart = null
})

function getNodeRelations(nodeName) {
  return kgGraphData.value.links
    .filter(l => l.source === nodeName || l.target === nodeName)
    .map(l => ({
      type: l.name,
      name: l.source === nodeName ? l.target : l.source
    }))
}

function initChart() {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value)

  // Handle window resize (save reference for cleanup)
  resizeHandler = () => {
    if (chart) chart.resize()
  }
  window.addEventListener('resize', resizeHandler)

  chart.on('click', async (params) => {
    if (params.dataType === 'node') {
      const nodeName = params.name
      const node = kgGraphData.value.nodes.find(n => n.name === nodeName)
      if (!node) return

      const base = { ...node, relations: getNodeRelations(nodeName) }
      selectedPerson.value = base
      personLoading.value = true
      personLoadError.value = false

      try {
        const res = await kgAPI.getPerson(nodeName)
        if (res.person) {
          selectedPerson.value = { ...base, ...res.person }
        }
      } catch (e) {
        console.warn('获取人物详情失败:', e)
        personLoadError.value = true
      } finally {
        personLoading.value = false
      }
    }
  })
}

async function initKG() {
  if (initializing.value || kgInitialized.value) return
  initializing.value = true
  initError.value = false
  try {
    // 使用后台模式启动初始化
    const res = await kgAPI.initKG(false, true)
    if (res.status === 'started') {
      ElMessage.info('知识图谱正在后台初始化中...')
      // 轮询状态直到完成
      await pollInitStatus()
    } else {
      // 同步模式完成
      kgInitialized.value = true
      await loadGraph()
    }
  } catch (e) {
    console.error('KG初始化失败:', e)
    ElMessage.error('知识图谱初始化失败：' + (e.message || '未知错误'))
    initError.value = true
  } finally {
    initializing.value = false
  }
}

async function pollInitStatus() {
  const maxAttempts = 120  // 最多等待2分钟
  let attempts = 0
  while (attempts < maxAttempts) {
    await new Promise(r => setTimeout(r, 1000))  // 每秒检查一次
    try {
      const status = await kgAPI.getKGInitStatus()
      if (status.completed) {
        if (status.error) {
          ElMessage.error('知识图谱初始化失败：' + status.error)
          initError.value = true
          return
        }
        if (status.result) {
          ElMessage.success(`知识图谱初始化完成：${status.result.persons_stored} 个人物，${status.result.relations_stored} 条关系`)
          kgInitialized.value = true
          await loadGraph()
        }
        return
      }
      attempts++
    } catch (e) {
      console.warn('检查初始化状态失败:', e)
      attempts++
    }
  }
  ElMessage.warning('知识图谱初始化超时，请稍后刷新页面')
  initError.value = true
}

async function loadGraph() {
  if (!chart) return

  try {
    const res = await kgAPI.getGraph(200)
    if (res.status === 'success' || res.status === 'in_memory_fallback') {
      kgGraphData.value = { nodes: res.nodes || [], links: res.links || [] }
      kgInitialized.value = (res.nodes || []).length > 0
    } else {
      kgGraphData.value = { nodes: [], links: [] }
      kgInitialized.value = false
    }
  } catch (e) {
    console.error('加载图谱失败:', e)
    kgGraphData.value = { nodes: [], links: [] }
    kgInitialized.value = false
    ElMessage.error('图谱加载失败：' + (e.message || '未知错误'))
    return
  }

  graphSimplified.value = kgGraphData.value.nodes.length > 200

  const nodes = kgGraphData.value.nodes
  const links = kgGraphData.value.links
  nodeCount.value = nodes.length
  linkCount.value = links.length

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(250, 248, 243, 0.96)',
      borderColor: '#d4cfc4',
      borderWidth: 1,
      textStyle: { color: '#1a1a1a', fontFamily: 'Noto Serif SC' },
      formatter: (params) => {
        if (params.dataType === 'node') {
          const node = nodes.find(n => n.name === params.name)
          return `<div style="padding:8px"><strong>${params.name}</strong><br/><span style="color:#6b8f8a">${node?.title || ''} ${node?.years || ''}</span></div>`
        }
        return `<div style="padding:8px"><span style="color:#4a4a4a">${params.data.source} → ${params.data.target}</span><br/><strong style="color:#b54a32">${params.data.name}</strong></div>`
      }
    },
    series: [{
      type: 'graph',
      layout: 'force',
      draggable: true,
      roam: true,
      cursor: 'pointer',
      data: nodes.map((n, idx) => ({
        name: n.name,
        category: n.category ?? 2,
        symbolSize: idx === 0 ? 60 : 48,
        symbol: 'rect',
        itemStyle: {
          color: categories[n.category ?? 2].color,
          borderWidth: 2,
          borderColor: '#faf8f3',
          shadowBlur: 8,
          shadowColor: 'rgba(0,0,0,0.12)'
        },
        label: {
          show: true,
          position: 'bottom',
          formatter: '{b}',
          fontSize: 12,
          color: '#1a1a1a',
          fontFamily: 'Noto Serif SC'
        }
      })),
      links: links.map(l => ({
        source: l.source,
        target: l.target,
        name: l.name,
        lineStyle: {
          color: 'rgba(107, 143, 138, 0.4)',
          width: 2,
          curveness: 0.15,
          opacity: 0.8
        },
        label: {
          show: true,
          position: 'middle',
          formatter: '{c}',
          fontSize: 10,
          color: '#4a4a4a',
          fontFamily: 'Noto Serif SC',
          backgroundColor: 'rgba(250, 248, 243, 0.92)',
          padding: [2, 4],
          borderRadius: 2
        }
      })),
      categories: categories.map(c => ({ name: c.name, itemStyle: { color: c.color } })),
      force: {
        repulsion: graphSimplified.value ? 60 : 180,
        edgeLength: graphSimplified.value ? 50 : 100,
        gravity: graphSimplified.value ? 0.15 : 0.08,
        layoutAnimation: !graphSimplified.value,
        friction: 0.9
      },
      scaleLimit: { min: 0.3, max: 3 },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 4, color: '#b54a32', opacity: 1 },
        itemStyle: { shadowBlur: 20, shadowColor: 'rgba(181, 74, 50, 0.35)', borderWidth: 3 }
      }
    }]
  }

  chart.setOption(option)
}

function getCategoryColor(categoryIndex) {
  return categories[categoryIndex]?.color || '#8a8a8a'
}

function initStatsChart() {
  if (!statsChartRef.value) return
  statsChart = echarts.init(statsChartRef.value)

  const option = {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(250, 248, 243, 0.96)',
      borderColor: '#d4cfc4',
      textStyle: { fontFamily: 'Noto Serif SC', color: '#1a1a1a' }
    },
    series: [{
      type: 'pie',
      radius: ['40%', '65%'],
      center: ['50%', '50%'],
      data: [
        { value: 502, name: '删文', itemStyle: { color: '#b54a32' } },
        { value: 51, name: '替换', itemStyle: { color: '#8a7a5a' } },
        { value: 34, name: '增文', itemStyle: { color: '#6b8f8a' } }
      ],
      label: { formatter: '{b}\n{d}%', fontSize: 12, fontFamily: 'Noto Serif SC', color: '#1a1a1a' },
      itemStyle: { borderRadius: 4, borderColor: '#faf8f3', borderWidth: 3 }
    }]
  }

  statsChart.setOption(option)
}

async function searchPerson() {
  if (!searchName.value) return
  const person = kgGraphData.value.nodes.find(n => n.name.includes(searchName.value))
  if (!person) {
    ElMessage.warning('未找到该人物')
    return
  }

  const base = { ...person, relations: getNodeRelations(person.name) }
  selectedPerson.value = base
  personLoading.value = true
  personLoadError.value = false

  try {
    const res = await kgAPI.getPerson(person.name)
    if (res.person) selectedPerson.value = { ...base, ...res.person }
  } catch (e) {
    console.warn('获取人物详情失败:', e)
    personLoadError.value = true
  } finally {
    personLoading.value = false
  }

  if (chart) {
    chart.dispatchAction({
      type: 'focusNodeAdjacency',
      seriesIndex: 0,
      dataIndex: kgGraphData.value.nodes.findIndex(n => n.name === person.name)
    })
  }
}

function onSearchInput() {
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer)
  const q = searchName.value.trim()
  if (!q || q.length < 2) return
  searchDebounceTimer = setTimeout(() => {
    searchPerson()
  }, 400)
}

function focusNode(name) {
  searchName.value = name
  searchPerson()
}

function fitView() { chart?.dispatchAction({ type: 'zoomToView' }) }
function zoomIn() { chart?.dispatchAction({ type: 'zoom', scaleFactor: 1.2 }) }
function zoomOut() { chart?.dispatchAction({ type: 'zoom', scaleFactor: 0.8 }) }
function refreshGraph() { loadGraph() }
</script>

<style scoped>
/* ==================== 古籍书房色板 ==================== */
.knowledge-view {
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  overflow: hidden;
  font-family: 'Noto Serif SC', serif;
}

/* ==================== 顶部栏 ==================== */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 32px;
  background: var(--bg-card);
  border-bottom: 1px solid #d4cfc4;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 16px;
}

.page-title {
  font-family: 'ZCOOL XiaoWei', 'Noto Serif SC', serif;
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: 0.05em;
}

.page-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

/* 搜索框 */
.search-box {
  display: flex;
  align-items: center;
  background: var(--bg-card);
  border: 1px solid #d4cfc4;
  border-radius: 4px;
  overflow: hidden;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.search-box:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(181, 74, 50, 0.08);
}

.search-input {
  border: none;
  outline: none;
  background: transparent;
  padding: 9px 14px;
  font-size: 14px;
  color: var(--text-primary);
  width: 180px;
  font-family: 'Noto Serif SC', serif;
}

.search-input::placeholder {
  color: var(--text-secondary);
}

.search-btn {
  padding: 9px 14px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  border-left: 1px solid #d4cfc4;
  transition: color 0.2s ease, background 0.2s ease;
}

.search-btn:hover {
  color: var(--accent);
  background: rgba(181, 74, 50, 0.04);
}

/* 按钮 */
.btn-primary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 9px 18px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s ease;
  font-family: 'ZCOOL XiaoWei', 'Noto Serif SC', serif;
  letter-spacing: 0.05em;
}

.btn-primary:hover:not(:disabled) {
  background: #a03f28;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ==================== 主内容 ==================== */
.main-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

/* ==================== 图谱卡片 ==================== */
.graph-card {
  background: var(--bg-card);
  border: 1px solid #d4cfc4;
  border-radius: 6px;
  height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
  border-left: 3px solid var(--secondary);
}

/* 图例 */
.graph-legend {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 12px 20px;
  border-bottom: 1px solid #ddd6c6;
  background: var(--bg-secondary);
}

.legend-title {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
}

.legend-items {
  display: flex;
  gap: 24px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 3px;
}

.legend-name {
  font-size: 12px;
  color: var(--text-secondary);
}

/* 图谱容器 */
.graph-container {
  flex: 1;
  min-height: 400px;
  height: 500px;
  width: 100%;
}

/* 空状态 */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
}

.empty-retry {
  margin-top: 8px;
}

.empty-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
  font-family: 'ZCOOL XiaoWei', 'Noto Serif SC', serif;
}

.empty-hint {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

/* 统计 */
.graph-stats {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  padding: 12px;
  border-top: 1px solid #ddd6c6;
  background: var(--bg-secondary);
  font-size: 13px;
  color: var(--text-secondary);
  font-family: 'JetBrains Mono', monospace;
}

.stat-sep {
  color: #b8b0a0;
}

/* 缩放控制 */
.zoom-controls {
  position: absolute;
  right: 20px;
  bottom: 70px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 10;
}

.zoom-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-card);
  border: 1px solid #d4cfc4;
  border-radius: 4px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease;
}

.zoom-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: rgba(181, 74, 50, 0.04);
}

/* ==================== 人物详情卡片 ==================== */
.person-card {
  background: var(--bg-card);
  border: 1px solid #d4cfc4;
  border-radius: 6px;
  margin-bottom: 16px;
  overflow: hidden;
  border-left: 3px solid var(--secondary);
  transition: border-color 0.2s ease;
}

.person-card:hover {
  border-left-color: var(--accent);
}

.person-header {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px;
}

.person-avatar {
  width: 52px;
  height: 52px;
  border: 2px solid;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-card);
  flex-shrink: 0;
}

.avatar-char {
  font-family: 'ZCOOL XiaoWei', 'Noto Serif SC', serif;
  font-size: 22px;
  font-weight: 600;
}

.person-title {
  flex: 1;
}

.person-name {
  font-family: 'ZCOOL XiaoWei', 'Noto Serif SC', serif;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 10px;
  letter-spacing: 0.05em;
}

.person-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tag {
  display: inline-block;
  padding: 3px 10px;
  font-size: 11px;
  color: var(--text-secondary);
  border: 1px solid #ccc5b5;
  border-radius: 3px;
  font-family: 'Noto Serif SC', serif;
}

.tag-muted {
  color: var(--text-secondary);
  border-style: dashed;
  border-color: #ddd6c6;
}

.close-btn {
  padding: 6px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 4px;
  transition: color 0.2s ease, background 0.2s ease;
}

.close-btn:hover {
  color: var(--accent);
  background: rgba(181, 74, 50, 0.06);
}

.person-info {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px 16px;
  background: var(--bg-secondary);
  margin: 0 16px 16px;
  border-radius: 4px;
  border: 1px solid #ddd6c6;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.info-value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
  font-family: 'Noto Serif SC', serif;
}

.relations-section {
  padding: 0 16px 16px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 12px;
  font-family: 'ZCOOL XiaoWei', 'Noto Serif SC', serif;
}

.relations-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.relation-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease;
  border: 1px solid transparent;
}

.relation-item:hover {
  background: rgba(181, 74, 50, 0.05);
  border-color: rgba(181, 74, 50, 0.15);
}

.rel-type {
  font-size: 11px;
  color: var(--text-secondary);
  min-width: 38px;
}

.rel-name {
  flex: 1;
  font-size: 13px;
  color: var(--accent);
  font-weight: 500;
  font-family: 'Noto Serif SC', serif;
}

.rel-arrow {
  color: var(--text-secondary);
}

/* 空状态 */
.person-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  text-align: center;
  padding: 24px;
}

.person-empty p {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

.person-loading {
  padding: 24px 16px;
}

.person-warn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 0 16px 12px;
  padding: 8px 12px;
  background: rgba(201, 169, 110, 0.12);
  border: 1px solid rgba(201, 169, 110, 0.3);
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.retry-btn {
  border: 1px solid var(--accent);
  background: transparent;
  color: var(--accent);
  padding: 3px 10px;
  font-size: 12px;
  border-radius: 3px;
  cursor: pointer;
  font-family: 'Noto Serif SC', serif;
  transition: background 0.2s ease;
}

.retry-btn:hover {
  background: rgba(181, 74, 50, 0.06);
}

/* ==================== 详情卡片 ==================== */
.detail-card {
  background: var(--bg-card);
  border: 1px solid #d4cfc4;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 16px;
  border-left: 3px solid var(--secondary);
}

.card-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid #ddd6c6;
  font-family: 'ZCOOL XiaoWei', 'Noto Serif SC', serif;
}

.versions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.version-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: 4px;
  border: 1px solid transparent;
  transition: border-color 0.2s ease;
}

.version-item:hover {
  border-color: #ccc5b5;
}

.version-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc5b5;
  flex-shrink: 0;
}

.version-dot.completed { background: var(--secondary); }
.version-dot.pending { background: #c9a96e; }

.version-name {
  flex: 1;
  font-size: 12px;
  color: var(--text-primary);
  font-family: 'Noto Serif SC', serif;
}

.version-count {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: 'JetBrains Mono', monospace;
}

.stats-chart {
  height: 150px;
}

/* 节点过多简化提示 */
.simplify-banner {
  position: absolute;
  top: 56px;
  left: 20px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: rgba(201, 169, 110, 0.16);
  border: 1px solid rgba(201, 169, 110, 0.4);
  border-radius: 3px;
  font-size: 12px;
  color: var(--text-secondary);
  z-index: 5;
}

/* ==================== 响应式 ==================== */
@media (max-width: 1200px) {
  .main-content :deep(.el-col:first-child) {
    margin-bottom: 16px;
  }
}

@media (max-width: 768px) {
  .page-header {
    padding: 14px 20px;
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }

  .header-right {
    width: 100%;
    justify-content: space-between;
  }

  .main-content {
    padding: 16px;
  }

  .graph-card {
    height: calc(100vh - 220px);
  }
}
</style>
