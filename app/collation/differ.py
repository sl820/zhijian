from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DiffType(Enum):
    INSERTION = "insertion"
    DELETION = "deletion"
    SUBSTITUTION = "substitution"
    VARIANT = "variant"
    TABOO = "taboo"
    TRANSPOSITION = "transposition"


class TextDiffer:
    def __init__(self, variant_map: dict = None, taboo_rules: dict = None):
        self.variant_map = variant_map or {}
        self.taboo_rules = taboo_rules or {}

    def detect_diffs(self, sentences_a: list, sentences_b: list, alignments: list) -> list:
        """
        Detect differences between two versions of text based on alignments.

        Args:
            sentences_a: List of sentences from version A
            sentences_b: List of sentences from version B
            alignments: List of alignment dicts from aligner output

        Returns:
            List of diff dicts with {type, position_a, position_b, text_a, text_b, char_diffs, judgment, confidence}
        """
        diffs = []

        for alignment in alignments:
            idx_a = alignment.get("idx_a")
            idx_b = alignment.get("idx_b")
            text_a = alignment.get("text_a", "")
            text_b = alignment.get("text_b", "")

            if idx_a is None:
                # INSERTION: present in B but not in A
                diff = {
                    "type": DiffType.INSERTION,
                    "position_a": None,
                    "position_b": idx_b,
                    "text_a": text_a,
                    "text_b": text_b,
                    "char_diffs": None,
                    "judgment": None,
                    "confidence": None
                }
                diffs.append(diff)
            elif idx_b is None:
                # DELETION: present in A but not in B
                diff = {
                    "type": DiffType.DELETION,
                    "position_a": idx_a,
                    "position_b": None,
                    "text_a": text_a,
                    "text_b": text_b,
                    "char_diffs": None,
                    "judgment": None,
                    "confidence": None
                }
                diffs.append(diff)
            else:
                # Replacement or variant - analyze character-level differences
                analysis = self._analyze_replacement(text_a, text_b)
                diff = {
                    "type": analysis["diff_type"],
                    "position_a": idx_a,
                    "position_b": idx_b,
                    "text_a": text_a,
                    "text_b": text_b,
                    "char_diffs": analysis["char_diffs"],
                    "judgment": None,
                    "confidence": None
                }
                diffs.append(diff)

        return diffs

    def _analyze_replacement(self, text_a: str, text_b: str) -> dict:
        """
        Analyze character-by-character differences between two texts.

        Returns dict with diff_type and char_diffs.
        """
        # Check for transposition first
        if self._is_transposition(text_a, text_b):
            return {
                "diff_type": DiffType.TRANSPOSITION,
                "char_diffs": self._get_char_diffs(text_a, text_b)
            }

        # Check against taboo rules
        if self._check_taboo(text_a, text_b):
            return {
                "diff_type": DiffType.TABOO,
                "char_diffs": self._get_char_diffs(text_a, text_b)
            }

        # Check against variant map
        if self._check_variant(text_a, text_b):
            return {
                "diff_type": DiffType.VARIANT,
                "char_diffs": self._get_char_diffs(text_a, text_b)
            }

        # Default to substitution
        return {
            "diff_type": DiffType.SUBSTITUTION,
            "char_diffs": self._get_char_diffs(text_a, text_b)
        }

    def _is_transposition(self, text_a: str, text_b: str) -> bool:
        """
        Check if text_b is a transposition of text_a (same characters, different order).
        """
        if len(text_a) != len(text_b):
            return False
        return sorted(text_a) == sorted(text_b)

    def _check_taboo(self, text_a: str, text_b: str) -> bool:
        """Check if the replacement matches any taboo rules."""
        for taboo_pattern, replacement_info in self.taboo_rules.items():
            if taboo_pattern in text_a and text_b == replacement_info.get("replacement"):
                return True
        return False

    def _check_variant(self, text_a: str, text_b: str) -> bool:
        """Check if the replacement matches a known variant mapping."""
        for variant_key, variants in self.variant_map.items():
            if text_a in variants and text_b in variants and text_a != text_b:
                return True
        return False

    def _get_char_diffs(self, text_a: str, text_b: str) -> list:
        """
        Perform character-by-character comparison and return list of differences.
        """
        char_diffs = []
        max_len = max(len(text_a), len(text_b))

        for i in range(max_len):
            char_a = text_a[i] if i < len(text_a) else None
            char_b = text_b[i] if i < len(text_b) else None

            if char_a != char_b:
                char_diffs.append({
                    "position": i,
                    "char_a": char_a,
                    "char_b": char_b
                })

        return char_diffs


def visualize_diff(diff: dict) -> str:
    """
    Return a formatted string showing the diff details.

    Args:
        diff: Diff dict with type, position_a, position_b, text_a, text_b, char_diffs

    Returns:
        Formatted string representation of the diff
    """
    diff_type = diff.get("type")
    if isinstance(diff_type, DiffType):
        diff_type = diff_type.value

    position_a = diff.get("position_a")
    position_b = diff.get("position_b")
    text_a = diff.get("text_a", "")
    text_b = diff.get("text_b", "")
    char_diffs = diff.get("char_diffs", [])

    lines = []
    lines.append(f"Diff Type: {diff_type}")
    lines.append(f"Position: A={position_a}, B={position_b}")
    lines.append(f"Text A: {repr(text_a)}")
    lines.append(f"Text B: {repr(text_b)}")

    if char_diffs:
        lines.append("Character differences:")
        for cd in char_diffs:
            lines.append(f"  Position {cd['position']}: {repr(cd['char_a'])} -> {repr(cd['char_b'])}")

    judgment = diff.get("judgment")
    confidence = diff.get("confidence")
    if judgment:
        lines.append(f"Judgment: {judgment} (confidence: {confidence})")

    return "\n".join(lines)
