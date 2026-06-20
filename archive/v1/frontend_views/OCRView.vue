<template>
  <div class="ocr-view">
    <!-- OCR 模块禁用状态卡（M1：默认关） -->
    <div v-if="ocrStore.ocrStatus?.status === 'disabled'" class="ocr-disabled-banner">
      <div class="banner-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
          <rect x="3" y="11" width="18" height="11" rx="2"/>
          <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
          <line x1="12" y1="15" x2="12" y2="19"/>
        </svg>
      </div>
      <div class="banner-content">
        <h2 class="banner-title">OCR 模块暂未启用</h2>
        <p class="banner-message">
          当前版本聚焦「星云图谱」与「RAG 智能问答」两大模块。
          后续如需加入扫描录入功能，可在后端环境变量中设置
          <code>ZHIJIAN_OCR_ENABLED=true</code> 并重启服务。
        </p>
        <p class="banner-hint">
          现有的「星云图谱」可浏览 200 万家谱人物，「RAG 问答」可对知识库提问。
        </p>
      </div>
      <div class="banner-actions">
        <el-button type="primary" plain @click="$router.push('/')">返回首页</el-button>
        <el-button type="primary" plain @click="$router.push('/knowledge')">查看星云图谱</el-button>
      </div>
    </div>

    <!-- OCR 启用时显示原有 UI -->
    <template v-else>
    <header class="page-header">
      <div class="header-left">
        <h1 class="page-title">OCR 古籍识别</h1>
        <p class="page-subtitle">扫描件自动识别 · 异体字检测 · 联动知识库</p>
      </div>
      <div class="header-right">
        <el-select v-model="ocrStore.provider" size="default" class="provider-select">
          <el-option
            v-for="p in providerOptions"
            :key="p.value"
            :label="p.label"
            :value="p.value"
            :disabled="!p.available"
          />
        </el-select>
        <el-button
          v-if="aliyunAvailable"
          type="warning"
          size="small"
          :loading="hiAccLoading"
          :disabled="!ocrStore.currentImage"
          @click="runHighAccuracy"
          title="阿里云古籍识别（消耗云端配额）"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
            <polygon points="12 2 15 8.5 22 9.3 17 14.1 18.2 21 12 17.8 5.8 21 7 14.1 2 9.3 9 8.5 12 2"/>
          </svg>
          高精度（云端）
        </el-button>
        <span class="status-tag" :class="ocrStatusClass">
          {{ ocrStatusLabel }}
        </span>
      </div>
    </header>

    <div class="ocr-layout">
      <!-- 左侧：上传 + 样本 -->
      <aside class="left-panel">
        <div
          class="upload-zone"
          :class="{ dragging: isDragging, hasImage: !!ocrStore.currentImage }"
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="handleDrop"
          @click="triggerFileInput"
        >
          <input
            ref="fileInput"
            type="file"
            accept="image/png,image/jpeg,image/tiff,image/bmp"
            style="display:none"
            @change="handleFileSelect"
          />
          <div v-if="!ocrStore.currentImage" class="upload-empty">
            <div class="upload-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
              </svg>
            </div>
            <p class="upload-title">拖拽图片到此处</p>
            <p class="upload-hint">或点击选择文件（PNG / JPG / TIFF / BMP，≤20MB）</p>
          </div>
          <div v-else class="upload-preview">
            <img :src="ocrStore.currentImage" alt="已上传图片" />
            <button class="preview-clear" @click.stop="ocrStore.reset()" title="清除">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>

        <button
          v-if="ocrStore.currentImage"
          class="btn-recognize"
          :disabled="ocrStore.loading"
          @click="runRecognize"
        >
          <span v-if="!ocrStore.loading" class="btn-content">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            开始识别
          </span>
          <span v-else class="btn-content">
            <span class="spinner"></span>
            识别中（首次会下载模型）...
          </span>
        </button>

        <div v-if="ocrStore.samples.length > 0" class="samples-section">
          <h3 class="section-title">样本图</h3>
          <div class="samples-grid">
            <div
              v-for="s in ocrStore.samples.slice(0, 6)"
              :key="s.name"
              class="sample-thumb"
              :class="{ active: ocrStore.currentFile?.name === s.name }"
              @click="loadSample(s)"
            >
              <img :src="s.url" :alt="s.name" />
              <div class="sample-meta">
                <span class="sample-name">{{ s.name }}</span>
                <span class="sample-size">{{ s.size_kb }}KB</span>
              </div>
            </div>
          </div>
        </div>
      </aside>

      <!-- 右侧：识别结果 -->
      <section class="right-panel">
        <div v-if="ocrStore.error" class="error-banner">
          <span>{{ ocrStore.error }}</span>
          <button @click="ocrStore.error = null">×</button>
        </div>

        <div v-if="!ocrStore.result" class="empty-state">
          <div class="empty-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" width="56" height="56">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="9" y1="13" x2="15" y2="13"/>
              <line x1="9" y1="17" x2="13" y2="17"/>
            </svg>
          </div>
          <h3>等待识别</h3>
          <p>上传图片或选择样本图开始 OCR 识别</p>
        </div>

        <div v-else class="result-content">
          <div class="result-stats">
            <div class="stat-item">
              <span class="stat-label">字符数</span>
              <span class="stat-value">{{ totalChars }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">行数</span>
              <span class="stat-value">{{ totalLines }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">置信度</span>
              <span class="stat-value">{{ avgConfidence }}%</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">异体字</span>
              <span class="stat-value highlight">{{ totalVariants }}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">避讳字</span>
              <span class="stat-value highlight">{{ totalTaboos }}</span>
            </div>
          </div>

          <div class="result-text">
            <h3 class="result-title">识别结果</h3>
            <pre class="text-block">{{ fullText }}</pre>
          </div>

          <div v-if="charsWithVariants.length > 0" class="variant-detail">
            <h3 class="result-title">异体字明细</h3>
            <div class="variant-list">
              <div
                v-for="(c, i) in charsWithVariants.slice(0, 20)"
                :key="i"
                class="variant-chip"
              >
                <span class="char-original">{{ c.char }}</span>
                <span class="char-arrow">→</span>
                <span class="char-standard">{{ c.variant_of || '?' }}</span>
                <span v-if="c.is_taboo" class="badge-taboo">避讳</span>
              </div>
            </div>
          </div>

          <!-- 联动按钮 -->
          <div class="action-bar">
            <button class="btn-action btn-rag" :disabled="!fullText" @click="showRagDialog = true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
              入问答库（RAG）
            </button>
            <button class="btn-action btn-kg" :disabled="!fullText" @click="previewKG">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <circle cx="12" cy="12" r="3"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="5" r="2"/>
              </svg>
              入知识库（KG）
            </button>
          </div>
        </div>
      </section>
    </div>

    <!-- KG 预览模态框 -->
    <el-dialog
      v-model="showKgDialog"
      title="预览候选实体与关系"
      width="700px"
      :close-on-click-modal="false"
    >
      <div v-if="ocrStore.previewing" class="dialog-loading">
        <span class="spinner"></span>
        抽取中...
      </div>
      <div v-else>
        <p class="dialog-summary">
          从识别结果中抽取到 <strong>{{ selectedEntities.length }}</strong> 个实体、
          <strong>{{ selectedRelations.length }}</strong> 条关系（已自动勾选）
        </p>
        <h4 class="dialog-section">实体</h4>
        <el-checkbox-group v-model="selectedEntities" class="entity-list">
          <el-checkbox
            v-for="e in ocrStore.previewEntities"
            :key="e.name"
            :value="e.name"
            :label="e.name"
            border
            class="entity-checkbox"
          >
            <span class="entity-name">{{ e.name }}</span>
            <span v-if="e.dynasty" class="entity-tag">{{ e.dynasty }}</span>
            <span v-if="e.birthplace" class="entity-meta">📍 {{ e.birthplace }}</span>
          </el-checkbox>
        </el-checkbox-group>
        <h4 v-if="ocrStore.previewRelations.length > 0" class="dialog-section">关系</h4>
        <el-checkbox-group v-model="selectedRelations" class="relation-list">
          <el-checkbox
            v-for="(r, i) in ocrStore.previewRelations"
            :key="i"
            :value="i"
            :label="`${r.source} → ${r.target}（${r.relation}）`"
            border
            class="relation-checkbox"
          />
        </el-checkbox-group>
      </div>
      <template #footer>
        <el-button @click="showKgDialog = false">取消</el-button>
        <el-button type="primary" :loading="kgImporting" @click="confirmKGImport">
          确认入库（{{ selectedEntities.length }} 实体 / {{ selectedRelations.length }} 关系）
        </el-button>
      </template>
    </el-dialog>

    <!-- RAG 灌入模态框 -->
    <el-dialog v-model="showRagDialog" title="入问答库" width="500px" :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="文档标题">
          <el-input v-model="ragTitle" placeholder="例如：康熙版固安县志第一页" />
        </el-form-item>
        <el-form-item label="章节标题（可选）">
          <el-input v-model="ragChapter" placeholder="例如：建置沿革" />
        </el-form-item>
        <el-form-item>
          <p class="dialog-summary">
            即将把 <strong>{{ totalChars }}</strong> 字识别结果灌入 RAG 知识库。<br/>
            完成后可在「智能问答」页面对该内容提问。
          </p>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRagDialog = false">取消</el-button>
        <el-button type="primary" :loading="ragImporting" @click="confirmRagImport">确认灌入</el-button>
      </template>
    </el-dialog>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useOcrStore } from '@/stores/ocr'
import { useAppStore } from '@/stores/app'
import { kgAPI, ragAPI, ocrAPI } from '@/services/api'

const ocrStore = useOcrStore()
const appStore = useAppStore()

const fileInput = ref(null)
const isDragging = ref(false)

const providerOptions = ref([])
const aliyunAvailable = ref(false)
const hiAccLoading = ref(false)

const showKgDialog = ref(false)
const showRagDialog = ref(false)
const selectedEntities = ref([])
const selectedRelations = ref([])
const kgImporting = ref(false)
const ragImporting = ref(false)
const ragTitle = ref('OCR 识别结果')
const ragChapter = ref('')

const ocrStatusClass = computed(() => {
  if (!ocrStore.ocrStatus) return 'pending'
  return ocrStore.ocrStatus.status === 'operational' ? 'ready' : 'error'
})
const ocrStatusLabel = computed(() => {
  if (!ocrStore.ocrStatus) return '加载中...'
  return ocrStore.ocrStatus.status === 'operational' ? 'OCR 就绪' : '不可用'
})

const totalChars = computed(() => {
  if (!ocrStore.result?.pages) return 0
  return ocrStore.result.pages.reduce((s, p) => s + (p.chars?.length || 0), 0)
})
const totalLines = computed(() => {
  if (!ocrStore.result?.pages) return 0
  return ocrStore.result.pages.reduce((s, p) => s + (p.lines?.length || 0), 0)
})
const totalVariants = computed(() => {
  if (!ocrStore.result?.pages) return 0
  return ocrStore.result.pages.reduce((s, p) => s + (p.variant_count || 0), 0)
})
const totalTaboos = computed(() => {
  if (!ocrStore.result?.pages) return 0
  return ocrStore.result.pages.reduce((s, p) => s + (p.taboo_count || 0), 0)
})
const avgConfidence = computed(() => {
  if (!ocrStore.result?.pages) return 0
  const confs = ocrStore.result.pages.map(p => p.ocr_confidence || 0).filter(c => c > 0)
  if (confs.length === 0) return 0
  return Math.round((confs.reduce((a, b) => a + b, 0) / confs.length) * 100)
})
const fullText = computed(() => ocrStore.getFullText())

const charsWithVariants = computed(() => {
  if (!ocrStore.result?.pages) return []
  const out = []
  for (const p of ocrStore.result.pages) {
    for (const c of (p.chars || [])) {
      if (c.is_variant || c.is_taboo) out.push(c)
    }
  }
  return out
})

function triggerFileInput() {
  fileInput.value?.click()
}

function handleFileSelect(e) {
  const file = e.target.files?.[0]
  if (file) loadFile(file)
}

function handleDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) loadFile(file)
}

function loadFile(file) {
  const reader = new FileReader()
  reader.onload = () => ocrStore.setCurrentImage(reader.result, file)
  reader.readAsDataURL(file)
}

async function loadSample(sample) {
  try {
    await ocrStore.recognizeFromUrl(sample)
    ElMessage.success(`已识别样本：${sample.name}`)
  } catch (e) {
    ElMessage.error('识别失败：' + (e.message || '未知错误'))
  }
}

async function runRecognize() {
  if (!ocrStore.currentFile) return
  try {
    await ocrStore.recognize(ocrStore.currentFile)
    ElMessage.success('识别完成')
  } catch (e) {
    ElMessage.error('识别失败：' + (e.message || '未知错误'))
  }
}

async function previewKG() {
  if (!fullText.value) return
  showKgDialog.value = true
  ocrStore.previewing = true
  try {
    const res = await kgAPI.extract(fullText.value.slice(0, 2000), 'OCR')
    ocrStore.previewEntities = res.entities || []
    ocrStore.previewRelations = res.relations || []
    selectedEntities.value = ocrStore.previewEntities
      .filter((e) => e.type === 'PER')
      .map((e) => e.name)
    selectedRelations.value = ocrStore.previewRelations.map((_, i) => i)
  } catch (e) {
    ElMessage.error('预览失败：' + (e.message || '未知错误'))
    showKgDialog.value = false
  } finally {
    ocrStore.previewing = false
  }
}

async function confirmKGImport() {
  kgImporting.value = true
  try {
    const entitiesToAdd = ocrStore.previewEntities.filter((e) => selectedEntities.value.includes(e.name))
    let ok = 0
    for (const e of entitiesToAdd) {
      try {
        await kgAPI.addEntity({
          name: e.name,
          entity_type: e.type || 'PER',
          biography: (e.biography || '').slice(0, 500),
          dynasty: e.dynasty || '',
          years: e.years || '',
          birthplace: e.birthplace || e.location || '',
          source: 'OCR',
        })
        ok++
      } catch (err) {
        console.warn('addEntity failed', e.name, err)
      }
    }
    let relOk = 0
    for (const i of selectedRelations.value) {
      const r = ocrStore.previewRelations[i]
      if (!r) continue
      try {
        await kgAPI.addRelation(r.source, r.target, r.relation || 'RELATED', 0.5)
        relOk++
      } catch (err) {
        console.warn('addRelation failed', r, err)
      }
    }
    ElMessage.success(`已入库：${ok} 实体 / ${relOk} 关系`)
    showKgDialog.value = false
    appStore.setModuleStatus('kg', { ready: true })
  } catch (e) {
    ElMessage.error('入库失败：' + (e.message || '未知错误'))
  } finally {
    kgImporting.value = false
  }
}

async function confirmRagImport() {
  ragImporting.value = true
  try {
    await ragAPI.ingest(fullText.value, ragTitle.value || 'OCR 识别结果', ragChapter.value || '', { source: 'OCR' })
    ElMessage.success('已灌入问答库')
    showRagDialog.value = false
    appStore.setModuleStatus('rag', { ready: true })
  } catch (e) {
    ElMessage.error('灌入失败：' + (e.message || '未知错误'))
  } finally {
    ragImporting.value = false
  }
}

async function fetchProviders() {
  try {
    const res = await ocrAPI.providers()
    const providers = res.providers || {}
    const labels = {
      easyocr: 'EasyOCR（本地）',
      paddleocr: 'PaddleOCR（本地）',
      rapidocr: 'RapidOCR（本地·推荐）',
      aliyun: '阿里云 OCR（云端）',
    }
    providerOptions.value = Object.entries(providers).map(([name, info]) => ({
      value: name,
      label: labels[name] || name,
      available: !!info.available,
      tier: info.tier || 'local',
      note: info.note || '',
    }))
    aliyunAvailable.value = !!(providers.aliyun && providers.aliyun.available)
    if (res.default) {
      ocrStore.provider = res.default
    }
  } catch (e) {
    console.warn('fetchProviders failed', e)
  }
}

async function runHighAccuracy() {
  if (!ocrStore.currentFile) {
    ElMessage.warning('请先选择图片')
    return
  }
  hiAccLoading.value = true
  try {
    await ocrStore.recognize(ocrStore.currentFile, 'aliyun')
    ElMessage.success('高精度识别完成')
  } catch (e) {
    ElMessage.error('云端识别失败：' + (e.response?.data?.detail || e.message || '未知错误'))
  } finally {
    hiAccLoading.value = false
  }
}

onMounted(async () => {
  await Promise.all([
    ocrStore.fetchStatus(),
    ocrStore.fetchSamples(),
    ocrStore.fetchVariants(),
    fetchProviders(),
  ])
})

onUnmounted(() => {
  // 不重置 store，避免误关页面丢失结果
})
</script>

<style scoped>
.ocr-view {
  min-height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}

/* ==================== Header ==================== */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px var(--space-xl);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}
.header-left { display: flex; flex-direction: column; gap: 2px; }
.page-title {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 400;
  margin: 0;
  letter-spacing: 0.1em;
  color: var(--text-primary);
}
.page-subtitle { font-size: 13px; color: var(--text-muted); margin: 0; font-family: var(--font-serif); }
.header-right { display: flex; align-items: center; gap: var(--space-md); }
.provider-select { width: 180px; }
.status-tag {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-family: var(--font-serif);
}
.status-tag.ready { background: var(--success-bg); color: var(--success); }
.status-tag.pending { background: var(--bg-secondary); color: var(--text-muted); }
.status-tag.error { background: var(--danger-bg); color: var(--danger); }

/* ==================== Layout ==================== */
.ocr-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: var(--space-lg);
  padding: var(--space-lg);
  overflow: hidden;
}

.left-panel,
.right-panel {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  padding: var(--space-lg);
  overflow-y: auto;
  box-shadow: var(--shadow-sm);
}

/* ==================== Upload ==================== */
.upload-zone {
  border: 2px dashed var(--border-medium);
  border-radius: var(--radius-lg);
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: var(--transition-fast);
  position: relative;
  overflow: hidden;
}
.upload-zone:hover { border-color: var(--accent); background: var(--accent-bg); }
.upload-zone.dragging { border-color: var(--accent); background: var(--accent-bg); transform: scale(1.01); }
.upload-zone.hasImage { border-style: solid; padding: 0; }
.upload-empty { text-align: center; padding: var(--space-lg); color: var(--text-muted); }
.upload-icon { color: var(--accent); margin-bottom: var(--space-sm); }
.upload-title { font-size: 15px; margin: 0 0 4px; color: var(--text-secondary); font-family: var(--font-serif); }
.upload-hint { font-size: 12px; margin: 0; color: var(--text-muted); }
.upload-preview { position: relative; width: 100%; height: 100%; min-height: 240px; }
.upload-preview img { width: 100%; height: 100%; object-fit: contain; background: var(--bg-secondary); }
.preview-clear {
  position: absolute; top: 8px; right: 8px;
  width: 28px; height: 28px;
  background: rgba(0,0,0,0.6);
  color: white; border: none; border-radius: var(--radius-sm);
  cursor: pointer; display: flex; align-items: center; justify-content: center;
}
.preview-clear:hover { background: var(--danger); }

.btn-recognize {
  width: 100%;
  margin-top: var(--space-md);
  padding: 12px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-family: var(--font-serif);
  cursor: pointer;
  transition: var(--transition-fast);
}
.btn-recognize:hover:not(:disabled) { background: var(--accent-light); }
.btn-recognize:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-content { display: flex; align-items: center; justify-content: center; gap: 8px; }

.spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ==================== Samples ==================== */
.samples-section { margin-top: var(--space-lg); }
.section-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin: 0 0 var(--space-sm);
  font-family: var(--font-display);
  letter-spacing: 0.05em;
}
.samples-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-sm);
}
.sample-thumb {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
  cursor: pointer;
  background: var(--bg-secondary);
  transition: var(--transition-fast);
}
.sample-thumb:hover { border-color: var(--accent); transform: translateY(-1px); }
.sample-thumb.active { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-bg); }
.sample-thumb img { width: 100%; aspect-ratio: 1; object-fit: cover; display: block; }
.sample-meta {
  padding: 4px 6px;
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.sample-name { font-size: 10px; color: var(--text-secondary); font-family: var(--font-mono); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.sample-size { font-size: 9px; color: var(--text-muted); }

/* ==================== Right Panel ==================== */
.right-panel { display: flex; flex-direction: column; gap: var(--space-md); }
.error-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px var(--space-md);
  background: var(--danger-bg);
  color: var(--danger);
  border-radius: var(--radius-md);
  font-size: 13px;
}
.error-banner button { background: none; border: none; color: inherit; font-size: 18px; cursor: pointer; }

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  text-align: center;
  gap: var(--space-sm);
}
.empty-icon { color: var(--accent); opacity: 0.3; }
.empty-state h3 { font-size: 16px; font-weight: 400; margin: 0; font-family: var(--font-display); color: var(--text-secondary); }
.empty-state p { font-size: 13px; margin: 0; font-family: var(--font-serif); }

.result-content { display: flex; flex-direction: column; gap: var(--space-md); }
.result-stats {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-sm);
  padding: var(--space-md);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}
.stat-item {
  flex: 1;
  min-width: 100px;
  text-align: center;
  padding: 6px;
}
.stat-label { display: block; font-size: 11px; color: var(--text-muted); font-family: var(--font-serif); }
.stat-value { display: block; font-size: 20px; font-weight: 500; color: var(--text-primary); font-family: var(--font-mono); margin-top: 2px; }
.stat-value.highlight { color: var(--accent); }

.result-text, .variant-detail { display: flex; flex-direction: column; gap: var(--space-sm); }
.result-title { font-size: 14px; font-weight: 500; color: var(--text-primary); margin: 0; font-family: var(--font-display); letter-spacing: 0.05em; }
.text-block {
  background: var(--bg-secondary);
  padding: var(--space-md);
  border-radius: var(--radius-md);
  font-family: var(--font-serif);
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-wrap: break-word;
  max-height: 360px;
  overflow-y: auto;
  margin: 0;
}

.variant-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.variant-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--accent);
  border-radius: var(--radius-sm);
  font-size: 12px;
}
.char-original { color: var(--accent); font-weight: 600; font-family: var(--font-display); }
.char-arrow { color: var(--text-muted); font-size: 10px; }
.char-standard { color: var(--text-primary); font-family: var(--font-display); }
.badge-taboo {
  background: var(--warning);
  color: white;
  padding: 1px 5px;
  border-radius: var(--radius-full);
  font-size: 9px;
  margin-left: 4px;
}

.action-bar {
  display: flex;
  gap: var(--space-sm);
  margin-top: var(--space-sm);
}
.btn-action {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: var(--transition-fast);
  font-family: var(--font-serif);
}
.btn-action:hover:not(:disabled) { transform: translateY(-1px); }
.btn-action:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-rag:hover:not(:disabled) { border-color: var(--secondary); color: var(--secondary); background: var(--secondary-bg); }
.btn-kg:hover:not(:disabled) { border-color: var(--warning); color: var(--warning); background: var(--warning-bg); }

/* ==================== Dialog ==================== */
.dialog-loading { display: flex; align-items: center; justify-content: center; gap: 10px; padding: var(--space-xl); color: var(--text-muted); }
.dialog-summary { font-size: 13px; color: var(--text-secondary); margin: 0 0 var(--space-md); font-family: var(--font-serif); }
.dialog-section { font-size: 13px; font-weight: 500; color: var(--text-primary); margin: var(--space-md) 0 var(--space-sm); }
.entity-list, .relation-list { display: flex; flex-direction: column; gap: 6px; max-height: 280px; overflow-y: auto; }
.entity-checkbox, .relation-checkbox { margin: 0; }
.entity-name { font-weight: 500; margin-right: 6px; }
.entity-tag { font-size: 11px; padding: 1px 6px; background: var(--accent-bg); color: var(--accent); border-radius: var(--radius-full); margin-right: 4px; }
.entity-meta { font-size: 11px; color: var(--text-muted); margin-left: 4px; }

/* ==================== Responsive ==================== */
@media (max-width: 1024px) {
  .ocr-layout { grid-template-columns: 1fr; }
  .left-panel { max-height: 400px; }
}

/* ==================== OCR Disabled Banner ==================== */
.ocr-disabled-banner {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 70vh;
  padding: 60px 40px;
  text-align: center;
  background: var(--card-bg);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-md);
  margin: 40px auto;
  max-width: 640px;
}

.ocr-disabled-banner .banner-icon {
  color: var(--text-muted);
  margin-bottom: 24px;
  opacity: 0.6;
}

.ocr-disabled-banner .banner-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px;
  font-family: var(--font-serif);
}

.ocr-disabled-banner .banner-message {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-secondary);
  margin: 0 0 12px;
  max-width: 480px;
}

.ocr-disabled-banner .banner-message code {
  background: var(--bg-tertiary);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--accent);
}

.ocr-disabled-banner .banner-hint {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 28px;
}

.ocr-disabled-banner .banner-actions {
  display: flex;
  gap: 12px;
}
</style>
