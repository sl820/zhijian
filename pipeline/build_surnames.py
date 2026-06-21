"""
Phase B-5: build_surnames.py
输出 data/processed/surnames.json：百家姓 hash 表。

数据源：
  A) shlib_jiapu.familynames（611 条，label_chs = 简体汉字）
  B) persons.family_name（拼音）与 familynames.label_chs 映射

输出 schema:
{
  "version": 1,
  "count": 611,
  "surnames": [
    {"key": "fu", "han": "傅", "angle": 0.0123, "count": 1234, "tier": "common"},
    ...
  ]
}

angle：用于星云角向 hash（0..1，乘 2π 即弧度）
  策略：按 surname 总人数从高到低排序，angle = idx / count（均匀分布）
tier: 1000+ → common, 100-999 → uncommon, < 100 → rare

用法：
  python pipeline/build_surnames.py
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(r"D:/上海图书馆开放数据/data/shlib_jiapu.db")
PERSONS = ROOT / "data" / "processed" / "persons.jsonl"
OUT_PATH = ROOT / "data" / "processed" / "surnames.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--persons", default=str(PERSONS))
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    # ---- A) familynames: pinyin → han ----
    pinyin_to_han = {}
    cur.execute("SELECT label_chs FROM familynames WHERE label_chs IS NOT NULL AND label_chs != ''")
    for (han,) in cur.fetchall():
        # han 字段实际是 拼音（如 "fu"/"yuan"/"fu"），不是汉字
        # 用 raw_json 提
        pass

    # 改：读 raw_json
    pinyin_to_han = {}
    cur.execute("SELECT raw_json FROM familynames WHERE raw_json IS NOT NULL AND raw_json != ''")
    for (raw,) in cur.fetchall():
        try:
            j = json.loads(raw)
            label_arr = j.get("label") or j.get("http://bibframe.org/vocab/label") or []
            if isinstance(label_arr, list) and len(label_arr) >= 2:
                pinyin = label_arr[0]  # "fu"
                han = label_arr[1]     # "傅"
                if pinyin and han and pinyin != han:
                    pinyin_to_han[pinyin] = han
        except Exception:
            pass

    print(f"familynames: {len(pinyin_to_han)} pinyin→han mappings")

    # ---- B) persons 中 family_name 计数（按拼音聚合）----
    family_name_counts = Counter()
    with open(args.persons, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            fn = r.get("family_name", "").strip()
            if fn:
                family_name_counts[fn] += 1

    # ---- 合并 ----
    # 取所有用过的拼音 + familynames 全部
    all_keys = set(family_name_counts.keys()) | set(pinyin_to_han.keys())
    rows = []
    for k in all_keys:
        han = pinyin_to_han.get(k, k)
        c = family_name_counts.get(k, 0)
        rows.append({"key": k, "han": han, "count": c})

    # 排序：count desc → angle 均匀
    rows.sort(key=lambda x: (-x["count"], x["key"]))
    n = len(rows)
    for i, r in enumerate(rows):
        r["angle"] = (i + 0.5) / n  # 中心化（0..1）
        if r["count"] >= 800:
            r["tier"] = "common"
        elif r["count"] >= 100:
            r["tier"] = "uncommon"
        elif r["count"] > 0:
            r["tier"] = "rare"
        else:
            r["tier"] = "unused"

    out = {"version": 1, "count": n, "surnames": rows}

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"written {n} surnames")
    print(f"top 20:")
    for r in rows[:20]:
        print(f"  {r['key']:<8} {r['han']:<6} count={r['count']:>6} angle={r['angle']:.4f} tier={r['tier']}")
    print(f"out: {out_path}")
    conn.close()


if __name__ == "__main__":
    main()