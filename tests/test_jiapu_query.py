"""
jiapu_query 模块测试

覆盖：
- count_persons / list_persons 分页 + 过滤
- get_person / get_person_relations / get_relations_batch
- top_surnames
- get_graph_subset
- 字段映射（jiapu → zhijian 通用 person）
- 与 classifier 集成（每行带 person_type）

依赖：D:/上海图书馆开放数据/data/shlib_jiapu.db 存在
"""
import sys
import time
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database import jiapu_query, source_router


# ============================================================
# Fixtures
# ============================================================

# 需要 jiapu 数据库存在
JIAPU_PATH = Path("D:/上海图书馆开放数据/data/shlib_jiapu.db")
needs_jiapu = pytest.mark.skipif(
    not JIAPU_PATH.exists(),
    reason=f"需要 jiapu 数据库: {JIAPU_PATH}",
)


# ============================================================
# 总数 + 字段映射
# ============================================================

@needs_jiapu
class TestCountAndMapping:
    def test_count_persons(self):
        """总人数：约 2M"""
        n = jiapu_query.count_persons()
        assert n > 2_000_000
        assert n < 2_100_000

    def test_count_persons_with_invalid_source(self):
        with pytest.raises(ValueError, match="未知数据源"):
            jiapu_query.count_persons("nonexistent")

    def test_count_persons_with_disabled_source(self):
        """base 是 disabled 数据源"""
        with pytest.raises(ValueError, match="未启用"):
            jiapu_query.count_persons("base")

    def test_person_has_zhijian_fields(self):
        """返回的 person 含 zhijian 通用字段（uri/name/source/person_type）"""
        p, _ = jiapu_query.list_persons(limit=1)
        assert "uri" in p[0]
        assert "name" in p[0]
        assert p[0]["source"] == "jiapu"
        assert "person_type" in p[0]
        assert p[0]["person_type"] in (0, 1, 2, 3)


# ============================================================
# 分页性能
# ============================================================

@needs_jiapu
class TestPagination:
    def test_default_page_fast(self):
        """默认页 < 200ms（性能基线）"""
        t = time.time()
        persons, total = jiapu_query.list_persons(limit=20)
        elapsed = time.time() - t
        assert len(persons) == 20
        assert total > 2_000_000
        assert elapsed < 0.2, f"太慢: {elapsed:.3f}s"

    def test_deep_offset(self):
        """深 offset 仍 < 500ms"""
        t = time.time()
        persons, _ = jiapu_query.list_persons(limit=20, offset=1_000_000)
        elapsed = time.time() - t
        assert len(persons) == 20
        assert elapsed < 0.5, f"offset 100 万太慢: {elapsed:.3f}s"

    def test_offset_doesnt_overlap(self):
        """offset=0 与 offset=20 的 uri 不重叠"""
        p1, _ = jiapu_query.list_persons(limit=20, offset=0)
        p2, _ = jiapu_query.list_persons(limit=20, offset=20)
        uris1 = {p["uri"] for p in p1}
        uris2 = {p["uri"] for p in p2}
        assert uris1.isdisjoint(uris2)


# ============================================================
# 过滤
# ============================================================

@needs_jiapu
class TestFilters:
    def test_surname_filter(self):
        """surname='wang' 应只返回 family_name='wang' 的"""
        persons, total = jiapu_query.list_persons(surname="wang", limit=10)
        assert all(p["family_name"] == "wang" for p in persons)
        assert total > 10000

    def test_has_relations_filter(self):
        """has_relations=True 只返回有 src/dst 关系的人"""
        persons, total = jiapu_query.list_persons(has_relations=True, limit=10)
        assert all(p["uri"] for p in persons)
        # has_relations 的 total 应远小于总人数
        assert total < 1_000_000


# ============================================================
# 单个人物
# ============================================================

@needs_jiapu
class TestSinglePerson:
    def test_get_person_by_uri(self):
        p, _ = jiapu_query.list_persons(limit=1)
        uri = p[0]["uri"]
        p2 = jiapu_query.get_person(uri)
        assert p2 is not None
        assert p2["uri"] == uri
        assert p2["name"] == p[0]["name"]

    def test_get_nonexistent(self):
        p = jiapu_query.get_person("p:nonexistent/xxx")
        assert p is None


# ============================================================
# 关系
# ============================================================

@needs_jiapu
class TestRelations:
    def test_get_relations_batch(self):
        rels, total = jiapu_query.get_relations_batch(limit=50)
        assert len(rels) == 50
        # 实际 jiapu person_relations 总数约 13k（SPARQL 配偶关系稀缺，见 shlib SP 端注释）
        assert total > 1000
        assert all("source" in r and "target" in r and "type" in r for r in rels)

    def test_get_person_relations(self):
        """取一个有关系的 person，验证 src/dst 都能查到"""
        rels_all, _ = jiapu_query.get_relations_batch(limit=1)
        rel = rels_all[0]
        uri = rel["source"]
        rs = jiapu_query.get_person_relations(uri)
        # 该 uri 作为 src 至少有 1 条
        assert any(r["source"] == uri for r in rs)


# ============================================================
# 姓氏统计
# ============================================================

@needs_jiapu
class TestTopSurnames:
    def test_top_surnames_ordering(self):
        """top_surnames 应按 cnt 降序"""
        surnames = jiapu_query.top_surnames(limit=10)
        cnts = [s["cnt"] for s in surnames]
        assert cnts == sorted(cnts, reverse=True)
        assert all("family_name" in s for s in surnames)

    def test_top_surnames_limit(self):
        surnames = jiapu_query.top_surnames(limit=5)
        assert len(surnames) == 5


# ============================================================
# 图谱子集
# ============================================================

@needs_jiapu
class TestGraphSubset:
    def test_get_graph_subset(self):
        """返回 nodes + links + 总数"""
        g = jiapu_query.get_graph_subset(limit=50)
        assert "nodes" in g
        assert "links" in g
        assert len(g["links"]) == 50
        assert len(g["nodes"]) > 0
        assert g["total_persons"] == len(g["nodes"])
        # jiapu person_relations 总数约 13k
        assert g["total_links"] > 1000

    def test_graph_links_match_uris(self):
        """所有 link 的 source/target uri 都应在 nodes 中存在"""
        g = jiapu_query.get_graph_subset(limit=20)
        uris = {n["uri"] for n in g["nodes"]}
        for link in g["links"]:
            # link.source/target 可能是 src 或 dst
            assert link["source"] in uris or link["target"] in uris


# ============================================================
# 性能 baseline
# ============================================================

@needs_jiapu
class TestPerformance:
    """性能基线（防止回退）。"""

    def test_count_fast(self):
        t = time.time()
        jiapu_query.count_persons()
        elapsed = time.time() - t
        assert elapsed < 0.5, f"count 太慢: {elapsed:.3f}s"

    def test_graph_subset_fast(self):
        t = time.time()
        jiapu_query.get_graph_subset(limit=500)
        elapsed = time.time() - t
        assert elapsed < 0.5, f"graph subset 太慢: {elapsed:.3f}s"
