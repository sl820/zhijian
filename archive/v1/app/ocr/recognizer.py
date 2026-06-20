"""
EasyOCR-based ancient book recognizer.

GPU-accelerated OCR using EasyOCR with RTX/GeForce GPU support.
Provides excellent Chinese text recognition quality.
"""

import logging
from typing import List, Dict, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Global EasyOCR reader instance (lazy-loaded, shared across calls)
_easyocr_reader = None


def _get_easyocr_reader(gpu: bool = True, languages: List[str] = None) -> "easyocr.Reader":
    """
    Get or create the global EasyOCR reader instance.

    Args:
        gpu: Whether to use GPU acceleration.
        languages: List of language codes. Defaults to ['ch_sim', 'en'].

    Returns:
        EasyOCR Reader instance.
    """
    global _easyocr_reader

    if _easyocr_reader is None:
        import easyocr

        languages = languages or ['ch_sim', 'en']
        logger.info(f"Initializing EasyOCR with GPU={gpu}, languages={languages}")

        _easyocr_reader = easyocr.Reader(
            languages,
            gpu=gpu,
            model_storage_directory=None,  # Use default ~/.EasyOCR/model
            download_enabled=True,
            detector=True,  # Enable text detection
            recognizer=True,  # Enable text recognition
            verbose=False,
        )
        logger.info("EasyOCR initialized successfully")

    return _easyocr_reader


class AncientBookOCR:
    """
    Ancient book OCR recognizer using EasyOCR.

    GPU-accelerated with RTX/GeForce GPU support for fast inference.
    Excellent Chinese (simplified/traditional) text recognition quality.

    Args:
        use_angle_cls: Whether to detect text angle/direction. EasyOCR handles this automatically.
        lang: Language code. 'ch_sim' for simplified Chinese, 'ch_tra' for traditional.
              Default 'ch_sim' matches the project's focus on Chinese gazetteers.
    """

    def __init__(
        self,
        use_angle_cls: bool = True,
        lang: str = "ch_sim",
        gpu: bool = True,
    ):
        """
        Initialize the AncientBookOCR recognizer.

        Args:
            use_angle_cls: Kept for API compatibility (EasyOCR always detects angles).
            lang: Language for OCR. Use 'ch_sim' (simplified Chinese) or 'ch_tra' (traditional).
                  You can also use 'ch_sim+en' for mixed Chinese-English.
            gpu: Whether to use GPU acceleration. Default True for RTX/GeForce GPUs.
        """
        self.lang = lang
        self.gpu = gpu
        self._reader = None  # Lazy-loaded

        # Build full language list
        if '+' in lang:
            self.languages = lang.split('+')
        else:
            self.languages = [lang]

        logger.info(
            f"AncientBookOCR initialized: lang={self.lang}, "
            f"languages={self.languages}, gpu={self.gpu}"
        )

    def _get_reader(self):
        """Lazy-load the EasyOCR reader."""
        if self._reader is None:
            self._reader = _get_easyocr_reader(gpu=self.gpu, languages=self.languages)
        return self._reader

    def recognize(self, image: np.ndarray) -> List[Dict]:
        """
        Recognize text in an image using EasyOCR.

        Args:
            image: numpy array of shape (H, W, C) in RGB format.
                   If BGR, will be converted internally.

        Returns:
            List of dictionaries, each containing:
                - text: recognized text string
                - confidence: confidence score (0-1)
                - bbox: bounding box [x1, y1, x2, y2]
                - polygon: polygon points (4 corner points from EasyOCR)
        """
        reader = self._get_reader()

        # Ensure RGB format for EasyOCR
        if len(image.shape) == 3 and image.shape[2] == 3:
            # EasyOCR expects RGB
            img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = image

        logger.debug(f"Running EasyOCR on image with shape {image.shape}")

        try:
            # EasyOCR returns list of [bbox, text, confidence]
            results = reader.readtext(img_rgb)

            if not results:
                logger.debug("No text detected in image")
                return []

            parsed_results = []
            for item in results:
                if item is None or len(item) < 3:
                    continue

                # EasyOCR result format: (bbox, text, confidence)
                # bbox is a list of 4 corner points [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                bbox_points = item[0]
                text = item[1]
                confidence = float(item[2]) if len(item) > 2 else 0.0

                # Convert 4-point polygon to bounding box [x1, y1, x2, y2]
                xs = [p[0] for p in bbox_points]
                ys = [p[1] for p in bbox_points]
                x1, y1 = min(xs), min(ys)
                x2, y2 = max(xs), max(ys)
                bbox = [int(x1), int(y1), int(x2), int(y2)]

                parsed_results.append({
                    "text": text,
                    "confidence": confidence,
                    "bbox": bbox,
                    "polygon": [[int(p[0]), int(p[1])] for p in bbox_points],
                })

            logger.debug(f"EasyOCR recognized {len(parsed_results)} text regions")
            return parsed_results

        except Exception as e:
            logger.error(f"EasyOCR recognition failed: {e}")
            return []

    def recognize_batch(self, images: List[np.ndarray]) -> List[List[Dict]]:
        """
        Recognize text in multiple images (batch processing).

        Args:
            images: List of numpy arrays (RGB format).

        Returns:
            List of result lists (one per image).
        """
        reader = self._get_reader()

        # Convert all to RGB
        rgb_images = []
        for img in images:
            if len(img.shape) == 3 and img.shape[2] == 3:
                rgb_images.append(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            else:
                rgb_images.append(img)

        try:
            # EasyOCR batch inference - much faster than calling recognize() in loop
            batch_results = reader.readtext_batch(rgb_images)

            all_parsed = []
            for results in batch_results:
                if not results:
                    all_parsed.append([])
                    continue

                parsed_results = []
                for item in results:
                    if item is None or len(item) < 3:
                        continue

                    bbox_points = item[0]
                    text = item[1]
                    confidence = float(item[2]) if len(item) > 2 else 0.0

                    xs = [p[0] for p in bbox_points]
                    ys = [p[1] for p in bbox_points]
                    x1, y1 = min(xs), min(ys)
                    x2, y2 = max(xs), max(ys)
                    bbox = [int(x1), int(y1), int(x2), int(y2)]

                    parsed_results.append({
                        "text": text,
                        "confidence": confidence,
                        "bbox": bbox,
                        "polygon": [[int(p[0]), int(p[1])] for p in bbox_points],
                    })

                all_parsed.append(parsed_results)

            return all_parsed

        except Exception as e:
            logger.error(f"EasyOCR batch recognition failed: {e}")
            return [[] for _ in images]

    def recognize_with_chars(self, image: np.ndarray) -> List[Dict]:
        """
        Perform character-level recognition by estimating character width from line bbox.

        Note: EasyOCR does not provide character-level bounding boxes natively.
        This method estimates character positions by dividing the line bbox evenly.

        Args:
            image: numpy array of shape (H, W, C) in RGB format.

        Returns:
            List of dictionaries with char-level results appended under "chars" key.
        """
        line_results = self.recognize(image)

        for line in line_results:
            text = line["text"]
            polygon = line["polygon"]
            bbox = line["bbox"]

            if len(text) == 0:
                line["chars"] = []
                continue

            # Estimate character width from line bounding box
            line_width = bbox[2] - bbox[0]
            char_width = line_width / len(text) if len(text) > 0 else 10

            # Estimate character height from line bounding box
            line_height = bbox[3] - bbox[1]

            chars = []
            x_start = bbox[0]

            for i, char in enumerate(text):
                char_bbox = [
                    int(x_start + i * char_width),
                    bbox[1],
                    int(x_start + (i + 1) * char_width),
                    bbox[3],
                ]
                # Approximate polygon for each character
                char_polygon = [
                    [char_bbox[0], bbox[1]],
                    [char_bbox[2], bbox[1]],
                    [char_bbox[2], bbox[3]],
                    [char_bbox[0], bbox[3]],
                ]
                chars.append({
                    "char": char,
                    "bbox": char_bbox,
                    "polygon": char_polygon,
                    "confidence": line["confidence"],
                })

            line["chars"] = chars

        logger.debug(f"Character-level recognition completed for {len(line_results)} lines")
        return line_results


def visualize_ocr_results(
    image: np.ndarray,
    ocr_results: List[Dict],
    output_path: str = None,
) -> np.ndarray:
    """
    Visualize OCR results on the image.

    Args:
        image: numpy array of shape (H, W, C) in RGB format.
        ocr_results: List of OCR result dictionaries from recognize().
        output_path: If provided, save the visualization to this path.

    Returns:
        The image with visualized OCR results (in BGR format for cv2).
    """
    # Convert to BGR for cv2 if RGB
    if len(image.shape) == 3 and image.shape[2] == 3:
        vis_image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    else:
        vis_image = image.copy()

    for result in ocr_results:
        polygon = result["polygon"]
        text = result["text"]
        confidence = result["confidence"]

        # Choose color based on confidence
        if confidence > 0.8:
            color = (0, 255, 0)  # Green for high confidence
        else:
            color = (0, 165, 255)  # Orange for low confidence

        # Draw polygon
        pts = np.array(polygon, dtype=np.int32)
        cv2.polylines(vis_image, [pts], isClosed=True, color=color, thickness=2)

        # Add text label with background
        if len(text) > 0:
            x_min = min(p[0] for p in polygon)
            y_min = min(p[1] for p in polygon)

            label = f"{text[:20]} ({confidence:.2f})" if len(text) > 20 else f"{text} ({confidence:.2f})"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (label_w, label_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)

            # Draw background rectangle for text
            cv2.rectangle(
                vis_image,
                (x_min, y_min - label_h - baseline - 5),
                (x_min + label_w, y_min),
                color,
                -1,
            )

            # Draw text
            cv2.putText(
                vis_image,
                label,
                (x_min, y_min - baseline - 2),
                font,
                font_scale,
                (255, 255, 255),
                thickness,
            )

    # Save if output path provided
    if output_path is not None:
        cv2.imwrite(output_path, vis_image)
        logger.info(f"Visualization saved to {output_path}")

    return vis_image
