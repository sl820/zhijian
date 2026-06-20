<!--
  InsightCard.vue — R9 研究发现单条卡片
  复用 pattern：source 标签 + metrics 数字 + 证据 computation 标签
-->
<template>
  <div class="insight-card" :class="['insight-card--' + (finding.source || 'computed')]">
    <div class="insight-card__head">
      <span class="insight-card__source" :class="['source-tag', 'source-tag--' + (finding.source || 'computed')]">
        {{ sourceLabel }}
      </span>
      <span v-if="finding.computation" class="insight-card__computation" :title="finding.computation">
        {{ computationLabel }}
      </span>
    </div>
    <p class="insight-card__text">{{ finding.text }}</p>
    <div v-if="metricsEntries.length" class="insight-card__metrics">
      <span v-for="m in metricsEntries" :key="m.key" class="metric-chip">
        <span class="metric-chip__key">{{ m.key }}</span>
        <span class="metric-chip__val">{{ m.val }}</span>
      </span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  finding: { type: Object, required: true },
})

const SOURCE_LABELS = {
  jiapu: '家谱',
  computed: '算法',
  layout: '布局',
  rag: 'RAG',
  kg: '知识图谱',
  cbdb: 'CBDB',
  source_router: '数据源',
  fallback: '兜底',
}

const sourceLabel = computed(() => {
  return SOURCE_LABELS[props.finding.source] || props.finding.source || '未知'
})

const computationLabel = computed(() => {
  const c = props.finding.computation || ''
  if (c.length <= 30) return c
  return c.slice(0, 28) + '…'
})

const metricsEntries = computed(() => {
  const m = props.finding.metrics || {}
  return Object.entries(m)
    .filter(([_, v]) => v !== null && v !== undefined && v !== '' && v !== [])
    .slice(0, 4)
    .map(([key, val]) => ({
      key,
      val: typeof val === 'number' ? formatNumber(val) : (typeof val === 'object' ? JSON.stringify(val).slice(0, 24) : String(val).slice(0, 24)),
    }))
})

function formatNumber(n) {
  if (typeof n !== 'number') return String(n)
  if (Math.abs(n) >= 1000) return n.toLocaleString()
  if (Number.isInteger(n)) return String(n)
  return n.toFixed(2)
}
</script>

<style scoped>
.insight-card {
  background: var(--bg-card, #faf8f3);
  border: 1px solid var(--border-light, #e0d8c5);
  border-left: 3px solid var(--accent, #b54a32);
  border-radius: 4px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: all 0.2s;
}

.insight-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  border-left-color: var(--accent-bright, #c2362a);
}

.insight-card--fallback {
  border-left-color: var(--warning, #c4a254);
  background: rgba(196, 162, 84, 0.04);
}

.insight-card__head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.insight-card__text {
  margin: 0;
  font-family: var(--font-serif, 'Noto Serif SC', serif);
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary, #2a2a2a);
}

.insight-card__metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.source-tag {
  display: inline-block;
  font-family: var(--font-display, 'ZCOOL XiaoWei', serif);
  font-size: 11px;
  letter-spacing: 0.15em;
  padding: 2px 8px;
  border-radius: 2px;
  background: rgba(181, 74, 50, 0.12);
  color: var(--accent, #b54a32);
}

.source-tag--jiapu { background: var(--accent-bg); color: var(--accent); }
.source-tag--computed { background: var(--secondary-bg); color: var(--secondary); }
.source-tag--source_router { background: var(--gold-faint); color: var(--gold-dim); }
.source-tag--rag { background: var(--warning-bg); color: var(--warning); }
.source-tag--kg { background: var(--success-bg); color: var(--success); }
.source-tag--fallback { background: var(--border-light); color: var(--text-muted); }

.insight-card__computation {
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: var(--text-muted, #888);
  background: rgba(0, 0, 0, 0.04);
  padding: 2px 6px;
  border-radius: 2px;
  letter-spacing: 0.05em;
}

.metric-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 2px;
  padding: 2px 6px;
}

.metric-chip__key {
  color: var(--text-muted, #888);
  font-family: 'JetBrains Mono', monospace;
}

.metric-chip__val {
  color: var(--text-primary, #2a2a2a);
  font-weight: 500;
}
</style>
