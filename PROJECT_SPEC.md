# 「志鉴」古籍方志智能化整理与知识服务平台

## 完整技术规格文档 v1.0

**文档版本**: v1.0
**编制日期**: 2026-04-02
**项目状态**: 精简版（OCR + KG + RAG 三大模块）

> **精简版说明**：本项目当前实现的是 **OCR 古籍识别、知识图谱、RAG 智能问答** 三大核心模块。原始规划的 8 大模块中，文本规范化、多版本校勘、多源辑佚、舆图提取、批校提取 5 个模块**当前不实施**（详见 `git log` 历史提交）。本规格文档保留原始 8 模块的设计供参考，但实际交付以三大模块为准。

---

## 目录

1. [项目概述](#1-项目概述)
2. [技术架构总览](#2-技术架构总览)
3. [三大核心模块详解](#3-三大核心模块详解)
4. [项目目录结构](#4-项目目录结构)
5. [API路由规范](#5-api路由规范)
6. [数据库设计](#6-数据库设计)
7. [前端架构](#7-前端架构)
8. [数据资源](#8-数据资源)
9. [核心算法详解](#9-核心算法详解)
10. [开发进度与规划](#10-开发进度与规划)
11. [部署指南](#11-部署指南)
12. [技术依赖清单](#12-技术依赖清单)

---

## 1. 项目概述

### 1.1 项目背景与问题

中国地方志是中国特有的文献类型，全国现存地方志超过8000余种，是研究中国古代至近现代地方历史、社会、经济、文化的第一手资料。然而：

- **90%以上**尚未完成数字化整理
- 传统人工校勘一部地方志需要 **3-5年** 时间
- 古籍专业性强，需要领域专家参与
- 多版本差异比对着依赖人工逐一比对，效率极低

### 1.2 解决方案

「志鉴」系统通过AI技术，将传统人工校勘3-5年的工作时间压缩到**数天**。系统实现了：

- 古籍扫描件的自动OCR识别
- 多版本方志的智能比对与差异检测
- 繁简/异体字/避讳字的自动规范化
- 基于知识图谱的人物关系挖掘
- RAG智能问答

### 1.3 项目定位

| 维度 | 内容 |
|------|------|
| 项目名称 | 志鉴（Zhijian） |
| 核心定位 | 古籍方志智能化整理与知识服务平台 |
| 目标用户 | 古籍研究者、地方志编纂机构、高校文史院系 |
| 应用场景 | 多版本方志校勘、古籍数字化、历史文化研究辅助 |
| 竞赛赛道 | 2026年中国大学生计算机设计大赛·人工智能应用（实践赛）|

### 1.4 核心技术指标

| 指标 | 数值 | 说明 |
|------|------|------|
| OCR识别速度 | ~10秒/页 | CPU模式，GPU可加速 |
| 单次校勘字符数 | ~25,000字 | 端到端处理 |
| 校勘总耗时 | ~269秒 | 含BERT语义编码 |
| BERT编码占比 | 96.6% | 主要性能瓶颈 |
| 已提取数据量 | 974,139字符 | 98年版固安县志 |
| 支持版本数 | 5个 | 康熙/咸丰/98年/民国/故宫 |

---

## 2. 技术架构总览

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              前端展示层 (Vue3)                              │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  ┌──────────┐           │
│  │ 首页     │  │ 校勘界面     │  │ 知识图谱      │  │ 智能问答 │           │
│  │ HomeView │  │CollationView│  │KnowledgeView  │  │ QAView   │           │
│  └──────────┘  └──────────────┘  └───────────────┘  └──────────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            API服务层 (FastAPI)                              │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐ ┌───────┐ ┌───────────┐  │
│  │ /ocr    │ │/normalize│ │/collation│ │/rag  │ │/map   │ │/compilation│ │
│  └─────────┘ └──────────┘ └──────────┘ └──────┘ └───────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
┌─────────────────────────────────────────────────────────────────────────────┐
│                            核心业务逻辑层                                   │
│  ┌─────────┐ ┌───────────┐ ┌───────────┐ ┌─────────┐ ┌────────────────┐  │
│  │ OCR模块 │ │ 规范化模块 │ │ 校勘模块  │ │ RAG模块 │ │ 知识图谱模块   │  │
│  │         │ │           │ │(核心模块)  │ │         │ │                │  │
│  │ ·预处理器│ │·繁简转换  │ │·分词器   │ │·检索器  │ │·Neo4j客户端   │  │
│  │ ·识别器  │ │·NER模型   │ │·对齐器   │ │·生成器  │ │·Milvus客户端  │  │
│  │ ·变体字  │ │           │ │·差异检测 │ │·混合检索│ │                │  │
│  └─────────┘ └───────────┘ └───────────┘ └─────────┘ └────────────────┘  │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐                   │
│  │ 舆图提取模块    │ │ 批校模块       │ │ 辑佚模块       │                   │
│  │ ·U-Net分割    │ │ ·Faster R-CNN │ │ ·版本排序      │                   │
│  │ ·矢量化       │ │ ·颜色分类     │ │ ·去重融合      │                   │
│  └────────────────┘ └────────────────┘ └────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              数据持久化层                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                  │
│  │ Neo4j 图数据库  │  │ Milvus 向量库  │  │  文件系统(本地) │                  │
│  │ ·人物关系图谱   │  │ ·语义向量检索  │  │ ·古籍PDF/图片   │                  │
│  │ ·版本关系图谱   │  │ ·混合检索     │  │ ·处理结果JSON  │                  │
│  └────────────────┘  └────────────────┘  └────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据处理流水线

```
古籍扫描件(PDF)
     │
     ▼
┌─────────────┐
│ PyMuPDF     │──── 可提取文字层？ ──── Yes ──► 直接提取文本
│ 文本提取     │
└─────────────┘
     │ No
     ▼
┌─────────────┐
│ PDF → 图像   │
│ (300 DPI)   │
└─────────────┘
     │
     ▼
┌─────────────┐
│ 图像预处理   │
│ ·去噪       │
│ ·倾斜校正   │
│ ·对比度增强 │
└─────────────┘
     │
     ▼
┌─────────────┐
│ OCR识别     │
│ ·PaddleOCR  │──── Python 3.13 不兼容 ──► EasyOCR 备用
│ ·PP-OCRv4  │
└─────────────┘
     │
     ▼
┌─────────────┐
│ 异体字规范化 │
│ ·变体字映射 │
│ ·避讳字检测 │
└─────────────┘
     │
     ▼
┌─────────────┐
│ 文本规范化   │
│ ·繁简转换   │
│ ·NER识别   │
└─────────────┘
     │
     ▼
┌─────────────┐
│ 多版本校勘   │
│ ·分章分句   │
│ ·BERT编码   │
│ ·语义对齐   │
│ ·差异检测   │
│ ·裁判判断   │
└─────────────┘
     │
     ▼
┌─────────────┐
│ 知识图谱    │
│ ·Neo4j存储 │
│ ·Milvus索引│
└─────────────┘
     │
     ▼
┌─────────────┐
│ RAG问答     │
│ ·向量检索   │
│ ·LLM生成   │
└─────────────┘
```

### 2.3 技术栈汇总

| 层次 | 技术选型 | 版本 | 说明 |
|------|---------|------|------|
| **后端框架** | FastAPI | 0.109.0 | 高性能异步API框架 |
| **运行时** | Python | 3.10/3.13 | 主力3.10，3.13存在兼容问题 |
| **OCR引擎** | PaddleOCR | 2.7.3 | PP-OCRv4，支持自定义训练 |
| **OCR备用** | EasyOCR | 1.7.2 | Python 3.13兼容 |
| **深度学习** | PyTorch | 2.1.2 | 主力框架 |
| **NLP模型** | BERT | bert-base-chinese | 语义编码与NER |
| **向量化** | BGE | bge-base-chinese-v1.5 | RAG文本嵌入 |
| **图数据库** | Neo4j | 5.12 | 人物关系图谱 |
| **向量库** | Milvus | 2.3.4 | 语义检索 |
| **繁简转换** | OpenCC | 0.1.7 | 支持多种中文变体 |
| **前端框架** | Vue3 | 3.x | 组合式API |
| **前端构建** | Vite | - | 快速构建工具 |
| **UI组件库** | Element Plus | - | Vue3组件库 |
| **图表库** | ECharts | - | 知识图谱可视化 |
| **容器化** | Docker Compose | - | 一键部署 |

---

## 3. 三大核心模块详解

> 精简版仅实现 OCR、知识图谱、RAG 三大模块。第 3.2-3.6 节（文本规范化、校勘、辑佚、舆图、批校）的设计文档作为历史参考保留，实际代码仓库中**不包含**这些模块。

### 3.1 模块①：古籍OCR识别 ✅

#### 模块概述

对古籍扫描件（PDF或图片）进行文字识别，支持图像预处理、异体字规范化、避讳字检测。

#### 文件结构

```
app/ocr/
├── __init__.py
├── processor.py      # OCR主处理器（301行）
├── recognizer.py     # EasyOCR识别器（363行）
├── preprocess.py     # 图像预处理（248行）
└── variant_map.py    # 异体字/避讳字映射（~2000行）
```

#### 核心类与接口

**ImagePreprocessor（图像预处理器）**

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `__init__` | `config: dict` | - | 初始化，`target_dpi=300`, `max_dimension=4096` |
| `load_image` | `image_path: str` | `np.ndarray` | 加载图像为RGB数组 |
| `preprocess` | `image: np.ndarray` | `np.ndarray` | 完整预处理流程 |
| `detect_skew_angle` | `binary_image: np.ndarray` | `float` | Hough变换检测倾斜 |
| `deskew` | `binary_image: np.ndarray, angle: float` | `np.ndarray` | 旋转校正 |
| `detect_text_regions` | `binary_image: np.ndarray` | `List[Tuple]` | 轮廓检测文本区域 |
| `remove_borders` | `binary_image: np.ndarray, border_size: int` | `np.ndarray` | 去除边框 |
| `enhance_contrast` | `gray_image: np.ndarray` | `np.ndarray` | CLAHE对比度增强 |

**预处理流程**：
1. 按需resize（max_dimension=4096）
2. BGR→灰度转换
3. 中值滤波去噪（kernel=5）
4. 自适应高斯二值化（blockSize=11, C=2）
5. 可选：倾斜校正、边框去除

**AncientBookOCR（古籍识别器）**

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `lang` | `str` | `ch_sim` | 语言代码 |
| `gpu` | `bool` | `False` | 是否使用GPU |
| `languages` | `List[str]` | `['ch_sim','en']` | 完整语言列表 |

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `__init__` | `use_angle_cls, lang, gpu` | - | 初始化 |
| `_get_reader` | - | `easyocr.Reader` | 懒加载EasyOCR |
| `recognize` | `image: np.ndarray` | `List[Dict]` | 识别单图 |
| `recognize_batch` | `images: List[np.ndarray]` | `List[List[Dict]]` | 批量识别 |

**OCRProcessor（OCR主处理器）**

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `process_image` | `image_path, detect_variants, detect_taboo, dynasty` | `Dict` | 处理单张图像 |
| `process_pdf` | `pdf_path, start_page, end_page` | `Dict` | 处理PDF |

#### 异体字映射（variant_map.py）

**VARIANT_CHAR_MAP**：包含1000+异体字映射对

```python
# 示例映射
{
  "吴": {"吳", "呉"},           # 吴的异体字
  "考": {"攷", "𣲾", "𠂉", "耂"}, # 考的异体字
  "迹": {"跡", "蹟"},           # 迹的异体字
  "並": {"并", "竝"},           # 並的异体字
}
```

**TABOO_RULES**：朝代避讳规则

```python
# 清代避讳示例
"康熙": {
    "玄": ["元", "眩", "玁"],  # 玄烨→元烨
    "燁": ["爆", "煜"],        # 避免康熙名
}
"雍正": {
    "胤": ["引", "印"],        # 雍正名允禛
}
"乾隆": {
    "弘": ["宏", "洪"],        # 乾隆名弘历
    "曆": ["历", "厤"},        # 避免乾隆名
}
```

#### API接口

```http
POST /api/v1/ocr/recognize
Content-Type: multipart/form-data

file: <图片文件>

Response:
{
  "doc_id": "uuid-string",
  "pages": [{
    "page_num": 1,
    "text": "识别文本...",
    "ocr_confidence": 0.85,
    "variant_count": 12,
    "taboo_count": 2,
    "chars": [{
      "char": "吴",
      "bbox": [x1,y1,x2,y2],
      "is_variant": true,
      "variant_of": "吳",
      "is_taboo": false
    }]
  }]
}
```

#### 当前问题与优化方向

| 问题 | 严重度 | 原因 | 解决方案 |
|------|--------|------|----------|
| OCR识别率极低 | 🔴高 | 竖排文字/手写体/墨迹淡化 | 训练专用古籍OCR模型 |
| OCR速度慢 | 🟡中 | CPU模式~10秒/页 | GPU加速部署 |
| PaddleOCR崩溃 | 🔴高 | Python 3.13 PIR不兼容 | 已用EasyOCR绕过 |

---

### 3.2 模块②：文本规范化 ✅

#### 模块概述

对OCR识别后的文本进行繁简转换、异体字规范化、NER实体识别，保护专有名词不被错误转换。

#### 文件结构

```
app/normalize/
├── __init__.py
├── normalizer.py      # 规范化主处理器（176行）
├── opencc_utils.py    # OpenCC繁简转换（176行）
└── ner_model.py       # BERT NER模型（163行）
```

#### 核心类与接口

**TextNormalizer（繁简转换器）**

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `__init__` | `config: dict` | - | 初始化OpenCC转换器 |
| `traditional_to_simplified` | `text: str` | `str` | 繁体→简体 |
| `simplified_to_traditional` | `text: str, variant: str` | `str` | 简体→繁体（可选台湾/香港变体）|
| `normalize_variants` | `text: str, target: str` | `str` | 异体字标准化 |
| `full_normalize` | `text: str, target_form, preserve_entities` | `str` | 完整规范化流程 |

**OpenCC配置支持**：

| 模式 | 说明 |
|------|------|
| `t2s` | 繁体→简体 |
| `s2t` | 简体→繁体 |
| `s2tw` | 简体→台湾繁体 |
| `s2hk` | 简体→香港繁体 |

**NERModel（命名实体识别模型）**

**NER标签体系**：

| 标签 | 说明 | 示例 |
|------|------|------|
| `B-PER` / `I-PER` | 人名 | 张知州、李氏 |
| `B-LOC` / `I-LOC` | 地名 | 固安县、霸州 |
| `B-TIME` / `I-TIME` | 时间 | 康熙八年、乾隆年间 |
| `B-ORG` / `I-ORG` | 机构名 | 县衙、学宫 |
| `B-WORK` / `I-WORK` | 著作名 | 《固安县志》 |

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `__init__` | `model_path, device` | - | 初始化，默认`bert-base-chinese` |
| `predict` | `text: str` | `List[Dict]` | 预测实体 |
| `batch_predict` | `texts: List[str]` | `List[List[Dict]]` | 批量预测 |

**NormalizationProcessor（规范化主处理器）**

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `__init__` | `config: dict` | - | 初始化 |
| `process` | `text: str, detect_entities: bool` | `Dict` | 规范化处理 |

#### API接口

```http
POST /api/v1/normalize
Content-Type: application/json

{
  "text": "吳氏者，固安人也。康熙八年任知州...",
  "target_form": "simplified",
  "detect_entities": true
}

Response:
{
  "text_original": "吳氏者，固安人也。康熙八年任知州...",
  "text_normalized": "吴氏者，固安人也。康熙八年任知州...",
  "entities": [
    {"type": "PER", "name": "吴氏", "start": 0, "end": 2},
    {"type": "LOC", "name": "固安", "start": 5, "end": 7},
    {"type": "TIME", "name": "康熙八年", "start": 9, "end": 14}
  ]
}
```

---

### 3.3 模块③：多版本智能校勘 ✅ 核心模块

#### 模块概述

对同一古籍的多版本进行语义对齐与差异检测，是整个系统的核心模块。

#### 文件结构

```
app/collation/
├── __init__.py
├── processor.py      # 校勘主处理器（147行）
├── tokenizer.py      # 古籍分词器（183行）
├── aligner.py        # BERT语义对齐器（209行）
├── differ.py         # 差异检测器（197行）
└── judge.py          # 校勘裁判规则（143行）
```

#### 核心类与接口

**TextTokenizer（古籍分词器）**

**章节标题正则模式**：

```python
CHAPTER_PATTERNS = [
    r"^(卷[零一二三四五六七八九十百\d]+)",      # 卷一, 卷二十, 卷一百零八
    r"^([上中下篇章节][\u4e00-\u9fa5]*)",      # 上卷, 第一节
    r"^([\u4e00-\u9fa5]{2,4}[志传记表])",      # 人物志, 列传, 本纪
    r"^([\u4e00-\u9fa5]{2,6}第[一二三四五]+)",
    r"^(【[^】]+】)",                          # 【概述】, 【凡例】
]
```

**句读分隔符**：`[。！？；]` + 换行符

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `split_chapters` | `text: str` | `List[Dict]` | 按标题模式分割章节 |
| `split_sentences` | `text: str` | `List[Dict]` | 按句读分割句子 |
| `extract_metadata` | `text: str` | `Dict` | 提取标题/版本/年代/地区 |

**split_chapters返回格式**：

```python
{
  "title": "卷一",           # 章节标题
  "content": "序一 序二...",  # 章节内容
  "start_pos": 0,
  "end_pos": 1024,
  "level": 0,               # 匹配的模式索引
  "title_type": "卷[零一二...]" # 匹配的模式
}
```

**SemanticAligner（语义对齐器）**

| 属性 | 类型 | 说明 |
|------|------|------|
| `device` | `str` | `cuda`或`cpu` |
| `tokenizer` | `BertTokenizer` | BERT分词器 |
| `model` | `BertModel` | BERT模型 |

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `__init__` | `model_name, device` | - | 加载BERT `bert-base-chinese` |
| `encode_sentences` | `sentences: List[str]` | `np.ndarray` | BERT [CLS]向量编码 |
| `cosine_similarity_matrix` | `embeddings_a, embeddings_b` | `np.ndarray` | 余弦相似度矩阵 |
| `needleman_wunsch` | `sim_matrix, gap_penalty, match_bonus, mismatch_penalty` | `list` | NW全局对齐 |
| `constrained_align` | `sentences_a, sentences_b, similarity_threshold` | `Dict` | 约束对齐 |

**Needleman-Wunsch算法参数**：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `gap_penalty` | -0.5 | 空位惩罚 |
| `match_bonus` | 1.0 | 匹配奖励 |
| `mismatch_penalty` | -0.5 | 不匹配惩罚 |
| `similarity_threshold` | 0.7 | 约束对齐阈值 |

**TextDiffer（差异检测器）**

**差异类型枚举（DiffType）**：

| 类型 | 说明 | 示例 |
|------|------|------|
| `INSERTION` | 插入（B中有A中无） | A:"古稀" vs B:"古稀有 |
| `DELETION` | 删除（A中有B中无） | A:"咸丰" vs B:"" |
| `SUBSTITUTION` | 替换 | A:"知州" vs B:"知府" |
| `VARIANT` | 异体字差异 | A:"并" vs B:"並" |
| `TABOO` | 避讳字差异 | A:"玄" vs B:"元"（康熙避讳）|
| `TRANSPOSITION` | 字序颠倒 | A:"乾隆" vs B:"雍乾" |

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `detect_diffs` | `sentences_a, sentences_b, alignments` | `List[Dict]` | 检测差异 |
| `_analyze_replacement` | `text_a, text_b` | `Dict` | 分析替换类型 |
| `_is_transposition` | `text_a, text_b` | `bool` | 检测字序颠倒 |
| `_check_taboo` | `text_a, text_b` | `bool` | 检测避讳 |
| `_check_variant` | `text_a, text_b` | `bool` | 检测异体字 |
| `_get_char_diffs` | `text_a, text_b` | `List[Dict]` | 字符级差异 |

**CollactionJudge（校勘裁判）**

**裁判规则枚举（JudgmentRule）**：

| 规则 | 优先级 | 说明 |
|------|--------|------|
| `TABOO_FIRST` | 1 | 避讳字优先还原 |
| `CHRONOLOGY` | 2 | 年代早者优先 |
| `GRAPHIC_SIM` | 3 | 字形相似优先 |
| `CONTEXT_SCORE` | 4 | 上下文评分 |

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `judge` | `diff: dict, context: dict` | `dict` | 判断单个差异 |
| `batch_judge` | `diffs: list, context: dict` | `list` | 批量判断 |

**裁判判断逻辑**：

```
1. 如果是避讳字差异 → 还原原字（confidence=0.9）
2. 如果是异体字差异 → 优选较短版本（confidence=0.85）
3. 如果有年代信息 → 优选较早版本（confidence=0.75）
4. 其他 → 字形相似度判断（confidence=0.3）
```

**CollationProcessor（校勘主处理器）**

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `process` | `text_a, text_b, metadata_a, metadata_b, output_path` | `Dict` | 完整校勘流程 |

**处理流程**：

```
1. 章节分割 (tokenizer.split_chapters)
   ↓
2. 句子分割 (tokenizer.split_sentences)
   ↓
3. BERT语义编码 (aligner.encode_sentences)
   ↓
4. 句子对齐 (aligner.constrained_align)
   ↓
5. 差异检测 (differ.detect_diffs)
   ↓
6. 批量判断 (batch_judge)
   ↓
7. 结果汇总
```

#### 性能指标（实验数据）

| 指标 | 数值 | 说明 |
|------|------|------|
| 测试数据 | 第一编政区建置 vs 第二编自然环境 | 98年版 |
| BERT语义编码耗时 | ~260秒 | 553句，CPU模式 |
| 校勘总耗时 | ~269秒 | 端到端 |
| 句子数（版本A） | 553句 | 政区建置 |
| 句子数（版本B） | 85句 | 自然环境 |
| 对齐分数 | -0.3133 | Needleman-Wunsch |
| 差异检测总数 | 587处 | - |

**差异类型分布**：

| 类型 | 数量 | 占比 |
|------|------|------|
| 删除（DELETION） | 502 | 85.5% |
| 替换（SUBSTITUTION） | 51 | 8.7% |
| 插入（INSERTION） | 34 | 5.8% |

**替换差异样例**：

| 位置 | 版本A | 版本B | 差异说明 |
|------|-------|-------|----------|
| pos_a=65 | 民（共）和 | 层，有， | 竖排误识+标点 |
| pos_a=66 | 战国 | 部有 | 字形相似误识 |
| pos_a=118 | 第 | 岩 | 上下文误识 |

#### API接口

```http
POST /api/v1/collation/compare
Content-Type: application/json

{
  "text_a": "卷一 序一 序二 旧序...",
  "text_b": "卷一 舆地志...",
  "metadata_a": {"title": "固安县志(咸丰)", "year": 1851},
  "metadata_b": {"title": "固安县志(康熙)", "year": 1672}
}

Response:
{
  "alignment_score": -0.3133,
  "diffs": [
    {
      "type": "substitution",
      "position_a": 65,
      "position_b": 65,
      "text_a": "民（共）和",
      "text_b": "层，有，",
      "char_diffs": [
        {"position": 0, "char_a": "民", "char_b": "层"},
        {"position": 1, "char_a": "共", "char_b": "，"}
      ],
      "judgment_result": {
        "preferred_version": "A",
        "judgment": "字形相似误识，建议采用A",
        "confidence": 0.3,
        "rule_used": "GRAPHIC_SIM"
      }
    }
  ],
  "summary": {
    "total_diffs": 587,
    "by_type": {
      "deletion": 502,
      "substitution": 51,
      "insertion": 34
    }
  }
}
```

---

### 3.4 模块④：多源辑佚与实体消解 ✅

#### 模块概述

多源古籍辑佚，实体跨版本消解与融合。

#### 文件结构

```
app/entity_resolution/
├── __init__.py
├── resolver.py           # 实体消解器（475行）
├── citation_analyzer.py   # 引文分析
└── merger.py             # 实体融合
```

#### 核心类与接口

**EntityResolver（实体消解器）**

**相似度权重配置**：

```python
DEFAULT_WEIGHTS = {
    "name_weight": 0.3,      # 名称相似度（编辑距离）
    "time_weight": 0.25,     # 时间重叠度
    "location_weight": 0.25, # 地域相似度
    "context_weight": 0.2    # 上下文相似度（TF-IDF）
}
```

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `compute_similarity` | `entity_a, entity_b` | `float` | 综合相似度计算 |
| `resolve_entity_pair` | `entity_a, entity_b` | `dict` | 判断两实体是否同一 |
| `batch_resolve` | `entities, threshold` | `list` | 批量消解 |
| `cluster_entities` | `entities` | `list` | 并查集聚类 |
| `extract_entity_features` | `entity` | `dict` | 提取实体特征向量 |

**相似度计算公式**：

```
similarity = name_weight * name_score
           + time_weight * time_overlap
           + location_weight * location_score
           + context_weight * context_score
```

**判定阈值**：默认`threshold=0.75`

#### 辑佚服务（app/compilation/）

```
app/compilation/
├── __init__.py
├── compilation_service.py # 辑佚服务（284行）
├── scraper.py              # 文本抓取
├── dedup.py                # 去重
├── merger.py               # 版本融合（~300行）
└── ranker.py               # 版本排序（362行）
```

**融合策略枚举（MergeStrategy）**：

| 策略 | 说明 |
|------|------|
| `PREFER_COMPLETE` | 优选完整版本 |
| `PREFER_QUALITY` | 优选高质量版本 |
| `PREFER_ORIGINAL` | 优选原始版本 |
| `VOTE_MERGE` | 投票融合 |
| `STRUCTURAL_MERGE` | 结构化融合 |

**版本评分权重（VersionRanker）**：

```python
DEFAULT_WEIGHTS = {
    "completeness": 0.4,     # 完整度
    "authority": 0.3,        # 权威性
    "age": 0.2,              # 年代
    "ocr_confidence": 0.1    # OCR置信度
}
```

---

### 3.5 模块⑤：舆图信息提取 🔜

#### 模块概述

从古籍舆图（地图）中提取地理要素，包括河流、山脉、城市、边界线等。

#### 文件结构

```
app/map_extraction/
├── __init__.py
├── map_service.py     # 舆图服务（307行）
├── segmenter.py       # U-Net分割器
├── vectorizer.py      # 要素矢量化
├── label_ocr.py       # 地图标注OCR
├── geo_mapper.py      # 地理坐标映射
└── unet_model.py      # U-Net模型定义
```

#### 核心类与接口

**舆图要素类型映射**：

| 类型ID | 要素类型 | 说明 |
|--------|---------|------|
| 0 | 背景 | 空白区域 |
| 1 | 河流 | 水系 |
| 2 | 山脉 | 地貌 |
| 3 | 城市 | 城镇聚落 |
| 4 | 边界线 | 行政区划 |
| 5 | 文字标注 | 地名标注 |

**MapExtractionService（舆图提取服务）**

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `process` | `image_path, perform_ocr, georeference, reference_points` | `Dict` | 端到端处理 |
| `extract_elements_only` | `image_path` | `Dict` | 仅提取要素 |

**处理流程**：

```
1. U-Net语义分割 → 要素类别掩码
2. 要素矢量化 → GeoJSON格式
3. OCR识别标注文字 → 地名-坐标映射
4. 地理坐标映射（可选）→ 像素坐标→地理坐标
```

**GeographicVectorizer（矢量化）**

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `raster_to_vectors` | `mask, element_type` | `List[Dict]` | 栅格转矢量 |
| `compute_polygon_area` | `polygon` | `float` | 计算面积 |
| `simplify_geometry` | `geometry, tolerance` | `Dict` | 简化几何 |

**GeoCoordinateMapper（坐标映射）**

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `pixel_to_geo` | `pixel_x, pixel_y` | `Tuple[float, float]` | 像素→地理坐标 |
| `calibrate` | `reference_points` | - | 校准映射参数 |

#### API接口

```http
POST /api/v1/map/extract
Content-Type: application/json

{
  "image_path": "/data/raw/kangxi_map.png",
  "perform_ocr": true,
  "georeference": false,
  "reference_points": []
}

Response:
{
  "image_path": "/data/raw/kangxi_map.png",
  "elements": {
    "rivers": [
      {"name": "白沟河", "coordinates": [[x1,y1], [x2,y2]], "type": "river"}
    ],
    "mountains": [...],
    "cities": [...],
    "boundaries": [...]
  },
  "text_labels": [
    {"text": "固安", "bbox": [x1,y1,x2,y2], "geo_coords": null}
  ],
  "statistics": {
    "total_elements": 45,
    "by_type": {"river": 12, "mountain": 8, "city": 15, "boundary": 10}
  }
}
```

#### 当前状态

| 状态 | 说明 |
|------|------|
| 🔜 框架代码 | 已完成 |
| ⏳ 模型训练 | 待准备训练数据 |
| ⏳ 实际验证 | 待部署测试 |

---

### 3.6 模块⑥：批校痕迹提取 🔜

#### 模块概述

检测并提取古籍上的批校痕迹，包括朱批、墨批、圈点、划线等。

#### 文件结构

```
app/annotation_extract/
├── __init__.py
├── annotation_service.py # 批校服务（298行）
├── detector.py            # Faster R-CNN检测器（683行）
├── aligner.py             # 批校对齐器（350行）
├── ocr.py                 # 批校OCR
└── faster_rcnn_model.py  # Faster R-CNN模型
```

#### 核心类与接口

**AnnotationDetector（批注检测器）**

**颜色检测**：

| 颜色类型 | HSV范围 | 说明 |
|----------|---------|------|
| 红色（朱批） | H: 0-20 或 340-360, S≥100, V≥50 | 红色墨迹 |
| 墨色（墨批） | 低亮度 | 黑色/深棕色墨迹 |

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `detect` | `image: Union[str, np.ndarray]` | `List[Dict]` | 检测批注 |
| `detect_and_group` | `image, distance_threshold` | `List[Dict]` | 检测并聚类 |

**AnnotationTypeClassifier（批注类型分类器）**

| 批注类型 | 说明 |
|----------|------|
| 朱批 | 红色批注 |
| 墨批 | 墨色批注 |
| 圈点 | 文字圈点标记 |
| 划线 | 删除/强调线 |
| 批注区域 | 大段批注文字 |

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `classify_by_color` | `region, image` | `str` | 基于颜色分类 |
| `classify_by_shape` | `region, image` | `str` | 基于形状分类 |
| `classify` | `region, image, confidence` | `Tuple[str, float]` | 综合分类 |

**AnnotationAligner（批校对齐器）**

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `_compute_iou` | `bbox1, bbox2` | `float` | 计算IoU |
| `_compute_vertical_overlap_ratio` | `annotation_bbox, text_bbox` | `float` | 垂直重叠率 |
| `align_annotation_to_text` | `annotation_bbox, page_layout, text_blocks` | `Optional[Dict]` | 批注-文本对齐 |
| `align_all_annotations` | `annotations, page_image, text_blocks` | `List[Dict]` | 批量对齐 |

**位置类型推断**：

| 类型 | 说明 |
|------|------|
| title | 标题区域 |
| margin | 页边空白 |
| footnote | 脚注区域 |
| inline | 行间批注 |
| unknown | 未识别 |

**AnnotationExtractionService（批校提取服务）**

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `process` | `image_path, text_blocks, perform_ocr` | `Dict` | 端到端处理 |
| `detect_only` | `image_path` | `Dict` | 仅检测 |
| `visualize_result` | `image_path, result, output_path` | `np.ndarray` | 可视化 |

#### API接口

```http
POST /api/v1/annotation/extract
Content-Type: application/json

{
  "image_path": "/data/raw/kangxi_page.png",
  "text_blocks": [{"bbox": [x1,y1,x2,y2], "text": "固安知州..."}],
  "perform_ocr": true
}

Response:
{
  "image_path": "/data/raw/kangxi_page.png",
  "annotations": [
    {
      "bbox": [125, 340, 280, 360],
      "type": "墨批",
      "confidence": 0.92,
      "text": "康熙八年任",
      "aligned_text": "康熙八年任知州",
      "position_type": "margin"
    }
  ],
  "statistics": {
    "total": 5,
    "by_type": {"墨批": 3, "朱批": 1, "圈点": 1}
  }
}
```

---

### 3.7 模块⑦：知识图谱 ✅

#### 模块概述

基于Neo4j构建方志知识图谱，基于Milvus实现向量语义检索。

#### 文件结构

```
app/database/
├── __init__.py
├── neo4j_client.py      # Neo4j客户端（102行）
├── milvus_client.py     # Milvus客户端（70行）
└── kg_service.py        # 知识图谱服务（160行）
```

#### Neo4j数据模型

**节点类型**：

| 节点类型 | 属性 | 说明 |
|----------|------|------|
| `Person` | name, biography, years, birthplace | 人物 |
| `Gazetteer` | title, content_count, year | 方志 |
| `Version` | title, year, dynasty | 版本 |
| `Variation` | id, type, text_a, text_b | 差异 |

**Person节点属性**：

```cypher
(name: string,        // 必填，人名
 biography: string,   // 传记
 years: string,        // 生卒年 "1672-1756"
 birthplace: string,   // 籍贯
 title: string,        // 官职
 dynasty: string,       // 朝代
 source: string,       // 来源方志
 embedding: float[])   // 向量，768维
```

**关系类型**：

| 关系类型 | 起点→终点 | 说明 |
|----------|----------|------|
| `FAMILY_RELATED_TO` | Person→Person | 家族关系 |
| `COLLEAGUE_OF` | Person→Person | 同事关系 |
| `MENTOR_OF` | Person→Person | 师生关系 |
| `CONTAINS_VERSION` | Gazetteer→Version | 包含版本 |
| `COMPARED_WITH` | Version→Version | 版本比较 |
| `HAS_VARIATION` | Version→Variation | 有差异 |
| `VARIATION_OF` | Variation→Version | 差异归属 |

**Neo4jClient接口**：

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `create_person` | `name: str, **properties` | `dict` | 创建人物节点 |
| `create_relation` | `from_name, to_name, relation_type, **properties` | `dict` | 创建关系 |
| `query_person_network` | `name: str, depth: int` | `dict` | 查询人物网络 |
| `create_gazetteer_node` | `title: str, **properties` | `dict` | 创建方志节点 |
| `execute_cypher` | `query: str, **params` | `list` | 执行Cypher查询 |
| `get_all_persons` | - | `list` | 获取所有人 |
| `find_person` | `name: str` | `dict` | 查找人物 |

#### Milvus数据模型

**Collection: persons**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 主键 |
| `vector` | float[768] | BGE嵌入向量 |
| `text` | string | 传记文本 |
| `metadata` | dict | {name, dynasty, ...} |

**Collection: gazetteers**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 主键 |
| `vector` | float[768] | BGE嵌入向量 |
| `text` | string | 方志内容块 |
| `metadata` | dict | {title, chapter, ...} |

**索引配置**：

```python
{
    "index_type": "HNSW",      # 近似最近邻索引
    "metric_type": "IP",        # 内积度量
    "dimension": 768,            # 向量维度
    "M": 16,                    # HNSW参数
    "efConstruction": 200      # HNSW参数
}
```

**MilvusVectorClient接口**：

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `create_collection` | `collection_name: str, dimension: int` | - | 创建collection |
| `insert_vectors` | `collection_name, vectors, texts, metadata` | - | 插入向量 |
| `search` | `collection_name, query_vector, top_k` | `List[Dict]` | 向量搜索 |
| `drop_collection` | `collection_name: str` | - | 删除collection |
| `has_collection` | `collection_name: str` | `bool` | 检查存在 |

#### KnowledgeGraphService接口

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `add_person_with_embedding` | `name, biography_text, embedding, **properties` | - | 添加人物+向量 |
| `add_gazetteer_content` | `gazetteer_title, content_chunks, embeddings` | - | 添加方志内容 |
| `query_person_info` | `name: str` | `dict` | 查询人物信息 |
| `query_related_persons` | `name: str, depth: int` | `list` | 查询关联人物 |
| `semantic_search` | `query_embedding, top_k, person_filter` | `list` | 语义搜索 |
| `store_collation_result` | `source_a, source_b, diffs, alignment_score, metadata` | `dict` | 存储校勘结果 |

---

### 3.8 模块⑧：RAG智能问答 🔜

#### 模块概述

基于古籍内容的RAG（检索增强生成）智能问答。

#### 文件结构

```
app/rag/
├── __init__.py
├── rag_service.py    # RAG服务（255行）
├── chunker.py         # 文本分块器（411行）
├── embedder.py        # BGE向量化（218行）
├── retriever.py       # 混合检索器（443行）
└── generator.py       # LLM生成器（272行）
```

#### 核心类与接口

**Embedder（BGE向量化器）**

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model_name` | `str` | `BAAI/bge-base-chinese-v1.5` | 模型名称 |
| `device` | `str` | `cuda`或`cpu` | 运行设备 |
| `embedding_dim` | `int` | `768` | 向量维度 |

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `encode` | `texts: List[str], batch_size` | `List[List[float]]` | 批量编码 |
| `encode_query` | `query: str` | `List[float]` | 查询编码 |
| `encode_query_batch` | `queries: List[str]` | `List[List[float]]` | 批量查询 |

**TextChunker（文本分块器）**

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `max_tokens` | `int` | `500` | 最大token数 |
| `overlap_tokens` | `int` | `50` | 重叠token数 |

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `chunk_by_chapter` | `text, chapter_title` | `List[Dict]` | 按章节分块 |
| `chunk_by_max_tokens` | `text, chapter_title` | `List[Dict]` | 按最大token分块 |
| `chunk` | `text, strategy, chapter_title` | `List[Dict]` | 主入口 |

**BM25（关键词检索）**

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `fit` | `documents: List[str]` | - | 构建BM25索引 |
| `search` | `query: str, top_k: int` | `List[Dict]` | BM25检索 |

**Retriever（混合检索器）**

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `index_collection_for_bm25` | `collection, texts, metadata` | - | 构建BM25索引 |
| `retrieve` | `query, query_vector, top_k, collection, alpha` | `List[Dict]` | 混合检索 |
| `_reciprocal_rank_fusion` | `vector_results, bm25_results, top_k, alpha` | `List[tuple]` | RRF融合 |

**Reciprocal Rank Fusion (RRF)**：

```python
# alpha=0.5 表示向量检索和BM25各占50%权重
combined_score = alpha * normalized_vector_score + (1-alpha) * normalized_bm25_score
```

**Generator（LLM生成器）**

**支持的LLM提供商**：

```python
PROVIDER_MODELS = {
    "openai": "gpt-4",
    "deepseek": "deepseek-chat",
    "kimi": "moonshot-v1-8k"
}

API_ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/v1/chat/completions",
    "kimi": "https://api.moonshot.cn/v1/chat/completions"
}
```

**环境变量**：`OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `KIMI_API_KEY`

**RAGService（RAG服务）**

| 方法 | 参数 | 返回值 | 功能 |
|------|------|--------|------|
| `ingest_document` | `text, title, chapter_title, metadata` | `Dict` | 摄入文档 |
| `ingest_documents` | `documents: List[Dict]` | `List[Dict]` | 批量摄入 |
| `ask` | `question, top_k, collection` | `Dict` | 问答 |
| `create_collection` | `collection_name, drop_existing` | `str` | 创建collection |

#### 处理流程

```
用户问题
    │
    ▼
查询编码 (Embedder.encode_query)
    │
    ├─► 向量检索 (Milvus) ──► Top-K结果
    │
    └─► BM25检索 ──► Top-K结果
              │
              ▼
      RRF融合算法
              │
              ▼
         Top-K结果
              │
              ▼
      构建提示词上下文
              │
              ▼
      LLM生成答案 (DeepSeek/Kimi/OpenAI)
              │
              ▼
         最终答案
```

#### API接口

```http
POST /api/v1/rag/ingest
Content-Type: application/json

{
  "text": "固安县知州吴氏，康熙八年任...",
  "title": "固安县志(咸丰)",
  "chapter_title": "人物志",
  "metadata": {"year": 1851, "dynasty": "清"}
}

Response:
{
  "status": "success",
  "chunk_count": 5
}

---

POST /api/v1/rag/ask
Content-Type: application/json

{
  "question": "固安县志中记载了哪些知州？",
  "top_k": 5
}

Response:
{
  "answer": "根据《固安县志》记载，康熙八年任知州的有吴氏...",
  "sources": [
    {
      "text": "吴氏者，固安人也。康熙八年任知州...",
      "source": "固安县志(康熙)",
      "score": 0.92
    }
  ]
}
```

---

## 4. 项目目录结构

```
zhijian/
├── app/                              # 主应用目录
│   ├── __init__.py
│   ├── main.py                       # FastAPI入口（67行）
│   │
│   ├── api/                          # API路由
│   │   ├── __init__.py
│   │   └── routes.py                 # API路由定义（459行）
│   │
│   ├── ocr/                          # ①OCR模块
│   │   ├── __init__.py
│   │   ├── processor.py              # OCR处理器（301行）
│   │   ├── recognizer.py             # EasyOCR识别器（363行）
│   │   ├── preprocess.py             # 图像预处理（248行）
│   │   └── variant_map.py            # 异体字/避讳字映射（~2000行）
│   │
│   ├── normalize/                    # ②规范化模块
│   │   ├── __init__.py
│   │   ├── normalizer.py             # 规范化处理器（176行）
│   │   ├── ner_model.py              # BERT NER模型（163行）
│   │   └── opencc_utils.py           # OpenCC繁简转换（176行）
│   │
│   ├── collation/                    # ③校勘模块（核心）
│   │   ├── __init__.py
│   │   ├── processor.py              # 校勘处理器（147行）
│   │   ├── tokenizer.py              # 古籍分词器（183行）
│   │   ├── aligner.py                # BERT语义对齐器（209行）
│   │   ├── differ.py                 # 差异检测器（197行）
│   │   └── judge.py                  # 校勘裁判规则（143行）
│   │
│   ├── entity_resolution/             # ④辑佚模块
│   │   ├── __init__.py
│   │   ├── resolver.py               # 实体消解器（475行）
│   │   ├── citation_analyzer.py       # 引文分析
│   │   └── merger.py                 # 实体融合
│   │
│   ├── map_extraction/                # ⑤舆图模块
│   │   ├── __init__.py
│   │   ├── map_service.py             # 舆图服务（307行）
│   │   ├── segmenter.py              # U-Net分割器
│   │   ├── vectorizer.py             # 矢量化
│   │   ├── label_ocr.py             # 地图标注OCR
│   │   ├── geo_mapper.py            # 地理坐标映射
│   │   └── unet_model.py            # U-Net模型
│   │
│   ├── annotation_extract/            # ⑥批校模块
│   │   ├── __init__.py
│   │   ├── annotation_service.py     # 批校服务（298行）
│   │   ├── detector.py               # Faster R-CNN检测器（683行）
│   │   ├── aligner.py               # 批校对齐器（350行）
│   │   ├── ocr.py                  # 批校OCR
│   │   └── faster_rcnn_model.py     # Faster R-CNN模型
│   │
│   ├── compilation/                   # 辑佚模块
│   │   ├── __init__.py
│   │   ├── compilation_service.py    # 辑佚服务（284行）
│   │   ├── scraper.py               # 文本抓取
│   │   ├── dedup.py                 # 去重
│   │   ├── merger.py                 # 版本融合（~300行）
│   │   └── ranker.py                # 版本排序（362行）
│   │
│   ├── rag/                          # ⑧RAG模块
│   │   ├── __init__.py
│   │   ├── rag_service.py            # RAG服务（255行）
│   │   ├── chunker.py               # 文本分块器（411行）
│   │   ├── embedder.py              # BGE向量化（218行）
│   │   ├── retriever.py             # 混合检索器（443行）
│   │   └── generator.py             # LLM生成器（272行）
│   │
│   ├── database/                     # ⑦知识图谱模块
│   │   ├── __init__.py
│   │   ├── neo4j_client.py          # Neo4j客户端（102行）
│   │   ├── milvus_client.py        # Milvus客户端（70行）
│   │   └── kg_service.py            # 知识图谱服务（160行）
│   │
│   ├── models/                       # 数据模型
│   │   ├── __init__.py
│   │   ├── collation.py
│   │   └── ocr.py
│   │
│   └── pipeline/                    # 处理流水线
│       └── gazetteer_pipeline.py
│
├── frontend/                        # Vue3前端
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.js                  # 前端入口
│       ├── App.vue                  # 根组件
│       ├── router/
│       │   └── index.js             # 路由配置
│       ├── views/
│       │   ├── HomeView.vue         # 首页
│       │   ├── CollationView.vue   # 校勘视图
│       │   ├── KnowledgeView.vue   # 知识图谱视图
│       │   └── QAView.vue          # 问答视图
│       └── assets/
│           └── styles/
│
├── docker/                         # Docker配置
│   └── docker-compose.yml          # Docker编排
│
├── scripts/                        # 工具脚本
│   ├── pdf_extractor.py           # PDF文本提取（261行）
│   ├── process_guanzhi.py          # 固安县志处理（229行）
│   ├── quick_collate.py           # 快速校勘测试（283行）
│   └── ocr_guanzhi.py             # OCR pipeline（241行）
│
├── data/                           # 数据目录
│   ├── raw/                        # 原始数据
│   │   ├── kangxi/                # 康熙版
│   │   ├── xianfeng/              # 咸丰版
│   │   ├── 1998/                  # 98年版（已提取）
│   │   └── 固安县志(...)/          # 其他版本
│   ├── processed/                  # 处理后数据
│   │   └── collation_results/     # 校勘结果
│   └── classical_chinese_data/     # 古文数据集
│
├── models/                         # 模型文件
│
├── reports/                        # 实验报表
│   ├── experiment_report_001.md
│   └── experiment_report_002.md
│
├── requirements.txt                 # Python依赖
├── README.md                       # 项目说明
└── PROJECT_SPEC.md                 # 本文档
```

---

## 5. API路由规范

### 5.1 路由总览

| 端点 | 方法 | 功能 | 模块 |
|------|------|------|------|
| `/api/v1/ocr/recognize` | POST | OCR识别 | ① |
| `/api/v1/normalize` | POST | 文本规范化 | ② |
| `/api/v1/collation/compare` | POST | 版本校勘 | ③ |
| `/api/v1/compilation/compile` | POST | 多源辑佚 | ④ |
| `/api/v1/map/extract` | POST | 舆图提取 | ⑤ |
| `/api/v1/annotation/extract` | POST | 批校提取 | ⑥ |
| `/api/v1/kg/collation-result` | POST | 校勘结果入图 | ⑦ |
| `/api/v1/rag/ask` | POST | RAG问答 | ⑧ |
| `/api/v1/rag/ingest` | POST | RAG文档摄入 | ⑧ |
| `/api/v1/health` | GET | 健康检查 | - |

### 5.2 请求/响应格式

#### OCR识别

```http
POST /api/v1/ocr/recognize
Content-Type: multipart/form-data

file: <图片文件>

Response: 200 OK
{
  "doc_id": "uuid-string",
  "pages": [{
    "page_num": 1,
    "image_path": "/path/to/page_001.png",
    "text": "识别文本...",
    "lines": [{"text": "...", "bbox": [...]}],
    "chars": [{
      "char": "吴",
      "bbox": [x1,y1,x2,y2],
      "is_variant": true,
      "variant_of": "吳",
      "is_taboo": false
    }],
    "ocr_confidence": 0.85,
    "variant_count": 12,
    "taboo_count": 2
  }],
  "ocr_confidence": 0.85,
  "variant_count": 12,
  "taboo_count": 2
}
```

#### 文本规范化

```http
POST /api/v1/normalize
Content-Type: application/json

{
  "text": "吳氏者，固安人也。康熙八年任知州...",
  "target_form": "simplified",
  "detect_entities": true
}

Response: 200 OK
{
  "text_original": "吳氏者，固安人也。康熙八年任知州...",
  "text_normalized": "吴氏者，固安人也。康熙八年任知州...",
  "entities": [
    {"type": "PER", "name": "吴氏", "start": 0, "end": 2},
    {"type": "LOC", "name": "固安", "start": 5, "end": 7},
    {"type": "TIME", "name": "康熙八年", "start": 9, "end": 14}
  ]
}
```

#### 多版本校勘

```http
POST /api/v1/collation/compare
Content-Type: application/json

{
  "text_a": "卷一 序一 序二...",
  "text_b": "卷一 舆地志...",
  "metadata_a": {"title": "固安县志(咸丰)", "year": 1851},
  "metadata_b": {"title": "固安县志(康熙)", "year": 1672}
}

Response: 200 OK
{
  "alignment_score": -0.3133,
  "diffs": [{
    "type": "substitution",
    "position_a": 65,
    "position_b": 65,
    "text_a": "民（共）和",
    "text_b": "层，有，",
    "char_diffs": [...],
    "judgment_result": {
      "preferred_version": "A",
      "judgment": "字形相似误识",
      "confidence": 0.3,
      "rule_used": "GRAPHIC_SIM"
    }
  }],
  "summary": {
    "total_diffs": 587,
    "by_type": {"deletion": 502, "substitution": 51, "insertion": 34}
  }
}
```

#### RAG问答

```http
POST /api/v1/rag/ask
Content-Type: application/json

{
  "question": "固安县志中记载了哪些知州？",
  "top_k": 5
}

Response: 200 OK
{
  "answer": "根据《固安县志》记载...",
  "sources": [{"text": "...", "source": "固安县志(康熙)", "score": 0.92}]
}
```

---

## 6. 数据库设计

### 6.1 Neo4j图数据库

#### 连接配置

```yaml
neo4j:
  uri: bolt://localhost:7687
  user: neo4j
  password: password
  database: neo4j
```

#### 节点定义

**Person（人物）**

```cypher
CREATE (p:Person {
  name: "吴氏",
  biography: "吴氏者，固安人也。康熙八年任知州...",
  years: "?-?",
  birthplace: "固安",
  title: "知州",
  dynasty: "清",
  source: "固安县志(康熙)",
  created_at: timestamp()
})
```

**Gazetteer（方志）**

```cypher
CREATE (g:Gazetteer {
  title: "固安县志",
  region: "固安",
  total_characters: 974139,
  version_count: 5,
  created_at: timestamp()
})
```

**Version（版本）**

```cypher
CREATE (v:Version {
  title: "固安县志(康熙)",
  year: 1672,
  dynasty: "清",
  ocr_completed: false,
  character_count: 0
})
```

**Variation（差异）**

```cypher
CREATE (v:Variation {
  id: randomUUID(),
  type: "substitution",
  text_a: "民（共）和",
  text_b: "层，有，",
  source_a: "固安县志(咸丰)",
  source_b: "固安县志(康熙)",
  position_a: 65,
  position_b: 65,
  judgment_rule: "GRAPHIC_SIM",
  confidence: 0.3
})
```

#### 关系定义

```cypher
-- 版本包含关系
(g:Gazetteer)-[:CONTAINS_VERSION]->(v:Version)

-- 版本比较关系
(v1:Version)-[:COMPARED_WITH {alignment_score: -0.3133}]->(v2:Version)

-- 差异归属
(v1:Version)-[:HAS_VARIATION]->(var:Variation)
(var:Variation)-[:VARIATION_OF]->(v2:Version)

-- 人物关系
(p1:Person)-[:FAMILY_RELATED_TO {relation: "父子"}]->(p2:Person)
(p1:Person)-[:COLLEAGUE_OF {title: "知州", period: "康熙八年"}]->(p2:Person)
```

### 6.2 Milvus向量数据库

#### 连接配置

```yaml
milvus:
  uri: ./milvus_zhijian.db  # SQLite本地存储
  dimension: 768
  index_type: HNSW
  metric_type: IP
```

#### Collection: persons

```python
{
    "collection_name": "persons",
    "fields": [
        {"name": "id", "type": "int64", "is_primary": True},
        {"name": "vector", "type": "float_vector", "dim": 768},
        {"name": "text", "type": "varchar", "max_length": 4096},
        {"name": "metadata", "type": "json"}
    ],
    "index_params": {
        "index_type": "HNSW",
        "metric_type": "IP",
        "params": {"M": 16, "efConstruction": 200}
    }
}
```

#### Collection: gazetteers

```python
{
    "collection_name": "gazetteers",
    "fields": [
        {"name": "id", "type": "int64", "is_primary": True},
        {"name": "vector", "type": "float_vector", "dim": 768},
        {"name": "text", "type": "varchar", "max_length": 4096},
        {"name": "metadata", "type": "json"}
    ],
    "index_params": {
        "index_type": "HNSW",
        "metric_type": "IP",
        "params": {"M": 16, "efConstruction": 200}
    }
}
```

---

## 7. 前端架构

### 7.1 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| 框架 | Vue 3 | 组合式API (Composition API) |
| 构建工具 | Vite | 快速热更新 |
| UI组件库 | Element Plus | Vue3组件库 |
| 图表库 | ECharts | 知识图谱可视化 |
| 路由 | Vue Router 4 | 前端路由 |
| HTTP客户端 | Axios | API调用 |

### 7.2 路由配置

```javascript
// router/index.js
const routes = [
  { path: '/', name: 'Home', component: HomeView },
  { path: '/collation', name: 'Collation', component: CollationView },
  { path: '/knowledge', name: 'Knowledge', component: KnowledgeView },
  { path: '/qa', name: 'QA', component: QAView }
]
```

### 7.3 视图组件详情

#### HomeView.vue（首页）

**功能模块**：

| 模块 | 说明 |
|------|------|
| 系统状态检查 | API连接、OCR、NER、校勘模块健康状态 |
| 项目介绍 | 志鉴系统定位、核心技术、价值主张 |
| 快速开始 | 环境配置、启动步骤 |

**状态检查接口**：

```javascript
// GET /api/v1/health
{
  "status": "healthy",
  "modules": {
    "ocr": "available",
    "normalizer": "available",
    "collation": "available"
  }
}
```

#### CollationView.vue（校勘视图）

**功能模块**：

| 模块 | 说明 |
|------|------|
| 双栏文本输入 | 版本A/版本B文本输入框，支持粘贴/上传 |
| OCR扫描上传 | 上传古籍图片，调用OCR识别 |
| 校勘执行 | 调用`/api/v1/collation/compare` |
| 差异表格 | 展示差异类型、位置、内容、置信度 |
| 饼图统计 | ECharts展示差异类型分布 |
| 对齐评分 | 展示对齐分数 |

**数据流向**：

```
用户输入/OCR上传
    │
    ▼
调用 /api/v1/collation/compare
    │
    ▼
返回差异列表
    │
    ├─► 差异表格展示
    │
    ├─► ECharts饼图统计
    │
    └─► 对齐评分展示
```

#### KnowledgeView.vue（知识图谱视图）

**功能模块**：

| 模块 | 说明 |
|------|------|
| ECharts力导向图 | 人物关系可视化 |
| 节点分类 | 苏氏家族/妻妾/其他人物（不同颜色）|
| 关系线标注 | 父子/兄弟/夫妻/师生/政敌 |
| 人物搜索 | 搜索框快速定位 |
| 详情面板 | 点击节点显示人物详情 |

**ECharts配置**：

```javascript
{
  type: 'graph',
  layout: 'force',
  symbolSize: 30,
  categories: [
    { name: '苏氏家族' },
    { name: '妻妾' },
    { name: '其他人物' }
  ],
  edgeSymbol: ['circle', 'arrow'],
  edgeLabel: { show: true, formatter: '{c}' },
  force: {
    repulsion: 100,
    edgeLength: 100
  }
}
```

#### QAView.vue（问答视图）

**功能模块**：

| 模块 | 说明 |
|------|------|
| 聊天界面 | 对话消息展示（user/assistant）|
| 输入框 | 问题输入，Ctrl+Enter发送 |
| 示例问题 | 预设问题标签快速提问 |
| 检索面板 | 右侧展示检索来源 |

**消息格式**：

```javascript
// 用户消息
{ role: 'user', content: '固安县志中记载了哪些知州？' }

// 助手消息
{ role: 'assistant', content: '根据《固安县志》记载...', sources: [...] }
```

---

## 8. 数据资源

### 8.1 古籍数据总览

| 版本 | PDF数 | 可用字符 | 文本层状态 | 处理方式 | 状态 |
|------|-------|---------|-----------|---------|------|
| 固安县志（康熙） | 17 | 0 | ❌ 纯扫描 | 需OCR | ⏳ 待处理 |
| 固安县志（咸丰） | 16 | 652 | ❌ 纯扫描 | 需OCR | ⚠️ 部分完成 |
| 固安县志（98年版）| 29 | **974,139** | ✅ 文字层 | PyMuPDF | ✅ 完成 |
| 固安县志（民国） | 1 | 0 | ❌ 纯扫描 | 需OCR | ⏳ 待处理 |
| 故宫博物院藏 | 1 | 0 | 未知 | 待定 | ⏳ 待处理 |

### 8.2 98年版已提取数据详情

| 章节 | 字符数 | 页数 | 备注 |
|------|--------|------|------|
| 第二十一编人物 | 105,283 | 47 | - |
| 第二十一编人物（续）| 167,103 | - | - |
| 第十九编教科文卫 | 449,569 | - | - |
| 第十四编农业 | 223,442 | - | - |
| 第十三编基础设施 | 224,421 | - | - |
| 第二十一编工商联 | 56,166 | - | - |
| 第十七编财税金融 | 60,348 | - | - |
| 第二十编民情民俗 | 45,794 | - | - |
| 第九编综合政务 | 42,950 | - | - |
| 大事记 | 42,218 | 39 | - |
| 第二编自然环境 | 25,675 | 25 | - |
| 第一编政区建置 | 24,228 | 24 | - |
| 第三编人口 | 12,580 | 13 | - |
| 概述 | 7,309 | 6 | - |
| **合计** | **974,139** | **~300页** | **29个TXT** |

### 8.3 咸丰版OCR测试数据

| PDF | 页数 | 提取字符 | 耗时 | 评估 |
|-----|------|---------|------|------|
| 凡例.pdf | 4 | 11 | 44秒 | 封面页，无正文 |
| 卷一（序、目录、舆地志）| 64 | 641 | 11分钟 | 识别率极低 |

**咸丰版OCR评估结论**：
- 引擎：EasyOCR 1.7.2（ch_sim + en）
- 速度：~10秒/页（CPU）
- 质量：极低（64页仅641字符）
- 原因：古籍竖排、手写体、墨迹不均

---

## 9. 核心算法详解

### 9.1 Needleman-Wunsch全局对齐算法

**位置**：`app/collation/aligner.py::SemanticAligner.needleman_wunsch`

**用途**：对两个句子序列进行全局最优对齐

**输入**：
- `sim_matrix`：相似度矩阵 (n×m)，n=序列A长度，m=序列B长度
- `gap_penalty`：空位惩罚，默认-0.5
- `match_bonus`：匹配奖励，默认1.0
- `mismatch_penalty`：不匹配惩罚，默认-0.5

**动态规划公式**：

```
dp[i][j] = max(
    dp[i-1][j-1] + (sim_matrix[i-1][j-1] > 0 ? match_bonus : mismatch_penalty),  # 对角线
    dp[i-1][j] + gap_penalty,  # 上方（序列A中有字符，B中为空位）
    dp[i][j-1] + gap_penalty   # 左方（序列B中有字符，A中为空位）
)
```

**初始化**：

```
dp[0][0] = 0
dp[i][0] = i * gap_penalty  # 序列A vs 空序列
dp[0][j] = j * gap_penalty  # 序列B vs 空序列
```

**回溯**：从`dp[n][m]`开始，根据dp值来源回溯：
- 来自`dp[i-1][j-1]`→ 对齐
- 来自`dp[i-1][j]`→ B中插入空位
- 来自`dp[i][j-1]`→ A中插入空位

**输出**：对齐路径列表 `[(idx_a, idx_b, score), ...]`

### 9.2 约束对齐算法

**位置**：`app/collation/aligner.py::SemanticAligner.constrained_align`

**改进**：在NW算法基础上添加相似度阈值约束

**逻辑**：

```python
def constrained_align(sentences_a, sentences_b, similarity_threshold=0.7):
    # 1. 计算相似度矩阵
    sim_matrix = cosine_similarity_matrix(encode(sentences_a), encode(sentences_b))

    # 2. NW对齐
    raw_alignments = needleman_wunsch(sim_matrix)

    # 3. 过滤低质量匹配
    filtered_alignments = []
    for idx_a, idx_b, score in raw_alignments:
        if score >= similarity_threshold:
            filtered_alignments.append((idx_a, idx_b, score))

    # 4. 返回结果
    return {
        "alignments": filtered_alignments,
        "unmatched_a": [i for i in range(len(sentences_a)) if i not in [a[0] for a in filtered_alignments]],
        "unmatched_b": [j for j in range(len(sentences_b)) if j not in [a[1] for a in filtered_alignments]],
        "alignment_score": sum(a[2] for a in filtered_alignments) / len(filtered_alignments) if filtered_alignments else 0
    }
```

### 9.3 Reciprocal Rank Fusion (RRF)

**位置**：`app/rag/retriever.py::Retriever._reciprocal_rank_fusion`

**用途**：融合向量检索和BM25关键词检索结果

**公式**：

```
RRF_score(doc) = Σ 1 / (k + rank_i(doc))
```

其中：
- `k`：常量，默认60
- `rank_i(doc)`：文档在第i个检索结果中的排名（从1开始）

**简化版本（系统使用）**：

```python
combined_score = alpha * normalized_vector_score + (1-alpha) * normalized_bm25_score
```

其中`alpha=0.5`表示平衡权重。

### 9.4 实体相似度计算

**位置**：`app/entity_resolution/resolver.py::EntityResolver.compute_similarity`

**公式**：

```
similarity = name_weight * edit_distance_score
           + time_weight * time_overlap_score
           + location_weight * location_score
           + context_weight * context_tfidf_score
```

**各项计算**：

| 维度 | 权重 | 计算方法 |
|------|------|----------|
| 名称 | 0.3 | 1 - Levenshtein_distance / max(len_a, len_b) |
| 时间 | 0.25 | overlap_duration / union_duration |
| 地域 | 0.25 | 字符串匹配 或 地理距离 |
| 上下文 | 0.2 | TF-IDF余弦相似度 |

### 9.5 并查集聚类算法

**位置**：`app/entity_resolution/resolver.py::EntityResolver.cluster_entities`

**用途**：将相似的实体聚类到同一组

```python
def cluster_entities(self, entities, threshold=0.75):
    parent = list(range(len(entities)))

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        px, py = find(x), find(y)
        if px != py and self.compute_similarity(entities[x], entities[y]) >= threshold:
            parent[px] = py

    # 两两检查，合并相似实体
    for i in range(len(entities)):
        for j in range(i+1, len(entities)):
            union(i, j)

    # 汇总聚类结果
    clusters = {}
    for i in range(len(entities)):
        root = find(i)
        if root not in clusters:
            clusters[root] = []
        clusters[root].append(entities[i])

    return list(clusters.values())
```

---

## 10. 开发进度与规划

### 10.1 模块开发状态

| # | 模块 | 状态 | 完成度 | 说明 |
|---|------|------|--------|------|
| ① | OCR识别 | ✅ | 100% | variant_map、preprocess、recognizer完成 |
| ② | 文本规范化 | ✅ | 100% | opencc_utils、ner_model完成 |
| ③ | 多版本校勘 | ✅ | 100% | tokenizer、aligner、differ、judge完成 |
| ④ | 辑佚模块 | ✅ | 80% | 代码完整，待数据验证 |
| ⑤ | 舆图提取 | 🔜 | 30% | 框架完成，模型待训练 |
| ⑥ | 批校痕迹 | 🔜 | 30% | 框架完成，模型待训练 |
| ⑦ | 知识图谱 | ✅ | 100% | neo4j_client、kg_service完成 |
| ⑧ | RAG问答 | 🔜 | 70% | 检索完成，LLM接入待实现 |

### 10.2 三阶段开发规划

#### 第一阶段：数据基础（约1-2天）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| 咸丰版批量OCR | 完成16个PDF的OCR识别 | 🔴 高 |
| 康熙版批量OCR | 完成17个PDF的OCR识别 | 🔴 高 |
| 民国版OCR | 完成民国版OCR | 🟡 中 |
| OCR模型微调 | 准备标注数据，训练古文OCR | 🔴 高 |

#### 第二阶段：模型优化（约3-5天）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| PaddleOCR古文微调 | 基于标注数据微调PP-OCRv4 | 🔴 高 |
| BERT NER微调 | 训练古文实体识别模型 | 🟡 中 |
| GPU加速部署 | BERT编码GPU加速 | 🟡 中 |
| 性能优化 | BERT知识蒸馏 | 🟢 低 |

#### 第三阶段：功能完善（约2-3天）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| RAG LLM接入 | 接入DeepSeek/Kimi API | 🟡 中 |
| 前端交互优化 | 完善Vue组件交互 | 🟢 低 |
| 知识图谱完善 | 补充人物关系 | 🟢 低 |
| 演示视频 | 制作参赛演示视频 | 🟢 低 |

### 10.3 关键里程碑

| 里程碑 | 目标日期 | 交付物 |
|--------|----------|--------|
| M1: 数据完整提取 | Day 1-2 | 5个版本全部完成OCR |
| M2: OCR模型微调 | Day 3-4 | 古文识别率>80% |
| M3: 端到端验证 | Day 5 | 完整校勘流程演示 |
| M4: RAG功能 | Day 6 | 问答系统演示 |
| M5: 作品提交 | Day 7 | 完整作品包 |

---

## 11. 部署指南

### 11.1 环境要求

| 要求 | 规格 |
|------|------|
| Python | 3.10.x（推荐3.10.5）|
| 内存 | ≥16GB（推荐32GB）|
| 显存 | ≥8GB（如需GPU加速）|
| 磁盘 | ≥50GB |
| 操作系统 | Windows/Linux/macOS |

### 11.2 安装步骤

```bash
# 1. 创建Python环境
conda create -n zhijian python=3.10.5 -y
conda activate zhijian

# 2. 安装依赖
cd zhijian
pip install -r requirements.txt

# 3. 下载NLP模型（首次运行自动下载）
# bert-base-chinese ~400MB
# BGE模型 ~400MB
# EasyOCR模型 ~300MB
```

### 11.3 启动服务

```bash
# 1. 启动Docker服务（Neo4j + Milvus）
cd docker
docker-compose up -d

# 2. 启动后端API
cd zhijian
uvicorn app.main:app --reload --port 8000

# 3. 启动前端（另一个终端）
cd frontend
npm install  # 首次
npm run dev

# 4. 访问
# 前端：http://localhost:3000
# API文档：http://localhost:8000/docs
```

### 11.4 Docker服务配置

```yaml
# docker/docker-compose.yml
services:
  neo4j:
    image: neo4j:5.12
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/password

  milvus:
    image: milvusdb/milvus:v2.3.4
    ports:
      - "19530:19530"
    environment:
      - ETCD_ENDPOINTS=localhost:2379
      - MINIO_ADDRESS=localhost:9000

  etcd:
    image: quay.io/coreos/etcd:v3.5.5
    ports:
      - "2379:2379"

  minio:
    image: minio/minio:latest
    ports:
      - "9000:9000"
      - "9001:9001"
```

---

## 12. 技术依赖清单

### 12.1 requirements.txt

```
# 核心框架
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3

# OCR
paddlepaddle==2.6.0
paddleocr==2.7.3
opencv-python==4.9.0.80
opencv-contrib-python==4.9.0.80
Pillow==10.2.0
easyocr==1.7.2

# 深度学习
torch==2.1.2
transformers==4.37.2
accelerate==0.26.0

# NLP
pkuseg==0.0.25
opencc-python-reimplemented==0.1.7

# 知识图谱
neo4j==5.14.1
py2neo==20231219

# 向量数据库
milvus-lite==2.3.7
pymilvus==2.3.7
flagembedding==1.2.10

# 可视化
matplotlib==3.8.2
seaborn==0.13.1

# PDF处理
pymupdf==1.23.0

# 其他
numpy==1.26.3
scikit-learn==1.4.0
python-multipart==0.0.6
aiofiles==23.2.1
```

### 12.2 前端依赖（frontend/package.json）

```json
{
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.2.0",
    "element-plus": "^2.5.0",
    "echarts": "^5.5.0",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.0.0"
  }
}
```

---

## 附录

### A. 关键文件行数统计

| 文件 | 行数 | 模块 |
|------|------|------|
| `app/api/routes.py` | 459 | API |
| `app/ocr/variant_map.py` | ~2000 | OCR |
| `app/ocr/recognizer.py` | 363 | OCR |
| `app/ocr/preprocess.py` | 248 | OCR |
| `app/ocr/processor.py` | 301 | OCR |
| `app/collation/aligner.py` | 209 | 校勘 |
| `app/collation/tokenizer.py` | 183 | 校勘 |
| `app/collation/differ.py` | 197 | 校勘 |
| `app/collation/judge.py` | 143 | 校勘 |
| `app/collation/processor.py` | 147 | 校勘 |
| `app/rag/retriever.py` | 443 | RAG |
| `app/rag/chunker.py` | 411 | RAG |
| `app/rag/generator.py` | 272 | RAG |
| `app/rag/embedder.py` | 218 | RAG |
| `app/entity_resolution/resolver.py` | 475 | 辑佚 |
| `app/map_extraction/map_service.py` | 307 | 舆图 |
| `app/annotation_extract/detector.py` | 683 | 批校 |
| `app/annotation_extract/aligner.py` | 350 | 批校 |
| `app/database/kg_service.py` | 160 | 图谱 |

### B. 实验报告索引

| 报告 | 日期 | 内容 |
|------|------|------|
| experiment_report_001.md | 2026-03-31 | 数据管道验证、核心流程测试 |
| experiment_report_002.md | 2026-03-31 | 完整数据提取、端到端校勘验证 |

### C. 已知问题清单

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| 1 | PaddleOCR + Python 3.13 PIR不兼容 | 🔴 | ✅ 已绕过（使用EasyOCR）|
| 2 | OCR识别率极低（古籍竖排/手写体）| 🔴 | ⚠️ 待优化 |
| 3 | BERT编码占校勘耗时96.6% | 🟡 | ⚠️ 待优化 |
| 4 | OCR速度慢（~10秒/页CPU）| 🟡 | ⚠️ 待优化 |
| 5 | 康熙/咸丰版无文字层 | 🔴 | ⏳ 待批量OCR |

---

**文档编制**：志鉴开发团队
**最后更新**：2026-04-02
**版本**：v1.0
