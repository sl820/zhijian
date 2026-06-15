/**
 * OCR 模块状态管理
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ocrAPI } from '@/services/api'

export const useOcrStore = defineStore('ocr', () => {
  // ==================== 状态 ====================

  const currentImage = ref(null)
  const currentFile = ref(null)
  const result = ref(null)
  const loading = ref(false)
  const error = ref(null)

  const variants = ref([])
  const totalVariants = ref(0)
  const totalTabooRules = ref(0)

  const samples = ref([])
  const provider = ref('easyocr')
  const ocrStatus = ref(null)

  // 联动 RAG/KG 流程
  const previewEntities = ref([])
  const previewRelations = ref([])
  const previewing = ref(false)

  // ==================== Actions ====================

  async function fetchStatus() {
    try {
      ocrStatus.value = await ocrAPI.status()
    } catch (e) {
      ocrStatus.value = { status: 'error', error: e.message }
    }
  }

  async function fetchVariants() {
    try {
      const res = await ocrAPI.variants()
      variants.value = res.sample || []
      totalVariants.value = res.total_variants || 0
      totalTabooRules.value = res.total_taboo_rules || 0
    } catch (e) {
      console.error('fetchVariants failed', e)
    }
  }

  async function fetchSamples() {
    try {
      const res = await ocrAPI.samples()
      samples.value = res.samples || []
    } catch (e) {
      console.error('fetchSamples failed', e)
    }
  }

  async function recognize(file, providerOverride = null) {
    loading.value = true
    error.value = null
    const useProvider = providerOverride || provider.value
    try {
      const data = await ocrAPI.recognize(file, useProvider)
      result.value = data
      currentFile.value = file
      return data
    } catch (e) {
      error.value = e.response?.data?.detail || e.message || '识别失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function recognizeFromUrl(sample) {
    loading.value = true
    error.value = null
    try {
      const blob = await ocrAPI.fetchSample(sample.url)
      const file = new File([blob], sample.name, { type: 'image/png' })
      const dataUrl = await new Promise((resolve) => {
        const reader = new FileReader()
        reader.onload = () => resolve(reader.result)
        reader.readAsDataURL(blob)
      })
      currentImage.value = dataUrl
      const data = await recognize(file)
      return data
    } catch (e) {
      error.value = e.response?.data?.detail || e.message || '识别失败'
      throw e
    } finally {
      loading.value = false
    }
  }

  function setCurrentImage(dataUrl, file = null) {
    currentImage.value = dataUrl
    if (file) currentFile.value = file
  }

  function reset() {
    currentImage.value = null
    currentFile.value = null
    result.value = null
    error.value = null
    previewEntities.value = []
    previewRelations.value = []
  }

  function getFullText() {
    if (!result.value?.pages) return ''
    return result.value.pages
      .map(p => p.text || '')
      .filter(Boolean)
      .join('\n')
  }

  return {
    currentImage,
    currentFile,
    result,
    loading,
    error,
    variants,
    totalVariants,
    totalTabooRules,
    samples,
    provider,
    ocrStatus,
    previewEntities,
    previewRelations,
    previewing,
    fetchStatus,
    fetchVariants,
    fetchSamples,
    recognize,
    recognizeFromUrl,
    setCurrentImage,
    reset,
    getFullText,
  }
})
