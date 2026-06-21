"""
朝代归并：把 persons.temporal_value 3121 个变体字符串归并到 16 个标准朝代 key。

规则：复合字符串（如"明末清初"）取第一个朝代为主；纯细分朝代（如"明洪武間"）归主朝代。
"""
from __future__ import annotations

# 标准朝代 key（id 0 最内最老 → id 15 最外最新 / 不详）
DYNASTIES: list[dict] = [
    {"id": 0,  "key": "shang",     "label": "商",       "pinyin": "shang",     "earliest": -1600, "latest": -1046},
    {"id": 1,  "key": "zhou",      "label": "周",       "pinyin": "zhou",      "earliest": -1046, "latest": -256},
    {"id": 2,  "key": "qin",       "label": "秦",       "pinyin": "qin",       "earliest": -221,  "latest": -206},
    {"id": 3,  "key": "han",       "label": "汉",       "pinyin": "han",       "earliest": -206,  "latest": 220},
    {"id": 4,  "key": "jin",       "label": "晋",       "pinyin": "jin",       "earliest": 265,   "latest": 420},
    {"id": 5,  "key": "nanbeichao","label": "南北朝",   "pinyin": "nanbeichao","earliest": 420,   "latest": 589},
    {"id": 6,  "key": "sui",       "label": "隋",       "pinyin": "sui",       "earliest": 581,   "latest": 618},
    {"id": 7,  "key": "tang",      "label": "唐",       "pinyin": "tang",      "earliest": 618,   "latest": 907},
    {"id": 8,  "key": "wudai",     "label": "五代",     "pinyin": "wudai",     "earliest": 907,   "latest": 960},
    {"id": 9,  "key": "song",      "label": "宋",       "pinyin": "song",      "earliest": 960,   "latest": 1279},
    {"id": 10, "key": "liaojin",   "label": "辽金",     "pinyin": "liaojin",   "earliest": 916,   "latest": 1234},
    {"id": 11, "key": "yuan",      "label": "元",       "pinyin": "yuan",      "earliest": 1271,  "latest": 1368},
    {"id": 12, "key": "ming",      "label": "明",       "pinyin": "ming",      "earliest": 1368,  "latest": 1644},
    {"id": 13, "key": "qing",      "label": "清",       "pinyin": "qing",      "earliest": 1644,  "latest": 1912},
    {"id": 14, "key": "minguo",    "label": "民国",     "pinyin": "minguo",    "earliest": 1912,  "latest": 1949},
    {"id": 15, "key": "unknown",   "label": "不详",     "pinyin": "unknown",   "earliest": None,  "latest": None},
]
KEY2ID = {d["key"]: d["id"] for d in DYNASTIES}
ID2KEY = {d["id"]: d["key"] for d in DYNASTIES}


# 用于"复合字符串取第一朝代"的检测顺序 —— 按时间从早到晚，确保"明末清初"命中"明"，"宋元之際"命中"宋"
# 关键检测顺序（取复合字符串中第一个出现的朝代）
_COMPOSITE_DYNASTIES_IN_ORDER = [
    ("shang",      ["商"]),
    ("zhou",       ["周", "春秋", "战国"]),
    ("qin",        ["秦"]),
    ("han",        ["汉", "漢"]),
    ("jin",        ["晋", "晉"]),
    ("nanbeichao", ["南朝", "北朝", "南北朝"]),
    ("sui",        ["隋"]),
    ("tang",       ["唐"]),         # 优先级高于 wudai：纯"唐"归 tang；"后唐"先单独处理
    ("wudai",      ["五代", "后唐", "後唐", "后周", "后汉", "后晋", "南唐"]),
    ("song",       ["宋"]),
    ("liaojin",    ["辽", "金"]),
    ("yuan",       ["元"]),
    ("ming",       ["明"]),
    ("qing",       ["清", "淸"]),
    ("minguo",     ["民国", "民國"]),
]


def _detect_composite(s: str) -> str | None:
    """复合字符串场景：找到第一个出现的朝代关键字。"""
    earliest_idx = None
    earliest_key = None
    for key, kws in _COMPOSITE_DYNASTIES_IN_ORDER:
        for kw in kws:
            i = s.find(kw)
            if i >= 0 and (earliest_idx is None or i < earliest_idx):
                earliest_idx = i
                earliest_key = key
    return earliest_key


def normalize(raw: str | None) -> str:
    """把任意朝代字符串归并到 16 个标准 key 之一。"""
    if not raw:
        return "unknown"
    s = raw.strip().strip("（）()").strip("，,。.?？").strip()
    if not s:
        return "unknown"

    # === 先排除：role_of_family 错填进 temporal_value 的语义 ===
    if any(kw in s for kw in ["始祖", "始迁祖", "始遷祖", "支祖", "房祖", "派", "堂", "孝子"]):
        return "unknown"

    # === 不详类 ===
    if s in {"不详", "?", "？", "未知", "上古", "远古", "皆明", "皆清",
             "不詳", "不祥", "年代不详", "上古时期", "请"}:
        return "unknown"

    # === 邻国/边朝代 → 不详（不入主朝代壳，但保留可查） ===
    if s in {"高丽", "新罗", "朝鮮", "朝鲜", "吴越", "高麗", "新羅"}:
        return "unknown"

    # === 当代/近现代 → 民国的延续，归 minguo ===
    if s in {"当代", "现代", "現代", "近代", "當代", "现代", "當代"}:
        return "minguo"

    # === 远古/神话 → 不详 ===
    if s in {"夏", "殷", "尧", "虞", "唐尧", "虞舜"}:
        return "unknown"

    # === 三国 → 新加 sanguo（暂归入 han 后，但放独立 key） ===
    if "三国" in s or "三國" in s:
        return "han"  # 三国在东汉末，归 han 简化

    # === 南朝细分：南齐 / 齐 / 梁 / 后梁 / 陈 / 南梁 / 南北 → 归 nanbeichao ===
    # 顺序：先"宋"再"南齐"等已包在南北朝里
    # 但齐单字 + 殷商齐不同，先处理"南北""南齐""齐"等
    if "南北" in s and len(s) <= 4:
        return "nanbeichao"
    if s in {"南齐", "南齊", "齐", "齊", "梁", "南梁", "后梁", "後梁", "陈", "陳",
             "北魏", "西魏", "东魏", "南陈", "北齐", "北周"}:
        return "nanbeichao"

    # 复合检测
    key = _detect_composite(s)
    if key is not None:
        return key

    return "unknown"


if __name__ == "__main__":
    tests = [
        ("明", "ming"), ("清", "qing"), ("明初", "ming"), ("南宋", "song"),
        ("北宋", "song"), ("后唐", "wudai"), ("後唐", "wudai"), ("南唐", "wudai"),
        ("五代", "wudai"), ("漢", "han"), ("晉", "jin"), ("東漢", "han"),
        ("西晋", "jin"), ("南宋末", "song"), ("明末清初", "ming"),
        ("明洪武間", "ming"), ("清康熙間", "qing"), ("民国", "minguo"),
        ("民國", "minguo"), ("不详", "unknown"), ("?", "unknown"),
        ("上古", "unknown"), ("", "unknown"), (None, "unknown"),
        ("约於明末（1460年前後）", "ming"),
        (",清同治间", "qing"),
        ("元末明初", "yuan"),
        ("宋元之際", "song"),
        ("清末民初", "qing"),
        ("宋末元初", "song"),
        ("明洪武二年", "ming"),
        ("淸", "qing"),
    ]
    ok = 0
    for raw, expected in tests:
        got = normalize(raw)
        if got == expected:
            ok += 1
        else:
            print(f"  [FAIL] {raw!r:<30} → {got!r} (expected {expected!r})")
    print(f"{ok}/{len(tests)} passed")