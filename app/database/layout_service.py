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
    - 竞赛交付：.npz 缺失时自动 CPU 兜底（random + cluster），绝不抛 FileNotFoundError
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from . import source_router

logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LAYOUTS_DIR = PROJECT_ROOT / "data" / "layouts"


# ============================================================
# 加载 + 缓存
# ============================================================

_LAYOUT_CACHE: Dict[str, Dict] = {}

# person_meta 按 URI tail 索引，兼容 layout 的无 /jp/ 前缀 vs DB 的有 /jp/ 前缀
# 同一人物在两种 URI 形式下 tail 一致（r5vmxq29ki9gddjn）
_PERSON_META_CACHE: Dict[str, Dict[str, Dict]] = {}


def _uri_tail(uri: str) -> str:
    """取 URI 末尾 ID。兼容 /jp/ 路径差异。空串返回空。"""
    if not uri:
        return ""
    return uri.rstrip("/").rsplit("/", 1)[-1]


def _get_person_meta(source: str, needed_tails: set = None) -> Dict[str, Dict]:
    """取 source 对应的人物元数据（带缓存）。首次扫描 ~10s，之后 < 50ms。

    needed_tails: 若提供，仅缓存这些 URI tail 对应的条目（节省内存）。
                  同一 source 第二次调用若 needed_tails 不同则强制重扫。
    """
    cache_key = source
    cached = _PERSON_META_CACHE.get(cache_key)
    if cached is not None and (needed_tails is None or cached.get("_needed_tails") == needed_tails):
        return cached["meta"]
    meta: Dict[str, Dict] = {}
    if source == "jiapu" and source_router.is_enabled(source):
        try:
            src_cfg = source_router.assert_enabled(source)
            import sqlite3
            conn = sqlite3.connect(str(src_cfg["path"]))
            conn.row_factory = sqlite3.Row
            # 不带 birthday 过滤：npz 抽样不限生日，只保留 needed_tails 命中
            rows = conn.execute("""
                SELECT uri, label_chs, label_cht, label_en, family_name, role_of_family,
                       courtesy_name, description, gender, birthday
                FROM persons
            """)
            for r in rows:
                tail = _uri_tail(r["uri"] or "")
                if not tail:
                    continue
                if needed_tails is not None and tail not in needed_tails:
                    continue
                from .jiapu_query import _row_to_person
                p = _row_to_person(r)
                raw_birthday = (r["birthday"] or "").strip()
                birth_year = None
                if raw_birthday and raw_birthday.replace("-", "").isdigit():
                    try:
                        birth_year = int(raw_birthday)
                    except ValueError:
                        birth_year = None
                meta[tail] = {
                    "name": p.get("name", ""),
                    "category": p.get("person_type", 2),
                    "biography": (p.get("biography") or "")[:120],
                    "birth_year": birth_year,
                }
            conn.close()
            logger.info(f"[layout] person_meta 缓存预热完成（{source}）: {len(meta)} 条 / needed={len(needed_tails) if needed_tails else 'all'}")
        except Exception as e:
            # 竞赛交付：失败时显式 log + 继续（filter 失效但 layout 数据可正常返回）
            logger.warning(f"[layout] person_meta 加载失败（{source}）: {str(e)[:200]}，category/dynasty filter 失效但 layout 正常返回")
    _PERSON_META_CACHE[cache_key] = {"meta": meta, "_needed_tails": needed_tails}
    return meta


def _layout_path(source: str) -> Path:
    """默认布局文件路径：data/layouts/{source}_v1.npz"""
    return LAYOUTS_DIR / f"{source}_v1.npz"


def _cpu_fallback_layout(source: str, target_count: int = 5000) -> Dict:
    """CPU 兜底布局：.npz 缺失时使用。

    设计：
      - 节点按 source 名 hash 出种子 → 同一 source 多次调用结果一致
      - 用 cluster 半径做 K 个簇，每个簇 50~150 节点
      - z 维用小随机扰动（最多 0.5）→ 视觉上仍是平面但有起伏
    """
    seed = abs(hash(source)) % (2**31)
    rng = np.random.default_rng(seed)
    cluster_count = max(8, min(40, target_count // 80))
    centers_x = rng.uniform(-40.0, 40.0, size=cluster_count).astype(np.float32)
    centers_y = rng.uniform(-40.0, 40.0, size=cluster_count).astype(np.float32)
    centers_z = rng.uniform(-0.5, 0.5, size=cluster_count).astype(np.float32)

    per_cluster = max(20, target_count // cluster_count)
    total = per_cluster * cluster_count
    node_ids = np.array(
        [f"{source}/cpu_node_{i:06d}" for i in range(total)],
        dtype=object,
    )
    cluster_idx = np.repeat(np.arange(cluster_count), per_cluster)
    sigma = 4.0
    x = (centers_x[cluster_idx] + rng.normal(0, sigma, size=total).astype(np.float32)).astype(np.float32)
    y = (centers_y[cluster_idx] + rng.normal(0, sigma, size=total).astype(np.float32)).astype(np.float32)
    z = (centers_z[cluster_idx] + rng.normal(0, 0.2, size=total).astype(np.float32)).astype(np.float32)

    # 边：每个节点最多连 2 个同簇邻居
    edge_src = []
    edge_dst = []
    for c in range(cluster_count):
        start = c * per_cluster
        end = start + per_cluster
        for i in range(start, end - 1):
            edge_src.append(i)
            edge_dst.append(i + 1)
    edge_src = np.array(edge_src, dtype=np.int32)
    edge_dst = np.array(edge_dst, dtype=np.int32)

    return {
        "node_ids": node_ids,
        "x": x,
        "y": y,
        "z": z,
        "edge_src": edge_src,
        "edge_dst": edge_dst,
        "_fallback": True,
    }


def _load_npz(path: Path) -> Dict:
    """加载 .npz → 返回结构化数据 + 内存缓存。失败不抛 → CPU 兜底。"""
    if not path.exists():
        logger.warning(f"[layout] .npz 缺失: {path}，启用 CPU fallback")
        return _cpu_fallback_layout(path.stem.replace("_v1", ""))

    try:
        data = np.load(path, allow_pickle=True)
        return {
            "node_ids": data["node_ids"],
            "x": data["x"].astype(np.float32),
            "y": data["y"].astype(np.float32),
            "z": data["z"].astype(np.float32),
            "edge_src": data["edge_src"],
            "edge_dst": data["edge_dst"],
            "_fallback": False,
        }
    except Exception as e:
        logger.error(f"[layout] .npz 加载失败 {path}: {e}，启用 CPU fallback")
        return _cpu_fallback_layout(path.stem.replace("_v1", ""))


def get_layout(source: str = "jiapu", force_reload: bool = False) -> Dict:
    """获取布局数据（带内存缓存）。"""
    if force_reload or source not in _LAYOUT_CACHE:
        path = _layout_path(source)
        _LAYOUT_CACHE[source] = _load_npz(path)
        if _LAYOUT_CACHE[source].get("_fallback"):
            logger.info(f"[layout] {source} 走 CPU fallback（{len(_LAYOUT_CACHE[source]['node_ids'])} 节点）")
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
            "total_in_bbox": int,
            "total_returned": int,
            "filters": {"category": ..., "dynasty": ...},
            "is_fallback": bool,  # True 表示走的是 CPU fallback
        }

    竞赛交付改造（2026-06-17）：
      - 不再 raise FileNotFoundError（.npz 缺失时自动 CPU 兜底）
      - person_meta 加载失败 → 显式 logger.warning + 继续（filter 失效但不全崩）
      - 返回 is_fallback 标志，前端可显示 "当前为兜底数据" 提示
    """
    layout = get_layout(source)
    node_ids: np.ndarray = layout["node_ids"]
    x: np.ndarray = layout["x"]
    y: np.ndarray = layout["y"]
    edge_src: np.ndarray = layout["edge_src"]
    edge_dst: np.ndarray = layout["edge_dst"]
    is_fallback: bool = bool(layout.get("_fallback", False))

    # 1. 取人物元数据（首次扫描 ~10s，缓存后 < 50ms）
    # 按 URI tail 索引，兼容 layout 的无 /jp/ vs DB 的有 /jp/
    # 只缓存 npz 命中的 5k 条目，内存可控
    needed_tails = {_uri_tail(str(u)) for u in node_ids.tolist() if u}
    person_meta: Dict[str, Dict] = _get_person_meta(source, needed_tails)

    # 2. 按 bbox 过滤
    if bbox:
        xmin, ymin, xmax, ymax = bbox
        mask = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
    else:
        mask = np.ones(len(node_ids), dtype=bool)

    # 3. 按 category/dynasty 过滤（按 URI tail 查 person_meta，兼容 /jp/ 路径差异）
    if (category is not None or dynasty) and person_meta:
        for i in range(len(node_ids)):
            if not mask[i]:
                continue
            tail = _uri_tail(str(node_ids[i]))
            meta = person_meta.get(tail, {})
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

    # 5. 构建节点
    nodes = []
    for i in slice_indices:
        uri = str(node_ids[i])
        tail = _uri_tail(uri)
        meta = person_meta.get(tail, {})
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

    # 6. 构建边
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
        "is_fallback": is_fallback,
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
        "is_fallback": bool(layout.get("_fallback", False)),
    }


def clear_cache(source: Optional[str] = None) -> None:
    """清缓存（测试用）。"""
    if source:
        _LAYOUT_CACHE.pop(source, None)
        _PERSON_META_CACHE.pop(source, None)
    else:
        _LAYOUT_CACHE.clear()
        _PERSON_META_CACHE.clear()
