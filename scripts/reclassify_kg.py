"""
一次性脚本：对 data/processed/kg_state.json 现有节点重跑分类。

Why：73 节点全 person_type=2（棕色），M3 修复后需要把已持久化的数据重算。
How：读 json → 调 classify_person → 写回 json。

对 SQLite 来源（jiapu 2M+ 节点）此脚本不适用；那边走 M5 的 SQL UPDATE 路径。
"""
import json
import sys
from pathlib import Path

# 加项目根到 path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.kg.classifier import classify_person, CATEGORY_CLAN, CATEGORY_WIFE, CATEGORY_OTHER, CATEGORY_OFFICIAL  # noqa: E402


KG_PATH = PROJECT_ROOT / "data" / "processed" / "kg_state.json"


def main():
    if not KG_PATH.exists():
        print(f"❌ KG 持久化文件不存在: {KG_PATH}")
        sys.exit(1)

    data = json.loads(KG_PATH.read_text(encoding="utf-8"))
    persons = data.get("persons", [])
    print(f"读取 {len(persons)} 个 person")

    before = [p.get("person_type", -1) for p in persons]
    reclassified = 0
    for p in persons:
        old = p.get("person_type", 2)
        new = classify_person(p)
        if new != old:
            reclassified += 1
        p["person_type"] = new

    # 写回
    KG_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 统计
    after = [p.get("person_type", 0) for p in persons]
    print(f"\n重新分类 {reclassified} 个节点（{len(persons) - reclassified} 个原本就对）")
    print(f"\n分类前分布: {dict((c, before.count(c)) for c in {0, 1, 2, 3})}")
    print(f"分类后分布: {dict((c, after.count(c)) for c in {0, 1, 2, 3})}")
    print(f"  0 (氏族):  {after.count(CATEGORY_CLAN)}")
    print(f"  1 (妻妾):  {after.count(CATEGORY_WIFE)}")
    print(f"  2 (其他):  {after.count(CATEGORY_OTHER)}")
    print(f"  3 (官吏):  {after.count(CATEGORY_OFFICIAL)}")

    print(f"\n[OK] 已写回 {KG_PATH}")


if __name__ == "__main__":
    main()
