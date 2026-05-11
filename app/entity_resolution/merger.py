"""实体合并模块

将相同实体的多个记载进行聚合，支持人物、地点、事件等不同类型实体的合并。
"""

import logging
from typing import List, Dict, Any, Optional
from collections import Counter

# 配置日志
logger = logging.getLogger(__name__)


class EntityMerger:
    """实体合并，将相同实体的多个记载聚合

    支持人物记录、地点记录、事件记录的合并，并处理冲突解决。
    """

    def __init__(self):
        """初始化实体合并器"""
        # 冲突解决策略配置
        self.conflict_resolution = {
            'prefer_earlier_source': True,
            'prefer_more_detail': True,
            'majority_vote': True
        }

        # 字段权重配置（用于判断哪个记录更详细）
        self.detail_weights = {
            'biography': 5,
            'family': 3,
            'events': 3,
            'location': 2,
            'dates': 4,
            'description': 2
        }

        logger.info("EntityMerger 初始化完成")

    def _compute_detail_score(self, record: dict) -> float:
        """计算记录的详细程度得分

        Args:
            record: 记录字典

        Returns:
            float: 详细程度得分
        """
        score = 0.0

        # 检查各字段是否存在及其填充程度
        fields_to_check = ['biography', 'family', 'events', 'location', 'dates', 'description']

        for field in fields_to_check:
            if field in record and record[field]:
                content = record[field]
                if isinstance(content, str):
                    # 按字数计分
                    word_count = len(content)
                    score += min(word_count / 100.0, 1.0) * self.detail_weights.get(field, 1)
                elif isinstance(content, (list, dict)):
                    # 按条目数计分
                    count = len(content)
                    score += min(count / 5.0, 1.0) * self.detail_weights.get(field, 1)

        # 额外字段加成分
        extra_fields = ['sources', 'references', 'notes']
        for field in extra_fields:
            if field in record and record[field]:
                score += 0.5

        return score

    def _resolve_field_conflict(self, field: str, values: List[Any],
                                sources: List[dict]) -> Any:
        """解决字段级别的冲突

        Args:
            field: 字段名
            values: 不同的值列表
            sources: 对应的来源信息列表

        Returns:
            解决冲突后的值
        """
        if not values:
            return None

        if len(values) == 1:
            return values[0]

        # 策略1：多数投票
        if self.conflict_resolution.get('majority_vote'):
            value_counts = Counter(values)
            most_common = value_counts.most_common(1)
            if most_common and most_common[0][1] > 1:
                return most_common[0][0]

        # 策略2：优先选择更详细的记录
        if self.conflict_resolution.get('prefer_more_detail'):
            best_idx = 0
            best_score = 0
            for i, source in enumerate(sources):
                source_detail = source.get('detail_score', 0)
                if source_detail > best_score:
                    best_score = source_detail
                    best_idx = i
            return values[best_idx]

        # 策略3：优先选择较早的来源
        if self.conflict_resolution.get('prefer_earlier_source'):
            best_idx = 0
            best_year = float('inf')
            for i, source in enumerate(sources):
                year = source.get('year', float('inf'))
                if year < best_year:
                    best_year = year
                    best_idx = i
            return values[best_idx]

        # 默认返回第一个
        return values[0]

    def merge_person_records(self, records: List[dict]) -> dict:
        """合并人物记录

        Args:
            records: 人物记录列表，每条记录包含:
                    - name: 姓名
                    - biography: 生平描述
                    - birth_year: 出生年
                    - death_year: 死亡年
                    - family: 家族信息
                    - events: 相关事件
                    - sources: 来源文献
                    - year: 记录年份/年代

        Returns:
            dict: 合并后的人物记录
        """
        if not records:
            return {}

        if len(records) == 1:
            return records[0].copy()

        logger.info(f"开始合并 {len(records)} 条人物记录")

        # 计算每条记录的详细程度
        for record in records:
            record['detail_score'] = self._compute_detail_score(record)

        # 初始化合并结果
        merged = {
            'name': records[0].get('name', ''),
            'type': 'person',
            'sources': [],
            'merged_from': []
        }

        # 收集所有来源
        all_sources = []
        for record in records:
            if 'sources' in record:
                all_sources.extend(record['sources'])
            merged['merged_from'].append(record.get('name', 'unknown'))

        merged['sources'] = all_sources

        # 合并生平
        biographies = []
        for record in records:
            bio = record.get('biography', '')
            if bio:
                biographies.append(bio)

        if biographies:
            merged['biography'] = '\n\n'.join(biographies)

        # 合并时间信息
        birth_years = []
        death_years = []
        for record in records:
            if 'birth_year' in record:
                birth_years.append((record['birth_year'], record))
            if 'death_year' in record:
                death_years.append((record['death_year'], record))

        if birth_years:
            # 选择最早或最常见的出生年
            birth_year_values = [y[0] for y in birth_years]
            birth_year_sources = [y[1] for y in birth_years]
            merged['birth_year'] = self._resolve_field_conflict(
                'birth_year', birth_year_values, birth_year_sources
            )

        if death_years:
            death_year_values = [y[0] for y in death_years]
            death_year_sources = [y[1] for y in death_years]
            merged['death_year'] = self._resolve_field_conflict(
                'death_year', death_year_values, death_year_sources
            )

        # 合并家族信息
        family_members = {}
        for record in records:
            family = record.get('family', {})
            if isinstance(family, dict):
                for relation, person in family.items():
                    if relation not in family_members:
                        family_members[relation] = []
                    if person not in family_members[relation]:
                        family_members[relation].append(person)
            elif isinstance(family, list):
                for member in family:
                    relation = member.get('relation', 'unknown')
                    if relation not in family_members:
                        family_members[relation] = []
                    if member not in family_members[relation]:
                        family_members[relation].append(member)

        if family_members:
            merged['family'] = family_members

        # 合并事件
        all_events = []
        for record in records:
            events = record.get('events', [])
            if isinstance(events, list):
                for event in events:
                    if event not in all_events:
                        all_events.append(event)

        if all_events:
            merged['events'] = all_events

        # 添加合并元信息
        merged['merge_info'] = {
            'record_count': len(records),
            'detail_score': max(r.get('detail_score', 0) for r in records),
            'conflict_resolved': True
        }

        logger.info(f"人物记录合并完成: {merged.get('name', 'unknown')}")

        return merged

    def merge_location_records(self, records: List[dict]) -> dict:
        """合并地点记录

        Args:
            records: 地点记录列表，每条记录包含:
                    - name: 地名
                    - modern_name: 现代名称
                    - historical_names: 历史名称列表
                    - description: 地理描述
                    - coordinates: 坐标
                    - era: 所属时代
                    - sources: 来源文献

        Returns:
            dict: 合并后的地点记录
        """
        if not records:
            return {}

        if len(records) == 1:
            return records[0].copy()

        logger.info(f"开始合并 {len(records)} 条地点记录")

        # 计算每条记录的详细程度
        for record in records:
            record['detail_score'] = self._compute_detail_score(record)

        # 初始化合并结果
        merged = {
            'name': records[0].get('name', ''),
            'type': 'location',
            'sources': [],
            'merged_from': []
        }

        # 收集所有来源
        all_sources = []
        for record in records:
            if 'sources' in record:
                all_sources.extend(record['sources'])
            merged['merged_from'].append(record.get('name', 'unknown'))

        merged['sources'] = all_sources

        # 合并现代名称
        modern_names = []
        for record in records:
            name = record.get('modern_name', '')
            if name and name not in modern_names:
                modern_names.append(name)

        if modern_names:
            merged['modern_name'] = modern_names[0]
            if len(modern_names) > 1:
                merged['alternative_modern_names'] = modern_names[1:]

        # 合并历史名称
        historical_names = []
        for record in records:
            names = record.get('historical_names', [])
            if isinstance(names, list):
                for name in names:
                    if name not in historical_names:
                        historical_names.append(name)

        if historical_names:
            merged['historical_names'] = historical_names

        # 合并描述
        descriptions = []
        for record in records:
            desc = record.get('description', '')
            if desc:
                descriptions.append(desc)

        if descriptions:
            # 按详细程度排序，合并所有描述
            sorted_descs = sorted(
                zip(descriptions, records),
                key=lambda x: x[1].get('detail_score', 0),
                reverse=True
            )
            merged['description'] = '\n\n'.join([d[0] for d in sorted_descs])

        # 合并坐标（优先选择有坐标的记录）
        coordinates = None
        for record in records:
            coord = record.get('coordinates')
            if coord:
                coordinates = coord
                break

        if coordinates:
            merged['coordinates'] = coordinates

        # 合并时代信息
        eras = []
        for record in records:
            era = record.get('era', '')
            if era and era not in eras:
                eras.append(era)

        if eras:
            merged['era'] = eras if len(eras) > 1 else eras[0]

        # 添加合并元信息
        merged['merge_info'] = {
            'record_count': len(records),
            'detail_score': max(r.get('detail_score', 0) for r in records),
            'conflict_resolved': True
        }

        logger.info(f"地点记录合并完成: {merged.get('name', 'unknown')}")

        return merged

    def merge_event_records(self, records: List[dict]) -> dict:
        """合并事件记录

        Args:
            records: 事件记录列表，每条记录包含:
                    - name: 事件名称
                    - date: 事件日期
                    - start_year: 开始年份
                    - end_year: 结束年份
                    - description: 事件描述
                    - participants: 参与者列表
                    - location: 事件地点
                    - sources: 来源文献

        Returns:
            dict: 合并后的事件记录
        """
        if not records:
            return {}

        if len(records) == 1:
            return records[0].copy()

        logger.info(f"开始合并 {len(records)} 条事件记录")

        # 计算每条记录的详细程度
        for record in records:
            record['detail_score'] = self._compute_detail_score(record)

        # 初始化合并结果
        merged = {
            'name': records[0].get('name', ''),
            'type': 'event',
            'sources': [],
            'merged_from': []
        }

        # 收集所有来源
        all_sources = []
        for record in records:
            if 'sources' in record:
                all_sources.extend(record['sources'])
            merged['merged_from'].append(record.get('name', 'unknown'))

        merged['sources'] = all_sources

        # 合并时间信息
        start_years = []
        end_years = []
        dates = []

        for record in records:
            if 'start_year' in record:
                start_years.append(record['start_year'])
            if 'end_year' in record:
                end_years.append(record['end_year'])
            date = record.get('date', '')
            if date and date not in dates:
                dates.append(date)

        if start_years:
            merged['start_year'] = min(start_years)  # 取最早开始

        if end_years:
            merged['end_year'] = max(end_years)  # 取最晚结束

        if dates:
            merged['date'] = dates[0]
            if len(dates) > 1:
                merged['alternative_dates'] = dates[1:]

        # 合并描述
        descriptions = []
        for record in records:
            desc = record.get('description', '')
            if desc:
                descriptions.append(desc)

        if descriptions:
            sorted_descs = sorted(
                zip(descriptions, records),
                key=lambda x: x[1].get('detail_score', 0),
                reverse=True
            )
            merged['description'] = '\n\n'.join([d[0] for d in sorted_descs])

        # 合并参与者
        participants = {}
        for record in records:
            parts = record.get('participants', {})
            if isinstance(parts, dict):
                for role, person_list in parts.items():
                    if role not in participants:
                        participants[role] = []
                    if isinstance(person_list, list):
                        for p in person_list:
                            if p not in participants[role]:
                                participants[role].append(p)
                    elif person_list and person_list not in participants[role]:
                        participants[role].append(person_list)
            elif isinstance(parts, list):
                for p in parts:
                    if p not in participants:
                        participants['participant'] = participants.get('participant', [])
                    if p not in participants['participant']:
                        participants['participant'].append(p)

        if participants:
            merged['participants'] = participants

        # 合并地点
        locations = []
        for record in records:
            loc = record.get('location', '')
            if loc and loc not in locations:
                locations.append(loc)

        if locations:
            merged['location'] = locations[0]
            if len(locations) > 1:
                merged['alternative_locations'] = locations[1:]

        # 添加合并元信息
        merged['merge_info'] = {
            'record_count': len(records),
            'detail_score': max(r.get('detail_score', 0) for r in records),
            'conflict_resolved': True
        }

        logger.info(f"事件记录合并完成: {merged.get('name', 'unknown')}")

        return merged
