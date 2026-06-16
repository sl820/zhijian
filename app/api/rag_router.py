"""
RAG 路由：智能问答 + 知识库状态 + 灌库

Why：从 routes.py 拆出，让 M8/M9 的 RAG 改造集中可改。
How to apply：app.include_router(rag_router.router)
"""
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ._shared import (
    RAGRequest, RAGResponse, get_rag_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

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
