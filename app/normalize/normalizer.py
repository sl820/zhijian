"""
Main normalization processor combining text normalization and NER.
"""

import logging
from typing import Optional

from .opencc_utils import TextNormalizer
from .ner_model import NERModel

logger = logging.getLogger(__name__)


class NormalizationProcessor:
    """
    Combined normalization processor that integrates text normalization
    with named entity recognition for proper noun preservation.
    """

    def __init__(self, config: dict = None):
        """
        Initialize the NormalizationProcessor.

        Args:
            config: Optional configuration dictionary with keys:
                - target_form: "simplified" or "traditional" (default: "simplified")
                - traditional_variant: "tw" or "hk" (default: "tw")
                - preserve_entities: bool (default: True)
                - ner_model_path: str, path to NER model (default: None, uses bert-base-chinese)
                - ner_device: str, device for NER model (default: None, auto-detect)
        """
        self.config = config or {}
        self.target_form = self.config.get('target_form', 'simplified')
        self.traditional_variant = self.config.get('traditional_variant', 'tw')
        self.preserve_entities = self.config.get('preserve_entities', True)

        # Initialize text normalizer
        self.text_normalizer = TextNormalizer(config=self.config)

        # NER model is lazy-loaded
        self.ner_model: Optional[NERModel] = None
        self._ner_model_loaded = False

        logger.info(f"NormalizationProcessor initialized with target_form={self.target_form}")

    def load_ner_model(self):
        """
        Lazy-load the NER model when needed.
        """
        if self._ner_model_loaded:
            return

        ner_config = {
            'model_path': self.config.get('ner_model_path'),
            'device': self.config.get('ner_device')
        }
        # Filter out None values
        ner_config = {k: v for k, v in ner_config.items() if v is not None}

        self.ner_model = NERModel(**ner_config)
        self.ner_model.load_ner_model()
        self._ner_model_loaded = True
        logger.info("NER model loaded in NormalizationProcessor")

    def process(self, text: str, detect_entities: bool = True) -> dict:
        """
        Process a single text with normalization and optional entity detection.

        Args:
            text: Input text to process.
            detect_entities: Whether to detect named entities (default: True).

        Returns:
            Dictionary containing:
                - text_original: Original input text
                - text_normalized: Normalized text
                - entities: List of detected entities (if detect_entities=True)
                - normalization_details: Details about the normalization applied
        """
        if not text:
            return {
                'text_original': text,
                'text_normalized': text,
                'entities': [],
                'normalization_details': {}
            }

        result = {
            'text_original': text,
            'entities': [],
            'normalization_details': {
                'target_form': self.target_form,
                'traditional_variant': self.traditional_variant if self.target_form == 'traditional' else None
            }
        }

        # Detect entities first if requested
        if detect_entities and self.preserve_entities:
            self.load_ner_model()
            entities = self.ner_model.predict(text)
            result['entities'] = entities
            logger.debug(f"Detected {len(entities)} entities: {entities}")
        else:
            entities = []

        # Perform text normalization
        normalized = self.text_normalizer.full_normalize(
            text,
            target_form=self.target_form,
            preserve_entities=self.preserve_entities
        )

        result['text_normalized'] = normalized
        result['normalization_details']['char_count_original'] = len(text)
        result['normalization_details']['char_count_normalized'] = len(normalized)

        logger.info(f"Processed text: {len(text)} -> {len(normalized)} chars, {len(entities)} entities")
        return result

    def process_batch(self, texts: list, detect_entities: bool = True) -> list:
        """
        Process a batch of texts.

        Args:
            texts: List of input texts.
            detect_entities: Whether to detect named entities for each text.

        Returns:
            List of result dictionaries (one per input text).
        """
        return [self.process(text, detect_entities=detect_entities) for text in texts]


def normalize_ocr_output(ocr_result: dict, target_form: str = "simplified") -> dict:
    """
    Normalize the output from an OCR processor.

    Args:
        ocr_result: Dictionary containing OCR output with keys like:
            - pages: List of page results, each containing 'text' field
            - doc_id: Document identifier
        target_form: Target normalization form - "simplified" or "traditional".

    Returns:
        Dictionary containing the normalized OCR result with additional fields:
            - text_original: Original OCR text
            - text_normalized: Normalized text
            - entities: Detected entities
            - normalized: Boolean indicating success
    """
    processor = NormalizationProcessor(config={'target_form': target_form})

    # Extract text from OCR result by iterating over pages
    pages = ocr_result.get('pages', [])
    if pages:
        # Concatenate text from all pages
        text = '\n'.join(page.get('text', '') for page in pages)
    else:
        text = ''

    # Process the text
    result = processor.process(text, detect_entities=True)

    # Build normalized output preserving original OCR structure
    normalized_result = {
        **ocr_result,
        'text_original': result['text_original'],
        'text_normalized': result['text_normalized'],
        'entities': result['entities'],
        'normalization_details': result['normalization_details'],
        'normalized': True
    }

    logger.info(f"Normalized OCR output: {len(text)} chars, {len(result['entities'])} entities")
    return normalized_result
