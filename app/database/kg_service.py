"""
知识图谱服务 — 纯内存实现

设计原则：
- 无外部数据库依赖（不依赖 Neo4j / Milvus / Docker）
- 启动时从 JSON 持久化文件加载，每次写入后落盘
- 简单可读的纯 Python 数据结构（dict + list + set）
- 接口稳定，调用方完全不需要知道是 in-memory

数据模型：
- persons:  { name -> { name, dynasty, years, biography, ... } }
- relations: [ { from, to, type, confidence } ]

时间复杂度：
- add_person / has_person: O(1) 哈希查找
- add_relation: O(1) 追加
- get_all_persons: O(N)
- get_graph_data: O(N + R)
- get_person_with_relations: O(R * depth)  BFS
"""
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from .. import config as app_config

logger = logging.getLogger(__name__)


# ============================================================
# 公开服务类
# ============================================================

class KnowledgeGraphService:
    """知识图谱服务（in-memory + JSON 持久化）"""

    def __init__(self, persist_path: Optional[Path] = None):
        self._persist_path = persist_path or app_config.KG_PERSIST_PATH
        self._persons: Dict[str, dict] = {}
        self._relations: List[dict] = []
        self._load()
        logger.info(
            f"KnowledgeGraphService 初始化完成: "
            f"{len(self._persons)} persons, {len(self._relations)} relations "
            f"(persist={self._persist_path})"
        )

    # ---------------------------------------------------------- 持久化

    def _load(self):
        if self._persist_path and Path(self._persist_path).exists():
            try:
                data = json.loads(Path(self._persist_path).read_text(encoding="utf-8"))
                self._persons = {p["name"]: p for p in data.get("persons", [])}
                self._relations = data.get("relations", [])
            except Exception as e:
                logger.warning(f"KG 持久化文件加载失败（{e}），使用空图")
                self._persons = {}
                self._relations = []

    def _save(self):
        if not self._persist_path:
            return
        try:
            p = Path(self._persist_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "persons": list(self._persons.values()),
                "relations": self._relations,
            }
            p.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"KG 持久化失败: {e}")

    # ---------------------------------------------------------- CRUD

    def add_person(self, person: dict) -> dict:
        """添加 / 更新一个人物（按 name 去重）。

        接收 dict 至少含 'name' 字段，其他字段（biography, dynasty, years, birthplace, ...）按需传入。
        返回存储后的完整 dict。
        """
        if not person or not person.get("name"):
            raise ValueError("person 必须包含 'name' 字段")
        name = person["name"]
        if name in self._persons:
            # 更新非空字段
            for k, v in person.items():
                if v not in (None, ""):
                    self._persons[name][k] = v
        else:
            # 新建
            self._persons[name] = {
                "name": name,
                "biography": person.get("biography", ""),
                "dynasty": person.get("dynasty", ""),
                "years": person.get("years", ""),
                "birthplace": person.get("birthplace", ""),
                "title": person.get("title", ""),
                "person_type": person.get("person_type", 2),
                "source": person.get("source", ""),
            }
        self._save()
        return self._persons[name]

    def has_person(self, name: str) -> bool:
        return name in self._persons

    def add_relation(
        self,
        from_name: str,
        to_name: str,
        relation_type: str,
        confidence: float = 0.5,
    ) -> dict:
        """添加一条人物关系。两端若不存在则自动创建为 stub。"""
        if not from_name or not to_name:
            raise ValueError("from_name 和 to_name 必填")
        for stub in (from_name, to_name):
            if stub not in self._persons:
                self._persons[stub] = {"name": stub, "stub": True}
        rel = {
            "from": from_name,
            "to": to_name,
            "type": relation_type,
            "confidence": float(confidence),
        }
        self._relations.append(rel)
        self._save()
        return rel

    def clear(self) -> None:
        self._persons.clear()
        self._relations.clear()
        self._save()
        logger.info("KG 已清空")

    # ---------------------------------------------------------- 查询

    def get_all_persons(self, limit: int = 200) -> List[dict]:
        """获取人物列表（按 name 排序），限制 limit 条"""
        return sorted(self._persons.values(), key=lambda p: p.get("name", ""))[:limit]

    def get_person_with_relations(self, name: str, depth: int = 1) -> Optional[dict]:
        """获取人物详情 + 直接关联的人物（BFS depth 跳）。不存在返回 None。"""
        if name not in self._persons:
            return None
        person = dict(self._persons[name])
        related_names: Set[str] = set()
        frontier = {name}
        for _ in range(max(1, depth)):
            next_frontier: Set[str] = set()
            for rel in self._relations:
                if rel["from"] in frontier and rel["to"] not in related_names and rel["to"] != name:
                    next_frontier.add(rel["to"])
                if rel["to"] in frontier and rel["from"] not in related_names and rel["from"] != name:
                    next_frontier.add(rel["from"])
            related_names.update(next_frontier)
            frontier = next_frontier
        # 直接关系列表（与该人物直接相连的）
        direct_relations = [
            {
                "type": r["type"],
                "name": r["to"] if r["from"] == name else r["from"],
                "direction": "outgoing" if r["from"] == name else "incoming",
                "confidence": r.get("confidence", 0.5),
            }
            for r in self._relations
            if r["from"] == name or r["to"] == name
        ]
        person["relations"] = direct_relations
        person["related_persons"] = sorted(related_names)
        return person

    def get_graph_data(self, limit: int = 200) -> dict:
        """ECharts 力导向图所需数据：nodes + links"""
        persons = self.get_all_persons(limit=limit)
        name_set = {p["name"] for p in persons}
        # 仅保留两端都在 nodes 中的关系
        links = []
        seen = set()
        for r in self._relations:
            if r["from"] in name_set and r["to"] in name_set:
                key = (r["from"], r["to"], r["type"])
                if key not in seen:
                    seen.add(key)
                    links.append({
                        "source": r["from"],
                        "target": r["to"],
                        "name": r["type"],
                        "relation": r["type"],
                    })
        nodes = [
            {
                "id": p["name"],
                "name": p["name"],
                "category": p.get("person_type", 2),
                "dynasty": p.get("dynasty", ""),
                "title": p.get("title", ""),
                "years": p.get("years", ""),
                "birthplace": p.get("birthplace", ""),
                "biography": p.get("biography", ""),
                "source": p.get("source", ""),
            }
            for p in persons
        ]
        return {
            "nodes": nodes,
            "links": links,
            "total_persons": len(nodes),
            "total_links": len(links),
            "status": "ready",
        }

    def get_stats(self) -> dict:
        return {
            "person_count": len(self._persons),
            "relation_count": len(self._relations),
        }

    def get_kg_status(self) -> dict:
        stats = self.get_stats()
        return {
            "status": "ready",
            "mode": "in_memory",
            "message": f"纯内存 KG，已持久化到 {self._persist_path}",
            "person_count": stats["person_count"],
            "relation_count": stats["relation_count"],
            "persist_path": str(self._persist_path),
        }


# ============================================================
# 模块级工具函数（被 routes.py 的 /kg/init 调用）
# ============================================================

def identify_dynasty(bio_text: str) -> str:
    """从传记文本里识别朝代（取第一个匹配的朝代标记）"""
    if not bio_text:
        return ""
    for marker in app_config.DYNASTY_MARKERS:
        if marker in bio_text:
            return marker
    return ""


_REL_SUFFIX_PATTERNS = [
    ("之父", "FATHER"),
    ("之母", "MOTHER"),
    ("之子", "SON"),
    ("之女", "DAUGHTER"),
    ("之兄", "ELDER_BROTHER"),
    ("之弟", "YOUNGER_BROTHER"),
    ("之妻", "WIFE"),
]

_STOP_CHARS = set("以，。；、：（）\"\"''【】《》" + "0123456789")


def _is_valid_target(target: str, stored: Set[str], dynasty_markers: Set[str], era_names: Set[str]) -> bool:
    if not target or len(target) < 2:
        return False
    if target in dynasty_markers or target in era_names:
        return False
    if target[0].isdigit() or target.startswith("之"):
        return False
    # 排除是别人子串的（避免 "X" 跟 "XX" 误匹配）
    if any(target in p and target != p for p in stored):
        return False
    return True


def post_process_relations(
    service: KnowledgeGraphService,
    full_text: str,
    stored_names: Set[str],
    pipeline_relations: List[dict],
) -> int:
    """
    后处理：从原文重新抽取家族关系，补充 pipeline 漏掉的关系。
    返回新存储的关系数。

    实现说明：
    - pipeline 的 extract_person_relations 在 entity-resolution 阶段会因短名覆盖而漏抽，
      此处直接用 stored_names 在原文中做规则匹配。
    - 同时也接受 pipeline 已抽到的 relations 列表，把两端都在 stored_names 里的存进去。
    """
    if not stored_names:
        return 0

    dynasty_markers = set(app_config.DYNASTY_MARKERS)
    era_names = app_config.ERA_NAMES
    relations_stored = 0

    # Step 1: 原文规则抽取
    for person_name in list(stored_names):
        # 在传记局部 + 原文前 5000 字中搜索
        search_text = full_text[:5000]

        for suffix, rel_type in _REL_SUFFIX_PATTERNS:
            pattern = person_name + suffix
            pos = 0
            while True:
                pos = search_text.find(pattern, pos)
                if pos < 0:
                    break
                rest = search_text[pos + len(pattern) : pos + len(pattern) + 8]
                # 跳过非 CJK 字符
                skip = 0
                while skip < len(rest) and not ('一' <= rest[skip] <= '鿿'):
                    skip += 1
                rest_cjk = rest[skip:]
                if not rest_cjk:
                    pos += 1
                    continue
                # 优先：从"之"前面找已知人名（处理"张缅，张弘策之子"类型）
                person_start = pos + len(pattern) - len(suffix)
                search_back = search_text[max(0, person_start - 10) : person_start]
                target = None
                for p_name in stored_names:
                    if p_name != person_name and len(p_name) >= 2 and search_back.rfind(p_name) >= 0:
                        target = p_name
                        break
                # 回退：提取 CJK 序列并清理
                if target is None:
                    year_m = re.match(r'([一-龥]{1,3})年', rest_cjk)
                    if year_m and len(year_m.group(1)) >= 2:
                        cjk_seq = year_m.group(1)
                    else:
                        end_idx = 0
                        while end_idx < len(rest_cjk) and rest_cjk[end_idx] not in _STOP_CHARS:
                            end_idx += 1
                        cjk_seq = rest_cjk[:end_idx] if end_idx > 0 else rest_cjk[:4]
                    m = re.match(r'([一-龥]{2,4})', cjk_seq)
                    if not m:
                        pos += 1
                        continue
                    target = m.group(1)
                    for s in ["后裔", "后"]:
                        if target.startswith(s):
                            target = target[len(s):]
                            break
                if _is_valid_target(target, stored_names, dynasty_markers, era_names):
                    try:
                        service.add_relation(person_name, target, rel_type, confidence=0.85)
                        relations_stored += 1
                    except Exception:
                        pass
                pos += 1

    # Step 2: 存 pipeline 抽到的关系（仅当两端都在 stored_names）
    for rel in pipeline_relations:
        from_name = rel.get("source", "")
        to_name = rel.get("target", "")
        if not from_name or not to_name:
            continue
        if to_name in dynasty_markers:
            continue
        if from_name not in stored_names or to_name not in stored_names:
            continue
        try:
            service.add_relation(
                from_name,
                to_name,
                rel.get("relation", "RELATED"),
                confidence=rel.get("confidence", 0.5),
            )
            relations_stored += 1
        except Exception as e:
            logger.warning(f"Failed to store relation {from_name}->{to_name}: {e}")

    return relations_stored
