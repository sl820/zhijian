# 「志鉴」— 古籍方志智能化整理与知识服务平台

2026年中国大学生计算机设计大赛 · 人工智能应用赛道

## 项目概述

全国现存地方志8000余种，超过90%尚未完成数字化整理。本项目通过AI技术，将传统人工校勘3-5年的工作时间压缩到**数天**。

## 技术架构

```
古籍扫描件 → OCR识别 → 文本规范化 → 多版本校勘 → 知识图谱 → RAG问答
```

8大核心模块：
- 模块①：古籍OCR识别（PaddleOCR + 异体字/避讳字检测）
- 模块②：文本规范化（繁简转换、NER实体识别）
- 模块③：多版本智能校勘（BERT语义对齐 + 动态规划）
- 模块④：多源辑佚与去重
- 模块⑤：舆图信息提取
- 模块⑥：批校痕迹提取
- 模块⑦：人物关系图谱（Neo4j）
- 模块⑧：RAG智能问答

## 快速开始

### 1. 环境准备

```bash
# 创建Python环境
conda create -n zhijian python=3.10.5 -y
conda activate zhijian

# 安装依赖
cd zhijian
pip install -r requirements.txt
```

### 2. 启动数据库服务

```bash
cd docker
docker-compose up -d
```

### 3. 启动后端API

```bash
uvicorn app.main:app --reload --port 8000
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

## 项目结构

```
zhijian/
├── app/
│   ├── ocr/              # OCR模块
│   ├── normalize/        # 规范化模块
│   ├── collation/        # 校勘模块（核心）
│   ├── entity_resolution/ # 辑佚模块
│   ├── map_extraction/  # 舆图模块
│   ├── annotation_extract/ # 批校模块
│   ├── knowledge_graph/  # 图谱模块
│   ├── rag/             # 问答模块
│   ├── api/             # API路由
│   └── database/         # 数据库客户端
├── frontend/            # Vue3前端
├── docker/              # Docker配置
├── tests/               # 测试
└── requirements.txt
```

## 开发进度

| 模块 | 状态 | 说明 |
|------|------|------|
| ① OCR识别 | ✅ 完成 | variant_map, preprocess, recognizer, processor |
| ② 文本规范化 | ✅ 完成 | opencc_utils, ner_model, normalizer |
| ③ 多版本校勘 | ✅ 完成 | tokenizer, aligner, differ, judge, processor |
| ④ 辑佚模块 | 🔜 待开发 | 实体消解 |
| ⑤ 舆图提取 | 🔜 待开发 | U-Net分割 |
| ⑥ 批校痕迹 | 🔜 待开发 | Faster R-CNN |
| ⑦ 知识图谱 | ✅ 完成 | neo4j_client, kg_service |
| ⑧ RAG问答 | 🔜 待开发 | 向量检索+LLM |

## 技术栈

- **后端**：FastAPI + Python 3.10
- **OCR**：PaddleOCR PP-OCRv4
- **NLP**：BERT (bert-base-chinese)
- **图数据库**：Neo4j 5.12
- **向量数据库**：Milvus
- **前端**：Vue3 + Element Plus + ECharts

## 团队分工

| 角色 | 负责模块 |
|------|---------|
| OCR/图像 | 模块①⑤⑥ |
| NLP/校勘 | 模块②③④ |
| 知识图谱 | 模块⑦⑧ |
| 后端 | FastAPI + 数据库 |
| 前端 | Vue3 + 可视化 |

## 参赛信息

- **赛道**：人工智能应用（实践赛）
- **学校**：河北大学
- **指导教师**：待填写
- **团队成员**：待填写
