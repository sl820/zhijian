"""Version quality ranking for multi-source text compilation."""

import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Known authoritative sources
# ----------------------------------------------------------------------
_AUTHORITATIVE_DOMAINS = {
    "ctext.org",
    "perseus.tufts.edu",
    "loebclassics.com",
    "sacred-texts.com",
    "nationallibrary.gov",
    "libraryofcongress.gov",
    "britishlibrary.uk",
    "gallica.bnf.fr",
    "europeana.eu",
    "archive.org",
}

_SOURCE_TYPE_AUTHORITY = {
    "database": 1.0,
    "library": 0.9,
    "digital_humanities_project": 0.8,
    "scholarly_edition": 0.85,
    "custom": 0.4,
    "ocr": 0.3,
    "unknown": 0.2,
}

# Expected lengths for various source types (rough word-count estimates)
_EXPECTED_TEXT_LENGTHS = {
    "short_text": 500,
    "medium_text": 5000,
    "long_text": 25000,
    "very_long_text": 100000,
}


# ----------------------------------------------------------------------
# Dataclasses
# ----------------------------------------------------------------------
@dataclass
class SourceQuality:
    """Quality metrics for a single text source."""

    source_name: str
    source_type: str
    text_length: int
    ocr_confidence: float | None  # None if not OCR-derived
    completeness_score: float  # 0-1
    age_score: float  # 0-1
    authority_score: float  # 0-1
    overall_score: float  # weighted combination


class TextSource:
    """Represents a text source with metadata.

    This class is a lightweight container expected to be provided by
    the caller.  It is not instantiated by this module.
    """

    def __init__(
        self,
        name: str,
        source_type: str,
        text: str,
        year: int | None = None,
        ocr_confidence: float | None = None,
        url: str | None = None,
    ):
        self.name = name
        self.source_type = source_type
        self.text = text
        self.year = year
        self.ocr_confidence = ocr_confidence
        self.url = url

    def __repr__(self) -> str:
        return f"TextSource(name={self.name!r}, source_type={self.source_type!r})"


# ----------------------------------------------------------------------
# VersionRanker
# ----------------------------------------------------------------------
class VersionRanker:
    """Rank text sources by overall quality using weighted scoring."""

    DEFAULT_WEIGHTS = {
        "completeness": 0.4,
        "authority": 0.3,
        "age": 0.2,
        "ocr_confidence": 0.1,
    }

    def __init__(self, weights: Dict[str, float] | None = None):
        """Initialize the ranker.

        Args:
            weights: Override for default weight dict. Keys must match
                     DEFAULT_WEIGHTS. Values should sum to 1.0 (not enforced).
        """
        self.weights = dict(self.DEFAULT_WEIGHTS)
        if weights is not None:
            self.weights.update(weights)
        logger.debug("VersionRanker initialised with weights: %s", self.weights)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def rank_versions(self, sources: List[TextSource]) -> List[Tuple[TextSource, float]]:
        """Rank text sources by overall quality score (descending).

        Args:
            sources: List of TextSource objects to rank.

        Returns:
            Sorted list of (source, overall_score) tuples, highest score first.
        """
        if not sources:
            logger.warning("rank_versions called with empty source list")
            return []

        scored = [(s, self.score_source(s)) for s in sources]
        scored.sort(key=lambda x: x[1].overall_score, reverse=True)

        for rank, (s, q) in enumerate(scored, 1):
            logger.info(
                "Rank %d — %s (%.4f): completeness=%.3f authority=%.3f age=%.3f ocr=%.3f",
                rank,
                s.name,
                q.overall_score,
                q.completeness_score,
                q.authority_score,
                q.age_score,
                q.ocr_confidence if q.ocr_confidence is not None else -1.0,
            )

        return [(s, q.overall_score) for s, q in scored]

    def select_best(self, sources: List[TextSource]) -> TextSource:
        """Return the single best source from a list.

        Args:
            sources: Non-empty list of TextSource objects.

        Returns:
            The source with the highest overall quality score.

        Raises:
            ValueError: If sources is empty.
        """
        if not sources:
            raise ValueError("select_best requires at least one source")

        ranked = self.rank_versions(sources)
        best_source, best_score = ranked[0]
        logger.info("Selected best source: %s (score=%.4f)", best_source.name, best_score)
        return best_source

    def score_source(self, source: TextSource) -> SourceQuality:
        """Compute detailed quality scores for one source.

        Args:
            source: A TextSource instance.

        Returns:
            A SourceQuality dataclass with all sub-scores and overall_score.
        """
        completeness = self._completeness(source)
        authority = self._authority(source)
        age = self._age_score(source)
        ocr = source.ocr_confidence  # may be None

        overall = (
            self.weights["completeness"] * completeness
            + self.weights["authority"] * authority
            + self.weights["age"] * age
            + (self.weights["ocr_confidence"] * ocr if ocr is not None else 0.0)
        )

        logger.debug(
            "Scored %s — completeness=%.3f authority=%.3f age=%.3f ocr=%s => overall=%.4f",
            source.name,
            completeness,
            authority,
            age,
            f"{ocr:.3f}" if ocr is not None else "N/A",
            overall,
        )

        return SourceQuality(
            source_name=source.name,
            source_type=source.source_type,
            text_length=len(source.text),
            ocr_confidence=ocr,
            completeness_score=completeness,
            age_score=age,
            authority_score=authority,
            overall_score=overall,
        )

    # ------------------------------------------------------------------
    # Quality heuristics
    # ------------------------------------------------------------------
    def _completeness(self, source: TextSource) -> float:
        """Estimate completeness based on text length vs expected norms.

        Longer text (up to a reasonable ceiling) yields higher scores.
        A text that is extremely short for its category is penalised.
        """
        length = len(source.text)

        # Determine a soft ceiling — very long texts don't keep gaining score
        ceiling = 100_000

        # Simple piecewise model:
        #   0 chars  -> 0.0
        #   500 chars -> ~0.2
        #   5 000 chars -> ~0.6
        #   25 000 chars -> ~0.9
        #   100 000+ -> 1.0 (capped)
        if length == 0:
            return 0.0
        if length >= ceiling:
            return 1.0

        # Log-scale curve up to ceiling, then flat
        import math

        normalised = math.log1p(length) / math.log1p(ceiling)
        return round(normalised, 4)

    def _authority(self, source: TextSource) -> float:
        """Score authority based on source type and known authoritative domains."""
        # Base authority from source type
        base = _SOURCE_TYPE_AUTHORITY.get(source.source_type, _SOURCE_TYPE_AUTHORITY["unknown"])

        # Boost for known domains
        if source.url:
            url_lower = source.url.lower()
            for domain in _AUTHORITATIVE_DOMAINS:
                if domain in url_lower:
                    base = max(base, 0.95)
                    logger.debug("Authority boost for known domain %s in source %s", domain, source.name)
                    break

        return round(base, 4)

    def _age_score(self, source: TextSource) -> float:
        """Score age/authority of a text.

        For ancient / historical texts, older tends to be more authoritative,
        but completeness outweighs age. This method returns a 0-1 score where
        1 = very old / canonical, 0 = very recent / uncertain.

        Texts without a year attribute receive a neutral 0.5.
        """
        year = source.year
        if year is None:
            return 0.5

        # Rough brackets — tune as needed
        #   < 0  (BCE)       -> 1.0
        #   0-500            -> 0.95
        #   500-1000         -> 0.85
        #   1000-1500        -> 0.7
        #   1500-1800        -> 0.5
        #   1800-1950        -> 0.35
        #   1950-2000        -> 0.2
        #   > 2000           -> 0.1
        if year < 0:
            return 1.0
        if year < 500:
            return 0.95
        if year < 1000:
            return 0.85
        if year < 1500:
            return 0.7
        if year < 1800:
            return 0.5
        if year < 1950:
            return 0.35
        if year < 2000:
            return 0.2
        return 0.1


# ----------------------------------------------------------------------
# ProvenanceTracker
# ----------------------------------------------------------------------
class ProvenanceTracker:
    """Track which source contributed which parts in merged output."""

    def create_provenance_map(
        self,
        merged_text: str,
        source_assignments: List[Tuple[str, str]],
    ) -> Dict:
        """Build a provenance map from segment-level source attributions.

        Args:
            merged_text: The final merged text (used for length / sanity checks).
            source_assignments: List of (text_segment, source_name) tuples in
                                the order they appear in the merged output.

        Returns:
            A dictionary with keys:
                - "total_chars": total character count in merged_text
                - "segments": list of dicts with "text", "source", "char_count"
                - "source_summary": dict mapping source_name -> total_chars contributed
                - "coverage_ratio": fraction of merged_text accounted for by assignments
        """
        if not source_assignments:
            logger.warning("create_provenance_map called with empty source_assignments")
            return {
                "total_chars": len(merged_text),
                "segments": [],
                "source_summary": {},
                "coverage_ratio": 0.0,
            }

        segments = []
        source_summary: Dict[str, int] = {}
        assigned_chars = 0

        for segment_text, source_name in source_assignments:
            char_count = len(segment_text)
            segments.append({
                "text": segment_text,
                "source": source_name,
                "char_count": char_count,
            })
            source_summary[source_name] = source_summary.get(source_name, 0) + char_count
            assigned_chars += char_count

        coverage = assigned_chars / len(merged_text) if merged_text else 0.0

        provenance = {
            "total_chars": len(merged_text),
            "segments": segments,
            "source_summary": source_summary,
            "coverage_ratio": round(coverage, 4),
        }

        logger.info(
            "Provenance map: %d segments, %d sources, coverage=%.2f%%",
            len(segments),
            len(source_summary),
            coverage * 100,
        )
        for src, count in source_summary.items():
            logger.debug("  %s: %d chars", src, count)

        return provenance
