"""
人物归类器测试

覆盖：
- 4 类基础规则
- 输入字段兼容（pipeline / jiapu / 旧 in-memory 三种形态）
- kg_service.add_person 集成
"""
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.kg.classifier import (
    classify_person,
    CATEGORY_CLAN,
    CATEGORY_WIFE,
    CATEGORY_OTHER,
    CATEGORY_OFFICIAL,
    CLAN_SURNAMES,
)


# ============================================================
# 基础规则
# ============================================================

class TestClanRule:
    def test_suzhe_is_clan(self):
        """苏辙：姓苏，无妻妾标识 → 0 (氏族)"""
        assert classify_person({"name": "苏辙", "family_name": "苏"}) == CATEGORY_CLAN

    def test_wanganshi_is_clan(self):
        """王安石：姓王 → 0"""
        assert classify_person({"name": "王安石", "family_name": "王"}) == CATEGORY_CLAN

    def test_li_bai_is_clan(self):
        assert classify_person({"name": "李白", "family_name": "李"}) == CATEGORY_CLAN

    def test_unknown_surname_is_other(self):
        """欧阳修：欧阳不在 CLAN_SURNAMES → 2"""
        assert classify_person({"name": "欧阳修", "family_name": "欧阳"}) == CATEGORY_OTHER


class TestWifeRule:
    def test_su_furen_is_wife(self):
        """苏夫人：姓苏 + 姓名含「夫人」→ 1 (妻妾)"""
        assert classify_person({"name": "苏夫人", "family_name": "苏"}) == CATEGORY_WIFE

    def test_su_shi_is_wife(self):
        """苏氏：姓苏 + 姓名含「氏」→ 1"""
        assert classify_person({"name": "苏氏", "family_name": "苏"}) == CATEGORY_WIFE

    def test_su_qie_is_wife(self):
        """苏妾：姓苏 + 姓名含「妾」→ 1"""
        assert classify_person({"name": "苏妾", "family_name": "苏"}) == CATEGORY_WIFE

    def test_role_of_family_qi(self):
        """jiapu 形态：role_of_family='妻' → 1"""
        assert classify_person({
            "label_chs": "王氏",
            "family_name": "王",
            "role_of_family": "妻",
        }) == CATEGORY_WIFE


class TestOfficialRule:
    def test_dynasty_and_title_non_clan(self):
        """朝代+官职 且 不是氏族 → 3 (官吏)"""
        # 欧阳修：姓欧阳不在 CLAN_SURNAMES
        assert classify_person({
            "name": "欧阳修",
            "family_name": "欧阳",
            "dynasty": "宋",
            "title": "翰林学士",
        }) == CATEGORY_OFFICIAL

    def test_dynasty_and_title_clan_stays_clan(self):
        """朝代+官职 但 是氏族 → 仍是 0 (氏族优先，按 plan 规则)"""
        # 王阳明：王氏族成员 + 明代 + 尚书 → CLAN (0)
        # 计划规则："朝代 + 官职且不是氏族 → 3"
        assert classify_person({
            "name": "王阳明",
            "family_name": "王",
            "dynasty": "明",
            "title": "尚书",
        }) == CATEGORY_CLAN

    def test_only_dynasty_is_other(self):
        """只有朝代没官职 → 2"""
        assert classify_person({
            "name": "某人",
            "dynasty": "宋",
        }) == CATEGORY_OTHER

    def test_only_title_is_other(self):
        """只有官职没朝代 → 2"""
        assert classify_person({
            "name": "某人",
            "title": "知县",
        }) == CATEGORY_OTHER


class TestDefault:
    def test_empty_dict_is_other(self):
        assert classify_person({}) == CATEGORY_OTHER

    def test_name_only_is_other(self):
        """只有 name，姓为空 → 2"""
        assert classify_person({"name": "无名氏"}) == CATEGORY_OTHER


# ============================================================
# 字段兼容
# ============================================================

class TestFieldCompat:
    def test_legacy_in_memory_format(self):
        """旧 in-memory 格式：name + dynasty + years + birthplace + title
        苏辙 name 以「苏」开头 → _extract_surname 回退取「苏」→ CLAN (0)"""
        p = {
            "name": "苏辙",
            "dynasty": "宋",
            "years": "1039-1112",
            "birthplace": "眉山",
            "title": "翰林学士",
        }
        assert classify_person(p) == CATEGORY_CLAN

    def test_legacy_format_unknown_surname(self):
        """旧格式 name 开头不是 CLAN 姓 + 有 dynasty+title → OFFICIAL (3)"""
        p = {
            "name": "欧阳修",  # 欧不在 CLAN_SURNAMES
            "dynasty": "宋",
            "title": "翰林学士",
        }
        assert classify_person(p) == CATEGORY_OFFICIAL

    def test_jiapu_format(self):
        """jiapu 格式：label_chs + family_name + role_of_family"""
        p = {
            "uri": "p:jiapu/12345",
            "label_chs": "苏辙",
            "label_cht": "蘇轍",
            "family_name": "苏",
            "family_uri": "f:jiapu/苏",
            "role_of_family": "子",
        }
        assert classify_person(p) == CATEGORY_CLAN

    def test_pipeline_format(self):
        """pipeline 抽取格式：name + biography + context
        name="苏辙" 首位「苏」→ CLAN (0)"""
        p = {
            "name": "苏辙",
            "type": "PER",
            "biography": "宋眉山人苏轼弟",
            "context": "苏辙，字子由...",
        }
        assert classify_person(p) == CATEGORY_CLAN


# ============================================================
# kg_service.add_person 集成
# ============================================================

class TestKGServiceIntegration:
    """验证 add_person 强制走 classifier，覆盖外部传入值。"""

    def _new_service(self, tmp_path):
        from app.database.kg_service import KnowledgeGraphService
        return KnowledgeGraphService(persist_path=tmp_path / "kg.json")

    def test_add_person_overrides_person_type(self, tmp_path):
        """add_person 应忽略外部传入的 person_type=2，按 classifier 重新计算。"""
        svc = self._new_service(tmp_path)
        result = svc.add_person({
            "name": "苏辙",
            "family_name": "苏",
            "person_type": 999,  # 调用方传错误值
        })
        assert result["person_type"] == CATEGORY_CLAN  # 应是 0

    def test_add_person_wife(self, tmp_path):
        svc = self._new_service(tmp_path)
        result = svc.add_person({
            "name": "苏夫人",
            "family_name": "苏",
        })
        assert result["person_type"] == CATEGORY_WIFE  # 应是 1

    def test_update_recomputes(self, tmp_path):
        """update 时也要重算（避免历史数据带错误 person_type）"""
        svc = self._new_service(tmp_path)
        svc.add_person({"name": "苏辙", "person_type": 2})  # 先用错的
        result = svc.add_person({
            "name": "苏辙",
            "family_name": "苏",  # 这次给字段
        })
        assert result["person_type"] == CATEGORY_CLAN


# ============================================================
# 健壮性
# ============================================================

class TestRobustness:
    def test_none_values(self):
        p = {"name": None, "family_name": None, "dynasty": None, "title": None}
        assert classify_person(p) == CATEGORY_OTHER

    def test_empty_strings(self):
        p = {"name": "", "family_name": "", "dynasty": "", "title": ""}
        assert classify_person(p) == CATEGORY_OTHER

    def test_non_string_types(self):
        """非字符串字段不应崩。str() 后还能从 list 中取出「苏」→ CLAN (0)"""
        p = {
            "name": 123,
            "family_name": ["苏"],  # str 后含 CJK「苏」
            "role_of_family": {"foo": "bar"},
        }
        # 不崩即可；当前实现能从 list 里 str() 拿到「苏」→ CLAN
        result = classify_person(p)
        assert result in (CATEGORY_CLAN, CATEGORY_OTHER)

    def test_clan_surnames_is_frozenset(self):
        """CLAN_SURNAMES 必须是 frozenset 以保证可哈希 + 不可变"""
        assert isinstance(CLAN_SURNAMES, frozenset)
        assert "苏" in CLAN_SURNAMES
        assert "王" in CLAN_SURNAMES
        assert "李" in CLAN_SURNAMES
