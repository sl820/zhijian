"""
Phase C-辅助: npz_to_layout_json.py
把 jiapu_v2.npz 转成 jiapu_v2.json 给前端用（浏览器不解析 NPZ）。

输出 schema:
{
  "nodeIds": string[],          // pid 列表
  "positions": Position[]        // 与 nodeIds 一一对应
}

Position:
  x, y, z: number
  radius, angle: number
  dynastyId, generation: number

用法:
  python pipeline/npz_to_layout_json.py
  # 一次性，产物入 git（~10MB 量级，GH Pages 1GB 限额内）
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
NPZ = ROOT / "public" / "layouts" / "jiapu_v2.npz"
JSON_OUT = ROOT / "public" / "layouts" / "jiapu_v2.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=str(NPZ))
    ap.add_argument("--out", default=str(JSON_OUT))
    args = ap.parse_args()

    print(f"loading {args.inp} ...")
    z = np.load(args.inp, allow_pickle=True)
    node_ids = z["node_ids"].tolist()
    x = z["x"].tolist()
    y = z["y"].tolist()
    pos_z = z["z"].tolist()
    radius = z["radius"].tolist()
    angle = z["angle"].tolist()
    dyn_id = z["dynasty_id"].tolist()
    gen = z["generation"].tolist()

    positions = [
        {
            "x": x[i], "y": y[i], "z": pos_z[i],
            "radius": radius[i], "angle": angle[i],
            "dynastyId": int(dyn_id[i]), "generation": int(gen[i]),
        }
        for i in range(len(node_ids))
    ]

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump({"nodeIds": node_ids, "positions": positions}, f, ensure_ascii=False)

    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"written: {out_path} ({size_mb:.2f} MB, {len(node_ids)} nodes)")


if __name__ == "__main__":
    main()
