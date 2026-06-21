"""
Phase B-8: precompute_layout.py

v2 布局策略（替代 v1 FA2 二维）：

  朝代同心壳（径向 r）
  + 姓氏 hash（角向 θ）
  + 世代号（高度 z）

r:
  15 朝代 key（id 0..14），加上 unknown(id 15)
  r(id) = (id + 1) * R_SHELL
  R_SHELL = 100（同诗云风格）
  unknown 半径 = 16 * 100 + 50 (最外圈)

θ:
  姓氏 hash 表（surnames.json 中的 angle 0..1）
  θ = angle * 2π
  未知姓氏 → 散到 θ=0..2π 均匀

z:
  世代号 — v2 暂用 heuristic：
    family_role 包含 "始祖/显祖/世祖" → gen = 0
    family_role 包含 "支祖" → gen = 1
    其他人 → gen = 2 (默认子代)
    order_of_seniority 解析为数字（"三"/"十七郎"/"三七" 等）作为同代内排序
  z = gen * Z_STEP + jitter(Z_STEP * 0.2)
  Z_STEP = 8

输出 jiapu_v2.npz（v1 同 schema + r/theta 字段）：
  node_ids: list of pid strings
  x, y, z:   float32（z 已含世代）
  radius:   朝代壳半径
  angle:    角向（0..2π）
  dynasty_id: int32
  generation: int32

Edge: 暂不写（运行时从 relations/{bucket}.json 拉取，FA2 算法路径已不在 v2 范围）

用法：
  python pipeline/precompute_layout.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
PERSONS = ROOT / "data" / "processed" / "persons.jsonl"
DYNASTIES = ROOT / "data" / "processed" / "dynasties.json"
SURNAMES = ROOT / "data" / "processed" / "surnames.json"
OUT = ROOT / "public" / "layouts" / "jiapu_v2.npz"

sys.path.insert(0, str(ROOT / "pipeline"))
from dynasty_normalize import DYNASTIES as DYNASTY_DEFS, KEY2ID

R_SHELL = 100.0      # 朝代壳间距
Z_STEP = 8.0         # 世代步长
Z_JITTER = 1.5       # 同代内抖动幅度


def parse_generation(role: str, order: str, label_type: str) -> int:
    """从 family_role + order_of_seniority 推断世代号。

    启发式：
      - shi-zu/shi-qian-zu (始祖/始迁祖) → gen 0
      - xian-zu/zhi-zu (显祖/支祖) → gen 1
      - yuan-zu/bi-zu/yuan-zu 等 → gen 0（祖代）
      - ming-ren (名人) → gen 2（默认子代）
      - 默认 gen 2
    """
    if role.startswith("shi-qian-zu") or role == "shi-zu" or role.startswith("yuan-zu"):
        return 0
    if role.startswith("xian-zu") or role.startswith("zhi-zu") or role.startswith("fang-zu"):
        return 1
    return 2


def chinese_to_int(s: str) -> int:
    """解析 order_of_seniority 字符串中的数字（如 '三'/'十七'/'三十七'/'政一'/'季七'）。

    返回 -1 表示无法解析（视为缺失）。
    """
    if not s:
        return -1
    digits = "〇一二三四五六七八九十百千零"
    n_map = {d: i for i, d in enumerate(digits)}
    # 简单规则：最后字符如果是 digits → 取其值
    last = s[-1]
    if last in n_map:
        return n_map[last]
    # 否则扫描所有 digits
    nums = [n_map[c] for c in s if c in n_map]
    if nums:
        return nums[0]
    return -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--persons", default=str(PERSONS))
    ap.add_argument("--dynasties", default=str(DYNASTIES))
    ap.add_argument("--surnames", default=str(SURNAMES))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--with-fa2-jitter", action="store_true",
                    help="在 (angle, z) 上叠加 FA2 偏移（v1 算法；默认关闭走纯壳）")
    args = ap.parse_args()

    # 加载 dynasty / surname 表
    with open(args.dynasties, encoding="utf-8") as f:
        dyn_data = json.load(f)
    dyn_id_by_key = {d["key"]: d["id"] for d in dyn_data["dynasties"]}

    with open(args.surnames, encoding="utf-8") as f:
        sn_data = json.load(f)
    sn_angle_by_key = {s["key"]: s["angle"] for s in sn_data["surnames"]}

    # 加载 persons（默认全集；只用有朝代的 17 万做布局）
    print(f"loading {args.persons} ...")
    pids = []
    names = []
    family_keys = []
    dynasty_ids = []
    generations = []
    order_ints = []
    with open(args.persons, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["dynasty"] == "unknown":
                continue  # 跳过无朝代 person
            pids.append(r["pid"])
            names.append(r["name"])
            family_keys.append(r["family_name"])
            dynasty_ids.append(dyn_id_by_key.get(r["dynasty"], 15))  # 15=unknown
            generations.append(parse_generation(r["family_role"], r["order"], r["label_type"]))
            order_ints.append(chinese_to_int(r["order"]))
    n = len(pids)
    print(f"  {n} persons (有朝代)")

    # 计算 (r, theta, z)
    radii = np.array([(dyn_id + 1) * R_SHELL for dyn_id in dynasty_ids], dtype=np.float32)

    # 角向 — 同朝代内均匀分布到 2π，按姓氏 hash 落到 0..1 上
    # 简化：angle = surname_angle * 2π
    angles = np.zeros(n, dtype=np.float32)
    for i, fn in enumerate(family_keys):
        a = sn_angle_by_key.get(fn)
        if a is None:
            # 未知姓氏：按家族 URI 散列兜底
            a = (hash(fn) % 1000) / 1000.0
        angles[i] = a * 2 * np.pi

    # z 轴 — 世代 * Z_STEP + 同代内顺序抖动
    z = np.array([gen * Z_STEP for gen in generations], dtype=np.float32)
    rng = np.random.RandomState(42)
    # 同代内按 order 排序后再 jitter，呈现"辈分高低"
    for gen_val in set(generations):
        mask = np.array(generations) == gen_val
        idx_in_gen = np.where(mask)[0]
        order_vals = np.array([order_ints[i] for i in idx_in_gen])
        # 缺失 order 的赋 +inf（沉到末尾）
        max_o = max([o for o in order_vals if o >= 0] + [10])
        order_vals = np.where(order_vals < 0, max_o + 1, order_vals)
        # 同代内按 order 排序
        sort_idx = np.argsort(order_vals)
        sorted_idx_in_gen = idx_in_gen[sort_idx]
        # 在 z 上加均匀 jitter
        z[sorted_idx_in_gen] += rng.uniform(-Z_JITTER, Z_JITTER, len(sorted_idx_in_gen))

    # x, y = r * cos(theta), r * sin(theta)
    x = (radii * np.cos(angles)).astype(np.float32)
    y = (radii * np.sin(angles)).astype(np.float32)

    # radius 字段复用 — 给前端做 sphere 碰撞，半径按辈分
    node_radii = np.where(np.array(generations) == 0, 2.0, 1.0).astype(np.float32)
    # hub: 同家族人数 > 50 的家族代表 → radius 1.5
    # 这里简化：暂时不做 hub 半径放大

    # 写 npz
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out_path,
        node_ids=np.array(pids, dtype=object),
        x=x, y=y, z=z,
        radius=node_radii,
        dyn_r=radii,
        angle=angles,
        dynasty_id=np.array(dynasty_ids, dtype=np.int32),
        generation=np.array(generations, dtype=np.int32),
    )

    size_kb = out_path.stat().st_size / 1024
    print(f"\nwritten: {out_path} ({size_kb:.1f} KB)")
    print(f"  x range: [{x.min():.2f}, {x.max():.2f}]")
    print(f"  y range: [{y.min():.2f}, {y.max():.2f}]")
    print(f"  z range: [{z.min():.2f}, {z.max():.2f}]")
    print(f"  dyn_r distinct: {sorted(set(radii.tolist()))[:5]} ...")
    print(f"  generation distribution:")
    from collections import Counter
    print(f"    {Counter(generations)}")


if __name__ == "__main__":
    main()