"""
KG 关系抽取器（M4 拆出）

Why：kg_service.py 的 post_process_relations 含 250+ 行关系抽取逻辑，
与 service 核心职责（CRUD）混淆。拆出独立模块让测试可单独覆盖。

How to apply：
- SuffixPatternExtractor 类：从古文「X之父Y」「X字Y」等 pattern 抽取关系
- chunked_extract()：分段扫描避免 5k 截断丢失长文关系
- kg_service.py 的 post_process_relations 调用本模块
"""
import logging
import re
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ============================================================
# Suffix patterns：古文称谓 → 关系类型
# ============================================================
# 20+ pattern 覆盖：直系血亲 / 旁系 / 婚姻 / 师徒 / 同僚 / 字号
#
# 中文古籍常见的「X之父 Y」「X之弟 Y」「X 字 Y」格式。
# 之X pattern 双向匹配（X之父 Y 或 Y 是 X 的父）

SUFFIX_PATTERNS: List[Tuple[str, str]] = [
    # 直系血亲（用「之」标记）
    ("之父", "FATHER"),
    ("之母", "MOTHER"),
    ("之子", "SON"),
    ("之女", "DAUGHTER"),
    ("之孙", "GRANDSON"),
    ("之曾孙", "GREAT_GRANDSON"),
    ("之外祖", "MATERNAL_GRANDFATHER"),
    ("之外祖母", "MATERNAL_GRANDMOTHER"),
    # 旁系
    ("之兄", "ELDER_BROTHER"),
    ("之弟", "YOUNGER_BROTHER"),
    ("之姐", "ELDER_SISTER"),
    ("之妹", "YOUNGER_SISTER"),
    ("之伯父", "ELDER_UNCLE"),
    ("之叔父", "YOUNGER_UNCLE"),
    ("之姑母", "AUNT"),
    # 婚姻
    ("之妻", "WIFE"),
    ("之妾", "CONCUBINE"),
    ("之夫", "HUSBAND"),
    ("之婿", "SON_IN_LAW"),
    ("之媳", "DAUGHTER_IN_LAW"),
    # 师徒 / 同僚
    ("之师", "TEACHER"),
    ("之徒", "STUDENT"),
    ("之友", "FRIEND"),
    ("之同僚", "COLLEAGUE"),
]

# 「字 X」/「号 X」/「讳 X」格式（用于同一人别名识别，存为别名不存为关系）
NAME_PATTERNS: List[Tuple[str, str]] = [
    ("字", "ALIAS"),
    ("号", "ALIAS"),
    ("讳", "ALIAS"),
    ("别号", "ALIAS"),
]

# 停字符：提取 target 时碰到这些就停
# 包含中文标点 + 古文常用连接字（为/乃/即/是/之/于/于/与/其）+ ASCII
_STOP_CHARS = set("以，。；、：（）" + "" "''【】《》" + "0123456789 " +
                  "为乃即是之于乎也与及其所自而")


# ============================================================
# Extractor class
# ============================================================

class SuffixPatternExtractor:
    """基于 suffix pattern 的关系抽取器。

    用法：
        ext = SuffixPatternExtractor(stored_names={"苏辙", "苏轼"})
        relations = ext.extract(text, "苏辙")
        # -> [{"from": "苏辙", "to": "苏轼", "type": "ELDER_BROTHER", "confidence": 0.85}, ...]
    """

    def __init__(
        self,
        stored_names: Set[str],
        dynasty_markers: Set[str] = None,
        era_names: Set[str] = None,
    ):
        self.stored_names = stored_names
        self.dynasty_markers = dynasty_markers or set()
        self.era_names = era_names or set()

    def extract(
        self,
        text: str,
        subject_name: str,
        chunk_size: int = 5000,
        chunk_overlap: int = 200,
    ) -> List[Dict]:
        """从 text 中抽取 subject_name 涉及的关系。

        Args:
            text: 全文
            subject_name: 主语（要查的人名）
            chunk_size: 每段扫描字数（默认 5000，避免内存爆炸）
            chunk_overlap: 段间重叠（防止 pattern 跨段被切断）

        Returns:
            [{"from": subject, "to": target, "type": rel_type, "confidence": 0.85}, ...]
        """
        if not text or not subject_name:
            return []

        results: List[Dict] = []
        seen_pairs: Set[Tuple[str, str, str]] = set()

        # 分段扫描（取消 5k 截断的关键改动）
        chunks = self._chunk_text(text, chunk_size, chunk_overlap)
        for chunk_start, chunk in chunks:
            for suffix, rel_type in SUFFIX_PATTERNS:
                pattern = subject_name + suffix
                pos = 0
                while True:
                    pos = chunk.find(pattern, pos)
                    if pos < 0:
                        break

                    target = self._extract_target(
                        chunk, pos, len(pattern), len(suffix)
                    )
                    if target and self._is_valid_target(target):
                        pair = (subject_name, target, rel_type)
                        if pair not in seen_pairs:
                            results.append({
                                "from": subject_name,
                                "to": target,
                                "type": rel_type,
                                "confidence": 0.85,
                            })
                            seen_pairs.add(pair)
                    pos += 1

        return results

    def _chunk_text(self, text: str, size: int, overlap: int) -> List[Tuple[int, str]]:
        """分段文本，返回 (offset, chunk) 列表。"""
        if len(text) <= size:
            return [(0, text)]
        chunks = []
        step = size - overlap
        for i in range(0, len(text), step):
            chunks.append((i, text[i : i + size]))
            if i + size >= len(text):
                break
        return chunks

    def _extract_target(self, text: str, pos: int, pattern_len: int, suffix_len: int) -> Optional[str]:
        """从匹配位置抽取 target 人名。

        优先级：
        1. 从 pattern 之前找已知 stored_names（处理"张缅，张弘策之子"）
        2. 从 pattern 之后找第一个 CJK 序列
        """
        # subject_name 在 text 中的起点 = pattern 起点 = pos
        # search_back：subject_name 之前的 10 字窗口
        search_back_start = max(0, pos - 10)
        search_back = text[search_back_start:pos]
        # subject_name 本身的文本，用于自我排除
        subject_end = pos + (pattern_len - suffix_len)

        # 1. 优先：往前找已知人名
        for p_name in self.stored_names:
            if not p_name or len(p_name) < 2:
                continue
            # 排除 subject_name 自身（避免「苏辙之父苏辙」误识）
            if text[pos:pos + len(p_name)] == p_name:
                continue
            idx = search_back.rfind(p_name)
            if idx >= 0:
                # found_start 必须 ≤ pos（即整个 p_name 在 subject_name 之前结束）
                found_start = search_back_start + idx
                if found_start + len(p_name) <= pos:
                    return p_name

        # 2. 回退：从 pattern 之后取 CJK 序列
        rest = text[pos + pattern_len : pos + pattern_len + 8]
        # 跳过非 CJK
        skip = 0
        while skip < len(rest) and not ('一' <= rest[skip] <= '鿿'):
            skip += 1
        rest_cjk = rest[skip:]
        if not rest_cjk:
            return None

        # 优先匹配「YYYY年」格式（如"生于宋仁宗嘉祐二年"）
        year_m = re.match(r'([一-鿿]{1,3})年', rest_cjk)
        if year_m and len(year_m.group(1)) >= 2:
            return year_m.group(1)

        # 否则取 CJK 序列直到停字符
        end_idx = 0
        while end_idx < len(rest_cjk) and rest_cjk[end_idx] not in _STOP_CHARS:
            end_idx += 1
        cjk_seq = rest_cjk[:end_idx] if end_idx > 0 else rest_cjk[:4]
        m = re.match(r'([一-鿿]{2,4})', cjk_seq)
        if not m:
            return None
        target = m.group(1)
        # 清理"后裔"、"后"等前缀
        for s in ["后裔", "后"]:
            if target.startswith(s):
                target = target[len(s):]
                break
        return target if target else None

    def _is_valid_target(self, target: str) -> bool:
        if not target or len(target) < 2:
            return False
        if target in self.dynasty_markers or target in self.era_names:
            return False
        if target[0].isdigit() or target.startswith("之"):
            return False
        # 排除是别人子串的（避免 "X" 跟 "XX" 误匹配）
        if any(target in p and target != p for p in self.stored_names):
            return False
        return True