<!--
  NarrativeView.vue — R9 研究叙事模式
  4-step 故事流：研究问题 → 数据基础 → 方法 → 核心发现
  + 一键评委包按钮
-->
<template>
  <div class="narrative-view">
    <!-- 顶部 Hero -->
    <header class="narrative-hero">
      <div class="narrative-hero__inner">
        <div class="narrative-hero__eyebrow">R9 · DIGITAL HUMANITIES RESEARCH</div>
        <h1 class="narrative-hero__title">研究叙事模式</h1>
        <p class="narrative-hero__subtitle">XINGYE ATLAS · RESEARCH NARRATIVE</p>
        <div class="narrative-hero__actions">
          <button class="btn-primary" @click="openJuryPack" :disabled="juryPackLoading">
            <span v-if="juryPackLoading">加载中...</span>
            <span v-else>📋 一键评委包 / Jury Pack</span>
          </button>
          <button class="btn-secondary" @click="onRefresh">🔄 刷新研究结论</button>
        </div>
      </div>
    </header>

    <!-- Step 1: 研究问题 -->
    <section class="narrative-step narrative-step--question">
      <div class="narrative-step__num">01</div>
      <div class="narrative-step__body">
        <h2 class="narrative-step__title">研究问题</h2>
        <p class="narrative-step__lead">
          我们研究<strong>中国家族结构的长期演化规律</strong>——
          跨多个世纪、跨多个地域的家族网络如何形成、扩张、消亡？
          哪些因素决定了家族在历史长河中的延续性？
        </p>
        <p class="narrative-step__detail">
          本研究以上海图书馆馆藏家谱数据（2.03M 人物、13,100 条关系）为基底，
          结合 ForceAtlas2 力导向布局与跨源 RAG 检索，
          从家族规模分布、世代深度、跨代婚姻三个维度展开实证分析。
        </p>
      </div>
    </section>

    <!-- Step 2: 数据基础 -->
    <section class="narrative-step">
      <div class="narrative-step__num">02</div>
      <div class="narrative-step__body">
        <h2 class="narrative-step__title">数据基础</h2>
        <p class="narrative-step__lead">
          以多源异构家谱数据为核心，覆盖人物、关系、地名、文献四个维度。
        </p>
        <div v-if="dataScale" class="data-stats">
          <div class="data-stat">
            <div class="data-stat__val">{{ formatNum(dataScale.jiapu_persons) }}</div>
            <div class="data-stat__key">家谱人物</div>
            <div class="data-stat__src">源: jiapu SQLite</div>
          </div>
          <div class="data-stat">
            <div class="data-stat__val">{{ formatNum(relationsCount) }}</div>
            <div class="data-stat__key">关系数据</div>
            <div class="data-stat__src">源: person_relations</div>
          </div>
          <div class="data-stat">
            <div class="data-stat__val">{{ dataScale.sources_registered || 0 }}</div>
            <div class="data-stat__key">数据源</div>
            <div class="data-stat__src">{{ dataScale.sources_enabled || 0 }} 启用 / {{ dataScale.sources_registered || 0 }} 注册</div>
          </div>
          <div class="data-stat">
            <div class="data-stat__val">{{ formatNum(dataScale.demo_node_limit) }}</div>
            <div class="data-stat__key">3D 节点上限</div>
            <div class="data-stat__src">demo_mode 默认</div>
          </div>
        </div>
        <div v-else class="narrative-step__loading">数据规模加载中...</div>
      </div>
    </section>

    <!-- Step 3: 方法 -->
    <section class="narrative-step">
      <div class="narrative-step__num">03</div>
      <div class="narrative-step__body">
        <h2 class="narrative-step__title">方法</h2>
        <p class="narrative-step__lead">四步流水线，每步都可独立验证。</p>
        <MethodFlow :steps="methodSteps" />
      </div>
    </section>

    <!-- Step 4: 核心发现 -->
    <section class="narrative-step">
      <div class="narrative-step__num">04</div>
      <div class="narrative-step__body">
        <h2 class="narrative-step__title">核心发现</h2>
        <p class="narrative-step__lead">
          由 insights_engine 自动从原始数据计算（零 LLM 编造）。
          每条发现配数据来源标签 + 算法说明 + 度量指标，可逐条追溯。
        </p>

        <div v-if="loadingInsights" class="narrative-step__loading">研究结论计算中...</div>
        <div v-else-if="insightsError" class="narrative-step__error">
          加载失败：{{ insightsError }}（已自动降级，演示可继续）
        </div>
        <div v-else class="insights-grid">
          <div class="insights-col">
            <h3 class="insights-col__title">
              <span class="insights-col__icon">👪</span>
              家族结构规律
            </h3>
            <InsightCard v-for="(f, i) in kinship" :key="'k' + i" :finding="f" />
          </div>
          <div class="insights-col">
            <h3 class="insights-col__title">
              <span class="insights-col__icon">🕸</span>
              图网络结构规律
            </h3>
            <InsightCard v-for="(f, i) in graph" :key="'g' + i" :finding="f" />
          </div>
          <div class="insights-col">
            <h3 class="insights-col__title">
              <span class="insights-col__icon">📊</span>
              数据覆盖边界
            </h3>
            <InsightCard v-for="(f, i) in audit" :key="'a' + i" :finding="f" />
          </div>
        </div>
      </div>
    </section>

    <JuryPackModal :open="modalOpen" :pack="juryPack" @close="modalOpen = false" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useSystemHealthStore } from '@/stores/systemHealth'
import { researchAPI } from '@/services/api'
import InsightCard from '@/components/narrative/InsightCard.vue'
import MethodFlow from '@/components/narrative/MethodFlow.vue'
import JuryPackModal from '@/components/narrative/JuryPackModal.vue'

const healthStore = useSystemHealthStore()

const methodSteps = [
  { step: 1, name: 'Graph Construction', tech: 'SQLite + Pydantic + 异构源合并' },
  { step: 2, name: 'Layout', tech: 'ForceAtlas2 (FA2) + numpy 预计算 + bbox 子集' },
  { step: 3, name: '3D Render', tech: 'Three.js + InstancedMesh + 视锥裁剪' },
  { step: 4, name: 'RAG Retrieval', tech: 'BGE + ChromaDB + Ollama Qwen2.5-3B' },
  { step: 5, name: 'Insights', tech: '纯 SQL + numpy（零 LLM）' },
]

const insights = ref({ kinship: [], graph: [], audit: [] })
const loadingInsights = ref(false)
const insightsError = ref('')
const relationsCount = ref(0)
const modalOpen = ref(false)
const juryPackLoading = ref(false)

const juryPack = computed(() => healthStore.juryPack || null)
const dataScale = computed(() => healthStore.juryPack?.data_scale || null)

const kinship = computed(() => insights.value.kinship || [])
const graph = computed(() => insights.value.graph || [])
const audit = computed(() => insights.value.audit || [])

async function loadAll() {
  loadingInsights.value = true
  insightsError.value = ''
  try {
    // 1. 拉 insights
    const res = await researchAPI.getInsights()
    insights.value = {
      kinship: res.kinship?.findings || [],
      graph: res.graph_structure?.findings || [],
      audit: res.data_audit?.findings || [],
    }
    // 关系数从 graph_structure.metrics.total_relations 取
    relationsCount.value = res.graph_structure?.metrics?.total_relations || 0
  } catch (e) {
    insightsError.value = e.response?.data?.message || e.message || '加载失败'
    insights.value = { kinship: [], graph: [], audit: [] }
  } finally {
    loadingInsights.value = false
  }
  // 2. 后台拉 jury pack（不阻塞展示）
  loadJuryPack(true)
}

async function loadJuryPack(silent = false) {
  if (!silent) juryPackLoading.value = true
  try {
    await healthStore.fetchJuryPack(true)
  } finally {
    if (!silent) juryPackLoading.value = false
  }
}

function openJuryPack() {
  modalOpen.value = true
  loadJuryPack()
}

function onRefresh() {
  loadAll()
}

function formatNum(n) {
  if (n == null) return '—'
  if (typeof n !== 'number') return String(n)
  if (Math.abs(n) >= 1000) return n.toLocaleString()
  return String(n)
}

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
@import '../styles/xingye.css';

.narrative-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 0 80px;
}

/* ==================== Hero ==================== */
.narrative-hero {
  background: linear-gradient(135deg, var(--cinnabar-faint), var(--celadon-faint));
  border-bottom: 1px solid var(--border-light);
  padding: 56px 32px 48px;
  margin-bottom: 24px;
  position: relative;
  overflow: hidden;
}

.narrative-hero::before {
  content: '考';
  position: absolute;
  right: -40px;
  top: -40px;
  font-family: var(--font-display, 'ZCOOL XiaoWei', serif);
  font-size: 360px;
  color: var(--cinnabar-faint);
  font-weight: 400;
  pointer-events: none;
}

.narrative-hero__inner {
  position: relative;
  z-index: 1;
  max-width: 760px;
}

.narrative-hero__eyebrow {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  letter-spacing: 0.3em;
  color: var(--accent, #b54a32);
  margin-bottom: 8px;
}

.narrative-hero__title {
  font-family: var(--font-display, 'ZCOOL XiaoWei', serif);
  font-size: 44px;
  font-weight: 500;
  margin: 0 0 8px;
  color: var(--text-primary, #2a2a2a);
  letter-spacing: 0.2em;
}

.narrative-hero__subtitle {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  color: var(--text-muted, #888);
  letter-spacing: 0.2em;
  margin: 0 0 28px;
}

.narrative-hero__actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.btn-primary,
.btn-secondary {
  padding: 10px 24px;
  border-radius: 4px;
  font-family: var(--font-display, 'ZCOOL XiaoWei', serif);
  font-size: 14px;
  letter-spacing: 0.2em;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid;
}

.btn-primary {
  background: var(--accent, #b54a32);
  color: #f4efe6;
  border-color: var(--accent, #b54a32);
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-bright, #c2362a);
  box-shadow: 0 4px 16px rgba(181, 74, 50, 0.3);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: wait;
}

.btn-secondary {
  background: transparent;
  color: var(--text-primary, #2a2a2a);
  border-color: var(--border-medium, #c4b89a);
}

.btn-secondary:hover {
  border-color: var(--accent, #b54a32);
  color: var(--accent, #b54a32);
}

/* ==================== Step sections ==================== */
.narrative-step {
  display: flex;
  gap: 24px;
  padding: 32px 32px;
  margin: 0 16px 16px;
  background: var(--bg-card, #faf8f3);
  border: 1px solid var(--border-light, #e0d8c5);
  border-radius: 6px;
}

.narrative-step__num {
  flex-shrink: 0;
  font-family: var(--font-display, 'ZCOOL XiaoWei', serif);
  font-size: 56px;
  font-weight: 500;
  color: var(--accent, #b54a32);
  opacity: 0.3;
  line-height: 1;
  letter-spacing: 0.05em;
}

.narrative-step__body {
  flex: 1;
  min-width: 0;
}

.narrative-step__title {
  font-family: var(--font-display, 'ZCOOL XiaoWei', serif);
  font-size: 26px;
  margin: 0 0 12px;
  color: var(--text-primary, #2a2a2a);
  letter-spacing: 0.15em;
  font-weight: 500;
}

.narrative-step__lead {
  font-family: var(--font-serif, 'Noto Serif SC', serif);
  font-size: 15px;
  line-height: 1.8;
  color: var(--text-primary, #2a2a2a);
  margin: 0 0 8px;
}

.narrative-step__detail {
  font-family: var(--font-serif, 'Noto Serif SC', serif);
  font-size: 13px;
  line-height: 1.85;
  color: var(--text-secondary, #6b6149);
  margin: 0;
}

.narrative-step__loading {
  padding: 24px;
  text-align: center;
  color: var(--text-muted, #888);
  font-style: italic;
}

.narrative-step__error {
  padding: 16px;
  background: var(--warning-bg);
  border: 1px dashed var(--gold-main);
  border-radius: 4px;
  color: var(--gold-dim);
  font-size: 13px;
}

/* ==================== Data stats ==================== */
.data-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.data-stat {
  background: var(--bg-primary, #f4efe6);
  border: 1px solid var(--border-light, #e0d8c5);
  border-left: 3px solid var(--accent, #b54a32);
  border-radius: 4px;
  padding: 16px 18px;
  text-align: left;
}

.data-stat__val {
  font-family: var(--font-display, 'ZCOOL XiaoWei', serif);
  font-size: 32px;
  font-weight: 500;
  color: var(--accent, #b54a32);
  line-height: 1.2;
  letter-spacing: 0.05em;
}

.data-stat__key {
  font-size: 13px;
  color: var(--text-primary, #2a2a2a);
  margin-top: 4px;
  letter-spacing: 0.1em;
}

.data-stat__src {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: var(--text-muted, #888);
  margin-top: 6px;
  letter-spacing: 0.05em;
}

/* ==================== Insights grid ==================== */
.insights-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-top: 20px;
}

@media (max-width: 960px) {
  .insights-grid { grid-template-columns: 1fr; }
}

.insights-col__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-display, 'ZCOOL XiaoWei', serif);
  font-size: 16px;
  color: var(--text-primary, #2a2a2a);
  margin: 0 0 12px;
  letter-spacing: 0.15em;
  font-weight: 500;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-light, #e0d8c5);
}

.insights-col__icon {
  font-size: 18px;
}

.insights-col {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

@media (max-width: 768px) {
  .narrative-hero__title { font-size: 32px; }
  .narrative-hero { padding: 36px 20px; }
  .narrative-step { padding: 20px; flex-direction: column; gap: 12px; }
  .narrative-step__num { font-size: 36px; }
  .narrative-step__title { font-size: 20px; }
}
</style>
