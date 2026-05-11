"""Vectorization of raster segmentation masks to GeoJSON-like vector features."""

import logging
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class GeographicVectorizer:
    """Converts raster segmentation masks to vector (GeoJSON-like) features."""

    # Class index mapping to element types
    CLASS_MAPPING = {
        1: "rivers",
        2: "mountains",
        3: "cities",
        4: "boundaries",
    }

    def __init__(self):
        """Initialize the vectorizer."""
        pass

    @staticmethod
    def raster_to_vectors(mask: np.ndarray, class_names: dict = None) -> dict:
        """
        Convert a segmentation mask to vector polygons.

        Args:
            mask: Segmentation mask as numpy array (H, W) with class indices
            class_names: Optional dict mapping class indices to names

        Returns:
            dict with keys: "rivers", "mountains", "cities", "boundaries"
            Each containing list of polygon coordinates
        """
        if class_names is None:
            class_names = GeographicVectorizer.CLASS_MAPPING

        vectors = {
            "rivers": [],
            "mountains": [],
            "cities": [],
            "boundaries": [],
        }

        if mask is None or mask.size == 0:
            logger.warning("Empty mask provided to raster_to_vectors")
            return vectors

        # Ensure mask is grayscale
        if len(mask.shape) > 2:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)

        # Process each class
        for class_idx, element_type in class_names.items():
            if element_type not in vectors:
                continue

            # Create binary mask for this class
            class_mask = (mask == class_idx).astype(np.uint8)

            # Find contours
            contours, hierarchy = cv2.findContours(
                class_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            # Convert contours to polygon coordinates
            for contour in contours:
                if contour.shape[0] >= 3:
                    # Simplify polygon using Douglas-Peucker
                    simplified = GeographicVectorizer.simplify_polygons(
                        contour, tolerance=2.0
                    )
                    # Convert to list of coordinate pairs
                    polygon = [
                        [float(pt[0][0]), float(pt[0][1])]
                        for pt in simplified
                    ]
                    if len(polygon) >= 3:
                        vectors[element_type].append(polygon)

        logger.info(
            f"Vectorized mask: rivers={len(vectors['rivers'])}, "
            f"mountains={len(vectors['mountains'])}, "
            f"cities={len(vectors['cities'])}, "
            f"boundaries={len(vectors['boundaries'])}"
        )

        return vectors

    @staticmethod
    def simplify_polygons(polygon: np.ndarray, tolerance: float = 2.0) -> np.ndarray:
        """
        Simplify polygon geometry using Douglas-Peucker algorithm.

        Args:
            polygon: Contour array of shape (N, 1, 2)
            tolerance: Douglas-Peucker tolerance distance

        Returns:
            Simplified contour array
        """
        if polygon is None or len(polygon) < 3:
            return polygon

        # Flatten polygon to (N, 2) format for approxPolyDP
        epsilon = tolerance * 1.0
        simplified = cv2.approxPolyDP(polygon, epsilon, closed=True)

        return simplified

    @staticmethod
    def compute_polygon_area(polygon: list) -> float:
        """
        Compute area of polygon in pixels using shoelace formula.

        Args:
            polygon: List of [x, y] coordinate pairs

        Returns:
            Area in square pixels
        """
        if polygon is None or len(polygon) < 3:
            return 0.0

        n = len(polygon)
        area = 0.0

        for i in range(n):
            j = (i + 1) % n
            area += polygon[i][0] * polygon[j][1]
            area -= polygon[j][0] * polygon[i][1]

        return abs(area) / 2.0

    @staticmethod
    def get_element_statistics(vectors: dict) -> dict:
        """
        Return statistics (count, total_area) per element type.

        Args:
            vectors: Dictionary with element types as keys and lists of polygons as values

        Returns:
            Dictionary with statistics per element type
        """
        statistics = {}

        element_types = ["rivers", "mountains", "cities", "boundaries"]

        for element_type in element_types:
            polygons = vectors.get(element_type, [])

            total_area = 0.0
            for polygon in polygons:
                total_area += GeographicVectorizer.compute_polygon_area(polygon)

            statistics[element_type] = {
                "count": len(polygons),
                "total_area": float(total_area),
            }

        logger.debug(f"Element statistics: {statistics}")

        return statistics
