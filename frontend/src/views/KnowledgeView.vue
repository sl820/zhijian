<!--
  志鉴·星野图考 KnowledgeView（v2 - 接入 nebula store）

  改造（2026-06-17）：
    - 删除 selectedNode / filterCategory / filterDynasty / activeDynasties / searchToast 内部 ref
    - 改用 useNebulaStore 单一真源
    - v-model 改 :value + @change（写入 store）
    - 搜索/筛选/时间轴事件写入 store，副作用由 middleware 集中处理
    - 保留 template + style 全部结构（最小侵入式）
-->
<template>
  <div class="nebula-view">
    <!-- 竞赛交付：SAFE MODE / DEGRADED 横幅 -->
    <div v-if="healthStore.safeMode" class="nebula-safe-banner">
      <span class="nebula-safe-banner-icon">⚠</span>
      <span class="nebula-safe-banner-text">
        系统处于降级模式（SAFE MODE）：部分功能已关闭，当前显示 {{ nodeLimit }} 颗节点上限。
      </span>
    </div>
    <div v-else-if="healthStore.isDegraded" class="nebula-warn-banner">
      <span class="nebula-warn-banner-icon">!</span>
      <span class="nebula-warn-banner-text">
        系统部分功能降级中（智能问答可能返回兜底答案），核心视图正常。
      </span>
    </div>

    <!-- 顶部栏 -->
    <header class="nebula-header">
      <div class="nebula-title">
        <span class="nebula-title-seal">星</span>
        <div>
          <div class="nebula-title-text">星野图考</div>
          <div class="nebula-subtitle">XINGYE · 北极天球立体投影 · 1247 苏州石刻天文图式</div>
        </div>
      </div>
      <div class="nebula-controls">
        <div class="nebula-search-box">
          <input
            :value="searchName"
            @input="searchName = $event.target.value"
            placeholder="搜人物..."
            class="nebula-search-input"
            @keyup.enter="onSearchEnter"
          />
        </div>
        <select :value="selectedSource" @change="onSourceChange" class="nebula-btn" style="background:transparent">
          <option v-for="s in sources" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <!-- M6 朝代/家族筛选（写入 store） -->
        <select
          :value="filterCategory ?? ''"
          @change="onCategoryChange"
          class="nebula-btn"
          style="background:transparent"
          title="按家族分类筛"
        >
          <option value="">全部氏族</option>
          <option value="0">姓氏族</option>
          <option value="1">妻妾</option>
          <option value="3">官吏·文人</option>
          <option value="2">其它人物</option>
        </select>
        <input
          :value="filterDynasty"
          @input="onDynastyInput"
          placeholder="朝代子串..."
          class="nebula-btn nebula-btn-input"
          title="按 biography/name 子串筛朝代"
          @keyup.enter="triggerLoadLayout"
        />
        <button v-if="hasFilter" class="nebula-btn nebula-btn-ghost" @click="onClearFilters">
          清除
        </button>
        <button class="nebula-btn" :disabled="loading" @click="triggerLoadLayout">
          {{ loading ? '加载中...' : '刷新星图' }}
        </button>
      </div>
    </header>

    <!-- 3D Canvas（不再监听 node-click / background-click：已迁到 store） -->
    <NebulaCanvas
      v-if="!loading && layoutNodes.length"
      ref="nebulaRef"
      :nodes="layoutNodes"
      :edges="layoutEdges"
      :loading="loading"
      :active-dynasties="activeDynasties"
      @nebula:load-layout="triggerLoadLayout"
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

    <!-- 搜索提示 toast（从 store 派生） -->
    <div v-if="searchToast" class="nebula-toast">{{ searchToast }}</div>

    <!-- 图例 -->
    <div v-if="layoutNodes.length || totalInBbox" class="nebula-legend">
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
        <template v-if="totalInBbox && (filterCategory !== null || filterDynasty)">
          <span style="margin: 0 8px">·</span>
          <span>匹配 {{ totalInBbox }} / {{ totalUnfiltered }} 颗</span>
          <span style="margin: 0 8px">·</span>
          <span class="nebula-legend-filter">筛 {{ filterLabel }}</span>
        </template>
      </div>
    </div>

    <!-- 节点详情面板（从 store 读 selectedNodeData） -->
    <PersonPanel />

    <!-- M6 朝代时间轴 -->
    <DynastyTimeline
      v-if="layoutNodes.length"
      :counts="dynastyCounts"
      :active="activeDynasties"
      :labels="dynastyLabels"
      @toggle="onToggleDynasty"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import NebulaCanvas from '../components/nebula/NebulaCanvas.vue'
import DynastyTimeline from '../components/nebula/DynastyTimeline.vue'
import PersonPanel from '../components/person/PersonPanel.vue'
import { kgAPI } from '../services/api.js'
import { PALETTE, CATEGORY_COLORS, CATEGORY_NAMES } from '../constants/palette.js'
import { useNebulaStore } from '../stores/nebula.js'
import { useSystemHealthStore } from '../stores/systemHealth'

const store = useNebulaStore()
const healthStore = useSystemHealthStore()

// 竞赛交付：节点上限取 systemHealth.demoNodeLimit（默认 5000）
const nodeLimit = computed(() => healthStore.demoNodeLimit || 5000)

// ============================================================
// 搜索框本地 state（不需要进 store）
// ============================================================
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
const nebulaRef = ref(null)

// ============================================================
// 从 store 派生（不再持有副本）
// ============================================================
const filterCategory = computed(() => store.filterCategory)
const filterDynasty = computed(() => store.filterDynasty)
const activeDynasties = computed(() => store.activeDynasties)
const searchToast = computed(() => store.searchToast)
const hasFilter = computed(() => filterCategory.value !== null || !!filterDynasty.value)

const totalInBbox = ref(0)
const totalUnfiltered = ref(0)

// ============================================================
// 朝代时间轴（M6）
// ============================================================
const dynastyLabels = [
  { id: 'pre_han',   label: '汉前/汉' },
  { id: 'three_jin', label: '三国/晋' },
  { id: 'north_sou', label: '南北朝' },
  { id: 'sui',       label: '隋' },
  { id: 'tang',      label: '唐' },
  { id: 'five_dyn',  label: '五代' },
  { id: 'song',      label: '宋' },
  { id: 'yuan',      label: '元' },
  { id: 'ming',      label: '明' },
  { id: 'qing',      label: '清' },
  { id: 'modern',    label: '民国+' },
]
function yearToDynasty(year) {
  if (year == null || isNaN(year)) return null
  const y = Number(year)
  if (y < 220) return 'pre_han'
  if (y < 420) return 'three_jin'
  if (y < 589) return 'north_sou'
  if (y < 618) return 'sui'
  if (y < 907) return 'tang'
  if (y < 960) return 'five_dyn'
  if (y < 1279) return 'song'
  if (y < 1368) return 'yuan'
  if (y < 1644) return 'ming'
  if (y < 1912) return 'qing'
  return 'modern'
}
const dynastyCounts = computed(() => {
  const counts = {}
  for (const n of layoutNodes.value) {
    const dy = yearToDynasty(n.birth_year)
    if (dy) counts[dy] = (counts[dy] || 0) + 1
  }
  return counts
})
function onToggleDynasty(id) {
  // 状态机：null（全激活）→ 含该 id 的 Set → 不含该 id 的 Set → 全空（隐式视为"全激活"）
  if (activeDynasties.value == null) {
    const s = new Set(dynastyLabels.map((d) => d.id))
    s.delete(id)
    store.setActiveDynasties(s)
    return
  }
  const s = new Set(activeDynasties.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  if (s.size === 0 || s.size === dynastyLabels.length) {
    store.setActiveDynasties(null)
  } else {
    store.setActiveDynasties(s)
  }
}

const filterLabel = computed(() => {
  const parts = []
  if (filterCategory.value !== null) {
    parts.push(CATEGORY_NAMES[filterCategory.value] || `类别 ${filterCategory.value}`)
  }
  if (filterDynasty.value) parts.push(`朝代「${filterDynasty.value}」`)
  return parts.join(' · ')
})

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
  if (error.value) return { label: '重试', handler: triggerLoadLayout }
  return null
})

// ============================================================
// Event handlers（写入 store）
// ============================================================
function onSourceChange(e) {
  selectedSource.value = e.target.value
  // 切源时清空 selection（不同源的 node id 不可比）
  store.clearSelected()
  triggerLoadLayout()
}

function onCategoryChange(e) {
  const v = e.target.value
  store.setFilterCategory(v === '' ? null : Number(v))
  // middleware 会 watch category 变化并自动调 loadLayout
}

function onDynastyInput(e) {
  store.setFilterDynasty(e.target.value)
  // middleware 会 watch dynasty 变化并 debounce 调 loadLayout
}

function onClearFilters() {
  store.clearFilters()
  triggerLoadLayout()  // 清除按钮立即触发
}

function triggerLoadLayout() {
  loadLayout()
}

async function loadSources() {
  try {
    const res = await kgAPI.listSources()
    const items = (res.sources || []).filter((s) => s.enabled).map((s) => ({ id: s.id, name: s.name }))
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

    const filters = {}
    if (filterCategory.value !== null) filters.category = filterCategory.value
    if (filterDynasty.value.trim()) filters.dynasty = filterDynasty.value.trim()

    // 竞赛交付：节点上限取 systemHealth.demoNodeLimit（demo 模式默认 5000）
    const res = await kgAPI.getLayout(selectedSource.value, null, nodeLimit.value, 0, filters)
    layoutNodes.value = (res.nodes || []).map((n) => ({
      id: n.uri || n.id,
      name: n.name || n.label_chs || n.uri?.split('/').pop() || n.id,
      x: n.x,
      y: n.y,
      z: n.z,
      dynasty: n.dynasty || '',
      region: n.region || '',
      biography: n.biography || '',
      category: n.category ?? 2,
      birth_year: n.birth_year ?? null,
    }))
    layoutEdges.value = (res.links || res.edges || []).map((e) => ({
      source: e.source,
      target: e.target,
      type: e.type || 'RELATED',
      confidence: e.confidence ?? 0.7,
    }))
    totalInBbox.value = res.total_in_bbox || 0
    totalUnfiltered.value = res.total_in_bbox_unfiltered || layoutMeta.value?.node_count || 0

    // 注意：NebulaCanvas watch props.nodes 会自动 buildScene + store.bumpLayout
    // 这里不需要再调，middleware 会做 reconciliation
  } catch (e) {
    console.error('[Nebula] loadLayout error:', e)
    const msg = e.response?.data?.detail || e.message || ''
    error.value = msg.includes('not found') || msg.includes('404')
      ? `源「${selectedSource.value}」未生成布局坐标，请运行：python -m scripts.precompute_layout --source ${selectedSource.value}`
      : `加载失败：${msg || '未知错误'}`
    layoutNodes.value = []
    layoutEdges.value = []
    totalInBbox.value = 0
  } finally {
    loading.value = false
  }
}

function onSearchEnter() {
  if (!searchName.value.trim()) return
  // 简单搜索：找到第一个匹配 name 的节点
  const target = layoutNodes.value.find((n) =>
    n.name && n.name.includes(searchName.value.trim()),
  )
  if (target) {
    // 写入 store：middleware 会自动 locate mesh + highlight + flyTo
    store.setSelected(target.id, {
      id: target.id,
      name: target.name,
      dynasty: target.dynasty,
      region: target.region,
      category: target.category,
    })
  } else {
    const scope = layoutNodes.value.length
    const total = totalInBbox.value || scope
    const hint = filterCategory.value !== null || filterDynasty.value
      ? '当前筛选条件下'
      : `当前可见 ${scope} 颗 / 全图 ${total} 颗`
    store.showSearchToast(`未找到「${searchName.value}」（${hint}）`)
  }
}

onMounted(async () => {
  // 竞赛交付：启动时先确认健康（避免 layout 在 PASS 之前就拉）
  if (healthStore.overall === 'UNKNOWN') {
    await healthStore.checkHealth()
  }
  await loadSources()
  await loadLayout()
})
</script>

<style scoped>
@import '../styles/xingye.css';

.nebula-view {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

/* Header 在 canvas 之上 */
.nebula-header {
  position: relative;
  z-index: 20;
  flex-shrink: 0;
}

/* 浮层 UI 在 canvas 之上 */
.nebula-legend,
.nebula-loading {
  position: absolute;
  z-index: 15;
}

/* Toast（北宋方志博物 · 纸卡 + 朱砂边） */
.nebula-toast {
  position: fixed;
  top: 90px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 60;
  padding: 10px 22px;
  background: var(--paper-hi);
  border: 1px solid var(--cinnabar-seal);
  border-left: 3px solid var(--cinnabar-seal);
  border-radius: 3px;
  color: var(--ink-main);
  font-family: var(--xingye-font-display);
  font-size: 13px;
  letter-spacing: 0.15em;
  box-shadow: 0 4px 18px rgba(168, 48, 42, 0.18);
  animation: nebula-toast-in 0.3s ease-out;
}

@keyframes nebula-toast-in {
  from { opacity: 0; transform: translate(-50%, -8px); }
  to { opacity: 1; transform: translate(-50%, 0); }
}

.nebula-legend-stats {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--ink-wash);
  font-size: 11px;
  color: var(--ink-pale);
  letter-spacing: 0.15em;
  font-family: var(--xingye-font-display);
}

.nebula-legend-filter {
  color: var(--cinnabar-seal);
  letter-spacing: 0.1em;
}

.nebula-btn-input {
  width: 130px;
  padding: 4px 8px;
}

.nebula-btn-ghost {
  background: transparent;
  border: 1px solid var(--cinnabar-seal);
  color: var(--cinnabar-bright);
}

/* 竞赛交付：SAFE MODE / DEGRADED 横幅（纸底 + 朱砂 / 金粉边） */
.nebula-safe-banner,
.nebula-warn-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 18px;
  font-family: var(--xingye-font-display);
  font-size: 13px;
  letter-spacing: 0.15em;
  border-radius: 3px;
  margin: 8px 16px 0;
  animation: nebula-banner-in 0.4s ease-out;
}

.nebula-safe-banner {
  background: var(--cinnabar-faint, rgba(168, 48, 42, 0.08));
  border: 1px solid var(--cinnabar-seal);
  color: var(--cinnabar-deep);
}

.nebula-warn-banner {
  background: var(--gold-faint, rgba(184, 148, 31, 0.12));
  border: 1px solid var(--gold-main);
  color: var(--gold-dim, #a0823a);
}

.nebula-safe-banner-icon,
.nebula-warn-banner-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  font-weight: 700;
  font-size: 13px;
  flex-shrink: 0;
}

.nebula-safe-banner-icon {
  background: var(--cinnabar-seal);
  color: var(--paper-hi);
}

.nebula-warn-banner-icon {
  background: var(--gold-main);
  color: var(--ink-main);
}

@keyframes nebula-banner-in {
  from { opacity: 0; transform: translateY(-6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
