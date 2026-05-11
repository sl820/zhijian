# CLAUDE.md — 志鉴项目约定

## 项目概述
古籍方志智能化整理与知识服务平台，2026年中国大学生计算机设计大赛参赛作品。
8大模块：OCR识别、文本规范化、多版本校勘、辑佚、舆图提取、批校提取、知识图谱、RAG问答。

## 技术栈
- 后端：FastAPI + Python 3.10（不要用 3.13，PaddleOCR 不兼容）
- OCR：EasyOCR（主力，ch_sim+en）/ PaddleOCR PP-OCRv4
- NLP：BERT (bert-base-chinese) + BGE (bge-base-chinese-v1.5)
- 图数据库：Neo4j 5.12（可选，有 in-memory 回退）
- 向量数据库：ChromaDB（实际使用）/ Milvus（可选）
- 前端：Vue3 + Vite + Element Plus + ECharts
- LLM：Ollama + Qwen2.5:3B（本地 / localhost:11434）

## 关键约定
- 后端入口：`app/main.py`，端口 8000
- 前端入口：`frontend/`，端口 3000，Vite 代理 `/api` → `http://localhost:8000`
- API 路由前缀：`/api/v1/`
- 虚拟环境忽略：`.venv_paddle/`、`node_modules/` 已在 .gitignore
- 模型权重不进仓库（models/*.pth 已 gitignore）
- 数据文件在 `data/raw/`，按版本分目录（1998/, kangxi/, xianfeng/ 等）
- 临时文件和日志不进仓库（*.log, temp_* 已 gitignore）

## 项目结构约定
```
app/ocr/              # ①OCR：processor, recognizer, preprocess, variant_map
app/normalize/        # ②规范化：normalizer, ner_model, opencc_utils
app/collation/        # ③校勘（核心）：processor, tokenizer, aligner, differ, judge
app/compilation/      # ④辑佚：compilation_service, scraper, dedup, merger, ranker
app/entity_resolution/ # 实体消解：resolver, citation_analyzer, merger
app/map_extraction/   # ⑤舆图：map_service, segmenter, vectorizer, unet_model
app/annotation_extract/ # ⑥批校：annotation_service, detector, aligner, faster_rcnn_model
app/database/         # ⑦知识图谱：neo4j_client, milvus_client, kg_service
app/rag/              # ⑧RAG：rag_service, chunker, embedder, retriever, generator
app/kg/               # KG pipeline：实体/关系抽取
app/api/              # API 路由：routes.py（~1900行）
app/llm/              # LLM 客户端：ollama_client, llama_cpp_client
scripts/              # 工具脚本
frontend/src/views/   # Vue 视图：Home, Collation, Compilation, Knowledge, QA, Map, Annotation
```

## 验证命令
```bash
# 后端
cd /d/zhijian && python -m pytest tests/ -v --tb=short
# 前端
cd /d/zhijian/frontend && npm run build -- --emptyOutDir
# 启动后端
cd /d/zhijian && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 不要做的事
- 不要硬编码绝对路径，用 `Path(__file__).parent.parent` 相对定位
- 不要提交 API key 或密码（Neo4j 密码已暴露但仅本地开发用）
- 不要升级 Python 到 3.13（PaddleOCR PIR 不兼容）
- 不要在根目录创建临时测试文件
