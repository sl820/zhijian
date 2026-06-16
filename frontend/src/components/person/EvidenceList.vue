<!--
  志鉴·星野图考 跨源证据列表
  列出该人物在不同源中的记录（家谱 / 基础知识库 / 古籍 / 地名志 / RAG 检索片段）
-->
<template>
  <div class="evidence-list">
    <div class="ev-header">
      <span class="title">跨源证据</span>
      <span class="stats" v-if="!loading">{{ evidence.length }} 条</span>
    </div>
    <div v-if="loading" class="ev-loading">索证中...</div>
    <div v-else-if="!evidence.length" class="ev-empty">暂无证据</div>
    <div v-else class="ev-items">
      <article
        v-for="(ev, idx) in evidence"
        :key="idx"
        class="ev-item"
        :class="['ev-type-' + ev.evidence_type]"
      >
        <div class="ev-meta">
          <span class="ev-source" :style="{ color: sourceColor(ev.source) }">
            {{ ev.source_label || ev.source }}
          </span>
          <span class="ev-type-tag">{{ typeLabel(ev.evidence_type) }}</span>
        </div>
        <h4 class="ev-title" v-if="ev.title">{{ ev.title }}</h4>
        <p class="ev-snippet">{{ ev.snippet }}</p>
        <div class="ev-score" v-if="ev.score !== undefined">
          相关度 {{ (1 - ev.score).toFixed(2) }}
        </div>
      </article>
    </div>
  </div>
</template>

<script setup>
import { PALETTE } from '../../constants/palette.js'

const props = defineProps({
  evidence: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
})

const TYPE_LABELS = {
  work_description: '家谱·始迁祖',
  place_record: '地名志',
  biography: '生平',
  rag_chunk: 'RAG 片段',
}

const SOURCE_COLORS = {
  jiapu: PALETTE.vermilion.bright,
  base: PALETTE.family || '#5b9b9c',
  memory: PALETTE.gold.main,
  rag: PALETTE.female || '#b85878',
  gufang: PALETTE.official,
  dimingzhi: '#8aaa8a',
  gmwx: '#a89060',
}

function sourceColor(src) {
  return SOURCE_COLORS[src] || PALETTE.rice.main
}

function typeLabel(t) {
  return TYPE_LABELS[t] || t
}
</script>

<style scoped>
@import '../../styles/xingye.css';

.evidence-list {
  margin: 14px 0;
}

.ev-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 10px;
}

.title {
  font-family: var(--xingye-font-display);
  font-size: 13px;
  color: var(--xingye-gold-main);
  letter-spacing: 0.25em;
}

.stats {
  font-size: 11px;
  color: var(--xingye-rice-dim);
}

.ev-loading,
.ev-empty {
  padding: 24px 0;
  text-align: center;
  font-family: var(--xingye-font-display);
  font-size: 12px;
  color: var(--xingye-ink-pale);
  letter-spacing: 0.2em;
}

.ev-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 280px;
  overflow-y: auto;
  padding-right: 4px;
}

.ev-items::-webkit-scrollbar {
  width: 4px;
}
.ev-items::-webkit-scrollbar-track {
  background: transparent;
}
.ev-items::-webkit-scrollbar-thumb {
  background: var(--xingye-ink-light);
  border-radius: 2px;
}

.ev-item {
  background: rgba(13, 13, 18, 0.7);
  border: 1px solid var(--xingye-ink-light);
  border-left: 3px solid var(--xingye-vermilion-seal);
  border-radius: 3px;
  padding: 8px 12px;
  transition: all 0.2s;
}

.ev-item:hover {
  background: rgba(168, 42, 31, 0.08);
  border-left-color: var(--xingye-vermilion-bright);
}

.ev-item.ev-type-rag_chunk {
  border-left-color: var(--xingye-gold-main);
}

.ev-item.ev-type-biography {
  border-left-color: var(--xingye-female || #b85878);
}

.ev-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.ev-source {
  font-family: var(--xingye-font-display);
  font-size: 11px;
  letter-spacing: 0.15em;
  font-weight: 500;
}

.ev-type-tag {
  font-size: 10px;
  color: var(--xingye-rice-dim);
  background: rgba(0, 0, 0, 0.3);
  padding: 1px 6px;
  border-radius: 2px;
  letter-spacing: 0.1em;
}

.ev-title {
  margin: 0 0 4px;
  font-family: var(--xingye-font-display);
  font-size: 13px;
  color: var(--xingye-rice-bright);
  font-weight: 500;
  letter-spacing: 0.05em;
}

.ev-snippet {
  margin: 0;
  font-size: 12px;
  line-height: 1.55;
  color: var(--xingye-rice-dim);
  font-family: var(--xingye-font-display);
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ev-score {
  margin-top: 4px;
  font-size: 10px;
  color: var(--xingye-gold-main);
  letter-spacing: 0.1em;
  font-family: var(--xingye-font-display);
}
</style>