"""
Phase B-6: build_name_lexicon.py
输出 data/processed/name_lexicon.json：字/号/讳别名表。

策略：聚合 persons 的 (name + courtesy + pseudonym)，构造：
  - 别名表: alias → [(canonical_name, type, count), ...]
  - 字表: courtesy_name → [(name, count), ...]
  - 号表: pseudonym → [(name, count), ...]

用于前端"逐句"搜索（输入字/号可跳转到对应人物）。

输出 schema:
{
  "version": 1,
  "total_names": 165022,
  "courtesy_total": 12835,
  "pseudonym_total": 3674,
  "by_courtesy": [
    {"alias": "元之", "names": ["王时"], "count": 1},
    ...
  ],
  "by_pseudonym": [
    {"alias": "半山", "names": ["王安石"], "count": 1},
    ...
  ]
}

用法：
  python pipeline/build_name_lexicon.py
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PERSONS = ROOT / "data" / "processed" / "persons.jsonl"
OUT_PATH = ROOT / "data" / "processed" / "name_lexicon.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--persons", default=str(PERSONS))
    ap.add_argument("--out", default=str(OUT_PATH))
    ap.add_argument("--min-count", type=int, default=1,
                    help="min count to include in alias index")
    args = ap.parse_args()

    courtesy_counter: Counter = Counter()
    courtesy_to_names: dict[str, Counter] = defaultdict(Counter)
    pseudonym_counter: Counter = Counter()
    pseudonym_to_names: dict[str, Counter] = defaultdict(Counter)
    total_names = 0

    with open(args.persons, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            name = r["name"]
            courtesy = r["courtesy"].strip()
            pseudonym = r["pseudonym"].strip()
            if name:
                total_names += 1
            if courtesy:
                courtesy_counter[courtesy] += 1
                courtesy_to_names[courtesy][name] += 1
            if pseudonym:
                pseudonym_counter[pseudonym] += 1
                pseudonym_to_names[pseudonym][name] += 1

    def build_index(counter: Counter, to_names: dict) -> list[dict]:
        out = []
        for alias, c in counter.most_common():
            if c < args.min_count:
                continue
            names = sorted(to_names[alias].items(), key=lambda x: -x[1])
            out.append({"alias": alias, "count": c, "names": [n for n, _ in names]})
        return out

    by_courtesy = build_index(courtesy_counter, courtesy_to_names)
    by_pseudonym = build_index(pseudonym_counter, pseudonym_to_names)

    out = {
        "version": 1,
        "total_names": total_names,
        "courtesy_total": sum(courtesy_counter.values()),
        "pseudonym_total": sum(pseudonym_counter.values()),
        "courtesy_unique": len(by_courtesy),
        "pseudonym_unique": len(by_pseudonym),
        "by_courtesy": by_courtesy,
        "by_pseudonym": by_pseudonym,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"total_names: {total_names}")
    print(f"courtesy: total={out['courtesy_total']} unique={out['courtesy_unique']}")
    print(f"pseudonym: total={out['pseudonym_total']} unique={out['pseudonym_unique']}")
    print(f"top 10 courtesy:")
    for r in by_courtesy[:10]:
        print(f"  {r['alias']!r:<8} count={r['count']:>3}  first={r['names'][:3]}")
    print(f"top 10 pseudonym:")
    for r in by_pseudonym[:10]:
        print(f"  {r['alias']!r:<8} count={r['count']:>3}  first={r['names'][:3]}")
    print(f"out: {out_path}")


if __name__ == "__main__":
    main()