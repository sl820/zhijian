"""实体解析模块

提供多源辑佚与实体消解、引用网络分析、实体合并等功能。
"""

from .resolver import EntityResolver
from .citation_analyzer import CitationAnalyzer
from .merger import EntityMerger

__all__ = [
    'EntityResolver',
    'CitationAnalyzer',
    'EntityMerger',
]
