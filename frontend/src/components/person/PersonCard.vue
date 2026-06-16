<!--
  志鉴·星野图考 人物名片
  朱砂印章式姓名 + 朝代生卒 + 籍贯 + 官职 + 家族 + 史源标签

  Why：M7 详情面板核心。名片要做到"一望可知此人来历"。
-->
<template>
  <div class="person-card">
    <!-- 朱砂印章 -->
    <div class="card-seal">
      <div class="seal-name">{{ name }}</div>
      <div class="seal-line">史</div>
    </div>

    <!-- 基本信息 -->
    <div class="card-body">
      <div class="card-row" v-if="dynasty">
        <span class="row-label">朝代</span>
        <span class="row-value dynasty">{{ dynasty }}</span>
      </div>
      <div class="card-row" v-if="years">
        <span class="row-label">生卒</span>
        <span class="row-value">{{ years }}</span>
      </div>
      <div class="card-row" v-if="region">
        <span class="row-label">籍贯</span>
        <span class="row-value">{{ region }}</span>
      </div>
      <div class="card-row" v-if="courtesy_name">
        <span class="row-label">字</span>
        <span class="row-value">{{ courtesy_name }}</span>
      </div>
      <div class="card-row" v-if="family_name">
        <span class="row-label">姓</span>
        <span class="row-value">{{ family_name }}</span>
      </div>
      <div class="card-row" v-if="role_of_family">
        <span class="row-label">身份</span>
        <span class="row-value">{{ role_of_family }}</span>
      </div>

      <!-- 史源标签 -->
      <div class="card-sources" v-if="sourceLabel">
        <span class="source-tag">史源 · {{ sourceLabel }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  name: { type: String, required: true },
  dynasty: { type: String, default: '' },
  years: { type: String, default: '' },
  region: { type: String, default: '' },
  courtesy_name: { type: String, default: '' },
  family_name: { type: String, default: '' },
  role_of_family: { type: String, default: '' },
  sourceLabel: { type: String, default: '' },
})
</script>

<style scoped>
@import '../../styles/xingye.css';

.person-card {
  position: relative;
  display: flex;
  gap: 16px;
  align-items: flex-start;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--xingye-ink-light);
}

/* 朱砂印章 */
.card-seal {
  position: relative;
  width: 56px;
  height: 56px;
  flex-shrink: 0;
  border: 2.5px solid var(--xingye-vermilion-seal);
  border-radius: 4px;
  background: rgba(168, 42, 31, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--xingye-glow-vermilion);
  transform: rotate(-3deg);
}

.seal-name {
  font-family: var(--xingye-font-display);
  font-size: 18px;
  font-weight: 700;
  color: var(--xingye-vermilion-bright);
  letter-spacing: 0.05em;
  text-shadow: 0 0 8px rgba(232, 72, 48, 0.6);
  z-index: 1;
}

.seal-line {
  position: absolute;
  inset: 4px;
  border: 1px solid var(--xingye-vermilion-deep);
  border-radius: 2px;
  pointer-events: none;
}

/* 基本信息 */
.card-body {
  flex: 1;
  min-width: 0;
}

.card-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 3px 0;
}

.row-label {
  width: 42px;
  font-size: 11px;
  color: var(--xingye-gold-main);
  letter-spacing: 0.25em;
  text-align: right;
  font-family: var(--xingye-font-display);
}

.row-value {
  flex: 1;
  font-size: 13px;
  color: var(--xingye-rice-main);
  letter-spacing: 0.05em;
  font-family: var(--xingye-font-display);
}

.row-value.dynasty {
  color: var(--xingye-gold-bright);
  font-weight: 500;
}

.card-sources {
  margin-top: 10px;
}

.source-tag {
  display: inline-block;
  font-size: 11px;
  color: var(--xingye-rice-dim);
  background: rgba(13, 13, 18, 0.6);
  border: 1px solid var(--xingye-ink-pale);
  border-radius: 3px;
  padding: 2px 8px;
  letter-spacing: 0.15em;
  font-family: var(--xingye-font-display);
}
</style>