"""
Phase B-7: pack_data.py
把 persons.jsonl / relations.jsonl 按 pid 分桶成 Range-friendly 的 JSON。

每片 ≤ 1MB。pid 排序保证可二分查找。
索引 idx.json 含每片 (id, count, start_pid, end_pid, byte_offset, byte_length)。

输出到 public/persons/ 与 public/relations/（运行时由前端 Range 取片）。

用法：
  python pipeline/pack_data.py
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PERSONS = ROOT / "data" / "processed" / "persons.jsonl"
RELATIONS = ROOT / "data" / "processed" / "relations.jsonl"
OUT_PERSONS = ROOT / "public" / "persons"
OUT_RELATIONS = ROOT / "public" / "relations"

MAX_BUCKET_BYTES = 900 * 1024  # 900KB，留余量 < 1MB


def pack_jsonl(
    src: Path,
    out_dir: Path,
    prefix: str,
    sort_key: str = "pid",
    filter_fn=None,
) -> dict:
    """jsonl → 按 (rows) 分桶 + idx.json。

    filter_fn: 可选过滤函数 (row) -> bool；返回 False 的行跳过。
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # 先全部读入（persons 167 万行 ≈ 600 MB，内存可接受）
    rows = []
    with src.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if filter_fn is not None and not filter_fn(r):
                continue
            rows.append(r)

    # 按指定字段排序（persons 用 pid，relations 用 src）
    rows.sort(key=lambda r: r[sort_key])

    idx = []
    cur_bucket = []
    cur_bytes = 2  # 起始 '['
    bid = 0
    tmp_path = out_dir / f"{prefix}_{bid:04d}.tmp"

    def flush(bid: int, cur_bucket: list[dict], cur_bytes: int) -> tuple[int, int]:
        # 写 bucket
        path = out_dir / f"{prefix}_{bid:04d}.json"
        with path.open("w", encoding="utf-8") as f:
            f.write("[")
            for i, r in enumerate(cur_bucket):
                if i > 0:
                    f.write(",")
                f.write(json.dumps(r, ensure_ascii=False))
            f.write("]")
        return len(cur_bucket), cur_bytes

    for r in rows:
        s = json.dumps(r, ensure_ascii=False)
        if cur_bucket:
            line_bytes = len(s.encode("utf-8")) + 1  # +1 for comma
        else:
            line_bytes = len(s.encode("utf-8"))
        # 检查是否需要切桶
        if cur_bytes + line_bytes + 1 > MAX_BUCKET_BYTES and cur_bucket:  # +1 for closing ]
            count, bytes_used = flush(bid, cur_bucket, cur_bytes)
            idx.append({
                "id": bid,
                "count": count,
                "bytes": bytes_used,
                "start_pid": cur_bucket[0].get("pid") or cur_bucket[0].get("src", ""),
                "end_pid": cur_bucket[-1].get("pid") or cur_bucket[-1].get("src", ""),
            })
            bid += 1
            cur_bucket = []
            cur_bytes = 2
        cur_bucket.append(r)
        cur_bytes += line_bytes

    if cur_bucket:
        count, bytes_used = flush(bid, cur_bucket, cur_bytes)
        idx.append({
            "id": bid,
            "count": count,
            "bytes": bytes_used,
            "start_pid": cur_bucket[0].get("pid") or cur_bucket[0].get("src", ""),
            "end_pid": cur_bucket[-1].get("pid") or cur_bucket[-1].get("src", ""),
        })

    # 写 idx.json
    with (out_dir / "idx.json").open("w", encoding="utf-8") as f:
        json.dump({"version": 1, "prefix": prefix, "buckets": idx}, f, ensure_ascii=False, indent=2)

    total = sum(b["count"] for b in idx)
    print(f"{prefix}: {len(idx)} buckets, {total} rows")
    for b in idx[:5]:
        print(f"  bucket {b['id']}: {b['count']} rows, {b['bytes']/1024:.1f} KB, "
              f"{b['start_pid']} → {b['end_pid']}")
    if len(idx) > 5:
        print(f"  ... ({len(idx)-5} more)")
    return {"buckets": len(idx), "total": total}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--persons", default=str(PERSONS))
    ap.add_argument("--relations", default=str(RELATIONS))
    ap.add_argument("--out-persons", default=str(OUT_PERSONS))
    ap.add_argument("--out-relations", default=str(OUT_RELATIONS))
    ap.add_argument("--persons-filter-dynasty", action="store_true",
                    help="公共 persons 只保留有朝代的（节省仓库空间 ~80%%）")
    args = ap.parse_args()

    print("=== packing persons ===")
    if args.persons_filter_dynasty:
        print("  [filter] 只保留 dynasty != 'unknown'")
    p_stats = pack_jsonl(
        Path(args.persons), Path(args.out_persons), "persons", sort_key="pid",
        filter_fn=(lambda r: r["dynasty"] != "unknown") if args.persons_filter_dynasty else None,
    )
    print(f"persons out: {args.out_persons}")

    print("\n=== packing relations ===")
    r_stats = pack_jsonl(Path(args.relations), Path(args.out_relations), "relations", sort_key="src")
    print(f"relations out: {args.out_relations}")


if __name__ == "__main__":
    main()