<!--
  JuryPackModal.vue — R9 一键评委包弹窗
  /api/v1/demo/jury_pack 全部内容集中展示
-->
<template>
  <transition name="modal">
    <div v-if="open" class="jury-modal" @click.self="onClose">
      <div class="jury-modal__card">
        <div class="jury-modal__head">
          <div>
            <div class="jury-modal__eyebrow">R9 · JURY PACK</div>
            <h2 class="jury-modal__title">{{ systemSummary.name || '志鉴·星野图考' }}</h2>
            <p class="jury-modal__tagline">{{ systemSummary.tagline || '' }}</p>
          </div>
          <button class="jury-modal__close" @click="onClose" aria-label="关闭">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>

        <div class="jury-modal__body">
          <!-- 系统能力 -->
          <section v-if="capabilities.length" class="jury-section">
            <h3 class="jury-section__title">▍ 核心能力</h3>
            <ul class="jury-cap-list">
              <li v-for="(c, i) in capabilities" :key="i" class="jury-cap-item">{{ c }}</li>
            </ul>
          </section>

          <!-- 数据规模 -->
          <section v-if="dataScale" class="jury-section">
            <h3 class="jury-section__title">▍ 数据规模</h3>
            <div class="jury-stats">
              <div class="jury-stat">
                <div class="jury-stat__val">{{ formatNum(dataScale.jiapu_persons) }}</div>
                <div class="jury-stat__key">家谱人物</div>
              </div>
              <div class="jury-stat">
                <div class="jury-stat__val">{{ dataScale.sources_registered || 0 }}</div>
                <div class="jury-stat__key">数据源注册</div>
              </div>
              <div class="jury-stat">
                <div class="jury-stat__val">{{ dataScale.sources_enabled || 0 }}</div>
                <div class="jury-stat__key">数据源启用</div>
              </div>
              <div class="jury-stat">
                <div class="jury-stat__val">{{ formatNum(dataScale.demo_node_limit) }}</div>
                <div class="jury-stat__key">节点上限</div>
              </div>
            </div>
          </section>

          <!-- 关键发现 -->
          <section v-if="topInsights.length" class="jury-section">
            <h3 class="jury-section__title">▍ 核心发现</h3>
            <div class="jury-insights">
              <InsightCard v-for="(f, i) in topInsights" :key="i" :finding="f" />
            </div>
          </section>

          <!-- 关键可视化 -->
          <section v-if="keyVisuals.length" class="jury-section">
            <h3 class="jury-section__title">▍ 关键可视化</h3>
            <div class="jury-visuals">
              <div v-for="v in keyVisuals" :key="v.id" class="jury-visual">
                <div class="jury-visual__name">{{ v.name }}</div>
                <div class="jury-visual__route">{{ v.route }}</div>
                <div class="jury-visual__desc">{{ v.description }}</div>
              </div>
            </div>
          </section>

          <!-- 示范问题 -->
          <section v-if="exampleQuestions.length" class="jury-section">
            <h3 class="jury-section__title">▍ 评委可能问的问题</h3>
            <ol class="jury-q-list">
              <li v-for="(q, i) in exampleQuestions" :key="i" class="jury-q-item">{{ q }}</li>
            </ol>
          </section>

          <!-- 兜底证据 -->
          <section v-if="fallbackEvidence.length" class="jury-section">
            <h3 class="jury-section__title">▍ 永不 500 证据</h3>
            <ul class="jury-fb-list">
              <li v-for="(f, i) in fallbackEvidence" :key="i" class="jury-fb-item">{{ f }}</li>
            </ul>
          </section>

          <!-- fallback notice -->
          <div v-if="!hasUsableData" class="jury-modal__empty">
            暂无评委包数据（请确认后端 /api/v1/demo/jury_pack 可达）
          </div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed } from 'vue'
import InsightCard from './InsightCard.vue'

const props = defineProps({
  open: { type: Boolean, default: false },
  pack: { type: Object, default: () => null },
})
const emit = defineEmits(['close'])

const onClose = () => emit('close')

const systemSummary = computed(() => props.pack?.system_summary || {})
const capabilities = computed(() => systemSummary.value?.core_capabilities || [])
const dataScale = computed(() => props.pack?.data_scale || null)
const topInsights = computed(() => props.pack?.top_insights || [])
const keyVisuals = computed(() => props.pack?.key_visualizations || [])
const exampleQuestions = computed(() => props.pack?.example_questions || [])
const fallbackEvidence = computed(() => props.pack?.fallback_evidence || [])

const hasUsableData = computed(() => Boolean(
  capabilities.value.length || dataScale.value || topInsights.value.length
))

function formatNum(n) {
  if (n == null) return '—'
  if (typeof n !== 'number') return String(n)
  if (Math.abs(n) >= 1000) return n.toLocaleString()
  return String(n)
}
</script>

<style scoped>
.jury-modal {
  position: fixed;
  inset: 0;
  background: rgba(13, 13, 18, 0.65);
  backdrop-filter: blur(6px);
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  font-family: var(--font-serif, 'Noto Serif SC', serif);
}

.jury-modal__card {
  background: var(--bg-primary, #f4efe6);
  border: 1px solid var(--accent, #b54a32);
  border-radius: 6px;
  max-width: 720px;
  width: 100%;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.4);
  overflow: hidden;
}

.jury-modal__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-light, #e0d8c5);
  background: rgba(181, 74, 50, 0.06);
}

.jury-modal__eyebrow {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.3em;
  color: var(--accent, #b54a32);
  margin-bottom: 4px;
}

.jury-modal__title {
  margin: 0;
  font-family: var(--font-display, 'ZCOOL XiaoWei', serif);
  font-size: 22px;
  color: var(--text-primary, #2a2a2a);
  letter-spacing: 0.15em;
  font-weight: 500;
}

.jury-modal__tagline {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-muted, #888);
  letter-spacing: 0.05em;
}

.jury-modal__close {
  background: transparent;
  border: 1px solid var(--border-light, #e0d8c5);
  color: var(--text-secondary, #6b6149);
  width: 32px;
  height: 32px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s;
}

.jury-modal__close:hover {
  border-color: var(--accent, #b54a32);
  color: var(--accent, #b54a32);
}

.jury-modal__body {
  flex: 1;
  overflow-y: auto;
  padding: 18px 24px 24px;
}

.jury-modal__body::-webkit-scrollbar { width: 4px; }
.jury-modal__body::-webkit-scrollbar-thumb { background: var(--border-medium, #c4b89a); border-radius: 2px; }

.jury-section {
  margin-bottom: 20px;
}

.jury-section__title {
  font-family: var(--font-display, 'ZCOOL XiaoWei', serif);
  font-size: 14px;
  color: var(--accent, #b54a32);
  letter-spacing: 0.2em;
  margin: 0 0 10px;
  font-weight: 500;
}

.jury-cap-list,
.jury-q-list,
.jury-fb-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.85;
  color: var(--text-primary, #2a2a2a);
}

.jury-cap-item::marker,
.jury-q-item::marker {
  color: var(--accent, #b54a32);
}

.jury-fb-list {
  list-style: none;
  padding: 0;
}

.jury-fb-item {
  padding: 6px 10px;
  background: var(--success-bg);
  border-left: 2px solid var(--success);
  border-radius: 2px;
  margin-bottom: 6px;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text-primary);
}

.jury-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
}

.jury-stat {
  background: var(--bg-card, #faf8f3);
  border: 1px solid var(--border-light, #e0d8c5);
  border-radius: 4px;
  padding: 10px 12px;
  text-align: center;
}

.jury-stat__val {
  font-family: var(--font-display, 'ZCOOL XiaoWei', serif);
  font-size: 22px;
  color: var(--accent, #b54a32);
  font-weight: 500;
  letter-spacing: 0.05em;
}

.jury-stat__key {
  font-size: 11px;
  color: var(--text-muted, #888);
  letter-spacing: 0.15em;
  margin-top: 2px;
}

.jury-insights {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.jury-visuals {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px;
}

.jury-visual {
  background: var(--bg-card, #faf8f3);
  border: 1px solid var(--border-light, #e0d8c5);
  border-radius: 4px;
  padding: 10px 12px;
  transition: all 0.2s;
  cursor: pointer;
}

.jury-visual:hover {
  border-color: var(--accent, #b54a32);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.jury-visual__name {
  font-family: var(--font-display, 'ZCOOL XiaoWei', serif);
  font-size: 13px;
  color: var(--text-primary, #2a2a2a);
  margin-bottom: 2px;
  letter-spacing: 0.08em;
}

.jury-visual__route {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: var(--accent, #b54a32);
  margin-bottom: 4px;
}

.jury-visual__desc {
  font-size: 11px;
  color: var(--text-muted, #888);
  line-height: 1.5;
}

.jury-modal__empty {
  padding: 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  background: var(--warning-bg);
  border: 1px dashed var(--warning);
  border-radius: 4px;
}

.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.25s;
}
.modal-enter-from,
.modal-leave-to { opacity: 0; }
</style>
