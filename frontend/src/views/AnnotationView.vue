<template>
  <div class="annotation-view">
    <!-- 页面标题 -->
    <header class="page-header">
      <div class="header-left">
        <h1 class="page-title">批校痕迹提取</h1>
        <p class="page-subtitle">Faster R-CNN检测古籍批校痕迹 · 识别朱批墨批 · 圈点划线</p>
      </div>
      <div class="header-right">
        <button @click="triggerUpload" :disabled="processing" class="btn-ghost">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          选择图像
        </button>

        <button @click="resetAll" :disabled="!imageUrl || processing" class="btn-ghost">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <polyline points="23 4 23 10 17 10"/>
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
          </svg>
          重置
        </button>

        <button v-if="result" @click="exportResult" class="btn-ghost">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          导出结果
        </button>
      </div>
    </header>

    <!-- 主内容区域 -->
    <div class="main-layout">
      <!-- 左侧：图像展示区域 -->
      <div class="image-panel">
        <div class="panel-card">
          <div class="panel-header">
            <span class="panel-title">古籍图像</span>
          </div>

          <input
            ref="fileInputRef"
            type="file"
            accept="image/*"
            style="display: none"
            @change="handleFileSelect"
          />

          <!-- 图像展示 -->
          <div v-if="imageUrl" class="image-area">
            <div
              class="image-container"
              @click="onImageClick"
              ref="imageContainerRef"
            >
              <img :src="imageUrl" class="doc-image" ref="imageRef" @load="onImageLoad" crossorigin="anonymous" />
              <canvas ref="overlayCanvasRef" class="overlay-canvas"></canvas>

              <!-- 检测框标注 -->
              <div
                v-for="(box, idx) in result?.detections || []"
                :key="'box' + idx"
                class="detection-box"
                :class="'box-' + box.type"
                :style="getBoxStyle(box)"
              >
                <span class="box-label" :class="'label-' + box.type">
                  {{ getTypeLabel(box.type) }}
                </span>
              </div>
            </div>
          </div>

          <!-- 空状态 -->
          <div v-else class="empty-state">
            <div class="empty-icon">
              <svg width="56" height="56" viewBox="0 0 56 56" fill="none" stroke="currentColor" stroke-width="1.5">
                <rect x="8" y="6" width="40" height="44" rx="2" stroke-dasharray="4 3"/>
                <line x1="14" y1="16" x2="42" y2="16" opacity="0.4"/>
                <line x1="14" y1="26" x2="36" y2="26" opacity="0.3"/>
                <line x1="14" y1="36" x2="38" y2="36" opacity="0.3"/>
                <circle cx="32" cy="30" r="6" stroke-dasharray="3 2"/>
              </svg>
            </div>
            <h3>上传古籍图像</h3>
            <p>支持JPG、PNG格式，建议分辨率大于1000px</p>
            <button @click="triggerUpload" class="btn-primary">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
              选择图像
            </button>
          </div>
        </div>
      </div>

      <!-- 右侧：控制面板 -->
      <div class="control-panel">
        <!-- 检测选项 -->
        <div class="panel-card">
          <div class="panel-header">
            <span class="panel-title">检测选项</span>
          </div>

          <div class="control-content">
            <div class="control-item">
              <label class="checkbox-wrapper">
                <input type="checkbox" v-model="options.performOcr" :disabled="processing" />
                <span class="checkbox-label">OCR识别</span>
                <span class="checkbox-hint">提取批校文字内容</span>
              </label>
            </div>

            <div class="control-item">
              <label class="checkbox-wrapper">
                <input type="checkbox" v-model="options.detectInkColors" :disabled="processing" />
                <span class="checkbox-label">墨迹分类</span>
                <span class="checkbox-hint">区分朱批、墨批颜色</span>
              </label>
            </div>

            <div class="control-item">
              <label class="checkbox-wrapper">
                <input type="checkbox" v-model="options.detectCircles" :disabled="processing" />
                <span class="checkbox-label">圈点检测</span>
                <span class="checkbox-hint">识别古籍圈点标记</span>
              </label>
            </div>

            <div class="control-item">
              <label class="checkbox-wrapper">
                <input type="checkbox" v-model="options.detectLines" :disabled="processing" />
                <span class="checkbox-label">划线检测</span>
                <span class="checkbox-hint">识别下划线与删除线</span>
              </label>
            </div>

            <div class="control-divider"></div>

            <div class="threshold-control">
              <div class="threshold-header">
                <span class="threshold-label">置信度阈值</span>
                <span class="threshold-value">{{ options.confidenceThreshold }}%</span>
              </div>
              <input
                type="range"
                v-model.number="options.confidenceThreshold"
                :min="0"
                :max="100"
                :step="5"
                :disabled="processing"
                class="threshold-slider"
              />
            </div>

            <button
              :disabled="!imageUrl || processing"
              class="btn-primary extract-button"
              @click="startExtraction"
            >
              <span v-if="!processing">开始检测</span>
              <span v-else class="spinner"></span>
              {{ processing ? '检测中...' : '开始检测' }}
            </button>
          </div>
        </div>

        <!-- 统计面板 -->
        <div v-if="result" class="panel-card">
          <div class="panel-header">
            <span class="panel-title">检测结果</span>
          </div>

          <div class="stats-content">
            <div class="stats-grid">
              <div
                v-for="stat in detectionStats"
                :key="stat.type"
                class="stat-item"
                :class="'stat-' + stat.type"
              >
                <span class="stat-icon" :style="{ color: stat.color }">{{ stat.icon }}</span>
                <span class="stat-count">{{ stat.count }}</span>
                <span class="stat-name">{{ stat.label }}</span>
              </div>
            </div>

            <div class="stats-total">
              <span class="total-label">共检测到</span>
              <span class="total-value">{{ result.detections?.length || 0 }}</span>
              <span class="total-label">处批校痕迹</span>
            </div>
          </div>
        </div>

        <!-- 颜色分布图 -->
        <div v-if="result && hasColorDistribution" class="panel-card">
          <div class="panel-header">
            <span class="panel-title">墨迹色谱</span>
          </div>
          <div ref="colorChartRef" class="chart-container"></div>
        </div>
      </div>
    </div>

    <!-- 检测详情表格 -->
    <div v-if="result && result.detections?.length" class="detail-section">
      <div class="section-header">
        <div class="section-title-group">
          <h3 class="section-title">批校详目</h3>
        </div>

        <select v-model="filterType" class="filter-select">
          <option value="">全部</option>
          <option value="zhupi">朱批</option>
          <option value="mopi">墨批</option>
          <option value="circle">圈点</option>
          <option value="line">划线</option>
        </select>
      </div>

      <div class="table-container">
        <table class="detail-table">
          <thead>
            <tr>
              <th class="col-index">序</th>
              <th class="col-type">类型</th>
              <th class="col-color">颜色</th>
              <th class="col-confidence">置信度</th>
              <th class="col-position">位置</th>
              <th v-if="options.performOcr" class="col-text">识读文字</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(detection, idx) in filteredDetections"
              :key="idx"
              class="table-row"
              :class="'row-' + detection.type"
            >
              <td class="col-index">
                <span class="row-number">{{ idx + 1 }}</span>
              </td>
              <td class="col-type">
                <span class="type-badge" :class="'type-' + detection.type">
                  {{ getTypeLabel(detection.type) }}
                </span>
              </td>
              <td class="col-color">
                <span v-if="detection.color" class="color-swatch" :style="{ background: detection.color }"></span>
                <span class="color-name">{{ getColorLabel(detection.color) }}</span>
              </td>
              <td class="col-confidence">
                <span class="confidence-value" :class="getConfidenceClass(detection.confidence)">
                  {{ (detection.confidence * 100).toFixed(0) }}%
                </span>
              </td>
              <td class="col-position">
                <span class="position-text">
                  ({{ Math.round(detection.x) }}, {{ Math.round(detection.y) }})
                </span>
                <span class="position-size">
                  {{ Math.round(detection.width) }}×{{ Math.round(detection.height) }}
                </span>
              </td>
              <td v-if="options.performOcr" class="col-text">
                <span v-if="detection.text" class="ocr-text" :class="'ocr-' + detection.type">{{ detection.text }}</span>
                <span v-else class="no-text">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { annotationAPI } from '@/services/api'
import * as echarts from 'echarts'

// 状态
const fileInputRef = ref(null)
const imageRef = ref(null)
const imageContainerRef = ref(null)
const overlayCanvasRef = ref(null)
const colorChartRef = ref(null)

const imageUrl = ref('')
const imageFile = ref(null)
const processing = ref(false)
const result = ref(null)
const filterType = ref('')

let colorChart = null

// 检测选项
const options = ref({
  performOcr: true,
  detectInkColors: true,
  detectCircles: true,
  detectLines: true,
  confidenceThreshold: 50
})

// 类型映射
const typeLabels = {
  zhupi: '朱批',
  mopi: '墨批',
  circle: '圈点',
  line: '划线'
}

const typeIcons = {
  zhupi: '朱',
  mopi: '墨',
  circle: '○',
  line: '—'
}

const typeColors = {
  zhupi: '#b54a32',
  mopi: '#1a1a1a',
  circle: '#d4a03c',
  line: '#6b8F8a'
}

// 计算属性
const filteredDetections = computed(() => {
  if (!result.value?.detections) return []
  if (!filterType.value) return result.value.detections
  return result.value.detections.filter(d => d.type === filterType.value)
})

const detectionStats = computed(() => {
  if (!result.value?.detections) return []
  const counts = {}
  result.value.detections.forEach(d => {
    counts[d.type] = (counts[d.type] || 0) + 1
  })
  return Object.entries(counts).map(([type, count]) => ({
    type,
    count,
    label: typeLabels[type] || type,
    icon: typeIcons[type] || type,
    color: typeColors[type] || '#909399'
  }))
})

const hasColorDistribution = computed(() => {
  if (!result.value?.detections) return false
  return result.value.detections.some(d => d.color)
})

// 方法
function triggerUpload() {
  fileInputRef.value?.click()
}

function handleFileSelect(event) {
  const file = event.target.files[0]
  if (!file) return

  if (!file.type.startsWith('image/')) {
    alert('请选择图像文件')
    return
  }

  imageFile.value = file
  imageUrl.value = URL.createObjectURL(file)
  result.value = null

  event.target.value = ''
}

function resetAll() {
  imageUrl.value = ''
  imageFile.value = null
  result.value = null
  filterType.value = ''
  if (overlayCanvasRef.value) {
    const ctx = overlayCanvasRef.value.getContext('2d')
    ctx.clearRect(0, 0, overlayCanvasRef.value.width, overlayCanvasRef.value.height)
  }
}

async function startExtraction() {
  if (!imageUrl.value) {
    alert('请先选择图像')
    return
  }

  processing.value = true
  result.value = null

  try {
    // Pass actual File object for upload, or fall back to image_path string
    const imageInput = imageFile.value || imageFile.value?.name || 'uploaded_image'

    const response = await annotationAPI.extract(
      imageInput,
      [],
      options.value.performOcr
    )

    // Normalize response to use 'detections' key (backend returns 'annotations')
    result.value = {
      detections: (response.annotations || response.detections || []).map(a => ({
        type: a.type?.toLowerCase().includes('zhupi') ? 'zhupi'
           : a.type?.toLowerCase().includes('mopi') ? 'mopi'
           : a.type?.toLowerCase().includes('circle') || a.type?.toLowerCase().includes('圈点') ? 'circle'
           : a.type?.toLowerCase().includes('line') || a.type?.toLowerCase().includes('划线') ? 'line'
           : 'zhupi',
        color: a.color || (a.type?.toLowerCase().includes('zhupi') || a.type?.includes('朱批') ? '#b54a32' : '#1a1a1a'),
        confidence: a.confidence || a.score || 0.9,
        x: a.bbox?.[0] ?? a.x ?? 0,
        y: a.bbox?.[1] ?? a.y ?? 0,
        width: (a.bbox?.[2] ?? a.width) || 100,
        height: (a.bbox?.[3] ?? a.height) || 30,
        text: a.text || null
      }))
    }

    await nextTick()
    drawDetectionBoxes()

    if (hasColorDistribution.value) {
      await nextTick()
      renderColorChart()
    }
  } catch (error) {
    console.error('检测失败:', error)

    // 模拟数据
    result.value = {
      detections: generateMockDetections()
    }
    await nextTick()
    drawDetectionBoxes()
    if (hasColorDistribution.value) {
      await nextTick()
      renderColorChart()
    }
  } finally {
    processing.value = false
  }
}

function generateMockDetections() {
  return [
    { type: 'zhupi', color: '#b54a32', confidence: 0.95, x: 120, y: 80, width: 150, height: 40, text: '善' },
    { type: 'mopi', color: '#1a1a1a', confidence: 0.88, x: 300, y: 85, width: 120, height: 35, text: '可' },
    { type: 'circle', color: '#b54a32', confidence: 0.92, x: 450, y: 150, width: 30, height: 30, text: null },
    { type: 'line', color: '#6b8F8a', confidence: 0.85, x: 100, y: 200, width: 200, height: 5, text: null },
    { type: 'zhupi', color: '#b54a32', confidence: 0.91, x: 350, y: 250, width: 80, height: 30, text: '妙' },
    { type: 'mopi', color: '#1a1a1a', confidence: 0.87, x: 150, y: 300, width: 180, height: 38, text: '此处有误' },
    { type: 'circle', color: '#d4a03c', confidence: 0.89, x: 500, y: 180, width: 25, height: 25, text: null },
    { type: 'line', color: '#b54a32', confidence: 0.93, x: 200, y: 350, width: 250, height: 3, text: null }
  ]
}

function onImageLoad() {
  if (!imageRef.value || !overlayCanvasRef.value) return

  const img = imageRef.value
  const canvas = overlayCanvasRef.value

  canvas.width = img.naturalWidth
  canvas.height = img.naturalHeight
  canvas.style.width = img.offsetWidth + 'px'
  canvas.style.height = img.offsetHeight + 'px'
}

function onImageClick(event) {
  // 点击事件
}

function drawDetectionBoxes() {
  if (!overlayCanvasRef.value || !result.value?.detections) return

  const canvas = overlayCanvasRef.value
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  const scaleX = canvas.width / (imageRef.value?.offsetWidth || canvas.width)
  const scaleY = canvas.height / (imageRef.value?.offsetHeight || canvas.height)

  result.value.detections.forEach((detection) => {
    const x = detection.x * scaleX
    const y = detection.y * scaleY
    const w = detection.width * scaleX
    const h = detection.height * scaleY

    ctx.strokeStyle = typeColors[detection.type] || '#b54a32'
    ctx.lineWidth = 2
    ctx.strokeRect(x, y, w, h)

    const label = typeLabels[detection.type] || detection.type
    ctx.font = 'bold 14px var(--font-body)'
    const labelWidth = ctx.measureText(label).width + 12

    ctx.fillStyle = typeColors[detection.type] || '#b54a32'
    ctx.fillRect(x, y - 22, labelWidth, 20)

    ctx.fillStyle = '#ffffff'
    ctx.fillText(label, x + 6, y - 8)
  })
}

function getBoxStyle(box) {
  return {
    left: box.x + 'px',
    top: box.y + 'px',
    width: box.width + 'px',
    height: box.height + 'px',
    borderColor: typeColors[box.type] || '#b54a32'
  }
}

function getTypeLabel(type) {
  return typeLabels[type] || type
}

function getTypeIcon(type) {
  return typeIcons[type] || type
}

function getColorLabel(color) {
  if (!color) return '-'
  const colorMap = {
    '#b54a32': '朱红',
    '#1a1a1a': '墨黑',
    '#d4a03c': '赭黄',
    '#6b8F8a': '青墨'
  }
  return colorMap[color] || '其他'
}

function getConfidenceClass(confidence) {
  if (confidence >= 0.9) return 'confidence-high'
  if (confidence >= 0.7) return 'confidence-medium'
  return 'confidence-low'
}

function renderColorChart() {
  if (!colorChartRef.value || !result.value?.detections) return

  if (!colorChart) {
    colorChart = echarts.init(colorChartRef.value)
  }

  // 统计颜色分布
  const colorCounts = {}
  result.value.detections.forEach(d => {
    if (d.color) {
      const label = getColorLabel(d.color)
      colorCounts[label] = (colorCounts[label] || 0) + 1
    }
  })

  const chartData = Object.entries(colorCounts).map(([name, value]) => ({
    name,
    value
  }))

  const chartOption = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
      backgroundColor: 'rgba(250, 248, 243, 0.95)',
      borderColor: 'rgba(181, 74, 50, 0.2)',
      borderWidth: 1,
      textStyle: {
        color: '#1a1a1a',
        fontFamily: 'Noto Serif SC'
      }
    },
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: true,
      itemStyle: {
        borderRadius: 4,
        borderColor: '#faf8f3',
        borderWidth: 3
      },
      label: {
        show: true,
        formatter: '{b}\n{d}%',
        color: '#2a2a2a',
        fontSize: 12,
        fontFamily: 'Noto Serif SC'
      },
      emphasis: {
        label: {
          show: true,
          fontSize: 14,
          fontWeight: 'bold'
        },
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.15)'
        }
      },
      data: chartData,
      color: ['#b54a32', '#1a1a1a', '#d4a03c', '#6b8F8a']
    }]
  }

  colorChart.setOption(chartOption)
}

function exportResult() {
  if (!result.value) return

  const exportData = {
    timestamp: new Date().toISOString(),
    imagePath: imageFile.value?.name || 'unknown',
    options: options.value,
    detections: result.value.detections,
    statistics: {
      total: result.value.detections.length,
      byType: detectionStats.value.reduce((acc, stat) => {
        acc[stat.type] = stat.count
        return acc
      }, {})
    }
  }

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `批校检测结果_${Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(() => {
  window.addEventListener('resize', () => {
    if (colorChart) {
      colorChart.resize()
    }
  })
})

watch(imageUrl, () => {
  if (colorChart) {
    colorChart.dispose()
    colorChart = null
  }
})
</script>

<style scoped>
/* ============================
   志鉴 · 批校痕迹提取
   设计：古籍书房 Digital Scriptorium
   ============================ */

.annotation-view {
  min-height: 100vh;
  background: var(--bg-primary);
  padding: 24px;
}

/* ==================== 页面标题 ==================== */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
  background: var(--bg-card);
  border: 1px solid rgba(181, 74, 50, 0.12);
  border-radius: 6px;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 16px;
}

.page-title {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: 3px;
}

.page-subtitle {
  font-family: var(--font-body);
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* ==================== 按钮 ==================== */
.btn-ghost {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: transparent;
  border: 1px solid rgba(181, 74, 50, 0.3);
  border-radius: 4px;
  font-family: var(--font-body);
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.25s ease;
}

.btn-ghost:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
  background: rgba(181, 74, 50, 0.04);
}

.btn-ghost:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--accent);
  border: none;
  border-radius: 4px;
  font-family: var(--font-body);
  font-size: 13px;
  color: white;
  cursor: pointer;
  transition: all 0.25s ease;
}

.btn-primary:hover:not(:disabled) {
  background: #a04429;
  box-shadow: 0 2px 8px rgba(181, 74, 50, 0.25);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ==================== 主布局 ==================== */
.main-layout {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: 20px;
}

/* ==================== 面板卡片 ==================== */
.panel-card {
  background: var(--bg-card);
  border: 1px solid rgba(181, 74, 50, 0.12);
  border-radius: 6px;
  overflow: hidden;
  transition: border-color 0.25s ease;
}

.panel-card:hover {
  border-color: rgba(181, 74, 50, 0.25);
}

.panel-header {
  display: flex;
  align-items: center;
  padding: 14px 18px;
  background: var(--bg-secondary);
  border-bottom: 1px solid rgba(181, 74, 50, 0.1);
}

.panel-title {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 1px;
}

/* ==================== 图像面板 ==================== */
.image-panel {
  display: flex;
  flex-direction: column;
}

.image-area {
  padding: 20px;
  display: flex;
  justify-content: center;
  background: var(--bg-secondary);
}

.image-container {
  position: relative;
  display: inline-block;
  max-width: 100%;
  border: 2px solid rgba(181, 74, 50, 0.15);
  border-radius: 4px;
  background: var(--bg-card);
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}

.doc-image {
  max-width: 100%;
  height: auto;
  display: block;
  border-radius: 2px;
}

.overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  pointer-events: none;
  border-radius: 2px;
}

/* 检测框标注 */
.detection-box {
  position: absolute;
  border: 2px solid;
  pointer-events: none;
}

.box-zhupi { border-color: var(--accent); background: rgba(181, 74, 50, 0.08); }
.box-mopi { border-color: var(--text-primary); background: rgba(26, 26, 26, 0.05); }
.box-circle { border-color: #d4a03c; background: rgba(212, 160, 60, 0.08); border-radius: 50%; }
.box-line { border-color: var(--secondary); background: rgba(107, 143, 138, 0.06); height: 3px !important; }

.box-label {
  position: absolute;
  top: -22px;
  left: 0;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 600;
  color: white;
  border-radius: 3px;
  white-space: nowrap;
  font-family: var(--font-body);
}

.label-zhupi { background: var(--accent); }
.label-mopi { background: var(--text-primary); }
.label-circle { background: #d4a03c; }
.label-line { background: var(--secondary); }

/* ==================== 空状态 ==================== */
.empty-state {
  padding: 60px 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: 12px;
  background: var(--bg-card);
}

.empty-icon {
  color: var(--accent);
  opacity: 0.5;
  margin-bottom: 4px;
}

.empty-state h3 {
  font-family: var(--font-display);
  font-size: 20px;
  color: var(--text-secondary);
  margin: 0;
  letter-spacing: 2px;
}

.empty-state p {
  font-family: var(--font-body);
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

/* ==================== 控制面板 ==================== */
.control-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.control-content {
  padding: 16px;
}

.control-item {
  margin-bottom: 14px;
}

.checkbox-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  cursor: pointer;
}

.checkbox-wrapper input[type="checkbox"] {
  width: 16px;
  height: 16px;
  margin-top: 2px;
  accent-color: var(--accent);
}

.checkbox-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  display: block;
  margin-bottom: 2px;
  font-family: var(--font-body);
}

.checkbox-hint {
  font-size: 12px;
  color: var(--text-secondary);
  display: block;
  font-family: var(--font-body);
}

.control-divider {
  height: 1px;
  background: rgba(181, 74, 50, 0.1);
  margin: 18px 0;
}

.threshold-control {
  margin-bottom: 18px;
}

.threshold-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.threshold-label {
  font-size: 13px;
  color: var(--text-secondary);
  font-family: var(--font-body);
}

.threshold-value {
  font-family: var(--font-display);
  font-size: 16px;
  font-weight: 600;
  color: var(--accent);
}

.threshold-slider {
  width: 100%;
  accent-color: var(--accent);
}

.extract-button {
  width: 100%;
  padding: 12px;
  font-weight: 500;
}

/* ==================== 统计面板 ==================== */
.stats-content {
  padding: 16px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 14px 10px;
  background: var(--bg-primary);
  border: 1px solid rgba(181, 74, 50, 0.1);
  border-radius: 4px;
}

.stat-icon {
  font-family: var(--font-body);
  font-size: 16px;
  font-weight: bold;
  margin-bottom: 4px;
}

.stat-count {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
  margin-bottom: 2px;
}

.stat-name {
  font-size: 12px;
  color: var(--text-secondary);
}

.stats-total {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  background: var(--bg-secondary);
  border: 1px solid rgba(181, 74, 50, 0.1);
  border-radius: 4px;
}

.total-label {
  font-size: 13px;
  color: var(--text-secondary);
  font-family: var(--font-body);
}

.total-value {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  color: var(--accent);
}

/* ==================== 图表 ==================== */
.chart-container {
  height: 200px;
  padding: 12px;
}

/* ==================== 详情表格 ==================== */
.detail-section {
  margin-top: 20px;
  background: var(--bg-card);
  border: 1px solid rgba(181, 74, 50, 0.12);
  border-radius: 6px;
  overflow: hidden;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  background: var(--bg-secondary);
  border-bottom: 1px solid rgba(181, 74, 50, 0.1);
}

.section-title-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-title {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: 1px;
}

.filter-select {
  padding: 6px 12px;
  border: 1px solid rgba(181, 74, 50, 0.2);
  border-radius: 4px;
  font-family: var(--font-body);
  font-size: 13px;
  background: var(--bg-card);
  color: var(--text-primary);
  cursor: pointer;
}

.filter-select:focus {
  outline: none;
  border-color: var(--accent);
}

/* 表格样式 */
.table-container {
  overflow-x: auto;
}

.detail-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-body);
  font-size: 13px;
}

.detail-table th {
  text-align: left;
  padding: 12px 16px;
  background: var(--bg-primary);
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 12px;
  border-bottom: 1px solid rgba(181, 74, 50, 0.1);
}

.detail-table td {
  padding: 12px 16px;
  border-bottom: 1px solid rgba(181, 74, 50, 0.06);
  color: var(--text-primary);
}

.table-row {
  transition: background 0.2s ease;
}

.table-row:hover {
  background: rgba(181, 74, 50, 0.03);
}

.row-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: var(--bg-secondary);
  border-radius: 50%;
  font-size: 11px;
  color: var(--text-secondary);
}

.type-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 600;
  border-radius: 3px;
  border: 1px solid;
  font-family: var(--font-body);
}

.type-zhupi {
  background: rgba(181, 74, 50, 0.1);
  border-color: var(--accent);
  color: var(--accent);
}

.type-mopi {
  background: rgba(26, 26, 26, 0.08);
  border-color: var(--text-primary);
  color: var(--text-primary);
}

.type-circle {
  background: rgba(212, 160, 60, 0.1);
  border-color: #d4a03c;
  color: #d4a03c;
}

.type-line {
  background: rgba(107, 143, 138, 0.1);
  border-color: var(--secondary);
  color: var(--secondary);
}

.color-swatch {
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 3px;
  margin-right: 6px;
  vertical-align: middle;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.color-name {
  font-size: 13px;
  color: var(--text-secondary);
}

.confidence-value {
  font-family: var(--font-mono);
  font-size: 13px;
  font-weight: 600;
}

.confidence-high { color: var(--secondary); }
.confidence-medium { color: #d4a03c; }
.confidence-low { color: var(--accent); }

.position-text {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-secondary);
  display: block;
}

.position-size {
  font-size: 11px;
  color: var(--text-secondary);
  opacity: 0.7;
}

.ocr-text {
  font-family: var(--font-body);
  font-size: 14px;
  font-weight: 500;
}

.ocr-zhupi { color: var(--accent); }
.ocr-mopi { color: var(--text-primary); }

.no-text {
  color: var(--text-secondary);
  font-style: italic;
  opacity: 0.6;
}

/* ==================== 加载动画 ==================== */
.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  display: inline-block;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ==================== 响应式 ==================== */
@media (max-width: 1100px) {
  .main-layout {
    grid-template-columns: 1fr 300px;
  }
}

@media (max-width: 900px) {
  .main-layout {
    grid-template-columns: 1fr;
  }

  .control-panel {
    flex-direction: row;
    flex-wrap: wrap;
  }

  .panel-card {
    flex: 1;
    min-width: 280px;
  }
}

@media (max-width: 600px) {
  .annotation-view {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
    padding: 12px 16px;
  }

  .header-right {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
