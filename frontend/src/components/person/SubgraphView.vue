<!--
  志鉴·星野图考 1-2 跳子图
  ECharts force-graph 渲染该人物 + 邻接

  Why：M7 子图联动 — 主图3D 看宏观，子图2D 看细节，双击可跳回主图。
-->
<template>
  <div class="subgraph-view">
    <div class="subgraph-header">
      <span class="title">关系子图</span>
      <span class="stats" v-if="!loading">{{ nodeCount }} 节点 · {{ linkCount }} 关系</span>
    </div>
    <div ref="chartRef" class="subgraph-chart" v-show="!loading"></div>
    <div v-if="loading" class="subgraph-loading">载录中...</div>
    <div v-if="!loading && !nodeCount" class="subgraph-empty">无关联人物</div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, computed, nextTick } from 'vue'
import * as echarts from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent, TitleComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([GraphChart, TooltipComponent, TitleComponent, CanvasRenderer])

import { PALETTE, CATEGORY_COLORS } from '../../constants/palette.js'

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  links: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  centerUri: { type: String, default: '' },
})
const emit = defineEmits(['node-click'])

const chartRef = ref(null)
let chart

const nodeCount = computed(() => props.nodes.length)
const linkCount = computed(() => props.links.length)

function buildOption() {
  const symbolSize = (val) => {
    if (val === props.centerUri) return 26
    return 12
  }

  const itemStyle = (params) => {
    if (params.data.is_center) {
      return { color: PALETTE.gold.bright, borderColor: PALETTE.vermilion.bright, borderWidth: 2 }
    }
    const cat = params.data.category ?? 2
    return { color: CATEGORY_COLORS[cat] || PALETTE.other }
  }

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(13, 13, 18, 0.95)',
      borderColor: PALETTE.vermilion.seal,
      borderWidth: 1,
      textStyle: { color: PALETTE.rice.main, fontFamily: '"LXGW WenKai TC", serif' },
      formatter: (p) => {
        if (p.dataType === 'node') {
          return `<b style="color:${PALETTE.gold.main}">${p.data.name}</b><br/>` +
                 `<span style="color:${PALETTE.rice.dim}">${p.data.dynasty || ''} ${p.data.role_of_family || ''}</span>`
        }
        return `<span style="color:${PALETTE.rice.dim}">${p.data.type || '关联'}</span>`
      },
    },
    animationDurationUpdate: 800,
    animationEasingUpdate: 'cubicInOut',
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      data: props.nodes.map(n => ({
        id: n.uri,
        name: n.name,
        category: n.person_type ?? n.category ?? 2,
        dynasty: n.dynasty || '',
        role_of_family: n.role_of_family || '',
        is_center: n.is_center,
        symbolSize: symbolSize(n.uri),
        itemStyle: itemStyle({ data: n }),
        label: {
          show: true,
          color: n.is_center ? PALETTE.gold.bright : PALETTE.rice.main,
          fontFamily: '"LXGW WenKai TC", serif',
          fontSize: n.is_center ? 14 : 11,
          fontWeight: n.is_center ? 600 : 400,
        },
      })),
      links: props.links.map(l => ({
        source: l.source,
        target: l.target,
        type: l.type,
        lineStyle: {
          color: PALETTE.ink.light,
          width: 1.2,
          opacity: 0.7,
          curveness: 0.1,
        },
      })),
      force: {
        repulsion: 220,
        edgeLength: [60, 110],
        gravity: 0.1,
        friction: 0.3,
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: { width: 2.5, color: PALETTE.gold.main },
      },
    }],
  }
}

async function renderChart() {
  if (!chartRef.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value, null, { renderer: 'canvas' })
    chart.on('click', { dataType: 'node' }, (params) => {
      emit('node-click', params.data)
    })
  }
  chart.setOption(buildOption(), true)
}

watch(() => [props.nodes, props.links], async () => {
  await nextTick()
  renderChart()
}, { deep: false })

onMounted(async () => {
  await nextTick()
  renderChart()
  window.addEventListener('resize', resizeChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeChart)
  chart?.dispose()
})

function resizeChart() {
  chart?.resize()
}
</script>

<style scoped>
@import '../../styles/xingye.css';

.subgraph-view {
  margin: 14px 0;
  padding: 12px 14px;
  background: rgba(13, 13, 18, 0.5);
  border: 1px solid var(--xingye-ink-light);
  border-radius: 4px;
}

.subgraph-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8px;
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
  letter-spacing: 0.1em;
}

.subgraph-chart {
  width: 100%;
  height: 200px;
  background: transparent;
}

.subgraph-loading,
.subgraph-empty {
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--xingye-font-display);
  font-size: 12px;
  color: var(--xingye-ink-pale);
  letter-spacing: 0.2em;
}
</style>