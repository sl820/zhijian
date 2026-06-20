"""
RAG 路由：智能问答 + 知识库状态 + 灌库

Why：从 routes.py 拆出，让 M8/M9 的 RAG 改造集中可改。
How to apply：app.include_router(rag_router.router)
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ._shared import (
    RAGRequest, RAGResponse, EvidenceItem, EvidenceResponse, get_rag_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

# RAG (智能问答)
# ============================================================

@router.post("/rag/ask", response_model=EvidenceResponse)
async def rag_ask(request: RAGRequest, source: str = None):
    """RAG 智能问答接口

    R9 升级（2026-06-18）：
      - response_model 改为 EvidenceResponse（统一证据链）
      - evidence 字段从 RAG sources 转换（source/chunk_id/confidence/snippet）
      - 任何异常 → fallback=True + 兜底文案 + 单条 fallback evidence
      - 前端可直接渲染 evidence chips + method 标签

    竞赛交付改造（2026-06-18）：
      - 任何异常（embedder 加载失败 / collection 缺失 / Ollama 宕机 / LLM timeout）
        都不再 500，而是返回结构化 fallback {answer, evidence: [...]}
      - 前端拿到的 response 永远是 EvidenceResponse，不会因为网络问题炸 UI

    Args:
        request: 问题 + top_k
        source: 数据源过滤（"jiapu" / "memory" / None=全源）。
            None 或 "all"：跨所有 collection 检索。
    """
    FALLBACK_ANSWER = "当前无足够史料支撑该问题，请尝试其他朝代或家族进行问询。"
    FALLBACK_EVIDENCE_TEXT = "暂无证据（RAG 检索失败或 collection 为空）"

    logger.info(f"RAG question: {request.question} (source={source})")
    try:
        rag_service = get_rag_service()
        if source:
            result = rag_service.ask_by_source(
                question=request.question,
                source=source,
                top_k=request.top_k,
            )
        else:
            result = rag_service.ask(question=request.question, top_k=request.top_k)

        answer = result.get("answer", "")
        sources = result.get("sources", []) or []

        # 防御：空 answer 也走 fallback 文案
        if not answer or not answer.strip():
            answer = FALLBACK_ANSWER

        # 包装成 EvidenceItem 列表
        evidence_list: List[EvidenceItem] = []
        for s in sources:
            try:
                # RAG source dict 字段: text/source/score/chunk_id
                score = float(s.get("score", 0))
                # ChromaDB distance → 转为 confidence（越小越好，转换 0-1）
                confidence = max(0.0, min(1.0, 1.0 - score))
                evidence_list.append(EvidenceItem(
                    source=f"rag:{s.get('source', 'unknown')[:30]}",
                    node_ids=[],  # RAG 不知道具体节点 URI，留空
                    edge_ids=[],
                    confidence=confidence,
                    snippet=(s.get("text") or "")[:200],
                    title=s.get("source"),
                ))
            except Exception as e:
                logger.warning(f"[rag] evidence 包装失败: {e}")
                continue

        # 兜底：evidence 为空时塞 1 条 fallback
        is_fallback = False
        if not evidence_list:
            evidence_list.append(EvidenceItem(
                source="fallback",
                node_ids=[],
                edge_ids=[],
                confidence=0.0,
                snippet=FALLBACK_EVIDENCE_TEXT,
                title="兜底证据",
            ))
            is_fallback = True

        return EvidenceResponse(
            answer=answer,
            evidence=evidence_list,
            method="retrieval + llm (qwen2.5-3b via ollama)",
            fallback=is_fallback,
        )
    except Exception as e:
        logger.error(f"Error in RAG ask: {e}")
        # 竞赛交付：兜底永远返回 200 + 结构化 response
        return EvidenceResponse(
            answer=FALLBACK_ANSWER,
            evidence=[EvidenceItem(
                source="fallback",
                node_ids=[],
                edge_ids=[],
                confidence=0.0,
                snippet=f"系统异常：{str(e)[:150]}",
                title="兜底证据",
            )],
            method="fallback",
            fallback=True,
            fallback_reason=str(e)[:200],
        )


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

        collections = rag_service.list_collections()

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


@router.get("/rag/sources")
async def rag_sources():
    """列出所有 RAG 数据源（=zhijian_* collections）。"""
    try:
        rag_service = get_rag_service()
        collections = rag_service.list_collections()
        return {"status": "success", "collections": collections}
    except Exception as e:
        logger.error(f"Error in RAG sources: {e}")
        return {"status": "error", "error": str(e), "collections": []}


# ============================================================
