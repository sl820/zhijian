"""
Normalization module for the zhijian project.

Provides text normalization (Traditional<->Simplified Chinese conversion,
variant character normalization) and named entity recognition.
"""

from .opencc_utils import TextNormalizer, batch_normalize
from .ner_model import NERModel, NER_LABELS, LABEL_TO_ID, ID_TO_LABEL
from .normalizer import NormalizationProcessor, normalize_ocr_output

__all__ = [
    'TextNormalizer',
    'batch_normalize',
    'NERModel',
    'NER_LABELS',
    'LABEL_TO_ID',
    'ID_TO_LABEL',
    'NormalizationProcessor',
    'normalize_ocr_output',
]
