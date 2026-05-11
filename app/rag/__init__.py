"""
RAG模块 - 检索增强生成问答系统

提供古籍方志的智能问答功能

主要组件:
- TextChunker: 文本分块
- Embedder: 向量嵌入
- Retriever: 混合检索
- Generator: LLM生成
- RAGService: 服务整合
"""

from .chunker import TextChunker
from .embedder import Embedder
from .retriever import Retriever, BM25
from .generator import Generator
from .rag_service import RAGService, get_rag_service

__all__ = [
    "TextChunker",
    "Embedder",
    "Retriever",
    "BM25",
    "Generator",
    "RAGService",
    "get_rag_service",
]
