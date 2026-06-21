"""
Phase B-4: build_dynasties.py
输出 data/processed/dynasties.json。

复用 dynasty_normalize.DYNASTIES（16 个标准 key）+ 从 persons.jsonl 统计每个朝代的
实际人数，作为辅助元数据。

输出 schema:
{
  "version": 1,
  "count": 16,
  "dynasties": [
    {"id": 0, "key": "shang", "label": "商", "pinyin": "shang",
     "earliest": -1600, "latest": -1046, "persons": 80},
    ...
  ]
}
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PERSONS = ROOT / "data" / "processed" / "persons.jsonl"
OUT_PATH = ROOT / "data" / "processed" / "dynasties.json"

import sys
sys.path.insert(0, str(ROOT / "pipeline"))
from dynasty_normalize import DYNASTIES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--persons", default=str(PERSONS))
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args()

    counts = Counter()
    with open(args.persons, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            counts[r["dynasty"]] += 1

    out = {"version": 1, "count": len(DYNASTIES), "dynasties": []}
    for d in DYNASTIES:
        out["dynasties"].append({
            "id":       d["id"],
            "key":      d["key"],
            "label":    d["label"],
            "pinyin":   d["pinyin"],
            "earliest": d["earliest"],
            "latest":   d["latest"],
            "persons":  counts.get(d["key"], 0),
        })

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"written {len(DYNASTIES)} dynasties")
    for d in out["dynasties"]:
        print(f"  id={d['id']:>2} {d['label']:<8} ({d['key']:<14}) persons={d['persons']:>6}")
    print(f"out: {out_path}")


if __name__ == "__main__":
    main()