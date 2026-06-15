"""
知识图谱构建 Pipeline
从文本 → 规则实体识别 → 关系抽取 → 存到 KnowledgeGraphService（in-memory）

注：原版本使用 NERModel（BERT）和 EntityResolver（TF-IDF），
    重构后两者均删除，改用纯规则+LLM 辅助。
"""
import logging
import re
from typing import List, Dict, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


# 关系模式定义（正则 + 关系类型）
# 使用 [\u4e00-\u9fff] 匹配纯中文，避免英文名干扰
RELATION_PATTERNS = [
    # 家族关系
    (r"([\u4e00-\u9fff]{2,4})之父", "FATHER", 0.8),
    (r"([\u4e00-\u9fff]{2,4})之母", "MOTHER", 0.8),
    (r"([\u4e00-\u9fff]{2,4})之子", "SON", 0.8),
    (r"([\u4e00-\u9fff]{2,4})之女", "DAUGHTER", 0.8),
    (r"([\u4e00-\u9fff]{2,4})之妻", "WIFE", 0.8),
    (r"([\u4e00-\u9fff]{2,4})之夫", "HUSBAND", 0.8),
    (r"([\u4e00-\u9fff]{2,4})之兄", "ELDER_BROTHER", 0.7),
    (r"([\u4e00-\u9fff]{2,4})之弟", "YOUNGER_BROTHER", 0.7),
    (r"([\u4e00-\u9fff]{2,4})之姐", "ELDER_SISTER", 0.7),
    (r"([\u4e00-\u9fff]{2,4})之妹", "YOUNGER_SISTER", 0.7),
    (r"([\u4e00-\u9fff]{2,4})祖父", "PATERNAL_GRANDFATHER", 0.8),
    (r"([\u4e00-\u9fff]{2,4})祖母", "PATERNAL_GRANDMOTHER", 0.8),
    (r"([\u4e00-\u9fff]{2,4})曾祖", "GREAT_GRANDFATHER", 0.7),
    (r"为([\u4e00-\u9fff]{2,4})所?生", "CHILD_OF", 0.8),
    # 官职/政治关系
    (r"([\u4e00-\u9fff]{2,4})知(州|府|县)", "OFFICIAL", 0.7),
    (r"任([\u4e00-\u9fff]{2,4})", "SERVED_AS", 0.6),
    (r"授([\u4e00-\u9fff]{2,4})", "APPOINTED", 0.6),
    # 师徒关系
    (r"从([\u4e00-\u9fff]{2,4})学", "STUDENT_OF", 0.7),
    (r"师从([\u4e00-\u9fff]{2,4})", "STUDENT_OF", 0.8),
    (r"([\u4e00-\u9fff]{2,4})之徒", "DISCIPLE", 0.7),
    # 地理关系
    (r"([\u4e00-\u9fff]{2,4})人", "NATIVE_OF", 0.6),  # "固安人"
    (r"籍贯([\u4e00-\u9fff]{2,4})", "NATIVE_OF", 0.8),
    (r"字([\u4e00-\u9fff]{2,4})", "COURTESY_NAME", 0.5),  # 字是人的别称
]

# 人物类型映射
PERSON_TYPE_MAP = {
    "官员": 0,
    "文人": 1,
    "苏氏家族": 0,
    "妻妾": 1,
    "其他人物": 2,
}


class KGPipeline:
    """知识图谱构建 Pipeline"""

    def __init__(self, config: dict = None):
        """
        初始化 KG Pipeline

        Args:
            config: 配置字典，包含：
                - ner_threshold: NER 置信度阈值 (默认 0.5)
                - relation_threshold: 关系置信度阈值 (默认 0.6)
                - person_type: 默认人物类型 (默认 2)
        """
        self.config = config or {}
        self.ner_threshold = self.config.get("ner_threshold", 0.5)
        self.relation_threshold = self.config.get("relation_threshold", 0.6)
        self.default_person_type = self.config.get("person_type", 2)

        logger.info(
            f"KGPipeline 初始化完成 - "
            f"ner_threshold={self.ner_threshold}, "
            f"relation_threshold={self.relation_threshold}"
        )

    def extract_entities(self, text: str) -> List[Dict]:
        """
        从文本中提取实体

        Args:
            text: 输入文本

        Returns:
            实体列表，每个包含 type, name, start, end, biography 等
        """
        if not text or len(text.strip()) < 10:
            return []

        # NER 模型未 fine-tuned，直接使用规则抽取
        ner_entities = self._rule_based_extract(text)

        entities = []

        for ent in ner_entities:
            entity_type = ent.get("type", "")
            name = ent.get("name", "")

            if not name or len(name) < 2:
                continue

            # 过滤过短的实体
            if entity_type == "PER" and len(name) < 2:
                continue

            # 构建实体字典
            entity = {
                "name": name,
                "type": entity_type,
                "start": ent.get("start", 0),
                "end": ent.get("end", 0),
                "biography": self._extract_biography(text, ent),
                "context": text[max(0, ent["start"] - 50):ent["end"] + 50],
            }

            # 提取时间信息
            time_info = self._extract_time(text, ent)
            if time_info:
                entity["time"] = time_info

            # 提取地名
            location = self._extract_location(text, ent)
            if location:
                entity["location"] = location

            entities.append(entity)

        # 按名称去重
        seen = set()
        unique_entities = []
        for e in entities:
            key = (e["name"], e["type"])
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)

        logger.info(f"从文本中提取到 {len(unique_entities)} 个实体")
        return unique_entities

    def _try_ner(self, text: str) -> List[Dict]:
        """尝试使用 NER 模型抽取实体"""
        try:
            ner_entities = self.ner_model.predict(text)
            # 只在有足够置信度时才使用 NER 结果
            # base BERT 模型没有 fine-tuned，只有在返回 PER/LOC 实体时才考虑
            if ner_entities and len(ner_entities) > 0:
                valid_entities = [
                    e for e in ner_entities
                    if e.get("type") in ("PER", "LOC") and len(e.get("name", "")) >= 2
                ]
                if valid_entities:
                    logger.info(f"NER 模型提取到 {len(valid_entities)} 个有效实体")
                    return valid_entities
                else:
                    logger.info(f"NER 模型结果无效，使用规则抽取")
        except Exception as e:
            logger.warning(f"NER 模型抽取失败: {e}")
        return []

    def _rule_based_extract(self, text: str) -> List[Dict]:
        """
        基于规则的实体抽取 - 逐行解析方志传记

        策略：按行/段落分割，每段分析人物传记的固定格式
        """
        entities = []
        seen = set()

        def add(e_type: str, name: str, start: int, end: int):
            if not name or len(name) < 2 or len(name) > 5:
                return
            if not re.match(r'^[\u4e00-\u9fff·]+$', name):
                return
            key = (name, e_type)
            if key not in seen:
                seen.add(key)
                entities.append({"type": e_type, "name": name, "start": start, "end": end})

        # 过滤噪音 - 扩展版
        def is_noise(name: str) -> bool:
            # 官职/爵位名称（不是人名）
            noise_words = {
                "太守", "将军", "博士", "侍郎", "尚书", "司马", "刺史",
                "长史", "著作", "太傅", "公侯", "帝即", "王之", "太守",
                "知州", "知府", "县令", "主簿", "判官", "推官",
                "安抚", "转运", "节度", "观察", "防御", "团练",
                "翰林", "御史", "中书", "门下", "太尉", "司徒", "司空",
                "大将军", "骠骑", "车骑", "郡守", "亭侯", "乡侯", "县侯", "列侯",
                "光禄", "卫尉", "太仆", "大理", "鸿胪", "宗正",
                "太子", "王世子", "长子", "次子",
            }
            if name in noise_words:
                return True
            # 年号/年号表达式过滤（以"年"结尾的）
            if name.endswith("年") and len(name) >= 2:
                return True
            # 帝X年、皇X年等皇帝年号表达式
            if len(name) == 3 and name[0] in {"帝", "皇", "王"} and name[1] in {"元", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"} and name[2] == "年":
                return True
            # 初X年、末X年、季X年
            if len(name) == 3 and name[0] in {"初", "末", "季"} and name[1] in {"元", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"} and name[2] == "年":
                return True
            # 地名常见后缀 - 以这些结尾的不是人名
            geo_suffixes = ["县", "州", "府", "城", "乡", "镇", "村", "里", "亭", "山", "水", "江", "河", "湖", "海", "港", "澳", "岛", "洲"]
            # 官职/尊称后缀
            title_suffixes = ["守", "尉", "监", "使", "相", "伯", "侯", "公", "王", "君", "臣", "郎", "史", "民", "仆"]
            if len(name) >= 2 and name[-1] in geo_suffixes:
                return True
            # 官职/尊称后缀（2字以上才过滤，如"太守"）
            if len(name) >= 2 and name[-1] in title_suffixes:
                return True
            # 过滤"X即位"等非人名模式（即位、立等是动作非人名）
            if name.endswith(("位", "立", "崩", "薨", "卒")):
                return True
            # 朝代简称（单字）
            dynasty_chars = {"汉", "唐", "宋", "元", "明", "清", "魏", "蜀", "吴", "晋", "隋", "秦", "周", "商", "夏", "虞", "金", "辽", "齐", "楚", "燕", "赵", "韩", "魏", "梁"}
            if name in dynasty_chars:
                return True
            # 年号/月/日相关（后跟年、月、日）
            year_patterns = {
                "元年", "二年", "三年", "四年", "五年", "六年", "七年", "八年", "九年", "十年",
                "正月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "十一月", "十二月",
                "一日", "二日", "三日", "四日", "五日", "六日", "七日", "八日", "九日", "十日",
                "十一日", "十二日", "十三日", "十四日", "十五日", "十六日", "十七日", "十八日", "十九日", "二十日",
            }
            if name in year_patterns:
                return True
            # 地名常用词
            geo_words = {"京兆", "河南", "河北", "山西", "山东", "江南", "江左", "江右", "岭南", "塞北", "辽东", "关中", "塞外", "西域"}
            if name in geo_words:
                return True
            # 书籍/文章名常用结尾字
            book_suffixes = ["记", "志", "传", "录", "史", "典", "论", "集", "编", "考", "略", "图", "谱", "表", "诏", "令", "策", "书"]
            if len(name) >= 2 and name[-1] in book_suffixes:
                return True
            # 机构名常用结尾
            org_suffixes = ["学", "寺", "观", "庙", "宫", "殿", "阁", "院", "府", "部", "省", "司"]
            if len(name) >= 2 and name[-1] in org_suffixes:
                return True
            return False

        # 按行分割处理
        lines = text.split('\n')
        for line_offset, line in enumerate(lines):
            if not line.strip():
                continue

            # 计算行起始位置（简化处理，用偏移估计）
            line_start = sum(len(l) + 1 for l in lines[:line_offset])

            # ========== 人物识别 ==========
            # 格式A: "韩婴，西汉..." - 行首姓名+逗号
            # 需要验证后续内容像人物传记（包含朝代、年号、字、号、官职等）
            m = re.match(r'([\u4e00-\u9fff]{2,3})，', line)
            if m and not is_noise(m.group(1)):
                # 排除年份开头的行（如"232—300，"）
                if not re.match(r'^[\d—\-～]+', line):
                    name = m.group(1)
                    rest = line[len(name)+1:]  # 逗号后面的内容
                    # 验证后续内容像人物传记（需要包含明确的传记指示词）
                    person_indicators = [
                        "西汉", "东汉", "唐朝", "宋代", "元朝", "明朝", "清朝", "南北朝",
                        "字", "号", "仕", "举", "进士", "举人", "生", "卒", "殁", "配", "继",
                        "知", "任", "拜", "授", "封", "赠", "擢", "迁", "史", "公",
                    ]
                    # 朝代后面通常跟着人名或其他内容
                    dynasty_chars = {"隋", "唐", "宋", "元", "明", "清", "汉", "魏", "蜀", "吴", "晋", "秦", "周", "商", "夏"}
                    # 如果以单字朝代开头，后面不能是单独的朝代名（需要有后续内容）
                    if rest and rest[0] in dynasty_chars and len(rest) < 3:
                        pass  # 不添加，可能是"唐，"单独出现
                    # 如果后面跟着常见的传记词汇，才认为是人名
                    elif any(rest.startswith(ind) for ind in person_indicators):
                        add("PER", name, line_start, line_start + len(name))

            # 格式B: "...(生卒年)，字XX，..." - 括号里的姓名
            # 只匹配真正的人名（2字姓名），排除年号表达式如"帝三年"、"初二年"等
            for m in re.finditer(r'([\u4e00-\u9fff]{2,3})\([\d\u2010\u2013\u2014\uff0e\u00b7～\-]+\)', line):
                name = m.group(1)
                # 排除以"年"结尾的年号表达式（如"帝三年"、"初二年"）
                if name.endswith("年"):
                    continue
                # 排除"帝X年"等皇帝年号表达式 (帝+数字+年)
                if len(name) == 3 and name[0] in {"帝", "皇"} and name[1] in {"元", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"} and name[2] == "年":
                    continue
                # 排除"初X年"、"末X年"等年号表达式
                if len(name) == 3 and name[0] in {"初", "末", "季"} and name[1] in {"元", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十"} and name[2] == "年":
                    continue
                # 排除以动作词结尾的非人名（如"丕即位"中的"即位"）
                if name.endswith(("即位", "立", "崩", "薨", "卒")):
                    continue
                add("PER", name, line_start + m.start(1), line_start + m.end(1))

            # 格式C: "XXX，字XX" - 姓名紧跟"字"
            m = re.match(r'([\u4e00-\u9fff]{3})，字', line)
            if m and not is_noise(m.group(1)):
                add("PER", m.group(1), line_start, line_start + 3)

            # 格式D: "XXX之父/之子..." - 关系句中的姓名
            for m in re.finditer(r'([\u4e00-\u9fff]{2,3})之(父|母|子|女|兄|弟|姐|妹)', line):
                name = m.group(1)
                if not is_noise(name):
                    add("PER", name, line_start + m.start(1), line_start + m.end(1))

            # ========== 地名识别 ==========
            # 格式: "(今XXX)"
            for m in re.finditer(r'\(今([\u4e00-\u9fff]{2,5})\)', line):
                add("LOC", m.group(1), line_start + m.start(1), line_start + m.end(1))

            # 格式: "XXX州" "XXX府" "XXX县"
            for m in re.finditer(r'([\u4e00-\u9fff]{2,4})(州|府|县)', line):
                place = m.group(1) + m.group(2)
                if not is_noise(place):
                    add("LOC", place, line_start + m.start(1), line_start + m.end(2))

        # 去重并清理
        entities = [e for e in entities if not is_noise(e["name"])]

        logger.info(f"规则抽取提取到 {len(entities)} 个实体")
        return entities

    def extract_relations(
        self,
        text: str,
        entities: List[Dict]
    ) -> List[Dict]:
        """
        从文本中抽取实体间关系

        Args:
            text: 输入文本
            entities: 已识别的实体列表

        Returns:
            关系列表，每个包含 source, target, relation, confidence
        """
        relations = []
        entity_names = {e["name"] for e in entities}

        for pattern, rel_type, base_conf in RELATION_PATTERNS:
            matches = re.finditer(pattern, text)
            for match in matches:
                person_name = match.group(1) if match.groups() else None

                if person_name and person_name in entity_names:
                    # 找到关系两端实体
                    relations.append({
                        "source": person_name,
                        "target": person_name,  # 自关联，后续需要解析
                        "relation": rel_type,
                        "confidence": base_conf,
                        "match_text": match.group(0),
                        "position": match.start(),
                    })

        # 去重
        seen = set()
        unique_relations = []
        for rel in relations:
            key = (rel["source"], rel["relation"], rel["match_text"])
            if key not in seen:
                seen.add(key)
                unique_relations.append(rel)

        logger.info(f"从文本中抽取到 {len(unique_relations)} 条关系")
        return unique_relations

    def extract_person_relations(
        self,
        text: str,
        person_entities: List[Dict]
    ) -> List[Dict]:
        """
        从文本中抽取人物之间的关系（更精确的抽取）

        针对方志文献中常见的表述模式：
        - "张三，李四之父"
        - "王五知苏州"
        - "赵六，固安人"
        """
        relations = []
        person_names = [p["name"] for p in person_entities]

        # 只保留已知人物名进行关系匹配
        known_persons = set(person_names)

        # 关系模式：查找已知人物名 + 关系词
        REL_TYPES = [
            ("之父", "FATHER"),
            ("之母", "MOTHER"),
            ("之子", "SON"),
            ("之女", "DAUGHTER"),
            ("之兄", "ELDER_BROTHER"),
            ("之弟", "YOUNGER_BROTHER"),
            ("之妻", "WIFE"),
        ]

        for person in known_persons:
            if len(person) < 2:
                continue
            for suffix, rel_type in REL_TYPES:
                pattern = person + suffix
                idx = 0
                while True:
                    idx = text.find(pattern, idx)
                    if idx < 0:
                        break
                    # 提取"之子X"中的X作为target
                    rest = text[idx + len(pattern):idx + len(pattern) + 5]
                    m = re.match(r'([\u4e00-\u9fff]{2,4})', rest)
                    target = m.group(1) if m else None
                    if target and len(target) >= 2:
                        # 目标不能是已知人名的子串（避免"刘正于咸熙"中提取出"刘正"）
                        is_substring = any(
                            target in p and target != p
                            for p in known_persons
                        )
                        if not is_substring:
                            relations.append({
                                "source": person,
                                "target": target,
                                "relation": rel_type,
                                "confidence": 0.85,
                                "match_text": pattern + target,
                                "position": idx,
                            })
                    idx += 1

        # ========== 关系词在名前的模式 ==========
        # 文本格式: "祖父X", "父X", "字X" - 关系词在名前
        # X是关系指向的人（如"祖父刘龠"中刘龠是祖父）
        # 需要根据上下文确定source（被描述的人）
        REL_PREFIX_TYPES = [
            ("祖父", "PATERNAL_GRANDFATHER"),
            ("祖母", "PATERNAL_GRANDMOTHER"),
            ("父", "FATHER"),
            ("母", "MOTHER"),
            ("字", "COURTESY_NAME"),
            ("号", "ART_NAME"),
        ]

        # 查找所有关系词出现位置，然后看前面最近的已知人名
        for prefix, rel_type in REL_PREFIX_TYPES:
            idx = 0
            while True:
                idx = text.find(prefix, idx)
                if idx < 0:
                    break
                # 避免匹配复合词中的部分（如"祖父"中的"父"）
                # 检查前一个字符是否是中文（若是则为复合词的一部分）
                if idx > 0 and re.match(r'[\u4e00-\u9fff]', text[idx - 1]):
                    idx += 1
                    continue
                # 获取关系词后的名字
                rest = text[idx + len(prefix):idx + len(prefix) + 5]
                m = re.match(r'([\u4e00-\u9fff]{2,4})', rest)
                if m:
                    target_name = m.group(1)
                    # 找前面最近的已知人物（在50字符内）
                    search_start = max(0, idx - 50)
                    search_text = text[search_start:idx]
                    # 反向查找最近的已知人名
                    source_person = None
                    for person in known_persons:
                        pos = search_text.rfind(person)
                        if pos >= 0:
                            source_person = person
                            break
                    if source_person and len(target_name) >= 2:
                        # 目标可能不在known_persons中（NER遗漏），仅用子串检查过滤
                        relations.append({
                            "source": source_person,
                            "target": target_name,
                            "relation": rel_type,
                            "confidence": 0.8,
                            "match_text": prefix + target_name,
                            "position": idx,
                        })
                idx += 1

        # 籍贯关系：已知人物名后跟"，...人"模式
        for person in known_persons:
            if len(person) < 2:
                continue
            # 查找 "X，...人" 模式
            pattern = person + "，"
            idx = 0
            while True:
                idx = text.find(pattern, idx)
                if idx < 0:
                    break
                # 看后面是否有 "X人" 或 "XX人"
                rest = text[idx + len(pattern):idx + len(pattern) + 15]
                m = re.match(r'([\u4e00-\u9fff]{2,4})人', rest)
                if m:
                    loc = m.group(1)
                    if len(loc) >= 2:
                        relations.append({
                            "source": person,
                            "relation": "NATIVE_OF",
                            "location": loc,
                            "confidence": 0.8,
                            "match_text": f"{person}，{loc}人",
                            "position": idx,
                        })
                idx += 1

        # 官员任职：查找已知人物的官职描述
        for person in known_persons:
            if len(person) < 2:
                continue
            # "知XX州" / "任XX府"
            for prefix in ["知", "任", "拜"]:
                pattern = person + prefix
                idx = 0
                while True:
                    idx = text.find(pattern, idx)
                    if idx < 0:
                        break
                    rest = text[idx + len(pattern):idx + len(pattern) + 10]
                    m = re.match(r'([\u4e00-\u9fff]{2,4})(州|府|县)', rest)
                    if m:
                        loc = m.group(1) + m.group(2)
                        relations.append({
                            "source": person,
                            "relation": "OFFICIAL",
                            "location": loc,
                            "confidence": 0.75,
                            "match_text": f"{person}{prefix}{loc}",
                            "position": idx,
                        })
                    idx += 1

        logger.info(f"抽取人物关系 {len(relations)} 条")
        return relations

    def build_kg_from_text(
        self,
        text: str,
        source: str = "unknown",
        title: str = "",
        use_llm: bool = True,
    ) -> Dict:
        """
        从文本构建知识图谱

        完整流程：
        1. 规则实体识别（基础）
        2. LLM辅助实体识别（增强，use_llm=True时）
        3. 规则关系抽取
        4. LLM辅助关系抽取（增强，use_llm=True时）
        5. 实体消解（去重合并）
        6. 返回结构化 KG 数据

        Args:
            text: 输入文本
            source: 来源（如 "康熙版固安县志"）
            title: 标题
            use_llm: 是否启用LLM辅助抽取（默认True）

        Returns:
            dict，包含 entities, relations, stats
        """
        logger.info(f"开始从文本构建 KG: source={source}, title={title}, use_llm={use_llm}")

        # Step 1: 规则实体识别（基础）
        entities = self.extract_entities(text)
        person_entities = [e for e in entities if e["type"] == "PER"]

        # Step 1b: LLM辅助实体识别（增强）
        if use_llm:
            llm_entities = self._extract_entities_with_llm(text)
            # 合并LLM实体到主列表
            for le in llm_entities:
                key = (le["name"], le["type"])
                if not any(e["name"] == le["name"] and e["type"] == le["type"] for e in entities):
                    entities.append(le)
                    if le["type"] == "PER":
                        person_entities.append(le)
            logger.info(f"LLM辅助识别后共 {len(entities)} 个实体")

        # Step 2: 规则关系抽取
        relations = self.extract_person_relations(text, person_entities)

        # Step 2b: LLM辅助关系抽取（增强）
        if use_llm:
            llm_relations = self._extract_relations_with_llm(text, person_entities)
            for lr in llm_relations:
                key = (lr["source"], lr["target"], lr["relation"])
                if not any(
                    r["source"] == lr["source"] and r["target"] == lr["target"] and r["relation"] == lr["relation"]
                    for r in relations
                ):
                    relations.append(lr)
            logger.info(f"LLM辅助抽取后共 {len(relations)} 条关系")

        # Step 3: 实体消解（合并相似实体）
        resolved_entities = self._resolve_entities(entities)

        stats = {
            "total_entities": len(entities),
            "person_entities": len(person_entities),
            "resolved_entities": len(resolved_entities),
            "total_relations": len(relations),
            "source": source,
            "title": title,
        }

        logger.info(f"KG 构建完成: {stats}")

        return {
            "entities": resolved_entities,
            "relations": relations,
            "stats": stats,
        }

    def _resolve_entities(self, entities: List[Dict]) -> List[Dict]:
        """对实体列表进行消解，去除重复。

        重构后：使用简单的 dict 去重（按 name + type），不再依赖 EntityResolver。
        复杂的别名合并交给 post_process_relations 在存储阶段处理。
        """
        if len(entities) <= 1:
            return entities

        try:
            seen: Dict[Tuple[str, str], Dict] = {}
            for e in entities:
                key = (e.get("name", ""), e.get("type", ""))
                if key not in seen:
                    seen[key] = e
                else:
                    # 合并 biography（取较长者）
                    existing_bio = seen[key].get("biography", "")
                    new_bio = e.get("biography", "")
                    if len(new_bio) > len(existing_bio):
                        seen[key]["biography"] = new_bio
            return list(seen.values())
        except Exception as e:
            logger.warning(f"实体消解失败: {e}，返回原始实体")
            return entities

    def _merge_entity_cluster(self, cluster: List[Dict]) -> Dict:
        """合并同类实体"""
        # 选取最长的名称
        best = max(cluster, key=lambda e: len(e.get("name", "")))

        merged = {
            "name": best["name"],
            "type": best["type"],
            "start": best.get("start", 0),
            "end": best.get("end", 0),
            "biography": best.get("biography", ""),
            "context": best.get("context", ""),
            "merged_count": len(cluster),
            "merged_from": [e.get("name", "") for e in cluster],
        }

        if "time" in best:
            merged["time"] = best["time"]
        if "location" in best:
            merged["location"] = best["location"]

        return merged

    def _extract_biography(self, text: str, entity: Dict) -> str:
        """提取实体的上下文传记信息"""
        start = entity.get("start", 0)
        end = entity.get("end", 0)

        # 提取实体周围 200 字符作为传记
        context_start = max(0, start - 100)
        context_end = min(len(text), end + 100)
        bio = text[context_start:context_end]

        # 清理换行
        bio = re.sub(r"\s+", " ", bio).strip()
        return bio

    def _extract_time(self, text: str, entity: Dict) -> Optional[Dict]:
        """提取时间信息"""
        # 常见年份模式：生于1234年，卒于5678年
        name = entity.get("name", "")
        patterns = [
            r"(%s)[^字]*生[于]?(\d{4})年?" % re.escape(name),
            r"(%s)[^字]*卒[于]?(\d{4})年?" % re.escape(name),
            r"(%s)[^字]*殁[于]?(\d{4})年?" % re.escape(name),
        ]

        time_info = {}
        full_pattern = "|".join(patterns)
        matches = re.findall(full_pattern, text)

        for match in matches:
            if len(match) >= 2 and match[1]:
                try:
                    year = int(match[1])
                    if "生" in text[max(0, entity["start"] - 20):entity["end"] + 20]:
                        time_info["birth_year"] = year
                    elif "卒" in text[max(0, entity["start"] - 20):entity["end"] + 20]:
                        time_info["death_year"] = year
                except ValueError:
                    pass

        return time_info if time_info else None

    def _extract_location(self, text: str, entity: Dict) -> Optional[str]:
        """提取地名信息"""
        # 常见模式："X，Y人" → Y是籍贯
        name = entity.get("name", "")
        pattern = re.compile(r"%s[，,]?([^字辈父母子妻兄姐弟丧殁卒生]{2,6})人" % re.escape(name))
        match = pattern.search(text)
        if match:
            return match.group(1)
        return None

    # ==================== LLM辅助抽取 ====================

    def _get_llm_client(self):
        """获取Ollama LLM客户端（延迟加载）"""
        if not hasattr(self, "_llm_client") or self._llm_client is None:
            try:
                from ..llm.ollama_client import OllamaClient
                self._llm_client = OllamaClient()
                logger.info("KGPipeline LLM客户端初始化成功")
            except Exception as e:
                logger.warning(f"KGPipeline LLM客户端初始化失败: {e}")
                self._llm_client = None
        return self._llm_client

    def _extract_entities_with_llm(self, text: str) -> List[Dict]:
        """
        使用LLM从文本中提取实体

        Args:
            text: 输入文本（取前4000字避免超出上下文）

        Returns:
            实体列表
        """
        llm = self._get_llm_client()
        if llm is None:
            return []

        # 截取文本（保留开头和结尾的关键信息）
        if len(text) > 4000:
            sample_text = text[:2000] + "\n...[中间省略]...\n" + text[-2000:]
        else:
            sample_text = text

        prompt = f"""你是一位古籍研究专家，擅长从地方志文本中识别人物、地名、官职等实体。

请从以下文本中提取所有实体，以JSON数组格式返回。每条实体包含：
- name: 实体名称
- type: 实体类型（PER=人物, LOC=地名, TITLE=官职）
- biography: 该人物的传记摘要（50字以内）

只返回JSON数组，不要包含其他文字。

文本：
{sample_text}

返回格式示例：
[
  {{"name": "张巡", "type": "PER", "biography": "唐朝名将，守睢阳，城破殉国"}},
  {{"name": "固安县", "type": "LOC", "biography": ""}}
]"""

        try:
            response = llm.generate(prompt)
            # 解析JSON响应
            entities = self._parse_llm_json_response(response)
            if entities:
                logger.info(f"LLM提取到 {len(entities)} 个实体")
            return entities
        except Exception as e:
            logger.warning(f"LLM实体抽取失败: {e}")
            return []

    def _extract_relations_with_llm(self, text: str, known_persons: List[Dict]) -> List[Dict]:
        """
        使用LLM从文本中抽取人物关系

        Args:
            text: 输入文本
            known_persons: 已识别的人物列表

        Returns:
            关系列表
        """
        llm = self._get_llm_client()
        if llm is None:
            return []

        person_names = [p["name"] for p in known_persons if len(p.get("name", "")) >= 2]
        if not person_names:
            return []

        # 取前3000字
        sample_text = text[:3000] if len(text) > 3000 else text

        persons_str = "、".join(person_names[:30])
        if len(person_names) > 30:
            persons_str += f"等（共{len(person_names)}人）"

        prompt = f"""你是一位古籍研究专家，擅长从地方志文本中分析人物之间的关系。

已知文本中的人物有：{persons_str}

请分析以下文本，提取这些人物之间的关系，以JSON数组格式返回。每条关系包含：
- source: 关系源人物（被描述的人）
- target: 关系目标人物
- relation: 关系类型（FATHER/MOTHER/SON/DAUGHTER/WIFE/HUSBAND/ELDER_BROTHER/YOUNGER_BROTHER/ELDER_SISTER/YOUNGER_SISTER/OFFICIAL/STUDENT_OF/DISCIPLE/NATIVE_OF/COURTESY_NAME/ART_NAME/RELATED）

只返回JSON数组，不要包含其他文字。如果某人物的关系不明确，skip该关系。

文本：
{sample_text}

返回格式示例：
[
  {{"source": "张巡", "target": "张苛", "relation": "FATHER", "confidence": 0.9}},
  {{"source": "李林", "target": "固安县", "relation": "NATIVE_OF", "confidence": 0.8}}
]"""

        try:
            response = llm.generate(prompt)
            relations = self._parse_llm_json_response(response)
            if relations:
                # 验证source和target是否在已知人物列表中
                known_names = set(person_names)
                valid_relations = []
                for rel in relations:
                    src = rel.get("source", "")
                    tgt = rel.get("target", "")
                    if src and tgt and src in known_names and tgt in known_names and src != tgt:
                        rel["confidence"] = rel.get("confidence", 0.8)
                        valid_relations.append(rel)
                logger.info(f"LLM提取到 {len(valid_relations)} 条有效关系")
                return valid_relations
            return []
        except Exception as e:
            logger.warning(f"LLM关系抽取失败: {e}")
            return []

    def _parse_llm_json_response(self, response: str) -> List[Dict]:
        """
        解析LLM返回的JSON字符串

        处理各种格式问题： markdown代码块、前后多余文字等
        """
        import json
        # 去除markdown代码块标记
        text = response.strip()
        if text.startswith("```"):
            # 去除 ```json 或 ``` 等标记
            lines = text.split("\n")
            text = "\n".join(lines[1:])  # 去除第一行
            text = text.rsplit("```", 1)[0]  # 去除最后一个 ```
        text = text.strip()

        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "entities" in data:
                return data["entities"]
            elif isinstance(data, dict) and "relations" in data:
                return data["relations"]
            else:
                return []
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}, 原始响应: {response[:200]}")
            return []
