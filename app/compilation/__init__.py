"""
多源辑佚模块 - 古籍多源辑录与融合整理

功能：自动收集同一古籍不同来源的文本，进行去重、排序和融合

主要组件:
- SourceScraper: 多源数据抓取
- TextHasher + Deduplicator: 去重算法
- TextMerger: 多源融合策略
- VersionRanker + ProvenanceTracker: 版本质量排序与溯源
- CompilationService: 服务整合
- EnhancedCompilationService: 集成实体消解的增强辑佚服务
"""

from .scraper import SourceScraper, TextSource, SourceType
from .dedup import TextHasher, Deduplicator
from .merger import TextMerger, MergeStrategy, AlignmentResult
from .ranker import VersionRanker, SourceQuality, ProvenanceTracker
from .compilation_service import CompilationService, get_compilation_service
from .enhanced_compilation_service import (
    EnhancedCompilationService,
    get_enhanced_compilation_service,
    ExtractedEntity
)

__all__ = [
    # 基础组件
    "SourceScraper",
    "TextSource",
    "SourceType",
    "TextHasher",
    "Deduplicator",
    "TextMerger",
    "MergeStrategy",
    "AlignmentResult",
    "VersionRanker",
    "SourceQuality",
    "ProvenanceTracker",
    # 服务
    "CompilationService",
    "get_compilation_service",
    # 增强服务
    "EnhancedCompilationService",
    "get_enhanced_compilation_service",
    "ExtractedEntity",
]
