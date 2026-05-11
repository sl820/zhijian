"""实体消解模块

多源辑佚与实体消解功能，支持实体特征提取、相似度计算、批量消解和聚类。
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# 配置日志
logger = logging.getLogger(__name__)


class EntityResolver:
    """多源辑佚与实体消解

    用于判断多个来源中的实体记录是否指向同一个真实世界实体。
    支持人名、地名、事件等不同类型实体的消解。
    """

    def __init__(self, config: dict = None):
        """初始化实体消解器

        Args:
            config: 配置字典，包含权重和阈值参数
                   - name_weight: 名称相似度权重 (默认 0.3)
                   - time_weight: 时间重叠权重 (默认 0.25)
                   - location_weight: 地域相似度权重 (默认 0.25)
                   - context_weight: 上下文相似度权重 (默认 0.2)
                   - default_threshold: 默认匹配阈值 (默认 0.8)
        """
        self.config = config or {}

        # 特征权重配置
        self.name_weight = self.config.get('name_weight', 0.3)
        self.time_weight = self.config.get('time_weight', 0.25)
        self.location_weight = self.config.get('location_weight', 0.25)
        self.context_weight = self.config.get('context_weight', 0.2)

        # 阈值配置
        self.default_threshold = self.config.get('default_threshold', 0.8)

        # TF-IDF向量化器，用于上下文相似度计算
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=1000,
            min_df=1,
            ngram_range=(1, 2)
        )

        # 已见过的文档上下文，用于TF-IDF训练
        self._trained_corpus: List[str] = []

        logger.info(
            f"EntityResolver 初始化完成 - "
            f"权重: name={self.name_weight}, time={self.time_weight}, "
            f"location={self.location_weight}, context={self.context_weight}"
        )

    def extract_entity_features(self, entity: dict) -> np.ndarray:
        """提取实体特征向量

        Args:
            entity: 实体字典，包含以下字段:
                    - name: 实体名称
                    - time: 时间信息 (start_year, end_year)
                    - location: 地理位置
                    - context: 上下文描述文本

        Returns:
            np.ndarray: 特征向量 [name_sim, time_overlap, location_sim, context_sim]
        """
        features = np.zeros(4)

        # 1. 名称相似度特征 (使用编辑距离归一化)
        name = entity.get('name', '')
        if name:
            # 名称长度作为特征之一
            features[0] = min(len(name) / 20.0, 1.0)  # 归一化到 [0, 1]

        # 2. 时间重叠特征
        time_info = entity.get('time', {})
        if time_info:
            start = time_info.get('start_year')
            end = time_info.get('end_year')
            if start is not None and end is not None:
                # 时间跨度作为特征
                duration = end - start if end >= start else 0
                features[1] = min(duration / 100.0, 1.0)

        # 3. 地域相似度特征
        location = entity.get('location', '')
        if location:
            # 地理位置长度/复杂度作为特征
            features[2] = min(len(location) / 50.0, 1.0)

        # 4. 上下文相似度特征
        context = entity.get('context', '')
        if context:
            # 上下文长度作为特征
            words = len(context.split())
            features[3] = min(words / 100.0, 1.0)

        return features

    def _edit_distance(self, str1: str, str2: str) -> int:
        """计算两个字符串的编辑距离

        Args:
            str1: 第一个字符串
            str2: 第二个字符串

        Returns:
            int: 编辑距离
        """
        if len(str1) < len(str2):
            return self._edit_distance(str2, str1)

        if len(str2) == 0:
            return len(str1)

        previous_row = range(len(str2) + 1)
        for i, c1 in enumerate(str1):
            current_row = [i + 1]
            for j, c2 in enumerate(str2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def _compute_name_similarity(self, name_a: str, name_b: str) -> float:
        """计算名称相似度（基于编辑距离）

        Args:
            name_a: 第一个名称
            name_b: 第二个名称

        Returns:
            float: 相似度分数 [0, 1]，1表示完全相同
        """
        if not name_a or not name_b:
            return 0.0

        # 计算编辑距离
        max_len = max(len(name_a), len(name_b))
        if max_len == 0:
            return 1.0

        distance = self._edit_distance(name_a.lower(), name_b.lower())
        similarity = 1.0 - (distance / max_len)

        return max(0.0, min(1.0, similarity))

    def _compute_time_overlap(self, time_a: dict, time_b: dict) -> float:
        """计算时间重叠程度

        Args:
            time_a: 第一个实体的时间信息 {'start_year': int, 'end_year': int}
            time_b: 第二个实体的时间信息

        Returns:
            float: 重叠分数 [0, 1]，1表示完全重叠
        """
        if not time_a or not time_b:
            return 0.0

        start_a = time_a.get('start_year')
        end_a = time_a.get('end_year')
        start_b = time_b.get('start_year')
        end_b = time_b.get('end_year')

        if None in [start_a, end_a, start_b, end_b]:
            return 0.0

        # 计算重叠区间
        overlap_start = max(start_a, start_b)
        overlap_end = min(end_a, end_b)

        if overlap_start > overlap_end:
            return 0.0

        overlap_duration = overlap_end - overlap_start + 1
        union_duration = max(end_a, end_b) - min(start_a, start_b) + 1

        if union_duration == 0:
            return 1.0

        return overlap_duration / union_duration

    def _compute_location_similarity(self, loc_a: str, loc_b: str) -> float:
        """计算地域相似度

        Args:
            loc_a: 第一个地理位置描述
            loc_b: 第二个地理位置描述

        Returns:
            float: 相似度分数 [0, 1]
        """
        if not loc_a or not loc_b:
            return 0.0

        # 简单的词汇重叠计算
        words_a = set(loc_a.lower().split())
        words_b = set(loc_b.lower().split())

        if not words_a or not words_b:
            return 0.0

        intersection = len(words_a & words_b)
        union = len(words_a | words_b)

        if union == 0:
            return 0.0

        # 考虑词根相似性（简单的包含检查）
        for word_a in words_a:
            for word_b in words_b:
                if word_a in word_b or word_b in word_a:
                    intersection += 0.5

        return min(1.0, intersection / max(len(words_a), len(words_b)))

    def _compute_context_similarity(self, context_a: str, context_b: str) -> float:
        """计算上下文相似度（基于TF-IDF）

        Args:
            context_a: 第一个实体的上下文描述
            context_b: 第二个实体的上下文描述

        Returns:
            float: 相似度分数 [0, 1]
        """
        if not context_a or not context_b:
            return 0.0

        # 更新语料库并训练向量化器
        corpus = [context_a, context_b]
        try:
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(corpus)
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return float(similarity)
        except Exception as e:
            logger.warning(f"TF-IDF相似度计算失败: {e}")
            # 回退到简单的词重叠
            words_a = set(context_a.split())
            words_b = set(context_b.split())
            if not words_a or not words_b:
                return 0.0
            intersection = len(words_a & words_b)
            union = len(words_a | words_b)
            return intersection / union if union > 0 else 0.0

    def compute_similarity(self, entity_a: dict, entity_b: dict) -> float:
        """计算两个实体之间的综合相似度

        Args:
            entity_a: 第一个实体字典
            entity_b: 第二个实体字典

        Returns:
            float: 综合相似度分数 [0, 1]
        """
        # 计算各维度相似度
        name_sim = self._compute_name_similarity(
            entity_a.get('name', ''),
            entity_b.get('name', '')
        )

        time_sim = self._compute_time_overlap(
            entity_a.get('time', {}),
            entity_b.get('time', {})
        )

        location_sim = self._compute_location_similarity(
            entity_a.get('location', ''),
            entity_b.get('location', '')
        )

        context_sim = self._compute_context_similarity(
            entity_a.get('context', ''),
            entity_b.get('context', '')
        )

        # 加权组合
        total_similarity = (
            name_sim * self.name_weight +
            time_sim * self.time_weight +
            location_sim * self.location_weight +
            context_sim * self.context_weight
        )

        logger.debug(
            f"相似度计算: name={name_sim:.3f}, time={time_sim:.3f}, "
            f"location={location_sim:.3f}, context={context_sim:.3f}, "
            f"total={total_similarity:.3f}"
        )

        return total_similarity

    def resolve_entity_pair(self, entity_a: dict, entity_b: dict) -> dict:
        """判断两个实体是否为同一实体

        Args:
            entity_a: 第一个实体字典
            entity_b: 第二个实体字典

        Returns:
            dict: 包含:
                  - is_same: bool，是否为同一实体
                  - confidence: float，置信度 [0, 1]
                  - reasons: list，匹配原因列表
        """
        similarity = self.compute_similarity(entity_a, entity_b)

        # 计算各维度相似度用于原因说明
        name_sim = self._compute_name_similarity(
            entity_a.get('name', ''),
            entity_b.get('name', '')
        )
        time_sim = self._compute_time_overlap(
            entity_a.get('time', {}),
            entity_b.get('time', {})
        )
        location_sim = self._compute_location_similarity(
            entity_a.get('location', ''),
            entity_b.get('location', '')
        )
        context_sim = self._compute_context_similarity(
            entity_a.get('context', ''),
            entity_b.get('context', '')
        )

        # 生成匹配原因
        reasons = []
        if name_sim > 0.8:
            reasons.append(f"名称高度相似 (编辑距离相似度: {name_sim:.2f})")
        if time_sim > 0.5:
            reasons.append(f"时间重叠 (重叠度: {time_sim:.2f})")
        if location_sim > 0.5:
            reasons.append(f"地域相近 (相似度: {location_sim:.2f})")
        if context_sim > 0.3:
            reasons.append(f"上下文相关 (相似度: {context_sim:.2f})")

        # 判断是否为同一实体
        threshold = self.config.get('match_threshold', self.default_threshold)
        is_same = similarity >= threshold

        result = {
            'is_same': is_same,
            'confidence': similarity,
            'reasons': reasons
        }

        logger.info(
            f"实体对消解结果: {entity_a.get('name', '?')} <-> {entity_b.get('name', '?')} "
            f"=> {'同一实体' if is_same else '不同实体'} (置信度: {similarity:.3f})"
        )

        return result

    def batch_resolve(self, entities: list, threshold: float = 0.8) -> list:
        """批量消解实体对

        Args:
            entities: 实体列表
            threshold: 匹配阈值，默认 0.8

        Returns:
            list: 消解结果列表，每个元素包含:
                  - entity_a: 第一个实体
                  - entity_b: 第二个实体
                  - is_same: bool
                  - confidence: float
                  - reasons: list
        """
        results = []
        n = len(entities)

        logger.info(f"开始批量消解 {n} 个实体，阈值: {threshold}")

        for i in range(n):
            for j in range(i + 1, n):
                entity_a = entities[i]
                entity_b = entities[j]

                # 快速过滤：名称差异过大直接跳过
                name_sim = self._compute_name_similarity(
                    entity_a.get('name', ''),
                    entity_b.get('name', '')
                )

                if name_sim < threshold * 0.5:
                    # 名称差异太大，跳过
                    continue

                result = self.resolve_entity_pair(entity_a, entity_b)

                # 只返回超过阈值的结果
                if result['confidence'] >= threshold:
                    results.append({
                        'entity_a': entity_a,
                        'entity_b': entity_b,
                        **result
                    })

        logger.info(f"批量消解完成，发现 {len(results)} 对匹配实体")

        return results

    def cluster_entities(self, entities: list) -> list:
        """使用并查集将实体聚类

        Args:
            entities: 实体列表

        Returns:
            list: 聚类结果，每个聚类包含一组指向同一真实实体的实体
        """
        n = len(entities)
        if n == 0:
            return []

        # 初始化并查集
        parent = list(range(n))
        rank = [0] * n

        def find(x: int) -> int:
            """路径压缩查找"""
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x: int, y: int):
            """按秩合并"""
            px, py = find(x), find(y)
            if px == py:
                return
            if rank[px] < rank[py]:
                px, py = py, px
            parent[py] = px
            if rank[px] == rank[py]:
                rank[px] += 1

        # 执行批量消解
        matches = self.batch_resolve(entities)

        # 根据匹配结果合并集合
        entity_to_idx = {id(entities[i]): i for i in range(n)}

        for match in matches:
            if match['is_same']:
                idx_a = entity_to_idx.get(id(match['entity_a']))
                idx_b = entity_to_idx.get(id(match['entity_b']))
                if idx_a is not None and idx_b is not None:
                    union(idx_a, idx_b)

        # 收集聚类结果
        clusters = {}
        for i in range(n):
            root = find(i)
            if root not in clusters:
                clusters[root] = []
            clusters[root].append(entities[i])

        result = list(clusters.values())

        logger.info(f"实体聚类完成，共 {len(result)} 个聚类")

        return result
