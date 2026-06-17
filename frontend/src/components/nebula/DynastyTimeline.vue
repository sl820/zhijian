<!--
  志鉴·星野图考 DynastyTimeline（M6 时间轴）
  底部横轴 pill bar：按朝代分组，多选 toggle，非激活朝代淡化（不在 DOM 删除）

  Props:
    - counts: { dynasty_id: count, ... } 当前布局中各朝代节点数（基于 birth_year）
    - active: Set< dynasty_id > 当前激活集合（null = 全部激活）
    - labels: Array<{id, label}> 朝代顺序定义

  Emits:
    - toggle(id): 切换某朝代的激活状态
-->
<template>
  <div class="dynasty-timeline">
    <div class="dynasty-timeline-label">朝代时间轴</div>
    <div class="dynasty-timeline-pills">
      <button
        v-for="d in orderedLabels"
        :key="d.id"
        class="dynasty-pill"
        :class="{ 'is-active': isActive(d.id), 'is-empty': (counts[d.id] || 0) === 0 }"
        :title="`${d.label} · ${counts[d.id] || 0} 颗星`"
        @click="$emit('toggle', d.id)"
      >
        <span class="dynasty-pill-label">{{ d.label }}</span>
        <span class="dynasty-pill-count">{{ counts[d.id] || 0 }}</span>
      </button>
    </div>
    <div class="dynasty-timeline-hint">
      点击朝代切换 · 多选
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  counts: { type: Object, default: () => ({}) },
  active: { type: [Set, Array, null], default: null },
  labels: { type: Array, required: true },
})

defineEmits(['toggle'])

const orderedLabels = computed(() => props.labels)

function isActive(id) {
  if (props.active == null) return true
  return props.active instanceof Set
    ? props.active.has(id)
    : props.active.includes(id)
}
</script>

<style scoped>
.dynasty-timeline {
  position: absolute;
  left: 50%;
  bottom: 24px;
  transform: translateX(-50%);
  z-index: 8;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 20px;
  background: linear-gradient(180deg,
    rgba(13, 13, 18, 0.85) 0%,
    rgba(26, 26, 36, 0.92) 100%);
  border: 1px solid var(--xingye-ink-light);
  border-radius: 4px;
  backdrop-filter: blur(8px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
  font-family: var(--xingye-font-display);
}

.dynasty-timeline-label {
  font-size: 12px;
  letter-spacing: 0.3em;
  color: var(--xingye-gold-main);
  writing-mode: vertical-rl;
  text-orientation: upright;
  user-select: none;
}

.dynasty-timeline-pills {
  display: flex;
  gap: 6px;
  align-items: center;
}

.dynasty-pill {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 56px;
  height: 44px;
  padding: 4px 8px;
  background: rgba(26, 26, 36, 0.6);
  border: 1px solid var(--xingye-ink-light);
  border-radius: 2px;
  color: var(--xingye-rice-dim);
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: inherit;
}

.dynasty-pill:hover {
  border-color: var(--xingye-gold-main);
  color: var(--xingye-rice-main);
}

.dynasty-pill.is-active {
  background: linear-gradient(180deg,
    rgba(194, 54, 42, 0.4) 0%,
    rgba(139, 40, 24, 0.3) 100%);
  border-color: var(--xingye-gold-main);
  color: var(--xingye-gold-bright);
  box-shadow: 0 0 8px rgba(212, 176, 112, 0.3);
}

.dynasty-pill.is-empty {
  opacity: 0.45;
}

.dynasty-pill-label {
  font-size: 13px;
  letter-spacing: 0.15em;
  font-weight: 500;
}

.dynasty-pill-count {
  font-size: 10px;
  margin-top: 2px;
  letter-spacing: 0.05em;
  opacity: 0.7;
  font-feature-settings: 'tnum';
}

.dynasty-timeline-hint {
  font-size: 10px;
  letter-spacing: 0.2em;
  color: var(--xingye-rice-dim);
  opacity: 0.5;
  writing-mode: vertical-rl;
  text-orientation: upright;
  user-select: none;
}
</style>
