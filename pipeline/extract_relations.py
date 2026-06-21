"""
Phase B-3: extract_relations.py
从 shlib_jiapu.db 抽关系网（两源合并），写 data/processed/relations.jsonl。

两源：
  A) person_relations 13k 行
     schema: (src_uri, dst_uri, relation)
     relation 取值: spouseOf / parentOf / childOf
     → 已标准化，直接用

  B) cbdb_relations 588k 行
     schema: (uri, subject_uri, object_uri, relation_label, special_type, source, raw_json)
     relation_label 取值: 子/父/兄/弟/丈夫/妻子/祖父/孫/母/曾孫/曾祖/岳父/女婿/女兒/墓誌銘由Y所作/...
     → 归一化为 parentOf / childOf / siblingOf / spouseOf / other
     注意 special_type = "亲属关系" 才是真亲缘；其他（社会/文学）归 other

归一化规则（基于 cbdb relation_label）：
  - 父/继父/岳父/祖父/曾祖/高祖/外祖父 → parentOf
  - 子/继子/长子/女兒/女婿/孫/曾孫/外孫/外孙 → childOf
  - 兄/弟/姐妹 → siblingOf
  - 丈夫/妻子/第二任妻/继配/继室 → spouseOf
  - 其他（社会/文学/政治/墓誌銘/書序等）→ "other"

输出字段：
  src          str  - 源 pid
  dst          str  - 目标 pid
  rel          str  - parentOf / childOf / siblingOf / spouseOf / other
  source       str  - "jiapu" | "cbdb"
  raw_label    str  - 原始 cbdb 标签（仅 cbdb；jiapu 留空）

用法：
  python pipeline/extract_relations.py
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(r"D:/上海图书馆开放数据/data/shlib_jiapu.db")
OUT_PATH = ROOT / "data" / "processed" / "relations.jsonl"


def pid_from_uri(uri: str) -> str:
    return uri.rsplit("/", 1)[-1][:16]


# CBDB relation_label → 标准 rel
_PARENT_LABELS = {
    "父", "继父", "岳父", "祖父", "曾祖", "高祖", "外祖父", "伯父", "叔父",
    "继父; 继父", "父; 父", "祖父; 祖父", "前夫", "後父",
}
_CHILD_LABELS = {
    "子", "继子", "長子; 第一子", "女兒", "女婿", "孫", "曾孫; 重孫", "外孫",
    "曾孫", "外孙", "第二子", "第三子", "第四子", "第五子", "第六子",
    "長子", "次子", "三子", "四子", "五子", "七子", "幼子", "末子",
    "女儿", "长子", "次女", "长女", "幼女",
}
_SIBLING_LABELS = {
    "兄", "弟", "姐妹", "姐", "姊", "妹", "兄; 兄", "弟; 弟",
}
_SPOUSE_LABELS = {
    "丈夫", "妻子", "第二任妻", "继配", "继室", "妾", "前妻", "後妻",
    "妻", "夫", "继妻",
}


def cbdb_rel_to_standard(label: str | None) -> str:
    if not label:
        return "other"
    if label in _PARENT_LABELS:
        return "parentOf"
    if label in _CHILD_LABELS:
        return "childOf"
    if label in _SIBLING_LABELS:
        return "siblingOf"
    if label in _SPOUSE_LABELS:
        return "spouseOf"
    # 模糊匹配（处理 "父; XXX" 复合标签）
    if "父" in label and "伯父" not in label and "叔父" not in label and "岳父" not in label:
        return "parentOf"
    if "子" in label and "妻子" not in label and "女婿" not in label and "继子" not in label:
        # 但"妻子"包含"子"字，需要排除
        # 进一步：实际"子"出现的标签基本都是子嗣
        return "childOf"
    if "孫" in label or "孙" in label:
        return "childOf"
    if "妻" in label or "夫" in label:
        return "spouseOf"
    if "兄" in label or "弟" in label or "姐" in label or "妹" in label:
        return "siblingOf"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    # 先把 persons.pid 集合准备好（用于过滤 — 端点必须在 persons.jsonl 里）
    # 为效率，仅抽 pid 集合
    print("loading persons pid set...")
    pids = set()
    cur.execute("SELECT uri FROM persons")
    for (uri,) in cur.fetchall():
        pids.add(pid_from_uri(uri))
    print(f"  pid pool: {len(pids)}")

    written = 0
    skipped_endpoint = 0
    with out_path.open("w", encoding="utf-8") as f:
        # ---- A) person_relations ----
        cur.execute("SELECT src_uri, dst_uri, relation FROM person_relations")
        for src_uri, dst_uri, rel in cur.fetchall():
            src = pid_from_uri(src_uri)
            dst = pid_from_uri(dst_uri)
            if src not in pids or dst not in pids:
                skipped_endpoint += 1
                continue
            rec = {"src": src, "dst": dst, "rel": rel, "source": "jiapu", "raw_label": ""}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1

        print(f"  after person_relations: {written}")

        # ---- B) cbdb_relations (only special_type='亲属关系') ----
        cur.execute("""
            SELECT subject_uri, object_uri, relation_label, special_type
            FROM cbdb_relations
            WHERE special_type = '亲属关系'
        """)
        cbdb_kept = 0
        for src_uri, dst_uri, label, spec in cur.fetchall():
            src = pid_from_uri(src_uri)
            dst = pid_from_uri(dst_uri)
            if src not in pids or dst not in pids:
                skipped_endpoint += 1
                continue
            rel = cbdb_rel_to_standard(label)
            rec = {"src": src, "dst": dst, "rel": rel, "source": "cbdb", "raw_label": label or ""}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1
            cbdb_kept += 1
            if cbdb_kept % 50000 == 0:
                print(f"  ...cbdb {cbdb_kept} rows")

    print(f"done. written={written}, skipped_endpoint={skipped_endpoint}")
    print(f"out: {out_path}")
    conn.close()


if __name__ == "__main__":
    main()