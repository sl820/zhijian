# AGENTS.md — 志鉴项目约定

## 项目概述
古籍方志智能化整理与知识服务平台，2026年中国大学生计算机设计大赛参赛作品。
**精简版三大模块**：OCR 古籍识别、知识图谱、RAG 智能问答。

## 技术栈
- 后端：FastAPI + Python 3.10+（Python 3.10/3.11/3.12 均可；3.13 上 PaddleOCR 不可用但 RapidOCR 仍 OK）
- OCR：**RapidOCR（默认·ONNX 后端）** > Aliyun OCR（云端·高精度·需 APP_CODE） > EasyOCR（兜底）> PaddleOCR（Linux/Mac 备选）
- NLP：BERT (bert-base-chinese) + BGE (bge-base-chinese-v1.5)
- 向量数据库：ChromaDB（实际使用）/ Milvus（可选）
- 前端：Vue3 + Vite + Element Plus + ECharts
- LLM：Ollama + Qwen2.5:3B（本地 / localhost:11434）

## 关键约定
- 后端入口：`app/main.py`，端口 8000
- 前端入口：`frontend/`，端口 3000，Vite 代理 `/api` → `http://localhost:8000`
- API 路由前缀：`/api/v1/`
- 虚拟环境忽略：`.venv_paddle/`、`node_modules/` 已在 .gitignore
- 模型权重不进仓库（models/*.pth 已 gitignore，RapidOCR 走 `~/.rapidocr/`，EasyOCR 走 `~/.EasyOCR/model/`）
- 数据文件在 `data/raw/`，按版本分目录（1998/, kangxi/, xianfeng/ 等）
- 临时文件和日志不进仓库（*.log, temp_* 已 gitignore）
- **OCR 是可选重型依赖**：默认装 `rapidocr-onnxruntime`（轻量，~30MB）。EasyOCR/PaddleOCR/Aliyun 均按需。Aliyun OCR 走环境变量 `ALIYUN_OCR_APP_CODE`，未配置则按钮隐藏

## 项目结构约定
```
app/ocr/              # ①OCR（重建）：processor, recognizer, preprocess, variant_map, ocr_service
app/ocr/providers/    #   OCR 引擎实现：base, easyocr, paddleocr, rapidocr（默认）, aliyun(可关)
app/database/         # ②知识图谱存储：chroma_client, kg_service
app/rag/              # ③RAG：rag_service, chunker, embedder, retriever, generator
app/kg/               #   KG 抽取 pipeline：实体/关系抽取
app/api/              # API 路由：routes.py（~700行）
app/llm/              # LLM 客户端：ollama_client, llama_cpp_client
scripts/              # 工具脚本
frontend/src/views/   # Vue 视图：Home, OCR, Knowledge, QA
frontend/src/stores/  # Pinia stores：app, ocr
```

## 验证命令
```bash
# 后端测试
cd /d/zhijian && python -m pytest tests/ -v --tb=short
# 前端构建
cd /d/zhijian/frontend && npm run build -- --emptyOutDir
# 启动后端
cd /d/zhijian && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# 启动前端
cd /d/zhijian/frontend && npm run dev
```

## 不要做的事
- 不要硬编码绝对路径，用 `Path(__file__).parent.parent` 相对定位
- 不要提交 API key 或密码（Neo4j 密码已暴露但仅本地开发用）
- 不要升级 Python 到 3.13（PaddleOCR PIR 不兼容）
- 不要在根目录创建临时测试文件
