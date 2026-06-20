"""Ancient book image preprocessor using OpenCV."""

import logging
from typing import List, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """Preprocessor for ancient book images."""

    def __init__(self, config: dict = None):
        """Initialize the preprocessor with configuration.

        Args:
            config: Dictionary containing preprocessing options.
                - target_dpi: Target DPI for resizing (default 300)
                - max_dimension: Maximum image dimension (default 4096)
        """
        self.config = config or {}
        self.target_dpi = self.config.get("target_dpi", 300)
        self.max_dimension = self.config.get("max_dimension", 4096)
        logger.info(
            f"ImagePreprocessor initialized with target_dpi={self.target_dpi}, "
            f"max_dimension={self.max_dimension}"
        )

    def load_image(self, image_path: str) -> np.ndarray:
        """Load an image from file and return as RGB array.

        Args:
            image_path: Path to the image file.

        Returns:
            RGB image as numpy array with values in [0, 255].
        """
        logger.info(f"Loading image from {image_path}")
        from app.utils import imread
        image = imread(image_path)
        if image is None:
            raise ValueError(f"Failed to load image from {image_path}")
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        logger.info(f"Image loaded successfully, shape: {rgb_image.shape}")
        return rgb_image

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """Preprocess the image: resize, grayscale, denoise, binarize.

        Args:
            image: Input RGB image.

        Returns:
            Binary image as numpy array.
        """
        logger.info("Starting preprocessing")

        # Resize if needed
        processed = self._resize_if_needed(image)

        # Convert to grayscale
        gray = cv2.cvtColor(processed, cv2.COLOR_RGB2GRAY)
        logger.info(f"Converted to grayscale, shape: {gray.shape}")

        # Apply median blur for denoising
        denoised = cv2.medianBlur(gray, ksize=5)
        logger.info("Applied median blur denoising")

        # Apply adaptive threshold for binarization
        binary = cv2.adaptiveThreshold(
            denoised,
            maxValue=255,
            adaptiveMethod=cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            thresholdType=cv2.THRESH_BINARY_INV,
            blockSize=11,
            C=2,
        )
        logger.info("Applied adaptive threshold binarization")

        return binary

    def _resize_if_needed(self, image: np.ndarray) -> np.ndarray:
        """Resize image if it exceeds max_dimension while preserving aspect ratio.

        Args:
            image: Input RGB image.

        Returns:
            Resized RGB image if needed, otherwise unchanged.
        """
        height, width = image.shape[:2]
        max_curr = max(height, width)

        if max_curr > self.max_dimension:
            scale = self.max_dimension / max_curr
            new_width = int(width * scale)
            new_height = int(height * scale)
            resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
            logger.info(f"Resized image from ({width}, {height}) to ({new_width}, {new_height})")
            return resized

        logger.info(f"No resizing needed, current max dimension: {max_curr}")
        return image

    def detect_skew_angle(self, binary_image: np.ndarray) -> float:
        """Detect skew angle using Hough transform on text lines.

        Args:
            binary_image: Binary image of the document.

        Returns:
            Median angle of detected lines in degrees.
        """
        logger.info("Detecting skew angle using Hough transform")

        # Apply morphological operations to connect text components
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
        dilated = cv2.dilate(binary_image, kernel, iterations=1)

        # Detect lines using HoughLines
        lines = cv2.HoughLines(
            dilated,
            rho=1,
            theta=np.pi / 180,
            threshold=100,
        )

        if lines is None or len(lines) == 0:
            logger.warning("No lines detected, returning 0.0")
            return 0.0

        # Extract angles from lines
        angles = []
        for line in lines:
            rho, theta = line[0]
            # Only consider nearly horizontal lines (theta close to 0 or pi)
            if theta < np.pi / 4 or theta > 3 * np.pi / 4:
                angle = (theta * 180 / np.pi) - 90
                angles.append(angle)

        if not angles:
            logger.warning("No suitable lines found for angle detection, returning 0.0")
            return 0.0

        median_angle = float(np.median(angles))
        logger.info(f"Detected skew angle: {median_angle:.2f} degrees")
        return median_angle

    def deskew(self, binary_image: np.ndarray, angle: float = None) -> np.ndarray:
        """Deskew the binary image by rotating by the given angle.

        Args:
            binary_image: Binary image to deskew.
            angle: Skew angle in degrees. If None, auto-detect via detect_skew_angle().

        Returns:
            Deskewed binary image.
        """
        # 任何实际倾斜都在 ±15° 之内；超出此范围的检测结果视为噪声
        # （竖排古籍的文本列容易被 Hough 误判为 -90° 倾斜，必须截断）
        MAX_DESKEW_ANGLE = 15.0

        if angle is None:
            angle = self.detect_skew_angle(binary_image)

        if abs(angle) < 0.5 or abs(angle) > MAX_DESKEW_ANGLE:
            logger.info(f"Skipping deskew: angle {angle:.2f}° out of safe range (±{MAX_DESKEW_ANGLE}°)")
            return binary_image

        logger.info(f"Deskewing image with angle: {angle:.2f} degrees")

        height, width = binary_image.shape[:2]
        center = (width / 2, height / 2)

        # Get rotation matrix
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

        # Rotate the image
        deskewed = cv2.warpAffine(
            binary_image,
            rotation_matrix,
            (width, height),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )

        logger.info("Deskewing completed")
        return deskewed

    def detect_text_regions(self, binary_image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect text regions using contour detection on dilated image.

        Args:
            binary_image: Binary image of the document.

        Returns:
            List of bounding boxes as (x1, y1, x2, y2) tuples.
        """
        logger.info("Detecting text regions using contours")

        # Apply morphological dilation to connect nearby text components
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
        dilated = cv2.dilate(binary_image, kernel, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        regions = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            # Filter out very small regions (likely noise)
            if w > 20 and h > 20:
                regions.append((x, y, x + w, y + h))

        logger.info(f"Detected {len(regions)} text regions")
        return regions

    def remove_borders(self, binary_image: np.ndarray, border_size: int = 10) -> np.ndarray:
        """Remove borders from the binary image.

        Args:
            binary_image: Binary image to process.
            border_size: Size of border to remove in pixels.

        Returns:
            Binary image with borders removed.
        """
        logger.info(f"Removing borders with size: {border_size}")

        height, width = binary_image.shape[:2]
        cropped = binary_image[
            border_size : height - border_size, border_size : width - border_size
        ]

        logger.info(f"Borders removed, new shape: {cropped.shape}")
        return cropped

    def enhance_contrast(self, gray_image: np.ndarray) -> np.ndarray:
        """Enhance contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization).

        Args:
            gray_image: Grayscale image.

        Returns:
            Contrast-enhanced grayscale image.
        """
        logger.info("Enhancing contrast using CLAHE")

        # Create CLAHE object
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        # Apply CLAHE
        enhanced = clahe.apply(gray_image)

        logger.info("Contrast enhancement completed")
        return enhanced
