"""
人物归类器 (Person Classifier)

设计原则：
- 纯规则，无外部依赖，无 LLM
- 输入 dict 字段是 jiapu / pipeline / 旧 in-memory 通用形态
- 4 类：0=氏族 / 1=妻妾 / 2=其他 / 3=官吏文人

字段约定（按优先级尝试）：
- 姓：family_name
- 名：label_chs / name
- 角色：role_of_family / role
- 朝代：dynasty
- 官职：title

Why：KG 默认 category=2 (其他) 导致 73 节点全棕色。归类逻辑从未落地。
How to apply：所有 add_person 路径必须经本函数；add_person 内部强制覆盖。
"""
from typing import Dict

# ============================================================
# 常量
# ============================================================

# 氏族：百家姓前 100 姓 + 苏（项目主轴）
# 可通过 env / config 覆盖
CLAN_SURNAMES = frozenset({
    "赵", "钱", "孙", "李", "周", "吴", "郑", "王", "冯", "陈",
    "褚", "卫", "蒋", "沈", "韩", "杨", "朱", "秦", "尤", "许",
    "何", "吕", "施", "张", "孔", "曹", "严", "华", "金", "魏",
    "陶", "姜", "戚", "谢", "邹", "喻", "柏", "水", "窦", "章",
    "云", "苏", "潘", "葛", "奚", "范", "彭", "郎", "鲁", "韦",
    "昌", "马", "苗", "凤", "花", "方", "俞", "任", "袁", "柳",
    "酆", "鲍", "史", "唐", "费", "廉", "岑", "薛", "雷", "贺",
    "倪", "汤", "滕", "殷", "罗", "毕", "郝", "邬", "安", "常",
    "乐", "于", "时", "傅", "皮", "卞", "齐", "康", "伍", "余",
    "元", "卜", "顾", "孟", "平", "黄", "和", "穆", "萧", "尹",
    "姚", "邵", "湛", "汪", "祁", "毛", "禹", "狄", "米", "贝",
})

# 妻妾标识词：role、称谓、姓名中含这些字视为妻妾
WIFE_KEYWORDS = ("妻", "妾", "孺人", "夫人", "氏")

# Category 枚举
CATEGORY_CLAN = 0      # 氏族成员
CATEGORY_WIFE = 1      # 妻妾
CATEGORY_OTHER = 2     # 其他人物（默认）
CATEGORY_OFFICIAL = 3  # 官吏 / 文人（有朝代+官职）


# ============================================================
# 分类函数
# ============================================================

def _get_field(person: Dict, *keys: str) -> str:
    """从 dict 取第一个非空字段。"""
    for k in keys:
        v = person.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _extract_surname(person: Dict) -> str:
    """提取姓氏。

    优先取 family_name（汉字形态）；若 family_name 是拼音或非汉字，
    回退到 label_chs / name 的首字（CJK 单字）。
    """
    family = _get_field(person, "family_name", "surname")
    if family and any('一' <= c <= '鿿' for c in family):
        # 取第一个 CJK 字符
        for c in family:
            if '一' <= c <= '鿿':
                return c
    # 回退：从名字首字
    name = _get_field(person, "label_chs", "name", "label")
    if name:
        for c in name:
            if '一' <= c <= '鿿':
                return c
    return ""


def _is_wife_name(name: str) -> bool:
    """判断姓名是否含妻妾标识。

    「氏」规则收紧：必须是「{单字姓}氏」2 字形态，避免「无名氏」「李氏宗祠」误判。
    其它关键词（妻/妾/孺人/夫人）只要子串匹配即可。
    """
    if not name:
        return False
    for kw in WIFE_KEYWORDS:
        if kw == "氏":
            # 仅匹配 2 字「X氏」形态
            if len(name) == 2 and name[1] == "氏":
                return True
        else:
            if kw in name:
                return True
    return False


def classify_person(person: Dict) -> int:
    """对一个人物 dict 进行分类。

    规则（按顺序匹配）：
    1. 姓在 CLAN_SURNAMES 且 role/姓名含妻妾标识 → CATEGORY_WIFE (1)
    2. 姓在 CLAN_SURNAMES → CATEGORY_CLAN (0)
    3. role/姓名含妻妾标识 → CATEGORY_WIFE (1)
    4. 有 dynasty + title（且无氏族背景）→ CATEGORY_OFFICIAL (3)
    5. 默认 → CATEGORY_OTHER (2)

    Args:
        person: 人物 dict，至少含以下可选字段：
            - family_name / role_of_family / label_chs / name
            - dynasty / title

    Returns:
        int: 0 / 1 / 2 / 3
    """
    family_name = _extract_surname(person)
    name = _get_field(person, "label_chs", "name", "label")
    role = _get_field(person, "role_of_family", "role")
    dynasty = _get_field(person, "dynasty")
    title = _get_field(person, "title", "official_title")

    is_wife_marked = any(kw in role for kw in WIFE_KEYWORDS) or _is_wife_name(name)

    # Rule 1: 氏族 + 妻妾
    if family_name and family_name in CLAN_SURNAMES and is_wife_marked:
        return CATEGORY_WIFE

    # Rule 2: 氏族
    if family_name and family_name in CLAN_SURNAMES:
        return CATEGORY_CLAN

    # Rule 3: 妻妾 markers（无氏族背景）
    if is_wife_marked:
        return CATEGORY_WIFE

    # Rule 4: 官吏/文人
    if dynasty and title:
        return CATEGORY_OFFICIAL

    # Default
    return CATEGORY_OTHER


# ============================================================
# 辅助：批量分类（用于一次性重跑）
# ============================================================

def classify_batch(persons):
    """对列表中每个人物跑 classify_person，返回 (uri, category) 列表。"""
    return [
        (
            p.get("uri") or p.get("name") or "",
            classify_person(p),
        )
        for p in persons
    ]
