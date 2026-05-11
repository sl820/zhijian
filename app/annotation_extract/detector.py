"""
Annotation detection pipeline for classifying and detecting annotation types
based on visual features (color, shape, location).
"""

import logging
import numpy as np
import cv2
from typing import List, Dict, Tuple, Union, Optional

logger = logging.getLogger(__name__)


# Color detection helper functions

def is_red_color(hsv_pixel: np.ndarray) -> bool:
    """
    Check if an HSV pixel is in the red color range.

    Args:
        hsv_pixel: HSV pixel array [hue, saturation, value]

    Returns:
        True if the pixel is in the red range
    """
    h, s, v = hsv_pixel

    # Red range: hue 0-20 or 340-360 (wrapped), with high saturation
    is_red_range = (h <= 20) or (h >= 340)
    is_high_saturation = s >= 100  # Adjust threshold as needed
    is_valid_value = v >= 50  # Not too dark

    return bool(is_red_range and is_high_saturation and is_valid_value)


def is_ink_color(hsv_pixel: np.ndarray) -> bool:
    """
    Check if a pixel is a dark ink color (black or dark blue/black ink).

    Args:
        hsv_pixel: HSV pixel array [hue, saturation, value]

    Returns:
        True if the pixel appears to be dark ink
    """
    h, s, v = hsv_pixel

    # Dark ink: low brightness, can have varying hue or be nearly achromatic
    is_dark = v <= 80
    # Can be black (low s) or dark blue/black ink (specific hue range)
    is_black_ink = (s <= 30 and v <= 80)
    is_blue_black_ink = (h >= 180) and (h <= 260) and (s >= 30) and (v <= 80)

    return bool(is_dark and (is_black_ink or is_blue_black_ink))


def extract_region_color(image: np.ndarray, bbox: Tuple[int, int, int, int]) -> Dict[str, float]:
    """
    Extract the dominant color from a region defined by a bounding box.

    Args:
        image: BGR image array
        bbox: Bounding box (x, y, width, height)

    Returns:
        Dictionary with dominant color info including mean_hsv, color_type
    """
    x, y, w, h = bbox
    x, y = max(0, x), max(0, y)
    x2, y2 = min(image.shape[1], x + w), min(image.shape[0], y + h)

    if x2 <= x or y2 <= y:
        return {'mean_hsv': np.array([0, 0, 0]), 'color_type': 'unknown', 'red_ratio': 0.0, 'ink_ratio': 0.0}

    region = image[y:y2, x:x2]
    hsv_region = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

    # Calculate mean HSV
    mean_hsv = np.mean(hsv_region, axis=(0, 1))

    # Calculate ratios for color classification
    hsv_flat = hsv_region.reshape(-1, 3)

    red_count = sum(1 for pixel in hsv_flat if is_red_color(pixel))
    ink_count = sum(1 for pixel in hsv_flat if is_ink_color(pixel))

    total_pixels = len(hsv_flat)
    red_ratio = red_count / total_pixels if total_pixels > 0 else 0.0
    ink_ratio = ink_count / total_pixels if total_pixels > 0 else 0.0

    # Determine dominant color type
    if red_ratio > 0.3:
        color_type = 'red_comment'
    elif ink_ratio > 0.3:
        color_type = 'ink_comment'
    else:
        color_type = 'unknown'

    return {
        'mean_hsv': mean_hsv,
        'color_type': color_type,
        'red_ratio': red_ratio,
        'ink_ratio': ink_ratio
    }


# AnnotationTypeClassifier class

class AnnotationTypeClassifier:
    """
    Classifies annotation types based on visual features including
    color, shape, and location characteristics.
    """

    def __init__(self):
        """Initialize the annotation type classifier."""
        self.color_weights = {
            'red_comment': 0.4,
            'ink_comment': 0.3,
            'circle_dot': 0.15,
            'underline': 0.15
        }
        self.shape_weights = {
            'underline': 0.4,
            'circle_dot': 0.3,
            'comment_block': 0.2,
            'unknown': 0.1
        }

    def classify_by_color(self, region: np.ndarray, image: np.ndarray) -> str:
        """
        Classify annotation type based on color characteristics.

        Uses color histogram and mean color analysis to identify:
        - Red comments: Red/orange colored annotations
        - Ink comments: Dark ink (black or blue-black) annotations
        - Circle/dot annotations: Often in red or dark ink
        - Underlines: Can be red or dark

        Args:
            region: Cropped region of the annotation (BGR image)
            image: Full original image (BGR image)

        Returns:
            Annotation type string: 'red_comment', 'ink_comment', 'circle_dot', 'underline'
        """
        hsv_region = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)

        # Calculate mean color
        mean_hsv = np.mean(hsv_region, axis=(0, 1))
        mean_h, mean_s, mean_v = mean_hsv

        # Calculate color ratios using histogram
        hsv_flat = hsv_region.reshape(-1, 3)

        red_count = sum(1 for pixel in hsv_flat if is_red_color(pixel))
        ink_count = sum(1 for pixel in hsv_flat if is_ink_color(pixel))
        total_pixels = len(hsv_flat)

        red_ratio = red_count / total_pixels if total_pixels > 0 else 0.0
        ink_ratio = ink_count / total_pixels if total_pixels > 0 else 0.0

        logger.debug(f"Color analysis - Red ratio: {red_ratio:.3f}, Ink ratio: {ink_ratio:.3f}, Mean HSV: {mean_hsv}")

        # Classification based on color characteristics
        if red_ratio > 0.25:
            return 'red_comment'
        elif ink_ratio > 0.25:
            return 'ink_comment'
        elif mean_s < 30 and mean_v > 200:
            # Light/white region - might be highlight or background
            return 'circle_dot'
        else:
            # Default classification
            return 'underline'

    def classify_by_shape(self, region: np.ndarray, image: np.ndarray) -> str:
        """
        Classify annotation type based on shape characteristics.

        Analyzes aspect ratio, area, and contour shape:
        - Long thin regions -> underline
        - Small round regions -> circle/dot
        - Large rectangular regions -> comment block

        Args:
            region: Cropped region of the annotation (BGR image)
            image: Full original image (BGR image) - used for context

        Returns:
            Annotation type string: 'underline', 'circle_dot', 'comment_block'
        """
        h, w = region.shape[:2]

        if h == 0 or w == 0:
            return 'unknown'

        # Calculate shape metrics
        aspect_ratio = w / h if h > 0 else 0
        area = w * h
        bounding_rect_area = area

        # Convert to grayscale for contour analysis
        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            # Get largest contour
            largest_contour = max(contours, key=cv2.contourArea)
            contour_area = cv2.contourArea(largest_contour)
            contour_perimeter = cv2.arcLength(largest_contour, True)

            # Calculate circularity: 4 * pi * area / perimeter^2
            if contour_perimeter > 0:
                circularity = 4 * np.pi * contour_area / (contour_perimeter ** 2)
            else:
                circularity = 0

            # Approximate contour shape
            epsilon = 0.02 * contour_perimeter
            approx = cv2.approxPolyDP(largest_contour, epsilon, True)
            num_vertices = len(approx)

            logger.debug(f"Shape analysis - Aspect ratio: {aspect_ratio:.2f}, Area: {area}, "
                         f"Circularity: {circularity:.3f}, Vertices: {num_vertices}")
        else:
            circularity = 0
            num_vertices = 0

        # Shape-based classification
        if aspect_ratio > 4 and h < 20:
            # Long thin region (horizontal line)
            return 'underline'
        elif aspect_ratio < 0.5 and w < 20:
            # Long thin region (vertical line)
            return 'underline'
        elif circularity > 0.7 and area < 1000:
            # High circularity and small area -> circle/dot
            return 'circle_dot'
        elif circularity > 0.5 and area < 500:
            return 'circle_dot'
        elif aspect_ratio > 2 and aspect_ratio < 5 and area > 2000:
            # Medium aspect ratio, large area -> comment block
            return 'comment_block'
        elif aspect_ratio > 3 and h < 15:
            # Thin horizontal line regardless of length
            return 'underline'
        else:
            return 'unknown'

    def classify(self, region: np.ndarray, image: np.ndarray, confidence: float = 0.5) -> Tuple[str, float]:
        """
        Combined classification using both color and shape analysis.

        Args:
            region: Cropped region of the annotation (BGR image)
            image: Full original image (BGR image)
            confidence: Detection confidence from the model

        Returns:
            Tuple of (annotation_type, combined_confidence)
        """
        # Handle empty or None region
        if region is None or region.size == 0:
            logger.warning("Empty region provided to classify, returning unknown")
            return ('unknown', 0.0)

        # Get classifications from both methods
        try:
            color_type = self.classify_by_color(region, image)
            shape_type = self.classify_by_shape(region, image)
        except Exception as e:
            logger.warning(f"Classification error: {e}, returning unknown")
            return ('unknown', 0.0)

        logger.debug(f"Color classification: {color_type}, Shape classification: {shape_type}")

        # Combine classifications with weights
        type_scores = {
            'red_comment': 0.0,
            'ink_comment': 0.0,
            'circle_dot': 0.0,
            'underline': 0.0,
            'comment_block': 0.0,
            'unknown': 0.0
        }

        # Add color-based score
        if color_type in type_scores:
            type_scores[color_type] += self.color_weights.get(color_type, 0.3)

        # Add shape-based score
        if shape_type in type_scores:
            type_scores[shape_type] += self.shape_weights.get(shape_type, 0.3)

        # Also consider pure color classification for red/ink comments
        hsv_region = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        mean_hsv = np.mean(hsv_region, axis=(0, 1))
        mean_h, mean_s, mean_v = mean_hsv

        hsv_flat = hsv_region.reshape(-1, 3)
        red_ratio = sum(1 for pixel in hsv_flat if is_red_color(pixel)) / len(hsv_flat) if len(hsv_flat) > 0 else 0
        ink_ratio = sum(1 for pixel in hsv_flat if is_ink_color(pixel)) / len(hsv_flat) if len(hsv_flat) > 0 else 0

        if red_ratio > 0.4:
            type_scores['red_comment'] += 0.3
        if ink_ratio > 0.4:
            type_scores['ink_comment'] += 0.3

        # Find the type with highest score
        best_type = max(type_scores, key=type_scores.get)

        # Calculate combined confidence
        base_confidence = confidence
        type_confidence = type_scores.get(best_type, 0.0)

        # Boost confidence if color and shape agree
        if color_type == shape_type and color_type not in ['unknown', 'comment_block']:
            combined_confidence = min(1.0, base_confidence * 1.2 + type_confidence * 0.3)
        else:
            combined_confidence = min(1.0, base_confidence * 0.8 + type_confidence * 0.4)

        logger.info(f"Final classification: {best_type} with confidence {combined_confidence:.3f}")

        return best_type, combined_confidence


# AnnotationDetector class

class AnnotationDetector:
    """
    High-level annotation detector combining model inference with
    post-processing, NMS, and classification.

    This detector is separate from the model in faster_rcnn_model.py and
    provides the complete detection pipeline.
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the annotation detector.

        Args:
            model_path: Optional path to a trained model. If None, uses
                      basic OpenCV-based detection.
        """
        self.model_path = model_path
        self.classifier = AnnotationTypeClassifier()
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """Load the detection model if path is provided."""
        if self.model_path is None:
            logger.info("No model path provided, using basic detection")
            return

        import torch
        if not (self.model_path.endswith('.pt') or self.model_path.endswith('.pth')):
            logger.warning(f"Unknown model format: {self.model_path}, using basic detection")
            return

        try:
            checkpoint = torch.load(self.model_path, map_location='cpu', weights_only=False)
        except Exception as e:
            logger.warning(f"Failed to load PyTorch model from {self.model_path}: {e}, using basic detection")
            self.model = None
            return

        # Handle checkpoint format from train_faster_rcnn_annotations.py
        if isinstance(checkpoint, dict):
            if 'model_state_dict' in checkpoint:
                state_dict = checkpoint['model_state_dict']
            elif 'state_dict' in checkpoint:
                state_dict = checkpoint['state_dict']
            else:
                # Direct state dict
                state_dict = checkpoint
        else:
            state_dict = checkpoint

        # Use faster_rcnn_model's create_model to build architecture, then load weights
        try:
            from .faster_rcnn_model import create_model
            self.model = create_model(num_classes=5)
            self.model.load_state_dict(state_dict)
            self.model.eval()
            logger.info(f"Loaded Faster R-CNN model from {self.model_path}")
        except Exception as e:
            logger.warning(f"Failed to load Faster R-CNN checkpoint: {e}, using basic detection")
            self.model = None

    def _preprocess_image(self, image: Union[str, np.ndarray]) -> np.ndarray:
        """
        Load and preprocess an image.

        Args:
            image: Image path or numpy array

        Returns:
            Preprocessed BGR image
        """
        if isinstance(image, str):
            import os
            from pathlib import Path
            # 解析相对路径
            if not os.path.isabs(image):
                project_root = Path(__file__).parent.parent.parent
                image = str(project_root / image)
            logger.info(f"Loading image from: {image}")
            from app.utils import imread
            img = imread(image)
            if img is None:
                raise ValueError(f"Could not read image from {image}")
            if len(img.shape) != 3 or img.shape[2] != 3:
                raise ValueError(f"Image is not a valid BGR image: shape={img.shape}")
            logger.info(f"Image loaded successfully: {img.shape}")
            return img
        elif isinstance(image, np.ndarray):
            if len(image.shape) == 2:
                # Grayscale, convert to BGR
                return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            elif len(image.shape) == 3 and image.shape[2] == 3:
                return image
            else:
                raise ValueError(f"Unexpected image shape: {image.shape}")
        else:
            raise TypeError(f"Expected str or np.ndarray, got {type(image)}")

    def _run_inference(self, image: np.ndarray) -> List[Dict]:
        """
        Run model inference on the image.

        Args:
            image: BGR image

        Returns:
            List of raw detections before filtering
        """
        if self.model is not None:
            try:
                import torch
                from PIL import Image
                import torchvision.transforms.functional as F
                if isinstance(self.model, torch.nn.Module):
                    self.model.eval()
                    # Convert BGR → RGB → PIL → tensor (Faster R-CNN expects this)
                    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(rgb)
                    img_tensor = F.to_tensor(pil_img).unsqueeze(0)
                    with torch.no_grad():
                        outputs = self.model([img_tensor.squeeze(0)])
                    detections = self._parse_torch_output(outputs)
                    return detections
            except (ImportError, Exception) as e:
                logger.warning(f"Model inference failed: {e}")

        # Fallback: Basic edge-based detection
        return self._basic_detection(image)

    def _parse_torch_output(self, outputs: list) -> List[Dict]:
        """Parse Faster R-CNN model output to standard detection format.

        Faster R-CNN output: list of dicts with 'boxes', 'labels', 'scores'
        Returns bbox in (x, y, w, h) format to match detect() expectations.
        """
        detections = []
        if not outputs or len(outputs) == 0:
            return detections

        pred = outputs[0]
        boxes = pred.get('boxes', torch.tensor([]))
        labels = pred.get('labels', torch.tensor([]))
        scores = pred.get('scores', torch.tensor([]))

        boxes = boxes.cpu().numpy()
        labels = labels.cpu().numpy()
        scores = scores.cpu().numpy()

        for box, label, score in zip(boxes, labels, scores):
            x1, y1, x2, y2 = box.tolist()
            detections.append({
                'bbox': (int(x1), int(y1), int(x2 - x1), int(y2 - y1)),  # (x, y, w, h)
                'confidence': float(score),
                'class': int(label)
            })
        return detections

    def _basic_detection(self, image: np.ndarray) -> List[Dict]:
        """
        Basic detection using OpenCV when no model is available.

        Args:
            image: BGR image

        Returns:
            List of basic detections
        """
        if image is None or image.size == 0:
            logger.warning("Empty image provided to _basic_detection")
            return []
        if len(image.shape) != 3 or image.shape[2] != 3:
            logger.warning(f"Invalid image shape for basic detection: {image.shape}")
            return []
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 100:  # Filter small contours
                continue

            x, y, w, h = cv2.boundingRect(contour)
            detections.append({
                'bbox': (x, y, w, h),
                'confidence': 0.5,
                'class': 'annotation'
            })

        return detections

    def _apply_nms(self, detections: List[Dict], iou_threshold: float = 0.5) -> List[Dict]:
        """
        Apply Non-Maximum Suppression to remove overlapping detections.

        Args:
            detections: List of detections with bbox and confidence
            iou_threshold: IoU threshold for NMS

        Returns:
            Filtered list of detections
        """
        if len(detections) <= 1:
            return detections

        # Convert to format for NMS
        boxes = []
        scores = []
        indices = []

        for i, det in enumerate(detections):
            x, y, w, h = det['bbox']
            boxes.append([x, y, x + w, y + h])
            scores.append(det['confidence'])

        boxes = np.array(boxes, dtype=np.float32)
        scores = np.array(scores, dtype=np.float32)

        # Compute IOU
        def compute_iou(box1, box2):
            x1 = max(box1[0], box2[0])
            y1 = max(box1[1], box2[1])
            x2 = min(box1[2], box2[2])
            y2 = min(box1[3], box2[3])

            intersection = max(0, x2 - x1) * max(0, y2 - y1)
            area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
            area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
            union = area1 + area2 - intersection

            return intersection / union if union > 0 else 0

        # Sort by score
        sorted_indices = np.argsort(scores)[::-1]

        keep = []
        while len(sorted_indices) > 0:
            current = sorted_indices[0]
            keep.append(current)

            if len(sorted_indices) == 1:
                break

            # Compute IOU with remaining boxes
            ious = [compute_iou(boxes[current], boxes[idx]) for idx in sorted_indices[1:]]

            # Keep boxes with IOU below threshold
            mask = np.array(ious) < iou_threshold
            sorted_indices = sorted_indices[1:][mask]

        return [detections[i] for i in keep]

    def detect(self, image: Union[str, np.ndarray]) -> List[Dict]:
        """
        Detect annotations in an image.

        Args:
            image: Image path or numpy array (BGR)

        Returns:
            List of detections with bbox, confidence, type, and full info
        """
        img = self._preprocess_image(image)

        # Run inference
        raw_detections = self._run_inference(img)

        # Filter low confidence detections
        filtered = [d for d in raw_detections if d.get('confidence', 0) >= 0.5]
        logger.info(f"After confidence filtering: {len(filtered)} detections")

        # Apply NMS
        if len(filtered) > 1:
            filtered = self._apply_nms(filtered)
            logger.info(f"After NMS: {len(filtered)} detections")

        # Classify each detection
        # If ML model provided a class, use it; otherwise fall back to rule-based
        ANNOTATION_TYPE_MAP = {
            0: ("朱批", 0.9),
            1: ("墨批", 0.9),
            2: ("圈点", 0.9),
            3: ("划线", 0.9),
            4: ("批注区域", 0.8),
        }

        results = []
        for det in filtered:
            x, y, w, h = det['bbox']
            region = img[y:y+h, x:x+w]

            if region.size == 0:
                continue

            # Use ML model's class if available, otherwise rule-based classifier
            ml_class = det.get('class')
            if ml_class is not None and self.model is not None:
                annotation_type, type_confidence = ANNOTATION_TYPE_MAP.get(
                    ml_class, ("unknown", 0.5)
                )
            else:
                annotation_type, type_confidence = self.classifier.classify(
                    region, img, det.get('confidence', 0.5)
                )

            result = {
                'bbox': det['bbox'],
                'bbox_abs': (x, y, x + w, y + h),
                'confidence': det.get('confidence', 0.5),
                'type': annotation_type,
                'type_confidence': type_confidence,
                'ml_class': ml_class,
                'width': w,
                'height': h,
                'area': w * h
            }
            results.append(result)

        logger.info(f"Final detections: {len(results)}")
        return results

    def detect_and_group(self, image: Union[str, np.ndarray],
                         distance_threshold: float = 50.0) -> List[Dict]:
        """
        Detect annotations and group nearby ones into clusters.

        Args:
            image: Image path or numpy array (BGR)
            distance_threshold: Maximum distance between annotations to group

        Returns:
            List of grouped regions with merged info
        """
        # First run detection
        detections = self.detect(image)

        if len(detections) == 0:
            return []

        # Build proximity graph and group
        def compute_distance(det1, det2):
            x1, y1 = det1['bbox'][0], det1['bbox'][1]
            x2, y2 = det2['bbox'][0], det2['bbox'][1]
            return np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)

        # Union-Find for grouping
        parent = list(range(len(detections)))

        def find(i):
            if parent[i] != i:
                parent[i] = find(parent[i])
            return parent[i]

        def union(i, j):
            pi, pj = find(i), find(j)
            if pi != pj:
                parent[pi] = pj

        # Group by proximity
        for i in range(len(detections)):
            for j in range(i + 1, len(detections)):
                if compute_distance(detections[i], detections[j]) < distance_threshold:
                    union(i, j)

        # Build groups
        groups = {}
        for i in range(len(detections)):
            p = find(i)
            if p not in groups:
                groups[p] = []
            groups[p].append(detections[i])

        # Merge grouped detections
        merged_results = []
        for group_id, group_dets in groups.items():
            if len(group_dets) == 1:
                merged_results.append(group_dets[0])
                merged_results[-1]['group_id'] = group_id
                merged_results[-1]['group_size'] = 1
            else:
                # Merge bounding boxes
                all_x = []
                all_y = []
                all_types = []
                max_confidence = 0
                total_area = 0

                for det in group_dets:
                    x, y, w, h = det['bbox']
                    all_x.extend([x, x + w])
                    all_y.extend([y, y + h])
                    all_types.append(det['type'])
                    max_confidence = max(max_confidence, det['confidence'])
                    total_area += det['area']

                merged_x = min(all_x)
                merged_y = min(all_y)
                merged_w = max(all_x) - merged_x
                merged_h = max(all_y) - merged_y

                # Majority vote for type
                type_counts = {}
                for t in all_types:
                    type_counts[t] = type_counts.get(t, 0) + 1
                dominant_type = max(type_counts, key=type_counts.get)

                merged_result = {
                    'bbox': (merged_x, merged_y, merged_w, merged_h),
                    'bbox_abs': (merged_x, merged_y, merged_x + merged_w, merged_y + merged_h),
                    'confidence': max_confidence,
                    'type': dominant_type,
                    'type_confidence': max_confidence,
                    'width': merged_w,
                    'height': merged_h,
                    'area': merged_w * merged_h,
                    'group_id': group_id,
                    'group_size': len(group_dets),
                    'num_annotations': len(group_dets),
                    'annotations': group_dets
                }
                merged_results.append(merged_result)

        logger.info(f"Grouped into {len(merged_results)} regions")
        return merged_results
