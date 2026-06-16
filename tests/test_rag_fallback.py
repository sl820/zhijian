"""
M9 RAG 离线降级测试

覆盖：
- ollama 不可用时 ask() 仍返回 200 + llm_unavailable=true
- 检索片段照常返回
- generate_with_fallback 模板化答案
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================
# ask() fallback
# ============================================================

class TestAskFallback:
    """ask() 应在 Ollama 不可用时走 fallback 模板。"""

    @pytest.fixture
    def temp_rag(self, tmp_path):
        from app import config as app_config
        from app.api import _shared

        original = app_config.CHROMA_PERSIST_DIR
        app_config.CHROMA_PERSIST_DIR = tmp_path / "chroma"
        _shared._rag_service = None

        yield tmp_path

        app_config.CHROMA_PERSIST_DIR = original
        _shared._rag_service = None

    def test_ask_returns_llm_unavailable_flag(self, temp_rag):
        """ask() 返回字典应含 llm_unavailable 字段"""
        from app.api import _shared
        rag = _shared.get_rag_service()

        # Mock generator：模拟 ollama 不可用
        mock_gen = MagicMock()
        mock_ollama = MagicMock()
        mock_ollama.is_available.return_value = False
        mock_gen._ollama = mock_ollama
        mock_gen.generate_with_fallback.return_value = "抱歉，LLM 暂不可用..."

        with patch.object(rag, "_get_generator", return_value=mock_gen):
            with patch.object(rag, "generator", mock_gen, create=True):
                result = rag.ask("苏辙的父亲是谁？")

        assert "llm_unavailable" in result
        # 没有 collection 时 sources 为空但答案字段一定有
        assert "answer" in result
        assert "sources" in result

    def test_ask_by_source_returns_llm_unavailable_flag(self, temp_rag):
        from app.api import _shared
        rag = _shared.get_rag_service()

        mock_gen = MagicMock()
        mock_ollama = MagicMock()
        mock_ollama.is_available.return_value = False
        mock_gen._ollama = mock_ollama
        mock_gen.generate_with_fallback.return_value = "fallback answer"

        with patch.object(rag, "_get_generator", return_value=mock_gen):
            with patch.object(rag, "generator", mock_gen, create=True):
                result = rag.ask_by_source("test", source="jiapu")

        assert "llm_unavailable" in result
        assert result["queried_collections"] == []  # no collections


# ============================================================
# generate_with_fallback 模板
# ============================================================

class TestFallbackTemplate:
    """generate_with_fallback 应返回有意义文本。"""

    def test_fallback_with_context(self):
        """有 context 时给出参考来源列表"""
        from app.rag.generator import Generator
        gen = Generator(config={"provider": "ollama"})

        # Mock generator.generate 抛异常（patch method）
        context = [
            {"source": "苏辙传", "text": "苏辙字子由..."},
            {"source": "宋史", "text": "苏辙..."},
        ]

        with patch.object(gen, "generate", side_effect=RuntimeError("connection refused")):
            result = gen.generate_with_fallback("苏辙是谁？", context)

        # 应返回有意义文本
        assert "苏辙传" in result or "宋史" in result or "抱歉" in result

    def test_fallback_empty_context(self):
        from app.rag.generator import Generator
        gen = Generator(config={"provider": "ollama"})
        result = gen.generate_with_fallback("test", [])
        # 空 context 应有兜底文案
        assert isinstance(result, str)
        assert len(result) > 0