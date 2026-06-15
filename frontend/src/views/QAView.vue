<template>
  <div class="qa-view">
    <!-- 顶部栏 -->
    <header class="qa-header">
      <div class="header-left">
        <h1 class="page-title">智能问答</h1>
        <p class="page-subtitle">基于古籍方志知识的智能问答系统</p>
      </div>
      <div class="header-right">
        <span v-if="sources.length > 0" class="source-count">
          {{ sources.length }} 条参考来源
        </span>
        <button v-if="messages.length > 0" class="btn-export" @click="exportChat" title="导出对话为 Markdown">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          导出
        </button>
        <button class="btn-clear" @click="clearChat">清空对话</button>
      </div>
    </header>

    <!-- 主内容 -->
    <div class="qa-layout">
      <!-- 聊天区 -->
      <div class="chat-panel">
        <!-- 消息列表 -->
        <div class="chat-messages" ref="chatContainer">
          <!-- 空状态 -->
          <div v-if="messages.length === 0" class="empty-state">
            <div class="empty-icon">
              <svg width="56" height="56" viewBox="0 0 56 56" fill="none">
                <circle cx="28" cy="28" r="24" stroke="currentColor" stroke-width="1.5" stroke-dasharray="4 3"/>
                <path d="M20 28 Q24 22 28 28 Q32 34 36 28" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>
                <circle cx="22" cy="22" r="2" fill="currentColor" opacity="0.4"/>
                <circle cx="34" cy="22" r="2" fill="currentColor" opacity="0.4"/>
              </svg>
            </div>
            <h3>开始提问</h3>
            <p>可询问固安县历史、人物、地理、职官等</p>
          </div>

          <!-- 消息列表 -->
          <div
            v-for="(msg, index) in messages"
            :key="index"
            :class="['message', msg.role]"
          >
            <div v-if="msg.role === 'assistant'" class="msg-avatar assistant">
              <span>智</span>
            </div>
            <div class="msg-body">
              <div class="msg-content" v-html="renderMarkdown(msg.content, msg.role === 'assistant' ? lastQuestion : '')"></div>
              <div class="msg-meta">
                <span class="msg-time">{{ msg.time }}</span>
                <button v-if="msg.role === 'user'" class="btn-copy" @click="copyMessage(msg.content)" title="复制">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                    <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>

          <!-- 加载状态 -->
          <div v-if="loading" class="message assistant">
            <div class="msg-avatar assistant">
              <span>智</span>
            </div>
            <div class="msg-body">
              <div class="msg-loading">
                <span class="load-dot"></span>
                <span class="load-dot"></span>
                <span class="load-dot"></span>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="input-area">
          <div class="input-wrapper">
            <textarea
              ref="inputRef"
              v-model="question"
              placeholder="输入问题，Enter 发送，Shift+Enter 换行"
              @keydown.enter.exact.prevent="handleEnterKey"
              @keydown.enter.shift="handleShiftEnter"
              :disabled="loading"
              rows="1"
              class="question-input"
            ></textarea>
            <button
              @click="sendQuestion"
              :disabled="loading || !question.trim()"
              class="send-btn"
            >
              <svg v-if="!loading" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="12" y1="19" x2="12" y2="5"/>
                <polyline points="5 12 12 5 19 12"/>
              </svg>
              <span v-else class="spinner"></span>
            </button>
          </div>
        </div>

        <!-- 示例问题 -->
        <div v-if="messages.length === 0" class="example-bar">
          <span class="example-label">试试问：</span>
          <button
            v-for="q in exampleQuestions"
            :key="q"
            class="example-btn"
            @click="selectExample(q)"
          >{{ q }}</button>
        </div>
      </div>

      <!-- 右侧面板 -->
      <aside class="side-panel">
        <!-- 参考来源 -->
        <div class="panel-card">
          <div class="panel-header">
            <span class="panel-title">参考来源</span>
            <span v-if="sources.length" class="panel-count">{{ sources.length }}</span>
          </div>
          <div class="ref-list">
            <div v-if="sources.length === 0" class="ref-empty">暂无参考来源</div>
            <div v-for="(source, i) in sources" :key="i" class="ref-item">
              <div class="ref-num">{{ i + 1 }}</div>
              <div class="ref-body">
                <p class="ref-text">{{ source.text }}</p>
                <div class="ref-footer">
                  <span class="ref-source">{{ source.source }}</span>
                  <span class="ref-score">{{ (source.score * 100).toFixed(0) }}%</span>
                </div>
                <div class="ref-bar">
                  <div class="ref-fill" :style="{ width: (source.score * 100) + '%' }"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 知识库状态 -->
        <div class="panel-card">
          <div class="panel-header">
            <span class="panel-title">知识库状态</span>
          </div>
          <div class="kg-body">
            <div class="kg-status-row">
              <span class="kg-dot" :class="currentStatusConfig.statusClass"></span>
              <span class="kg-label">{{ currentStatusConfig.label }}</span>
            </div>
            <div class="kg-info">
              <div class="kg-row">
                <span class="kg-key">文档</span>
                <span class="kg-val">{{ ragCollection?.count || 0 }} 条</span>
              </div>
              <div class="kg-row">
                <span class="kg-key">Embedding</span>
                <span class="kg-val">{{ embedderInfo?.model || '—' }}</span>
              </div>
              <div class="kg-row">
                <span class="kg-key">向量维度</span>
                <span class="kg-val">{{ embeddingDimension || '—' }}</span>
              </div>
              <div class="kg-row">
                <span class="kg-key">检索策略</span>
                <span class="kg-val">BGE+BM25+RRF</span>
              </div>
            </div>
            <button @click="seedKnowledgeBase" :disabled="isInitializing" class="btn-rebuild">
              <svg v-if="!isInitializing" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="23 4 23 10 17 10"/>
                <polyline points="1 20 1 14 7 14"/>
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
              </svg>
              <span v-else class="spinner small"></span>
              {{ isInitializing ? '重建中...' : '重建索引' }}
            </button>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { ragAPI } from '@/services/api'
import { EXAMPLE_QUESTIONS } from '@/constants'

// 状态
const question = ref('')
const loading = ref(false)
const messages = ref([])
const sources = ref([])
const chatContainer = ref(null)
const inputRef = ref(null)
const ragStatus = ref('checking')
const ragCollection = ref(null)
const isInitializing = ref(false)
const embedderInfo = ref(null)
const embeddingDimension = ref(null)
const exampleQuestions = ref(EXAMPLE_QUESTIONS)
const lastQuestion = ref('')

const ragStatusConfig = {
  ready: { statusClass: 'ready', label: '已就绪' },
  checking: { statusClass: 'checking', label: '检查中' },
  error: { statusClass: 'error', label: '需重建' },
  unavailable: { statusClass: 'unavailable', label: '未连接' }
}

const currentStatusConfig = computed(() =>
  ragStatusConfig[ragStatus.value] || ragStatusConfig.unavailable
)

onMounted(async () => {
  loadHistory()
  await checkRAGStatus()
  if (messages.value.length === 0) {
    messages.value.push({
      role: 'assistant',
      content: '您好！我是志鉴智能问答助手，可以回答关于固安县历史、人物、地理、职官等方面的问题。\n\n请开始提问。',
      time: formatTime(new Date())
    })
  }
})

async function checkRAGStatus() {
  if (isInitializing.value) return
  try {
    const status = await ragAPI.status()
    const statusMap = {
      'operational': 'ready', 'ready': 'ready',
      'error': 'error', 'checking': 'checking'
    }
    ragStatus.value = statusMap[status.status] || 'unavailable'
    ragCollection.value = status.collections?.[0] || null
    embedderInfo.value = status.embedder || null
    embeddingDimension.value = status.embedding_dimension || null

    if (status.status === 'error' || !ragCollection.value?.exists || ragCollection.value?.count === 0) {
      messages.value.push({
        role: 'assistant',
        content: '知识库尚未建立，正在初始化...',
        time: formatTime(new Date())
      })
      await seedKnowledgeBase()
    }
  } catch (e) {
    ragStatus.value = 'unavailable'
    console.warn('RAG状态检查失败:', e)
  }
}

async function seedKnowledgeBase() {
  if (isInitializing.value) return
  isInitializing.value = true
  try {
    const result = await ragAPI.seed()
    if (result.status === 'success') {
      ragStatus.value = 'ready'
      messages.value.push({
        role: 'assistant',
        content: `知识库已建立完成！\n\n已导入文档 ${result.total_docs} 卷，析为知识碎片 ${result.total_chunks} 条。\n\n请问有什么可以帮您？`,
        time: formatTime(new Date())
      })
    }
  } catch (e) {
    ragStatus.value = 'error'
    console.error('知识库灌入失败:', e)
    messages.value.push({
      role: 'assistant',
      content: `知识库初始化失败。\n\n请确保后台服务已启动：\n\`\`\`\npython -m uvicorn app.main:app --port 8000\n\`\`\``,
      time: formatTime(new Date())
    })
  } finally {
    isInitializing.value = false
  }
}

async function sendQuestion() {
  if (!question.value.trim() || loading.value) return

  const q = question.value.trim()
  messages.value.push({ role: 'user', content: q, time: formatTime(new Date()) })
  lastQuestion.value = q
  question.value = ''
  loading.value = true
  sources.value = []
  autoResize()
  await scrollToBottom()
  saveHistory()

  try {
    const res = await ragAPI.ask(q)
    messages.value.push({
      role: 'assistant',
      content: res.answer || '抱歉，未能回答此问题。',
      time: formatTime(new Date())
    })
    sources.value = res.sources || []
  } catch (error) {
    console.error('RAG问答失败', error)
    messages.value.push({
      role: 'assistant',
      content: `问答服务暂时不可用（${error.message || 'API 请求失败'}）。\n\n请检查：\n1. 后台服务是否已启动\n2. Ollama + Qwen2.5-3B 是否正常运行\n3. Milvus 向量数据库是否在线`,
      time: formatTime(new Date())
    })
    ElMessage.error('问答服务暂时不可用')
  } finally {
    loading.value = false
    saveHistory()
    await scrollToBottom()
    autoResize()
    inputRef.value?.focus()
  }
}

function handleEnterKey() {
  sendQuestion()
}

function handleShiftEnter() {}

function selectExample(q) {
  question.value = q
  sendQuestion()
}

function clearChat() {
  messages.value = [{
    role: 'assistant',
    content: '对话已清空，请开始新提问。',
    time: formatTime(new Date())
  }]
  sources.value = []
  saveHistory()
}

const HISTORY_KEY = 'zhijian_qa_history'
const HISTORY_MAX = 200

function saveHistory() {
  try {
    const trimmed = messages.value.slice(-HISTORY_MAX)
    localStorage.setItem(HISTORY_KEY, JSON.stringify(trimmed))
  } catch (e) {
    console.warn('保存对话历史失败', e)
  }
}

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed) && parsed.length > 0) {
      messages.value = parsed
    }
  } catch (e) {
    console.warn('读取对话历史失败', e)
  }
}

function exportChat() {
  if (messages.value.length === 0) return
  const lines = ['# 志鉴智能问答 - 对话记录', '']
  lines.push(`导出时间：${new Date().toLocaleString('zh-CN')}`)
  lines.push('')
  messages.value.forEach((m, i) => {
    const role = m.role === 'user' ? '🙋 用户' : '🤖 智鉴'
    lines.push(`## ${i + 1}. ${role}　·　${m.time}`)
    lines.push('')
    lines.push(m.content)
    lines.push('')
  })
  if (sources.value.length > 0) {
    lines.push('---')
    lines.push('')
    lines.push('## 参考来源')
    lines.push('')
    sources.value.forEach((s, i) => {
      lines.push(`[${i + 1}] ${s.source}　·　相关度 ${(s.score * 100).toFixed(0)}%`)
      lines.push(`> ${s.text}`)
      lines.push('')
    })
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `志鉴对话-${new Date().toISOString().slice(0, 10)}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  ElMessage.success('对话已导出')
}

async function copyMessage(content) {
  try {
    await navigator.clipboard.writeText(content)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}

async function scrollToBottom() {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

function formatTime(date) {
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function autoResize() {
  nextTick(() => {
    const el = inputRef.value
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
  })
}

function renderMarkdown(text, query = '') {
  if (!text) return ''
  let html = text
  html = html.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  html = html.replace(/```([\s\S]*?)```/g, (_, code) => `<pre class="md-code"><code>${code.trim()}</code></pre>`)
  html = html.replace(/`([^`]+)`/g, '<code class="md-code-inline">$1</code>')
  html = html.replace(/^#{1,6}\s+(.+)$/gm, '<h class="md-h">$1</h>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/^[\-\•]\s+(.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul class="md-list">$&</ul>')
  html = html.replace(/^\d+\.\s+(.+)$/gm, '<li class="md-li-ordered">$1</li>')
  html = html.replace(/^---+$/gm, '<hr class="md-hr">')
  html = html.replace(/\n\n+/g, '</p><p class="md-p">')
  html = html.replace(/\n/g, '<br/>')
  html = `<p class="md-p">${html}</p>`
  html = html.replace(/<p class="md-p"><br\/><\/p>/g, '')

  // 关键词高亮：用提问中的中文词在回答中以黄底标记（最多 8 个关键词，每个 2-6 字）
  if (query) {
    const keywords = extractKeywords(query)
    keywords.forEach((kw) => {
      if (kw.length < 2) return
      const escaped = kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      const re = new RegExp(escaped, 'g')
      html = html.replace(re, (m) => `<mark class="kw-hl">${m}</mark>`)
    })
  }

  return html
}

function extractKeywords(query) {
  if (!query) return []
  // 切出连续中文 2-6 字片段 + 引号内词
  const cn = query.match(/[一-龥]{2,6}/g) || []
  const qm = (query.match(/[「」『』"']([^「」『』"']{2,8})[「」『』"']/g) || [])
    .map(s => s.slice(1, -1))
  const all = [...new Set([...qm, ...cn])]
  return all.slice(0, 8)
}
</script>

<style scoped>
.qa-view {
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
  overflow: hidden;
}

/* ==================== 顶部栏 ==================== */
.qa-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px var(--space-xl);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: var(--space-md);
}

.page-title {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 400;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: 0.1em;
}

.page-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0;
  font-family: var(--font-serif);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-md);
}

.source-count {
  font-size: 12px;
  color: var(--accent);
  padding: 4px 12px;
  background: var(--accent-bg);
  border-radius: var(--radius-full);
  font-family: var(--font-serif);
}

.btn-clear {
  padding: 6px 14px;
  background: transparent;
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: var(--transition-fast);
  font-family: var(--font-serif);
}

.btn-clear:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.btn-export {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: transparent;
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: var(--transition-fast);
  font-family: var(--font-serif);
}

.btn-export:hover {
  border-color: var(--accent);
  color: var(--accent);
}

/* ==================== 主布局 ==================== */
.qa-layout {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: var(--space-lg);
  padding: var(--space-lg);
  overflow: hidden;
}

/* ==================== 聊天面板 ==================== */
.chat-panel {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: var(--shadow-md);
}

/* ==================== 消息列表 ==================== */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

/* 空状态 */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-sm);
  color: var(--text-muted);
  text-align: center;
}

.empty-icon {
  color: var(--accent);
  opacity: 0.4;
  margin-bottom: var(--space-xs);
}

.empty-state h3 {
  font-size: 18px;
  font-weight: 400;
  color: var(--text-secondary);
  margin: 0;
  font-family: var(--font-display);
}

.empty-state p {
  font-size: 14px;
  margin: 0;
  font-family: var(--font-serif);
}

/* 消息 */
.message {
  display: flex;
  gap: var(--space-sm);
  animation: msgIn 0.3s var(--ease-out);
}

@keyframes msgIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message.user {
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 400;
  flex-shrink: 0;
  font-family: var(--font-display);
}

.msg-avatar.assistant {
  background: var(--accent);
  color: var(--text-inverse);
  box-shadow: var(--shadow-sm);
}

.msg-body {
  flex: 1;
  max-width: 72%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.message.user .msg-body {
  align-items: flex-end;
}

.msg-content {
  padding: 14px 18px;
  border-radius: var(--radius-lg);
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
  font-family: var(--font-serif);
}

.message.user .msg-content {
  background: var(--accent-bg);
  color: var(--text-primary);
  border-left: 3px solid var(--accent);
  border-radius: 0 var(--radius-lg) var(--radius-lg) 0;
}

.message.assistant .msg-content {
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-radius: 0 var(--radius-lg) var(--radius-lg) 0;
}

.msg-meta {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 0 4px;
}

.message.user .msg-meta {
  flex-direction: row-reverse;
}

.msg-time {
  font-size: 11px;
  color: var(--text-muted);
}

.btn-copy {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-muted);
  padding: 2px;
  border-radius: var(--radius-sm);
  opacity: 0;
  transition: var(--transition-fast);
}

.message:hover .btn-copy {
  opacity: 1;
}

.btn-copy:hover {
  color: var(--accent);
}

/* 加载 */
.msg-loading {
  display: flex;
  gap: 6px;
  padding: 14px 18px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-radius: 0 var(--radius-lg) var(--radius-lg) 0;
}

.load-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--text-muted);
  animation: dotBounce 1.2s ease-in-out infinite;
}

.load-dot:nth-child(1) { animation-delay: 0s; }
.load-dot:nth-child(2) { animation-delay: 0.15s; }
.load-dot:nth-child(3) { animation-delay: 0.3s; }

@keyframes dotBounce {
  0%, 80%, 100% { transform: scale(0.7); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

.spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  display: inline-block;
}

.spinner.small {
  width: 12px;
  height: 12px;
  border-color: rgba(255,255,255,0.3);
  border-top-color: white;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ==================== 输入区 ==================== */
.input-area {
  padding: var(--space-md);
  background: var(--bg-secondary);
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: var(--space-sm);
  background: var(--bg-card);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-lg);
  padding: 10px 14px;
  transition: var(--transition-fast);
}

.input-wrapper:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-bg);
}

.question-input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-family: var(--font-serif);
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  resize: none;
  overflow-y: auto;
  max-height: 120px;
  min-height: 24px;
}

.question-input::placeholder {
  color: var(--text-muted);
}

.question-input:disabled {
  opacity: 0.6;
}

.send-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: var(--transition-fast);
}

.send-btn:hover:not(:disabled) {
  background: var(--accent-light);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 示例问题 */
.example-bar {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 10px var(--space-md);
  background: var(--bg-card);
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
  overflow-x: auto;
}

.example-label {
  font-size: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
  font-family: var(--font-serif);
}

.example-btn {
  flex-shrink: 0;
  padding: 5px 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-full);
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  white-space: nowrap;
  transition: var(--transition-fast);
  font-family: var(--font-serif);
}

.example-btn:hover {
  background: var(--accent-bg);
  border-color: var(--accent);
  color: var(--accent);
}

/* ==================== 侧边栏 ==================== */
.side-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  overflow-y: auto;
}

.panel-card {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px var(--space-md);
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-light);
}

.panel-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  font-family: var(--font-display);
}

.panel-count {
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  background: var(--accent);
  color: white;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ref-list {
  padding: var(--space-sm);
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  max-height: 260px;
  overflow-y: auto;
}

.ref-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-xl);
  font-size: 13px;
  color: var(--text-muted);
}

.ref-item {
  display: flex;
  gap: var(--space-sm);
  padding: var(--space-sm);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.ref-num {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  background: var(--secondary);
  color: white;
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ref-body {
  flex: 1;
  min-width: 0;
}

.ref-text {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-primary);
  margin: 0 0 4px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-family: var(--font-serif);
}

.ref-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.ref-source {
  font-size: 11px;
  color: var(--text-muted);
}

.ref-score {
  font-size: 11px;
  color: var(--accent);
  font-weight: 600;
}

.ref-bar {
  height: 3px;
  background: var(--border-light);
  border-radius: 2px;
  overflow: hidden;
}

.ref-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 2px;
  transition: width 0.4s ease;
}

/* 知识库状态 */
.kg-body {
  padding: var(--space-md);
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
}

.kg-status-row {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.kg-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.kg-dot.ready { background: var(--success); }
.kg-dot.checking { background: var(--warning); animation: pulse 1.5s infinite; }
.kg-dot.error, .kg-dot.unavailable { background: var(--text-muted); }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.kg-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  font-family: var(--font-serif);
}

.kg-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.kg-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  border-bottom: 1px dashed var(--border-light);
}

.kg-row:last-child {
  border-bottom: none;
}

.kg-key {
  font-size: 12px;
  color: var(--text-muted);
  font-family: var(--font-serif);
}

.kg-val {
  font-size: 12px;
  color: var(--text-primary);
  font-weight: 500;
  font-family: var(--font-mono);
}

.btn-rebuild {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 8px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-md);
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: var(--transition-fast);
  font-family: var(--font-serif);
}

.btn-rebuild:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-bg);
}

.btn-rebuild:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* Markdown */
.msg-content :deep(.md-p) {
  margin: 0 0 6px;
  font-size: 14px;
  line-height: 1.8;
  color: inherit;
}

.msg-content :deep(.md-p:last-child) { margin-bottom: 0; }
.msg-content :deep(.md-h) { font-size: 14px; font-weight: 700; color: var(--text-primary); margin: 0 0 6px; display: block; }
.msg-content :deep(strong) { font-weight: 700; color: inherit; }
.msg-content :deep(em) { font-style: italic; }
.msg-content :deep(.md-list), .msg-content :deep(ul) { margin: 4px 0 6px; padding-left: 18px; list-style: none; }
.msg-content :deep(li), .msg-content :deep(.md-li-ordered) { position: relative; font-size: 14px; margin-bottom: 3px; }
.msg-content :deep(li::before) { content: '·'; position: absolute; left: -12px; color: var(--accent); }
.msg-content :deep(.md-code) { background: var(--bg-secondary); border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 10px 14px; margin: 6px 0; overflow-x: auto; }
.msg-content :deep(.md-code code) { font-family: var(--font-mono); font-size: 13px; color: var(--text-primary); white-space: pre; }
.msg-content :deep(.md-code-inline) { background: var(--bg-secondary); padding: 1px 5px; border-radius: var(--radius-sm); font-family: var(--font-mono); font-size: 13px; color: var(--accent); }
.msg-content :deep(.md-hr) { border: none; border-top: 1px dashed var(--border-medium); margin: 10px 0; }
.message.user .msg-content :deep(.md-code-inline) { background: rgba(181, 74, 50, 0.15); color: var(--accent); }

/* 关键词高亮（仅 assistant 消息） */
.msg-content :deep(mark.kw-hl) {
  background: rgba(229, 193, 88, 0.45);
  color: inherit;
  padding: 0 2px;
  border-radius: 2px;
  font-weight: 500;
}

/* ==================== 响应式 ==================== */
@media (max-width: 1100px) {
  .qa-layout {
    grid-template-columns: 1fr 280px;
  }
}

@media (max-width: 900px) {
  .qa-layout {
    grid-template-columns: 1fr;
    grid-template-rows: 1fr auto;
  }

  .side-panel {
    flex-direction: row;
    overflow-x: auto;
  }

  .panel-card {
    min-width: 280px;
  }
}

@media (max-width: 600px) {
  .qa-header {
    padding: 12px var(--space-md);
    flex-direction: column;
    align-items: flex-start;
    gap: var(--space-sm);
  }

  .qa-layout {
    padding: var(--space-md);
  }

  .msg-body {
    max-width: 85%;
  }
}
</style>
