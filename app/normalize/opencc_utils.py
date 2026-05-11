"""
OpenCC-based text normalization utilities for Traditional/Simplified Chinese conversion.
"""

import logging
from opencc import OpenCC

try:
    from app.ocr.variant_map import VARIANT_CHAR_MAP, normalize_variant_text
except ImportError:
    VARIANT_CHAR_MAP = {}
    normalize_variant_text = lambda text, **kwargs: text  # identity fallback

logger = logging.getLogger(__name__)


class TextNormalizer:
    """
    Text normalizer for Chinese text conversion between Traditional and Simplified Chinese,
    as well as variant character normalization.
    """

    def __init__(self, config: dict = None):
        """
        Initialize the TextNormalizer with OpenCC converters.

        Args:
            config: Optional configuration dictionary for future extensibility.
        """
        self.config = config or {}
        self._s2t = OpenCC('s2t')  # Simplified to Traditional
        self._t2s = OpenCC('t2s')  # Traditional to Simplified
        self._s2tw = OpenCC('s2tw')  # Simplified to Traditional (Taiwan variant)
        self._s2hk = OpenCC('s2hk')  # Simplified to Traditional (Hong Kong variant)
        self._variant_char_map = VARIANT_CHAR_MAP
        self._normalize_variant_text = normalize_variant_text
        logger.info("TextNormalizer initialized with OpenCC converters")

    def traditional_to_simplified(self, text: str) -> str:
        """
        Convert Traditional Chinese to Simplified Chinese.

        Args:
            text: Input text in Traditional Chinese.

        Returns:
            Converted text in Simplified Chinese.
        """
        if not text:
            return text
        result = self._t2s.convert(text)
        logger.debug(f"Traditional to Simplified conversion: {len(text)} -> {len(result)} chars")
        return result

    def simplified_to_traditional(self, text: str, variant: str = "tw") -> str:
        """
        Convert Simplified Chinese to Traditional Chinese with specified variant.

        Args:
            text: Input text in Simplified Chinese.
            variant: Target variant - "tw" (Taiwan), "hk" (Hong Kong), or "t" (Traditional).

        Returns:
            Converted text in Traditional Chinese of the specified variant.
        """
        if not text:
            return text

        if variant == "hk":
            result = self._s2hk.convert(text)
        elif variant == "tw":
            result = self._s2tw.convert(text)
        else:
            result = self._s2t.convert(text)

        logger.debug(f"Simplified to Traditional ({variant}) conversion: {len(text)} -> {len(result)} chars")
        return result

    def normalize_variants(self, text: str, target: str = "standard") -> str:
        """
        Normalize variant characters to standard forms.

        Args:
            text: Input text with potential variant characters.
            target: Target normalization standard, currently only "standard" is supported.

        Returns:
            Text with variant characters normalized to standard forms.
        """
        if not text:
            return text

        if self._normalize_variant_text is not None:
            result = self._normalize_variant_text(text, target)
        else:
            # Fallback: simple character replacement
            result = text
            for variant_char, standard_char in self._variant_char_map.items():
                result = result.replace(variant_char, standard_char)

        logger.debug(f"Variant normalization ({target}): {len(text)} -> {len(result)} chars")
        return result

    def preserve_proper_nouns(self, text: str, entities: list) -> str:
        """
        Preserve proper nouns (entities) by marking them during normalization.

        This is a placeholder for future functionality to protect proper nouns
        from being incorrectly normalized.

        Args:
            text: Input text.
            entities: List of entity dictionaries with 'name' and 'type' keys.

        Returns:
            Text with entities preserved (currently returns original text).
        """
        # Placeholder for entity preservation logic
        # In a full implementation, this would mark entities to protect them during normalization
        logger.debug(f"Preserving {len(entities)} entities in text")
        return text

    def full_normalize(self, text: str, target_form: str = "simplified", preserve_entities: bool = True) -> str:
        """
        Perform full normalization: Traditional<->Simplified conversion followed by variant normalization.

        Args:
            text: Input text to normalize.
            target_form: Target form - "simplified" or "traditional".
            preserve_entities: Whether to preserve recognized entities during normalization.

        Returns:
            Fully normalized text.
        """
        if not text:
            return text

        entities = []
        if preserve_entities:
            # Extract entities for preservation (placeholder - would integrate with NER)
            pass

        # Step 1:繁简转换 (Traditional<->Simplified conversion)
        if target_form == "simplified":
            # Check if text appears to be Traditional
            normalized = self.traditional_to_simplified(text)
        else:
            # Convert to Traditional with specified variant
            variant = self.config.get('traditional_variant', 'tw')
            normalized = self.simplified_to_traditional(text, variant)

        # Step 2: 异体字标准化 (Variant character normalization)
        normalized = self.normalize_variants(normalized)

        # Preserve entities if requested
        if preserve_entities and entities:
            normalized = self.preserve_proper_nouns(normalized, entities)

        logger.info(f"Full normalization ({target_form}): {len(text)} -> {len(normalized)} chars")
        return normalized


def batch_normalize(texts: list, **kwargs) -> list:
    """
    Normalize a batch of texts.

    Args:
        texts: List of text strings to normalize.
        **kwargs: Additional arguments passed to TextNormalizer.full_normalize.

    Returns:
        List of normalized text strings.
    """
    normalizer = TextNormalizer()
    return [normalizer.full_normalize(text, **kwargs) for text in texts]
