<!--
  志鉴·星野图考 人物名片
  64x64 圆形篆书头像 + 朱砂姓名 + 朝代生卒 + 籍贯 + 官职 + 家族 + 史源标签

  Why：M7 详情面板核心。名片要做到"一望可知此人来历"。
  头像字符按 category 映射：
    0 姓氏族   → 姓首字（family_name?.[0]）
    1 妻妾     → 「女」
    2 其它     → 「人」
    3 官吏·文人 → 「文」
  无 category 时回退到姓名首字。
  真实头像后续接 Wikipedia / 百度百科。
-->
<template>
  <div class="person-card">
    <!-- 64x64 圆形篆书头像 -->
    <div class="card-avatar" :data-category="categoryLabel">
      <span class="avatar-char">{{ avatarChar }}</span>
      <span class="avatar-ring" aria-hidden="true"></span>
    </div>

    <!-- 主体：姓名 + 信息行 + 史源 -->
    <div class="card-body">
      <div class="card-name">{{ name }}</div>

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

      <div class="card-sources" v-if="sourceLabel">
        <span class="source-tag">史源 · {{ sourceLabel }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, required: true },
  category: { type: Number, default: null },
  dynasty: { type: String, default: '' },
  years: { type: String, default: '' },
  region: { type: String, default: '' },
  courtesy_name: { type: String, default: '' },
  family_name: { type: String, default: '' },
  role_of_family: { type: String, default: '' },
  sourceLabel: { type: String, default: '' },
})

// 头像字符：姓氏族=姓首字 / 妻=女 / 官吏=文 / 其它=人；无 category 时回退姓名首字
const avatarChar = computed(() => {
  if (props.category === 0 && props.family_name) return props.family_name.charAt(0)
  if (props.category === 1) return '女'
  if (props.category === 3) return '文'
  if (props.category === 2 || props.category === null || props.category === undefined) {
    if (props.category === 2) return '人'
    // 兜底：姓名首字（不知道 category 时）
    return (props.name || '？').charAt(0)
  }
  return (props.name || '？').charAt(0)
})

const categoryLabel = computed(() => {
  return ['clan', 'consort', 'other', 'official'][props.category ?? 2] || 'other'
})
</script>

<style scoped>
@import '../../styles/xingye.css';

.person-card {
  position: relative;
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--xingye-ink-light);
}

/* === 64x64 圆形篆书头像 === */
.card-avatar {
  position: relative;
  width: 64px;
  height: 64px;
  flex-shrink: 0;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(circle at 35% 30%,
    var(--xingye-vermilion-seal) 0%,
    var(--xingye-vermilion-main) 60%,
    var(--xingye-vermilion-deep) 100%);
  box-shadow:
    inset 0 0 6px rgba(0, 0, 0, 0.25),
    0 0 14px rgba(232, 72, 48, 0.5);
  overflow: hidden;
}

.avatar-char {
  font-family: var(--xingye-font-display);
  font-size: 30px;
  font-weight: 800;
  color: var(--xingye-rice-bright);
  text-shadow:
    0 0 6px rgba(240, 232, 212, 0.8),
    0 1px 2px rgba(0, 0, 0, 0.7);
  z-index: 1;
  line-height: 1;
  letter-spacing: -0.02em;
}

/* 外圈金粉环 */
.avatar-ring {
  position: absolute;
  inset: 2px;
  border: 2px solid var(--xingye-gold-main);
  border-radius: 50%;
  pointer-events: none;
  opacity: 0.85;
}

/* 官吏·文人 用米白底朱砂字（区别于朱砂底米白字） */
.card-avatar[data-category="official"] {
  background: radial-gradient(circle at 30% 30%,
    var(--xingye-rice-main) 0%,
    var(--xingye-rice-dim) 100%);
  box-shadow:
    inset 0 0 8px rgba(0, 0, 0, 0.2),
    0 0 10px rgba(240, 232, 212, 0.3);
}
.card-avatar[data-category="official"] .avatar-char {
  color: var(--xingye-vermilion-bright);
  text-shadow: 0 0 3px rgba(232, 72, 48, 0.5);
}

/* === 主体 === */
.card-body {
  flex: 1;
  min-width: 0;
}

.card-name {
  font-family: var(--xingye-font-display);
  font-size: 19px;
  font-weight: 700;
  color: var(--xingye-vermilion-bright);
  letter-spacing: 0.08em;
  text-shadow: 0 0 8px rgba(232, 72, 48, 0.4);
  margin-bottom: 6px;
  line-height: 1.2;
}

.card-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 2px 0;
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
