/**
 * 志鉴系统 API 服务层
 * 精简版：仅 RAG + KG
 */
import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json'
  }
})

apiClient.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error)
)

apiClient.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.message || error.message || '请求失败'
    console.error(`[API Error] ${message}`)
    return Promise.reject(error)
  }
)

// ==================== 健康检查 ====================

export const healthAPI = {
  check: () => apiClient.get('/health')
}

// ==================== 系统健康 Gate（竞赛交付）====================
// 启动时拉一次 → 决定 SAFE MODE / 节点上限 / OCR 入口可见性
export const systemHealthAPI = {
  check: () => apiClient.get('/system/health')
}

// ==================== R9 研究引擎 / 一键评委包 ====================
export const researchAPI = {
  getInsights: () => apiClient.get('/research/insights'),
  getInsight: (kind) => apiClient.get(`/research/insights/${kind}`),
  getPersonNarrative: (uri) => apiClient.get(`/research/person/${encodeURIComponent(uri)}/narrative`),
  getHealth: () => apiClient.get('/research/health'),
}

export const demoAPI = {
  getJuryPack: () => apiClient.get('/demo/jury_pack'),
  getSystemSummary: () => apiClient.get('/demo/system_summary'),
}

// ==================== OCR 古籍识别模块 ====================

export const ocrAPI = {
  status: () => apiClient.get('/ocr/status'),

  providers: () => apiClient.get('/ocr/providers'),

  variants: (limit = 100) => apiClient.get('/ocr/variants', { params: { limit } }),

  samples: () => apiClient.get('/ocr/samples'),

  recognize: (file, provider = 'easyocr', detectVariants = true, detectTaboo = true) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post('/ocr/recognize', formData, {
      params: { provider, detect_variants: detectVariants, detect_taboo: detectTaboo },
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    })
  },

  batch: (files, provider = 'easyocr') => {
    const formData = new FormData()
    files.forEach((f) => formData.append('files', f))
    return apiClient.post('/ocr/batch', formData, {
      params: { provider },
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 600000,
    })
  },

  fetchSample: (url) => apiClient.get(url.replace(/^\/api\/v1/, ''), { responseType: 'blob' }),
}

// ==================== RAG 问答模块 ====================

export const ragAPI = {
  ask: (question, topK = 5) => {
    return apiClient.post('/rag/ask', { question, top_k: topK })
  },

  ingest: (text, title, chapterTitle = '', metadata = {}) => {
    return apiClient.post('/rag/ingest', {
      text,
      title,
      chapter_title: chapterTitle,
      metadata
    })
  },

  seed: (dataDir = 'data/raw/1998', collection = 'gazetteer_chunks', rebuild = true) => {
    return apiClient.post('/rag/seed', null, {
      params: { data_dir: dataDir, collection, rebuild }
    })
  },

  status: () => apiClient.get('/rag/status')
}

// ==================== 知识图谱模块 ====================

export const kgAPI = {
  status: () => apiClient.get('/kg/status'),

  listPersons: (limit = 200) => {
    return apiClient.get('/kg/persons', { params: { limit } })
  },

  getPerson: (name) => {
    return apiClient.get(`/kg/persons/${encodeURIComponent(name)}`)
  },

  getGraph: (limit = 200, source = null) => {
    return apiClient.get('/kg/graph', { params: { limit, source } })
  },

  initKG: (clear = false, background = false) => {
    return apiClient.post('/kg/init', null, { params: { clear, background } })
  },

  getKGInitStatus: () => apiClient.get('/kg/init/status'),

  extract: (text, source = 'OCR', title = '') => {
    return apiClient.post('/kg/entity/extract', { text, source, title })
  },

  // 星云图谱（M6）
  getLayout: (source = 'jiapu', bbox = null, limit = 500, offset = 0, filters = {}) => {
    return apiClient.get('/kg/layout', { params: { source, bbox, limit, offset, ...filters } })
  },

  getLayoutMetadata: (source = 'jiapu') => {
    return apiClient.get('/kg/layout/metadata', { params: { source } })
  },

  listSources: () => apiClient.get('/kg/sources'),

  // 详情面板（M7）
  getSubgraph: (uri, source = 'jiapu', hops = 2, maxNodes = 80) => {
    return apiClient.get(`/kg/person/${encodeURIComponent(uri)}/subgraph`, {
      params: { source, hops, max_nodes: maxNodes },
    })
  },

  getEvidence: (uri, name = null) => {
    return apiClient.get(`/kg/person/${encodeURIComponent(uri)}/evidence`, {
      params: name ? { name } : {},
    })
  },

  personRAG: (uri, q, name = null, topK = 3) => {
    return apiClient.get(`/kg/person/${encodeURIComponent(uri)}/rag`, {
      params: { q, name, top_k: topK },
    })
  },
}

export default {
  health: healthAPI,
  systemHealth: systemHealthAPI,
  research: researchAPI,
  demo: demoAPI,
  rag: ragAPI,
  kg: kgAPI
}
