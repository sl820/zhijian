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
