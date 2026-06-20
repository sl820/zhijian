import os
import json
import logging
from typing import Dict, List, Optional
from pathlib import Path

from .preprocess import ImagePreprocessor
from .variant_map import VARIANT_CHAR_MAP, TABOO_RULES, normalize_variant_text, detect_taboo_context
from .providers import (
    EasyOCRProvider,
    AliyunOCRProvider,
    PaddleOCRProvider,
    RapidOCRProvider,
    BaseOCRProvider,
    DEFAULT_PROVIDER,
)

logger = logging.getLogger(__name__)

# Provider 映射
_OCR_PROVIDERS = {
    "easyocr": EasyOCRProvider,
    "aliyun": AliyunOCRProvider,
    "paddleocr": PaddleOCRProvider,
    "rapidocr": RapidOCRProvider,
}


class OCRProcessor:
    def __init__(self, config: dict = None, provider: str = None):
        """
        Initialize OCRProcessor with optional configuration.

        Args:
            config: Optional configuration dictionary with keys like
                    'dpi', 'language', 'confidence_threshold', etc.
            provider: OCR provider name, one of ['easyocr', 'paddleocr', 'rapidocr', 'aliyun'].
                     Defaults to DEFAULT_PROVIDER (rapidocr if available, else easyocr).
        """
        self.config = config or {}
        self.preprocessor = ImagePreprocessor(self.config.get('preprocess', {}))

        # 选择 OCR provider
        provider_name = provider or self.config.get('provider', DEFAULT_PROVIDER)
        provider_class = _OCR_PROVIDERS.get(provider_name)

        if provider_class is None:
            logger.warning(f"Unknown OCR provider '{provider_name}', using {DEFAULT_PROVIDER}")
            provider_class = _OCR_PROVIDERS.get(DEFAULT_PROVIDER) or EasyOCRProvider
            provider_class = EasyOCRProvider

        self.ocr = provider_class(self.config.get('ocr', {}))
        logger.info(f"OCRProcessor initialized with provider={provider_name}, config={self.config}")

    def process_image(
        self,
        image_path: str,
        output_dir: str = None,
        detect_variants: bool = True,
        detect_taboo: bool = True,
        dynasty: str = None
    ) -> Dict:
        """
        Process a single image through the OCR pipeline.

        Args:
            image_path: Path to the input image file
            output_dir: Optional directory to save JSON output
            detect_variants: Whether to detect variant characters
            detect_taboo: Whether to detect taboo characters
            dynasty: Optional dynasty name for context (e.g., 'qing', 'ming')

        Returns:
            Dict with doc_id, pages containing OCR results
        """
        import uuid
        doc_id = str(uuid.uuid4())[:8]

        logger.info("Processing image: %s (doc_id: %s)", image_path, doc_id)

        # Load and preprocess
        image = self.preprocessor.load_image(image_path)
        if image is None:
            logger.error("Failed to load image: %s", image_path)
            return {'doc_id': doc_id, 'error': 'Failed to load image', 'pages': []}

        preprocessed = self.preprocessor.preprocess(image)
        deskewed = self.preprocessor.deskew(preprocessed)

        # OCR recognition
        ocr_result = self.ocr.recognize(deskewed)
        # 适配两种返回形态：
        # 1) List[Dict]（BaseOCRProvider 约定）→ 每项是 {text, confidence, bbox, polygon}
        # 2) Dict with {text, lines, chars, confidence}（旧 internal 格式）
        if isinstance(ocr_result, list):
            lines = ocr_result
            text = '\n'.join(item.get('text', '') for item in lines)
            confidences = [item.get('confidence', 0.0) for item in lines if item.get('confidence') is not None]
            ocr_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            chars = []
            for line in lines:
                line_text = line.get('text', '')
                line_conf = line.get('confidence', 0.0)
                line_bbox = line.get('bbox', [])
                for i, ch in enumerate(line_text):
                    chars.append({
                        'char': ch,
                        'bbox': line_bbox,
                        'confidence': line_conf,
                    })
        else:
            text = ocr_result.get('text', '')
            lines = ocr_result.get('lines', [])
            chars = ocr_result.get('chars', [])
            ocr_confidence = ocr_result.get('confidence', 0.0)

        # Detect variants and taboo characters
        variant_count = 0
        taboo_count = 0

        if detect_variants or detect_taboo:
            for char_info in chars:
                char = char_info.get('char', '')
                bbox = char_info.get('bbox', [])

                # Variant detection
                if detect_variants:
                    normalized = normalize_variant_text(char)
                    if normalized != char and normalized in VARIANT_CHAR_MAP:
                        char_info['is_variant'] = True
                        char_info['variant_of'] = normalized
                        variant_count += 1
                    else:
                        char_info['is_variant'] = False
                        char_info['variant_of'] = None

                # Taboo detection
                if detect_taboo:
                    taboo_details = detect_taboo_context(char, dynasty)
                    if taboo_details:
                        char_info['is_taboo'] = True
                        char_info['taboo_details'] = taboo_details
                        taboo_count += 1
                    else:
                        char_info['is_taboo'] = False
                        char_info['taboo_details'] = None

        # Build page result
        page_result = {
            'page_num': 0,
            'image_path': image_path,
            'text': text,
            'lines': lines,
            'chars': chars,
            'ocr_confidence': ocr_confidence,
            'variant_count': variant_count,
            'taboo_count': taboo_count,
            'preprocess_info': {
                'deskewed': deskewed is not None,
                'preprocessed': preprocessed is not None
            }
        }

        result = {
            'doc_id': doc_id,
            'pages': [page_result]
        }

        # Save to output_dir if specified
        if output_dir:
            self._save_result(result, output_dir, doc_id)

        logger.info(
            "Image processed: %s - chars: %d, variants: %d, taboo: %d, confidence: %.2f",
            image_path, len(chars), variant_count, taboo_count, ocr_confidence
        )

        return result

    def process_pdf(
        self,
        pdf_path: str,
        output_dir: str = None,
        start_page: int = 0,
        end_page: int = None
    ) -> Dict:
        """
        Process a PDF file by converting pages to images and OCR-ing each.

        Args:
            pdf_path: Path to the input PDF file
            output_dir: Optional directory to save JSON output
            start_page: Starting page index (0-based)
            end_page: Ending page index (inclusive), None for all pages

        Returns:
            Dict with doc_id, pages containing OCR results for each page
        """
        import uuid
        from pdf2image import convert_from_path
        doc_id = str(uuid.uuid4())[:8]

        logger.info("Processing PDF: %s (doc_id: %s)", pdf_path, doc_id)

        try:
            # Convert PDF pages to images
            images = convert_from_path(pdf_path, first_page=start_page + 1, last_page=end_page)
        except Exception as e:
            logger.error("Failed to convert PDF: %s - %s", pdf_path, str(e))
            return {'doc_id': doc_id, 'error': str(e), 'pages': []}

        pages = []
        for page_idx, image in enumerate(images):
            page_num = start_page + page_idx

            # Convert PIL image to numpy array for processing
            import numpy as np
            image_array = np.array(image)

            # Preprocess
            preprocessed = self.preprocessor.preprocess(image_array)
            deskewed = self.preprocessor.deskew(preprocessed)

            # OCR
            ocr_result = self.ocr.recognize(deskewed)
            text = ocr_result.get('text', '')
            lines = ocr_result.get('lines', [])
            chars = ocr_result.get('chars', [])
            ocr_confidence = ocr_result.get('confidence', 0.0)

            # Detect variants and taboo
            variant_count = 0
            taboo_count = 0
            for char_info in chars:
                char = char_info.get('char', '')

                normalized = normalize_variant_text(char)
                if normalized != char and normalized in VARIANT_CHAR_MAP:
                    char_info['is_variant'] = True
                    char_info['variant_of'] = normalized
                    variant_count += 1
                else:
                    char_info['is_variant'] = False
                    char_info['variant_of'] = None

                taboo_details = detect_taboo_context(char)
                if taboo_details:
                    char_info['is_taboo'] = True
                    char_info['taboo_details'] = taboo_details
                    taboo_count += 1
                else:
                    char_info['is_taboo'] = False
                    char_info['taboo_details'] = None

            page_result = {
                'page_num': page_num,
                'image_path': f"{pdf_path} (page {page_num})",
                'text': text,
                'lines': lines,
                'chars': chars,
                'ocr_confidence': ocr_confidence,
                'variant_count': variant_count,
                'taboo_count': taboo_count,
                'preprocess_info': {
                    'deskewed': deskewed is not None,
                    'preprocessed': preprocessed is not None
                }
            }
            pages.append(page_result)

            logger.info(
                "PDF page %d processed: chars: %d, variants: %d, taboo: %d",
                page_num, len(chars), variant_count, taboo_count
            )

        result = {
            'doc_id': doc_id,
            'pages': pages
        }

        if output_dir:
            self._save_result(result, output_dir, doc_id)

        logger.info("PDF processed: %s - %d pages", pdf_path, len(pages))
        return result

    def _save_result(self, result: Dict, output_dir: str, doc_id: str):
        """Save result to JSON file in output directory."""
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{doc_id}.json")
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info("Result saved to: %s", output_path)
        except Exception as e:
            logger.error("Failed to save result to %s: %s", output_path, str(e))


def batch_process_images(
    image_dir: str,
    output_dir: str,
    extensions: List[str] = [".jpg", ".jpeg", ".png", ".tif", ".tiff"]
) -> List[Dict]:
    """
    Process all images in a directory.

    Args:
        image_dir: Directory containing image files
        output_dir: Directory to save JSON outputs
        extensions: List of file extensions to process

    Returns:
        List of result dictionaries, one per image
    """
    logger.info("Batch processing images from: %s", image_dir)

    processor = OCRProcessor()
    results = []

    image_dir_path = Path(image_dir)
    if not image_dir_path.exists():
        logger.error("Image directory does not exist: %s", image_dir)
        return results

    # Collect all image files
    image_files = []
    for ext in extensions:
        image_files.extend(image_dir_path.glob(f"*{ext}"))
        image_files.extend(image_dir_path.glob(f"*{ext.upper()}"))

    logger.info("Found %d images to process", len(image_files))

    for image_path in sorted(image_files):
        try:
            result = processor.process_image(str(image_path), output_dir)
            results.append(result)
        except Exception as e:
            logger.error("Failed to process %s: %s", image_path, str(e))
            results.append({
                'doc_id': None,
                'error': str(e),
                'pages': [],
                'image_path': str(image_path)
            })

    logger.info("Batch processing complete: %d images processed", len(results))
    return results
