"""
jiapu 数据源查询层

对 shlib_jiapu.db 的只读查询 + 结果转成 zhijian 通用 person 字典。

Why：M5 数据接入。jiapu.db 有 2M persons，in-memory kg_service 扛不住。
How to apply：所有 jiapu 相关端点（/kg/persons、/kg/graph、/kg/person）都通过本模块。
"""
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from . import source_router
from ..kg.classifier import classify_person


# ============================================================
# Schema 字段映射
# ============================================================
# jiapu.persons 字段 → zhijian 通用 person 字段
PERSON_FIELD_MAP = {
    "uri": "uri",
    "label_chs": "name",
    "label_cht": "name_zh_tw",
    "label_en": "name_en",
    "family_name": "family_name",       # 拼音
    "role_of_family": "role_of_family",
    "courtesy_name": "courtesy_name",   # 字
}

# jiapu.person_relations 字段
RELATION_FIELD_MAP = {
    "src_uri": "source",
    "dst_uri": "target",
    "relation": "type",
}


# ============================================================
# 查询函数
# ============================================================

def _connect(path: Path) -> sqlite3.Connection:
    """开一个连接，row_factory 设成 Row。"""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_person(row: sqlite3.Row) -> Dict:
    """sqlite Row → zhijian 通用 person dict（带 classifier 结果）。"""
    p = {zhijian_key: row[jiapu_key] for jiapu_key, zhijian_key in PERSON_FIELD_MAP.items()
         if row[jiapu_key] is not None}
    p["source"] = "jiapu"
    p["person_type"] = classify_person(dict(p))
    return p


def count_persons(source: str = "jiapu") -> int:
    """jiapu 总人数。"""
    src = source_router.assert_enabled(source)
    with _connect(src["path"]) as conn:
        return conn.execute("SELECT COUNT(*) FROM persons").fetchone()[0]


def list_persons(
    source: str = "jiapu",
    limit: int = 200,
    offset: int = 0,
    surname: Optional[str] = None,
    has_relations: bool = False,
) -> Tuple[List[Dict], int]:
    """分页列人物。

    Args:
        source: 数据源名
        limit: 返回上限
        offset: 跳过
        surname: 按姓过滤（jiapu family_name 是拼音；如 "su"）
        has_relations: 仅返回在 person_relations 出现过的（有 src/dst 关系）

    Returns:
        (persons, total) — 当前页 + 过滤后总人数
    """
    src = source_router.assert_enabled(source)
    with _connect(src["path"]) as conn:
        where_clauses: List[str] = []
        params: List = []

        # 注：persons 所有字段 NOT NULL（空值是空串），不需要 label_chs IS NOT NULL
        # （强制该过滤会令 SQLite 走全表扫描，2M 行 7s+）
        if surname:
            where_clauses.append("family_name = ?")
            params.append(surname)

        if has_relations:
            where_clauses.append(
                "(uri IN (SELECT DISTINCT src_uri FROM person_relations) "
                "OR uri IN (SELECT DISTINCT dst_uri FROM person_relations))"
            )

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # 总数
        total = conn.execute(
            f"SELECT COUNT(*) FROM persons{where_sql}", params
        ).fetchone()[0]

        # 当前页（ORDER BY uri 让 SQLite 用主键索引提前停）
        rows = conn.execute(
            f"SELECT * FROM persons{where_sql} "
            f"ORDER BY uri LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        # Python 层过滤空 label_chs（85/2M，可忽略但保持语义）
        persons = [p for p in (_row_to_person(r) for r in rows) if p.get("name")]
        return persons, total


def get_person(uri: str, source: str = "jiapu") -> Optional[Dict]:
    """按 uri 取单个人物。"""
    src = source_router.assert_enabled(source)
    with _connect(src["path"]) as conn:
        row = conn.execute(
            "SELECT * FROM persons WHERE uri = ?", (uri,)
        ).fetchone()
        return _row_to_person(row) if row else None


def get_person_relations(uri: str, source: str = "jiapu") -> List[Dict]:
    """取一个人物的所有关系（src 或 dst）。"""
    src = source_router.assert_enabled(source)
    with _connect(src["path"]) as conn:
        rows = conn.execute(
            "SELECT * FROM person_relations WHERE src_uri = ? OR dst_uri = ?",
            (uri, uri),
        ).fetchall()
        return [
            {zhijian_key: row[jiapu_key] for jiapu_key, zhijian_key in RELATION_FIELD_MAP.items()}
            for row in rows
        ]


def get_relations_batch(
    source: str = "jiapu",
    limit: int = 1000,
    offset: int = 0,
) -> Tuple[List[Dict], int]:
    """分页列关系。"""
    src = source_router.assert_enabled(source)
    with _connect(src["path"]) as conn:
        total = conn.execute("SELECT COUNT(*) FROM person_relations").fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM person_relations LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        rels = [
            {zhijian_key: row[jiapu_key] for jiapu_key, zhijian_key in RELATION_FIELD_MAP.items()}
            for row in rows
        ]
        return rels, total


def top_surnames(source: str = "jiapu", limit: int = 20) -> List[Dict]:
    """按 family_name 统计，返回 top N 姓。"""
    src = source_router.assert_enabled(source)
    with _connect(src["path"]) as conn:
        rows = conn.execute(
            "SELECT family_name, COUNT(*) as cnt FROM persons "
            "WHERE family_name IS NOT NULL AND family_name != '' "
            "GROUP BY family_name ORDER BY cnt DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_graph_subset(
    source: str = "jiapu",
    limit: int = 500,
    offset: int = 0,
) -> Dict:
    """取图谱可视化的子集：N 个有关系的 person + 他们的关系。

    算法：
    1. 取 person_relations offset..offset+limit
    2. 收集涉及的所有 uri 去重
    3. 查这些 uri 的 persons 信息
    4. 返回 {nodes, links}
    """
    src = source_router.assert_enabled(source)
    with _connect(src["path"]) as conn:
        # 取一段关系
        rows = conn.execute(
            "SELECT * FROM person_relations LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        if not rows:
            return {"nodes": [], "links": [], "total_persons": 0, "total_links": 0}

        uris = set()
        links = []
        for r in rows:
            uris.add(r["src_uri"])
            uris.add(r["dst_uri"])
            links.append({
                "source": r["src_uri"],
                "target": r["dst_uri"],
                "name": r["relation"],
                "relation": r["relation"],
            })

        # 查这些 person
        placeholders = ",".join("?" * len(uris))
        person_rows = conn.execute(
            f"SELECT * FROM persons WHERE uri IN ({placeholders})",
            list(uris),
        ).fetchall()

        nodes = [_row_to_person(r) for r in person_rows]

        # 统计总关系数
        total_links = conn.execute("SELECT COUNT(*) FROM person_relations").fetchone()[0]

        return {
            "nodes": nodes,
            "links": links,
            "total_persons": len(nodes),
            "total_links": total_links,
        }
