/**
 * 志鉴系统常量配置
 */

// 8大核心模块定义
export const MODULES = [
  {
    id: 1,
    name: '古籍OCR识别',
    icon: 'Document',
    path: '/collation',
    status: 'completed',
    color: '#409EFF',
    description: 'PaddleOCR PP-OCRv4 + EasyOCR双引擎，支持异体字、避讳字检测',
    features: ['多引擎OCR识别', '异体字规范化', '避讳字检测', '置信度评估'],
    technologies: ['PaddleOCR 2.7.3', 'EasyOCR 1.7.2', 'OpenCV图像处理']
  },
  {
    id: 2,
    name: '文本规范化',
    icon: 'Edit',
    path: '/collation',
    status: 'completed',
    color: '#67C23A',
    description: '繁简转换、NER实体识别，保护专有名词不被错误转换',
    features: ['繁简转换', 'NER实体识别', '实体保留机制', '多地区变体'],
    technologies: ['OpenCC', 'BERT NER', 'bert-base-chinese']
  },
  {
    id: 3,
    name: '多版本智能校勘',
    icon: 'Connection',
    path: '/collation',
    status: 'completed',
    color: '#E6A23C',
    description: 'BERT语义对齐 + Needleman-Wunsch动态规划，自动发现并分类版本差异',
    features: ['古籍分章分句', 'BERT语义编码', '句子对齐', '裁判规则'],
    technologies: ['BERT语义编码', 'Needleman-Wunsch', '规则引擎']
  },
  {
    id: 4,
    name: '多源辑佚与实体消解',
    icon: 'Merge',
    path: '/compilation',
    status: 'completed',
    color: '#909399',
    description: '多源古籍辑佚，实体跨版本消解与融合',
    features: ['实体特征提取', '多维相似度', '并查集聚类', '版本排序'],
    technologies: ['TF-IDF', '编辑距离', '并查集算法']
  },
  {
    id: 5,
    name: '舆图信息提取',
    icon: 'MapLocation',
    path: '/map',
    status: 'completed',
    color: '#F56C6C',
    description: '从古籍舆图中提取地理要素（河流、山脉、城市、边界线）',
    features: ['U-Net语义分割', '要素矢量化', 'OCR标注识别', '坐标映射'],
    technologies: ['U-Net', 'GeoJSON', 'OCR', 'GIS']
  },
  {
    id: 6,
    name: '批校痕迹提取',
    icon: 'Brush',
    path: '/annotation',
    status: 'completed',
    color: '#9B59B6',
    description: '检测并提取古籍上的批校痕迹（朱批、墨批、圈点、划线）',
    features: ['Faster R-CNN检测', '颜色分类', '位置推断', '文本对齐'],
    technologies: ['Faster R-CNN', '颜色检测', 'HSV空间']
  },
  {
    id: 7,
    name: '知识图谱',
    icon: 'NetworkChart',
    path: '/knowledge',
    status: 'completed',
    color: '#3498DB',
    description: 'Neo4j图数据库 + Milvus向量库，人物关系可视化',
    features: ['人物节点', '关系网络', '向量检索', '校勘存储'],
    technologies: ['Neo4j 5.12', 'Milvus 2.3.4', 'Cypher']
  },
  {
    id: 8,
    name: 'RAG智能问答',
    icon: 'ChatDotRound',
    path: '/qa',
    status: 'completed',
    color: '#1ABC9C',
    description: '向量检索 + BM25混合搜索 + LLM生成，精准回答古籍问题',
    features: ['混合检索', 'RRF融合', '上下文构建', 'LLM生成'],
    technologies: ['BGE向量化', 'BM25', 'DeepSeek/Kimi']
  }
]

// 技术栈定义
export const TECH_STACK = {
  backend: [
    { name: 'FastAPI', version: '0.109.0', category: '框架' },
    { name: 'Python', version: '3.10', category: '语言' },
    { name: 'PaddleOCR', version: '2.7.3', category: 'OCR' },
    { name: 'EasyOCR', version: '1.7.2', category: 'OCR' },
    { name: 'PyTorch', version: '2.1.2', category: '深度学习' },
    { name: 'BERT', version: 'bert-base-chinese', category: 'NLP' },
    { name: 'OpenCC', version: '0.1.7', category: '文本处理' }
  ],
  database: [
    { name: 'Neo4j', version: '5.12', category: '图数据库' },
    { name: 'Milvus', version: '2.3.4', category: '向量库' }
  ],
  frontend: [
    { name: 'Vue 3', version: '3.x', category: '框架' },
    { name: 'Vite', version: '5.x', category: '构建' },
    { name: 'Element Plus', version: '2.5.x', category: 'UI组件' },
    { name: 'ECharts', version: '5.5.x', category: '图表' }
  ],
  infra: [
    { name: 'Docker Compose', version: '-', category: '容器化' },
    { name: 'MinIO', version: 'latest', category: '对象存储' },
    { name: 'etcd', version: 'v3.5.5', category: '元数据' }
  ]
}

// 数据版本定义
export const GAZETTEER_VERSIONS = [
  {
    id: 'kangxi',
    name: '固安县志（康熙）',
    year: 1672,
    dynasty: '清',
    pdfCount: 17,
    status: 'pending',
    description: '康熙十一年版，17个PDF，纯扫描图像'
  },
  {
    id: 'xianfeng',
    name: '固安县志（咸丰）',
    year: 1851,
    dynasty: '清',
    pdfCount: 16,
    status: 'partial',
    description: '咸丰年间版，16个PDF，部分完成OCR'
  },
  {
    id: '1998',
    name: '固安县志（98年版）',
    year: 1998,
    dynasty: '现代',
    pdfCount: 29,
    status: 'completed',
    characterCount: 974139,
    description: '1998年编修版，29个PDF，已提取97万字符'
  },
  {
    id: 'minguo',
    name: '固安县志（民国）',
    year: 1940,
    dynasty: '民国',
    pdfCount: 1,
    status: 'pending',
    description: '民国版，1个PDF，待处理'
  },
  {
    id: 'gugong',
    name: '固安县志（故宫博物院藏）',
    year: null,
    dynasty: '清',
    pdfCount: 1,
    status: 'pending',
    description: '故宫博物院藏本，待处理'
  }
]

// 差异类型定义
export const DIFF_TYPES = {
  insertion: {
    label: '增文',
    color: '#67C23A',
    tagType: 'success',
    description: '版本B中有而版本A中无的内容'
  },
  deletion: {
    label: '删文',
    color: '#F56C6C',
    tagType: 'danger',
    description: '版本A中有而版本B中无的内容'
  },
  substitution: {
    label: '替换',
    color: '#E6A23C',
    tagType: 'warning',
    description: '两个版本中字词不同'
  },
  variant: {
    label: '异体',
    color: '#909399',
    tagType: 'info',
    description: '异体字差异'
  },
  taboo: {
    label: '避讳',
    color: '#9B59B6',
    tagType: '',
    description: '避讳字差异'
  },
  transposition: {
    label: '颠倒',
    color: '#3498DB',
    tagType: '',
    description: '字序颠倒'
  }
}

// 示例问题
export const EXAMPLE_QUESTIONS = [
  '固安县志中记载了哪些知州？',
  '康熙年间固安县发生了什么大事？',
  '固安县的人物有哪些著名家族？',
  '固安县的地理环境有什么特点？',
  '固安县志的编纂历史是怎样的？'
]

// 快速开始步骤
export const QUICK_START_STEPS = [
  {
    title: '上传扫描件',
    description: '上传方志古籍PDF或图片',
    icon: 'Upload'
  },
  {
    title: 'OCR识别',
    description: '自动识别文字内容',
    icon: 'Document'
  },
  {
    title: '多版本校勘',
    description: '对比不同版本差异',
    icon: 'Connection'
  },
  {
    title: '知识问答',
    description: '用自然语言提问',
    icon: 'ChatDotRound'
  }
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

export default {
  MODULES,
  TECH_STACK,
  GAZETTEER_VERSIONS,
  DIFF_TYPES,
  EXAMPLE_QUESTIONS,
  QUICK_START_STEPS,
  PROJECT_STATS
}
