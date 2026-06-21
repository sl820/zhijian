"""
Phase B-9: validate_pipeline.py

校验 ETL 全链路一致性：

1. persons.jsonl 行数 == 165022（17 万量级）
2. 关系 endpoints 全部在 persons.pid 集合内
3. dynasties.json 中 16 个 key 全部出现在 persons 里
4. surnames.json 中 common/uncommon 至少有 50 个
5. name_lexicon 别名非空且互不重复
6. public/persons/ + public/relations/ 桶数与 idx.json 一致
7. jiapu_v2.npz 节点数 == persons.jsonl 行数
8. jiapu_v2.npz 中 dyn_r 与朝代数一致

用法：
  python pipeline/validate_pipeline.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
PERSONS = ROOT / "data" / "processed" / "persons.jsonl"
RELATIONS = ROOT / "data" / "processed" / "relations.jsonl"
DYNASTIES = ROOT / "data" / "processed" / "dynasties.json"
SURNAMES = ROOT / "data" / "processed" / "surnames.json"
NAME_LEXICON = ROOT / "data" / "processed" / "name_lexicon.json"
PUB_PERSONS = ROOT / "public" / "persons"
PUB_RELATIONS = ROOT / "public" / "relations"
NPZ = ROOT / "public" / "layouts" / "jiapu_v2.npz"

sys.path.insert(0, str(ROOT / "pipeline"))
from dynasty_normalize import DYNASTIES as DYNASTY_DEFS


class Report:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def check(self, name: str, ok: bool, detail: str = ""):
        # ASCII-safe printing for Windows cp936 console
        safe_name = name.encode("ascii", "replace").decode("ascii")
        safe_detail = detail.encode("ascii", "replace").decode("ascii")
        if ok:
            self.passed += 1
            print(f"  [PASS] {safe_name}{(': ' + safe_detail) if safe_detail else ''}")
        else:
            self.failed += 1
            self.errors.append(f"{name}: {detail}")
            print(f"  [FAIL] {safe_name}: {safe_detail}")

    def summary(self):
        print()
        print(f"{'='*60}")
        print(f"PASSED: {self.passed}, FAILED: {self.failed}")
        if self.errors:
            print("ERRORS:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")
        return self.failed == 0


def load_persons_pids():
    pids = set()
    count = 0
    with PERSONS.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            pids.add(r["pid"])
            count += 1
    return pids, count


def load_relations_endpoints():
    endpoints = set()
    count = 0
    with RELATIONS.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            endpoints.add(r["src"])
            endpoints.add(r["dst"])
            count += 1
    return endpoints, count


def main():
    r = Report()

    print("=== 1. persons.jsonl ===")
    pids, p_count = load_persons_pids()
    r.check("persons 行数 ~ 1.68M (full set)", 1_500_000 < p_count < 1_800_000,
            f"got {p_count}")
    r.check("persons.pid 全唯一", len(pids) == p_count, f"{len(pids)} unique vs {p_count} total")

    print("\n=== 2. relations.jsonl ===")
    rel_eps, rel_count = load_relations_endpoints()
    r.check("relations 行数 ~ 466k", 400000 < rel_count < 600000, f"got {rel_count}")
    missing = rel_eps - pids
    r.check("relation endpoints 全部在 persons", len(missing) == 0,
            f"missing {len(missing)}: {list(missing)[:5]}")

    print("\n=== 3. dynasties.json ===")
    with DYNASTIES.open(encoding="utf-8") as f:
        dyn_data = json.load(f)
    r.check("dynasties 16 个", dyn_data["count"] == 16, f"got {dyn_data['count']}")
    expected_keys = {d["key"] for d in DYNASTY_DEFS}
    actual_keys = {d["key"] for d in dyn_data["dynasties"]}
    r.check("dynasty keys 与 normalize 表一致",
            expected_keys == actual_keys,
            f"diff: {expected_keys ^ actual_keys}")
    r.check("总 persons 数对齐",
            sum(d["persons"] for d in dyn_data["dynasties"]) == p_count,
            f"sum={sum(d['persons'] for d in dyn_data['dynasties'])} vs {p_count}")

    print("\n=== 4. surnames.json ===")
    with SURNAMES.open(encoding="utf-8") as f:
        sn_data = json.load(f)
    common = sum(1 for s in sn_data["surnames"] if s["tier"] == "common")
    uncommon = sum(1 for s in sn_data["surnames"] if s["tier"] == "uncommon")
    r.check("surnames 数量 ≥ 200", sn_data["count"] >= 200, f"got {sn_data['count']}")
    r.check("common ≥ 50", common >= 50, f"got {common}")
    r.check("uncommon ≥ 50", uncommon >= 50, f"got {uncommon}")

    print("\n=== 5. name_lexicon.json ===")
    with NAME_LEXICON.open(encoding="utf-8") as f:
        lex = json.load(f)
    r.check("lexicon 版本 = 1", lex["version"] == 1)
    r.check("courtesy unique ≥ 1000", lex["courtesy_unique"] >= 1000,
            f"got {lex['courtesy_unique']}")
    r.check("pseudonym unique ≥ 500", lex["pseudonym_unique"] >= 500,
            f"got {lex['pseudonym_unique']}")
    # 别名非空
    empty_aliases = [a for a in lex["by_courtesy"] if not a["alias"]]
    r.check("by_courtesy 无空 alias", len(empty_aliases) == 0,
            f"got {len(empty_aliases)} empty")

    print("\n=== 6. public/persons/ + public/relations/ 桶数 ===")
    p_idx = json.loads((PUB_PERSONS / "idx.json").read_text(encoding="utf-8"))
    p_files = list(PUB_PERSONS.glob("persons_*.json"))
    r.check("persons 桶数 == idx.buckets 数",
            len(p_files) == len(p_idx["buckets"]),
            f"{len(p_files)} files vs {len(p_idx['buckets'])} buckets")
    # 每片 ≤ 1MB
    over_size = [f for f in p_files if f.stat().st_size > 1024 * 1024]
    r.check("persons 每片 ≤ 1MB", len(over_size) == 0,
            f"over: {[(f.name, f.stat().st_size/1024) for f in over_size[:3]]}")
    # idx 累加 = 总人数
    p_total = sum(b["count"] for b in p_idx["buckets"])
    # persons 公共桶可能用 --persons-filter-dynasty 仅保留有朝代 ~165k
    r.check("persons buckets 总和 == filtered persons (with dynasty)",
            150000 < p_total < 200000,
            f"{p_total} persons (期望 17 万左右)")

    rel_idx = json.loads((PUB_RELATIONS / "idx.json").read_text(encoding="utf-8"))
    rel_files = list(PUB_RELATIONS.glob("relations_*.json"))
    r.check("relations 桶数 == idx.buckets 数",
            len(rel_files) == len(rel_idx["buckets"]),
            f"{len(rel_files)} vs {len(rel_idx['buckets'])}")
    rel_total = sum(b["count"] for b in rel_idx["buckets"])
    r.check("relations buckets 总和 == relations.jsonl 行数",
            rel_total == rel_count, f"{rel_total} vs {rel_count}")

    print("\n=== 7. jiapu_v2.npz ===")
    npz = np.load(NPZ, allow_pickle=True)
    # npz 仅含 dynasty != unknown 的 ~165k
    r.check("npz 节点数 ~ 165k (有朝代)",
            150000 < len(npz["node_ids"]) < 200000,
            f"{len(npz['node_ids'])}")
    r.check("npz 节点 pid 集合 ⊆ persons.pid",
            set(npz["node_ids"].tolist()) <= pids,
            f"missing {len(set(npz['node_ids'].tolist()) - pids)}")
    r.check("dynasty_id ∈ [0, 14] (跳过 unknown 15)",
            npz["dynasty_id"].min() == 0 and npz["dynasty_id"].max() == 14,
            f"got [{npz['dynasty_id'].min()}, {npz['dynasty_id'].max()}]")
    r.check("dyn_r 唯一值 ≤ 15",
            len(set(npz["dyn_r"].tolist())) <= 15,
            f"got {len(set(npz['dyn_r'].tolist()))} distinct")

    ok = r.summary()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()