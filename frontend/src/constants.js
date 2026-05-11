/**
 * 志鉴系统常量配置
 */

// 8大核心模块配置
export const MODULES = [
  {
    id: 'ocr',
    name: 'OCR识别',
    description: '古籍扫描件文字识别，支持繁简中文、多字体混排',
    icon: 'Reading',
    color: '#c94043',
    path: '/collation',
    status: 'completed',
    features: ['PaddleOCR', '繁简识别', '多语言'],
    technologies: ['PaddlePaddle', 'DeepLearning']
  },
  {
    id: 'normalize',
    name: '文本规范化',
    description: '繁简转换、异体字统一、文本清洗标准化',
    icon: 'Edit',
    color: '#4a9d6e',
    path: '/collation',
    status: 'completed',
    features: ['繁简转换', '异体字', '文本清洗'],
    technologies: ['OpenCC', '字典映射']
  },
  {
    id: 'collation',
    name: '多版本校勘',
    description: '多版本语义对齐，差异自动标注与融合',
    icon: 'Connection',
    color: '#d4a853',
    path: '/collation',
    status: 'completed',
    features: ['语义对齐', '差异检测', '智能融合'],
    technologies: ['Transformer', '编辑距离']
  },
  {
    id: 'map',
    name: '舆图提取',
    description: '古地图要素分割与矢量化，支持地理配准',
    icon: 'MapLocation',
    color: '#5b8def',
    path: '/map',
    status: 'completed',
    features: ['U-Net分割', '地理配准', 'GeoJSON导出'],
    technologies: ['PyTorch', 'Segmentation', 'OpenCV']
  },
  {
    id: 'annotation',
    name: '批校提取',
    description: '古籍批校痕迹检测与文字识别',
    icon: 'EditPen',
    color: '#9b59b6',
    path: '/collation',
    status: 'in_progress',
    features: ['痕迹检测', 'OCR识别'],
    technologies: ['图像处理', 'PaddleOCR']
  },
  {
    id: 'kg',
    name: '知识图谱',
    description: '实体关系抽取，构建方志知识网络',
    icon: 'DataAnalysis',
    color: '#e67e22',
    path: '/knowledge',
    status: 'completed',
    features: ['NER', '关系抽取', 'Neo4j存储'],
    technologies: ['Neo4j', 'LLM']
  },
  {
    id: 'rag',
    name: 'RAG问答',
    description: '基于检索增强生成的智能问答系统',
    icon: 'ChatDotRound',
    color: '#1abc9c',
    path: '/qa',
    status: 'completed',
    features: ['向量检索', '上下文理解', '答案生成'],
    technologies: ['ChromaDB', 'Embedding', 'LLM']
  },
  {
    id: 'compilation',
    name: '多源辑佚',
    description: '多源文献辑佚编译，去重与融合',
    icon: 'Document',
    color: '#34495e',
    path: '/collation',
    status: 'in_progress',
    features: ['多源收集', '去重', '融合编译'],
    technologies: ['MinHash', '文本相似度']
  }
]

// 技术栈配置
export const TECH_STACK = {
  backend: [
    { name: 'FastAPI', version: '0.109+'},
    { name: 'PyTorch', version: '2.0+'},
    { name: 'PaddleOCR', version: '2.7+'},
    { name: 'Transformers', version: '4.37+'}
  ],
  database: [
    { name: 'Neo4j', version: '5.x'},
    { name: 'ChromaDB', version: '0.4+'},
    { name: 'PostgreSQL', version: '15+'}
  ],
  frontend: [
    { name: 'Vue3', version: '3.4+'},
    { name: 'Element Plus', version: '2.5+'},
    { name: 'ECharts', version: '5.5+'},
    { name: 'Vite', version: '5.0+'}
  ],
  infra: [
    { name: 'Docker', version: '24+'},
    { name: 'Python', version: '3.10+'},
    { name: 'CUDA', version: '12.x'}
  ]
}

// 固安县志版本数据
export const GAZETTEER_VERSIONS = [
  {
    id: 'kangxi',
    name: '康熙版',
    year: '1673',
    description: '固安县志最早版本，清康熙九年编纂',
    characterCount: 185000,
    status: 'completed'
  },
  {
    id: 'qianlong',
    name: '乾隆版',
    year: '1742',
    description: '乾隆七年重修，内容较康熙版丰富',
    characterCount: 243000,
    status: 'completed'
  },
  {
    id: 'jiaqing',
    name: '嘉庆版',
    year: '1800',
    description: '嘉庆五年补刊，史料价值极高',
    characterCount: 198000,
    status: 'partial'
  },
  {
    id: 'guangxu',
    name: '光绪版',
    year: '1875',
    description: '光绪年间最后一次大规模修订',
    characterCount: 267000,
    status: 'completed'
  },
  {
    id: 'minguo',
    name: '民国版',
    year: '1933',
    description: '民国二十二年铅印本，近现代留存',
    characterCount: 210000,
    status: 'partial'
  }
]

// 差异类型定义
export const DIFF_TYPES = {
  deletion: { label: '删减', color: '#c94043', tagType: 'danger' },
  insertion: { label: '增补', color: '#4a9d6e', tagType: 'success' },
  substitution: { label: '替换', color: '#c9943a', tagType: 'warning' },
  variant: { label: '异体', color: '#4a7ab8', tagType: 'info' },
  move: { label: '移动', color: '#8b6b4a', tagType: '' },
  format: { label: '格式', color: '#7b6b8a', tagType: 'info' }
}

// 示例问题
export const EXAMPLE_QUESTIONS = [
  '固安县志中记载了哪些知州？',
  '康熙年间固安县发生了什么大事？',
  '固安县的人物有哪些著名家族？',
  '固安县的地理环境有什么特点？',
  '固安县志的编纂历史是怎样的？'
]

// 项目统计
export const PROJECT_STATS = {
  totalVersions: 5,
  totalCharacters: 974139,
  totalPDFs: 64,
  moduleCount: 8,
  completedModules: 4,
  pendingModules: 4
}

// 快速开始步骤
export const QUICK_START_STEPS = [
  {
    title: '上传古籍',
    description: '上传扫描件或照片，支持PDF/图片格式',
    icon: 'Upload'
  },
  {
    title: 'OCR识别',
    description: '自动识别古籍文字，输出结构化文本',
    icon: 'Reading'
  },
  {
    title: '版本校勘',
    description: '选择多版本进行语义对齐与差异分析',
    icon: 'Connection'
  },
  {
    title: '导出成果',
    description: '导出校勘结果、知识图谱或问答知识库',
    icon: 'Download'
  }
]
