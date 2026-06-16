"""
M8 RAG 分 collection 测试

覆盖：
- ask_by_source 在指定 source 下检索
- list_collections 列出 zhijian_* collections
- ingest_chroma 脚本可调通

依赖：chroma_zhijian 目录可写（每个测试用临时 dir）
"""
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================
# ask_by_source + list_collections
# ============================================================

class TestRAGBySource:
    """用临时 CHROMA_PERSIST_DIR 隔离。"""

    @pytest.fixture
    def temp_rag(self, tmp_path):
        """临时 RAG service（独立 chroma dir）。"""
        from app import config as app_config

        original = app_config.CHROMA_PERSIST_DIR
        app_config.CHROMA_PERSIST_DIR = tmp_path / "chroma"

        # 重置 _shared._rag_service 单例
        from app.api import _shared
        _shared._rag_service = None

        yield tmp_path

        app_config.CHROMA_PERSIST_DIR = original
        _shared._rag_service = None

    def test_list_collections_empty(self, temp_rag):
        """空库时 list_collections 应返回空列表"""
        from app.api import _shared
        rag = _shared.get_rag_service()
        assert rag.list_collections() == []

    def test_ask_by_source_no_collections(self, temp_rag):
        """没有任何 collection 时 ask_by_source 应不崩"""
        from app.api import _shared
        rag = _shared.get_rag_service()
        result = rag.ask_by_source("苏辙的父亲", source="jiapu")
        # 检索不到任何东西，但应正常返回
        assert "answer" in result
        assert "sources" in result
        assert isinstance(result["sources"], list)

    def test_ask_by_source_all_with_no_collections(self, temp_rag):
        """source=all 时也无 collection"""
        from app.api import _shared
        rag = _shared.get_rag_service()
        result = rag.ask_by_source("test", source="all")
        assert result["queried_collections"] == []  # 没 collection 就不查

    def test_ask_by_source_default_fallback(self, temp_rag):
        """source=None 时等价于 all"""
        from app.api import _shared
        rag = _shared.get_rag_service()
        result = rag.ask_by_source("test", source=None)
        assert "answer" in result


# ============================================================
# scripts/ingest_chroma.py CLI 烟雾测试
# ============================================================

class TestIngestScript:
    """验证脚本可调通（用 mock 跳过实际 embedding）。"""

    def test_ingest_memory_works(self, tmp_path):
        """memory 源：用 in-memory KG 灌库"""
        from app import config as app_config
        from app.api import _shared

        # 隔离 CHROMA_PERSIST_DIR
        original = app_config.CHROMA_PERSIST_DIR
        app_config.CHROMA_PERSIST_DIR = tmp_path / "chroma"
        _shared._rag_service = None

        try:
            from scripts.ingest_chroma import extract_from_memory_kg, ingest_source
            texts = extract_from_memory_kg()
            # 73 个样本里可能有 biography 为空的，过滤后 >= 0
            assert isinstance(texts, list)
            if texts:
                result = ingest_source("memory", texts, rebuild=True)
                assert result["status"] == "success"
                assert result["collection"] == "zhijian_memory"
                assert result["total_chunks"] > 0
        finally:
            app_config.CHROMA_PERSIST_DIR = original
            _shared._rag_service = None

    def test_ingest_empty_texts(self, tmp_path):
        """空文本列表应返回 skipped，不崩"""
        from scripts.ingest_chroma import ingest_source
        result = ingest_source("nonexistent", [], rebuild=False)
        assert result["status"] == "skipped"
        assert "no texts" in result["reason"]