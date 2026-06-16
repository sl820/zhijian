"""
志鉴 API 路由 — 精简版
三大模块：OCR (古籍识别) + KG (知识图谱) + RAG (智能问答)
"""
import asyncio
import logging
import os
import tempfile
import time
from typing import Optional, List, Dict
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ============================================================
# Lazy-initialized service singletons
# ============================================================

_rag_service = None
_kg_service = None
_ocr_processor = None
_kg_init_state: Dict = {
    "running": False,
    "completed": False,
    "error": None,
    "result": None,
}


def get_rag_service():
    global _rag_service
    if _rag_service is None:
        from ..rag.rag_service import RAGService
        _rag_service = RAGService()
    return _rag_service


def get_kg_service():
    global _kg_service
    if _kg_service is None:
        from ..database.kg_service import KnowledgeGraphService
        _kg_service = KnowledgeGraphService()
    return _kg_service


def get_ocr_processor():
    global _ocr_processor
    if _ocr_processor is None:
        from ..ocr.processor import OCRProcessor
        _ocr_processor = OCRProcessor()
    return _ocr_processor


# ============================================================
# Request / Response models
# ============================================================

class RAGRequest(BaseModel):
    question: str = Field(..., min_length=1, description="用户问题（不能为空）")
    top_k: int = Field(5, ge=1, le=20)


class RAGResponse(BaseModel):
    answer: str
    sources: List[Dict]


class KGEntityExtractRequest(BaseModel):
    text: str
    source: Optional[str] = ""
    title: Optional[str] = ""


class KGPipelineRequest(BaseModel):
    text: str
    source: str = "unknown"
    title: str = ""
    store: bool = True


class KGEntityStoreRequest(BaseModel):
    name: str
    entity_type: str = "PER"
    biography: Optional[str] = ""
    dynasty: Optional[str] = ""
    years: Optional[str] = ""
    birthplace: Optional[str] = ""
    title: Optional[str] = ""
    person_type: int = 2
    source: Optional[str] = ""


class KGRelationRequest(BaseModel):
    from_name: str
    to_name: str
    relation_type: str
    properties: Optional[Dict] = None


class KGInitResponse(BaseModel):
    status: str
    persons_stored: int
    relations_stored: int
    total_persons: int
    total_relations: int
    sample_persons: List[str]


class KGInitStatusResponse(BaseModel):
    running: bool
    completed: bool
    error: Optional[str]
    result: Optional[KGInitResponse]


# ============================================================
# Warmup state — 跟踪三大模块启动预热进度
# ============================================================

router = APIRouter(prefix="/api/v1")

_warmup_state: Dict = {
    "running": False,
    "completed": False,
    "started_at": None,
    "completed_at": None,
    "modules": {
        "ocr": {"status": "pending", "duration_sec": None, "error": None},
        "kg": {"status": "pending", "duration_sec": None, "error": None},
        "rag": {"status": "pending", "duration_sec": None, "error": None},
    },
    "last_error": None,
}


def get_warmup_state() -> Dict:
    return _warmup_state


def _warmup_ocr() -> None:
    """初始化 OCR processor（含 RapidOCR ONNX 模型）。模型在 __init__ 时已加载。"""
    proc = get_ocr_processor()
    if proc is None or proc.ocr is None:
        raise RuntimeError("OCR processor/provider not initialized")
    # 各 provider 内部模型字段不一，统一做「对象存在 + 可识别」的最弱检查
    engine_attr = getattr(proc.ocr, "_engine", None) or getattr(proc.ocr, "reader", None)
    if engine_attr is None and not hasattr(proc.ocr, "recognize"):
        raise RuntimeError(f"OCR provider {type(proc.ocr).__name__} has no engine/recognize")


def _warmup_kg() -> None:
    """初始化 KG service（读 kg_state.json 入内存）。在 __init__ 时已加载。"""
    svc = get_kg_service()
    _ = len(svc._persons)


def _warmup_rag() -> None:
    """初始化 RAG 三件套：
    - embedder（BGE 模型 → CUDA，最慢 ~30s 首次加载）
    - generator（Ollama 客户端，5s 内可达）
    - retriever（ChromaDB 连接）
    """
    rag = get_rag_service()
    rag._get_embedder()
    rag._get_generator()
    rag._get_retriever()


async def trigger_warmup() -> None:
    """异步顺序预热三个模块。失败不抛，只记录到 _warmup_state。"""
    if _warmup_state["running"]:
        logger.info("[warmup] 已在进行中，跳过")
        return

    _warmup_state["running"] = True
    _warmup_state["started_at"] = time.time()
    _warmup_state["completed"] = False
    for mod in _warmup_state["modules"].values():
        mod["status"] = "pending"
        mod["duration_sec"] = None
        mod["error"] = None
    _warmup_state["last_error"] = None

    logger.info("[warmup] 开始预热三大模块...")

    for module_name, fn in [("ocr", _warmup_ocr), ("kg", _warmup_kg), ("rag", _warmup_rag)]:
        mod_state = _warmup_state["modules"][module_name]
        mod_state["status"] = "loading"
        start = time.time()
        try:
            logger.info(f"[warmup] {module_name} 预热中...")
            await asyncio.to_thread(fn)
            mod_state["status"] = "loaded"
            mod_state["duration_sec"] = round(time.time() - start, 2)
            logger.info(f"[warmup] {module_name} 预热完成 ({mod_state['duration_sec']}s)")
        except Exception as e:
            mod_state["status"] = "failed"
            mod_state["error"] = str(e)[:200]
            mod_state["duration_sec"] = round(time.time() - start, 2)
            _warmup_state["last_error"] = f"{module_name}: {e}"
            logger.error(f"[warmup] {module_name} 预热失败: {e}")

    _warmup_state["running"] = False
    _warmup_state["completed_at"] = time.time()
    _warmup_state["completed"] = True
    logger.info("[warmup] 全部预热结束")


# ============================================================
# System
# ============================================================

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "zhijian-api"}


@router.get("/status")
async def api_status():
    warm = _warmup_state
    return {
        "api_version": "v1",
        "endpoints": ["/ocr", "/kg", "/rag"],
        "warmup": {
            "completed": warm["completed"],
            "running": warm["running"],
            "last_error": warm["last_error"],
        },
    }


@router.get("/warmup/status")
async def warmup_status():
    """查看三大模块预热进度。BGE 首次加载 ~30s，期间此端点会反映 loading 状态。"""
    return _warmup_state


@router.post("/warmup")
async def warmup_trigger():
    """手动触发预热（启动时已自动跑；失败时可用此端点重试）。"""
    if _warmup_state["running"]:
        return {"status": "already_running", "state": _warmup_state}
    asyncio.create_task(trigger_warmup())
    return {"status": "started", "state": _warmup_state}


# ============================================================
# RAG (智能问答)
# ============================================================

@router.post("/rag/ask", response_model=RAGResponse)
async def rag_ask(request: RAGRequest):
    """RAG 智能问答接口"""
    try:
        logger.info(f"RAG question: {request.question}")
        rag_service = get_rag_service()
        result = rag_service.ask(question=request.question, top_k=request.top_k)
        return RAGResponse(
            answer=result.get("answer", ""),
            sources=result.get("sources", []),
        )
    except Exception as e:
        logger.error(f"Error in RAG ask: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/ingest")
async def rag_ingest(text: str, title: str = "未知文档"):
    """摄入单文档到 RAG 知识库"""
    try:
        logger.info(f"RAG ingest: {title}")
        rag_service = get_rag_service()
        result = rag_service.ingest_document(text=text, title=title)
        return result
    except Exception as e:
        logger.error(f"Error in RAG ingest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag/seed")
async def rag_seed(
    data_dir: str = "data/raw/1998",
    collection: str = "gazetteer_chunks",
    rebuild: bool = True,
):
    """从文本目录批量灌入 RAG 知识库"""
    try:
        project_root = Path(__file__).resolve().parents[2]
        full_data_dir = project_root / data_dir
        if not full_data_dir.exists():
            raise HTTPException(status_code=400, detail=f"数据目录不存在: {full_data_dir}")

        SKIP_FILES = {"图片.txt", "封面.txt", "目录 (2).txt"}
        texts = []
        for txt_file in sorted(full_data_dir.glob("*.txt")):
            if txt_file.name in SKIP_FILES:
                continue
            try:
                content = txt_file.read_text(encoding="utf-8").strip()
                if len(content) < 50:
                    continue
                texts.append({
                    "title": txt_file.stem,
                    "text": content,
                    "metadata": {"source": str(txt_file)},
                })
            except Exception as e:
                logger.warning(f"加载失败 {txt_file.name}: {e}")

        if not texts:
            raise HTTPException(status_code=400, detail="没有找到有效的文本文件")

        logger.info(f"开始灌入 {len(texts)} 个文件")

        rag_service = get_rag_service()
        original_collection = rag_service.collection_name
        try:
            rag_service.collection_name = collection
            retriever = rag_service._get_retriever()
            vector_client = retriever.vector_client  # ChromaDB (was misnamed milvus_client)

            if rebuild and vector_client.has_collection(collection):
                vector_client.drop_collection(collection)
                logger.info(f"已删除旧 collection: {collection}")
            if not vector_client.has_collection(collection):
                embedder = rag_service._get_embedder()
                vector_client.create_collection(collection, dimension=embedder.embedding_dim)

            results = rag_service.ingest_documents(texts)
            total_chunks = sum(r.get("chunk_count", 0) for r in results if r.get("status") == "success")

            return {
                "status": "success",
                "collection": collection,
                "total_docs": len(texts),
                "total_chunks": total_chunks,
                "data_dir": str(full_data_dir),
            }
        finally:
            rag_service.collection_name = original_collection

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in RAG seed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rag/status")
async def rag_status():
    """获取 RAG 系统状态"""
    try:
        rag_service = get_rag_service()
        # 触发各组件初始化（确保 status 反映真实状态）
        vector_client = rag_service._get_retriever().vector_client
        rag_service._get_generator()

        collections = []
        for name in ["gazetteer_chunks"]:
            if vector_client.has_collection(name):
                try:
                    col = vector_client.get_collection(name)
                    collections.append({"name": name, "count": col.count(), "exists": True})
                except Exception:
                    collections.append({"name": name, "exists": True, "count": "unknown"})
            else:
                collections.append({"name": name, "exists": False, "count": 0})

        try:
            embedder = rag_service._get_embedder()
            if embedder._loaded:
                embedder_status = {
                    "model": embedder.model_name,
                    "device": embedder.device,
                    "dimension": embedder.embedding_dim,
                    "status": "loaded" if embedder.model else "tfidf_fallback",
                }
            else:
                embedder_status = {"status": "未加载"}
        except Exception as e:
            embedder_status = {"status": "加载失败", "error": str(e)[:200]}

        gen = rag_service.generator
        llm_provider = "unknown"
        if gen is not None:
            if hasattr(gen, "_ollama") and gen._ollama is not None:
                llm_provider = "ollama:ready" if gen._ollama.is_available() else "ollama:down"
            elif hasattr(gen, "_ollama"):
                llm_provider = "ollama:down"
            else:
                llm_provider = gen.__class__.__name__

        return {
            "status": "operational",
            "collections": collections,
            "embedder": embedder_status,
            "llm_provider": llm_provider,
            "embedding_dimension": rag_service.embedding_dim,
        }
    except Exception as e:
        logger.error(f"Error in RAG status: {e}")
        return {"status": "error", "error": str(e), "collections": [], "embedder": "unknown"}


# ============================================================
# OCR (古籍识别)
# ============================================================

@router.get("/ocr/status")
async def ocr_status():
    """OCR 服务状态（不触发模型下载）"""
    try:
        from ..ocr.providers import ALIYUN_AVAILABLE, DEFAULT_PROVIDER, provider_availability
        avail = provider_availability()
        return {
            "status": "operational",
            "providers": avail,
            "default_provider": DEFAULT_PROVIDER,
            "model_load": "lazy",
            "ready": True,
        }
    except Exception as e:
        logger.error(f"Error in OCR status: {e}")
        return {"status": "error", "error": str(e)}


@router.get("/ocr/providers")
async def ocr_providers():
    """详细列出每个 provider 的能力与可用性"""
    from ..ocr.providers import (
        ALIYUN_AVAILABLE,
        DEFAULT_PROVIDER,
        provider_availability,
    )
    avail = provider_availability()
    details = {
        "easyocr": {
            "available": avail["easyocr"],
            "tier": "fallback",
            "quality": "low",
            "languages": ["ch_sim", "en"],
            "size_mb": 100,
            "note": "竖排繁体古籍识别效果差",
        },
        "paddleocr": {
            "available": avail["paddleocr"],
            "tier": "local",
            "quality": "high",
            "languages": ["ch_sim", "ch_cht", "en"],
            "size_mb": 200,
            "note": "Windows 兼容性差（paddlepaddle + langchain 冲突）",
        },
        "rapidocr": {
            "available": avail["rapidocr"],
            "tier": "local",
            "quality": "high",
            "languages": ["ch_sim", "ch_cht", "en"],
            "size_mb": 50,
            "note": "推荐默认：ONNX 后端、跨平台稳",
        },
        "aliyun": {
            "available": avail["aliyun"],
            "tier": "cloud",
            "quality": "best",
            "languages": ["ch_sim", "ch_cht", "ancient"],
            "size_mb": None,
            "note": "古籍识别最强，需 ALIYUN_OCR_APP_CODE 环境变量",
        },
    }
    return {
        "default": DEFAULT_PROVIDER,
        "providers": details,
    }


@router.post("/ocr/recognize")
async def ocr_recognize(
    file: UploadFile = File(...),
    provider: str = None,  # None 时走默认（rapidocr）
    detect_variants: bool = True,
    detect_taboo: bool = True,
):
    """OCR 识别单张图片"""
    from ..ocr.providers import ALIYUN_AVAILABLE, DEFAULT_PROVIDER, provider_availability

    # 缺省 provider
    if not provider:
        provider = DEFAULT_PROVIDER

    avail = provider_availability()

    if provider == "aliyun" and not avail["aliyun"]:
        raise HTTPException(
            status_code=400,
            detail="Aliyun OCR 未配置（需 ALIYUN_OCR_APP_CODE 或 ALIYUN_ACCESS_KEY_* 环境变量）",
        )
    if provider not in ("easyocr", "paddleocr", "rapidocr", "aliyun"):
        raise HTTPException(status_code=400, detail=f"未知 provider: {provider}")
    if not avail.get(provider, False):
        raise HTTPException(
            status_code=400,
            detail=f"provider '{provider}' 当前不可用（未安装 / 未配置）",
        )

    suffix = Path(file.filename or "image.png").suffix.lower() or ".png"
    if suffix not in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"):
        raise HTTPException(status_code=400, detail=f"不支持的图片格式: {suffix}")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件超过 20MB")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if provider == "easyocr":
            processor = get_ocr_processor()
        else:
            from ..ocr.processor import OCRProcessor
            processor = OCRProcessor(provider=provider)
        result = processor.process_image(
            tmp_path,
            detect_variants=detect_variants,
            detect_taboo=detect_taboo,
        )
        return result
    except Exception as e:
        logger.error(f"OCR recognize error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


@router.post("/ocr/batch")
async def ocr_batch(
    files: List[UploadFile] = File(...),
    provider: str = "easyocr",
):
    """批量 OCR 识别（≤10 张，总大小 ≤20MB）"""
    from ..ocr.providers import ALIYUN_AVAILABLE

    if provider == "aliyun" and not ALIYUN_AVAILABLE:
        raise HTTPException(status_code=400, detail="Aliyun OCR 未配置")
    if provider not in ("easyocr", "paddleocr", "aliyun"):
        raise HTTPException(status_code=400, detail=f"未知 provider: {provider}")
    if len(files) > 10:
        raise HTTPException(status_code=413, detail=f"批量最多 10 张（收到 {len(files)}）")

    blobs = []
    total = 0
    for f in files:
        content = await f.read()
        total += len(content)
        blobs.append((f.filename or "image.png", content))
    if total > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"批量总大小超 20MB（{total/1024/1024:.1f}MB）")

    results = []
    for filename, content in blobs:
        suffix = Path(filename).suffix.lower() or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            if provider == "easyocr":
                processor = get_ocr_processor()
            else:
                from ..ocr.processor import OCRProcessor
                processor = OCRProcessor(provider=provider)
            result = processor.process_image(tmp_path)
            result["filename"] = filename
            results.append(result)
        except Exception as e:
            logger.error(f"OCR batch error on {filename}: {e}")
            results.append({"filename": filename, "error": str(e), "pages": []})
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    return {"status": "success", "count": len(results), "results": results}


@router.get("/ocr/variants")
async def ocr_variants(limit: int = 100):
    """异体字映射表统计 + 前 N 条样本"""
    try:
        from ..ocr.variant_map import VARIANT_CHAR_MAP, TABOO_RULES
        sample = [
            {"standard": std, "variants": sorted(list(variants))}
            for std, variants in list(VARIANT_CHAR_MAP.items())[:limit]
        ]
        return {
            "total_variants": len(VARIANT_CHAR_MAP),
            "total_taboo_rules": len(TABOO_RULES),
            "sample_size": len(sample),
            "sample": sample,
        }
    except Exception as e:
        logger.error(f"Error in OCR variants: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ocr/samples")
async def ocr_samples():
    """列出样本图（kangxi 系列）"""
    try:
        project_root = Path(__file__).resolve().parents[2]
        sample_dirs = [
            project_root / "data" / "raw" / "kangxi",
            project_root / "data" / "raw",
        ]
        samples = []
        seen = set()
        for sample_dir in sample_dirs:
            if not sample_dir.exists():
                continue
            for ext in ("*.png", "*.jpg", "*.jpeg"):
                for img in sorted(sample_dir.glob(ext)):
                    if img.name in seen or not img.name.startswith("kangxi"):
                        continue
                    seen.add(img.name)
                    samples.append({
                        "name": img.name,
                        "path": str(img.relative_to(project_root)),
                        "size_kb": img.stat().st_size // 1024,
                        "url": f"/api/v1/ocr/samples/{img.name}",
                    })
        return {"count": len(samples), "samples": samples}
    except Exception as e:
        logger.error(f"Error in OCR samples: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ocr/samples/{filename}")
async def ocr_sample_file(filename: str):
    """直出样本图 PNG/JPG bytes"""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    project_root = Path(__file__).resolve().parents[2]
    candidates = [
        project_root / "data" / "raw" / "kangxi" / filename,
        project_root / "data" / "raw" / filename,
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            if candidate.suffix.lower() in (".png", ".jpg", ".jpeg"):
                return FileResponse(candidate)
    raise HTTPException(status_code=404, detail=f"样本图不存在: {filename}")


# ============================================================
# KG (知识图谱)
# ============================================================

@router.get("/kg/sources")
async def kg_sources():
    """列出所有可用数据源"""
    from ..database import source_router
    sources = source_router.list_sources()
    return {
        "status": "success",
        "sources": [
            {"name": k, "label": v.get("label", k), "enabled": v.get("enabled", False)}
            for k, v in sources.items()
        ],
    }


@router.get("/kg/status")
async def kg_status():
    """获取知识图谱系统状态"""
    try:
        return get_kg_service().get_kg_status()
    except Exception as e:
        logger.error(f"Error getting KG status: {e}")
        return {"status": "error", "error": str(e)}


@router.get("/kg/persons")
async def kg_list_persons(
    limit: int = 200,
    offset: int = 0,
    source: str = None,
    surname: str = None,
    has_relations: bool = False,
):
    """获取所有人物列表

    Args:
        limit: 返回上限
        offset: 跳过
        source: 数据源标识（如 "jiapu"），None 用 in-memory
        surname: 按姓过滤（拼音，仅 SQLite 源）
        has_relations: 仅返回在关系中出现的（仅 SQLite 源）
    """
    try:
        if source:
            # SQLite 数据源路径
            from ..database import jiapu_query
            persons, total = jiapu_query.list_persons(
                source=source,
                limit=limit,
                offset=offset,
                surname=surname,
                has_relations=has_relations,
            )
            return {
                "status": "success",
                "source": source,
                "persons": persons,
                "count": len(persons),
                "total": total,
            }
        # in-memory 默认路径
        service = get_kg_service()
        persons = service.get_all_persons(limit=limit)
        return {"status": "success", "source": "memory", "persons": persons, "count": len(persons)}
    except Exception as e:
        logger.error(f"Error listing persons: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kg/persons/{name}")
async def kg_get_person(name: str, depth: int = 1, source: str = None):
    """获取单个人物详情（含关系）

    注：SQLite 源时 name 应为 uri（如 p:jiapu/xxx）
    """
    try:
        if source:
            from ..database import jiapu_query
            person = jiapu_query.get_person(name, source=source)
            if not person:
                raise HTTPException(status_code=404, detail=f"人物 '{name}' 在 {source} 中未找到")
            relations = jiapu_query.get_person_relations(name, source=source)
            person["relations"] = relations
            return {"status": "success", "source": source, "person": person}
        service = get_kg_service()
        person = service.get_person_with_relations(name, depth=depth)
        if not person:
            raise HTTPException(status_code=404, detail=f"人物 '{name}' 未找到")
        return {"status": "success", "person": person}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting person {name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kg/graph")
async def kg_get_graph(limit: int = 200, offset: int = 0, source: str = None):
    """获取图谱可视化数据（ECharts 格式：nodes + links）

    SQLite 源：取一段关系 + 涉及的 person
    in-memory：取全部
    """
    try:
        if source:
            from ..database import jiapu_query
            data = jiapu_query.get_graph_subset(source=source, limit=limit, offset=offset)
        else:
            service = get_kg_service()
            data = service.get_graph_data(limit=limit)
        nodes = data.get("nodes", [])
        links = data.get("links", [])
        return {
            "status": "success",
            "source": source or "memory",
            "nodes": nodes,
            "links": links,
            "total_persons": data.get("total_persons", len(nodes)),
            "total_links": data.get("total_links", len(links)),
        }
    except Exception as e:
        logger.error(f"Error getting graph data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kg/surnames")
async def kg_top_surnames(source: str = "jiapu", limit: int = 20):
    """按姓统计 top N（仅 SQLite 源）"""
    try:
        from ..database import jiapu_query
        rows = jiapu_query.top_surnames(source=source, limit=limit)
        return {"status": "success", "source": source, "surnames": rows}
    except Exception as e:
        logger.error(f"Error getting top surnames: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kg/entity/extract")
async def kg_extract_entities(request: KGEntityExtractRequest):
    """从文本中提取实体（不存储）—— 用于 OCR 联动预览"""
    try:
        from ..kg import KGPipeline
        pipeline = KGPipeline()
        result = pipeline.build_kg_from_text(
            text=request.text,
            source=request.source,
            title=request.title,
        )
        return {
            "status": "success",
            "entities": result.get("entities", []),
            "relations": result.get("relations", []),
            "stats": result.get("stats", {}),
        }
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kg/build")
async def kg_build_pipeline(request: KGPipelineRequest):
    """从文本构建知识图谱（可选择存储）"""
    try:
        from ..kg import KGPipeline
        pipeline = KGPipeline()
        result = pipeline.build_kg_from_text(
            text=request.text,
            source=request.source,
            title=request.title,
        )

        stored_count = 0
        relation_count = 0
        if request.store:
            service = get_kg_service()
            for entity in result["entities"]:
                if entity.get("type") != "PER":
                    continue
                name = entity.get("name", "")
                if not name:
                    continue
                try:
                    service.add_person({
                        "name": name,
                        "biography": entity.get("biography", ""),
                        "dynasty": entity.get("dynasty", ""),
                        "years": entity.get("years", ""),
                        "birthplace": entity.get("location", ""),
                        "person_type": entity.get("person_type", 2),
                        "source": entity.get("source", request.source),
                    })
                    stored_count += 1
                except Exception as e:
                    logger.warning(f"Failed to store person {name}: {e}")

            for rel in result["relations"]:
                from_name = rel.get("source", "")
                to_name = rel.get("target", "")
                if not from_name or not to_name:
                    continue
                try:
                    service.add_relation(
                        from_name=from_name,
                        to_name=to_name,
                        relation_type=rel.get("relation", "RELATED"),
                        confidence=rel.get("confidence", 0.5),
                    )
                    relation_count += 1
                except Exception as e:
                    logger.warning(f"Failed to store relation {from_name}->{to_name}: {e}")

            result["stats"]["stored_entities"] = stored_count
            result["stats"]["stored_relations"] = relation_count

        return {
            "status": "success",
            "entities": result["entities"],
            "relations": result["relations"],
            "stats": result["stats"],
        }
    except Exception as e:
        logger.error(f"Error building KG: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kg/entity")
async def kg_add_entity(request: KGEntityStoreRequest):
    """添加单个实体到知识图谱"""
    try:
        service = get_kg_service()
        if not request.name:
            raise HTTPException(status_code=400, detail="name is required")
        person = service.add_person({
            "name": request.name,
            "biography": request.biography or "",
            "dynasty": request.dynasty or "",
            "years": request.years or "",
            "birthplace": request.birthplace or "",
            "title": request.title or "",
            "person_type": request.person_type or 2,
            "source": request.source or "",
        })
        return {"status": "success", "person": person}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kg/relate")
async def kg_add_relation(request: KGRelationRequest):
    """添加关系到知识图谱"""
    try:
        service = get_kg_service()
        if not request.from_name or not request.to_name:
            raise HTTPException(status_code=400, detail="from_name and to_name are required")
        relation = service.add_relation(
            from_name=request.from_name,
            to_name=request.to_name,
            relation_type=request.relation_type,
            confidence=(request.properties or {}).get("confidence", 0.5),
        )
        return {"status": "success", "relation": relation}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding relation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# KG 初始化（背景 + 同步）
# ============================================================

def _run_kg_init_background(clear: bool, corpus_path: str):
    """后台线程：运行 KG 初始化"""
    global _kg_init_state
    _kg_init_state = {
        "running": True, "completed": False, "error": None, "result": None,
    }
    try:
        from ..kg import KGPipeline
        from ..database.kg_service import identify_dynasty, post_process_relations

        project_root = Path(__file__).resolve().parents[2]
        person_file = project_root / corpus_path
        if not person_file.exists():
            raise FileNotFoundError(f"人物志文件不存在: {person_file}")

        service = get_kg_service()
        if clear:
            service.clear()

        text = person_file.read_text(encoding="utf-8")
        logger.info(f"KG background init: reading {len(text):,} chars from {person_file.name}")

        pipeline = KGPipeline()
        result = pipeline.build_kg_from_text(
            text=text,
            source=str(person_file),
            title=person_file.stem,
        )

        stored_names = set()
        for entity in result["entities"]:
            if entity.get("type") != "PER":
                continue
            name = entity.get("name", "")
            if not name or name in stored_names:
                continue
            if service.has_person(name):
                stored_names.add(name)
                continue
            bio = (entity.get("biography") or "")[:500]
            service.add_person({
                "name": name,
                "biography": bio,
                "dynasty": identify_dynasty(bio),
                "years": entity.get("years", ""),
                "birthplace": entity.get("location", ""),
                "person_type": entity.get("person_type", 2),
                "source": str(person_file),
            })
            stored_names.add(name)

        relations_stored = post_process_relations(service, text, stored_names, result["relations"])

        stats = service.get_stats()
        samples = [p["name"] for p in service.get_all_persons(limit=5)]
        _kg_init_state["result"] = KGInitResponse(
            status="success",
            persons_stored=len(stored_names),
            relations_stored=relations_stored,
            total_persons=stats["person_count"],
            total_relations=stats["relation_count"],
            sample_persons=samples,
        )
        _kg_init_state["completed"] = True
        logger.info(f"KG background init complete: {len(stored_names)} persons, {relations_stored} relations")
    except Exception as e:
        logger.error(f"KG background init error: {e}")
        _kg_init_state["error"] = str(e)
        _kg_init_state["completed"] = True
    finally:
        _kg_init_state["running"] = False


@router.get("/kg/init/status", response_model=KGInitStatusResponse)
async def kg_init_status():
    return KGInitStatusResponse(
        running=_kg_init_state["running"],
        completed=_kg_init_state["completed"],
        error=_kg_init_state["error"],
        result=_kg_init_state["result"],
    )


@router.post("/kg/init", response_model=KGInitResponse)
async def kg_init(
    corpus_path: str = "data/raw/1998/第二十一编人物.txt",
    clear: bool = False,
    background: bool = False,
):
    """
    从人物志文本初始化知识图谱。
    corpus_path 默认为 1998 版固安县志人物志，可指定其他路径。
    """
    if _kg_init_state["running"]:
        raise HTTPException(status_code=409, detail="KG 初始化已在运行中")
    if _kg_init_state["completed"] and _kg_init_state["result"] and not clear:
        return _kg_init_state["result"]

    if background:
        import threading
        thread = threading.Thread(target=_run_kg_init_background, args=(clear, corpus_path))
        thread.daemon = True
        thread.start()
        return KGInitResponse(
            status="started",
            persons_stored=0, relations_stored=0,
            total_persons=0, total_relations=0,
            sample_persons=[],
        )

    # 同步执行
    try:
        from ..kg import KGPipeline
        from ..database.kg_service import identify_dynasty, post_process_relations

        project_root = Path(__file__).resolve().parents[2]
        person_file = project_root / corpus_path
        if not person_file.exists():
            raise HTTPException(status_code=404, detail=f"人物志文件不存在: {person_file}")

        service = get_kg_service()
        if clear:
            service.clear()

        text = person_file.read_text(encoding="utf-8")
        logger.info(f"KG init: reading {len(text):,} chars from {person_file.name}")

        pipeline = KGPipeline()
        result = pipeline.build_kg_from_text(
            text=text,
            source=str(person_file),
            title=person_file.stem,
        )

        stored_names = set()
        for entity in result["entities"]:
            if entity.get("type") != "PER":
                continue
            name = entity.get("name", "")
            if not name or name in stored_names:
                continue
            if service.has_person(name):
                stored_names.add(name)
                continue
            bio = (entity.get("biography") or "")[:500]
            service.add_person({
                "name": name,
                "biography": bio,
                "dynasty": identify_dynasty(bio),
                "years": entity.get("years", ""),
                "birthplace": entity.get("location", ""),
                "source": str(person_file),
            })
            stored_names.add(name)

        relations_stored = post_process_relations(service, text, stored_names, result["relations"])

        stats = service.get_stats()
        samples = [p["name"] for p in service.get_all_persons(limit=5)]
        logger.info(
            f"KG init complete: {len(stored_names)} persons, {relations_stored} relations. "
            f"Total: {stats['person_count']} persons, {stats['relation_count']} relations"
        )
        return KGInitResponse(
            status="success",
            persons_stored=len(stored_names),
            relations_stored=relations_stored,
            total_persons=stats["person_count"],
            total_relations=stats["relation_count"],
            sample_persons=samples,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in KG init: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def register_routes(app):
    app.include_router(router)
    logger.info("Routes registered")
