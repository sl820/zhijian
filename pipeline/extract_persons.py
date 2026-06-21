"""
Phase B-2: extract_persons.py
从 shlib_jiapu.db 抽 persons，写 data/processed/persons.jsonl。

输出字段（每行 JSON）：
  pid          str  - 内部 id（URI 末尾 16 字符）
  uri          str  - 原始 URI（jp 或非 jp）
  source       str  - "jiapu" | "cbdb"
  name         str  - 简体姓名（label_chs）
  name_alt     str  - 繁体姓名（label_cht）
  courtesy     str  - 字
  pseudonym    str  - 号
  gender       str  - 男/女/?
  family_name  str  - 姓氏拼音（family_name）
  family_uri   str  - 家谱族 URI（仅 jiapu）
  family_role  str  - 始祖/显祖/世祖 等
  dynasty      str  - 标准朝代 key（明/清/宋/...）
  temporal_raw str  - 原始朝代字符串（仅 jiapu）
  generation   int  - 世代号（v1 推导，本期固定 0 → 后续脚本算）
  order        str  - 排行
  description  str  - 描述
  label_type   str  - full_name/anonymous/surname_only/etc_marker/empty

筛选条件：
  - temporal_value 非空 且归并到标准 key ≠ "unknown"（v2 数据上界 17 万）
  - label_chs 非空

用法：
  python pipeline/extract_persons.py
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from dynasty_normalize import normalize

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(r"D:/上海图书馆开放数据/data/shlib_jiapu.db")
OUT_PATH = ROOT / "data" / "processed" / "persons.jsonl"


def pid_from_uri(uri: str) -> str:
    """URI 末尾 16 字符（兼容 jp/entity 和 entity 两套 URI）。"""
    return uri.rsplit("/", 1)[-1][:16]


def map_role(role_uri: str | None) -> str:
    """role_of_family URI → 短标签。"""
    if not role_uri:
        return ""
    return role_uri.rsplit("/", 1)[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--out", default=str(OUT_PATH))
    ap.add_argument("--with-dynasty-only", action="store_true", default=False,
                    help="只输出有朝代的人（默认 False：保留全部有 label_chs 的人，"
                         "覆盖 relations endpoints + 后续 precompute 全量）")
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    # 默认保留全部有 label_chs 的人 — 覆盖 relations 端点全集
    # （relations ETL 用全 persons 表 pid 集合，端点必须能在 persons.jsonl 里查到）
    sql = """
        SELECT uri, label_chs, label_cht, courtesy_name, pseudonym,
               gender, family_name, family_uri, role_of_family,
               temporal_value, generation_character, order_of_seniority,
               description, label_type
        FROM persons
        WHERE label_chs IS NOT NULL AND label_chs != ''
    """
    if args.with_dynasty_only:
        sql += " AND temporal_value IS NOT NULL AND temporal_value != ''"

    kept = 0
    dropped_unknown = 0
    written = 0
    with out_path.open("w", encoding="utf-8") as f:
        cur.execute(sql)
        for row in cur:
            (uri, name_chs, name_cht, courtesy, pseudonym, gender, family_name,
             family_uri, role, temporal_raw, gen_char, order, desc, label_type) = row
            dyn = normalize(temporal_raw)
            rec = {
                "pid":          pid_from_uri(uri),
                "uri":          uri,
                "source":       "jiapu" if "/jp/" in uri else "cbdb",
                "name":         name_chs,
                "name_alt":     name_cht or "",
                "courtesy":     courtesy or "",
                "pseudonym":    pseudonym or "",
                "gender":       gender or "",
                "family_name":  family_name or "",
                "family_uri":   family_uri or "",
                "family_role":  map_role(role),
                "dynasty":      dyn,
                "temporal_raw": temporal_raw or "",
                "generation":   0,  # 后续 build_dynasties / precompute_layout 计算
                "order":        order or "",
                "description":  desc or "",
                "label_type":   label_type or "",
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1
            kept += 1
            if kept % 100000 == 0:
                print(f"  ...{kept} rows")

    print(f"done. kept={kept}, written={written}")
    print(f"out: {out_path}")
    conn.close()


if __name__ == "__main__":
    main()