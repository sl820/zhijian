<!--
  志鉴·星野图考 人物详情面板
  M7 主体（M6 阶段为占位 stub）：
  - 名片（朱砂印章式）
  - 1-2 跳子图
  - 跨源证据列表
  - RAG 入口

  此处为最小可用版本，仅显示人物姓名 + 朝代。M7 阶段会扩展。
-->
<template>
  <aside class="person-panel" @click.stop>
    <header class="panel-header">
      <h2 class="panel-name">{{ person.name || person.id }}</h2>
      <button class="panel-close" @click="$emit('close')" aria-label="关闭">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    </header>
    <div class="panel-body">
      <div class="panel-row" v-if="person.dynasty">
        <span class="row-label">朝代</span>
        <span class="row-value">{{ person.dynasty }}</span>
      </div>
      <div class="panel-row" v-if="person.region">
        <span class="row-label">籍贯</span>
        <span class="row-value">{{ person.region }}</span>
      </div>
      <div class="panel-row">
        <span class="row-label">分类</span>
        <span class="row-value">{{ categoryName }}</span>
      </div>
      <p class="panel-placeholder">人物详情 · 子图 · 跨源证据 · RAG 入口（M7 待实现）</p>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { CATEGORY_NAMES } from '../../constants/palette.js'

const props = defineProps({
  person: { type: Object, required: true },
})
defineEmits(['close'])

const categoryName = computed(() => {
  return CATEGORY_NAMES[props.person.category ?? 2] || '其它人物'
})
</script>

<style scoped>
@import '../../styles/xingye.css';

.person-panel {
  position: absolute;
  top: 80px;
  right: 24px;
  width: 320px;
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
  animation: panel-slide-in 0.35s var(--ease-out, cubic-bezier(0.22, 1, 0.36, 1));
}

@keyframes panel-slide-in {
  from { transform: translateX(120%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--xingye-ink-light);
  background: rgba(168, 42, 31, 0.12);
}

.panel-name {
  margin: 0;
  font-size: 22px;
  font-weight: 500;
  letter-spacing: 0.12em;
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
  padding: 16px 20px;
  font-size: 13px;
}

.panel-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--xingye-ink-light);
}
.panel-row:last-of-type { border-bottom: none; }

.row-label {
  width: 50px;
  font-size: 11px;
  color: var(--xingye-gold-main);
  letter-spacing: 0.2em;
  text-align: right;
}

.row-value {
  flex: 1;
  color: var(--xingye-rice-main);
  letter-spacing: 0.08em;
}

.panel-placeholder {
  margin-top: 16px;
  padding: 12px;
  background: rgba(13, 13, 18, 0.6);
  border: 1px dashed var(--xingye-ink-pale);
  border-radius: 4px;
  font-size: 11px;
  color: var(--xingye-ink-pale);
  text-align: center;
  letter-spacing: 0.15em;
}
</style>