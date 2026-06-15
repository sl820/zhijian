"""
志鉴系统精简版集成测试

精简后仅 RAG + KG 两个模块，故只测试这两个模块的导入与基础功能。
"""
import sys
import tempfile
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================
# 导入测试
# ============================================================

class TestImports:
    def test_rag_imports(self):
        from app.rag.chunker import TextChunker
        from app.rag.embedder import Embedder
        from app.rag.retriever import Retriever, BM25
        from app.rag.generator import Generator
        from app.rag.rag_service import RAGService, get_rag_service
        assert all([TextChunker, Embedder, Retriever, BM25, Generator, RAGService, get_rag_service])

    def test_kg_imports(self):
        from app.database.kg_service import KnowledgeGraphService
        from app.kg.pipeline import KGPipeline
        assert KnowledgeGraphService is not None
        assert KGPipeline is not None

    def test_llm_imports(self):
        from app.llm.ollama_client import OllamaClient
        assert OllamaClient is not None

    def test_api_routes_imports(self):
        from app.api.routes import (
            router,
            get_rag_service,
            get_kg_service,
        )
        assert router is not None
        assert callable(get_rag_service)
        assert callable(get_kg_service)

    def test_config_exports(self):
        from app import config
        assert hasattr(config, "OLLAMA_BASE_URL")
        assert hasattr(config, "LLM_MODEL")
        assert hasattr(config, "CHROMA_PERSIST_DIR")
        assert hasattr(config, "KG_PERSIST_PATH")
        assert hasattr(config, "DYNASTY_MARKERS")


# ============================================================
# BM25 / Chunker 基础
# ============================================================

class TestRAGCore:
    def test_bm25_basic(self):
        from app.rag.retriever import BM25
        bm25 = BM25()
        corpus = [
            "清苑县历史悠久",
            "吳氏居焉世为农",
            "苏轼字子瞻眉山人",
        ]
        bm25.fit(corpus)
        results = bm25.search("吳氏", top_k=2)
        assert len(results) <= 2
        assert all("score" in r for r in results)

    def test_chunker_basic(self):
        from app.rag.chunker import TextChunker
        chunker = TextChunker(max_tokens=50, overlap_tokens=10)
        text = "卷一·总志。清苑县历史悠久，世为农。吳氏居焉。"
        chunks_by_chapter = chunker.chunk(text, strategy="by_chapter")
        chunks_by_tokens = chunker.chunk(text, strategy="by_max_tokens")
        assert isinstance(chunks_by_chapter, list)
        assert isinstance(chunks_by_tokens, list)


# ============================================================
# KG in-memory 单元测试
# ============================================================

class TestKGService:
    @pytest.fixture
    def fresh_kg(self):
        from app.database.kg_service import KnowledgeGraphService
        with tempfile.TemporaryDirectory() as tmpdir:
            yield KnowledgeGraphService(persist_path=Path(tmpdir) / "kg_test.json")

    def test_add_and_query_person(self, fresh_kg):
        svc = fresh_kg
        svc.add_person({"name": "测试人物A", "dynasty": "唐", "biography": "生于京兆"})
        assert svc.has_person("测试人物A")
        got = svc.get_person_with_relations("测试人物A")
        assert got["name"] == "测试人物A"
        assert got["dynasty"] == "唐"
        assert "relations" in got

    def test_add_relation_creates_stubs(self, fresh_kg):
        svc = fresh_kg
        rel = svc.add_relation("甲", "乙", "FATHER", confidence=0.9)
        assert rel["from"] == "甲"
        assert rel["to"] == "乙"
        assert rel["type"] == "FATHER"
        assert svc.has_person("甲")
        assert svc.has_person("乙")

    def test_graph_data_shape(self, fresh_kg):
        svc = fresh_kg
        svc.add_person({"name": "X", "dynasty": "宋"})
        svc.add_person({"name": "Y", "dynasty": "宋"})
        svc.add_relation("X", "Y", "FATHER")
        data = svc.get_graph_data(limit=10)
        assert "nodes" in data
        assert "links" in data
        assert len(data["nodes"]) == 2
        assert len(data["links"]) == 1
        assert data["links"][0]["source"] == "X"
        assert data["links"][0]["target"] == "Y"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
