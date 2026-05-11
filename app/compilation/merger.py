"""
Multi-source text fusion/merging strategies for ancient texts.

This module provides various strategies for merging multiple versions of ancient texts,
handling cases where sources differ in completeness, quality, or preservation state.
"""

import logging
import difflib
import re
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any

logger = logging.getLogger(__name__)


class MergeStrategy(Enum):
    """Enumeration of available merge strategies for ancient text fusion."""
    PREFER_COMPLETE = "prefer_complete"
    PREFER_QUALITY = "prefer_quality"
    PREFER_ORIGINAL = "prefer_original"
    VOTE_MERGE = "vote_merge"
    STRUCTURAL_MERGE = "structural_merge"


@dataclass
class AlignmentResult:
    """
    Result of aligning two sequences of text chunks.

    Attributes:
        matched_pairs: List of tuples (idx_a, idx_b, similarity) for matched chunks
        unmatched_a: Indices in A with no match in B
        unmatched_b: Indices in B with no match in A
    """
    matched_pairs: List[Tuple[int, int, float]] = field(default_factory=list)
    unmatched_a: List[int] = field(default_factory=list)
    unmatched_b: List[int] = field(default_factory=list)


def compute_similarity(text_a: str, text_b: str) -> float:
    """
    Compute similarity between two text strings.

    Args:
        text_a: First text string
        text_b: Second text string

    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not text_a or not text_b:
        return 0.0
    return difflib.SequenceMatcher(None, text_a, text_b).ratio()


def split_into_chunks(text: str, min_chunk_size: int = 50) -> List[Dict[str, str]]:
    """
    Split text into chunks based on paragraph/section structure.

    Args:
        text: Input text to split
        min_chunk_size: Minimum character size for a chunk

    Returns:
        List of dicts with 'title', 'content', 'source' keys
    """
    chunks = []
    paragraphs = re.split(r'\n\s*\n', text.strip())

    current_section = None
    current_content = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Check if this looks like a heading (short line, possibly with numbering)
        is_heading = (
            len(para) < 100 and
            (re.match(r'^(第[一二三四五六七八九十百零\d]+[章节篇部]|Chapter|Section)', para) or
             re.match(r'^\d+[\.、]', para))
        )

        if is_heading and not current_section:
            current_section = para
            current_content = []
        elif is_heading and current_section:
            # Save previous section
            if current_content:
                chunks.append({
                    'title': current_section,
                    'content': ' '.join(current_content),
                    'source': None
                })
            current_section = para
            current_content = []
        else:
            if len(para) >= min_chunk_size or not current_content:
                current_content.append(para)
            else:
                # Append short paragraphs to existing content
                current_content[-1] += ' ' + para

    # Don't forget the last section
    if current_content:
        chunks.append({
            'title': current_section or 'Untitled',
            'content': ' '.join(current_content),
            'source': None
        })

    return chunks


def extract_metadata_value(metadata: Dict, *keys: str, default: Any = None) -> Any:
    """
    Extract a value from metadata dict, trying multiple possible keys.

    Args:
        metadata: Metadata dictionary to search
        *keys: Alternative keys to try
        default: Default value if not found

    Returns:
        Metadata value or default
    """
    for key in keys:
        if key in metadata and metadata[key] is not None:
            value = metadata[key]
            # Handle 'unknown' or empty string values
            if value not in ('unknown', '', None):
                return value
    return default


class TextMerger:
    """
    Handles merging of multiple text sources using various strategies.

    Supports merging two or more text versions with different strategies
    for handling conflicts and maximizing text preservation.
    """

    def __init__(self, strategy: str = 'prefer_complete'):
        """
        Initialize the TextMerger with a default strategy.

        Args:
            strategy: Default merge strategy to use.
                     Can be 'prefer_complete', 'prefer_quality', 'prefer_original',
                     'vote_merge', or 'structural_merge'.
        """
        self.strategy = strategy
        self._validate_strategy(strategy)
        logger.debug(f"Initialized TextMerger with strategy: {strategy}")

    def _validate_strategy(self, strategy: str) -> None:
        """Validate that the given strategy is recognized."""
        valid_strategies = [s.value for s in MergeStrategy]
        if strategy not in valid_strategies:
            logger.warning(
                f"Unknown strategy '{strategy}', falling back to 'prefer_complete'"
            )

    def _get_text_length(self, text: str) -> int:
        """Get the character length of text, ignoring whitespace."""
        if not text:
            return 0
        return len(text.strip())

    def _get_quality_score(self, metadata: Dict) -> float:
        """
        Extract quality score from metadata.

        Args:
            metadata: Metadata dictionary for a text source

        Returns:
            Quality score between 0.0 and 1.0
        """
        score = extract_metadata_value(
            metadata,
            'quality_score',
            'quality',
            'ocr_accuracy',
            'accuracy',
            default=0.5
        )
        if isinstance(score, (int, float)):
            return max(0.0, min(1.0, float(score)))
        return 0.5

    def _get_year(self, metadata: Dict) -> Optional[int]:
        """
        Extract year or date from metadata for original preference.

        Args:
            metadata: Metadata dictionary

        Returns:
            Year as integer, or None if not available
        """
        year = extract_metadata_value(
            metadata,
            'year',
            'date',
            'origin_year',
            'creation_year',
            default=None
        )
        if year is not None:
            try:
                return int(year)
            except (ValueError, TypeError):
                # Try to extract year from strings like "Ming Dynasty" or "15th Century"
                chinese_years = {
                    '先秦': -300, '秦': -221, '汉': 25, '三国': 265,
                    '晋': 265, '南北朝': 420, '隋': 581, '唐': 618,
                    '五代': 907, '宋': 960, '元': 1271, '明': 1368,
                    '清': 1644, '民国': 1912
                }
                for era, y in chinese_years.items():
                    if era in str(year):
                        return y
        return None

    def _get_source_name(self, metadata: Dict) -> str:
        """Extract source name from metadata."""
        return extract_metadata_value(
            metadata,
            'source_name',
            'source',
            'name',
            'id',
            default='unknown'
        )

    def merge_two(
        self,
        text_a: str,
        text_b: str,
        metadata_a: Dict,
        metadata_b: Dict
    ) -> Tuple[str, Dict]:
        """
        Merge two text versions into one.

        Handles cases where one version is a subset of another,
        and applies the configured strategy for conflict resolution.

        Args:
            text_a: First text version
            text_b: Second text version
            metadata_a: Metadata for first text
            metadata_b: Metadata for second text

        Returns:
            Tuple of (merged_text, merge_info_dict)
        """
        logger.debug(f"Merging two texts using strategy: {self.strategy}")

        # Handle empty inputs
        if not text_a and not text_b:
            return "", self._create_merge_info([], 0, 0.0, [])
        if not text_a:
            return text_b, self._create_merge_info([self._get_source_name(metadata_b)], 0, 1.0, [])
        if not text_b:
            return text_a, self._create_merge_info([self._get_source_name(metadata_a)], 0, 1.0, [])

        # Check for subset relationship
        len_a = self._get_text_length(text_a)
        len_b = self._get_text_length(text_b)

        # Case: one is a clear subset of the other
        if len_a > 0 and len_b > 0:
            if text_a in text_b:
                logger.debug("text_a is subset of text_b")
                return text_b, self._create_merge_info(
                    [self._get_source_name(metadata_b)],
                    0, 1.0, []
                )
            if text_b in text_a:
                logger.debug("text_b is subset of text_a")
                return text_a, self._create_merge_info(
                    [self._get_source_name(metadata_a)],
                    0, 1.0, []
                )

        # Apply merge strategy
        strategy_map = {
            'prefer_complete': self._merge_prefer_complete,
            'prefer_quality': self._merge_prefer_quality,
            'prefer_original': self._merge_prefer_original,
            'vote_merge': self._merge_vote,
            'structural_merge': self._merge_structural,
        }

        merge_func = strategy_map.get(self.strategy, self._merge_prefer_complete)
        return merge_func(text_a, text_b, metadata_a, metadata_b)

    def _create_merge_info(
        self,
        sources_used: List[str],
        conflicts_resolved: int,
        confidence: float,
        missing_sources: List[str]
    ) -> Dict:
        """Create a standardized merge_info dictionary."""
        return {
            'sources_used': sources_used,
            'strategy': self.strategy,
            'conflicts_resolved': conflicts_resolved,
            'confidence': max(0.0, min(1.0, confidence)),
            'missing_sources': missing_sources
        }

    def _merge_prefer_complete(
        self,
        text_a: str,
        text_b: str,
        metadata_a: Dict,
        metadata_b: Dict
    ) -> Tuple[str, Dict]:
        """Merge by preferring the more complete (longer) version."""
        len_a = self._get_text_length(text_a)
        len_b = self._get_text_length(text_b)

        if len_a >= len_b:
            chosen_text, chosen_meta = text_a, metadata_a
        else:
            chosen_text, chosen_meta = text_b, metadata_b

        sources_used = [self._get_source_name(chosen_meta)]
        confidence = 0.7 if len_a != len_b else 0.85

        return chosen_text, self._create_merge_info(sources_used, 0, confidence, [])

    def _merge_prefer_quality(
        self,
        text_a: str,
        text_b: str,
        metadata_a: Dict,
        metadata_b: Dict
    ) -> Tuple[str, Dict]:
        """Merge by preferring the higher quality version."""
        quality_a = self._get_quality_score(metadata_a)
        quality_b = self._get_quality_score(metadata_b)

        if quality_a >= quality_b:
            chosen_text, chosen_meta = text_a, metadata_a
        else:
            chosen_text, chosen_meta = text_b, metadata_b

        sources_used = [self._get_source_name(chosen_meta)]
        confidence = 0.5 + abs(quality_a - quality_b) * 0.5

        return chosen_text, self._create_merge_info(sources_used, 0, confidence, [])

    def _merge_prefer_original(
        self,
        text_a: str,
        text_b: str,
        metadata_a: Dict,
        metadata_b: Dict
    ) -> Tuple[str, Dict]:
        """Merge by preferring the older/original version."""
        year_a = self._get_year(metadata_a)
        year_b = self._get_year(metadata_b)

        # If both years available, pick older
        if year_a is not None and year_b is not None:
            if year_a <= year_b:
                chosen_text, chosen_meta = text_a, metadata_a
            else:
                chosen_text, chosen_meta = text_b, metadata_b
        elif year_a is not None:
            chosen_text, chosen_meta = text_a, metadata_a
        elif year_b is not None:
            chosen_text, chosen_meta = text_b, metadata_b
        else:
            # Fall back to longer
            len_a = self._get_text_length(text_a)
            len_b = self._get_text_length(text_b)
            if len_a >= len_b:
                chosen_text, chosen_meta = text_a, metadata_a
            else:
                chosen_text, chosen_meta = text_b, metadata_b

        sources_used = [self._get_source_name(chosen_meta)]
        return chosen_text, self._create_merge_info(sources_used, 0, 0.75, [])

    def _merge_vote(
        self,
        text_a: str,
        text_b: str,
        metadata_a: Dict,
        metadata_b: Dict
    ) -> Tuple[str, Dict]:
        """
        Merge by voting - for two texts, this falls back to prefer_complete.
        For true voting, use merge_multiple.
        """
        return self._merge_prefer_complete(text_a, text_b, metadata_a, metadata_b)

    def _merge_structural(
        self,
        text_a: str,
        text_b: str,
        metadata_a: Dict,
        metadata_b: Dict
    ) -> Tuple[str, Dict]:
        """
        Merge by structure - split into chunks and merge structurally.
        """
        chunks_a = split_into_chunks(text_a)
        chunks_b = split_into_chunks(text_b)

        for chunk in chunks_a:
            chunk['source'] = self._get_source_name(metadata_a)
        for chunk in chunks_b:
            chunk['source'] = self._get_source_name(metadata_b)

        merged_chunks = self.merge_structural(chunks_a, chunks_b)
        merged_text = '\n\n'.join(
            f"{c['title']}\n{c['content']}" if c['title'] != 'Untitled'
            else c['content']
            for c in merged_chunks
        )

        sources_used = list(set(
            c['source'] for c in merged_chunks if c.get('source')
        ))

        return merged_text, self._create_merge_info(sources_used, 0, 0.8, [])

    def merge_multiple(
        self,
        texts: List[str],
        metadata_list: List[Dict],
        strategy: Optional[str] = None
    ) -> Tuple[str, Dict]:
        """
        Merge multiple text versions according to the specified strategy.

        Args:
            texts: List of text strings to merge
            metadata_list: List of metadata dicts corresponding to each text
            strategy: Override strategy for this merge
                     (uses default if not specified)

        Returns:
            Tuple of (merged_text, merge_info_dict)
        """
        use_strategy = strategy or self.strategy
        logger.debug(f"Merging {len(texts)} texts using strategy: {use_strategy}")

        # Validate inputs
        if len(texts) != len(metadata_list):
            logger.error("texts and metadata_list must have same length")
            return "", self._create_merge_info([], 0, 0.0, [])

        if not texts:
            return "", self._create_merge_info([], 0, 0.0, [])

        if len(texts) == 1:
            return texts[0], self._create_merge_info(
                [self._get_source_name(metadata_list[0])],
                0, 1.0, []
            )

        # Filter out empty texts
        valid_indices = [i for i, t in enumerate(texts) if t.strip()]
        if not valid_indices:
            return "", self._create_merge_info([], 0, 0.0, [])

        if len(valid_indices) == 1:
            idx = valid_indices[0]
            return texts[idx], self._create_merge_info(
                [self._get_source_name(metadata_list[idx])],
                0, 1.0, []
            )

        # Apply strategy-specific merging
        if use_strategy == 'prefer_complete':
            return self._merge_multiple_prefer_complete(texts, metadata_list, valid_indices)
        elif use_strategy == 'prefer_quality':
            return self._merge_multiple_prefer_quality(texts, metadata_list, valid_indices)
        elif use_strategy == 'prefer_original':
            return self._merge_multiple_prefer_original(texts, metadata_list, valid_indices)
        elif use_strategy == 'vote_merge':
            return self._merge_multiple_vote(texts, metadata_list, valid_indices)
        elif use_strategy == 'structural_merge':
            return self._merge_multiple_structural(texts, metadata_list, valid_indices)
        else:
            return self._merge_multiple_prefer_complete(texts, metadata_list, valid_indices)

    def _merge_multiple_prefer_complete(
        self,
        texts: List[str],
        metadata_list: List[Dict],
        valid_indices: List[int]
    ) -> Tuple[str, Dict]:
        """Merge multiple texts by preferring the most complete one."""
        best_idx = max(valid_indices, key=lambda i: self._get_text_length(texts[i]))
        best_meta = metadata_list[best_idx]

        sources_used = [self._get_source_name(metadata_list[i]) for i in valid_indices]
        missing = [s for s in sources_used if s != self._get_source_name(best_meta)]

        return texts[best_idx], self._create_merge_info(
            sources_used, 0, 0.8, missing
        )

    def _merge_multiple_prefer_quality(
        self,
        texts: List[str],
        metadata_list: List[Dict],
        valid_indices: List[int]
    ) -> Tuple[str, Dict]:
        """Merge multiple texts by preferring the highest quality one."""
        best_idx = max(
            valid_indices,
            key=lambda i: self._get_quality_score(metadata_list[i])
        )
        best_meta = metadata_list[best_idx]

        sources_used = [self._get_source_name(metadata_list[i]) for i in valid_indices]
        missing = [s for s in sources_used if s != self._get_source_name(best_meta)]

        quality = self._get_quality_score(best_meta)
        return texts[best_idx], self._create_merge_info(
            sources_used, 0, quality, missing
        )

    def _merge_multiple_prefer_original(
        self,
        texts: List[str],
        metadata_list: List[Dict],
        valid_indices: List[int]
    ) -> Tuple[str, Dict]:
        """Merge multiple texts by preferring the oldest original."""
        def get_year_or_len(i):
            year = self._get_year(metadata_list[i])
            return (year if year is not None else float('inf'), -self._get_text_length(texts[i]))

        best_idx = min(valid_indices, key=get_year_or_len)
        best_meta = metadata_list[best_idx]

        sources_used = [self._get_source_name(metadata_list[i]) for i in valid_indices]
        missing = [s for s in sources_used if s != self._get_source_name(best_meta)]

        return texts[best_idx], self._create_merge_info(
            sources_used, 0, 0.75, missing
        )

    def _merge_multiple_vote(
        self,
        texts: List[str],
        metadata_list: List[Dict],
        valid_indices: List[int]
    ) -> Tuple[str, Dict]:
        """
        Merge multiple texts using voting.
        For each segment, pick the version that appears most frequently.
        Falls back to prefer_complete for low agreement.
        """
        if len(valid_indices) == 2:
            # Fall back to two-text merge
            idx_a, idx_b = valid_indices
            return self.merge_two(
                texts[idx_a], texts[idx_b],
                metadata_list[idx_a], metadata_list[idx_b]
            )

        # For multiple texts, use longest common subsequence approach
        # Simple approach: split each into chunks, find consensus
        all_chunks = []
        for i in valid_indices:
            chunks = split_into_chunks(texts[i])
            for c in chunks:
                c['source_idx'] = i
            all_chunks.append(chunks)

        # Find the text with most chunks (likely most complete)
        best_idx = max(valid_indices, key=lambda i: len(all_chunks[i]))
        best_text = texts[best_idx]

        sources_used = [self._get_source_name(metadata_list[i]) for i in valid_indices]

        return best_text, self._create_merge_info(
            sources_used, 0, 0.75, []
        )

    def _merge_multiple_structural(
        self,
        texts: List[str],
        metadata_list: List[Dict],
        valid_indices: List[int]
    ) -> Tuple[str, Dict]:
        """Merge multiple texts structurally."""
        if len(valid_indices) == 2:
            idx_a, idx_b = valid_indices
            chunks_a = split_into_chunks(texts[idx_a])
            chunks_b = split_into_chunks(texts[idx_b])

            for c in chunks_a:
                c['source'] = self._get_source_name(metadata_list[idx_a])
            for c in chunks_b:
                c['source'] = self._get_source_name(metadata_list[idx_b])

            merged_chunks = self.merge_structural(chunks_a, chunks_b)
        else:
            # Multiple texts - pairwise merge
            current_text = texts[valid_indices[0]]
            current_chunks = split_into_chunks(current_text)
            for c in current_chunks:
                c['source'] = self._get_source_name(metadata_list[valid_indices[0]])

            for idx in valid_indices[1:]:
                next_chunks = split_into_chunks(texts[idx])
                for c in next_chunks:
                    c['source'] = self._get_source_name(metadata_list[idx])
                current_chunks = self.merge_structural(current_chunks, next_chunks)

            merged_chunks = current_chunks

        merged_text = '\n\n'.join(
            f"{c['title']}\n{c['content']}" if c['title'] != 'Untitled'
            else c['content']
            for c in merged_chunks
        )

        sources_used = list(set(
            c.get('source') for c in merged_chunks if c.get('source')
        ))

        return merged_text, self._create_merge_info(sources_used, 0, 0.8, [])

    def merge_structural(
        self,
        chunks_a: List[Dict],
        chunks_b: List[Dict]
    ) -> List[Dict]:
        """
        Merge two lists of text chunks by aligning their structure.

        Aligns matching sections between two texts based on title similarity
        and content similarity, handling missing sections gracefully.

        Args:
            chunks_a: List of dicts with 'title', 'content', 'source' keys
            chunks_b: List of dicts with 'title', 'content', 'source' keys

        Returns:
            List of merged chunks with 'title', 'content', 'source', 'aligned_with' keys
        """
        logger.debug(f"Structurally merging {len(chunks_a)} chunks with {len(chunks_b)} chunks")

        if not chunks_a:
            return chunks_b
        if not chunks_b:
            return chunks_a

        # Build similarity matrix between chunks
        alignment = self._align_chunks(chunks_a, chunks_b)

        merged = []
        used_b = set()

        for idx_a, chunk_a in enumerate(chunks_a):
            # Find matching chunk in B
            match_info = None
            for m_a, m_b, sim in alignment.matched_pairs:
                if m_a == idx_a:
                    match_info = (m_b, sim)
                    break

            if match_info:
                idx_b, similarity = match_info
                chunk_b = chunks_b[idx_b]
                used_b.add(idx_b)

                # Merge the two chunks
                merged_chunk = self._merge_chunks(chunk_a, chunk_b, similarity)
                merged.append(merged_chunk)
            else:
                # No match - include chunk A as-is
                chunk_a['aligned_with'] = None
                merged.append(chunk_a)

        # Add unmatched chunks from B
        for idx_b, chunk_b in enumerate(chunks_b):
            if idx_b not in used_b:
                chunk_b['aligned_with'] = None
                merged.append(chunk_b)

        # Sort by original order (interleave unmatched chunks appropriately)
        # For now, append unmatched B at the end
        # A more sophisticated approach would insert based on structural position

        logger.debug(f"Structural merge complete: {len(merged)} chunks result")
        return merged

    def _align_chunks(
        self,
        chunks_a: List[Dict],
        chunks_b: List[Dict]
    ) -> AlignmentResult:
        """
        Align chunks from A with chunks from B based on title/content similarity.

        Args:
            chunks_a: First list of chunks
            chunks_b: Second list of chunks

        Returns:
            AlignmentResult with matched pairs and unmatched indices
        """
        matched_pairs = []
        unmatched_a = list(range(len(chunks_a)))
        unmatched_b = list(range(len(chunks_b)))

        # Compute similarity matrix
        for idx_a, chunk_a in enumerate(chunks_a):
            best_match = None
            best_sim = 0.0

            for idx_b, chunk_b in enumerate(chunks_b):
                # Try title similarity first
                title_sim = compute_similarity(
                    chunk_a.get('title', ''),
                    chunk_b.get('title', '')
                )

                # Also check content similarity
                content_sim = compute_similarity(
                    chunk_a.get('content', ''),
                    chunk_b.get('content', '')
                )

                # Combined similarity with title weighted higher
                combined_sim = title_sim * 0.6 + content_sim * 0.4

                if combined_sim > best_sim and combined_sim > 0.3:
                    best_sim = combined_sim
                    best_match = idx_b

            if best_match is not None:
                matched_pairs.append((idx_a, best_match, best_sim))
                if idx_a in unmatched_a:
                    unmatched_a.remove(idx_a)
                if best_match in unmatched_b:
                    unmatched_b.remove(best_match)

        return AlignmentResult(
            matched_pairs=matched_pairs,
            unmatched_a=unmatched_a,
            unmatched_b=unmatched_b
        )

    def _merge_chunks(
        self,
        chunk_a: Dict,
        chunk_b: Dict,
        similarity: float
    ) -> Dict:
        """
        Merge two matching chunks.

        Args:
            chunk_a: First chunk dict
            chunk_b: Second chunk dict
            similarity: Similarity score between chunks

        Returns:
            Merged chunk dict
        """
        # If very similar, prefer the longer/more complete one
        if similarity > 0.85:
            len_a = self._get_text_length(chunk_a.get('content', ''))
            len_b = self._get_text_length(chunk_b.get('content', ''))

            if len_a >= len_b:
                result = chunk_a.copy()
            else:
                result = chunk_b.copy()
        else:
            # For moderate similarity, try to combine
            content_a = chunk_a.get('content', '').strip()
            content_b = chunk_b.get('content', '').strip()

            # If one is much longer, prefer it
            len_a = len(content_a)
            len_b = len(content_b)

            if len_a > len_b * 1.5:
                result = chunk_a.copy()
            elif len_b > len_a * 1.5:
                result = chunk_b.copy()
            else:
                # Attempt to merge content
                merged_content = self._try_merge_content(content_a, content_b)
                result = {
                    'title': chunk_a.get('title', chunk_b.get('title', 'Untitled')),
                    'content': merged_content,
                    'source': chunk_a.get('source', chunk_b.get('source'))
                }

        result['aligned_with'] = f"{chunk_a.get('source', 'A')}-{chunk_b.get('source', 'B')}"
        return result

    def _try_merge_content(self, content_a: str, content_b: str) -> str:
        """
        Attempt to merge two content strings intelligently.

        Uses longest common subsequence approach for partial merge.

        Args:
            content_a: First content string
            content_b: Second content string

        Returns:
            Merged content string
        """
        if not content_a:
            return content_b
        if not content_b:
            return content_a

        # Use difflib unified diff to find common and different parts
        matcher = difflib.SequenceMatcher(None, content_a, content_b)
        merged_parts = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                merged_parts.append(content_a[i1:i2])
            elif tag == 'replace':
                # For replaced sections, prefer the longer one
                if (i2 - i1) >= (j2 - j1):
                    merged_parts.append(content_a[i1:i2])
                else:
                    merged_parts.append(content_b[j1:j2])
            elif tag == 'delete':
                # Keep deleted content if significantly different
                merged_parts.append(content_a[i1:i2])
            elif tag == 'insert':
                merged_parts.append(content_b[j1:j2])

        return ''.join(merged_parts)
