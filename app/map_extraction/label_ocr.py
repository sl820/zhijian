"""OCR for reading text labels on ancient maps using EasyOCR."""

import logging
from typing import List, Tuple, Optional, Dict, Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Global EasyOCR reader for map labels (shared instance)
_map_label_reader = None


def _get_map_label_reader(gpu: bool = True) -> "easyocr.Reader":
    """Get or create the global EasyOCR reader for map labels."""
    global _map_label_reader

    if _map_label_reader is None:
        import easyocr

        # Map label OCR needs Chinese and English
        logger.info("Initializing EasyOCR for map labels with GPU=%s", gpu)
        _map_label_reader = easyocr.Reader(
            ['ch_sim', 'en'],
            gpu=gpu,
            model_storage_directory=None,
            download_enabled=True,
            verbose=False,
        )
        logger.info("Map label EasyOCR initialized successfully")

    return _map_label_reader


class MapLabelOCR:
    """OCR for reading text labels on ancient maps using EasyOCR."""

    TEXT_CLASS_INDEX = 5  # Class index for text labels in segmentation mask

    def __init__(self, use_angle_cls: bool = True, lang: str = 'ch_sim', gpu: bool = True):
        """
        Initialize MapLabelOCR with EasyOCR.

        Args:
            use_angle_cls: Kept for API compatibility (EasyOCR handles this internally).
            lang: Language code. Default 'ch_sim' for simplified Chinese.
            gpu: Whether to use GPU acceleration.
        """
        self._reader = None
        self._gpu = gpu
        self._lang = lang
        logger.info(f"MapLabelOCR initialized: gpu={gpu}, lang={lang}")

    def _get_reader(self):
        """Lazy-load the EasyOCR reader."""
        if self._reader is None:
            self._reader = _get_map_label_reader(gpu=self._gpu)
        return self._reader

    def detect_text_regions(
        self, mask: np.ndarray, min_area: int = 100
    ) -> List[List[int]]:
        """
        Find text label regions from mask (class 5 = text labels).

        Args:
            mask: Segmentation mask as numpy array
            min_area: Minimum bounding box area to consider as text region

        Returns:
            List of bounding boxes as [x1, y1, x2, y2] for potential text regions
        """
        if mask is None or mask.size == 0:
            logger.warning("Empty mask provided to detect_text_regions")
            return []

        # Ensure mask is grayscale
        if len(mask.shape) > 2:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)

        # Create binary mask for text class
        text_mask = (mask == self.TEXT_CLASS_INDEX).astype(np.uint8)

        # Find contours of text regions
        contours, _ = cv2.findContours(
            text_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        bboxes = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            if area >= min_area:
                bboxes.append([x, y, x + w, y + h])

        logger.debug(f"Detected {len(bboxes)} text regions with min_area={min_area}")

        return bboxes

    def _adjust_bbox(self, poly, offset_x: int, offset_y: int) -> List[int]:
        """Convert polygon points to bounding box with offset adjustment."""
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        return [
            int(offset_x + min(xs)),
            int(offset_y + min(ys)),
            int(offset_x + max(xs)),
            int(offset_y + max(ys))
        ]

    def recognize_labels(
        self, image: np.ndarray, text_regions: List[List[int]]
    ) -> List[Tuple[List[int], str, float]]:
        """
        Take list of bounding boxes, return list of (bbox, text, confidence).

        Args:
            image: Image array (H, W, C)
            text_regions: List of bounding boxes [x1, y1, x2, y2]

        Returns:
            List of (bbox, text, confidence) tuples
        """
        if image is None or image.size == 0:
            logger.warning("Empty image provided to recognize_labels")
            return []

        if not text_regions:
            logger.debug("No text regions provided")
            return []

        reader = self._get_reader()

        # Convert to RGB if needed
        if len(image.shape) == 3 and image.shape[2] == 3:
            img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = image

        results = []

        for bbox in text_regions:
            x1, y1, x2, y2 = bbox

            # Ensure bbox coordinates are within image bounds
            h, w = image.shape[:2]
            x1 = max(0, min(x1, w - 1))
            y1 = max(0, min(y1, h - 1))
            x2 = max(x1 + 1, min(x2, w))
            y2 = max(y1 + 1, min(y2, h))

            # Crop region
            roi = img_rgb[y1:y2, x1:x2]

            if roi.size == 0:
                continue

            # Run EasyOCR on region
            try:
                ocr_result = reader.readtext(roi)

                if ocr_result:
                    for item in ocr_result:
                        if item is None or len(item) < 3:
                            continue
                        poly, text, confidence = item
                        adjusted_bbox = self._adjust_bbox(poly, x1, y1)
                        results.append((adjusted_bbox, text, float(confidence)))
                else:
                    # No text detected in this region
                    results.append((bbox, "", 0.0))

            except Exception as e:
                logger.warning(f"OCR failed for region {bbox}: {e}")
                results.append((bbox, "", 0.0))

        logger.info(f"Recognized {len(results)} text labels")

        return results

    def recognize_from_image(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect and recognize all text on the map image.

        Args:
            image: Full map image array (H, W, C)

        Returns:
            List of dicts with: text, bbox, confidence, position
        """
        if image is None or image.size == 0:
            logger.warning("Empty image provided to recognize_from_image")
            return []

        reader = self._get_reader()

        # Convert to RGB if needed
        if len(image.shape) == 3 and image.shape[2] == 3:
            img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = image

        results = []

        try:
            ocr_result = reader.readtext(img_rgb)

            if ocr_result:
                for item in ocr_result:
                    if item is None or len(item) < 3:
                        continue

                    poly, text, confidence = item

                    # Convert polygon to bounding box
                    xs = [p[0] for p in poly]
                    ys = [p[1] for p in poly]
                    bbox = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]

                    # Compute center position
                    center_x = sum(xs) / len(xs)
                    center_y = sum(ys) / len(ys)

                    results.append({
                        "text": text,
                        "bbox": bbox,
                        "confidence": float(confidence),
                        "position": {
                            "center_x": float(center_x),
                            "center_y": float(center_y),
                        },
                    })

        except Exception as e:
            logger.error(f"OCR recognition failed: {e}")

        logger.info(f"Recognized {len(results)} text elements from image")

        return results
