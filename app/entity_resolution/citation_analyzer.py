"""引用网络分析模块

用于分析文档间的引用关系，判断内容可信度。
"""

import logging
from typing import List, Dict, Any, Set, Optional
from collections import defaultdict, deque

# 配置日志
logger = logging.getLogger(__name__)


class CitationAnalyzer:
    """引用网络分析，用于判断内容可信度

    构建文档间的引用有向图，计算文档权威度，找出共同来源。
    """

    def __init__(self):
        """初始化引用分析器"""
        # 引用图：doc_id -> set of cited doc_ids
        self.citation_graph: Dict[str, Set[str]] = defaultdict(set)

        # 反向引用图：doc_id -> set of citing doc_ids
        self.reverse_graph: Dict[str, Set[str]] = defaultdict(set)

        # 已处理的文档
        self.documents: Dict[str, dict] = {}

        # 权威度缓存
        self.authority_scores: Dict[str, float] = {}

        # PageRank配置
        self.damping_factor = 0.85
        self.max_iterations = 100
        self.tolerance = 1.0e-6

        logger.info("CitationAnalyzer 初始化完成")

    def build_citation_graph(self, documents: list) -> dict:
        """构建引用图

        Args:
            documents: 文档列表，每个文档包含:
                      - id: 文档唯一标识
                      - references: 该文档引用的其他文档ID列表

        Returns:
            dict: 引用图，格式为 {doc_id: [cited_doc_ids]}
        """
        logger.info(f"开始构建引用图，共 {len(documents)} 个文档")

        # 清空现有数据
        self.citation_graph.clear()
        self.reverse_graph.clear()
        self.documents.clear()
        self.authority_scores.clear()

        # 遍历文档构建图
        for doc in documents:
            doc_id = doc.get('id')
            if not doc_id:
                logger.warning(f"文档缺少ID，跳过: {doc}")
                continue

            # 存储文档信息
            self.documents[doc_id] = doc

            # 获取引用列表
            references = doc.get('references', [])
            if not isinstance(references, list):
                references = [references] if references else []

            # 添加引用边
            for ref_id in references:
                if ref_id != doc_id:  # 避免自引用
                    self.citation_graph[doc_id].add(ref_id)
                    self.reverse_graph[ref_id].add(doc_id)

        logger.info(
            f"引用图构建完成: {len(self.citation_graph)} 个节点，"
            f"{sum(len(v) for v in self.citation_graph.values())} 条边"
        )

        return dict(self.citation_graph)

    def _compute_pagerank(self) -> Dict[str, float]:
        """计算PageRank权威度

        Returns:
            dict: doc_id -> authority score
        """
        if not self.documents:
            return {}

        # 初始化
        n = len(self.documents)
        doc_ids = list(self.documents.keys())

        # 初始PageRank值
        pr = {doc_id: 1.0 / n for doc_id in doc_ids}

        # 创建反向索引
        doc_id_to_idx = {doc_id: i for i, doc_id in enumerate(doc_ids)}

        # 迭代计算
        for iteration in range(self.max_iterations):
            new_pr = {}

            for doc_id in doc_ids:
                # 计算来自所有引用该文档的节点的贡献
                sum_contribution = 0.0

                # 通过反向图获取所有引用该文档的节点
                for citing_doc in self.reverse_graph[doc_id]:
                    out_degree = len(self.citation_graph[citing_doc])
                    if out_degree > 0:
                        sum_contribution += pr[citing_doc] / out_degree

                # PageRank公式
                new_pr[doc_id] = (1 - self.damping_factor) / n + \
                                self.damping_factor * sum_contribution

            # 检查收敛
            diff = sum(abs(new_pr[doc_id] - pr[doc_id]) for doc_id in doc_ids)

            pr = new_pr

            if diff < self.tolerance:
                logger.debug(f"PageRank 在第 {iteration + 1} 次迭代后收敛")
                break

        # 归一化
        max_pr = max(pr.values()) if pr.values() else 1.0
        if max_pr > 0:
            pr = {k: v / max_pr for k, v in pr.items()}

        return pr

    def compute_authority(self, doc_id: str) -> float:
        """计算单个文档的权威度

        Args:
            doc_id: 文档ID

        Returns:
            float: 权威度分数 [0, 1]，1表示最高权威
        """
        if doc_id not in self.documents:
            logger.warning(f"文档 {doc_id} 不存在于引用图中")
            return 0.0

        # 如果缓存存在，直接返回
        if self.authority_scores:
            return self.authority_scores.get(doc_id, 0.0)

        # 计算所有文档的权威度
        self.authority_scores = self._compute_pagerank()

        return self.authority_scores.get(doc_id, 0.0)

    def get_all_authorities(self) -> Dict[str, float]:
        """获取所有文档的权威度

        Returns:
            dict: doc_id -> authority score
        """
        if not self.authority_scores:
            self.authority_scores = self._compute_pagerank()

        return self.authority_scores.copy()

    def find_common_sources(self, doc_ids: List[str]) -> List[dict]:
        """找出多个文档的共同来源

        Args:
            doc_ids: 文档ID列表

        Returns:
            list: 共同来源文档列表，每个元素包含:
                  - doc_id: 文档ID
                  - cited_by: 被这些文档引用的次数
                  - authority: 该来源的权威度
        """
        if not doc_ids:
            return []

        # 过滤存在于图中的文档
        valid_doc_ids = [d for d in doc_ids if d in self.citation_graph]

        if not valid_doc_ids:
            logger.warning(f"提供的文档ID都不在引用图中: {doc_ids}")
            return []

        logger.info(f"查找共同来源: {len(valid_doc_ids)} 个文档")

        # 统计每个文档被引用的次数
        citation_count: Dict[str, int] = defaultdict(int)

        for doc_id in valid_doc_ids:
            # 获取该文档直接引用的文档
            for cited_doc in self.citation_graph[doc_id]:
                citation_count[cited_doc] += 1

        # 找出被所有文档共同引用的来源
        common_sources = []
        min_citations = len(valid_doc_ids)

        # 确保权威度已计算
        if not self.authority_scores:
            self.authority_scores = self._compute_pagerank()

        for cited_doc, count in citation_count.items():
            if count >= min_citations:
                # 计算该来源在共同来源中的相对权威度
                authority = self.authority_scores.get(cited_doc, 0.0)

                common_sources.append({
                    'doc_id': cited_doc,
                    'cited_by': count,
                    'authority': authority,
                    'is_mutual': count == len(valid_doc_ids)
                })

        # 按被引用次数和权威度排序
        common_sources.sort(
            key=lambda x: (x['cited_by'], x['authority']),
            reverse=True
        )

        logger.info(f"找到 {len(common_sources)} 个共同来源")

        return common_sources

    def find_common_sources_breadth(self, doc_ids: List[str], depth: int = 2) -> List[dict]:
        """找出多个文档的共同来源（支持多跳传播）

        Args:
            doc_ids: 文档ID列表
            depth: 传播深度

        Returns:
            list: 共同来源列表
        """
        if not doc_ids:
            return []

        # 过滤存在于图中的文档
        valid_doc_ids = [d for d in doc_ids if d in self.citation_graph]

        if not valid_doc_ids:
            return []

        # BFS扩散收集所有可达文档及其距离
        doc_distances: Dict[str, Dict[str, int]] = defaultdict(dict)

        for start_doc in valid_doc_ids:
            visited = {start_doc: 0}
            queue = deque([(start_doc, 0)])

            while queue:
                current, dist = queue.popleft()

                if dist >= depth:
                    continue

                for neighbor in self.citation_graph[current]:
                    if neighbor not in visited or visited[neighbor] > dist + 1:
                        visited[neighbor] = dist + 1
                        queue.append((neighbor, dist + 1))

            doc_distances[start_doc] = visited

        # 找出被所有文档共同引用的来源（考虑距离）
        source_scores: Dict[str, float] = defaultdict(float)

        for start_doc, distances in doc_distances.items():
            for source_doc, distance in distances.items():
                # 距离越近权重越高
                weight = 1.0 / (distance + 1)
                source_scores[source_doc] += weight

        # 确保权威度已计算
        if not self.authority_scores:
            self.authority_scores = self._compute_pagerank()

        # 归一化得分并排序
        max_score = max(source_scores.values()) if source_scores else 1.0

        results = []
        for source_doc, score in source_scores.items():
            normalized_score = score / max_score if max_score > 0 else 0
            results.append({
                'doc_id': source_doc,
                'score': normalized_score,
                'authority': self.authority_scores.get(source_doc, 0.0)
            })

        results.sort(key=lambda x: (x['score'], x['authority']), reverse=True)

        return results

    def get_citation_chain(self, doc_id: str, max_depth: int = 3) -> List[List[str]]:
        """获取引用链

        Args:
            doc_id: 起始文档ID
            max_depth: 最大深度

        Returns:
            list: 引用链列表，每条链是从起始文档到某个源头文档的路径
        """
        if doc_id not in self.citation_graph:
            return []

        chains = []
        visited = set()

        def dfs(current: str, path: List[str], depth: int):
            if depth > max_depth:
                return

            path.append(current)

            cited = self.citation_graph.get(current, set())

            if not cited:
                # 到达源头
                chains.append(path.copy())
            else:
                for next_doc in cited:
                    if next_doc not in visited or len(path) < len(visited.get(next_doc, [])):
                        visited[next_doc] = path.copy()
                        dfs(next_doc, path, depth + 1)

            path.pop()

        dfs(doc_id, [], 0)

        return chains
