<template>
  <div class="collation-view">
    <!-- 顶部栏 -->
    <header class="page-header">
      <div class="header-left">
        <h1 class="page-title">多版本校勘</h1>
        <p class="page-subtitle">对比不同版本方志 · 自动发现差异 · 版本保存复用</p>
      </div>
      <div class="header-right">
        <div class="version-count-switch">
          <span class="switch-label">版本数量：</span>
          <el-button-group>
            <el-button :type="versionCount === 2 ? 'primary' : 'default'" size="small" @click="setVersionCount(2)">2</el-button>
            <el-button :type="versionCount === 3 ? 'primary' : 'default'" size="small" @click="setVersionCount(3)">3</el-button>
            <el-button :type="versionCount === 4 ? 'primary' : 'default'" size="small" @click="setVersionCount(4)">4</el-button>
          </el-button-group>
        </div>
        <span v-if="result" class="diff-badge">
          {{ result.diffs?.length || 0 }} 处差异
        </span>
      </div>
    </header>

    <!-- 主内容 -->
    <div class="main-content">
      <!-- 版本管理栏 -->
      <section class="version-manager-bar">
        <div class="saved-versions">
          <span class="bar-label">已保存版本：</span>
          <div class="version-chips">
            <el-tag
              v-for="v in savedVersions"
              :key="v.id"
              closable
              @close="handleDeleteVersion(v.id)"
              class="version-chip"
            >
              {{ v.name }} ({{ v.char_count }}字)
            </el-tag>
            <span v-if="savedVersions.length === 0" class="no-versions">暂无保存的版本</span>
          </div>
        </div>
        <el-button size="small" @click="loadSavedVersions" :loading="loadingVersions">
          刷新列表
        </el-button>
      </section>

      <!-- 对比区域 -->
      <section class="compare-section" :class="`versions-${versionCount}`">
        <div
          v-for="(panel, index) in panels"
          :key="index"
          class="text-panel"
        >
          <div class="panel-header">
            <div class="version-marker">
              <span class="marker-label">版本 {{ String.fromCharCode(65 + index) }}</span>
            </div>
            <el-select
              v-model="panel.selectedVersionId"
              placeholder="选择已保存版本"
              size="default"
              class="version-select"
              clearable
              @change="handleVersionSelect(index)"
            >
              <el-option
                v-for="v in savedVersions"
                :key="v.id"
                :label="v.name"
                :value="v.id"
              />
            </el-select>
          </div>
          <div class="panel-body">
            <el-input
              v-model="panel.text"
              type="textarea"
              :rows="8"
              :placeholder="`输入版本 ${String.fromCharCode(65 + index)} 内容，或上传文件...`"
              class="text-input"
              @input="updatePanelText(index)"
            />
          </div>
          <div class="panel-footer">
            <div class="upload-actions">
              <el-upload :show-file-list="false" :auto-upload="false" :before-upload="(file) => handleUpload(file, index, 'image')">
                <el-button type="default" size="small" class="upload-btn">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
                  </svg>
                  图片OCR
                </el-button>
              </el-upload>
              <el-upload :show-file-list="false" :auto-upload="false" :before-upload="(file) => handleUpload(file, index, 'text')">
                <el-button type="default" size="small" class="upload-btn">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                  </svg>
                  文本上传
                </el-button>
              </el-upload>
              <el-upload :show-file-list="false" :auto-upload="false" accept=".pdf" :before-upload="(file) => handleUpload(file, index, 'pdf')">
                <el-button type="default" size="small" class="upload-btn">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="14" height="14">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                  </svg>
                  PDF上传
                </el-button>
              </el-upload>
            </div>
            <div class="text-stats">
              <span>{{ countChars(panel.text) }} 字符</span>
              <span class="stat-sep">·</span>
              <span>{{ countSentences(panel.text) }} 句</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 操作栏 -->
      <section class="action-bar">
        <el-button type="primary" size="large" :loading="comparing" @click="startCompare" class="btn-compare">
          开始校勘 ({{ versionCount }}个版本)
        </el-button>
        <el-button size="large" @click="resetAll" class="btn-reset">重置</el-button>
        <el-button v-if="result" size="large" @click="exportResult" class="btn-export">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          导出结果
        </el-button>
      </section>

      <!-- 结果区域 -->
      <section v-if="result" class="results-section">
        <!-- 对齐矩阵 -->
        <div class="matrix-card">
          <h3 class="card-title">版本对齐矩阵</h3>
          <div class="matrix-table">
            <table>
              <thead>
                <tr>
                  <th></th>
                  <th v-for="(name, i) in result.summary?.version_names || []" :key="i">
                    {{ String.fromCharCode(65 + i) }}: {{ name }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in result.alignment_matrix || []" :key="i">
                  <th>{{ String.fromCharCode(65 + i) }}</th>
                  <td v-for="(score, j) in row" :key="j" :class="{ 'diag': i === j }">
                    {{ (score * 100).toFixed(1) }}%
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 分数卡片 -->
        <div class="score-grid">
          <div class="score-card">
            <div class="score-value">{{ result.diffs?.length || 0 }}</div>
            <div class="score-label">差异总数</div>
          </div>
          <div class="score-card" v-for="(count, type) in result.summary?.by_type || {}" :key="type">
            <div class="score-value">{{ count }}</div>
            <div class="score-label">{{ getTypeLabel(type) }}</div>
          </div>
        </div>

        <!-- 图表 -->
        <div class="charts-row">
          <div class="chart-card">
            <h3 class="chart-title">差异类型分布</h3>
            <div ref="pieChartRef" class="chart-container"></div>
          </div>
          <div class="chart-card">
            <h3 class="chart-title">版本字符数对比</h3>
            <div ref="barChartRef" class="chart-container"></div>
          </div>
        </div>

        <!-- 差异列表 -->
        <div class="diff-section">
          <div class="diff-header">
            <h3 class="diff-title">差异详情</h3>
            <div class="diff-actions">
              <el-input v-model="searchText" placeholder="搜索差异..." prefix-icon="Search" size="default" class="search-input" clearable />
              <el-select v-model="filterType" placeholder="筛选类型" size="default" clearable class="type-filter">
                <el-option label="全部" value="" />
                <el-option label="增文" value="insertion" />
                <el-option label="删文" value="deletion" />
                <el-option label="替换" value="substitution" />
                <el-option label="异体" value="variant" />
              </el-select>
            </div>
          </div>

          <div class="diff-table">
            <el-table :data="filteredDiffs" stripe style="width: 100%" max-height="400">
              <el-table-column type="index" label="序号" width="60" />
              <el-table-column label="类型" width="100">
                <template #default="{ row }">
                  <el-tag :type="getTagType(row.type)" size="small">{{ getTypeLabel(row.type) }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="对比" width="100">
                <template #default="{ row }">
                  <span class="compare-label">{{ row.compare_with || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="版本 A" min-width="150">
                <template #default="{ row }">
                  <span class="diff-text" :class="{ 'text-del': row.type === 'deletion' }">{{ row.text_a || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="版本 B" min-width="150">
                <template #default="{ row }">
                  <span class="diff-text" :class="{ 'text-ins': row.type === 'insertion' }">{{ row.text_b || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="position" label="位置" width="100" />
            </el-table>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { collationAPI, ocrAPI } from '@/services/api'
import { GAZETTEER_VERSIONS, DIFF_TYPES } from '@/constants'
import * as echarts from 'echarts'

// 状态
const versionCount = ref(2)
const panels = ref([])
const comparing = ref(false)
const result = ref(null)
const searchText = ref('')
const filterType = ref('')
const savedVersions = ref([])
const loadingVersions = ref(false)

// 图表 refs
const pieChartRef = ref(null)
const barChartRef = ref(null)
let pieChart = null
let barChart = null

// 初始化面板
function initPanels(count) {
  const newPanels = []
  for (let i = 0; i < count; i++) {
    newPanels.push({
      text: '',
      selectedVersionId: '',
      metadata: {}
    })
  }
  panels.value = newPanels
}

// 设置版本数量
function setVersionCount(count) {
  versionCount.value = count
  // 保留现有面板的内容
  while (panels.value.length < count) {
    panels.value.push({ text: '', selectedVersionId: '', metadata: {} })
  }
  panels.value = panels.value.slice(0, count)
}

// 加载已保存版本
async function loadSavedVersions() {
  loadingVersions.value = true
  try {
    const response = await collationAPI.listVersions()
    savedVersions.value = response.versions || []
  } catch (error) {
    console.error('加载版本列表失败:', error)
  } finally {
    loadingVersions.value = false
  }
}

// 删除版本
async function handleDeleteVersion(versionId) {
  try {
    await collationAPI.deleteVersion(versionId)
    ElMessage.success('版本已删除')
    await loadSavedVersions()
    // 清除选择该版本的面板
    panels.value.forEach(p => {
      if (p.selectedVersionId === versionId) {
        p.selectedVersionId = ''
      }
    })
  } catch (error) {
    console.error('删除版本失败:', error)
    ElMessage.error('删除失败')
  }
}

// 选择已保存版本
async function handleVersionSelect(panelIndex) {
  const versionId = panels.value[panelIndex].selectedVersionId
  if (!versionId) return

  try {
    const response = await collationAPI.getVersion(versionId)
    panels.value[panelIndex].text = response.text_content || ''
    panels.value[panelIndex].metadata = response.metadata || {}
    ElMessage.success(`已加载版本: ${response.name}`)
  } catch (error) {
    console.error('加载版本失败:', error)
    ElMessage.error('加载版本失败')
  }
}

// 处理文件上传
async function handleUpload(file, panelIndex, uploadType) {
  const isImage = uploadType === 'image'
  const isPdf = uploadType === 'pdf'

  if (isImage && !file.type.startsWith('image/')) {
    ElMessage.error('请上传图片文件')
    return false
  }

  if (isPdf && file.type !== 'application/pdf') {
    ElMessage.error('请上传 PDF 文件')
    return false
  }

  try {
    if (isImage) {
      // 图片 OCR
      ElMessage.info('正在进行文字识别，请稍候...')
      const response = await ocrAPI.recognize(file)
      const text = response.pages?.map(p => p.text).join('\n') || ''
      panels.value[panelIndex].text = text
      ElMessage.success(`识别完成：${response.pages?.length || 0} 页，${countChars(text)} 字符`)
    } else if (isPdf) {
      // PDF 解析
      ElMessage.info('正在解析 PDF，请稍候...')
      const response = await collationAPI.parsePDF(file)
      panels.value[panelIndex].text = response.text || ''
      ElMessage.success(`PDF 解析完成：${response.page_count || 0} 页，${response.char_count || 0} 字符`)
    } else {
      // 文本文件
      const text = await readTextFile(file)
      panels.value[panelIndex].text = text
      ElMessage.success(`已加载文本文件：${countChars(text)} 字符`)
    }
  } catch (error) {
    console.error('文件处理失败:', error)
    ElMessage.error('文件处理失败：' + (error.message || '未知错误'))
  }
  return false
}

// 读取文本文件内容
function readTextFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => resolve(e.target.result)
    reader.onerror = reject
    reader.readAsText(file, 'utf-8')
  })
}

// 更新面板文本
function updatePanelText(index) {
  // 清除该面板的版本选择（因为用户正在编辑文本）
  panels.value[index].selectedVersionId = ''
}

// 工具函数
function countChars(text) {
  return text?.length || 0
}

function countSentences(text) {
  if (!text) return 0
  const matches = text.match(/[。！？\n]+/g)
  return matches ? matches.length + 1 : 1
}

function getTypeLabel(type) {
  return DIFF_TYPES[type]?.label || type
}

function getTagType(type) {
  const map = {
    insertion: 'success',
    deletion: 'danger',
    substitution: 'warning',
    variant: 'info'
  }
  return map[type] || 'info'
}

// 开始校勘
async function startCompare() {
  const texts = panels.value.map(p => p.text).filter(t => t.trim())
  if (texts.length < 2) {
    ElMessage.warning('请至少输入两个版本的内容')
    return
  }

  comparing.value = true
  try {
    const metadataList = panels.value.map(p => p.metadata || {})
    const response = await collationAPI.compareMulti(null, texts, metadataList)
    result.value = response
    await nextTick()
    renderCharts()
  } catch (error) {
    console.error('校勘失败:', error)
    ElMessage.error('校勘失败：' + (error.message || '未知错误'))
  } finally {
    comparing.value = false
  }
}

// 保存版本
async function saveCurrentVersion(panelIndex) {
  const panel = panels.value[panelIndex]
  if (!panel.text.trim()) {
    ElMessage.warning('请先输入版本内容')
    return
  }

  const name = prompt('请输入版本名称（如：康熙志、咸丰志）', `版本 ${String.fromCharCode(65 + panelIndex)}`)
  if (!name) return

  try {
    const file = new File([panel.text], `${name}.txt`, { type: 'text/plain' })
    const response = await collationAPI.uploadVersion(file, name, panel.metadata || {})
    ElMessage.success(`版本 "${name}" 已保存`)
    await loadSavedVersions()
    panels.value[panelIndex].selectedVersionId = response.id
  } catch (error) {
    console.error('保存版本失败:', error)
    ElMessage.error('保存失败')
  }
}

// 渲染图表
function renderCharts() {
  if (!result.value?.diffs) return

  // 差异类型饼图
  const typeCount = {}
  result.value.diffs.forEach(d => {
    typeCount[d.type] = (typeCount[d.type] || 0) + 1
  })

  if (pieChartRef.value) {
    if (!pieChart) pieChart = echarts.init(pieChartRef.value)
    pieChart.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        avoidLabelOverlap: false,
        itemStyle: { borderRadius: 6, borderColor: '#faf8f3', borderWidth: 2 },
        label: { show: true, formatter: '{b}\n{d}%', color: '#1a1a1a', fontSize: 12, fontFamily: 'Noto Serif SC' },
        emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
        data: Object.entries(typeCount).map(([type, count]) => ({
          name: getTypeLabel(type),
          value: count,
          itemStyle: { color: DIFF_TYPES[type]?.color || '#9ca3af' }
        }))
      }]
    })
  }

  // 版本字符数对比图
  if (barChartRef.value) {
    const charCounts = panels.value.map(p => countChars(p.text))
    const versionLabels = panels.value.map((_, i) => `版本 ${String.fromCharCode(65 + i)}`)

    if (!barChart) barChart = echarts.init(barChartRef.value)
    barChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
      xAxis: { type: 'category', data: versionLabels, axisLabel: { color: '#4a4a4a', fontFamily: 'Noto Serif SC' } },
      yAxis: { type: 'value', axisLabel: { color: '#4a4a4a', fontFamily: 'JetBrains Mono' } },
      series: [{
        type: 'bar',
        data: charCounts,
        itemStyle: { color: '#b54a32', borderRadius: [4, 4, 0, 0] },
        barWidth: '50%'
      }]
    })
  }
}

// 导出结果
function exportResult() {
  if (!result.value) return
  const data = JSON.stringify(result.value, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `校勘结果_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success('结果已导出')
}

// 重置
function resetAll() {
  panels.value.forEach(p => {
    p.text = ''
    p.selectedVersionId = ''
    p.metadata = {}
  })
  result.value = null
  searchText.value = ''
  filterType.value = ''
  if (pieChart) { pieChart.dispose(); pieChart = null }
  if (barChart) { barChart.dispose(); barChart = null }
}

// 计算属性
const filteredDiffs = computed(() => {
  if (!result.value?.diffs) return []
  let diffs = result.value.diffs
  if (filterType.value) {
    diffs = diffs.filter(d => d.type === filterType.value)
  }
  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    diffs = diffs.filter(d =>
      (d.text_a || '').toLowerCase().includes(search) ||
      (d.text_b || '').toLowerCase().includes(search)
    )
  }
  return diffs
})

// 监听版本数量变化
watch(versionCount, (newCount) => {
  setVersionCount(newCount)
})

// 生命周期
onMounted(() => {
  initPanels(versionCount.value)
  loadSavedVersions()
  window.addEventListener('resize', () => {
    if (pieChart) pieChart.resize()
    if (barChart) barChart.resize()
  })
})
</script>

<style scoped>
/* ==================== 古籍书房色板 ==================== */
.collation-view {
  min-height: calc(100vh - 60px);
  background: var(--bg-primary);
  font-family: 'Noto Serif SC', serif;
}

/* ==================== 顶部栏 ==================== */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 32px;
  background: var(--bg-card);
  border-bottom: 1px solid #d4cfc4;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 16px;
}

.page-title {
  font-family: 'ZCOOL XiaoWei', 'Noto Serif SC', serif;
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: 0.05em;
}

.page-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
  font-family: 'Noto Serif SC', serif;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.version-count-switch {
  display: flex;
  align-items: center;
  gap: 8px;
}

.switch-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.diff-badge {
  font-size: 13px;
  color: var(--accent);
  padding: 5px 14px;
  background: rgba(181, 74, 50, 0.08);
  border: 1px solid rgba(181, 74, 50, 0.2);
  border-radius: 4px;
  font-weight: 500;
  font-family: 'JetBrains Mono', monospace;
}

/* ==================== 主内容 ==================== */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 28px 32px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* ==================== 版本管理栏 ==================== */
.version-manager-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  background: var(--bg-card);
  border: 1px solid #ddd6c6;
  border-radius: 6px;
  border-left: 3px solid var(--secondary);
}

.bar-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-right: 12px;
}

.saved-versions {
  display: flex;
  align-items: center;
  flex: 1;
}

.version-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.version-chip {
  font-family: 'Noto Serif SC', serif;
}

.no-versions {
  font-size: 13px;
  color: #b8b0a0;
  font-style: italic;
}

/* ==================== 对比区域 ==================== */
.compare-section {
  display: grid;
  gap: 20px;
  align-items: stretch;
}

.compare-section.versions-2 { grid-template-columns: repeat(2, 1fr); }
.compare-section.versions-3 { grid-template-columns: repeat(3, 1fr); }
.compare-section.versions-4 { grid-template-columns: repeat(4, 1fr); }

.text-panel {
  background: var(--bg-card);
  border: 1px solid #ddd6c6;
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  border-left: 3px solid transparent;
}

.text-panel:hover {
  border-left-color: var(--accent);
  box-shadow: 0 2px 12px rgba(26, 26, 26, 0.06);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--bg-secondary);
  border-bottom: 1px solid #ddd6c6;
}

.version-marker {
  display: flex;
  align-items: center;
  gap: 8px;
}

.marker-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: 'ZCOOL XiaoWei', 'Noto Serif SC', serif;
}

.version-select {
  width: 120px;
}

.panel-body {
  flex: 1;
  padding: 16px;
  min-height: 200px;
}

.text-input :deep(.el-textarea__inner) {
  font-family: 'Noto Serif SC', serif;
  font-size: 14px;
  line-height: 1.9;
  border: 1px solid #ddd6c6;
  border-radius: 4px;
  resize: none;
  background: var(--bg-card);
  color: var(--text-primary);
}

.text-input :deep(.el-textarea__inner:focus) {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(181, 74, 50, 0.1);
}

.panel-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  border-top: 1px solid #ddd6c6;
  background: var(--bg-secondary);
}

.upload-actions {
  display: flex;
  gap: 8px;
}

.upload-btn {
  font-family: 'Noto Serif SC', serif;
  color: var(--text-secondary);
  border-color: #ccc5b5;
  background: var(--bg-card);
}

.upload-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
  background: rgba(181, 74, 50, 0.04);
}

.text-stats {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  font-family: 'JetBrains Mono', monospace;
}

.stat-sep {
  color: #b8b0a0;
}

/* ==================== 操作栏 ==================== */
.action-bar {
  display: flex;
  justify-content: center;
  gap: 14px;
  padding: 18px;
  background: var(--bg-card);
  border: 1px solid #ddd6c6;
  border-radius: 6px;
  border-left: 3px solid var(--secondary);
}

.btn-compare {
  font-family: 'ZCOOL XiaoWei', 'Noto Serif SC', serif;
  background: var(--accent) !important;
  border-color: var(--accent) !important;
  letter-spacing: 0.1em;
}

.btn-compare:hover {
  background: #a03f28 !important;
  border-color: #a03f28 !important;
}

.btn-reset {
  font-family: 'Noto Serif SC', serif;
  color: var(--text-secondary);
  border-color: #ccc5b5;
  background: var(--bg-card);
}

.btn-reset:hover {
  color: var(--text-primary);
  border-color: #b8b0a0;
  background: var(--bg-secondary);
}

.btn-export {
  font-family: 'Noto Serif SC', serif;
  color: var(--secondary);
  border-color: var(--secondary);
  background: rgba(107, 143, 138, 0.06);
}

.btn-export:hover {
  background: rgba(107, 143, 138, 0.12);
  border-color: var(--secondary);
  color: var(--secondary);
}

/* ==================== 结果区域 ==================== */
.results-section {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 对齐矩阵 */
.matrix-card {
  background: var(--bg-card);
  border: 1px solid #ddd6c6;
  border-radius: 6px;
  padding: 20px;
  border-left: 3px solid var(--secondary);
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px;
  font-family: 'ZCOOL XiaoWei', 'Noto Serif SC', serif;
}

.matrix-table {
  overflow-x: auto;
}

.matrix-table table {
  width: 100%;
  border-collapse: collapse;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
}

.matrix-table th,
.matrix-table td {
  padding: 10px 16px;
  text-align: center;
  border: 1px solid #ddd6c6;
}

.matrix-table th {
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-weight: 600;
}

.matrix-table td {
  color: var(--text-primary);
}

.matrix-table td.diag {
  background: rgba(181, 74, 50, 0.08);
  color: var(--accent);
  font-weight: 600;
}

/* 分数卡片 */
.score-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 16px;
}

.score-card {
  background: var(--bg-card);
  border: 1px solid #ddd6c6;
  border-radius: 6px;
  padding: 20px;
  text-align: center;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  border-left: 3px solid transparent;
}

.score-card:hover {
  border-left-color: var(--secondary);
  box-shadow: 0 2px 12px rgba(26, 26, 26, 0.05);
}

.score-card:first-child {
  border-left-color: var(--accent);
}

.score-value {
  font-family: 'JetBrains Mono', monospace;
  font-size: 28px;
  font-weight: 700;
  color: var(--accent);
  line-height: 1;
}

.score-card:first-child .score-value { color: var(--accent); }

.score-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 8px;
  font-family: 'Noto Serif SC', serif;
}

/* 图表 */
.charts-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.chart-card {
  background: var(--bg-card);
  border: 1px solid #ddd6c6;
  border-radius: 6px;
  padding: 20px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  border-left: 3px solid transparent;
}

.chart-card:hover {
  border-left-color: var(--secondary);
  box-shadow: 0 2px 12px rgba(26, 26, 26, 0.05);
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px;
  font-family: 'ZCOOL XiaoWei', 'Noto Serif SC', serif;
}

.chart-container {
  height: 200px;
}

/* 差异列表 */
.diff-section {
  background: var(--bg-card);
  border: 1px solid #ddd6c6;
  border-radius: 6px;
  padding: 20px;
  border-left: 3px solid var(--accent);
}

.diff-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.diff-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  font-family: 'ZCOOL XiaoWei', 'Noto Serif SC', serif;
}

.diff-actions {
  display: flex;
  gap: 10px;
}

.search-input {
  width: 160px;
}

.search-input :deep(.el-input__wrapper) {
  background: var(--bg-card);
  border-color: #ddd6c6;
  box-shadow: none;
}

.search-input :deep(.el-input__wrapper:hover),
.search-input :deep(.el-input__wrapper.is-focus) {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(181, 74, 50, 0.08);
}

.type-filter :deep(.el-select__wrapper) {
  background: var(--bg-card);
  border-color: #ddd6c6;
  box-shadow: none;
}

.type-filter :deep(.el-select__wrapper:hover),
.type-filter :deep(.el-select__wrapper.is-focus) {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(181, 74, 50, 0.08);
}

.diff-text {
  font-family: 'Noto Serif SC', serif;
  color: var(--text-primary);
}

.text-del {
  text-decoration: line-through;
  color: var(--accent);
  background: rgba(181, 74, 50, 0.06);
  padding: 1px 4px;
  border-radius: 2px;
}

.text-ins {
  color: var(--secondary);
  background: rgba(107, 143, 138, 0.06);
  padding: 1px 4px;
  border-radius: 2px;
}

.compare-label {
  font-size: 12px;
  color: var(--secondary);
  font-family: 'JetBrains Mono', monospace;
}

/* Element Plus Table Override */
.diff-table :deep(.el-table) {
  background: var(--bg-card);
  border-color: #ddd6c6;
  font-family: 'Noto Serif SC', serif;
}

.diff-table :deep(.el-table__header-wrapper th) {
  background: var(--bg-secondary) !important;
  color: var(--text-primary);
  font-weight: 600;
  border-color: #ddd6c6;
}

.diff-table :deep(.el-table__body-wrapper tr) {
  background: var(--bg-card);
}

.diff-table :deep(.el-table__body-wrapper td) {
  border-color: #ebe7de;
}

.diff-table :deep(.el-table__row:hover > td) {
  background: rgba(181, 74, 50, 0.03) !important;
}

/* ==================== 响应式 ==================== */
@media (max-width: 1200px) {
  .compare-section.versions-4 {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 900px) {
  .compare-section.versions-3,
  .compare-section.versions-2 {
    grid-template-columns: 1fr;
  }

  .charts-row {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }
}
</style>
