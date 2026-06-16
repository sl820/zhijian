<!--
  志鉴·星野图谱 KnowledgeView（M6 重写）
  替代旧的 ECharts 2D 力导向，用 three.js 3D + 服务端 FA2 预布局 + 视锥裁剪 + 视差星空背景

  Why：星野图考美学是产品核心差异化（靛蓝底 + 留白星点 + 朱砂节点 + 墨黑边 + 金粉高光）。
-->
<template>
  <div class="nebula-view">
    <!-- 顶部栏 -->
    <header class="nebula-header">
      <div class="nebula-title">
        <span class="nebula-title-seal">星</span>
        <div>
          <div class="nebula-title-text">星野图考</div>
          <div class="nebula-subtitle">XINGYE · 人物星云图谱</div>
        </div>
      </div>
      <div class="nebula-controls">
        <div class="nebula-search-box">
          <input
            v-model="searchName"
            placeholder="搜人物..."
            class="nebula-search-input"
            @keyup.enter="onSearchEnter"
          />
        </div>
        <select v-model="selectedSource" class="nebula-btn" style="background:transparent">
          <option v-for="s in sources" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <button class="nebula-btn" :disabled="loading" @click="loadLayout">
          {{ loading ? '加载中...' : '刷新星图' }}
        </button>
      </div>
    </header>

    <!-- 3D Canvas -->
    <NebulaCanvas
      v-if="!loading && layoutNodes.length"
      :nodes="layoutNodes"
      :edges="layoutEdges"
      :loading="loading"
      @node-click="onNodeClick"
      @background-click="onBackgroundClick"
    />

    <!-- 加载状态 -->
    <div v-if="loading" class="nebula-loading">
      <div class="nebula-loading-seal">星</div>
      <div class="nebula-loading-text">观星中...</div>
    </div>

    <!-- 空状态 -->
    <div v-if="!loading && !layoutNodes.length" class="nebula-empty">
      <div class="nebula-empty-title">{{ emptyTitle }}</div>
      <div class="nebula-empty-hint">{{ emptyHint }}</div>
      <button v-if="emptyAction" class="nebula-btn" @click="emptyAction.handler">
        {{ emptyAction.label }}
      </button>
    </div>

    <!-- 图例 -->
    <div v-if="layoutNodes.length" class="nebula-legend">
      <div class="nebula-legend-title">星宿分类</div>
      <div class="nebula-legend-items">
        <div v-for="cat in categoryLegend" :key="cat.id" class="nebula-legend-item">
          <span class="nebula-legend-dot" :style="{ background: cat.color }"></span>
          <span>{{ cat.name }}</span>
        </div>
      </div>
      <div class="nebula-legend-stats">
        <span>{{ layoutNodes.length }} 颗星</span>
        <span style="margin: 0 8px">·</span>
        <span>{{ layoutEdges.length }} 条连线</span>
      </div>
    </div>

    <!-- 节点详情面板（M7：名片 + 子图 + 证据 + RAG） -->
    <PersonPanel
      v-if="selectedNode"
      :person="selectedNode"
      @close="selectedNode = null"
      @navigate="onNavigate"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import NebulaCanvas from '../components/nebula/NebulaCanvas.vue'
import PersonPanel from '../components/person/PersonPanel.vue'
import { kgAPI } from '../services/api.js'
import { PALETTE, CATEGORY_COLORS, CATEGORY_NAMES } from '../constants/palette.js'

const searchName = ref('')
const selectedSource = ref('jiapu')
const sources = ref([
  { id: 'jiapu', name: '家谱' },
  { id: 'memory', name: '内储' },
])
const loading = ref(false)
const layoutNodes = ref([])
const layoutEdges = ref([])
const layoutMeta = ref({})
const error = ref('')
const selectedNode = ref(null)

const categoryLegend = [
  { id: 0, name: CATEGORY_NAMES[0], color: CATEGORY_COLORS[0] },
  { id: 1, name: CATEGORY_NAMES[1], color: CATEGORY_COLORS[1] },
  { id: 3, name: CATEGORY_NAMES[3], color: CATEGORY_COLORS[3] },
  { id: 2, name: CATEGORY_NAMES[2], color: CATEGORY_COLORS[2] },
]

const emptyTitle = computed(() => {
  if (error.value) return '观星失败'
  if (!layoutNodes.value.length) return '星河未现'
  return ''
})
const emptyHint = computed(() => {
  if (error.value) return error.value
  return '请点击「刷新星图」或运行 precompute_layout.py 生成坐标'
})
const emptyAction = computed(() => {
  if (error.value) return { label: '重试', handler: loadLayout }
  return null
})

async function loadSources() {
  try {
    const res = await kgAPI.listSources()
    const items = (res.sources || []).filter(s => s.enabled).map(s => ({ id: s.id, name: s.name }))
    if (items.length) sources.value = items
  } catch (e) {
    console.warn('[Nebula] listSources failed:', e)
  }
}

async function loadLayout() {
  loading.value = true
  error.value = ''
  try {
    const meta = await kgAPI.getLayoutMetadata(selectedSource.value)
    layoutMeta.value = meta

    const res = await kgAPI.getLayout(selectedSource.value, null, 500, 0)
    layoutNodes.value = (res.nodes || []).map(n => ({
      id: n.uri || n.id,
      name: n.label_chs || n.name || n.uri?.split('/').pop() || n.id,
      x: n.x,
      y: n.y,
      z: n.z,
      dynasty: n.dynasty || '',
      region: n.region || '',
      category: n.category ?? 2,
    }))
    layoutEdges.value = (res.links || res.edges || []).map(e => ({
      source: e.source,
      target: e.target,
      type: e.type || 'RELATED',
      confidence: e.confidence ?? 0.7,
    }))
  } catch (e) {
    console.error('[Nebula] loadLayout error:', e)
    const msg = e.response?.data?.detail || e.message || ''
    error.value = msg.includes('not found') || msg.includes('404')
      ? `源「${selectedSource.value}」未生成布局坐标，请运行：python -m scripts.precompute_layout --source ${selectedSource.value}`
      : `加载失败：${msg || '未知错误'}`
    layoutNodes.value = []
    layoutEdges.value = []
  } finally {
    loading.value = false
  }
}

function onSearchEnter() {
  if (!searchName.value.trim()) return
  // 简单搜索：找到第一个匹配 name 的节点并选中
  const target = layoutNodes.value.find(n =>
    n.name && n.name.includes(searchName.value.trim()),
  )
  if (target) {
    onNodeClick(target)
  } else {
    error.value = `未找到人物「${searchName.value}」`
  }
}

function onNodeClick(node) {
  selectedNode.value = node
}

function onBackgroundClick() {
  selectedNode.value = null
}

function onNavigate(nodeData) {
  // 子图节点点击 → 切到该人物
  selectedNode.value = {
    id: nodeData.id,
    name: nodeData.name,
    dynasty: nodeData.dynasty,
    region: '',
    category: nodeData.category ?? 2,
  }
}

onMounted(async () => {
  await loadSources()
  await loadLayout()
})
</script>

<style scoped>
@import '../styles/xingye.css';

.nebula-legend-stats {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--xingye-ink-light);
  font-size: 11px;
  color: var(--xingye-rice-dim);
  letter-spacing: 0.15em;
  font-family: var(--xingye-font-display);
}
</style>