# 「志鉴」古籍方志智能化整理与知识服务平台

<p align="center">
  <img src="docs/images/01_cover.png" alt="志鉴系统封面" width="600">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10-blue" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.109-green" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue-3.4-brightgreen" alt="Vue">
  <img src="https://img.shields.io/badge/BERT-bert--base--chinese-orange" alt="BERT">
  <img src="https://img.shields.io/badge/Neo4j-5.12-blue" alt="Neo4j">
  <img src="https://img.shields.io/badge/license-MIT-lightgrey" alt="License">
</p>

---

## 项目概述

中国地方志是特有的文献类型，全国现存超过 **8000 种**，**90% 以上**尚未完成数字化整理。传统人工校勘一部地方志需要 **3-5 年**，且需要领域专家深度参与。

「志鉴」通过 AI 技术将这一过程压缩到 **数天**，实现：

- 古籍扫描件的自动 OCR 识别与异体字/避讳字检测
- 多版本方志的 BERT 语义对齐与差异检测
- 繁简转换、异体字规范化、NER 实体识别
- Neo4j 知识图谱人物关系挖掘与可视化
- 基于 RAG 的古籍智能问答

> **构建方式**：本项目由 Claude Code Agent 驱动构建，零手动编码。**精简版三大模块**——OCR 古籍识别、知识图谱、RAG 智能问答——端到端打通。OCR 基于 EasyOCR + 1000+ 异体字映射 + 清代避讳规则，识别扫描件并标注异体；知识图谱采用「规则引擎打底 + Qwen2.5-3B 本地 LLM 增强」的双重抽取策略，解决了古文 NER 冷启动难题；RAG 问答走「BGE 向量 + BM25 + RRF 融合 + Qwen2.5-3B」四步检索增强链路。覆盖 5 个历史版本、974,139 字符真实方志数据，由 hbusl 与 Claude 协作完成。

### 核心指标

| 指标 | 数值 | 说明 |
|------|------|------|
| OCR 识别速度 | ~10 秒/页 | CPU 模式，GPU 可加速 |
| 已提取数据量 | 974,139 字符 | 98 年版固安县志 |
| 支持版本数 | 5 个 | 康熙 / 咸丰 / 98年 / 民国 / 故宫 |
| 异体字映射 | 1000+ 条 | 覆盖清代避讳与通假 |

---

## 系统架构

<p align="center">
  <img src="docs/images/02_architecture.png" alt="系统架构图" width="800">
</p>

```
古籍扫描件 → OCR识别 ──┐
                      ├→ 知识图谱 ──→ RAG问答
                      └→ 直接入问答库
```

### 三大核心模块

| # | 模块 | 核心技术 |
|---|------|----------|
| ① | **OCR 古籍识别** | EasyOCR / PaddleOCR + 1000+ 异体字映射 + 清代避讳规则 + OpenCV 预处理 |
| ② | **知识图谱** | 纯内存存储 + 正则/LLM 实体抽取 + ECharts 力导向可视化 |
| ③ | **RAG 智能问答** | BGE 向量化 + BM25 混合检索 + RRF 融合 + Ollama/Qwen2.5 |

---

## 功能展示

### OCR 古籍识别

<p align="center">
  <img src="docs/images/03_ocr_showcase.png" alt="OCR识别展示" width="700">
</p>

支持竖排文字、手写体、墨迹不均等古籍特有挑战。内置 1000+ 异体字映射和清代康熙/雍正/乾隆避讳字检测。

### 知识图谱可视化

<p align="center">
  <img src="docs/images/04_knowledge_graph.png" alt="知识图谱展示" width="700">
</p>

从方志文本中自动抽取人物实体和家族/同事/师生关系，ECharts 力导向图可视化，支持点击查看人物详情。

### RAG 智能问答

<p align="center">
  <img src="docs/images/05_rag_interface.png" alt="RAG问答界面" width="700">
</p>

基于检索增强生成的古籍问答，支持向量语义检索 + BM25 关键词检索的混合策略，本地 Ollama 部署 Qwen2.5-3B。

---

## 快速开始

### 环境要求

| 组件 | 最低 | 推荐 |
|------|------|------|
| Python | 3.10 | 3.10.5 |
| 内存 | 16 GB | 32 GB |
| 显存 | - | 8 GB (GPU 加速) |
| 磁盘 | 10 GB | 50 GB |
| Node.js | 18 | 20 LTS |

### 1. 后端

```bash
# 创建虚拟环境
conda create -n zhijian python=3.10.5 -y
conda activate zhijian

# 安装依赖
cd zhijian
pip install -r requirements.txt

# 启动 API 服务
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API 文档自动生成：http://localhost:8000/docs

> 需要 RAG 生成式问答时，另启 Ollama：`ollama serve`（详见 [DEPLOY.md](DEPLOY.md)）

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000

### 3. 数据准备（可选）

```bash
# 将古籍 PDF/图片放入 data/raw/<版本名>/
# 文本文件放入 data/raw/1998/ 可直接被 RAG ingestion 使用

# 初始化知识图谱（从人物志文本）
curl -X POST "http://localhost:8000/api/v1/kg/init?clear=true"

# 灌入 RAG 知识库
curl -X POST "http://localhost:8000/api/v1/rag/seed?data_dir=data/raw/1998&rebuild=true"
```

---

## API 端点

| 端点 | 方法 | 模块 | 说明 |
|------|------|------|------|
| `/api/v1/health` | GET | 系统 | 健康检查 |
| `/api/v1/status` | GET | 系统 | 模块状态与端点清单 |
| `/api/v1/ocr/status` | GET | OCR | Provider / 模型就绪状态 |
| `/api/v1/ocr/recognize` | POST | OCR | 上传图片进行 OCR 识别 |
| `/api/v1/ocr/batch` | POST | OCR | 批量识别（≤10 张） |
| `/api/v1/ocr/variants` | GET | OCR | 异体字映射表（1000+ 条） |
| `/api/v1/ocr/samples` | GET | OCR | 列出样本图（kangxi 页） |
| `/api/v1/ocr/samples/{filename}` | GET | OCR | 直出样本图 PNG |
| `/api/v1/kg/status` | GET | KG | 图谱就绪状态 |
| `/api/v1/kg/persons` | GET | KG | 人物列表 |
| `/api/v1/kg/persons/{name}` | GET | KG | 人物详情 |
| `/api/v1/kg/graph` | GET | KG | 图谱可视化数据 |
| `/api/v1/kg/init` | POST | KG | 初始化人物图谱 |
| `/api/v1/kg/extract/preview` | POST | KG | 文本→候选实体/关系（不入库） |
| `/api/v1/kg/entity` | POST | KG | 手动新增实体 |
| `/api/v1/kg/relate` | POST | KG | 手动新增关系 |
| `/api/v1/rag/ask` | POST | RAG | 古籍智能问答 |
| `/api/v1/rag/ingest` | POST | RAG | 文档摄入 |
| `/api/v1/rag/seed` | POST | RAG | 灌入知识库（默认 1998 版） |
| `/api/v1/rag/status` | GET | RAG | 知识库就绪状态 |

---

## 项目结构

```
zhijian/
├── app/
│   ├── main.py                # FastAPI 入口
│   ├── api/routes.py          # API 路由（~700行）
│   ├── ocr/                   # ① OCR 识别（含 providers/）
│   ├── database/              # ② 知识图谱存储（kg_service, chroma_client）
│   ├── rag/                   # ③ RAG 问答（chunker, embedder, retriever, generator）
│   ├── kg/                    #    KG 抽取 pipeline
│   └── llm/                   #    LLM 客户端
├── frontend/                  # Vue3 前端
│   └── src/views/             # 4 个视图：Home, OCR, Knowledge, QA
├── scripts/                   # 工具脚本
├── tests/                     # 测试
├── docs/                      # 文档与截图
├── requirements.txt           # Python 依赖（OCR 走 extras 装）
└── CLAUDE.md                  # 项目约定
```

---

## 技术栈

| 层次 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI 0.109 | 高性能异步 API |
| OCR 引擎 | EasyOCR 1.7（主力）/ PaddleOCR 2.7（备选） | 双引擎切换，extras 装 |
| 图像处理 | OpenCV 4.9 | 灰度/二值化/降噪/旋转矫正 |
| NLP 模型 | bert-base-chinese + BGE bge-base-chinese-v1.5 | 768 维嵌入 + NER |
| 向量数据库 | ChromaDB | 持久化在 `chroma_zhijian/` |
| 前端框架 | Vue 3.4 + Vite 5 | 组合式 API |
| UI 组件 | Element Plus 2.5 | Vue3 组件库 |
| 可视化 | ECharts 5.5 | 知识图谱力导向图 |
| LLM | Ollama + Qwen2.5:3B | 本地部署，中文优化 |

---

## 开发进度

| # | 模块 | 状态 |
|---|------|------|
| ① | OCR 古籍识别 | 完成：RapidOCR（默认）+ Aliyun OCR（高精度）+ 1000+ 异体字 + 预处理 + 批量 + 样本图 |
| ② | 知识图谱 | 完成：纯内存存储 + 实体/关系抽取 + ECharts 可视化 |
| ③ | RAG 智能问答 | 完成：BGE + BM25 + RRF 融合 + Ollama + Qwen2.5-3B |

---

## 部署到服务器

完整部署手册见 [DEPLOY.md](DEPLOY.md)。快速流程：

```bash
# 1. 上传部署包到服务器
scp -r zhijian_deploy/ user@SERVER_IP:/root/zhijian_deploy/

# 2. 一键部署（含 Ollama + Qwen2.5-3B）
cd /root/zhijian_deploy
SERVER_IP=8.218.131.76 sudo -E bash deploy.sh
```

部署栈：**Nginx + systemd + Ollama（Qwen2.5-3B 本地）**。
