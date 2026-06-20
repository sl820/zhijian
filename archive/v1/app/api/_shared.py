"""
API 共享层：service 单例 + Pydantic models + OCR_ENABLED 检查

Why：4 个 router (system/rag/ocr/kg) 都需要 service 单例和共享模型，
抽到 _shared.py 避免循环依赖和重复定义。
How to apply：4 个 router 通过 `from ._shared import ...` 引入。
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


# ============================================================
# R9 统一证据链结构（P0 — 数字人文研究系统升级）
# ============================================================
# Why：所有 RAG / KG evidence / insights 端点必须返回统一结构，
#      前端可以无差别渲染 evidence chips + fallback 徽章。
# How：所有「回答类」端点的 response_model 改用 EvidenceResponse，
#      在 router 内部把旧结构包装成新结构。
#
# 强约束：
#   - 禁止纯文本回答（answer 字段必须填）
#   - 禁止无 evidence 输出（evidence 至少 1 条，或 fallback=True）
#   - 禁止无来源数据（每条 evidence 必须有 source 字段）
#   - 禁止无 method（默认 "graph_traversal + retrieval + heuristic"）

class EvidenceItem(BaseModel):
    """单条证据项 — 可被 RAG / KG evidence / insights 复用。"""
    source: str  # jiapu | cbdb | kg | rag | layout | computed | fallback
    node_ids: List[str] = []
    edge_ids: List[str] = []
    confidence: float = 0.0  # 0-1
    snippet: Optional[str] = None  # 原文片段
    title: Optional[str] = None
    metadata: Optional[Dict] = None


class EvidenceResponse(BaseModel):
    """统一证据链响应 — 所有「回答类」端点用此 schema。"""
    answer: str  # 主回答（必有，非空字符串）
    evidence: List[EvidenceItem]  # 证据列表（fallback 时可为空但会带 fallback=True）
    method: str = "graph_traversal + retrieval + heuristic"
    fallback: bool = False  # True 表示走了降级路径
    fallback_reason: Optional[str] = None
    computed_at: float = Field(default_factory=time.time)


# 兼容旧 RAGResponse 的别名（避免破坏既有调用方）
RAGResponse.evidence = []  # type: ignore
RAGResponse.method = "retrieval + llm"  # type: ignore
RAGResponse.fallback = False  # type: ignore


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



def _ocr_enabled() -> bool:
    """OCR 模块是否启用（centralized check）。"""
    from ..config import OCR_ENABLED
    return bool(OCR_ENABLED)
