import logging
import json
from typing import Optional, Dict, List

from .tokenizer import TextTokenizer
from .aligner import SemanticAligner
from .differ import TextDiffer, DiffType
from .judge import CollactionJudge, JudgmentRule, batch_judge

logger = logging.getLogger(__name__)


class CollationProcessor:
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.tokenizer = TextTokenizer()
        self.aligner = SemanticAligner()
        self.differ = TextDiffer()
        self.judge_instance = CollactionJudge()
        logger.info("CollationProcessor initialized")

    def process(self, text_a: str, text_b: str, metadata_a: dict = None, metadata_b: dict = None, output_path: str = None) -> dict:
        try:
            logger.info("Starting collation process")
            metadata_a = metadata_a or {}
            metadata_b = metadata_b or {}

            # Step 1: Split chapters on both texts
            chapters_a = self.tokenizer.split_chapters(text_a)
            chapters_b = self.tokenizer.split_chapters(text_b)
            chapter_count_a = len(chapters_a)
            chapter_count_b = len(chapters_b)
            logger.info(f"Chapter split: A={chapter_count_a}, B={chapter_count_b}")

            # Fallback: if no chapters found, treat whole text as one chapter
            if not chapters_a:
                chapters_a = [{'title': 'main', 'content': text_a, 'level': 0}]
                logger.info("No chapters found in text A, using whole text as single chapter")
            if not chapters_b:
                chapters_b = [{'title': 'main', 'content': text_b, 'level': 0}]
                logger.info("No chapters found in text B, using whole text as single chapter")

            # Step 2: Split sentences on both texts
            sentences_a = []
            sentences_b = []
            for chapter_a, chapter_b in zip(chapters_a, chapters_b):
                sentences_a.extend(self.tokenizer.split_sentences(chapter_a.get('content', '')))
                sentences_b.extend(self.tokenizer.split_sentences(chapter_b.get('content', '')))
            # Extract text strings for aligner
            texts_a = [s['text'] for s in sentences_a]
            texts_b = [s['text'] for s in sentences_b]
            sentence_count_a = len(sentences_a)
            sentence_count_b = len(sentences_b)
            logger.info(f"Sentence split: A={sentence_count_a}, B={sentence_count_b}")

            # Step 3: Constrained align to align sentences
            alignment_result = self.aligner.constrained_align(texts_a, texts_b)
            alignment_score = alignment_result.get('alignment_score', 0.0)
            logger.info(f"Alignment score: {alignment_score}")

            # Step 4: Detect diffs to find differences
            # Convert tuple alignments (idx_a, idx_b, score) to dict format expected by differ
            raw_alignments = alignment_result['alignments']
            alignment_dicts = []
            for item in raw_alignments:
                if isinstance(item, tuple) and len(item) >= 2:
                    idx_a, idx_b = item[0], item[1]
                    alignment_dicts.append({
                        'idx_a': idx_a,
                        'idx_b': idx_b,
                        'text_a': texts_a[idx_a] if idx_a is not None else '',
                        'text_b': texts_b[idx_b] if idx_b is not None else '',
                    })
            # Handle unmatched sentences as insertions/deletions
            for idx in alignment_result.get('unmatched_a', []):
                alignment_dicts.append({
                    'idx_a': idx, 'idx_b': None,
                    'text_a': texts_a[idx], 'text_b': '',
                })
            for idx in alignment_result.get('unmatched_b', []):
                alignment_dicts.append({
                    'idx_a': None, 'idx_b': idx,
                    'text_a': '', 'text_b': texts_b[idx],
                })
            diffs = self.differ.detect_diffs(texts_a, texts_b, alignment_dicts)
            logger.info(f"Detected {len(diffs)} differences")

            # Step 5: Batch judge with context (version years, dynasty)
            context = {
                'version_a_year': metadata_a.get('year'),
                'version_b_year': metadata_b.get('year'),
                'dynasty': metadata_a.get('dynasty', 'qing'),
            }
            diffs = batch_judge(diffs, context=context)
            logger.info(f"Judged {len(diffs)} differences")

            # Step 6: Summarize diffs
            summary = self._summarize_diffs(diffs)

            result = {
                'alignment_score': alignment_score,
                'alignment_result': alignment_result,
                'chapter_count_a': chapter_count_a,
                'chapter_count_b': chapter_count_b,
                'sentence_count_a': sentence_count_a,
                'sentence_count_b': sentence_count_b,
                'diffs': diffs,
                'summary': summary
            }

            # Output to JSON if output_path specified
            if output_path:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                logger.info(f"Result written to {output_path}")

            return result

        except Exception as e:
            logger.error(f"Error in collation process: {e}")
            raise

    def _summarize_diffs(self, diffs: list) -> dict:
        summary = {
            'total_diffs': len(diffs),
            'by_type': {}
        }
        for diff in diffs:
            diff_type = diff.get('type', 'unknown')
            if diff_type not in summary['by_type']:
                summary['by_type'][diff_type] = 0
            summary['by_type'][diff_type] += 1
        return summary


def compare_gazetteer_versions(file_a: str, file_b: str, output_dir: str = None) -> dict:
    logger.info(f"Comparing gazetteer versions: {file_a} vs {file_b}")
    try:
        # Read files
        with open(file_a, 'r', encoding='utf-8') as f:
            text_a = f.read()
        with open(file_b, 'r', encoding='utf-8') as f:
            text_b = f.read()

        # Process
        processor = CollationProcessor()
        result = processor.process(text_a, text_b, output_path=output_dir)

        logger.info("Gazetteer comparison completed")
        return result

    except Exception as e:
        logger.error(f"Error comparing gazetteer versions: {e}")
        raise
