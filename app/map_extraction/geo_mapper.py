"""
Geographic coordinate mapping for ancient maps.

Provides georeferencing functionality to map pixel coordinates on historical maps
to real-world geographic coordinates using control point transformations.
"""

import json
import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class GeoCoordinateMapper:
    """
    Maps pixel coordinates on a historical map to real-world geographic coordinates.

    Uses OpenCV's perspective and affine transformations to establish a mapping
    between pixel space and geographic coordinate space based on control points.
    """

    def __init__(self):
        """Initialize the GeoCoordinateMapper."""
        self._pixel_coords: Optional[np.ndarray] = None
        self._geo_coords: Optional[np.ndarray] = None
        self._transform: Optional[np.ndarray] = None
        self._inverse_transform: Optional[np.ndarray] = None
        self._transform_type: str = "none"
        self._image_size: Tuple[int, int] = (0, 0)
        self._map_bounds: Optional[Dict[str, int]] = None

    def set_reference_points(
        self,
        pixel_coords: List[Tuple[float, float]],
        geo_coords: List[Tuple[float, float]],
    ) -> None:
        """
        Set control point pairs for georeferencing.

        Args:
            pixel_coords: List of (x, y) pixel positions on the map image.
            geo_coords: List of (lon, lat) real-world geographic coordinates.

        Raises:
            ValueError: If the number of pixel and geo coordinates don't match,
                       or if there aren't enough points for the transformation.
        """
        if len(pixel_coords) != len(geo_coords):
            raise ValueError(
                f"Number of pixel coordinates ({len(pixel_coords)}) must match "
                f"number of geo coordinates ({len(geo_coords)})"
            )

        if len(pixel_coords) < 4:
            raise ValueError(
                f"At least 4 control points are required for georeferencing, "
                f"but only {len(pixel_coords)} were provided"
            )

        self._pixel_coords = np.array(pixel_coords, dtype=np.float32)
        self._geo_coords = np.array(geo_coords, dtype=np.float32)

        self._compute_transform()
        logger.info(
            f"Set {len(pixel_coords)} reference points, transform type: {self._transform_type}"
        )

    def _compute_transform(self) -> None:
        """Compute the transformation matrix based on current reference points."""
        n_points = len(self._pixel_coords)

        if n_points == 4:
            # Use perspective transform (homography) for exactly 4 points
            self._transform = cv2.getPerspectiveTransform(
                self._pixel_coords, self._geo_coords
            )
            self._transform_type = "perspective"
            # Compute inverse for geo_to_pixel
            self._inverse_transform = cv2.getPerspectiveTransform(
                self._geo_coords, self._pixel_coords
            )
        elif n_points < 8:
            # Use affine transform for 5-7 points
            self._transform, _ = cv2.estimateAffine2D(
                self._pixel_coords, self._geo_coords
            )
            self._transform_type = "affine"
            # Compute inverse
            self._inverse_transform, _ = cv2.invertAffineTransform(self._transform)
        else:
            # Use similarity/rigid transform for 8+ points (allows scale, rotation, translation)
            self._transform, _ = cv2.estimateAffine2D(
                self._pixel_coords, self._geo_coords, method=cv2.RANSAC
            )
            self._transform_type = "rigid_ransac"
            # Compute inverse
            self._inverse_transform, _ = cv2.invertAffineTransform(self._transform)

        logger.debug(
            f"Computed {self._transform_type} transform with shape {self._transform.shape}"
        )

    def pixel_to_geo(self, pixel_x: float, pixel_y: float) -> Tuple[float, float]:
        """
        Convert pixel coordinates to geographic coordinates.

        Args:
            pixel_x: X coordinate in pixel space.
            pixel_y: Y coordinate in pixel space.

        Returns:
            Tuple of (longitude, latitude) in geographic space.

        Raises:
            ValueError: If no transformation has been set up.
        """
        if self._transform is None:
            raise ValueError(
                "No transformation has been set up. "
                "Call set_reference_points() first."
            )

        # Convert to homogeneous coordinates
        pixel_point = np.array([[[pixel_x, pixel_y]]], dtype=np.float32)

        if self._transform_type == "perspective":
            geo_point = cv2.perspectiveTransform(pixel_point, self._transform)
        else:
            geo_point = cv2.transform(pixel_point, self._transform)

        return float(geo_point[0][0][0]), float(geo_point[0][0][1])

    def geo_to_pixel(self, geo_lon: float, geo_lat: float) -> Tuple[float, float]:
        """
        Convert geographic coordinates to pixel coordinates.

        Args:
            geo_lon: Longitude in geographic space.
            geo_lat: Latitude in geographic space.

        Returns:
            Tuple of (pixel_x, pixel_y) in pixel space.

        Raises:
            ValueError: If no transformation has been set up.
        """
        if self._inverse_transform is None:
            raise ValueError(
                "No transformation has been set up. "
                "Call set_reference_points() first."
            )

        # Convert to homogeneous coordinates
        geo_point = np.array([[[geo_lon, geo_lat]]], dtype=np.float32)

        if self._transform_type == "perspective":
            pixel_point = cv2.perspectiveTransform(geo_point, self._inverse_transform)
        else:
            pixel_point = cv2.transform(geo_point, self._inverse_transform)

        return float(pixel_point[0][0][0]), float(pixel_point[0][0][1])

    def apply_transform(
        self, points: Union[List[Tuple[float, float]], np.ndarray]
    ) -> np.ndarray:
        """
        Apply the transformation to a set of points.

        Args:
            points: List of (x, y) tuples or numpy array of shape (N, 2) in source space.

        Returns:
            Numpy array of transformed points in target space with shape (N, 2).

        Raises:
            ValueError: If no transformation has been set up or points format is invalid.
        """
        if self._transform is None:
            raise ValueError(
                "No transformation has been set up. "
                "Call set_reference_points() first."
            )

        if isinstance(points, list):
            points = np.array(points, dtype=np.float32)

        if points.ndim == 1:
            # Single point
            points = np.array([[[points[0], points[1]]]], dtype=np.float32)
        elif points.ndim == 2:
            # Multiple points - reshape to (N, 1, 2)
            points = np.expand_dims(points, axis=1)

        if self._transform_type == "perspective":
            transformed = cv2.perspectiveTransform(points, self._transform)
        else:
            transformed = cv2.transform(points, self._transform)

        return transformed.squeeze()

    def detect_map_bounds(self, mask: np.ndarray) -> Dict[str, int]:
        """
        Detect the outer boundary of the map from a binary mask.

        Args:
            mask: Binary mask image where map region is white (255) and
                  background is black (0). Can be a single channel or
                  3-channel image.

        Returns:
            Dictionary containing bounding box with keys: 'top', 'bottom',
            'left', 'right', 'width', 'height'.

        Raises:
            ValueError: If mask is empty or has invalid format.
        """
        if mask is None or mask.size == 0:
            raise ValueError("Mask cannot be empty")

        # Convert to grayscale if needed
        if len(mask.shape) == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)

        # Threshold to ensure binary
        _, binary = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)

        # Find contours - use RETR_EXTERNAL to find only outer contour
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            raise ValueError("No map boundary found in mask")

        # Get the largest contour (assuming map is the largest connected region)
        largest_contour = max(contours, key=cv2.contourArea)

        # Get bounding rectangle
        x, y, w, h = cv2.boundingRect(largest_contour)

        self._map_bounds = {
            "top": int(y),
            "bottom": int(y + h),
            "left": int(x),
            "right": int(x + w),
            "width": int(w),
            "height": int(h),
        }

        logger.info(
            f"Detected map bounds: {self._map_bounds['width']}x{self._map_bounds['height']} "
            f"at ({self._map_bounds['left']}, {self._map_bounds['top']})"
        )

        return self._map_bounds

    def generate_grid_lines(
        self, rows: int = 10, cols: int = 10
    ) -> Dict[str, List[Tuple[Tuple[float, float], Tuple[float, float]]]]:
        """
        Generate a coordinate grid overlay for the map.

        Args:
            rows: Number of horizontal divisions (default 10).
            cols: Number of vertical divisions (default 10).

        Returns:
            Dictionary with 'horizontal' and 'vertical' keys, each containing
            a list of line segments. Each line segment is a tuple of two points,
            where each point is (lon, lat) for geo coordinates or (x, y) for pixel
            coordinates depending on context.

        Raises:
            ValueError: If map bounds haven't been detected.
        """
        if self._map_bounds is None:
            raise ValueError(
                "Map bounds not set. Call detect_map_bounds() first."
            )

        if rows < 1 or cols < 1:
            raise ValueError("Rows and cols must be positive integers")

        bounds = self._map_bounds
        left = bounds["left"]
        right = bounds["right"]
        top = bounds["top"]
        bottom = bounds["bottom"]

        # Generate grid lines as pixel coordinates
        horizontal_lines = []
        vertical_lines = []

        # Horizontal lines (constant y, varying x)
        for i in range(rows + 1):
            y = int(top + (bottom - top) * i / rows)
            horizontal_lines.append(((float(left), float(y)), (float(right), float(y))))

        # Vertical lines (constant x, varying y)
        for j in range(cols + 1):
            x = int(left + (right - left) * j / cols)
            vertical_lines.append(((float(x), float(top)), (float(x), float(bottom))))

        logger.debug(
            f"Generated {len(horizontal_lines)} horizontal and "
            f"{len(vertical_lines)} vertical grid lines"
        )

        return {
            "horizontal": horizontal_lines,
            "vertical": vertical_lines,
        }

    def generate_geo_grid_lines(
        self, rows: int = 10, cols: int = 10
    ) -> Dict[str, List[Tuple[Tuple[float, float], Tuple[float, float]]]]:
        """
        Generate a coordinate grid overlay in geographic coordinates.

        Uses the established georeferencing to produce grid lines in
        longitude/latitude space.

        Args:
            rows: Number of horizontal divisions (default 10).
            cols: Number of vertical divisions (default 10).

        Returns:
            Dictionary with 'horizontal' and 'vertical' keys, each containing
            a list of line segments in (lon, lat) format.

        Raises:
            ValueError: If map bounds haven't been detected or transform not set.
        """
        if self._transform is None:
            raise ValueError(
                "No transformation has been set up. "
                "Call set_reference_points() first."
            )

        if self._map_bounds is None:
            raise ValueError(
                "Map bounds not set. Call detect_map_bounds() first."
            )

        bounds = self._map_bounds
        left = bounds["left"]
        right = bounds["right"]
        top = bounds["top"]
        bottom = bounds["bottom"]

        horizontal_lines = []
        vertical_lines = []

        # Horizontal lines (constant latitude, varying longitude)
        for i in range(rows + 1):
            y = top + (bottom - top) * i / rows
            p1 = self.pixel_to_geo(left, y)
            p2 = self.pixel_to_geo(right, y)
            horizontal_lines.append((p1, p2))

        # Vertical lines (constant longitude, varying latitude)
        for j in range(cols + 1):
            x = left + (right - left) * j / cols
            p1 = self.pixel_to_geo(x, top)
            p2 = self.pixel_to_geo(x, bottom)
            vertical_lines.append((p1, p2))

        return {
            "horizontal": horizontal_lines,
            "vertical": vertical_lines,
        }

    def create_geojson(
        self,
        vectors: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Convert vector features to GeoJSON format with proper CRS.

        Args:
            vectors: List of vector feature dictionaries. Each dictionary should
                    contain:
                    - 'type': Feature type ('point', 'line', 'polygon')
                    - 'coordinates': For point: (lon, lat) or [lon, lat].
                                    For line: List of [lon, lat] pairs.
                                    For polygon: List of ring lists, where each
                                    ring is a list of [lon, lat] pairs.
                    - 'properties' (optional): Dict of feature properties.
            metadata: Optional metadata dictionary to include in the GeoJSON.
                     Commonly includes 'title', 'description', 'date', etc.

        Returns:
            A GeoJSON FeatureCollection dictionary.

        Raises:
            ValueError: If vectors list is empty or contains invalid features.
        """
        if not vectors:
            raise ValueError("Vectors list cannot be empty")

        def normalize_coordinates(coords: Any) -> Any:
            """Normalize coordinates to [lon, lat] format."""
            if isinstance(coords, tuple):
                # Point coordinates
                return [float(coords[0]), float(coords[1])]
            elif isinstance(coords, list):
                if all(isinstance(c, (int, float)) for c in coords):
                    # Point coordinates as list
                    return [float(coords[0]), float(coords[1])]
                else:
                    # Line or polygon - recursively normalize
                    return [normalize_coordinates(c) for c in coords]
            return coords

        def create_feature(vector: Dict[str, Any]) -> Dict[str, Any]:
            """Create a GeoJSON feature from a vector dictionary."""
            feature_type = vector.get("type", "").lower()

            if feature_type == "point":
                geojson_type = "Point"
                coordinates = normalize_coordinates(vector["coordinates"])
            elif feature_type == "line" or feature_type == "linestring":
                geojson_type = "LineString"
                coordinates = normalize_coordinates(vector["coordinates"])
            elif feature_type == "polygon":
                geojson_type = "Polygon"
                coordinates = normalize_coordinates(vector["coordinates"])
            elif feature_type == "multipoint":
                geojson_type = "MultiPoint"
                coordinates = normalize_coordinates(vector["coordinates"])
            elif feature_type == "multiline":
                geojson_type = "MultiLineString"
                coordinates = normalize_coordinates(vector["coordinates"])
            elif feature_type == "multipolygon":
                geojson_type = "MultiPolygon"
                coordinates = normalize_coordinates(vector["coordinates"])
            else:
                raise ValueError(f"Unknown vector type: {feature_type}")

            return {
                "type": "Feature",
                "geometry": {"type": geojson_type, "coordinates": coordinates},
                "properties": vector.get("properties", {}),
            }

        features = []
        for i, vector in enumerate(vectors):
            try:
                feature = create_feature(vector)
                features.append(feature)
            except KeyError as e:
                logger.warning(f"Skipping vector {i} missing required field: {e}")
            except Exception as e:
                logger.warning(f"Skipping vector {i} due to error: {e}")

        if not features:
            raise ValueError("No valid features could be created from the provided vectors")

        geojson = {
            "type": "FeatureCollection",
            "crs": {
                "type": "name",
                "properties": {"name": "urn:ogc:def:crs:EPSG::4326"},
            },
            "features": features,
        }

        if metadata:
            geojson["metadata"] = metadata

        logger.info(f"Created GeoJSON with {len(features)} features")
        return geojson

    def set_image_size(self, width: int, height: int) -> None:
        """
        Set the image dimensions for bounds calculations.

        Args:
            width: Image width in pixels.
            height: Image height in pixels.
        """
        self._image_size = (width, height)
        logger.debug(f"Set image size to {width}x{height}")

    def get_reference_points(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get the current reference points.

        Returns:
            Tuple of (pixel_coords, geo_coords) as numpy arrays.
        """
        if self._pixel_coords is None or self._geo_coords is None:
            raise ValueError("No reference points have been set")
        return self._pixel_coords.copy(), self._geo_coords.copy()

    def get_transform_matrix(self) -> Optional[np.ndarray]:
        """
        Get the current transformation matrix.

        Returns:
            The transformation matrix, or None if not set.
        """
        return self._transform.copy() if self._transform is not None else None

    def get_transform_type(self) -> str:
        """
        Get the type of transformation being used.

        Returns:
            String describing the transform type: 'perspective', 'affine',
            'rigid_ransac', or 'none'.
        """
        return self._transform_type

    @property
    def map_bounds(self) -> Optional[Dict[str, int]]:
        """Get the detected map bounds."""
        return self._map_bounds.copy() if self._map_bounds else None
