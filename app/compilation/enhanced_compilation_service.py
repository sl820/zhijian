"""
增强版辑佚服务 - 集成实体消解

在原有CompilationService基础上添加：
1. 实体抽取：从融合文本中提取人名、地名、机构名
2. 实体消解：跨版本识别同一实体
3. 实体融合：合并消解后的实体记录

Usage:
    from enhanced_compilation_service import EnhancedCompilationService

    service = EnhancedCompilationService()
    result = service.compile_with_entities(source_configs)
    # result 包含 merged_text, merge_info, entities, clusters
"""

import logging
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .compilation_service import CompilationService
from ..normalize.ner_model import NERModel
from ..entity_resolution.resolver import EntityResolver

logger = logging.getLogger(__name__)


# 古籍NER模式（补充NER模型）
CLASSICAL_CHINESE_PATTERNS = {
    # 朝代年号
    "DYNASTY_YEAR": re.compile(
        r'(?:'
        r'西周|东周|战国|秦|西汉|东汉|三国|西晋|东晋|南北朝|隋|唐|五代|宋|辽|金|元|明|清'
        r')[朝代国号年岁祭](?:'
        r'\d+|'
        r'[一二三四五六七八九十百零〇]+年?'
        r')'
    ),
    # 职官
    "OFFICIAL": re.compile(
        r'(?:'
        r'知州|知府|县令|太守|刺史|尚书|侍郎|丞相|太尉|将军|御史|主簿|县尉'
        r'|'
        r'教授|教谕|学正|训导|博士|助教'
        r'|'
        r'举人|进士|状元|榜眼|探花|贡生|秀才'
        r')'
    ),
}


@dataclass
class ExtractedEntity:
    """抽取的实体"""
    name: str
    entity_type: str  # PER, LOC, ORG, TIME, OFFICIAL
    source: str  # 来源文本标识
    context: str  # 上下文（用于消解）
    position: int  # 在文本中的起始位置


class EnhancedCompilationService:
    """
    增强版辑佚服务

    在CompilationService基础上添加：
    - 实体抽取（NER + 规则）
    - 实体消解（EntityResolver）
    - 实体融合（EntityMerger）
    """

    def __init__(self, config: dict = None):
        """
        初始化增强辑佚服务

        Args:
            config: 配置参数
                - ner_model: NER模型路径（默认使用bert-base-chinese）
                - entity_threshold: 实体消解阈值 (default: 0.75)
                - 其他继承自CompilationService的参数
        """
        self.config = config or {}

        # 初始化基础辑佚服务
        compilation_config = {
            k: v for k, v in self.config.items()
            if k in ["dedup_threshold", "dedup_method", "merge_strategy", "quality_weights"]
        }
        self.base_service = CompilationService(compilation_config)

        # 初始化NER模型
        self._ner_model = None

        # 初始化实体消解器
        entity_config = {
            "default_threshold": self.config.get("entity_threshold", 0.75),
            "name_weight": 0.35,  # 提高名称权重
            "time_weight": 0.25,
            "location_weight": 0.2,
            "context_weight": 0.2,
        }
        self.entity_resolver = EntityResolver(entity_config)

        # 实体缓存
        self._entities: List[ExtractedEntity] = []

        logger.info("EnhancedCompilationService初始化完成")

    @property
    def ner_model(self):
        """懒加载NER模型"""
        if self._ner_model is None:
            model_path = self.config.get("ner_model", "bert-base-chinese")
            self._ner_model = NERModel(model_path=model_path)
        return self._ner_model

    def extract_entities_from_text(
        self,
        text: str,
        source: str = "unknown"
    ) -> List[ExtractedEntity]:
        """
        从文本中抽取实体

        Args:
            text: 古籍文本
            source: 来源标识

        Returns:
            抽取的实体列表
        """
        entities = []

        # 1. NER模型抽取
        try:
            ner_results = self.ner_model.predict(text)
            for entity in ner_results:
                ent = ExtractedEntity(
                    name=entity.get("name", ""),
                    entity_type=entity.get("type", "PER"),
                    source=source,
                    context=self._extract_context(text, entity.get("start", 0), entity.get("end", 0)),
                    position=entity.get("start", 0)
                )
                entities.append(ent)
        except Exception as e:
            logger.warning(f"NER抽取失败: {e}")

        # 2. 规则抽取补充
        # 职官名
        for match in CLASSICAL_CHINESE_PATTERNS["OFFICIAL"].finditer(text):
            name = match.group()
            # 检查是否已存在
            if not any(e.name == name and e.entity_type == "OFFICIAL" for e in entities):
                ent = ExtractedEntity(
                    name=name,
                    entity_type="OFFICIAL",
                    source=source,
                    context=self._extract_context(text, match.start(), match.end()),
                    position=match.start()
                )
                entities.append(ent)

        logger.info(f"从 {source} 抽取了 {len(entities)} 个实体")

        # 按名称去重
        seen = set()
        unique_entities = []
        for e in entities:
            key = (e.name, e.entity_type)
            if key not in seen:
                seen.add(key)
                unique_entities.append(e)

        return unique_entities

    def _extract_context(self, text: str, start: int, end: int, window: int = 50) -> str:
        """提取实体上下文字符串"""
        ctx_start = max(0, start - window)
        ctx_end = min(len(text), end + window)
        return text[ctx_start:ctx_end]

    def resolve_entities(
        self,
        entities: List[ExtractedEntity]
    ) -> List[List[ExtractedEntity]]:
        """
        实体消解：将相似的实体聚类

        Args:
            entities: 抽取的实体列表

        Returns:
            消解后的实体聚类列表
        """
        if not entities:
            return []

        # 转换为EntityResolver格式
        entity_dicts = []
        for ent in entities:
            entity_dict = {
                "name": ent.name,
                "type": ent.entity_type,
                "time": {},
                "location": "",
                "context": ent.context
            }

            # 尝试从上下文中提取时间
            time_match = CLASSICAL_CHINESE_PATTERNS["DYNASTY_YEAR"].search(ent.context)
            if time_match:
                year_text = time_match.group()
                # 简单解析年号
                entity_dict["time"] = {"raw": year_text}

            # 尝试从上下文中提取地名
            loc_pattern = re.compile(r'[\u4e00-\u9fa5]{2,4}(?:县|州|府|城|乡|镇|村)')
            loc_match = loc_pattern.search(ent.context)
            if loc_match:
                entity_dict["location"] = loc_match.group()

            entity_dicts.append(entity_dict)

        # 聚类
        try:
            clusters = self.entity_resolver.cluster_entities(entity_dicts)
            logger.info(f"实体消解完成: {len(clusters)} 个聚类")

            # 转换回ExtractedEntity格式
            # 由于聚类后丢失了实体对象，我们重新构建
            # 这里简化处理，直接按名称匹配
            result_clusters = []
            name_to_entities = {}
            for ent in entities:
                if ent.name not in name_to_entities:
                    name_to_entities[ent.name] = []
                name_to_entities[ent.name].append(ent)

            for cluster in clusters:
                cluster_entities = []
                for ent_dict in cluster:
                    name = ent_dict.get("name", "")
                    if name in name_to_entities:
                        cluster_entities.extend(name_to_entities[name])
                if cluster_entities:
                    result_clusters.append(cluster_entities)

            return result_clusters

        except Exception as e:
            logger.error(f"实体消解失败: {e}")
            # 回退：按名称分组
            name_groups = {}
            for ent in entities:
                if ent.name not in name_groups:
                    name_groups[ent.name] = []
                name_groups[ent.name].append(ent)
            return list(name_groups.values())

    def compile_with_entities(
        self,
        source_configs: List[Dict],
        deduplicate: bool = True,
        merge_strategy: str = None,
        extract_entities: bool = True,
        resolve: bool = True
    ) -> Dict:
        """
        完整辑佚流程（带实体处理）

        在原有compile流程基础上添加：
        1. 收集来源
        2. 去重
        3. 融合
        4. 实体抽取
        5. 实体消解

        Args:
            source_configs: 来源配置列表
            deduplicate: 是否去重
            merge_strategy: 融合策略
            extract_entities: 是否抽取实体
            resolve: 是否消解实体

        Returns:
            {
                "merged_text": "...",
                "merge_info": {...},
                "unique_source_count": N,
                "entities": [  # 抽取的实体
                    {"name": "...", "type": "PER", "count": 3, "sources": ["康熙版", "咸丰版"]},
                    ...
                ],
                "entity_clusters": [  # 消解后的实体聚类
                    {
                        "canonical_name": "张知州",
                        "entities": [...],
                        "similarity": 0.85
                    },
                    ...
                ],
                "provenance": {...}
            }
        """
        logger.info("=== 开始增强辑佚流程（带实体处理）===")

        # Step 1-3: 基础辑佚流程
        base_result = self.base_service.compile(
            source_configs,
            deduplicate=deduplicate,
            merge_strategy=merge_strategy
        )

        result = {
            "merged_text": base_result["merged_text"],
            "merge_info": base_result["merge_info"],
            "unique_source_count": base_result["unique_source_count"],
            "total_source_count": base_result["total_source_count"],
            "duplicate_group_count": base_result.get("duplicate_group_count", 0),
            "provenance": base_result.get("provenance", {}),
            "entities": [],
            "entity_clusters": []
        }

        if not extract_entities:
            return result

        # Step 4: 实体抽取
        logger.info("Step 4: 抽取实体...")
        all_entities = []

        # 从融合文本中抽取
        merged_text = result["merged_text"]
        if merged_text:
            entities = self.extract_entities_from_text(merged_text, source="merged")
            all_entities.extend(entities)

        # 从各来源文本中抽取（保留来源信息）
        for source in base_result.get("provenance", {}).get("sources", []):
            source_text = source.get("text", "")
            source_name = source.get("name", "unknown")
            if source_text:
                entities = self.extract_entities_from_text(source_text, source=source_name)
                all_entities.extend(entities)

        # 汇总统计
        entity_stats = {}
        for ent in all_entities:
            key = (ent.name, ent.entity_type)
            if key not in entity_stats:
                entity_stats[key] = {
                    "name": ent.name,
                    "type": ent.entity_type,
                    "count": 0,
                    "sources": set()
                }
            entity_stats[key]["count"] += 1
            if ent.source:
                entity_stats[key]["sources"].add(ent.source)

        result["entities"] = [
            {
                "name": v["name"],
                "type": v["type"],
                "count": v["count"],
                "sources": list(v["sources"])
            }
            for v in entity_stats.values()
        ]

        # 按出现次数排序
        result["entities"].sort(key=lambda x: x["count"], reverse=True)

        logger.info(f"共抽取 {len(result['entities'])} 种实体")

        if not resolve:
            return result

        # Step 5: 实体消解
        logger.info("Step 5: 实体消解...")
        clusters = self.resolve_entities(all_entities)

        result["entity_clusters"] = [
            {
                "canonical_name": cluster[0].name if cluster else "",
                "type": cluster[0].entity_type if cluster else "",
                "entities": [
                    {"name": e.name, "source": e.source}
                    for e in cluster
                ],
                "count": len(cluster)
            }
            for cluster in clusters
            if cluster
        ]

        logger.info(f"实体消解完成: {len(result['entity_clusters'])} 个聚类")

        return result


# 全局单例
_enhanced_service: Optional[EnhancedCompilationService] = None


def get_enhanced_compilation_service(config: dict = None) -> EnhancedCompilationService:
    """获取增强辑佚服务单例"""
    global _enhanced_service
    if _enhanced_service is None:
        _enhanced_service = EnhancedCompilationService(config)
    return _enhanced_service
