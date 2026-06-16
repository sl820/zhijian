"""
布局预计算读取服务（M5 second cut 第二步）

Why：M6 星云图谱前端需要服务端预布局坐标。
本模块从 data/layouts/*.npz 读取节点坐标，支持按 source / bbox / zoom 切片。

How to apply：
    /api/v1/kg/layout?source=jiapu&bbox=[-50,-50,50,50]&limit=500
    返回 {nodes, links, bbox, total_in_view}

约束：
    - 单层 2D 布局（z=0 占位），M6 转 three.js 时再加 z 维
    - 不重新计算布局，只读取 .npz
"""
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from . import source_router


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAYOUTS_DIR = PROJECT_ROOT / "data" / "layouts"


# ============================================================
# 加载 + 缓存
# ============================================================

_LAYOUT_CACHE: Dict[str, Dict] = {}


def _layout_path(source: str) -> Path:
    """默认布局文件路径：data/layouts/{source}_v1.npz"""
    return LAYOUTS_DIR / f"{source}_v1.npz"


def _load_npz(path: Path) -> Dict:
    """加载 .npz → 返回结构化数据 + 内存缓存。"""
    if not path.exists():
        raise FileNotFoundError(f"布局文件不存在: {path}（先跑 precompute_layout.py）")

    data = np.load(path, allow_pickle=True)
    return {
        "node_ids": data["node_ids"],         # object array
        "x": data["x"].astype(np.float32),
        "y": data["y"].astype(np.float32),
        "z": data["z"].astype(np.float32),
        "edge_src": data["edge_src"],
        "edge_dst": data["edge_dst"],
    }


def get_layout(source: str = "jiapu", force_reload: bool = False) -> Dict:
    """获取布局数据（带内存缓存）。"""
    if force_reload or source not in _LAYOUT_CACHE:
        path = _layout_path(source)
        _LAYOUT_CACHE[source] = _load_npz(path)
    return _LAYOUT_CACHE[source]


# ============================================================
# 查询 API
# ============================================================

def get_layout_subset(
    source: str = "jiapu",
    bbox: Optional[Tuple[float, float, float, float]] = None,
    limit: int = 500,
    offset: int = 0,
) -> Dict:
    """取布局子集。

    Args:
        source: 数据源
        bbox: (xmin, ymin, xmax, ymax)，None 表示全量
        limit: 返回上限
        offset: 跳过

    Returns:
        {
            "nodes": [{"uri": "...", "x": 1.2, "y": 3.4}, ...],
            "links": [{"source": "uri1", "target": "uri2"}, ...],
            "total_in_bbox": int,
            "total_returned": int,
        }
    """
    layout = get_layout(source)
    node_ids: np.ndarray = layout["node_ids"]
    x: np.ndarray = layout["x"]
    y: np.ndarray = layout["y"]
    edge_src: np.ndarray = layout["edge_src"]
    edge_dst: np.ndarray = layout["edge_dst"]

    # 1. 按 bbox 过滤
    if bbox:
        xmin, ymin, xmax, ymax = bbox
        mask = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
    else:
        mask = np.ones(len(node_ids), dtype=bool)

    visible_indices = np.where(mask)[0]
    total_in_bbox = int(len(visible_indices))

    # 2. 按 offset/limit 切片
    slice_indices = visible_indices[offset:offset + limit]

    # 3. 构建节点
    nodes = [
        {
            "uri": str(node_ids[i]),
            "x": float(x[i]),
            "y": float(y[i]),
            "z": float(layout["z"][i]),
        }
        for i in slice_indices
    ]

    # 4. 构建边（只保留两端都在当前返回的节点中）
    # 注：必须用 slice_indices 而不是 visible_indices，否则 bbox 大时
    # links 数量会远超 limit，前端渲染会崩
    returned_set = set(slice_indices.tolist())
    links = []
    for s, d in zip(edge_src, edge_dst):
        if s in returned_set and d in returned_set:
            links.append({
                "source": str(node_ids[s]),
                "target": str(node_ids[d]),
            })

    return {
        "nodes": nodes,
        "links": links,
        "total_in_bbox": total_in_bbox,
        "total_returned": len(nodes),
        "total_visible_for_links": len(links),
    }


def get_layout_metadata(source: str = "jiapu") -> Dict:
    """取布局元信息（节点/边总数 + 坐标范围）。"""
    layout = get_layout(source)
    return {
        "source": source,
        "node_count": int(len(layout["node_ids"])),
        "edge_count": int(len(layout["edge_src"])),
        "x_range": [float(layout["x"].min()), float(layout["x"].max())],
        "y_range": [float(layout["y"].min()), float(layout["y"].max())],
        "z_range": [float(layout["z"].min()), float(layout["z"].max())],
    }


def clear_cache(source: Optional[str] = None) -> None:
    """清缓存（测试用）。"""
    if source:
        _LAYOUT_CACHE.pop(source, None)
    else:
        _LAYOUT_CACHE.clear()
