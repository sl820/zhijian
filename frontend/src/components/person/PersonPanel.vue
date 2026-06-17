<!--
  志鉴·星野图考 人物详情面板（M7 完整版）

  - 名片（朱砂印章式）
  - 1-2 跳局部子图
  - 跨源证据列表
  - RAG 入口（面板内嵌问答）
-->
<template>
  <aside class="person-panel" @click.stop>
    <header class="panel-header">
      <h2 class="panel-title">人物志</h2>
      <button class="panel-close" @click="$emit('close')" aria-label="关闭">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </header>

    <div class="panel-body" v-if="loadingDetail">
      <div class="panel-loading">索证中...</div>
    </div>

    <div class="panel-body" v-else>
      <!-- 名片 -->
      <PersonCard
        :name="displayName"
        :category="detail.person_type ?? person.category ?? null"
        :dynasty="detail.dynasty || person.dynasty"
        :years="detail.years"
        :region="detail.region"
        :courtesy_name="detail.courtesy_name"
        :family_name="detail.family_name"
        :role_of_family="detail.role_of_family"
        :sourceLabel="detail.source === 'jiapu' ? '上海图书馆家谱' : (detail.source || '')"
      />

      <!-- 1-2 跳子图 -->
      <SubgraphView
        :nodes="subgraph.nodes"
        :links="subgraph.links"
        :loading="loadingSubgraph"
        :centerUri="person.id"
        @node-click="onSubgraphNodeClick"
      />

      <!-- 跨源证据 -->
      <EvidenceList
        :evidence="evidence"
        :loading="loadingEvidence"
      />

      <!-- RAG 入口 -->
      <div class="panel-rag">
        <div class="rag-title">问此人物</div>
        <div class="rag-input-row">
          <input
            v-model="ragQuery"
            class="rag-input"
            placeholder="如：其父何人？何年生？"
            @keyup.enter="askRAG"
            :disabled="loadingRAG"
          />
          <button
            class="rag-btn"
            @click="askRAG"
            :disabled="!ragQuery.trim() || loadingRAG"
          >
            {{ loadingRAG ? '问...' : '问' }}
          </button>
        </div>
        <div v-if="ragAnswer" class="rag-answer">
          <div class="rag-answer-text">{{ ragAnswer }}</div>
          <div v-if="ragSources && ragSources.length" class="rag-sources">
            <span
              v-for="(s, i) in ragSources.slice(0, 3)"
              :key="i"
              class="rag-source-tag"
            >{{ s.source }}</span>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import PersonCard from './PersonCard.vue'
import SubgraphView from './SubgraphView.vue'
import EvidenceList from './EvidenceList.vue'
import { kgAPI } from '../../services/api.js'

const props = defineProps({
  person: { type: Object, required: true },
})
const emit = defineEmits(['close', 'navigate'])

const loadingDetail = ref(false)
const loadingSubgraph = ref(false)
const loadingEvidence = ref(false)
const loadingRAG = ref(false)

const detail = ref({})
const subgraph = ref({ nodes: [], links: [] })
const evidence = ref([])
const ragQuery = ref('')
const ragAnswer = ref('')
const ragSources = ref([])

const displayName = computed(() => {
  return props.person.name || props.person.id?.split('/').pop() || '未知'
})

watch(() => props.person, async (p) => {
  if (!p) return
  ragAnswer.value = ''
  ragQuery.value = ''
  detail.value = {}
  subgraph.value = { nodes: [], links: [] }
  evidence.value = []

  // 1. 详情 + 子图 + 证据 并发拉
  loadingDetail.value = true
  loadingSubgraph.value = true
  loadingEvidence.value = true

  try {
    // 详情（合并多源）— 试 jiapu / memory
    try {
      const res = await kgAPI.getPerson(p.id, 1, 'jiapu')
      detail.value = { ...res.person, source: 'jiapu' }
    } catch (e) {
      try {
        const res = await kgAPI.getPerson(displayName.value)
        detail.value = { ...res.person, source: 'memory' }
      } catch (_) {}
    }

    // 子图
    try {
      const sub = await kgAPI.getSubgraph(p.id, 'jiapu', 2, 80)
      subgraph.value = { nodes: sub.nodes, links: sub.links }
    } catch (e) {
      console.warn('[M7] subgraph load failed:', e)
    }
    loadingSubgraph.value = false

    // 证据
    try {
      const ev = await kgAPI.getEvidence(p.id, displayName.value)
      evidence.value = ev.evidence || []
    } catch (e) {
      console.warn('[M7] evidence load failed:', e)
    }
    loadingEvidence.value = false
    loadingDetail.value = false
  } catch (e) {
    console.error('[M7] detail load failed:', e)
    loadingDetail.value = false
    loadingSubgraph.value = false
    loadingEvidence.value = false
  }
}, { immediate: true })

async function askRAG() {
  const q = ragQuery.value.trim()
  if (!q) return
  loadingRAG.value = true
  ragAnswer.value = ''
  try {
    const res = await kgAPI.personRAG(props.person.id, q, displayName.value, 3)
    ragAnswer.value = res.answer || '（无答案）'
    ragSources.value = res.sources || []
  } catch (e) {
    ragAnswer.value = `问询失败：${e.response?.data?.detail || e.message || '未知错误'}`
  } finally {
    loadingRAG.value = false
  }
}

function onSubgraphNodeClick(nodeData) {
  // 子图节点点击 → 主图飞向（M6 GSAP 已经在 NebulaCanvas 里实现）
  // 这里只 emit 事件，让 KnowledgeView 决定是否切换 selectedNode
  emit('navigate', nodeData)
}
</script>

<style scoped>
@import '../../styles/xingye.css';

.person-panel {
  position: absolute;
  top: 80px;
  right: 24px;
  width: 360px;
  max-height: calc(100vh - 120px);
  z-index: 50;
  background: rgba(13, 13, 18, 0.92);
  border: 1px solid var(--xingye-vermilion-seal);
  border-radius: 6px;
  backdrop-filter: blur(12px);
  box-shadow: var(--xingye-glow-vermilion);
  color: var(--xingye-rice-main);
  font-family: var(--xingye-font-display);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  animation: panel-slide-in 0.35s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes panel-slide-in {
  from { transform: translateX(120%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--xingye-ink-light);
  background: rgba(168, 42, 31, 0.12);
}

.panel-title {
  margin: 0;
  font-size: 18px;
  font-weight: 500;
  letter-spacing: 0.4em;
  color: var(--xingye-rice-bright);
}

.panel-close {
  background: transparent;
  border: 1px solid var(--xingye-ink-pale);
  color: var(--xingye-rice-dim);
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.panel-close:hover {
  border-color: var(--xingye-vermilion-seal);
  color: var(--xingye-vermilion-bright);
}

.panel-body {
  flex: 1;
  padding: 16px 20px 20px;
  overflow-y: auto;
}

.panel-body::-webkit-scrollbar {
  width: 4px;
}
.panel-body::-webkit-scrollbar-track { background: transparent; }
.panel-body::-webkit-scrollbar-thumb {
  background: var(--xingye-ink-light);
  border-radius: 2px;
}

.panel-loading {
  padding: 40px 0;
  text-align: center;
  color: var(--xingye-ink-pale);
  font-size: 12px;
  letter-spacing: 0.3em;
}

/* RAG */
.panel-rag {
  margin-top: 16px;
  padding: 12px;
  background: rgba(13, 13, 18, 0.7);
  border: 1px solid var(--xingye-gold-dim);
  border-radius: 4px;
}

.rag-title {
  font-size: 13px;
  color: var(--xingye-gold-main);
  letter-spacing: 0.3em;
  margin-bottom: 8px;
}

.rag-input-row {
  display: flex;
  gap: 8px;
}

.rag-input {
  flex: 1;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid var(--xingye-ink-light);
  border-radius: 3px;
  color: var(--xingye-rice-main);
  font-family: var(--xingye-font-display);
  font-size: 13px;
  padding: 6px 10px;
  outline: none;
}
.rag-input:focus {
  border-color: var(--xingye-vermilion-seal);
  box-shadow: 0 0 6px rgba(194, 54, 42, 0.3);
}
.rag-input:disabled {
  opacity: 0.5;
}

.rag-btn {
  background: rgba(168, 42, 31, 0.18);
  border: 1px solid var(--xingye-vermilion-seal);
  color: var(--xingye-vermilion-bright);
  font-family: var(--xingye-font-display);
  font-size: 14px;
  width: 36px;
  border-radius: 3px;
  cursor: pointer;
  transition: all 0.2s;
}
.rag-btn:hover:not(:disabled) {
  background: rgba(194, 54, 42, 0.3);
  box-shadow: var(--xingye-glow-vermilion);
}
.rag-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.rag-answer {
  margin-top: 10px;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.4);
  border-radius: 3px;
  border-left: 2px solid var(--xingye-gold-main);
}

.rag-answer-text {
  font-size: 13px;
  line-height: 1.65;
  color: var(--xingye-rice-main);
  white-space: pre-wrap;
}

.rag-sources {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 8px;
}

.rag-source-tag {
  font-size: 10px;
  color: var(--xingye-gold-pale);
  background: rgba(168, 144, 96, 0.18);
  padding: 2px 6px;
  border-radius: 2px;
  letter-spacing: 0.1em;
}
</style>