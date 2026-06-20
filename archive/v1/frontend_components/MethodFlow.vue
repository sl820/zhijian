<!--
  MethodFlow.vue — R9 方法栈 4 步流程图
  复用 ECharts 主题，简单 flex 步骤卡片
-->
<template>
  <div class="method-flow">
    <div v-for="(step, idx) in steps" :key="step.step" class="method-flow__step">
      <div class="method-flow__num">{{ step.step }}</div>
      <div class="method-flow__body">
        <div class="method-flow__name">{{ step.name }}</div>
        <div class="method-flow__tech">{{ step.tech }}</div>
      </div>
      <div v-if="idx < steps.length - 1" class="method-flow__arrow">→</div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  steps: { type: Array, default: () => [] },
})
</script>

<style scoped>
.method-flow {
  display: flex;
  align-items: stretch;
  gap: 0;
  flex-wrap: wrap;
}

.method-flow__step {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 200px;
  padding: 14px 16px;
  background: var(--bg-card, #faf8f3);
  border: 1px solid var(--border-light, #e0d8c5);
  border-right: none;
  position: relative;
}

.method-flow__step:last-child {
  border-right: 1px solid var(--border-light, #e0d8c5);
}

.method-flow__num {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--accent, #b54a32);
  color: var(--text-inverse, #f4efe6);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display, 'ZCOOL XiaoWei', serif);
  font-size: 16px;
  font-weight: 500;
}

.method-flow__body {
  flex: 1;
  min-width: 0;
}

.method-flow__name {
  font-family: var(--font-display, 'ZCOOL XiaoWei', serif);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, #2a2a2a);
  letter-spacing: 0.1em;
  margin-bottom: 2px;
}

.method-flow__tech {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--text-muted, #888);
  line-height: 1.5;
}

.method-flow__arrow {
  position: absolute;
  right: -10px;
  top: 50%;
  transform: translateY(-50%);
  z-index: 2;
  background: var(--bg-primary, #f4efe6);
  color: var(--accent, #b54a32);
  font-size: 16px;
  font-weight: 700;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
}

@media (max-width: 768px) {
  .method-flow__step { flex: 1 1 100%; border-right: 1px solid var(--border-light, #e0d8c5); }
  .method-flow__arrow { display: none; }
}
</style>
