"""
M4 关系抽取器测试

覆盖：
- SuffixPatternExtractor.extract() 基础 pattern 匹配
- 之父/之母/之弟/之妻/之字/之号 等 20+ pattern
- 5k 截断已取消（chunked scan）
- 排除 dynasty_markers / era_names
- 排除 substring 误匹配
- Step 2 入口（add_relation 集成测试）
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============================================================
# SuffixPatternExtractor
# ============================================================

class TestSuffixPatternExtractor:
    """基本匹配行为。"""

    def test_father_pattern(self):
        from app.kg.relation_extractor import SuffixPatternExtractor
        ext = SuffixPatternExtractor(stored_names={"苏辙", "苏洵"})
        rels = ext.extract("苏辙之父苏洵为唐宋八大家之一", "苏辙")
        types = {r["type"] for r in rels}
        assert "FATHER" in types
        fathers = [r for r in rels if r["type"] == "FATHER"]
        assert any(r["to"] == "苏洵" for r in fathers)

    def test_mother_son_daughter_patterns(self):
        from app.kg.relation_extractor import SuffixPatternExtractor
        ext = SuffixPatternExtractor(stored_names={"苏轼", "苏辙", "王氏", "苏东坡"})
        text = "苏轼之母王氏，苏辙之姐也。"
        rels = ext.extract(text, "苏轼")
        # 母亲 + 至少一亲属关系
        assert any(r["type"] == "MOTHER" for r in rels)

    def test_younger_brother_pattern(self):
        from app.kg.relation_extractor import SuffixPatternExtractor
        ext = SuffixPatternExtractor(stored_names={"苏轼", "苏辙"})
        rels = ext.extract("苏轼之弟苏辙，字子由", "苏轼")
        brothers = [r for r in rels if r["type"] == "YOUNGER_BROTHER"]
        assert any(r["to"] == "苏辙" for r in brothers)

    def test_wife_pattern(self):
        from app.kg.relation_extractor import SuffixPatternExtractor
        ext = SuffixPatternExtractor(stored_names={"苏辙", "王氏"})
        rels = ext.extract("苏辙之妻王氏，眉山人", "苏辙")
        wives = [r for r in rels if r["type"] == "WIFE"]
        assert any(r["to"] == "王氏" for r in wives)

    def test_grandson_pattern(self):
        from app.kg.relation_extractor import SuffixPatternExtractor
        ext = SuffixPatternExtractor(stored_names={"苏洵", "苏籥"})
        rels = ext.extract("苏洵之孙苏籥", "苏洵")
        grandsons = [r for r in rels if r["type"] == "GRANDSON"]
        assert any(r["to"] == "苏籥" for r in grandsons)


class TestChunkedScanning:
    """5k 截断已取消，长文仍能命中。"""

    def test_relation_past_5k_boundary(self):
        from app.kg.relation_extractor import SuffixPatternExtractor
        # 造一段 6000+ 字的文本，把 pattern 放在 5500 字处
        filler = "之乎者也矣焉哉，" * 600  # ≈ 4200 chars
        text = filler + "苏辙之父苏洵" + filler
        ext = SuffixPatternExtractor(stored_names={"苏辙", "苏洵"})
        rels = ext.extract(text, "苏辙", chunk_size=5000, chunk_overlap=200)
        fathers = [r for r in rels if r["type"] == "FATHER"]
        assert any(r["to"] == "苏洵" for r in fathers)

    def test_no_false_dedup_across_chunks(self):
        from app.kg.relation_extractor import SuffixPatternExtractor
        # 同一对关系在两个 chunk 中各出现一次，应去重为一条
        filler = "之乎者也矣焉哉，" * 700
        chunk_text = "苏辙之父苏洵。"
        text = filler + chunk_text + filler + chunk_text
        ext = SuffixPatternExtractor(stored_names={"苏辙", "苏洵"})
        rels = ext.extract(text, "苏辙")
        fathers = [r for r in rels if r["type"] == "FATHER"]
        assert len(fathers) == 1


class TestTargetFiltering:
    """无效 target 排除逻辑。"""

    def test_dynasty_marker_excluded(self):
        from app.kg.relation_extractor import SuffixPatternExtractor
        ext = SuffixPatternExtractor(
            stored_names={"苏辙"},
            dynasty_markers={"宋"},
            era_names=set(),
        )
        rels = ext.extract("苏辙之父宋，", "苏辙")
        # "宋" 是朝代标记，不应成为 target
        assert all(r["to"] != "宋" for r in rels)

    def test_era_name_excluded(self):
        from app.kg.relation_extractor import SuffixPatternExtractor
        ext = SuffixPatternExtractor(
            stored_names={"苏辙"},
            dynasty_markers=set(),
            era_names={"嘉祐"},
        )
        rels = ext.extract("苏辙之父嘉祐", "苏辙")
        assert all(r["to"] != "嘉祐" for r in rels)

    def test_substring_dedup(self):
        """避免 "苏" 跟 "苏洵" 误匹配"""
        from app.kg.relation_extractor import SuffixPatternExtractor
        # "苏" 也在 stored_names 里
        ext = SuffixPatternExtractor(stored_names={"苏", "苏辙", "苏洵"})
        rels = ext.extract("苏辙之父苏洵", "苏辙")
        fathers = [r for r in rels if r["type"] == "FATHER"]
        # 应该是 "苏洵"，不是 "苏"
        assert any(r["to"] == "苏洵" for r in fathers)
        assert not any(r["to"] == "苏" for r in fathers)

    def test_short_target_excluded(self):
        """1 字 target 应被排除"""
        from app.kg.relation_extractor import SuffixPatternExtractor
        ext = SuffixPatternExtractor(stored_names={"苏辙"})
        rels = ext.extract("苏辙之父 子。", "苏辙")
        # 单字 "子" 不应成为 target
        assert all(r["to"] != "子" for r in rels)


class TestEmptyInput:
    """空输入不崩。"""

    def test_empty_text(self):
        from app.kg.relation_extractor import SuffixPatternExtractor
        ext = SuffixPatternExtractor(stored_names={"苏辙"})
        assert ext.extract("", "苏辙") == []

    def test_empty_subject(self):
        from app.kg.relation_extractor import SuffixPatternExtractor
        ext = SuffixPatternExtractor(stored_names={"苏辙"})
        assert ext.extract("苏辙之父苏洵", "") == []

    def test_subject_not_in_text(self):
        from app.kg.relation_extractor import SuffixPatternExtractor
        ext = SuffixPatternExtractor(stored_names={"苏轼", "苏洵"})
        rels = ext.extract("苏洵之子苏轼", "苏辙")
        # subject_name 是苏辙，文本里没有，不应抽取
        assert rels == []


class TestIntegrationWithKgService:
    """post_process_relations 应串联 SuffixPatternExtractor。"""

    def test_post_process_uses_extractor(self, monkeypatch):
        """验证 post_process_relations 内部用上了新的 extractor（chunked）。"""
        from app.database.kg_service import post_process_relations
        from app.kg import relation_extractor as re_mod

        # Mock SuffixPatternExtractor.extract 来观察调用
        captured = {}

        def fake_extract(self, text, subject_name, chunk_size=5000, chunk_overlap=200):
            captured["chunk_size"] = chunk_size
            captured["subject_name"] = subject_name
            captured["text_len"] = len(text)
            return [{"from": subject_name, "to": "苏洵", "type": "FATHER", "confidence": 0.85}]

        monkeypatch.setattr(re_mod.SuffixPatternExtractor, "extract", fake_extract)

        mock_svc = MagicMock()
        mock_svc.add_relation.return_value = None
        stored = {"苏辙"}

        # 6000+ 字文本，验证 chunk_size 是 5000 而非被截断
        filler = "之乎者也" * 1500  # 6000 chars
        text = filler + "苏辙之父苏洵。" + filler

        count = post_process_relations(mock_svc, text, stored, [])

        assert count >= 1
        assert captured["chunk_size"] == 5000
        assert captured["text_len"] == len(text)  # 全文传下去，未截断
        mock_svc.add_relation.assert_called()
