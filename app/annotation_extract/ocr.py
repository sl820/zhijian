"""
OCR module for handwritten text recognition in annotations.

Uses EasyOCR with GPU acceleration for high-quality Chinese text recognition.
"""

import logging
from typing import List, Dict, Tuple
import numpy as np
import cv2

logger = logging.getLogger(__name__)

# Global EasyOCR reader for annotations (shared instance)
_annotation_reader = None


def _get_annotation_reader(gpu: bool = True) -> "easyocr.Reader":
    """Get or create the global annotation EasyOCR reader."""
    global _annotation_reader

    if _annotation_reader is None:
        import easyocr

        # Annotation OCR needs both Chinese and English for handwritten comments
        logger.info("Initializing EasyOCR for annotations with GPU=%s", gpu)
        _annotation_reader = easyocr.Reader(
            ['ch_sim', 'en'],
            gpu=gpu,
            model_storage_directory=None,
            download_enabled=True,
            verbose=False,
        )
        logger.info("Annotation EasyOCR initialized successfully")

    return _annotation_reader


class AnnotationOCR:
    """
    OCR handler for recognizing handwritten text in annotations.

    Uses EasyOCR with GPU acceleration.
    Optimized for handwritten Chinese annotations (朱批、墨批).
    """

    def __init__(self, use_angle_cls: bool = True, lang: str = 'ch_sim', gpu: bool = True):
        """
        Initialize AnnotationOCR.

        Args:
            use_angle_cls: Kept for API compatibility (EasyOCR handles this internally).
            lang: Language code. Default 'ch_sim' for simplified Chinese.
            gpu: Whether to use GPU acceleration.
        """
        self._reader = None
        self._gpu = gpu
        self._lang = lang
        logger.info(f"AnnotationOCR initialized: gpu={gpu}, lang={lang}")

    def _get_reader(self):
        """Lazy-load the EasyOCR reader."""
        if self._reader is None:
            self._reader = _get_annotation_reader(gpu=self._gpu)
        return self._reader

    def recognize_text(
        self,
        image: np.ndarray,
        bboxes: List[Tuple[int, int, int, int]]
    ) -> List[Dict]:
        """
        Recognize text within specified bounding boxes.

        Args:
            image: Input image as numpy array (BGR format).
            bboxes: List of bounding boxes, each as (x1, y1, x2, y2).

        Returns:
            List of dicts with keys: 'bbox' (tuple), 'text' (str), 'confidence' (float).
            Returns empty list if OCR fails.
        """
        if image is None or len(bboxes) == 0:
            logger.warning("Empty image or no bounding boxes provided.")
            return []

        try:
            reader = self._get_reader()

            # Convert to RGB for EasyOCR
            if len(image.shape) == 3:
                img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                img_rgb = image

            results = []
            for bbox in bboxes:
                x1, y1, x2, y2 = bbox
                # Crop region
                crop = img_rgb[y1:y2, x1:x2]
                if crop.size == 0:
                    continue

                # Run EasyOCR on crop
                ocr_result = reader.readtext(crop)

                if ocr_result:
                    for item in ocr_result:
                        if item is None or len(item) < 3:
                            continue
                        poly, text, confidence = item
                        # Adjust bbox coordinates to original image space
                        xs = [p[0] for p in poly]
                        ys = [p[1] for p in poly]
                        adjusted_bbox = (
                            x1 + int(min(xs)),
                            y1 + int(min(ys)),
                            x1 + int(max(xs)),
                            y1 + int(max(ys))
                        )
                        results.append({
                            "bbox": adjusted_bbox,
                            "text": text,
                            "confidence": float(confidence)
                        })
                else:
                    results.append({
                        "bbox": bbox,
                        "text": "",
                        "confidence": 0.0
                    })

            logger.debug(f"Recognized {len(results)} text items from {len(bboxes)} bboxes.")
            return results

        except Exception as e:
            logger.error(f"OCR text recognition failed: {e}")
            return []

    def recognize_region(
        self,
        image: np.ndarray,
        region_bbox: Tuple[int, int, int, int]
    ) -> List[Dict]:
        """
        Recognize all text within a specified region.

        Args:
            image: Input image as numpy array.
            region_bbox: Region bounding box as (x1, y1, x2, y2).

        Returns:
            List of recognized text items with bbox, text, and confidence.
        """
        if image is None:
            logger.warning("Empty image provided.")
            return []

        try:
            reader = self._get_reader()

            x1, y1, x2, y2 = region_bbox
            crop = image[y1:y2, x1:x2]

            if crop.size == 0:
                logger.warning("Region crop is empty.")
                return []

            # Convert to RGB
            if len(crop.shape) == 3:
                crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            else:
                crop_rgb = crop

            ocr_result = reader.readtext(crop_rgb)

            if not ocr_result:
                return []

            results = []
            for item in ocr_result:
                if item is None or len(item) < 3:
                    continue
                poly, text, confidence = item
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                adjusted_bbox = (
                    x1 + int(min(xs)),
                    y1 + int(min(ys)),
                    x1 + int(max(xs)),
                    y1 + int(max(ys))
                )
                results.append({
                    "bbox": adjusted_bbox,
                    "text": text,
                    "confidence": float(confidence)
                })

            logger.debug(f"Recognized {len(results)} text items in region.")
            return results

        except Exception as e:
            logger.error(f"Region OCR recognition failed: {e}")
            return []

    def recognize_full_image(self, image: np.ndarray) -> List[Tuple]:
        """
        Detect and recognize all text on the entire page.

        Args:
            image: Input image as numpy array.

        Returns:
            List of tuples: (bbox, text, confidence).
        """
        if image is None:
            logger.warning("Empty image provided.")
            return []

        try:
            reader = self._get_reader()

            # Convert to RGB
            if len(image.shape) == 3:
                img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                img_rgb = image

            ocr_result = reader.readtext(img_rgb)

            if not ocr_result:
                logger.debug("No text detected in full image.")
                return []

            results = []
            for item in ocr_result:
                if item is None or len(item) < 3:
                    continue
                poly, text, confidence = item
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                bbox = (int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys)))
                results.append((bbox, text, float(confidence)))

            logger.info(f"Full image OCR: detected {len(results)} text regions.")
            return results

        except Exception as e:
            logger.error(f"Full image OCR failed: {e}")
            return []
