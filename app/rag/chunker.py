"""Text chunker for RAG pipeline on ancient Chinese texts."""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Pre-compiled patterns for ancient book structure markers
CHAPTER_PATTERNS = [
    r"^(卷[零一二三四五六七八九十百\d]+)",  # 卷一, 卷二十, 卷三百二十五
    r"^([上中下篇章节][\u4e00-\u9fa5]*)",    # 上卷, 中篇, 下章, 第一节
    r"^([\u4e00-\u9fa5]{2,4}[志传记表])",    # 人物志, 列传, 本纪, 年表
]
_COMPILED_CHAPTER_PATTERNS = [re.compile(p) for p in CHAPTER_PATTERNS]

# Section patterns (节)
SECTION_PATTERNS = [
    r"^(第[零一二三四五六七八九十百\d]+[节章])",  # 第一节, 第二章
    r"^([上中下篇章节][\u4e00-\u9fa5]*)",          # 上篇, 中章
]
_COMPILED_SECTION_PATTERNS = [re.compile(p) for p in SECTION_PATTERNS]

# Paragraph delimiter (空行分隔)
PARAGRAPH_DELIMITER = r'\n\s*\n'

# Sentence delimiter pattern (pre-compiled)
_SENTENCE_DELIMITER_PATTERN = re.compile(r'[。！？；]')

# Default max tokens for chunking (approximately 500 Chinese characters)
DEFAULT_MAX_TOKENS = 500


class TextChunker:
    """Chunker for ancient Chinese texts (古籍) optimized for RAG.

    Provides semantic chunking strategies:
    - by_chapter: Split by chapter structure
    - by_max_tokens: Split by maximum token count with overlap

    Attributes:
        max_tokens: Maximum tokens per chunk when using by_max_tokens strategy.
        overlap_tokens: Number of overlapping tokens between chunks.
    """

    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        overlap_tokens: int = 50
    ):
        """Initialize the TextChunker.

        Args:
            max_tokens: Maximum number of tokens per chunk (default 500).
            overlap_tokens: Number of overlapping tokens between chunks (default 50).
        """
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        logger.info(
            "TextChunker initialized: max_tokens=%d, overlap_tokens=%d",
            max_tokens, overlap_tokens
        )

    def chunk_by_chapter(
        self,
        text: str,
        chapter_title: Optional[str] = None
    ) -> list:
        """Split text into semantic chunks based on chapter structure.

        Detects chapters (卷), sections (节), and paragraphs to create
        meaningful chunks that preserve document structure.

        Args:
            text: The full text content to chunk.
            chapter_title: Optional title for the chapter (used if no chapter
                title detected in text).

        Returns:
            List of dicts with keys:
                - text: The chunk content
                - chapter_title: Title of the chapter this chunk belongs to
                - chunk_index: Index of this chunk within its chapter
                - metadata: Dict with chapter_level, section_title, paragraph_index
        """
        logger.info("Starting chapter-based chunking, text length: %d", len(text))

        chunks = []
        lines = text.split('\n')
        current_chapter = None
        current_section = None
        current_paragraph_lines = []
        current_chapter_index = 0
        current_section_index = 0
        current_paragraph_index = 0
        chapter_start_pos = 0

        def _flush_paragraph(is_last: bool = False):
            """Flush current paragraph lines as a chunk."""
            nonlocal current_paragraph_lines, current_paragraph_index, chunks

            if not current_paragraph_lines:
                return

            paragraph_text = '\n'.join(current_paragraph_lines).strip()
            if not paragraph_text:
                return

            chunk = {
                'text': paragraph_text,
                'chapter_title': current_chapter or chapter_title or 'Unknown',
                'chunk_index': len(chunks),
                'metadata': {
                    'chapter_level': current_chapter,
                    'section_title': current_section,
                    'paragraph_index': current_paragraph_index
                }
            }
            chunks.append(chunk)
            logger.debug(
                "Created chunk %d: chapter=%s, section=%s, para=%d",
                chunk['chunk_index'],
                chunk['chapter_title'],
                current_section,
                current_paragraph_index
            )
            current_paragraph_lines = []
            current_paragraph_index += 1

        def _detect_chapter_title(line: str) -> tuple:
            """Detect if line is a chapter title. Returns (title, pattern_idx) or (None, None)."""
            for pattern_idx, pattern in enumerate(_COMPILED_CHAPTER_PATTERNS):
                match = pattern.match(line.strip())
                if match:
                    return match.group(1), pattern_idx
            return None, None

        def _detect_section_title(line: str) -> tuple:
            """Detect if line is a section title. Returns (title, pattern_idx) or (None, None)."""
            for pattern_idx, pattern in enumerate(_COMPILED_SECTION_PATTERNS):
                match = pattern.match(line.strip())
                if match:
                    return match.group(1), pattern_idx
            return None, None

        for line_num, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                # Empty line marks paragraph boundary
                _flush_paragraph()
                continue

            # Check if line is a chapter title
            chapter_title_detected, chapter_pattern_idx = _detect_chapter_title(line)
            if chapter_title_detected is not None:
                # Flush remaining paragraph before starting new chapter
                _flush_paragraph()
                if current_chapter is not None:
                    current_chapter_index += 1
                    current_section_index = 0
                    current_paragraph_index = 0
                current_chapter = chapter_title_detected
                current_section = None
                logger.debug(
                    "Detected chapter %d: %s (pattern %d)",
                    current_chapter_index,
                    current_chapter,
                    chapter_pattern_idx
                )
                continue

            # Check if line is a section title
            section_title_detected, section_pattern_idx = _detect_section_title(line)
            if section_title_detected is not None:
                _flush_paragraph()
                current_section = section_title_detected
                current_section_index += 1
                current_paragraph_index = 0
                logger.debug(
                    "Detected section: %s (pattern %d)",
                    current_section,
                    section_pattern_idx
                )
                continue

            # Regular content line - add to current paragraph
            current_paragraph_lines.append(line)

        # Flush any remaining paragraph
        _flush_paragraph(is_last=True)

        logger.info(
            "Chapter-based chunking complete: created %d chunks from %d chapters",
            len(chunks),
            current_chapter_index + 1
        )
        return chunks

    def chunk_by_max_tokens(
        self,
        text: str,
        chapter_title: Optional[str] = None
    ) -> list:
        """Split text into chunks by maximum token count.

        Attempts to split at sentence boundaries (。！？) to maintain
        semantic coherence. Falls back to character-level split if
        a single sentence exceeds max_tokens.

        Args:
            text: The full text content to chunk.
            chapter_title: Optional title for the chapter.

        Returns:
            List of dicts with keys:
                - text: The chunk content
                - chapter_title: Title of the chapter this chunk belongs to
                - chunk_index: Global index of this chunk
                - metadata: Dict with char_count, token_estimate, chunk_start, chunk_end
        """
        logger.info(
            "Starting max-tokens chunking: text_len=%d, max_tokens=%d",
            len(text),
            self.max_tokens
        )

        chunks = []
        # Split by sentence delimiters
        sentences = self._split_sentences(text)
        current_chunk_sentences = []
        current_char_count = 0
        chunk_start = 0

        for sent_idx, sentence in enumerate(sentences):
            sent_text = sentence['text']
            sent_len = sentence['char_count']

            # Check if adding this sentence would exceed limit
            if (current_char_count + sent_len > self.max_tokens
                    and current_chunk_sentences):
                # Flush current chunk
                chunk_text = ''.join(s['text'] for s in current_chunk_sentences)
                chunks.append({
                    'text': chunk_text,
                    'chapter_title': chapter_title or 'Unknown',
                    'chunk_index': len(chunks),
                    'metadata': {
                        'char_count': current_char_count,
                        'token_estimate': self._estimate_tokens(chunk_text),
                        'chunk_start': chunk_start,
                        'chunk_end': chunk_start + current_char_count
                    }
                })
                logger.debug(
                    "Created chunk %d: chars=%d, tokens=%d",
                    chunks[-1]['chunk_index'],
                    current_char_count,
                    chunks[-1]['metadata']['token_estimate']
                )

                # Start new chunk with overlap
                overlap_sentences = self._get_overlap_sentences(
                    current_chunk_sentences
                )
                current_chunk_sentences = overlap_sentences + [sentence]
                current_char_count = sum(s['char_count'] for s in current_chunk_sentences)
                chunk_start = sentence['start']

                # Update indices for overlap
                if overlap_sentences:
                    chunk_start = overlap_sentences[0]['start']

            else:
                current_chunk_sentences.append(sentence)
                current_char_count += sent_len

        # Don't forget the last chunk
        if current_chunk_sentences:
            chunk_text = ''.join(s['text'] for s in current_chunk_sentences)
            chunks.append({
                'text': chunk_text,
                'chapter_title': chapter_title or 'Unknown',
                'chunk_index': len(chunks),
                'metadata': {
                    'char_count': current_char_count,
                    'token_estimate': self._estimate_tokens(chunk_text),
                    'chunk_start': chunk_start,
                    'chunk_end': chunk_start + current_char_count
                }
            })
            logger.debug(
                "Created final chunk %d: chars=%d, tokens=%d",
                chunks[-1]['chunk_index'],
                current_char_count,
                chunks[-1]['metadata']['token_estimate']
            )

        logger.info("Max-tokens chunking complete: created %d chunks", len(chunks))
        return chunks

    def chunk(
        self,
        text: str,
        strategy: str = "by_chapter",
        chapter_title: Optional[str] = None
    ) -> list:
        """Main entry point for chunking text.

        Args:
            text: The full text content to chunk.
            strategy: Chunking strategy - "by_chapter" or "by_max_tokens".
            chapter_title: Optional title for the chapter.

        Returns:
            List of chunk dicts. Structure depends on strategy used.

        Raises:
            ValueError: If strategy is not recognized.
        """
        if strategy == "by_chapter":
            return self.chunk_by_chapter(text, chapter_title)
        elif strategy == "by_max_tokens":
            return self.chunk_by_max_tokens(text, chapter_title)
        else:
            raise ValueError(
                f"Unknown chunking strategy: {strategy}. "
                f"Expected 'by_chapter' or 'by_max_tokens'."
            )

    def _split_sentences(self, text: str) -> list:
        """Split text into sentences based on ancient book punctuation.

        Args:
            text: The text content to split.

        Returns:
            List of dicts with keys: text, start, end, char_count.
        """
        parts = _SENTENCE_DELIMITER_PATTERN.split(text)
        delimiters = _SENTENCE_DELIMITER_PATTERN.findall(text)

        sentences = []
        current_pos = 0

        for i, part in enumerate(parts):
            if not part.strip():
                if i < len(delimiters):
                    current_pos += len(delimiters[i])
                continue

            start = current_pos
            text_part = part.strip()
            char_count = len(text_part)

            if i < len(delimiters):
                text_with_delim = text_part + delimiters[i]
                end = start + len(text_part) + len(delimiters[i])
            else:
                text_with_delim = text_part
                end = start + char_count

            sentences.append({
                'text': text_with_delim,
                'start': start,
                'end': end,
                'char_count': char_count
            })
            current_pos = end

        return sentences

    def _get_overlap_sentences(self, sentences: list) -> list:
        """Get overlapping sentences for chunk continuity.

        Args:
            sentences: List of sentence dicts.

        Returns:
            List of sentences to use as overlap (from end of previous chunk).
        """
        if not sentences or self.overlap_tokens <= 0:
            return []

        overlap_chars = 0
        overlap_start_idx = len(sentences)

        # Find sentences that fit within overlap token budget
        for i in range(len(sentences) - 1, -1, -1):
            overlap_chars += sentences[i]['char_count']
            if overlap_chars > self.overlap_tokens:
                overlap_start_idx = i + 1
                break

        return sentences[overlap_start_idx:]

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for Chinese text.

        Uses a rough approximation: 1 token ≈ 1.5-2 Chinese characters
        for classical Chinese text.

        Args:
            text: The text content to estimate.

        Returns:
            Estimated token count.
        """
        char_count = len(text)
        # Conservative estimate: 1 token per 1.5 characters for classical Chinese
        return int(char_count / 1.5)
