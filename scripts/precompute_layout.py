"""
布局预计算脚本（M5 second cut 第一步）

Why：M6 三维星野图谱需要服务端预布局坐标（前端只渲染，不跑布局）。
对 2M 全量跑 FA2 不现实，本脚本先对代表性子集（top 连接数 + 跨源）
跑 networkx.spring_layout 输出坐标。后续 M6 视锥裁剪时按重要性抽样。

How to use:
    python -m scripts.precompute_layout --source jiapu --max-nodes 1000 --output data/layouts/jiapu_v1.npz

输出格式：
    node_ids:  list of uri strings
    x, y, z:   float32 arrays (z = 0 占位，未来可加 z 维)

约束：
    只使用 cbdb_relations（有 588k 条，person_relations 仅 13k 太少）。
    抽样策略：连接数 top N 个节点 + 他们的全部边。
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

def load_top_edges(db_path: Path, max_nodes: int) -> Tuple[List[str], List[Tuple[str, str, str]]]:
    """取连接数 top max_nodes 节点 + 他们的全部边（cbdb_relations）。

    Returns:
        node_ids: 子集中的 uri 列表（连接数降序）
        edges: (src, dst, rel) 列表
    """
    conn = sqlite3.connect(str(db_path))

    # 1. 统计每个 uri 的连接数（src + dst 之和）
    degree_sql = """
        SELECT uri, cnt FROM (
            SELECT subject_uri AS uri, COUNT(*) AS cnt FROM cbdb_relations
            WHERE subject_uri IS NOT NULL
            GROUP BY subject_uri
            UNION ALL
            SELECT object_uri AS uri, COUNT(*) AS cnt FROM cbdb_relations
            WHERE object_uri IS NOT NULL
            GROUP BY object_uri
        )
        GROUP BY uri
        ORDER BY SUM(cnt) DESC
        LIMIT ?
    """
    print(f"[1/3] 计算 degree top {max_nodes}...")
    t = time.time()
    top_uris = [r[0] for r in conn.execute(degree_sql, (max_nodes,)).fetchall()]
    print(f"      {len(top_uris)} 个核心节点 ({time.time()-t:.2f}s)")

    if not top_uris:
        return [], []

    # 2. 取这些节点涉及的边
    print(f"[2/3] 取涉及的 cbdb_relations 边...")
    t = time.time()
    placeholders = ",".join("?" * len(top_uris))
    edge_rows = conn.execute(
        f"""
        SELECT subject_uri, object_uri, COALESCE(relation_label, 'related')
        FROM cbdb_relations
        WHERE subject_uri IN ({placeholders})
          AND object_uri IN ({placeholders})
        """,
        top_uris + top_uris,
    ).fetchall()
    edges = [(r[0], r[1], r[2]) for r in edge_rows]
    print(f"      {len(edges)} 条边 ({time.time()-t:.2f}s)")

    return top_uris, edges


# ============================================================
# 布局计算
# ============================================================

def compute_layout(uris: List[str], edges: List[Tuple[str, str, str]]) -> Dict[str, Tuple[float, float]]:
    """用 networkx.spring_layout 跑 2D 布局。

    Returns: uri -> (x, y) 坐标 dict
    """
    import networkx as nx

    print(f"[3/3] 跑 spring_layout（{len(uris)} 节点, {len(edges)} 边）...")
    t = time.time()

    G = nx.Graph()
    G.add_nodes_from(uris)
    for src, dst, _ in edges:
        G.add_edge(src, dst)

    # spring_layout: Fruchterman-Reingold (FR) 算法
    # k: 最优节点间距；iterations: 迭代次数；scale: 输出坐标范围
    pos = nx.spring_layout(
        G,
        k=1.0 / np.sqrt(len(uris)) if len(uris) > 1 else 1.0,
        iterations=50,
        scale=100.0,
        seed=42,
    )
    print(f"      布局完成 ({time.time()-t:.2f}s)")

    return pos


# ============================================================
# 输出
# ============================================================

def save_npz(
    pos: Dict[str, Tuple[float, float]],
    uris: List[str],
    edges: List[Tuple[str, str, str]],
    output: Path,
) -> None:
    """保存为 .npz 格式：node_ids + x + y + z(z=0 占位) + edge index。"""
    output.parent.mkdir(parents=True, exist_ok=True)

    # 节点坐标（按 uris 顺序）
    node_ids = np.array(uris, dtype=object)
    xy = np.array([pos.get(u, (0.0, 0.0)) for u in uris], dtype=np.float32)
    x = xy[:, 0]
    y = xy[:, 1]
    z = np.zeros(len(uris), dtype=np.float32)

    # 边索引（uri → index）
    uri_to_idx = {u: i for i, u in enumerate(uris)}
    edge_src = []
    edge_dst = []
    for s, d, _ in edges:
        if s in uri_to_idx and d in uri_to_idx:
            edge_src.append(uri_to_idx[s])
            edge_dst.append(uri_to_idx[d])
    edge_src = np.array(edge_src, dtype=np.int32)
    edge_dst = np.array(edge_dst, dtype=np.int32)

    np.savez_compressed(
        output,
        node_ids=node_ids,
        x=x, y=y, z=z,
        edge_src=edge_src,
        edge_dst=edge_dst,
    )
    print(f"      写入: {output}  ({output.stat().st_size / 1024:.1f} KB)")
    print(f"      节点: {len(uris)}, 边: {len(edge_src)}")
    print(f"      x 范围: [{x.min():.2f}, {x.max():.2f}]  y 范围: [{y.min():.2f}, {y.max():.2f}]")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="预计算 jiapu 节点布局坐标")
    parser.add_argument("--source", default="jiapu", choices=list(SOURCES.keys()))
    parser.add_argument("--max-nodes", type=int, default=1000, help="采样节点上限")
    parser.add_argument("--output", type=str, default=None, help="输出 .npz 路径")
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
    pos = compute_layout(uris, edges)
    save_npz(pos, uris, edges, output)
    print(f"\n[DONE] 总耗时 {time.time()-t0:.2f}s")


if __name__ == "__main__":
    main()
