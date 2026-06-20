"""
按数据源灌库脚本（M8）

Why：M8 RAG 分 collection。每数据源灌到独立 collection (zhijian_{source})，
避免不同来源的 chunks 互相污染检索。

How to use:
    # 单源灌库
    python -m scripts.ingest_chroma --source jiapu
    # 跨源：把 jiapu person descriptions 转成 chunks
    python -m scripts.ingest_chroma --source jiapu --from-db \\
        --db-path D:/上海图书馆开放数据/data/shlib_jiapu.db \\
        --extract-type work_descriptions

支持的数据源：
- jiapu：家谱元数据（work descriptions, person biographies）
- 1998：1998 年清苑县志（默认 data/raw/1998/*.txt）
- memory：in-memory KG（73 个样本人物 biography）
"""
import argparse
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 必须在 sys.path.insert 之后
from app.rag.rag_service import get_rag_service
from app.database.source_router import SOURCES


# ============================================================
# 各数据源的内容提取器
# ============================================================

def extract_from_1998(data_dir: Path) -> List[Dict]:
    """1998 清苑县志：data/raw/1998/*.txt。"""
    SKIP = {"图片.txt", "封面.txt", "目录 (2).txt"}
    texts = []
    for txt_file in sorted(data_dir.glob("*.txt")):
        if txt_file.name in SKIP:
            continue
        content = txt_file.read_text(encoding="utf-8").strip()
        if len(content) < 50:
            continue
        texts.append({
            "title": txt_file.stem,
            "text": content,
            "metadata": {"source": str(txt_file), "extractor": "1998_dir"},
        })
    return texts


def extract_from_jiapu_db(db_path: Path, extract_type: str = "work_descriptions",
                         limit: int = 10000) -> List[Dict]:
    """家谱 SQLite：按 extract_type 取内容。"""
    conn = sqlite3.connect(str(db_path))
    texts = []

    if extract_type == "work_descriptions":
        # work.graph descriptions：始迁祖迁徙叙事
        rows = conn.execute(
            """SELECT work_uri, title, description
            FROM works
            WHERE description IS NOT NULL AND description != ''
            LIMIT ?""",
            (limit,),
        ).fetchall()
        for r in rows:
            texts.append({
                "title": f"家谱-{r[1] or r[0]}",
                "text": r[2],
                "metadata": {
                    "source": "shlib_jiapu",
                    "extractor": "work_descriptions",
                    "work_uri": r[0],
                },
            })

    elif extract_type == "person_biographies":
        # person biography 字段（很多为空，跳过）
        rows = conn.execute(
            """SELECT uri, label_chs, description
            FROM persons
            WHERE description IS NOT NULL AND description != ''
            LIMIT ?""",
            (limit,),
        ).fetchall()
        for r in rows:
            texts.append({
                "title": f"人物-{r[1] or r[0]}",
                "text": r[2],
                "metadata": {
                    "source": "shlib_jiapu",
                    "extractor": "person_biographies",
                    "person_uri": r[0],
                },
            })

    elif extract_type == "place_records":
        # places：地名记录
        rows = conn.execute(
            """SELECT uri, label_chs, description
            FROM places
            WHERE description IS NOT NULL AND description != ''
            LIMIT ?""",
            (limit,),
        ).fetchall()
        for r in rows:
            texts.append({
                "title": f"地名-{r[1] or r[0]}",
                "text": r[2],
                "metadata": {
                    "source": "shlib_jiapu",
                    "extractor": "place_records",
                    "place_uri": r[0],
                },
            })
    else:
        raise ValueError(f"未知 extract_type: {extract_type}")

    conn.close()
    return texts


def extract_from_memory_kg() -> List[Dict]:
    """in-memory KG：73 个样本人物的 biography。"""
    from app.database.kg_service import KnowledgeGraphService
    svc = KnowledgeGraphService()
    texts = []
    for p in svc.get_all_persons(limit=200):
        bio = p.get("biography", "")
        if not bio or len(bio) < 10:
            continue
        texts.append({
            "title": p["name"],
            "text": bio,
            "metadata": {
                "source": "memory_kg",
                "extractor": "person_biography",
                "dynasty": p.get("dynasty", ""),
            },
        })
    return texts


# ============================================================
# 灌库主流程
# ============================================================

def ingest_source(
    source: str,
    texts: List[Dict],
    collection: str = None,
    rebuild: bool = True,
) -> Dict:
    """灌库到指定 collection。"""
    if not texts:
        return {"status": "skipped", "reason": "no texts", "source": source}

    collection_name = collection or f"zhijian_{source}"
    rag = get_rag_service()
    original = rag.collection_name
    try:
        rag.collection_name = collection_name
        retriever = rag._get_retriever()
        client = retriever.vector_client

        if rebuild and client.has_collection(collection_name):
            client.drop_collection(collection_name)
            print(f"[{source}] 已删除旧 collection: {collection_name}")

        if not client.has_collection(collection_name):
            embedder = rag._get_embedder()
            client.create_collection(collection_name, dimension=embedder.embedding_dim)
            print(f"[{source}] 已创建 collection: {collection_name}")

        results = rag.ingest_documents(texts)
        total_chunks = sum(r.get("chunk_count", 0) for r in results if r.get("status") == "success")
        return {
            "status": "success",
            "source": source,
            "collection": collection_name,
            "total_docs": len(texts),
            "total_chunks": total_chunks,
        }
    finally:
        rag.collection_name = original


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="按数据源灌 RAG 库")
    parser.add_argument("--source", required=True,
                       choices=["1998", "jiapu", "memory"])
    parser.add_argument("--collection", default=None,
                       help="覆盖默认 collection 名（默认 zhijian_{source}）")
    parser.add_argument("--from-db", action="store_true",
                       help="从 SQLite 数据库提取（jiapu 专用）")
    parser.add_argument("--db-path", default=None,
                       help="SQLite 数据库路径（覆盖 source_router）")
    parser.add_argument("--extract-type", default="work_descriptions",
                       choices=["work_descriptions", "person_biographies", "place_records"])
    parser.add_argument("--limit", type=int, default=10000,
                       help="从 SQLite 取的记录上限")
    parser.add_argument("--data-dir", default="data/raw/1998",
                       help="1998 数据目录")
    parser.add_argument("--no-rebuild", action="store_true",
                       help="不重建 collection（追加）")
    args = parser.parse_args()

    t0 = time.time()
    texts = []

    if args.source == "1998":
        data_dir = Path(args.data_dir)
        if not data_dir.is_absolute():
            data_dir = PROJECT_ROOT / data_dir
        texts = extract_from_1998(data_dir)

    elif args.source == "jiapu":
        if args.from_db:
            db_path = Path(args.db_path) if args.db_path else SOURCES["jiapu"]["path"]
            texts = extract_from_jiapu_db(db_path, args.extract_type, args.limit)
        else:
            raise ValueError("jiapu 源需要 --from-db")

    elif args.source == "memory":
        texts = extract_from_memory_kg()

    print(f"[extract] {args.source}: {len(texts)} docs")
    result = ingest_source(
        source=args.source,
        texts=texts,
        collection=args.collection,
        rebuild=not args.no_rebuild,
    )
    print(f"[result] {result}")
    print(f"[time] {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()