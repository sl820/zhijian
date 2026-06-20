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
from pathlib import Path
from typing import Dict, List, Optional, Set

from .. import config as app_config
from ..kg.classifier import classify_person

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

        注：person_type 始终由 classifier 决定（不信任调用方传入值）。
        """
        if not person or not person.get("name"):
            raise ValueError("person 必须包含 'name' 字段")
        name = person["name"]
        if name in self._persons:
            # 更新非空字段（person_type 由 classifier 强制重算）
            for k, v in person.items():
                if k == "person_type":
                    continue
                if v not in (None, ""):
                    self._persons[name][k] = v
            self._persons[name]["person_type"] = classify_person(self._persons[name])
        else:
            # 新建
            stored = {
                "name": name,
                "biography": person.get("biography", ""),
                "dynasty": person.get("dynasty", ""),
                "years": person.get("years", ""),
                "birthplace": person.get("birthplace", ""),
                "title": person.get("title", ""),
                "family_name": person.get("family_name", ""),
                "role_of_family": person.get("role_of_family", ""),
                "source": person.get("source", ""),
            }
            stored["person_type"] = classify_person(stored)
            self._persons[name] = stored
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

    # Step 1: 原文规则抽取（M4：拆到 SuffixPatternExtractor，25 patterns + 分段扫描）
    from app.kg.relation_extractor import SuffixPatternExtractor
    extractor = SuffixPatternExtractor(
        stored_names=stored_names,
        dynasty_markers=dynasty_markers,
        era_names=era_names,
    )

    # 跨全文分段扫描（取消 5k 截断的关键改动）
    for person_name in list(stored_names):
        extracted = extractor.extract(full_text, person_name)
        for rel in extracted:
            try:
                service.add_relation(
                    rel["from"], rel["to"], rel["type"], confidence=rel["confidence"],
                )
                relations_stored += 1
            except Exception:
                pass

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
