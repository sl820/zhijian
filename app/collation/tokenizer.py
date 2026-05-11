"""Ancient book text tokenizer for collation tasks."""

import re
import logging

logger = logging.getLogger(__name__)

# Regex patterns for ancient book chapter titles (pre-compiled at module level)
CHAPTER_PATTERNS = [
    r"^(卷[零一二三四五六七八九十百\d]+)",  # 卷一, 卷二十, 卷三百二十五
    r"^([上中下篇章节][\u4e00-\u9fa5]*)",    # 上卷, 中篇, 下章, 第一节
    r"^([\u4e00-\u9fa5]{2,4}[志传记表])",    # 人物志, 列传, 本纪, 年表
]
_COMPILED_CHAPTER_PATTERNS = [re.compile(p) for p in CHAPTER_PATTERNS]

# Sentence delimiter characters (古籍句读标记)
SENTENCE_DELIMITERS = r'[。！？；]'


class TextTokenizer:
    """Tokenizer for ancient Chinese book texts.

    Provides methods to split text into chapters, sentences, and extract metadata.
    """

    def split_chapters(self, text: str) -> list:
        """Split text into chapters based on title patterns.

        Args:
            text: The full text content to split.

        Returns:
            List of dicts with keys: title, content, start_pos, end_pos, level, title_type.
        """
        logger.info("Starting chapter splitting, text length: %d", len(text))
        chapters = []
        lines = text.split('\n')
        current_chapter = None
        current_content_parts = []
        current_start_pos = 0

        for line_num, line in enumerate(lines):
            matched_pattern = None
            matched_title = None

            # Check if line matches any chapter pattern (using pre-compiled module-level patterns)
            for pattern_idx, pattern in enumerate(_COMPILED_CHAPTER_PATTERNS):
                match = pattern.match(line.strip())
                if match:
                    matched_pattern = pattern_idx
                    matched_title = match.group(1)
                    logger.debug("Line %d matched pattern %d: %s", line_num, pattern_idx, matched_title)
                    break

            if matched_pattern is not None:
                # Save previous chapter if exists
                if current_chapter is not None:
                    current_chapter['content'] = '\n'.join(current_content_parts)
                    current_chapter['end_pos'] = current_start_pos + len('\n'.join(current_content_parts)) if current_content_parts else current_start_pos
                    chapters.append(current_chapter)
                    logger.info("Saved chapter: %s", current_chapter['title'])

                # Start new chapter
                current_start_pos = text.find(line, 0 if current_chapter is None else current_chapter['end_pos'])
                current_chapter = {
                    'title': matched_title,
                    'content': '',
                    'start_pos': current_start_pos,
                    'end_pos': 0,
                    'level': matched_pattern,
                    'title_type': CHAPTER_PATTERNS[matched_pattern]
                }
                current_content_parts = []
            elif current_chapter is not None:
                current_content_parts.append(line)

        # Don't forget the last chapter
        if current_chapter is not None:
            current_chapter['content'] = '\n'.join(current_content_parts)
            current_chapter['end_pos'] = current_start_pos + len(current_chapter['content'])
            chapters.append(current_chapter)
            logger.info("Saved final chapter: %s", current_chapter['title'])

        logger.info("Chapter splitting complete, found %d chapters", len(chapters))
        return chapters

    def split_sentences(self, text: str) -> list:
        """Split text into sentences based on ancient book punctuation.

        Args:
            text: The text content to split.

        Returns:
            List of dicts with keys: text, start, end, char_count.
        """
        logger.info("Starting sentence splitting, text length: %d", len(text))

        # Split on sentence delimiters
        parts = re.split(SENTENCE_DELIMITERS, text)
        delimiters = re.findall(SENTENCE_DELIMITERS, text)

        sentences = []
        current_pos = 0

        for i, part in enumerate(parts):
            if not part.strip():
                # Empty part, just add delimiter position
                if i < len(delimiters):
                    current_pos += len(delimiters[i])
                continue

            start = current_pos
            text_part = part.strip()
            char_count = len(text_part)

            # Add delimiter back to text if exists
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
            logger.debug("Sentence %d: start=%d, end=%d, char_count=%d", len(sentences), start, end, char_count)

        logger.info("Sentence splitting complete, found %d sentences", len(sentences))
        return sentences

    def extract_metadata(self, text: str) -> dict:
        """Extract metadata from ancient book text.

        Args:
            text: The text content to extract metadata from.

        Returns:
            Dict with keys: title, version, year_range, area.
        """
        logger.info("Starting metadata extraction")

        metadata = {
            'title': None,
            'version': None,
            'year_range': None,
            'area': None
        }

        first_line = text.split('\n')[0] if text else ''

        # Extract gazetteer title 《...》
        title_match = re.search(r'《([^》]+)》', first_line)
        if title_match:
            metadata['title'] = title_match.group(1)
            logger.info("Extracted title: %s", metadata['title'])

        # Extract version from patterns like 康熙, 乾隆, etc.
        version_patterns = [
            r'(康熙)', r'(乾隆)', r'(雍正)', r'(光绪)',
            r'(嘉庆)', r'(道光)', r'(同治)', r'(咸丰)', r'(宣统)'
        ]
        for pattern in version_patterns:
            version_match = re.search(pattern, text)
            if version_match:
                metadata['version'] = version_match.group(1)
                logger.info("Extracted version: %s", metadata['version'])
                break

        # Extract year from 4-digit patterns
        year_match = re.search(r'\d{4}', text)
        if year_match:
            metadata['year_range'] = year_match.group(0)
            logger.info("Extracted year: %s", metadata['year_range'])

        logger.info("Metadata extraction complete: %s", metadata)
        return metadata
