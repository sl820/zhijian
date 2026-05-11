<template>
  <div class="compilation-view">
    <!-- 页面标题 -->
    <header class="page-header">
      <div class="header-left">
        <h1 class="page-title">
          <svg class="title-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="26" height="26">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
            <line x1="8" y1="6" x2="16" y2="6"/>
            <line x1="8" y1="10" x2="14" y2="10"/>
          </svg>
          多源辑佚
        </h1>
        <p class="page-subtitle">整合多个古籍来源，自动去重、融合、追踪版本血缘</p>
      </div>
      <div class="header-right">
        <span v-if="sources.length > 0" class="source-count">
          <span class="count-dot"></span>
          {{ sources.length }} 条来源
        </span>
      </div>
    </header>

    <!-- 主内容 -->
    <div class="main-layout">
      <!-- 左侧配置区域 -->
      <div class="config-column">
        <!-- 来源配置 -->
        <div class="config-card">
          <div class="config-card-header">
            <span class="config-card-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
              来源配置
            </span>
            <el-button size="small" type="primary" @click="addSource" class="add-btn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                <line x1="12" y1="5" x2="12" y2="19"/>
                <line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              添加
            </el-button>
          </div>

          <div class="sources-list">
            <TransitionGroup name="source-list">
              <div v-for="(source, index) in sources" :key="index" class="source-item">
                <div class="source-header">
                  <div class="source-badge">{{ index + 1 }}</div>
                  <el-select v-model="source.type" size="small" class="type-select" @change="handleTypeChange(source)">
                    <el-option label="ctext.org" value="ctext" />
                    <el-option label="自定义URL" value="custom" />
                    <el-option label="上传PDF" value="upload" />
                  </el-select>
                  <el-button size="small" text type="danger" @click="removeSource(index)" class="remove-btn">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                      <line x1="18" y1="6" x2="6" y2="18"/>
                      <line x1="6" y1="6" x2="18" y2="18"/>
                    </svg>
                  </el-button>
                </div>

                <!-- URL 输入 (ctext/custom) -->
                <template v-if="source.type === 'ctext' || source.type === 'custom'">
                  <el-input
                    v-model="source.url"
                    placeholder="输入URL或路径"
                    size="default"
                    clearable
                  />
                </template>

                <!-- PDF 上传 (upload) -->
                <template v-else-if="source.type === 'upload'">
                  <div class="upload-area">
                    <el-upload
                      :show-file-list="false"
                      :auto-upload="false"
                      accept=".pdf"
                      :before-upload="(file) => handlePDFUpload(file, index)"
                      class="pdf-uploader"
                    >
                      <el-button type="default" size="small" class="upload-btn">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14">
                          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                          <polyline points="14 2 14 8 20 8"/>
                          <line x1="12" y1="18" x2="12" y2="12"/>
                          <line x1="9" y1="15" x2="15" y2="15"/>
                        </svg>
                        {{ source.pdfFile?.name || '上传 PDF 文件' }}
                      </el-button>
                    </el-upload>
                    <div v-if="source.pdfLoading" class="pdf-loading">
                      <span class="loading-text">正在解析 PDF...</span>
                    </div>
                    <div v-else-if="source.text" class="pdf-info">
                      <span class="pdf-chars">{{ source.text.length }} 字符</span>
                    </div>
                  </div>
                </template>

                <div class="source-meta" v-if="source.metadata">
                  <el-input
                    v-model="source.metadata.year"
                    placeholder="年代 (如: 康熙、咸丰)"
                    size="small"
                    class="year-input"
                  />
                </div>
              </div>
            </TransitionGroup>

            <el-empty v-if="sources.length === 0" description="暂无来源，请添加" :image-size="60">
              <template #image>
                <svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
              </template>
            </el-empty>
          </div>
        </div>

        <!-- 融合参数 -->
        <div class="config-card">
          <div class="config-card-header">
            <span class="config-card-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16">
                <circle cx="12" cy="12" r="3"/>
                <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
              </svg>
              融合参数
            </span>
          </div>

          <div class="config-form">
            <!-- 去重阈值 -->
            <div class="config-item">
              <label class="config-label">去重相似度阈值</label>
              <div class="slider-container">
                <el-slider
                  v-model="config.dedupThreshold"
                  :min="0.5"
                  :max="1"
                  :step="0.05"
                  :show-tooltip="true"
                  :format-tooltip="val => (val * 100).toFixed(0) + '%'"
                />
              </div>
              <div class="threshold-display">
                <span class="threshold-value">{{ (config.dedupThreshold * 100).toFixed(0) }}%</span>
              </div>
            </div>

            <!-- 去重算法 -->
            <div class="config-item">
              <label class="config-label">去重算法</label>
              <el-radio-group v-model="config.dedupMethod" size="small" class="method-radio">
                <el-radio-button label="minhash">MinHash</el-radio-button>
                <el-radio-button label="simhash">SimHash</el-radio-button>
              </el-radio-group>
            </div>

            <!-- 融合策略 -->
            <div class="config-item">
              <label class="config-label">融合策略</label>
              <el-select v-model="config.mergeStrategy" size="default" class="strategy-select">
                <el-option label="优先完整版本" value="prefer_complete" />
                <el-option label="优先高质量版本" value="prefer_quality" />
                <el-option label="优先原始版本" value="prefer_original" />
                <el-option label="投票融合" value="vote_merge" />
                <el-option label="结构化融合" value="structural_merge" />
              </el-select>
            </div>

            <!-- 执行去重 -->
            <div class="config-item checkbox-item">
              <el-checkbox v-model="config.deduplicate">
                <span class="checkbox-text">执行去重</span>
              </el-checkbox>
            </div>

            <!-- 开始按钮 -->
            <el-button
              type="primary"
              size="large"
              :loading="compiling"
              @click="startCompilation"
              class="start-btn"
            >
              <svg v-if="!compiling" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <polygon points="5 3 19 12 5 21 5 3"/>
              </svg>
              {{ compiling ? '处理中...' : '开始辑佚' }}
            </el-button>
          </div>
        </div>
      </div>

      <!-- 右侧结果区域 -->
      <div class="result-column">
        <!-- 统计信息 -->
        <div v-if="result" class="stats-section">
          <div class="stats-grid">
            <div v-for="(stat, index) in statsData" :key="index" class="stat-card">
              <div class="stat-value">{{ stat.value }}</div>
              <div class="stat-label">{{ stat.label }}</div>
            </div>
          </div>
        </div>

        <!-- 融合结果 -->
        <div class="config-card result-card">
          <div class="config-card-header">
            <span class="config-card-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
              </svg>
              融合结果
            </span>
            <el-button v-if="result?.merged_text" size="small" @click="copyResult" class="copy-btn">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
              复制
            </el-button>
          </div>

          <div v-if="result?.merged_text" class="merged-text">
            <pre>{{ result.merged_text }}</pre>
          </div>

          <div v-else-if="!compiling" class="empty-result">
            <div class="empty-icon">
              <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                <line x1="8" y1="6" x2="16" y2="6"/>
                <line x1="8" y1="10" x2="14" y2="10"/>
              </svg>
            </div>
            <p class="empty-hint">请配置来源并开始辑佚</p>
            <p class="empty-sub-hint">融合多个古籍版本，生成统一文本</p>
          </div>

          <div v-else class="loading-state">
            <div class="loading-dots">
              <span class="loading-dot"></span>
              <span class="loading-dot"></span>
              <span class="loading-dot"></span>
            </div>
            <p>正在处理辑佚，请稍候...</p>
          </div>
        </div>

        <!-- 来源血缘 -->
        <div class="config-card provenance-card" v-if="result?.provenance">
          <div class="config-card-header">
            <span class="config-card-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16">
                <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
              </svg>
              来源血缘
            </span>
          </div>
          <div class="provenance-list">
            <TransitionGroup name="provenance-list">
              <div v-for="(item, index) in result.provenance" :key="index" class="provenance-item">
                <div class="provenance-marker">
                  <span class="marker-num">{{ index + 1 }}</span>
                </div>
                <div class="provenance-text">{{ item.text }}</div>
                <div class="provenance-sources">
                  <el-tag v-for="src in item.sources" :key="src" size="small" effect="plain" class="source-tag">
                    {{ src }}
                  </el-tag>
                </div>
              </div>
            </TransitionGroup>
          </div>
        </div>

        <!-- 重复组 -->
        <div class="config-card dup-card" v-if="result?.duplicate_groups?.length > 0">
          <div class="config-card-header">
            <span class="config-card-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="16" height="16">
                <rect x="8" y="8" width="12" height="12" rx="2"/>
                <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>
              </svg>
              重复组
              <span class="dup-count">{{ result.duplicate_groups.length }}</span>
            </span>
          </div>
          <div class="dup-groups-list">
            <div v-for="(group, index) in result.duplicate_groups" :key="index" class="dup-group" :class="'dup-severity-' + getDupSeverity(group.length)">
              <div class="dup-group-header">
                <span class="dup-group-badge">{{ index + 1 }}</span>
                <el-tag :type="getDupTagType(group.length)" size="small" effect="light">
                  {{ group.length }} 个重复
                </el-tag>
              </div>
              <div class="dup-group-sources">
                <div v-for="(src, srcIdx) in group" :key="srcIdx" class="dup-source">
                  <span class="source-index">{{ srcIdx + 1 }}</span>
                  来源 {{ src }}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { compilationAPI } from '@/services/api'
import { ElMessage } from 'element-plus'

// 来源列表
const sources = ref([
  {
    type: 'ctext',
    url: 'https://ctext.org/guang-an-zhi/kanji-xiange/zh',
    metadata: { year: '康熙' },
    pdfFile: null,
    text: '',
    pdfLoading: false
  }
])

// 配置
const config = reactive({
  dedupThreshold: 0.85,
  dedupMethod: 'minhash',
  mergeStrategy: 'prefer_complete',
  deduplicate: true
})

// 结果
const result = ref(null)
const compiling = ref(false)

// 统计数据计算
const statsData = computed(() => {
  if (!result.value) return []
  return [
    { value: result.value.total_source_count || 0, label: '总来源' },
    { value: result.value.unique_source_count || 0, label: '去重后' },
    { value: result.value.duplicate_group_count || 0, label: '重复组' },
    { value: (result.value.merge_info?.confidence || 0).toFixed(2), label: '置信度' }
  ]
})

function addSource() {
  sources.value.push({
    type: 'ctext',
    url: '',
    metadata: { year: '' },
    pdfFile: null,
    text: '',
    pdfLoading: false
  })
}

function handleTypeChange(source) {
  // 切换类型时清空相关数据
  if (source.type !== 'upload') {
    source.pdfFile = null
    source.text = ''
    source.url = ''
  }
}

async function handlePDFUpload(file, index) {
  if (file.type !== 'application/pdf') {
    ElMessage.error('请上传 PDF 文件')
    return false
  }

  sources.value[index].pdfFile = file
  sources.value[index].pdfLoading = true

  try {
    const response = await compilationAPI.parsePDF(file)
    sources.value[index].text = response.text || ''
    sources.value[index].url = `[PDF] ${file.name}`
    ElMessage.success(`PDF 解析完成：${response.page_count} 页，${response.char_count} 字符`)
  } catch (error) {
    console.error('PDF 解析失败:', error)
    ElMessage.error('PDF 解析失败：' + (error.message || '未知错误'))
  } finally {
    sources.value[index].pdfLoading = false
  }

  return false
}

function removeSource(index) {
  sources.value.splice(index, 1)
}

function getSourceType(type) {
  const types = {
    ctext: 'primary',
    custom: 'success',
    library: 'warning',
    local: 'info'
  }
  return types[type] || 'info'
}

function getSourceTypeLabel(type) {
  const labels = {
    ctext: 'ctext.org',
    custom: '自定义URL',
    library: '图书馆',
    local: '本地',
    upload: '上传PDF'
  }
  return labels[type] || type
}

function getDupSeverity(count) {
  if (count >= 5) return 'high'
  if (count >= 3) return 'medium'
  return 'low'
}

function getDupTagType(count) {
  if (count >= 5) return 'danger'
  if (count >= 3) return 'warning'
  return 'info'
}

async function startCompilation() {
  if (sources.value.length === 0) {
    ElMessage.warning('请至少添加一个来源')
    return
  }

  compiling.value = true
  result.value = null

  try {
    const sourceConfigs = sources.value.map(s => ({
      type: s.type,
      url: s.url,
      filters: s.metadata || {}
    }))

    result.value = await compilationAPI.compile(
      sourceConfigs,
      config.deduplicate,
      config.mergeStrategy
    )

    ElMessage.success('辑佚完成')
  } catch (error) {
    console.error('辑佚失败:', error)
    ElMessage.error('辑佚失败: ' + (error.message || error))
  } finally {
    compiling.value = false
  }
}

function copyResult() {
  if (result.value?.merged_text) {
    navigator.clipboard.writeText(result.value.merged_text)
    ElMessage.success('已复制到剪贴板')
  }
}
</script>

<style scoped>
/* ============================
   志鉴 · 多源辑佚
   设计：古籍书房 Digital Scriptorium
   ============================ */

.compilation-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-primary);
}

/* ==================== 页面标题 ==================== */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 28px;
  background: var(--bg-card);
  border-bottom: 1px solid rgba(181, 74, 50, 0.15);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 16px;
}

.page-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: 0.05em;
}

.title-icon {
  color: var(--accent);
}

.page-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
  font-family: var(--font-serif);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.source-count {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-secondary);
  padding: 6px 14px;
  background: var(--bg-secondary);
  border-radius: 4px;
  border: 1px solid rgba(181, 74, 50, 0.12);
  font-family: var(--font-serif);
}

.count-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
}

/* ==================== 主布局 ==================== */
.main-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 24px;
  overflow: hidden;
  padding: 24px 28px;
}

.config-column {
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow-y: auto;
}

.result-column {
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow-y: auto;
}

/* ==================== 配置卡片 ==================== */
.config-card {
  background: var(--bg-card);
  border: 1px solid rgba(181, 74, 50, 0.12);
  border-radius: 6px;
  overflow: hidden;
}

.config-card:hover {
  border-color: rgba(181, 74, 50, 0.25);
}

.config-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  background: var(--bg-secondary);
  border-bottom: 1px solid rgba(181, 74, 50, 0.1);
}

.config-card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.03em;
}

.config-card-title svg {
  color: var(--accent);
}

.add-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-serif);
}

/* ==================== 来源列表 ==================== */
.sources-list {
  padding: 14px;
  max-height: 320px;
  overflow-y: auto;
}

.source-item {
  padding: 14px;
  background: var(--bg-secondary);
  border-radius: 4px;
  margin-bottom: 12px;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.source-item:last-child {
  margin-bottom: 0;
}

.source-item:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 8px rgba(181, 74, 50, 0.08);
}

.source-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.source-badge {
  width: 22px;
  height: 22px;
  background: var(--accent);
  color: white;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  font-family: var(--font-mono);
}

.source-type-tag {
  font-family: var(--font-serif);
}

.remove-btn {
  margin-left: auto;
  opacity: 0.5;
  transition: opacity 0.2s ease;
}

.remove-btn:hover {
  opacity: 1;
}

.source-meta {
  margin-top: 10px;
}

/* ==================== PDF 上传 ==================== */
.type-select {
  width: 110px;
}

.type-select :deep(.el-input__wrapper) {
  background: var(--bg-card);
  border-color: rgba(181, 74, 50, 0.2);
  box-shadow: none;
  font-family: var(--font-serif);
  font-size: 12px;
}

.type-select :deep(.el-input.is-focus .el-input__wrapper) {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(181, 74, 50, 0.1);
}

.upload-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pdf-uploader {
  display: inline-block;
}

.pdf-uploader :deep(.el-upload) {
  display: inline-block;
}

.upload-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-serif);
  color: var(--text-secondary);
  border-color: #ccc5b5;
  background: var(--bg-card);
}

.upload-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
  background: rgba(181, 74, 50, 0.04);
}

.pdf-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.loading-text {
  font-family: var(--font-serif);
}

.pdf-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(107, 143, 138, 0.08);
  border-radius: 4px;
  font-size: 12px;
}

.pdf-chars {
  color: var(--secondary);
  font-family: var(--font-mono);
}

/* 来源列表动画 */
.source-list-enter-active,
.source-list-leave-active {
  transition: all 0.3s ease;
}

.source-list-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

.source-list-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

/* ==================== 参数表单 ==================== */
.config-form {
  padding: 16px 18px;
}

.config-item {
  margin-bottom: 20px;
}

.config-item:last-child {
  margin-bottom: 0;
}

.config-label {
  display: block;
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
  margin-bottom: 10px;
  font-family: var(--font-serif);
}

.slider-container {
  padding: 0 4px;
}

.threshold-display {
  text-align: center;
  margin-top: 8px;
}

.threshold-value {
  font-family: var(--font-mono);
  font-size: 16px;
  font-weight: 700;
  color: var(--accent);
}

.method-radio {
  display: flex;
  gap: 8px;
}

.method-radio :deep(.el-radio-button__inner) {
  background: var(--bg-secondary);
  border-color: rgba(181, 74, 50, 0.2);
  color: var(--text-secondary);
  font-family: var(--font-serif);
}

.method-radio :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

.strategy-select {
  width: 100%;
}

.strategy-select :deep(.el-input__wrapper) {
  background: var(--bg-secondary);
  border-color: rgba(181, 74, 50, 0.2);
  box-shadow: none;
}

.strategy-select :deep(.el-input.is-focus .el-input__wrapper) {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(181, 74, 50, 0.1);
}

.checkbox-item {
  padding-top: 4px;
}

.checkbox-text {
  font-family: var(--font-serif);
  font-size: 13px;
}

.start-btn {
  width: 100%;
  margin-top: 8px;
  height: 44px;
  font-size: 15px;
  font-family: var(--font-display);
  letter-spacing: 0.1em;
  background: var(--accent);
  border-color: var(--accent);
}

.start-btn:hover {
  background: #a03f2a;
  border-color: #a03f2a;
}

/* ==================== 统计信息 ==================== */
.stats-section {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid rgba(181, 74, 50, 0.12);
  border-radius: 6px;
  padding: 16px;
  text-align: center;
}

.stat-card:hover {
  border-color: rgba(181, 74, 50, 0.25);
}

.stat-value {
  font-family: var(--font-mono);
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
  font-family: var(--font-serif);
}

/* ==================== 结果区域 ==================== */
.result-card {
  min-height: 200px;
}

.copy-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: var(--font-serif);
}

.merged-text {
  max-height: 400px;
  overflow-y: auto;
  padding: 16px;
  background: var(--bg-secondary);
  border-radius: 4px;
  margin: 14px 18px 18px;
}

.merged-text pre {
  font-family: var(--font-serif);
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-wrap: break-word;
  color: var(--text-primary);
  margin: 0;
}

/* 空状态 */
.empty-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  color: var(--text-secondary);
}

.empty-icon {
  color: var(--accent);
  opacity: 0.35;
  margin-bottom: 12px;
}

.empty-hint {
  margin: 0;
  font-size: 15px;
  font-family: var(--font-display);
  color: var(--text-secondary);
  letter-spacing: 0.03em;
}

.empty-sub-hint {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
  font-family: var(--font-serif);
  opacity: 0.7;
}

/* 加载状态 */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  color: var(--text-secondary);
}

.loading-dots {
  display: flex;
  gap: 6px;
  margin-bottom: 12px;
}

.loading-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  animation: dotBounce 1.2s ease-in-out infinite;
}

.loading-dot:nth-child(1) { animation-delay: 0s; }
.loading-dot:nth-child(2) { animation-delay: 0.15s; }
.loading-dot:nth-child(3) { animation-delay: 0.3s; }

@keyframes dotBounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

/* ==================== 来源血缘 ==================== */
.provenance-card {
  animation: fadeIn 0.3s ease;
}

.provenance-list {
  padding: 14px;
  max-height: 220px;
  overflow-y: auto;
}

.provenance-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 4px;
  margin-bottom: 10px;
  border-left: 3px solid var(--accent);
}

.provenance-item:last-child {
  margin-bottom: 0;
}

.provenance-marker {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  background: var(--accent);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
}

.provenance-text {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  font-family: var(--font-serif);
  line-height: 1.6;
}

.provenance-sources {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.source-tag {
  font-family: var(--font-serif);
}

.provenance-list-enter-active,
.provenance-list-leave-active {
  transition: all 0.3s ease;
}

.provenance-list-enter-from,
.provenance-list-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* ==================== 重复组 ==================== */
.dup-card {
  animation: fadeIn 0.3s ease;
}

.dup-count {
  background: var(--accent);
  color: white;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
  font-weight: 600;
  margin-left: 8px;
  font-family: var(--font-mono);
}

.dup-groups-list {
  padding: 14px;
  max-height: 220px;
  overflow-y: auto;
}

.dup-group {
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 4px;
  margin-bottom: 10px;
  border-left: 3px solid var(--secondary);
}

.dup-group:last-child {
  margin-bottom: 0;
}

.dup-severity-high {
  border-left-color: var(--accent);
  background: linear-gradient(90deg, rgba(181, 74, 50, 0.06), var(--bg-secondary));
}

.dup-severity-medium {
  border-left-color: var(--secondary);
}

.dup-severity-low {
  border-left-color: var(--secondary);
}

.dup-group-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.dup-group-badge {
  width: 20px;
  height: 20px;
  background: var(--accent);
  color: white;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
}

.dup-severity-low .dup-group-badge {
  background: var(--secondary);
}

.dup-severity-medium .dup-group-badge {
  background: var(--secondary);
}

.dup-group-sources {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.dup-source {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: var(--bg-card);
  border-radius: 20px;
  font-size: 12px;
  color: var(--text-secondary);
  font-family: var(--font-serif);
  border: 1px solid rgba(181, 74, 50, 0.1);
}

.source-index {
  width: 16px;
  height: 16px;
  background: var(--bg-secondary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
}

/* ==================== 响应式 ==================== */
@media (max-width: 1100px) {
  .main-layout {
    grid-template-columns: 340px 1fr;
  }
}

@media (max-width: 900px) {
  .main-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
    padding: 16px 20px;
  }

  .config-column {
    flex-direction: row;
    overflow-x: auto;
  }

  .config-card {
    min-width: 300px;
  }

  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .page-header {
    padding: 12px 16px;
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }

  .page-title {
    font-size: 18px;
  }

  .sources-list {
    max-height: 240px;
  }

  .merged-text {
    max-height: 300px;
  }
}
</style>
