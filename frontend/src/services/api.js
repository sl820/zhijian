/**
 * 志鉴系统 API 服务层
 * 封装所有后端API调用
 */
import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`)
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器
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

// ==================== OCR 模块 ====================

export const ocrAPI = {
  /**
   * OCR识别
   * @param {File} file - 图片文件
   * @returns {Promise<Object>} OCR结果
   */
  recognize: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post('/ocr/recognize', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  /**
   * 批量OCR识别
   * @param {File[]} files - 文件列表
   * @returns {Promise<Object[]>} OCR结果列表
   */
  recognizeBatch: async (files) => {
    const results = []
    for (const file of files) {
      try {
        const result = await ocrAPI.recognize(file)
        results.push(result)
      } catch (e) {
        console.error(`OCR识别失败: ${file.name}`, e)
      }
    }
    return results
  }
}

// ==================== 文本规范化模块 ====================

export const normalizeAPI = {
  /**
   * 文本规范化
   * @param {string} text - 待规范化文本
   * @param {string} targetForm - 目标形式 ('simplified' | 'traditional')
   * @param {boolean} detectEntities - 是否检测实体
   * @returns {Promise<Object>} 规范化结果
   */
  normalize: (text, targetForm = 'simplified', detectEntities = true) => {
    return apiClient.post('/normalize', {
      text,
      target_form: targetForm,
      detect_entities: detectEntities
    })
  }
}

// ==================== 多版本校勘模块 ====================

export const collationAPI = {
  /**
   * 版本校勘对比（两版本）
   * @param {string} textA - 版本A文本
   * @param {string} textB - 版本B文本
   * @param {Object} metadataA - 版本A元数据
   * @param {Object} metadataB - 版本B元数据
   * @returns {Promise<Object>} 校勘结果
   */
  compare: (textA, textB, metadataA = {}, metadataB = {}) => {
    return apiClient.post('/collation/compare', {
      text_a: textA,
      text_b: textB,
      metadata_a: metadataA,
      metadata_b: metadataB
    })
  },

  /**
   * 上传版本文件（图片或文本）
   * @param {File} file - 文件
   * @param {string} name - 版本名称
   * @param {Object} metadata - 版本元数据
   * @returns {Promise<Object>} 上传结果
   */
  uploadVersion: (file, name, metadata = {}) => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', name)
    formData.append('metadata', JSON.stringify(metadata))
    return apiClient.post('/collation/versions/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  /**
   * 列出所有已保存的版本
   * @returns {Promise<Object>} 版本列表
   */
  listVersions: () => {
    return apiClient.get('/collation/versions')
  },

  /**
   * 获取指定版本的内容
   * @param {string} versionId - 版本ID
   * @returns {Promise<Object>} 版本详情
   */
  getVersion: (versionId) => {
    return apiClient.get(`/collation/versions/${versionId}`)
  },

  /**
   * 删除指定版本
   * @param {string} versionId - 版本ID
   * @returns {Promise<Object>} 删除结果
   */
  deleteVersion: (versionId) => {
    return apiClient.delete(`/collation/versions/${versionId}`)
  },

  /**
   * 对图片版本重新OCR识别
   * @param {string} versionId - 版本ID
   * @returns {Promise<Object>} OCR结果
   */
  reocrVersion: (versionId) => {
    return apiClient.post(`/collation/versions/${versionId}/ocr`)
  },

  /**
   * 多版本比较（2-4个版本）
   * @param {string[]} versionIds - 版本ID列表
   * @param {string[]} texts - 或直接传文本列表
   * @param {Object[]} metadataList - 元数据列表
   * @returns {Promise<Object>} 校勘结果
   */
  compareMulti: (versionIds = null, texts = null, metadataList = []) => {
    return apiClient.post('/collation/compare-multi', {
      version_ids: versionIds,
      texts: texts,
      metadata: metadataList
    })
  }
}

// ==================== RAG 问答模块 ====================

export const ragAPI = {
  /**
   * 问答
   * @param {string} question - 问题
   * @param {number} topK - 返回结果数
   * @returns {Promise<Object>} 问答结果
   */
  ask: (question, topK = 5) => {
    return apiClient.post('/rag/ask', { question, top_k: topK })
  },

  /**
   * 摄入文档
   * @param {string} text - 文档文本
   * @param {string} title - 标题
   * @param {string} chapterTitle - 章节标题
   * @param {Object} metadata - 元数据
   * @returns {Promise<Object>} 摄入结果
   */
  ingest: (text, title, chapterTitle = '', metadata = {}) => {
    return apiClient.post('/rag/ingest', {
      text,
      title,
      chapter_title: chapterTitle,
      metadata
    })
  },

  /**
   * 从文本目录灌入数据
   * @param {string} dataDir - 数据目录（相对于项目根目录）
   * @param {string} collection - Collection 名称
   * @param {boolean} rebuild - 是否重建
   * @returns {Promise<Object>} 灌入结果
   */
  seed: (dataDir = 'data/raw/1998', collection = 'gazetteer_chunks', rebuild = true) => {
    return apiClient.post('/rag/seed', null, {
      params: { data_dir: dataDir, collection, rebuild }
    })
  },

  /**
   * 获取 RAG 系统状态
   * @returns {Promise<Object>} 状态信息
   */
  status: () => {
    return apiClient.get('/rag/status')
  }
}

// ==================== 舆图提取模块 ====================

export const mapAPI = {
  /**
   * 舆图要素提取
   * @param {Object} options - 选项
   * @param {string|File} options.imagePath - 图像路径（服务器路径）或File对象
   * @param {boolean} options.performOcr - 是否执行OCR
   * @param {boolean} options.georeference - 是否地理配准
   * @param {Array} options.referencePoints - 参考点 [[px, py, lon, lat], ...]
   * @returns {Promise<Object>} 提取结果
   */
  extract: ({ imagePath = '', performOcr = true, georeference = false, referencePoints = [] } = {}) => {
    // If imagePath is a File object, send as FormData
    if (imagePath instanceof File) {
      const formData = new FormData()
      formData.append('file', imagePath)
      formData.append('perform_ocr', String(performOcr))
      formData.append('georeference', String(georeference))
      formData.append('reference_points', JSON.stringify(referencePoints))
      return apiClient.post('/map/extract', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    }
    // Otherwise send as JSON
    return apiClient.post('/map/extract', {
      image_path: imagePath,
      perform_ocr: performOcr,
      georeference,
      reference_points: referencePoints
    })
  }
}

// ==================== 批校提取模块 ====================

export const annotationAPI = {
  /**
   * 批校痕迹提取
   * @param {string|File} imagePath - 图像路径或File对象
   * @param {Array} textBlocks - 文本块
   * @param {boolean} performOcr - 是否执行OCR
   * @returns {Promise<Object>} 提取结果
   */
  extract: (imagePath, textBlocks = [], performOcr = true) => {
    // If imagePath is a File object, send as FormData
    if (imagePath instanceof File) {
      const formData = new FormData()
      formData.append('file', imagePath)
      formData.append('text_blocks', JSON.stringify(textBlocks))
      formData.append('perform_ocr', String(performOcr))
      return apiClient.post('/annotation/extract', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    }
    // Otherwise send as JSON with image_path
    return apiClient.post('/annotation/extract', {
      image_path: imagePath,
      text_blocks: textBlocks,
      perform_ocr: performOcr
    })
  }
}

// ==================== 知识图谱模块 ====================

export const kgAPI = {
  /**
   * 存储校勘结果到图谱
   * @param {Object} collationResult - 校勘结果
   * @returns {Promise<Object>} 存储结果
   */
  storeCollationResult: (collationResult) => {
    return apiClient.post('/kg/collation-result', collationResult)
  },

  /**
   * 获取 KG 系统状态
   * @returns {Promise<Object>} 状态信息
   */
  status: () => {
    return apiClient.get('/kg/status')
  },

  /**
   * 获取所有人物列表
   * @param {number} limit - 数量限制
   * @returns {Promise<Object>} 人物列表
   */
  listPersons: (limit = 200) => {
    return apiClient.get('/kg/persons', { params: { limit } })
  },

  /**
   * 获取单个人物详情
   * @param {string} name - 人物名称
   * @returns {Promise<Object>} 人物详情
   */
  getPerson: (name) => {
    return apiClient.get(`/kg/persons/${encodeURIComponent(name)}`)
  },

  /**
   * 获取图谱可视化数据
   * @param {number} limit - 数量限制
   * @returns {Promise<Object>} 图谱数据
   */
  getGraph: (limit = 200) => {
    return apiClient.get('/kg/graph', { params: { limit } })
  },

  /**
   * 初始化知识图谱（从人物志文本）
   * @param {boolean} clear - 是否清除已有数据
   * @param {boolean} background - 是否后台运行
   * @returns {Promise<Object>} 初始化结果
   */
  initKG: (clear = false, background = false) => {
    return apiClient.post('/kg/init', null, { params: { clear, background } })
  },

  /**
   * 获取 KG 初始化状态
   * @returns {Promise<Object>} 状态信息
   */
  getKGInitStatus: () => {
    return apiClient.get('/kg/init/status')
  }
}

// ==================== 辑佚模块 ====================

export const compilationAPI = {
  /**
   * 多源辑佚编译（完整流程）
   * @param {Array} sources - 来源配置
   * @param {boolean} deduplicate - 是否去重
   * @param {string} mergeStrategy - 融合策略
   * @returns {Promise<Object>} 编译结果
   */
  compile: (sources, deduplicate = true, mergeStrategy = 'prefer_complete') => {
    return apiClient.post('/compilation/compile', {
      sources,
      deduplicate,
      merge_strategy: mergeStrategy
    })
  },

  /**
   * 只做去重
   * @param {Array} sources - 来源配置
   * @param {number} threshold - 相似度阈值
   * @param {string} method - 去重算法 (minhash/simhash)
   * @returns {Promise<Object>} 去重结果
   */
  deduplicate: (sources, threshold = 0.85, method = 'minhash') => {
    return apiClient.post('/compilation/deduplicate', {
      sources,
      threshold,
      method
    })
  },

  /**
   * 只做融合
   * @param {Array} texts - 文本列表
   * @param {Array} metadata - 元数据列表
   * @param {string} strategy - 融合策略
   * @returns {Promise<Object>} 融合结果
   */
  merge: (texts, metadata = [], strategy = 'prefer_complete') => {
    return apiClient.post('/compilation/merge', {
      texts,
      metadata,
      strategy
    })
  },

  /**
   * 解析 PDF 文件，提取文本
   * @param {File} file - PDF 文件
   * @returns {Promise<Object>} 解析结果
   */
  parsePDF: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiClient.post('/compilation/parse-pdf', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}

export default {
  health: healthAPI,
  ocr: ocrAPI,
  normalize: normalizeAPI,
  collation: collationAPI,
  rag: ragAPI,
  map: mapAPI,
  annotation: annotationAPI,
  kg: kgAPI,
  compilation: compilationAPI
}
