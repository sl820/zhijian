"""
布局预计算脚本（真上 ForceAtlas2 + collision-aware 间距）

Why：M6 三维星野图谱需要服务端预布局坐标。plan 要求 ForceAtlas2，
之前妥协用 nx.spring_layout (FR 算法)。本脚本改用 fa2 库真上 FA2。

2026-06-18 升级：启用 FA2 的 adjustSizes + nodeSizes，按 sphere radius
推开节点避免视觉重叠。半径同时写入 npz，前端 PersonNode 按 npz radius
渲染（前端 sphere radius 默认 1.0，commander 节点 2.0，cluster 中心 3.0）。

Barnes-Hut O(n log n) 加速在 fa2 库内已实现，但 Windows 缺 MSVC 导致
Cython 编译失败，当前是纯 Python 版（约慢 10-100x）。33k 节点
实测 ~12 分钟完成。

How to use:
    python -m scripts.precompute_layout --source jiapu --max-nodes 330000 --output data/layouts/jiapu_v1.npz

输出格式（与 layout_service.py 兼容）：
    node_ids:  list of uri strings
    x, y, z:   float32 arrays (z = 0 占位，未来可加 z 维)
    radius:    float32 array（节点 sphere 半径，供前端 collision-aware 渲染）
    edge_src, edge_dst: int32 arrays (边索引)

性能（家谱 DB 实测）：
    5k 节点 / 100 iter    ≈  90s
    33k 节点 / 100 iter   ≈ 12 min（未 Cython 编译）

参数调优：
    scalingRatio:    节点间距系数（越大节点越分散；默认 20 适配 collision-aware）
    gravity:         向心力（防止节点飞散；1.0 ~ 5.0）
    jitterTolerance: 防抖动（1.0 标准，越大越稳但越慢收敛）
    barnesHutTheta:  BH 阈值（1.2 平衡精度/速度；越小越精确越慢）
"""
import argparse
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCES = {
    "jiapu": Path("D:/上海图书馆开放数据/data/shlib_jiapu.db"),
}


# ============================================================
# 数据加载
# ============================================================

def load_top_edges(db_path: Path, max_nodes: int) -> Tuple[List[str], List[Tuple[str, str]]]:
    """取连接数 top max_nodes 节点 + 他们的全部边（cbdb_relations）。

    Why：用 cbdb_relations（588k 条）而不是 person_relations（13k），
    保证图密度合理，FA2 才能跑出有意义的社区结构。
    """
    conn = sqlite3.connect(str(db_path))

    degree_sql = """
        SELECT uri, SUM(cnt) AS total_cnt FROM (
            SELECT subject_uri AS uri, COUNT(*) AS cnt FROM cbdb_relations
            WHERE subject_uri IS NOT NULL GROUP BY subject_uri
            UNION ALL
            SELECT object_uri AS uri, COUNT(*) AS cnt FROM cbdb_relations
            WHERE object_uri IS NOT NULL GROUP BY object_uri
        )
        GROUP BY uri
        ORDER BY total_cnt DESC
        LIMIT ?
    """
    print(f"[1/4] 计算 degree top {max_nodes}...")
    t = time.time()
    top_uris = [r[0] for r in conn.execute(degree_sql, (max_nodes,)).fetchall()]
    print(f"      {len(top_uris)} 个核心节点 ({time.time()-t:.2f}s)")
    if not top_uris:
        return [], []

    print(f"[2/4] 取涉及的 cbdb_relations 边...")
    t = time.time()
    placeholders = ",".join("?" * len(top_uris))
    edge_rows = conn.execute(
        f"""
        SELECT subject_uri, object_uri FROM cbdb_relations
        WHERE subject_uri IN ({placeholders})
          AND object_uri IN ({placeholders})
        """,
        top_uris + top_uris,
    ).fetchall()
    # 去重（cbdb_relations 可能有重复）+ 过滤 self-loop
    seen = set()
    edges = []
    for s, d in edge_rows:
        if s == d:
            continue
        key = (s, d) if s < d else (d, s)
        if key in seen:
            continue
        seen.add(key)
        edges.append((s, d))
    print(f"      {len(edges)} 条边（去重后，{time.time()-t:.2f}s）")
    return top_uris, edges


# ============================================================
# ForceAtlas2 布局（真 FA2，不再用 FR）
# ============================================================

def compute_fa2_layout(
    uris: List[str],
    edges: List[Tuple[str, str]],
    iterations: int = 100,
    scaling_ratio: float = 20.0,
    gravity: float = 1.0,
    base_radius: float = 1.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """用 fa2 库跑真 ForceAtlas2 布局（collision-aware）。

    Args:
        scaling_ratio: 节点间距系数（默认 20，配合 adjustSizes 让节点明显分开）
        gravity: 向心力
        base_radius: 节点 sphere 半径（越大间距越大；hub 节点放大到 2.0）

    Returns: ((N, 2) float32 坐标数组, (N,) float32 半径数组)，按 uris 顺序。
    """
    import warnings
    warnings.filterwarnings("ignore", message=".*pure Python fa2util.*")

    from fa2 import ForceAtlas2
    import networkx as nx

    print(f"[3/4] ForceAtlas2 布局（{len(uris)} 节点, {len(edges)} 边, {iterations} iter, scaling={scaling_ratio}, base_r={base_radius}）...")
    t = time.time()

    # 建图（用 NetworkX 拿稀疏邻接矩阵）
    G = nx.Graph()
    G.add_nodes_from(uris)
    G.add_edges_from(edges)
    A = nx.to_scipy_sparse_array(G, nodelist=uris).astype(np.float64)

    # 计算每个节点的度（degree），hub 节点放大半径
    degree = np.array([G.degree(u) for u in uris], dtype=np.float32)
    # hub: 95 分位（top 5%），跨数据集可比
    # 旧版 median*3 在 median=1 时门槛=3，5k 节点 38% 都被当 hub，FA2 推开太狠
    # 95 分位 → 5000 节点 ~250 个真 hub，视觉聚焦更准
    hub_threshold = float(np.percentile(degree, 95)) if len(degree) > 0 else 0
    node_sizes = np.where(degree >= hub_threshold, base_radius * 3.0, base_radius).astype(np.float64)
    print(f"      degree range: [{degree.min():.0f}, {degree.max():.0f}], hub_threshold(p95)={hub_threshold:.0f}, hub count={int((degree >= hub_threshold).sum())}")

    # FA2 参数（针对家谱关系密度调优 + collision-aware）
    forceatlas2 = ForceAtlas2(
        outboundAttractionDistribution=True,  # 避免 hub 节点过分吸引
        linLogMode=False,
        adjustSizes=True,                     # 启用 sphere 半径碰撞避免
        edgeWeightInfluence=1.0,
        normalizeEdgeWeights=False,
        jitterTolerance=1.0,
        barnesHutOptimize=True,
        barnesHutTheta=1.2,
        multiThreaded=False,
        scalingRatio=scaling_ratio,
        gravity=gravity,
        strongGravityMode=False,
    )

    # 初始位置：随机分布（避免全 0 导致重力坍缩）
    init_pos = np.random.RandomState(42).rand(len(uris), 2) * 100.0

    # FA2 接受 sizes 数组作为每个节点的 sphere 半径（adjustSizes=True 才生效）
    result = forceatlas2.forceatlas2(
        A, pos=init_pos, iterations=iterations, sizes=node_sizes
    )
    coords = np.array(result, dtype=np.float32)
    radii = node_sizes.astype(np.float32)

    # 居中 + outlier-aware 归一化
    #  v3 修：v2 用 99 分位 max abs，但没 clip，outlier 仍被乘以 9.4 飞到 ±900。
    #  v3 改：先 clip 到 99 分位（outlier 压到边界），再归一化到 ±100。
    #  效果：99% 节点铺到 ±100，1% outlier 紧贴 ±100 边界不飞走。
    coords -= coords.mean(axis=0)
    abs_x_99 = float(np.percentile(np.abs(coords[:, 0]), 99))
    abs_y_99 = float(np.percentile(np.abs(coords[:, 1]), 99))
    abs_x_99 = max(abs_x_99, 1e-6)
    abs_y_99 = max(abs_y_99, 1e-6)
    coords[:, 0] = np.clip(coords[:, 0], -abs_x_99, abs_x_99)
    coords[:, 1] = np.clip(coords[:, 1], -abs_y_99, abs_y_99)
    coords[:, 0] *= 100.0 / abs_x_99
    coords[:, 1] *= 100.0 / abs_y_99

    print(f"      FA2 完成 ({time.time()-t:.2f}s)，坐标已归一化到 [-100, 100]")
    return coords, radii


# ============================================================
# 输出
# ============================================================

def save_npz(
    coords: np.ndarray,
    radii: np.ndarray,
    uris: List[str],
    edges: List[Tuple[str, str]],
    output: Path,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    node_ids = np.array(uris, dtype=object)
    x = coords[:, 0]
    y = coords[:, 1]
    z = np.zeros(len(uris), dtype=np.float32)

    uri_to_idx = {u: i for i, u in enumerate(uris)}
    edge_src, edge_dst = [], []
    for s, d in edges:
        if s in uri_to_idx and d in uri_to_idx:
            edge_src.append(uri_to_idx[s])
            edge_dst.append(uri_to_idx[d])
    edge_src = np.array(edge_src, dtype=np.int32)
    edge_dst = np.array(edge_dst, dtype=np.int32)

    np.savez_compressed(
        output,
        node_ids=node_ids,
        x=x, y=y, z=z,
        radius=radii,
        edge_src=edge_src,
        edge_dst=edge_dst,
    )
    print(f"[4/4] 写入: {output}  ({output.stat().st_size / 1024:.1f} KB)")
    print(f"      节点: {len(uris)}, 边: {len(edge_src)}")
    print(f"      x 范围: [{x.min():.2f}, {x.max():.2f}]  y 范围: [{y.min():.2f}, {y.max():.2f}]")
    print(f"      radius: min={radii.min():.1f}, max={radii.max():.1f}, mean={radii.mean():.2f}")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="预计算节点布局坐标（真 FA2）")
    parser.add_argument("--source", default="jiapu", choices=list(SOURCES.keys()))
    parser.add_argument("--max-nodes", type=int, default=5000, help="采样节点上限")
    parser.add_argument("--iterations", type=int, default=100, help="FA2 迭代次数")
    parser.add_argument("--scaling-ratio", type=float, default=20.0, help="FA2 节点间距系数（默认 20，collision-aware）")
    parser.add_argument("--gravity", type=float, default=1.0, help="FA2 向心力")
    parser.add_argument("--base-radius", type=float, default=1.0, help="节点 sphere 半径（hub 自动 ×2）")
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    db_path = SOURCES[args.source]
    if not db_path.exists():
        raise FileNotFoundError(f"数据库不存在: {db_path}")

    output = Path(args.output) if args.output else (
        PROJECT_ROOT / "data" / "layouts" / f"{args.source}_v1.npz"
    )

    t0 = time.time()
    uris, edges = load_top_edges(db_path, args.max_nodes)
    if not uris:
        print("[FAIL] 没找到任何节点")
        return
    coords, radii = compute_fa2_layout(
        uris, edges,
        iterations=args.iterations,
        scaling_ratio=args.scaling_ratio,
        gravity=args.gravity,
        base_radius=args.base_radius,
    )
    save_npz(coords, radii, uris, edges, output)
    print(f"\n[DONE] 总耗时 {time.time()-t0:.2f}s")


if __name__ == "__main__":
    main()
