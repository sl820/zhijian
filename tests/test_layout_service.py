"""
layout_service 测试

前置：data/layouts/jiapu_v1.npz 存在
（precompute_layout.py 跑 5k 节点 67s，先跑一遍生成）

覆盖：
- 加载 + 缓存
- bbox 过滤
- offset/limit 切片
- 元信息
"""
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database import layout_service


NPZ_PATH = Path("data/layouts/jiapu_v1.npz")
needs_npz = pytest.mark.skipif(
    not NPZ_PATH.exists(),
    reason=f"需要预布局文件: {NPZ_PATH}（跑 precompute_layout.py）",
)


@needs_npz
class TestLoading:
    def test_get_layout_loads_npz(self):
        layout = layout_service.get_layout(force_reload=True)
        assert "node_ids" in layout
        assert "x" in layout
        assert "y" in layout
        assert "z" in layout
        assert "edge_src" in layout
        assert "edge_dst" in layout

    def test_get_layout_uses_cache(self):
        layout_service.clear_cache()
        layout1 = layout_service.get_layout()
        layout2 = layout_service.get_layout()
        # 同一个 dict 实例（缓存命中）
        assert layout1 is layout2

    def test_force_reload(self):
        layout1 = layout_service.get_layout()
        layout2 = layout_service.get_layout(force_reload=True)
        # force_reload 重新加载，但 node_ids 内容一致
        assert layout1["node_ids"].shape == layout2["node_ids"].shape


@needs_npz
class TestSubset:
    def test_no_bbox_returns_all(self):
        """无 bbox → 返回所有节点（按 limit 截断）"""
        result = layout_service.get_layout_subset(limit=50)
        assert len(result["nodes"]) == 50
        assert result["total_in_bbox"] == result["total_returned"] + 4950  # 5k - 50

    def test_bbox_filters(self):
        """bbox 只返回范围内节点"""
        # 全图 x ∈ [-100, 100]，bbox = [-10, -10, 10, 10] 应过滤掉大部分
        result = layout_service.get_layout_subset(bbox=(-10, -10, 10, 10), limit=500)
        assert all(
            -10 <= n["x"] <= 10 and -10 <= n["y"] <= 10
            for n in result["nodes"]
        )
        # 中心区节点数应远小于全量
        assert result["total_in_bbox"] < 5000

    def test_offset_limit_pagination(self):
        r1 = layout_service.get_layout_subset(limit=10, offset=0)
        r2 = layout_service.get_layout_subset(limit=10, offset=10)
        uris1 = {n["uri"] for n in r1["nodes"]}
        uris2 = {n["uri"] for n in r2["nodes"]}
        assert uris1.isdisjoint(uris2)

    def test_links_only_in_bbox(self):
        """link 两端都在当前返回的节点中（不是 visible_indices 全集）"""
        result = layout_service.get_layout_subset(bbox=(-10, -10, 10, 10), limit=20)
        returned_uris = {n["uri"] for n in result["nodes"]}
        for link in result["links"]:
            assert link["source"] in returned_uris
            assert link["target"] in returned_uris
        # 边数不应超过 limit * (limit-1)（含平行边的宽松上界）
        max_possible = len(returned_uris) * max(len(returned_uris) - 1, 1)
        assert len(result["links"]) <= max_possible


@needs_npz
class TestMetadata:
    def test_metadata(self):
        meta = layout_service.get_layout_metadata()
        assert meta["node_count"] > 0
        assert meta["edge_count"] > 0
        assert meta["x_range"][0] < meta["x_range"][1]
        assert meta["y_range"][0] < meta["y_range"][1]
        assert meta["source"] == "jiapu"


@needs_npz
class TestClearCache:
    def test_clear(self):
        layout_service.get_layout()
        assert "jiapu" in layout_service._LAYOUT_CACHE
        layout_service.clear_cache("jiapu")
        assert "jiapu" not in layout_service._LAYOUT_CACHE
