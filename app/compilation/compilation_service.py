"""
多源辑佚服务 - 整合抓取、去重、融合、排序全流程

Usage:
1. 收集多个来源的古籍文本
2. 检测并去除重复内容
3. 评估版本质量
4. 智能融合多版本内容
5. 追踪来源血缘关系
"""

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import asdict

from .scraper import SourceScraper, TextSource, SourceType
from .dedup import TextHasher, Deduplicator
from .merger import TextMerger, MergeStrategy
from .ranker import VersionRanker, ProvenanceTracker

logger = logging.getLogger(__name__)


class CompilationService:
    """
    多源辑佚服务

    整合抓取、去重、融合、排序的完整流程
    """

    def __init__(self, config: dict = None):
        """
        初始化辑佚服务

        Args:
            config: 配置参数
                - dedup_threshold: 去重相似度阈值 (default: 0.85)
                - dedup_method: 去重方法 'minhash' or 'simhash' (default: 'minhash')
                - merge_strategy: 默认融合策略 (default: 'prefer_complete')
                - quality_weights: 版本评分权重
        """
        self.config = config or {}

        # 初始化各组件
        self.scraper = SourceScraper()
        self.hasher = TextHasher()
        self.deduplicator = Deduplicator(
            threshold=self.config.get("dedup_threshold", 0.85),
            method=self.config.get("dedup_method", "minhash")
        )
        self.merger = TextMerger(
            strategy=self.config.get("merge_strategy", "prefer_complete")
        )
        self.ranker = VersionRanker(
            weights=self.config.get("quality_weights")
        )
        self.provenance_tracker = ProvenanceTracker()

        logger.info("CompilationService初始化完成")

    def collect_sources(self, source_configs: List[Dict]) -> List[TextSource]:
        """
        从多个配置收集古籍来源

        Args:
            source_configs: 来源配置列表，每项包含:
                - type: 来源类型
                - url: URL或路径
                - ocr_callback: 回调函数（用于本地扫描件）

        Returns:
            收集到的TextSource列表
        """
        all_sources = []

        for config in source_configs:
            try:
                source_type = config.get("type")
                url = config.get("url")

                if source_type == SourceType.CTEXT_ORG:
                    source = self.scraper.fetch_ctext(url)
                    all_sources.append(source)

                elif source_type == SourceType.CUSTOM_URL:
                    source = self.scraper.fetch_custom_url(url)
                    all_sources.append(source)

                elif source_type == SourceType.LIBRARY_CATALOG:
                    filters = config.get("filters", {})
                    sources = self.scraper.fetch_library_catalog(url, filters)
                    all_sources.extend(sources)

                elif source_type == SourceType.LOCAL_SCAN:
                    ocr_callback = config.get("ocr_callback")
                    sources = self.scraper.fetch_local_scan(url, ocr_callback)
                    all_sources.extend(sources)

            except Exception as e:
                logger.error(f"收集来源失败: {config.get('url')}, 错误: {e}")

        logger.info(f"共收集到 {len(all_sources)} 个来源")

        # 按质量排序
        ranked = self.ranker.rank_versions(all_sources)
        logger.info(f"来源质量排序完成，最高分: {ranked[0][1]:.3f}" if ranked else "")

        return all_sources

    def deduplicate(self, sources: List[TextSource],
                    remove_duplicates: bool = True) -> Dict:
        """
        检测并去除重复来源

        Args:
            sources: TextSource列表
            remove_duplicates: 是否实际删除重复项

        Returns:
            {
                "unique_sources": [...],  # 去重后的来源
                "duplicate_groups": [[idx1, idx2, ...], ...],  # 重复组
                "duplicate_pairs": [(idx1, idx2, similarity), ...]
            }
        """
        texts = [s.text_content for s in sources]

        # 查找重复对
        duplicate_pairs = self.deduplicator.find_duplicates(texts)

        # 聚类重复项
        duplicate_clusters = self.deduplicator.cluster_documents(texts)

        logger.info(f"发现 {len(duplicate_pairs)} 对重复，{len(duplicate_clusters)} 个重复组")

        if not remove_duplicates:
            return {
                "unique_sources": sources,
                "duplicate_groups": duplicate_clusters,
                "duplicate_pairs": duplicate_pairs
            }

        # 去除重复，保留最优版本
        text_to_source = {s.text_content: s for s in sources}
        unique_texts = self.deduplicator.deduplicate(texts, prefer_longer=True)
        unique_sources = [text_to_source[t] for t in unique_texts]

        # 重新排序
        unique_sources = [s for s, _ in self.ranker.rank_versions(unique_sources)]

        return {
            "unique_sources": unique_sources,
            "duplicate_groups": duplicate_clusters,
            "duplicate_pairs": duplicate_pairs
        }

    def merge_versions(self, sources: List[TextSource],
                       strategy: str = None) -> Tuple[str, Dict]:
        """
        融合多个版本

        Args:
            sources: 排序后的TextSource列表（已去重）
            strategy: 融合策略（可选）

        Returns:
            (融合后的文本, 融合信息)
        """
        if not sources:
            return "", {}

        if len(sources) == 1:
            return sources[0].text_content, {
                "sources_used": [sources[0].source_name],
                "strategy": "single_source",
                "confidence": 1.0
            }

        # 准备文本和元数据列表
        texts = [s.text_content for s in sources]
        metadata_list = [
            {
                "source_name": s.source_name,
                "source_type": s.source_type.value if hasattr(s.source_type, 'value') else str(s.source_type),
                "quality_score": s.quality_score,
                "year": s.metadata.get("year") if s.metadata else None
            }
            for s in sources
        ]

        # 融合
        merger_strategy = strategy or self.config.get("merge_strategy", "prefer_complete")
        merged_text, merge_info = self.merger.merge_multiple(
            texts, metadata_list, strategy=merger_strategy
        )

        logger.info(f"融合完成: {merge_info.get('sources_used', [])}, "
                   f"策略: {merge_info.get('strategy')}, "
                   f"置信度: {merge_info.get('confidence', 0):.2f}")

        return merged_text, merge_info

    def compile(self, source_configs: List[Dict],
                deduplicate: bool = True,
                merge_strategy: str = None) -> Dict:
        """
        完整的辑佚流程

        Args:
            source_configs: 来源配置列表
            deduplicate: 是否去重
            merge_strategy: 融合策略

        Returns:
            {
                "merged_text": "...",
                "merge_info": {...},
                "unique_source_count": N,
                "duplicate_group_count": M,
                "provenance": {...}
            }
        """
        logger.info("=== 开始辑佚流程 ===")

        # Step 1: 收集来源
        logger.info("Step 1: 收集来源...")
        sources = self.collect_sources(source_configs)

        if not sources:
            return {
                "merged_text": "",
                "merge_info": {"error": "未能收集到任何来源"},
                "unique_source_count": 0,
                "duplicate_group_count": 0,
                "provenance": {}
            }

        # Step 2: 去重
        dedup_result = {"unique_sources": sources, "duplicate_groups": [], "duplicate_pairs": []}
        if deduplicate and len(sources) > 1:
            logger.info("Step 2: 检测重复...")
            dedup_result = self.deduplicate(sources, remove_duplicates=True)
        unique_sources = dedup_result["unique_sources"]

        # Step 3: 融合
        logger.info("Step 3: 融合版本...")
        merged_text, merge_info = self.merge_versions(unique_sources, merge_strategy)

        # Step 4: 来源追踪
        logger.info("Step 4: 来源追踪...")
        source_assignments = [
            (merged_text, s.source_name)  # 简化：整篇归因于一个来源
            for s in unique_sources
        ]
        provenance = self.provenance_tracker.create_provenance_map(
            merged_text, source_assignments
        )

        result = {
            "merged_text": merged_text,
            "merge_info": merge_info,
            "unique_source_count": len(unique_sources),
            "total_source_count": len(sources),
            "duplicate_group_count": len(dedup_result.get("duplicate_groups", [])),
            "duplicate_pairs": dedup_result.get("duplicate_pairs", []),
            "provenance": provenance
        }

        logger.info(f"=== 辑佚完成: 使用 {len(unique_sources)} 个来源 ===")

        return result


# 全局单例
_compilation_service: Optional[CompilationService] = None


def get_compilation_service(config: dict = None) -> CompilationService:
    """获取辑佚服务单例"""
    global _compilation_service
    if _compilation_service is None:
        _compilation_service = CompilationService(config)
    return _compilation_service
