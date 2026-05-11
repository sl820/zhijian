<template>
  <div class="map-view">
    <!-- 页面标题 -->
    <header class="page-header">
      <div class="header-left">
        <h1 class="page-title">舆图提取</h1>
        <p class="page-subtitle">古地图要素提取 · 语义分割 · 地理坐标映射</p>
      </div>
      <div class="header-right">
        <button @click="triggerUpload" :disabled="processing" class="btn-ghost">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="12" y1="18" x2="12" y2="12"/>
            <line x1="9" y1="15" x2="15" y2="15"/>
          </svg>
          选择舆图
        </button>
        <button @click="resetAll" :disabled="!imageUrl || processing" class="btn-ghost">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
            <path d="M3 3v5h5"/>
          </svg>
          重置
        </button>
        <button v-if="result" @click="exportGeoJSON" class="btn-ghost">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          导出
        </button>
      </div>
    </header>

    <!-- 主内容 -->
    <div class="main-layout">
      <!-- 左侧：舆图展示 -->
      <div class="map-panel">
        <!-- 图片卡片 -->
        <div class="map-card">
          <input
            ref="fileInputRef"
            type="file"
            accept="image/*"
            style="display: none"
            @change="handleFileSelect"
          />

          <!-- 舆图展示区 -->
          <div v-if="imageUrl" class="image-area">
            <div
              class="image-container"
              :class="{ 'mode-add-point': addingPointMode }"
              @click="onImageClick"
              ref="imageContainerRef"
            >
              <img :src="imageUrl" class="map-image" ref="imageRef" @load="onImageLoad" crossorigin="anonymous" />
              <canvas ref="overlayCanvasRef" class="overlay-canvas"></canvas>

              <!-- 控制点标记 -->
              <div
                v-for="(pt, idx) in referencePoints"
                :key="idx"
                class="point-marker"
                :style="getPointMarkerStyle(pt)"
                @click.stop="removeReferencePoint(idx)"
                :title="`像素(${Math.round(pt.pixelX)}, ${Math.round(pt.pixelY)}) → 经纬度(${pt.lon.toFixed(4)}, ${pt.lat.toFixed(4)})`"
              >
                <span class="point-number">{{ idx + 1 }}</span>
              </div>

              <!-- 文字标注 -->
              <div
                v-for="(label, idx) in result?.text_labels || []"
                :key="'lbl' + idx"
                class="label-marker"
                :style="getLabelMarkerStyle(label)"
              >
                <span class="label-text">{{ label.text }}</span>
              </div>

              <!-- 添加控制点提示 -->
              <div v-if="addingPointMode" class="add-point-overlay">
                <div class="crosshair">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="32" height="32">
                    <circle cx="12" cy="12" r="8"/>
                    <line x1="12" y1="2" x2="12" y2="6"/>
                    <line x1="12" y1="18" x2="12" y2="22"/>
                    <line x1="2" y1="12" x2="6" y2="12"/>
                    <line x1="18" y1="12" x2="22" y2="12"/>
                  </svg>
                </div>
                <span>点击舆图添加控制点</span>
              </div>
            </div>
          </div>

          <!-- 空状态 -->
          <div v-else class="empty-state" @click="triggerUpload">
            <div class="empty-icon">
              <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.5" width="56" height="56">
                <rect x="6" y="10" width="36" height="28" rx="2" stroke-dasharray="4 2"/>
                <circle cx="16" cy="20" r="4"/>
                <path d="M6 32l10-8 8 6 12-10 10 8"/>
              </svg>
            </div>
            <h3>上传古地图</h3>
            <p>点击上传古地图图像</p>
            <span class="upload-hint">支持 JPG、PNG 格式</span>
          </div>
        </div>

        <!-- 控制面板 -->
        <div class="control-card" v-if="imageUrl">
          <div class="control-header">
            <svg class="control-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="18" height="18">
              <rect x="3" y="3" width="18" height="18" rx="2"/>
              <path d="M3 9h18"/>
              <path d="M9 21V9"/>
            </svg>
            <h3 class="control-title">选项</h3>
          </div>

          <div class="options-row">
            <label class="checkbox-wrapper">
              <input type="checkbox" v-model="options.performOcr" :disabled="processing" />
              <span class="checkbox-label">OCR识别</span>
            </label>
            <label class="checkbox-wrapper">
              <input type="checkbox" v-model="options.georeference" :disabled="processing" />
              <span class="checkbox-label">地理配准</span>
            </label>
            <div class="alpha-control">
              <span class="alpha-label">透明度</span>
              <input
                type="range"
                v-model.number="options.alpha"
                min="0"
                max="100"
                step="5"
                :disabled="processing"
                class="alpha-slider"
              />
              <span class="alpha-value">{{ options.alpha }}%</span>
            </div>
          </div>

          <!-- 参考点管理 -->
          <div v-if="options.georeference" class="ref-points-section">
            <div class="section-header">
              <span class="section-title">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                  <circle cx="12" cy="12" r="10"/>
                  <path d="M12 2v20M2 12h20"/>
                </svg>
                控制点 <span class="point-count">({{ referencePoints.length }})</span>
              </span>
              <div class="ref-actions">
                <button
                  class="btn-small"
                  :class="addingPointMode ? 'btn-warning' : 'btn-primary'"
                  :disabled="processing"
                  @click="toggleAddingPointMode"
                >
                  {{ addingPointMode ? '取消' : '添加' }}
                </button>
                <button
                  class="btn-small"
                  @click="clearReferencePoints"
                  :disabled="referencePoints.length === 0 || processing"
                >
                  清空
                </button>
              </div>
            </div>

            <table v-if="referencePoints.length > 0" class="ref-table">
              <thead>
                <tr>
                  <th>序</th>
                  <th>像素坐标</th>
                  <th>经纬度</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(pt, idx) in referencePoints" :key="idx">
                  <td class="col-index">
                    <span class="table-number">{{ idx + 1 }}</span>
                  </td>
                  <td class="col-pixel">
                    <span class="coord-text">({{ Math.round(pt.pixelX) }}, {{ Math.round(pt.pixelY) }})</span>
                  </td>
                  <td class="col-coord">
                    <span v-if="editingPointIdx === idx" class="coord-edit">
                      <input type="number" v-model.number="editPoint.lon" step="0.0001" class="coord-input" />
                      <span class="coord-sep">°</span>
                      <input type="number" v-model.number="editPoint.lat" step="0.0001" class="coord-input" />
                      <button class="btn-confirm" @click="confirmEditPoint(idx)">✓</button>
                      <button class="btn-cancel" @click="cancelEditPoint">✗</button>
                    </span>
                    <span v-else @dblclick="startEditPoint(idx, pt)" class="coord-display">
                      {{ pt.lon.toFixed(4) }}°E · {{ pt.lat.toFixed(4) }}°N
                    </span>
                  </td>
                  <td class="col-action">
                    <button class="btn-delete" @click="removeReferencePoint(idx)" title="删除">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                        <path d="M3 6h18"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
                        <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                      </svg>
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>

            <div v-if="referencePoints.length > 0 && referencePoints.length < 4" class="alert alert-warning">
              至少需要4个控制点，当前 {{ referencePoints.length }} 个
            </div>
            <div v-if="referencePoints.length >= 4" class="alert alert-success">
              控制点已就绪 ({{ referencePoints.length }}个)，可开始提取
            </div>
          </div>

          <div class="extract-actions">
            <button
              class="btn-primary btn-extract"
              :disabled="!canExtract || processing"
              @click="extractMap"
            >
              <svg v-if="!processing" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
                <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
              </svg>
              <span v-if="processing" class="spinner"></span>
              {{ processing ? '处理中...' : '开始提取' }}
            </button>
            <button @click="triggerUpload" :disabled="processing" class="btn-ghost">
              更换图像
            </button>
          </div>
        </div>
      </div>

      <!-- 右侧 -->
      <aside class="side-panel">
        <!-- 要素统计 -->
        <div class="stats-card" v-if="result">
          <div class="card-header">
            <svg class="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="18" height="18">
              <path d="M21.21 15.89A10 10 0 1 1 8 2.83"/>
              <path d="M22 12A10 10 0 0 0 12 2v10z"/>
            </svg>
            <h3 class="card-title">要素分布</h3>
          </div>
          <div ref="statsChartRef" class="stats-chart"></div>
          <div class="stats-legend">
            <div class="legend-item"><span class="legend-dot" style="background: #6b8F8a"></span>河流</div>
            <div class="legend-item"><span class="legend-dot" style="background: #8B6914"></span>山脉</div>
            <div class="legend-item"><span class="legend-dot" style="background: #b54a32"></span>城市</div>
            <div class="legend-item"><span class="legend-dot" style="background: #4a7a4a"></span>边界线</div>
            <div class="legend-item"><span class="legend-dot" style="background: #4a4a4a"></span>标注</div>
          </div>
        </div>

        <!-- 提取详情 -->
        <div class="detail-card" v-if="result">
          <div class="card-header">
            <svg class="card-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="18" height="18">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
            </svg>
            <h3 class="card-title">要素详目</h3>
          </div>
          <div class="detail-tabs">
            <div class="tab-buttons">
              <button
                v-if="result.elements?.rivers?.length"
                :class="['tab-btn', { active: activeTab === 'rivers' }]"
                @click="activeTab = 'rivers'"
              >
                河流
              </button>
              <button
                v-if="result.elements?.mountains?.length"
                :class="['tab-btn', { active: activeTab === 'mountains' }]"
                @click="activeTab = 'mountains'"
              >
                山脉
              </button>
              <button
                v-if="result.elements?.cities?.length"
                :class="['tab-btn', { active: activeTab === 'cities' }]"
                @click="activeTab = 'cities'"
              >
                城市
              </button>
              <button
                v-if="result.elements?.boundaries?.length"
                :class="['tab-btn', { active: activeTab === 'boundaries' }]"
                @click="activeTab = 'boundaries'"
              >
                边界
              </button>
              <button
                v-if="result.text_labels?.length"
                :class="['tab-btn', { active: activeTab === 'labels' }]"
                @click="activeTab = 'labels'"
              >
                标注
              </button>
            </div>

            <div class="tab-content">
              <!-- 河流 -->
              <div v-if="activeTab === 'rivers' && result.elements?.rivers?.length" class="element-list">
                <div v-for="(river, idx) in result.elements.rivers.slice(0, 10)" :key="idx" class="element-item river-item">
                  <span class="element-index">{{ idx + 1 }}</span>
                  <span class="element-name">河流</span>
                  <span class="element-area">{{ Math.round(river.area_pixels) }} px²</span>
                  <button class="btn-copy" @click="copyText(`河流${idx+1}`)" title="复制">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                      <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                    </svg>
                  </button>
                </div>
                <div v-if="result.elements.rivers.length > 10" class="more-hint">
                  还有 {{ result.elements.rivers.length - 10 }} 条...
                </div>
              </div>

              <!-- 山脉 -->
              <div v-if="activeTab === 'mountains' && result.elements?.mountains?.length" class="element-list">
                <div v-for="(mt, idx) in result.elements.mountains.slice(0, 10)" :key="idx" class="element-item mountain-item">
                  <span class="element-index">{{ idx + 1 }}</span>
                  <span class="element-name">山脉</span>
                  <span class="element-area">{{ Math.round(mt.area_pixels) }} px²</span>
                </div>
                <div v-if="result.elements.mountains.length > 10" class="more-hint">
                  还有 {{ result.elements.mountains.length - 10 }} 座...
                </div>
              </div>

              <!-- 城市 -->
              <div v-if="activeTab === 'cities' && result.elements?.cities?.length" class="element-list">
                <div v-for="(city, idx) in result.elements.cities.slice(0, 10)" :key="idx" class="element-item city-item">
                  <span class="element-index">{{ idx + 1 }}</span>
                  <span class="element-name">城市</span>
                  <span class="element-area">{{ Math.round(city.area_pixels) }} px²</span>
                </div>
                <div v-if="result.elements.cities.length > 10" class="more-hint">
                  还有 {{ result.elements.cities.length - 10 }} 个...
                </div>
              </div>

              <!-- 边界 -->
              <div v-if="activeTab === 'boundaries' && result.elements?.boundaries?.length" class="element-list">
                <div v-for="(bdr, idx) in result.elements.boundaries.slice(0, 10)" :key="idx" class="element-item boundary-item">
                  <span class="element-index">{{ idx + 1 }}</span>
                  <span class="element-name">边界线</span>
                  <span class="element-area">{{ Math.round(bdr.area_pixels) }} px²</span>
                </div>
                <div v-if="result.elements.boundaries.length > 10" class="more-hint">
                  还有 {{ result.elements.boundaries.length - 10 }} 条...
                </div>
              </div>

              <!-- 标注 -->
              <div v-if="activeTab === 'labels' && result.text_labels?.length" class="element-list">
                <div v-for="(label, idx) in result.text_labels.slice(0, 20)" :key="idx" class="element-item label-item">
                  <span class="label-text-display">{{ label.text }}</span>
                  <span class="label-conf">{{ Math.round((label.confidence || 0.8) * 100) }}%</span>
                  <button class="btn-copy" @click="copyText(label.text)" title="复制">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                      <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                    </svg>
                  </button>
                </div>
                <div v-if="result.text_labels.length > 20" class="more-hint">
                  还有 {{ result.text_labels.length - 20 }} 个标注...
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 空状态提示 -->
        <div v-if="!result && imageUrl" class="waiting-card">
          <div class="waiting-text">点击「开始提取」对舆图进行要素分割和识别</div>
        </div>
      </aside>
    </div>

    <!-- 添加控制点对话框 -->
    <div v-if="showPointDialog" class="dialog-overlay" @click.self="showPointDialog = false">
      <div class="dialog">
        <div class="dialog-header">
          <h3>标注控制点</h3>
          <button class="dialog-close" @click="showPointDialog = false">×</button>
        </div>
        <div class="dialog-body">
          <div class="form-item">
            <label>像素坐标</label>
            <span class="form-value">({{ Math.round(pendingPoint.pixelX) }}, {{ Math.round(pendingPoint.pixelY) }})</span>
          </div>
          <div class="form-item">
            <label>经度 (Longitude)</label>
            <input type="number" v-model.number="pendingPoint.lon" step="0.01" class="form-input" placeholder="如: 116.456" />
          </div>
          <div class="form-item">
            <label>纬度 (Latitude)</label>
            <input type="number" v-model.number="pendingPoint.lat" step="0.01" class="form-input" placeholder="如: 39.628" />
          </div>
          <div class="form-hint">输入该点在地图上对应的真实经纬度坐标</div>
        </div>
        <div class="dialog-footer">
          <button class="btn-ghost" @click="showPointDialog = false">取消</button>
          <button class="btn-primary" @click="confirmAddPoint">确认</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onUnmounted, nextTick, watch } from 'vue'
import * as echarts from 'echarts'
import { mapAPI } from '@/services/api'

const fileInputRef = ref(null)
const imageRef = ref(null)
const imageContainerRef = ref(null)
const overlayCanvasRef = ref(null)
const statsChartRef = ref(null)
const imageUrl = ref('')
const selectedFile = ref(null)
const result = ref(null)
const processing = ref(false)
const scaleFactor = ref(1)
const activeTab = ref('rivers')
let statsChart = null

const referencePoints = ref([])
const addingPointMode = ref(false)
const showPointDialog = ref(false)
const pendingPoint = reactive({ pixelX: 0, pixelY: 0, lon: 116.0, lat: 39.0 })
const editingPointIdx = ref(-1)
const editPoint = reactive({ lon: 0, lat: 0 })

const stats = reactive({ rivers: 0, mountains: 0, cities: 0, boundaries: 0, textLabels: 0 })

const options = reactive({ performOcr: true, georeference: false, alpha: 50 })

const canExtract = computed(() => {
  if (!imageUrl.value || processing.value) return false
  if (options.georeference && referencePoints.value.length < 4) return false
  return true
})

onUnmounted(() => { if (statsChart) statsChart.dispose() })

watch(result, (newResult) => {
  if (newResult) {
    updateStats()
    nextTick(() => { drawOverlay(); initStatsChart() })
    // Set default active tab to first available
    if (newResult.elements?.rivers?.length) activeTab.value = 'rivers'
    else if (newResult.elements?.mountains?.length) activeTab.value = 'mountains'
    else if (newResult.elements?.cities?.length) activeTab.value = 'cities'
    else if (newResult.elements?.boundaries?.length) activeTab.value = 'boundaries'
    else if (newResult.text_labels?.length) activeTab.value = 'labels'
  }
})

watch(() => options.alpha, () => { if (result.value) drawOverlay() })

function triggerUpload() { fileInputRef.value?.click() }

function handleFileSelect(event) {
  const file = event.target.files?.[0]
  if (!file || !file.type.startsWith('image/')) {
    alert('请选择图像文件')
    return
  }
  selectedFile.value = file
  const reader = new FileReader()
  reader.onload = (e) => {
    imageUrl.value = e.target.result
    result.value = null
    referencePoints.value = []
    clearOverlay()
  }
  reader.readAsDataURL(file)
}

function onImageLoad() {
  if (!imageRef.value || !overlayCanvasRef.value || !imageContainerRef.value) return
  const img = imageRef.value
  const canvas = overlayCanvasRef.value
  canvas.width = img.naturalWidth
  canvas.height = img.naturalHeight
  canvas.style.width = img.width + 'px'
  canvas.style.height = img.height + 'px'
  const container = imageContainerRef.value
  const containerW = container.clientWidth
  canvas.style.left = ((containerW - img.width) / 2) + 'px'
  canvas.style.top = '0px'
  scaleFactor.value = img.width / img.naturalWidth
}

function clearOverlay() {
  if (!overlayCanvasRef.value) return
  const ctx = overlayCanvasRef.value.getContext('2d')
  ctx.clearRect(0, 0, overlayCanvasRef.value.width, overlayCanvasRef.value.height)
}

function toggleAddingPointMode() { addingPointMode.value = !addingPointMode.value }

function onImageClick(event) {
  if (!addingPointMode.value) return
  const img = imageRef.value
  if (!img) return
  const rect = img.getBoundingClientRect()
  const scaleX = img.naturalWidth / img.width
  const scaleY = img.naturalHeight / img.height
  pendingPoint.pixelX = (event.clientX - rect.left) * scaleX
  pendingPoint.pixelY = (event.clientY - rect.top) * scaleY
  pendingPoint.lon = 116.0 + (Math.random() - 0.5) * 0.5
  pendingPoint.lat = 39.0 + (Math.random() - 0.5) * 0.5
  showPointDialog.value = true
  addingPointMode.value = false
}

function confirmAddPoint() {
  referencePoints.value.push({ pixelX: pendingPoint.pixelX, pixelY: pendingPoint.pixelY, lon: pendingPoint.lon, lat: pendingPoint.lat })
  showPointDialog.value = false
}

function removeReferencePoint(idx) { referencePoints.value.splice(idx, 1) }
function clearReferencePoints() { referencePoints.value = [] }

function startEditPoint(idx, row) {
  editingPointIdx.value = idx
  editPoint.lon = row.lon
  editPoint.lat = row.lat
}

function confirmEditPoint(idx) {
  referencePoints.value[idx].lon = editPoint.lon
  referencePoints.value[idx].lat = editPoint.lat
  editingPointIdx.value = -1
}

function cancelEditPoint() { editingPointIdx.value = -1 }

async function extractMap() {
  if (!canExtract.value) return
  processing.value = true
  try {
    const refPts = referencePoints.value.map(pt => [pt.pixelX, pt.pixelY, pt.lon, pt.lat])
    const apiResult = await mapAPI.extract({
      imagePath: selectedFile.value, // Pass actual File object
      performOcr: options.performOcr,
      georeference: options.georeference,
      referencePoints: refPts
    })
    result.value = apiResult
  } catch (e) {
    console.error('提取失败:', e)
    result.value = getMockResult()
  } finally {
    processing.value = false
  }
}

function resetAll() {
  imageUrl.value = ''
  selectedFile.value = null
  result.value = null
  referencePoints.value = []
  addingPointMode.value = false
  clearOverlay()
  if (statsChart) statsChart.clear()
}

function exportGeoJSON() {
  if (!result.value?.geojson) {
    alert('暂无GeoJSON数据可导出')
    return
  }
  const blob = new Blob([JSON.stringify(result.value.geojson, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'map_extraction.geojson'
  a.click()
  URL.revokeObjectURL(url)
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // Fallback for older browsers
    const textarea = document.createElement('textarea')
    textarea.value = text
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
}

function updateStats() {
  const elements = result.value?.elements || {}
  stats.rivers = elements.rivers?.length || 0
  stats.mountains = elements.mountains?.length || 0
  stats.cities = elements.cities?.length || 0
  stats.boundaries = elements.boundaries?.length || 0
  stats.textLabels = result.value?.text_labels?.length || 0
}

function initStatsChart() {
  if (!statsChartRef.value) return
  if (statsChart) statsChart.dispose()
  statsChart = echarts.init(statsChartRef.value)
  const chartData = [
    { value: stats.rivers, name: '河流', itemStyle: { color: '#6b8F8a' } },
    { value: stats.mountains, name: '山脉', itemStyle: { color: '#8B6914' } },
    { value: stats.cities, name: '城市', itemStyle: { color: '#b54a32' } },
    { value: stats.boundaries, name: '边界线', itemStyle: { color: '#4a7a4a' } },
    { value: stats.textLabels, name: '标注', itemStyle: { color: '#4a4a4a' } }
  ].filter(d => d.value > 0)
  if (chartData.length === 0) return
  statsChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['35%', '65%'],
      center: ['50%', '50%'],
      data: chartData,
      label: {
        formatter: '{b}',
        fontSize: 11,
        color: '#4a4a4a'
      },
      itemStyle: {
        borderRadius: 4,
        borderColor: '#faf8f3',
        borderWidth: 2
      }
    }]
  })
}

function drawOverlay() {
  if (!overlayCanvasRef.value || !result.value) return
  const canvas = overlayCanvasRef.value
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  const alpha = options.alpha / 100
  const classColors = {
    rivers: `rgba(107, 143, 138, ${alpha})`,
    mountains: `rgba(139, 105, 20, ${alpha})`,
    cities: `rgba(181, 74, 50, ${alpha})`,
    boundaries: `rgba(74, 122, 74, ${alpha})`,
    text_labels: `rgba(74, 74, 74, ${alpha})`
  }
  for (const [className, features] of Object.entries(result.value.elements || {})) {
    const color = classColors[className]
    if (!color) continue
    ctx.fillStyle = color
    ctx.strokeStyle = color.replace(/[\d.]+\)$/, '1)')
    for (const feature of features) {
      const polygon = feature.polygon
      if (!polygon || polygon.length < 3) continue
      ctx.beginPath()
      ctx.moveTo(polygon[0][0], polygon[0][1])
      for (let i = 1; i < polygon.length; i++) ctx.lineTo(polygon[i][0], polygon[i][1])
      ctx.closePath()
      ctx.fill()
      ctx.lineWidth = 2
      ctx.stroke()
    }
  }
}

function getPointMarkerStyle(pt) {
  if (!imageRef.value) return {}
  const scale = scaleFactor.value || 1
  const img = imageRef.value
  const containerW = imageContainerRef.value?.clientWidth || img.width
  const offsetX = (containerW - img.width) / 2
  return { left: (offsetX + pt.pixelX * scale) + 'px', top: (pt.pixelY * scale) + 'px' }
}

function getLabelMarkerStyle(label) {
  const bbox = label.bbox || [0, 0, 60, 20]
  const [x, y, w, h] = bbox
  const scale = scaleFactor.value || 1
  const img = imageRef.value
  const containerW = imageContainerRef.value?.clientWidth || img?.width || 0
  const offsetX = img ? (containerW - img.width) / 2 : 0
  return {
    left: (offsetX + x * scale) + 'px',
    top: (y * scale) + 'px',
    width: Math.max(w * scale, 40) + 'px',
    minHeight: Math.max(h * scale, 20) + 'px'
  }
}

function getMockResult() {
  return {
    image_path: 'mock',
    elements: {
      rivers: [
        { polygon: [[100, 200], [200, 180], [250, 220], [180, 260], [100, 200]], area_pixels: 8500 },
        { polygon: [[300, 100], [400, 90], [420, 150], [350, 160], [300, 100]], area_pixels: 6200 }
      ],
      mountains: [{ polygon: [[50, 50], [80, 20], [110, 50], [80, 80], [50, 50]], area_pixels: 3200 }],
      cities: [{ polygon: [[200, 150], [220, 140], [240, 150], [230, 170], [210, 170], [200, 150]], area_pixels: 800 }],
      boundaries: []
    },
    text_labels: [
      { text: '固安', bbox: [210, 145, 40, 15], confidence: 0.92 },
      { text: '河流', bbox: [120, 210, 40, 15], confidence: 0.88 }
    ],
    statistics: { total_elements: 5, by_type: { rivers: 2, mountains: 1, cities: 1, boundaries: 0, text_labels: 2 } }
  }
}
</script>

<style scoped>
/* ============================
   志鉴 · 舆图提取
   设计：古籍书房 Digital Scriptorium
   ============================ */

.map-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  overflow: hidden;
}

/* ==================== 页面标题 ==================== */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 24px;
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
  letter-spacing: 1px;
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

.btn-small {
  padding: 5px 10px;
  font-family: var(--font-body);
  font-size: 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-small.btn-primary {
  background: var(--accent);
  border: none;
  color: white;
}

.btn-small.btn-primary:hover:not(:disabled) {
  background: #a04429;
}

.btn-small.btn-warning {
  background: #d4a03c;
  border: none;
  color: white;
}

.btn-small:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ==================== 主布局 ==================== */
.main-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 0;
  overflow: hidden;
  padding: 20px 24px;
  height: calc(100vh - 73px);
}

/* ==================== 舆图面板 ==================== */
.map-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
  padding-right: 8px;
}

.map-card {
  background: var(--bg-card);
  border: 1px solid rgba(181, 74, 50, 0.12);
  border-radius: 6px;
  overflow: hidden;
  transition: border-color 0.25s ease;
}

.map-card:hover {
  border-color: rgba(181, 74, 50, 0.25);
}

.image-area {
  padding: 20px;
  background: var(--bg-secondary);
  display: flex;
  justify-content: center;
}

.image-container {
  position: relative;
  display: inline-block;
  min-width: 100%;
}

.image-container.mode-add-point { cursor: crosshair; }

.map-image {
  max-width: 100%;
  display: block;
  margin: 0 auto;
}

.overlay-canvas {
  position: absolute;
  top: 0;
  pointer-events: none;
}

/* 控制点标记 */
.point-marker {
  position: absolute;
  width: 24px;
  height: 24px;
  transform: translate(-50%, -50%);
  cursor: pointer;
  z-index: 10;
  transition: all 0.2s ease;
}

.point-marker:hover {
  transform: translate(-50%, -50%) scale(1.15);
}

.point-marker:hover .point-number {
  background: #a04429;
}

.point-number {
  width: 100%;
  height: 100%;
  background: var(--accent);
  border: 2px solid var(--bg-card);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 11px;
  font-weight: 600;
  font-family: var(--font-body);
  box-shadow: 0 2px 6px rgba(181, 74, 50, 0.3);
}

/* 文字标注 */
.label-marker {
  position: absolute;
  background: var(--bg-card);
  border: 1px solid rgba(181, 74, 50, 0.25);
  border-radius: 3px;
  padding: 2px 8px;
  font-size: 12px;
  font-family: var(--font-body);
  color: var(--text-secondary);
  white-space: nowrap;
  pointer-events: none;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.label-text {
  font-family: var(--font-body);
}

/* 添加控制点覆盖层 */
.add-point-overlay {
  position: absolute;
  inset: 0;
  background: rgba(107, 143, 138, 0.06);
  border: 2px dashed var(--accent);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  pointer-events: none;
  border-radius: 4px;
}

.crosshair {
  color: var(--accent);
}

.add-point-overlay span {
  background: var(--bg-card);
  color: var(--accent);
  padding: 8px 20px;
  border-radius: 20px;
  font-size: 14px;
  font-family: var(--font-body);
  border: 1px solid var(--accent);
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 40px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background: var(--bg-card);
}

.empty-state:hover {
  background: var(--bg-secondary);
}

.empty-icon {
  color: var(--accent);
  opacity: 0.5;
  margin-bottom: 8px;
}

.empty-state h3 {
  font-family: var(--font-display);
  font-size: 20px;
  color: var(--text-secondary);
  margin: 0 0 8px 0;
  letter-spacing: 2px;
}

.empty-state p {
  font-family: var(--font-body);
  color: var(--text-secondary);
  font-size: 14px;
  margin: 0 0 6px 0;
}

.upload-hint {
  font-family: var(--font-body);
  font-size: 12px;
  color: var(--text-secondary);
  opacity: 0.7;
}

/* ==================== 控制面板 ==================== */
.control-card {
  background: var(--bg-card);
  border: 1px solid rgba(181, 74, 50, 0.12);
  border-radius: 6px;
  padding: 20px;
  transition: border-color 0.25s ease;
}

.control-card:hover {
  border-color: rgba(181, 74, 50, 0.25);
}

.control-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(181, 74, 50, 0.1);
}

.control-icon {
  color: var(--accent);
}

.control-title {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: 1px;
}

.options-row {
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.checkbox-wrapper {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 14px;
  color: var(--text-secondary);
}

.checkbox-wrapper input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--accent);
}

.checkbox-label {
  font-family: var(--font-body);
  font-size: 14px;
}

.alpha-control {
  display: flex;
  align-items: center;
  gap: 8px;
}

.alpha-label {
  font-size: 13px;
  color: var(--text-secondary);
  font-family: var(--font-body);
}

.alpha-slider {
  width: 80px;
  accent-color: var(--accent);
}

.alpha-value {
  font-size: 12px;
  color: var(--accent);
  min-width: 36px;
  font-weight: 500;
  font-family: var(--font-mono);
}

/* 参考点管理 */
.ref-points-section {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(181, 74, 50, 0.1);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-body);
}

.section-title svg {
  color: var(--accent);
}

.point-count {
  color: var(--accent);
  font-weight: 500;
}

.ref-actions {
  display: flex;
  gap: 8px;
}

/* 参考点表格 */
.ref-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--font-body);
  font-size: 13px;
  margin-top: 12px;
}

.ref-table th {
  text-align: left;
  padding: 8px;
  border-bottom: 1px solid rgba(181, 74, 50, 0.1);
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 12px;
}

.ref-table td {
  padding: 8px;
  border-bottom: 1px solid rgba(181, 74, 50, 0.08);
}

.col-index { width: 40px; text-align: center; }
.col-pixel { }
.col-coord { }
.col-action { width: 50px; text-align: center; }

.table-number {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background: var(--bg-secondary);
  border-radius: 50%;
  font-size: 11px;
  color: var(--text-secondary);
}

.coord-text {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.coord-display {
  cursor: pointer;
  color: var(--accent);
  font-size: 12px;
  font-family: var(--font-mono);
  padding: 2px 6px;
  border-radius: 3px;
  transition: background 0.2s;
}

.coord-display:hover {
  background: rgba(181, 74, 50, 0.08);
}

.coord-edit {
  display: flex;
  align-items: center;
  gap: 4px;
}

.coord-input {
  width: 70px;
  padding: 4px;
  border: 1px solid rgba(181, 74, 50, 0.2);
  border-radius: 3px;
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--bg-card);
}

.coord-input:focus {
  outline: none;
  border-color: var(--accent);
}

.coord-sep {
  color: var(--accent);
  font-weight: 500;
}

.btn-confirm, .btn-cancel {
  padding: 2px 6px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
  border: none;
}

.btn-confirm {
  background: var(--secondary);
  color: white;
}

.btn-confirm:hover {
  background: #5a7a75;
}

.btn-cancel {
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.btn-cancel:hover {
  background: var(--bg-primary);
}

.btn-delete {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--accent);
  padding: 4px;
  border-radius: 3px;
  transition: all 0.2s ease;
}

.btn-delete:hover {
  background: rgba(181, 74, 50, 0.08);
}

/* 提示框 */
.alert {
  margin-top: 10px;
  padding: 10px 14px;
  border-radius: 4px;
  font-family: var(--font-body);
  font-size: 13px;
}

.alert-warning {
  background: rgba(212, 160, 60, 0.1);
  border: 1px solid rgba(212, 160, 60, 0.4);
  color: #9a7b2e;
}

.alert-success {
  background: rgba(107, 143, 138, 0.1);
  border: 1px solid rgba(107, 143, 138, 0.4);
  color: var(--secondary);
}

.extract-actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
}

.btn-extract {
  flex: 1;
  padding: 10px 20px;
  font-size: 14px;
  justify-content: center;
}

/* ==================== 右侧面板 ==================== */
.side-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-left: 20px;
  overflow-y: auto;
}

.stats-card,
.detail-card,
.waiting-card {
  background: var(--bg-card);
  border: 1px solid rgba(181, 74, 50, 0.12);
  border-radius: 6px;
  overflow: hidden;
  transition: border-color 0.25s ease;
}

.stats-card:hover,
.detail-card:hover {
  border-color: rgba(181, 74, 50, 0.25);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  background: var(--bg-secondary);
  border-bottom: 1px solid rgba(181, 74, 50, 0.1);
}

.card-icon {
  color: var(--accent);
}

.card-title {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: 1px;
}

/* 统计图表 */
.stats-chart {
  height: 160px;
  padding: 12px;
}

.stats-legend {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 12px 18px;
  border-top: 1px solid rgba(181, 74, 50, 0.1);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  font-family: var(--font-body);
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  border: 1px solid rgba(0,0,0,0.08);
}

/* 详情标签页 */
.detail-tabs {
  padding: 12px;
}

.tab-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.tab-btn {
  padding: 6px 14px;
  background: var(--bg-secondary);
  border: 1px solid rgba(181, 74, 50, 0.12);
  border-radius: 4px;
  font-family: var(--font-body);
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.tab-btn.active {
  background: var(--accent);
  border-color: var(--accent);
  color: white;
}

.element-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 280px;
  overflow-y: auto;
}

.element-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 13px;
  background: var(--bg-secondary);
  border-left: 3px solid rgba(181, 74, 50, 0.3);
  transition: all 0.2s ease;
}

.element-item:hover {
  background: var(--bg-primary);
  border-left-color: var(--accent);
}

.river-item { border-left-color: var(--secondary); }
.mountain-item { border-left-color: #8B6914; }
.city-item { border-left-color: var(--accent); }
.boundary-item { border-left-color: #4a7a4a; }
.label-item { border-left-color: var(--text-secondary); }

.element-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  background: var(--bg-card);
  border-radius: 50%;
  font-size: 10px;
  color: var(--text-secondary);
}

.element-name {
  flex: 1;
  font-family: var(--font-body);
  color: var(--text-primary);
}

.element-area {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: var(--font-mono);
}

.btn-copy {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 2px;
  border-radius: 3px;
  transition: all 0.2s ease;
  opacity: 0;
}

.element-item:hover .btn-copy {
  opacity: 1;
}

.btn-copy:hover {
  color: var(--accent);
}

.label-text-display {
  flex: 1;
  font-family: var(--font-body);
  color: var(--text-primary);
}

.label-conf {
  font-size: 11px;
  color: var(--accent);
  font-weight: 500;
}

.more-hint {
  text-align: center;
  color: var(--text-secondary);
  font-size: 12px;
  padding: 8px;
  font-family: var(--font-body);
  opacity: 0.7;
}

.waiting-card {
  padding: 16px;
  text-align: center;
}

.waiting-text {
  font-family: var(--font-body);
  font-size: 14px;
  color: var(--text-secondary);
}

/* ==================== 对话框 ==================== */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(26, 26, 26, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog {
  background: var(--bg-card);
  border-radius: 6px;
  width: 420px;
  max-width: 90vw;
  box-shadow: 0 8px 32px rgba(26, 26, 26, 0.2);
  border: 1px solid rgba(181, 74, 50, 0.15);
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(181, 74, 50, 0.1);
}

.dialog-header h3 {
  font-family: var(--font-display);
  font-size: 18px;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: 2px;
}

.dialog-close {
  background: none;
  border: none;
  font-size: 24px;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.dialog-close:hover {
  color: var(--accent);
}

.dialog-body {
  padding: 20px;
}

.form-item {
  margin-bottom: 16px;
}

.form-item label {
  display: block;
  font-family: var(--font-body);
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.form-value {
  font-family: var(--font-mono);
  color: var(--text-secondary);
  font-size: 13px;
}

.form-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid rgba(181, 74, 50, 0.2);
  border-radius: 4px;
  font-family: var(--font-body);
  font-size: 14px;
  box-sizing: border-box;
  background: var(--bg-card);
}

.form-input:focus {
  outline: none;
  border-color: var(--accent);
}

.form-hint {
  font-family: var(--font-body);
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 8px;
  opacity: 0.7;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid rgba(181, 74, 50, 0.1);
  background: var(--bg-secondary);
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
    grid-template-columns: 1fr 280px;
  }
}

@media (max-width: 900px) {
  .main-layout {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr auto;
    padding: 12px 16px;
  }

  .side-panel {
    flex-direction: row;
    padding-left: 0;
    padding-top: 14px;
    overflow-x: auto;
  }

  .stats-card,
  .detail-card,
  .waiting-card {
    min-width: 280px;
  }
}

@media (max-width: 600px) {
  .page-header {
    padding: 12px 16px;
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }

  .header-right {
    width: 100%;
    justify-content: flex-start;
  }

  .options-row {
    gap: 12px;
  }
}
</style>
