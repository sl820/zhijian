"""
Aligner module for mapping detected annotations to original book text.
Aligns annotation bounding boxes with text block positions.
"""

import logging
from typing import List, Dict, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class AnnotationAligner:
    """Handles alignment of detected annotations with original book text."""

    def __init__(self):
        """Initialize the annotation aligner."""
        logger.info("AnnotationAligner initialized.")

    def _compute_iou(
        self,
        bbox1: Tuple[int, int, int, int],
        bbox2: Tuple[int, int, int, int]
    ) -> float:
        """
        Compute Intersection over Union between two bounding boxes.

        Args:
            bbox1: First bbox as (x1, y1, x2, y2).
            bbox2: Second bbox as (x1, y1, x2, y2).

        Returns:
            IoU score between 0 and 1.
        """
        x1_1, y1_1, x2_1, y2_1 = bbox1
        x1_2, y1_2, x2_2, y2_2 = bbox2

        # Intersection coordinates
        xi1 = max(x1_1, x1_2)
        yi1 = max(y1_1, y1_2)
        xi2 = min(x2_1, x2_2)
        yi2 = min(y1_1, y2_2)

        # Compute intersection area
        inter_width = max(0, xi2 - xi1)
        inter_height = max(0, yi2 - yi1)
        inter_area = inter_width * inter_height

        # Compute union area
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union_area = area1 + area2 - inter_area

        if union_area == 0:
            return 0.0

        return inter_area / union_area

    def _compute_vertical_overlap_ratio(
        self,
        annotation_bbox: Tuple[int, int, int, int],
        text_bbox: Tuple[int, int, int, int]
    ) -> float:
        """
        Compute vertical overlap ratio between annotation and text block.

        Args:
            annotation_bbox: Annotation bounding box.
            text_bbox: Text block bounding box.

        Returns:
            Overlap ratio (0 to 1).
        """
        _, ann_y1, _, ann_y2 = annotation_bbox
        _, txt_y1, _, txt_y2 = text_bbox

        overlap_y1 = max(ann_y1, txt_y1)
        overlap_y2 = min(ann_y2, txt_y2)

        if overlap_y2 <= overlap_y1:
            return 0.0

        overlap_height = overlap_y2 - overlap_y1
        ann_height = ann_y2 - ann_y1

        if ann_height == 0:
            return 0.0

        return overlap_height / ann_height

    def align_annotation_to_text(
        self,
        annotation_bbox: Tuple[int, int, int, int],
        page_layout: Dict,
        text_blocks: List[Dict]
    ) -> Optional[Dict]:
        """
        Map an annotation bounding box to its corresponding text region.

        Args:
            annotation_bbox: Bounding box of the annotation as (x1, y1, x2, y2).
            page_layout: Pre-computed layout with text block positions.
            text_blocks: List of dicts with 'bbox' and 'text' keys.

        Returns:
            Matched text block dict or None if no match found.
        """
        if not text_blocks:
            logger.debug("No text blocks provided for alignment.")
            return None

        try:
            best_match = None
            best_score = 0.0

            for block in text_blocks:
                text_bbox = block.get('bbox')
                if not text_bbox:
                    continue

                # Compute IoU
                iou = self._compute_iou(annotation_bbox, text_bbox)

                # Also consider vertical overlap
                v_overlap = self._compute_vertical_overlap_ratio(
                    annotation_bbox, text_bbox
                )

                # Combined score favoring IoU but considering vertical alignment
                score = iou * 0.7 + v_overlap * 0.3

                if score > best_score:
                    best_score = score
                    best_match = block

            # Threshold for valid match
            if best_score > 0.1:
                logger.debug(
                    f"Aligned annotation to text with score {best_score:.3f}"
                )
                return best_match
            else:
                logger.debug("No text block exceeded alignment threshold.")
                return None

        except Exception as e:
            logger.error(f"Annotation-to-text alignment failed: {e}")
            return None

    def align_all_annotations(
        self,
        annotations: List[Dict],
        page_image: np.ndarray,
        text_blocks: List[Dict]
    ) -> List[Dict]:
        """
        Align all detected annotations to their corresponding text.

        Args:
            annotations: List of annotation dicts with 'bbox' and other info.
            page_image: Page image (used for context if needed).
            text_blocks: List of dicts with 'bbox' and 'text'.

        Returns:
            List of dicts containing annotation info with aligned text.
        """
        aligned_results = []

        for ann in annotations:
            ann_bbox = ann.get('bbox')
            if not ann_bbox:
                logger.warning("Annotation missing bbox, skipping.")
                continue

            # Align to text
            aligned_text = self.align_annotation_to_text(
                ann_bbox,
                {},  # page_layout not used in current impl
                text_blocks
            )

            result = {
                'annotation': ann,
                'aligned_text_block': aligned_text,
                'aligned_text': aligned_text.get('text') if aligned_text else None,
                'has_match': aligned_text is not None
            }
            aligned_results.append(result)

        logger.info(
            f"Aligned {len(annotations)} annotations. "
            f"{sum(1 for r in aligned_results if r['has_match'])} had text matches."
        )
        return aligned_results

    def infer_annotation_type_by_position(
        self,
        annotation_bbox: Tuple[int, int, int, int],
        page_layout: Dict,
        text_block: Dict
    ) -> str:
        """
        Infer the type of annotation based on position relative to text.

        Args:
            annotation_bbox: Bounding box of the annotation.
            page_layout: Pre-computed layout with page structure.
            text_block: The aligned text block dict.

        Returns:
            Annotation type string:
            - 'title': Above the text -> title or margin comment
            - 'footnote': Below the text -> footnote or comment
            - 'inline': Overlapping with text -> inline correction/reading mark
            - 'margin': Side margin annotation
            - 'unknown': Cannot determine
        """
        if not text_block:
            return 'unknown'

        try:
            ann_x1, ann_y1, ann_x2, ann_y2 = annotation_bbox
            txt_x1, txt_y1, txt_x2, txt_y2 = text_block.get('bbox')

            ann_center_y = (ann_y1 + ann_y2) / 2
            txt_center_y = (txt_y1 + txt_y2) / 2

            # Compute overlap
            v_overlap = self._compute_vertical_overlap_ratio(
                annotation_bbox, text_block.get('bbox')
            )

            # Horizontal overlap ratio
            h_overlap_x1 = max(ann_x1, txt_x1)
            h_overlap_x2 = min(ann_x2, txt_x2)
            h_overlap = max(0, h_overlap_x2 - h_overlap_x1)
            ann_width = ann_x2 - ann_x1
            h_overlap_ratio = h_overlap / ann_width if ann_width > 0 else 0

            # Determine type based on position
            if v_overlap > 0.5 and h_overlap_ratio > 0.5:
                return 'inline'
            elif ann_y2 < txt_y1:
                # Annotation is above text
                if ann_center_y < txt_y1 * 0.5:
                    return 'title'
                else:
                    return 'margin'
            elif ann_y1 > txt_y2:
                # Annotation is below text
                return 'footnote'
            elif h_overlap_ratio > 0.3:
                # Annotation overlaps horizontally but not vertically much
                return 'margin'
            else:
                return 'unknown'

        except Exception as e:
            logger.error(f"Annotation type inference failed: {e}")
            return 'unknown'

    def build_annotation_layer(
        self,
        annotations: List[Dict],
        aligned_texts: List[Dict]
    ) -> Dict:
        """
        Build a structured layer of all annotations with their text associations.

        Args:
            annotations: List of annotation dicts.
            aligned_texts: List of aligned text results from align_all_annotations.

        Returns:
            Hierarchical structure dict with annotations organized by type/location.
        """
        try:
            # Initialize layer structure
            layer = {
                'title_annotations': [],
                'margin_annotations': [],
                'footnote_annotations': [],
                'inline_annotations': [],
                'unmatched_annotations': [],
                'all_annotations': []
            }

            # Create lookup from annotation to aligned result
            aligned_lookup = {}
            for aligned in aligned_texts:
                ann = aligned.get('annotation', {})
                ann_id = ann.get('id', id(ann))
                aligned_lookup[ann_id] = aligned

            # Organize annotations by type
            for ann in annotations:
                ann_id = ann.get('id', id(ann))
                aligned = aligned_lookup.get(ann_id, {})

                # Infer type
                ann_type = 'unknown'
                if aligned.get('has_match') and aligned.get('aligned_text_block'):
                    ann_type = self.infer_annotation_type_by_position(
                        ann.get('bbox'),
                        {},
                        aligned.get('aligned_text_block')
                    )

                annotated_item = {
                    'annotation': ann,
                    'aligned_text': aligned.get('aligned_text'),
                    'type': ann_type
                }

                layer['all_annotations'].append(annotated_item)

                # Categorize by type
                if ann_type == 'title':
                    layer['title_annotations'].append(annotated_item)
                elif ann_type == 'margin':
                    layer['margin_annotations'].append(annotated_item)
                elif ann_type == 'footnote':
                    layer['footnote_annotations'].append(annotated_item)
                elif ann_type == 'inline':
                    layer['inline_annotations'].append(annotated_item)
                else:
                    layer['unmatched_annotations'].append(annotated_item)

            logger.info(
                f"Built annotation layer: "
                f"{len(layer['title_annotations'])} title, "
                f"{len(layer['margin_annotations'])} margin, "
                f"{len(layer['footnote_annotations'])} footnote, "
                f"{len(layer['inline_annotations'])} inline, "
                f"{len(layer['unmatched_annotations'])} unmatched"
            )

            return layer

        except Exception as e:
            logger.error(f"Annotation layer building failed: {e}")
            return {
                'title_annotations': [],
                'margin_annotations': [],
                'footnote_annotations': [],
                'inline_annotations': [],
                'unmatched_annotations': [],
                'all_annotations': []
            }
