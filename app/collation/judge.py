from enum import Enum


class JudgmentRule(Enum):
    TABOO_FIRST = 1
    CHRONOLOGY = 2
    GRAPHIC_SIM = 3
    CONTEXT_SCORE = 4


class CollactionJudge:
    def __init__(self, config: dict = None):
        self.config = config or {}

    def judge(self, diff: dict, context: dict = None) -> dict:
        """
        Judge a single diff and return the preferred version with reasoning.

        Args:
            diff: Diff dict with type, text_a, text_b, etc.
            context: Optional context dict with version_a_year, version_b_year, etc.

        Returns:
            Dict with preferred_version, judgment, confidence, rule_used
        """
        diff_type = diff.get("type")

        # Route to appropriate judgment method based on diff type
        if diff_type == "taboo":
            return self._judge_taboo(diff)
        elif diff_type == "variant":
            return self._judge_variant(diff)
        elif diff_type == "insertion" or diff_type == "deletion":
            # For insertions/deletions, try chronology first
            result = self._judge_chronology(diff, context)
            if result:
                return result
            return self._judge_graphic_similarity(diff)
        elif diff_type == "substitution" or diff_type == "transposition":
            # Try chronology first for substitutions/transpositions
            result = self._judge_chronology(diff, context)
            if result:
                return result
            # Fall back to graphic similarity
            return self._judge_graphic_similarity(diff)
        else:
            return {
                "preferred_version": None,
                "judgment": "unknown",
                "confidence": 0.0,
                "rule_used": None
            }

    def _judge_taboo(self, diff: dict) -> dict:
        """
        Judge taboo replacements - recommend restoring the original.
        """
        return {
            "preferred_version": "original",
            "judgment": "restore_original",
            "confidence": 0.9,
            "rule_used": JudgmentRule.TABOO_FIRST.name
        }

    def _judge_variant(self, diff: dict) -> dict:
        """
        Judge variant differences - choose the shorter version (standard form is usually shorter).
        """
        text_a = diff.get("text_a", "")
        text_b = diff.get("text_b", "")

        # Prefer shorter version as standard form
        preferred = "A" if len(text_a) <= len(text_b) else "B"

        return {
            "preferred_version": preferred,
            "judgment": f"prefer_shorter({preferred})",
            "confidence": 0.85,
            "rule_used": JudgmentRule.GRAPHIC_SIM.name
        }

    def _judge_chronology(self, diff: dict, context: dict = None) -> dict:
        """
        Judge based on chronology - prefer earlier version if years are available.
        """
        if not context:
            return None

        version_a_year = context.get("version_a_year")
        version_b_year = context.get("version_b_year")

        if version_a_year and version_b_year:
            text_a = diff.get("text_a", "")
            text_b = diff.get("text_b", "")

            if version_a_year < version_b_year:
                return {
                    "preferred_version": "A",
                    "judgment": f"prefer_earlier(A:{version_a_year}<B:{version_b_year})",
                    "confidence": 0.75,
                    "rule_used": JudgmentRule.CHRONOLOGY.name
                }
            else:
                return {
                    "preferred_version": "B",
                    "judgment": f"prefer_earlier(B:{version_b_year}<A:{version_a_year})",
                    "confidence": 0.75,
                    "rule_used": JudgmentRule.CHRONOLOGY.name
                }

        return None

    def _judge_graphic_similarity(self, diff: dict) -> dict:
        """
        Judge based on graphic similarity - placeholder implementation.
        """
        return {
            "preferred_version": None,
            "judgment": "unknown",
            "confidence": 0.3,
            "rule_used": JudgmentRule.GRAPHIC_SIM.name
        }


def batch_judge(diffs: list, context: dict = None) -> list:
    """
    Apply judge() to all diffs and add judgment_result to each.

    Args:
        diffs: List of diff dicts
        context: Optional context dict

    Returns:
        List of diffs with judgment_result added to each
    """
    judge = CollactionJudge()

    for diff in diffs:
        judgment_result = judge.judge(diff, context)
        diff["judgment_result"] = judgment_result

    return diffs
