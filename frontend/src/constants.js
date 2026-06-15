/**
 * 志鉴系统常量配置
 * 精简版：OCR + KG + RAG 三大模块
 */

export const MODULES = [
  {
    id: 'ocr',
    name: 'OCR 古籍识别',
    description: '上传古籍扫描件，自动识别文字、检测异体字与清代避讳字，支持批量处理与样本图',
    icon: 'Document',
    color: '#9b59b6',
    path: '/ocr',
    status: 'completed',
    features: ['RapidOCR · AliyunOCR', '1000+ 异体字', '避讳字检测', '竖排古籍旋转'],
    technologies: ['RapidOCR · ONNX', 'EasyOCR 兜底', 'OpenCV 预处理', '阿里云 · 可选']
  },
  {
    id: 'kg',
    name: '知识图谱',
    description: '从方志文本中抽取人物实体与家族关系，构建可探索的知识网络',
    icon: 'DataAnalysis',
    color: '#e67e22',
    path: '/knowledge',
    status: 'completed',
    features: ['NER 实体抽取', '家族关系识别', '力导向可视化'],
    technologies: ['正则 + LLM 抽取', '纯内存存储', 'ECharts']
  },
  {
    id: 'rag',
    name: 'RAG 智能问答',
    description: '基于方志原文的检索增强问答，支持自然语言提问与原文片段引用',
    icon: 'ChatDotRound',
    color: '#1abc9c',
    path: '/qa',
    status: 'completed',
    features: ['向量检索', 'BM25 关键词', 'RRF 融合', 'LLM 生成'],
    technologies: ['ChromaDB', 'sentence-transformers', 'Qwen2.5-3B']
  }
]

// 技术栈配置
export const TECH_STACK = {
  backend: [
    { name: 'FastAPI', version: '0.109+'},
    { name: 'Python', version: '3.10+'},
    { name: 'Pydantic', version: 'v2'}
  ],
  ocr: [
    { name: 'RapidOCR', version: 'ONNX 默认'},
    { name: 'AliyunOCR', version: '云端·古籍增强'},
    { name: 'EasyOCR', version: '1.7+ 兜底'},
    { name: 'OpenCV', version: '4.9+ 预处理'},
    { name: '异体字表', version: '1000+ 收录'}
  ],
  rag: [
    { name: 'ChromaDB', version: '0.4+'},
    { name: 'sentence-transformers', version: 'paraphrase-multilingual'},
    { name: 'Ollama', version: '0.20+'},
    { name: 'Qwen2.5', version: '3B 本地'}
  ],
  kg: [
    { name: '存储', version: 'in-memory + JSON'},
    { name: '实体识别', version: '正则 + 字典'},
    { name: '关系抽取', version: 'LLM 辅助 + 规则后处理'}
  ],
  frontend: [
    { name: 'Vue 3', version: '3.4+'},
    { name: 'Element Plus', version: '2.5+'},
    { name: 'ECharts', version: '5.5+'},
    { name: 'Vite', version: '5.0+'}
  ]
}

// 示例问题
export const EXAMPLE_QUESTIONS = [
  '固安县的地理位置在哪里？',
  '张知州是哪里人？',
  '固安县志中记载了哪些知州？',
  '康熙年间固安县发生过什么大事？',
  '固安县的人物有哪些著名家族？'
]

// 项目统计
export const PROJECT_STATS = {
  totalCorpusFiles: 26,
  totalCharacters: 974139,
  moduleCount: 3,
  completedModules: 3
}

export const QUICK_START_STEPS = [
  {
    title: 'OCR 古籍识别',
    description: '上传扫描件，自动识别文字与异体字',
    icon: 'Document'
  },
  {
    title: '知识图谱',
    description: '从方志「人物志」抽取人物与家族关系，构建可视化图谱',
    icon: 'DataAnalysis'
  },
  {
    title: '智能问答',
    description: '用自然语言提问，系统从原文检索并由大模型生成准确答案',
    icon: 'ChatDotRound'
  }
]
