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
    category: Optional[int] = None,
    dynasty: Optional[str] = None,
) -> Dict:
    """取布局子集。

    Args:
        source: 数据源
        bbox: (xmin, ymin, xmax, ymax)，None 表示全量
        limit: 返回上限
        offset: 跳过
        category: 0=氏族 / 1=妻妾 / 2=其他 / 3=官吏（M6 筛选）
        dynasty: 朝代子串（M6 筛选，jiapu 源用 biography/name 子串匹配）

    Returns:
        {
            "nodes": [{"uri": "...", "name": "...", "x": 1.2, "y": 3.4,
                       "category": 0, "biography": "..."}, ...],
            "links": [...],
            "total_in_bbox": int,  # bbox 内 + category/dynasty 匹配
            "total_returned": int,
            "filters": {"category": ..., "dynasty": ...},
        }
    """
    layout = get_layout(source)
    node_ids: np.ndarray = layout["node_ids"]
    x: np.ndarray = layout["x"]
    y: np.ndarray = layout["y"]
    edge_src: np.ndarray = layout["edge_src"]
    edge_dst: np.ndarray = layout["edge_dst"]

    # 1. 一次性加载人物元数据（person_type + biography 摘要）用于 category/dynasty 过滤
    person_meta: Dict[str, Dict] = {}
    try:
        from . import jiapu_query
        # 只在 jiapu 源时尝试（其它源无此 helper）
        if source_router.is_enabled(source):
            src_cfg = source_router.assert_enabled(source)
            import sqlite3
            conn = sqlite3.connect(str(src_cfg["path"]))
            conn.row_factory = sqlite3.Row
            # M6 时间轴：birthday 列携带数字年（如 "1628"）或中文日期，前端按年映射朝代
            # WHERE 过滤空值：2M → ~260k，省 7x 时间
            # SELECT 覆盖 PERSON_FIELD_MAP 全部列（否则 _row_to_person IndexError 会被外层 try 静默吞掉，
            # 导致 person_meta 永远是空 dict，name 全部回退到 URI tail）
            for r in conn.execute("""
                SELECT uri, label_chs, label_cht, label_en, family_name, role_of_family,
                       courtesy_name, description, gender, birthday
                FROM persons
                WHERE birthday IS NOT NULL AND birthday != ''
            """):
                from .jiapu_query import _row_to_person
                p = _row_to_person(r)
                # 解析 birth_year：纯数字才返回 int，否则 None
                raw_birthday = (r["birthday"] or "").strip()
                birth_year = None
                if raw_birthday and raw_birthday.replace("-", "").isdigit():
                    try:
                        birth_year = int(raw_birthday)
                    except ValueError:
                        birth_year = None
                person_meta[p["uri"]] = {
                    "name": p.get("name", ""),
                    "category": p.get("person_type", 2),
                    "biography": (p.get("biography") or "")[:120],
                    "birth_year": birth_year,
                }
            conn.close()
    except Exception:
        # 失败时不阻塞主流程（filter 会失效但返回全量）
        pass

    # 2. 按 bbox 过滤
    if bbox:
        xmin, ymin, xmax, ymax = bbox
        mask = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
    else:
        mask = np.ones(len(node_ids), dtype=bool)

    # 3. 按 category/dynasty 过滤（numpy 不友好，逐个判断）
    if category is not None or dynasty:
        for i in range(len(node_ids)):
            if not mask[i]:
                continue
            uri = str(node_ids[i])
            meta = person_meta.get(uri, {})
            if category is not None and meta.get("category") != category:
                mask[i] = False
                continue
            if dynasty:
                haystack = meta.get("biography", "") + meta.get("name", "")
                if dynasty not in haystack:
                    mask[i] = False

    visible_indices = np.where(mask)[0]
    total_in_bbox = int(len(visible_indices))

    # 4. 按 offset/limit 切片
    slice_indices = visible_indices[offset:offset + limit]

    # 5. 构建节点（含 name/category/biography/birth_year 给前端用）
    nodes = []
    for i in slice_indices:
        uri = str(node_ids[i])
        meta = person_meta.get(uri, {})
        nodes.append({
            "uri": uri,
            "x": float(x[i]),
            "y": float(y[i]),
            "z": float(layout["z"][i]),
            "name": meta.get("name") or uri.split("/")[-1],
            "category": meta.get("category", 2),
            "biography": meta.get("biography", ""),
            "birth_year": meta.get("birth_year"),
        })

    # 6. 构建边（只保留两端都在当前返回的节点中）
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
        "filters": {"category": category, "dynasty": dynasty},
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
