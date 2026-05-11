"""
Segmentation pipeline for ancient Chinese maps.
"""

import logging
import sys
from pathlib import Path
from typing import List, Union, Dict, Any, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# CLASS_COLORS: color mapping for visualization
# Format: {class_name: (B, G, R)}
CLASS_COLORS = {
    "background": (0, 0, 0),
    "rivers": (0, 255, 255),
    "mountains": (139, 90, 43),
    "cities": (255, 0, 0),
    "boundaries": (0, 255, 0),
    "text_labels": (255, 255, 0),
}

CLASS_NAMES = list(CLASS_COLORS.keys())

# ImageNet normalization values
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406])
IMAGENET_STD = np.array([0.229, 0.224, 0.225])

INPUT_SIZE = (512, 512)


class MapSegmenter:
    """
    Segmentation model for ancient Chinese maps.

    Supports segmentation of rivers, mountains, cities, boundaries, and text labels.
    """

    def __init__(self, model_path: str = None):
        """
        Initialize the segmenter with lazy model loading.

        Args:
            model_path: Path to the trained segmentation model checkpoint.
                      If None, model loading will be skipped and a warning issued.
        """
        self.model_path = model_path
        self._model = None
        self._device = None

    @property
    def model(self):
        """Lazy load the model on first access."""
        if self._model is None:
            self._load_model()
        return self._model

    def _load_model(self):
        """Load the segmentation model from disk."""
        if self.model_path is None:
            logger.warning(
                "No model_path provided to MapSegmenter. "
                "Segmentation will return placeholder output."
            )
            return

        try:
            import torch

            state_dict = torch.load(self.model_path, map_location="cpu", weights_only=False)
            # Handle checkpoint format (with 'model_state_dict' key) vs raw state_dict
            if isinstance(state_dict, dict) and 'model_state_dict' in state_dict:
                state_dict = state_dict['model_state_dict']

            # Determine which model class to use based on state_dict keys
            first_key = next(iter(state_dict.keys()), "")
            if first_key.startswith('model.'):
                # AncientMapUNet format
                try:
                    from .unet_model import AncientMapUNet
                    self._model = AncientMapUNet(pretrained_encoder=False)
                    self._model.load_state_dict(state_dict)
                    self._model.eval()
                    logger.info(f"Loaded AncientMapUNet from {self.model_path}")
                    return
                except Exception as e:
                    logger.warning(f"AncientMapUNet load failed: {e}")

            # Try SimpleUNet format (enc1.0.weight, dec1.0.weight, etc.)
            try:
                # Import SimpleUNet from training script
                import sys as _sys
                script_path = Path(__file__).parent.parent.parent / "scripts" / "train_unet_maps.py"
                if script_path.exists():
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("train_unet_scripts", script_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    SimpleUNet = module.SimpleUNet
                    self._model = SimpleUNet(in_channels=3, num_classes=6)
                    self._model.load_state_dict(state_dict)
                    self._model.eval()
                    logger.info(f"Loaded SimpleUNet from {self.model_path}")
                    return
            except Exception as e:
                logger.warning(f"SimpleUNet load failed: {e}")

            # Fallback - try AncientMapUNet anyway
            try:
                from .unet_model import AncientMapUNet
                self._model = AncientMapUNet(pretrained_encoder=False)
                self._model.load_state_dict(state_dict)
                self._model.eval()
                logger.info(f"Loaded AncientMapUNet (fallback) from {self.model_path}")
            except Exception as e:
                logger.warning(
                    f"Failed to load model from {self.model_path}: {e}. "
                    "Segmentation will return placeholder output."
                )
                self._model = None

        except FileNotFoundError:
            logger.warning(
                f"Model file not found at {self.model_path}. "
                "Segmentation will return placeholder output."
            )
            self._model = None
        except Exception as e:
            logger.warning(
                f"Failed to load model from {self.model_path}: {e}. "
                "Segmentation will return placeholder output."
            )
            self._model = None

    def _preprocess_image(
        self, image: np.ndarray
    ) -> Tuple[np.ndarray, float, Tuple[int, int]]:
        """
        Preprocess image for inference.

        Args:
            image: Input image in RGB format, shape (H, W, 3).

        Returns:
            Tuple of (preprocessed tensor, scale factor, original size).
        """
        orig_h, orig_w = image.shape[:2]

        # Resize to model input size
        resized = cv2.resize(image, INPUT_SIZE, interpolation=cv2.INTER_LINEAR)

        # Convert RGB to BGR for models expecting BGR
        bgr = cv2.cvtColor(resized, cv2.COLOR_RGB2BGR)

        # Normalize with ImageNet mean/std
        normalized = (bgr / 255.0 - IMAGENET_MEAN) / IMAGENET_STD

        # Convert to CHW format
        transposed = np.transpose(normalized, (2, 0, 1))

        return transposed, 1.0, (orig_w, orig_h)

    def _postprocess_output(
        self, output: np.ndarray, scale: float, orig_size: Tuple[int, int]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Postprocess model output to get mask and probabilities.

        Args:
            output: Model output tensor of shape (C, H, W).
            scale: Scale factor from preprocessing.
            orig_size: Original image size (width, height).

        Returns:
            Tuple of (mask of shape (H, W) with class IDs,
                     probabilities of shape (6, H, W)).
        """
        # Apply softmax to get probabilities
        exp_output = np.exp(output - np.max(output, axis=0, keepdims=True))
        probabilities = exp_output / np.sum(exp_output, axis=0, keepdims=True)

        # Get class IDs from argmax
        mask = np.argmax(probabilities, axis=0).astype(np.uint8)

        # Resize mask back to original size
        orig_w, orig_h = orig_size
        mask = cv2.resize(
            mask, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST
        )

        # Resize probabilities (C, H, W)
        probs_resized = np.zeros(
            (probabilities.shape[0], orig_h, orig_w), dtype=np.float32
        )
        for c in range(probabilities.shape[0]):
            probs_resized[c] = cv2.resize(
                probabilities[c].astype(np.float32),
                (orig_w, orig_h),
                interpolation=cv2.INTER_LINEAR,
            )

        return mask, probs_resized

    def segment(
        self, image: Union[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """
        Segment a single image.

        Args:
            image: Either a path to an image file or an RGB numpy array (H, W, 3).

        Returns:
            Dictionary containing:
                - 'mask': numpy array of shape (H, W) with class IDs (0-5).
                - 'probabilities': numpy array of shape (6, H, W) with class probabilities.
        """
        # Load image if path is provided
        if isinstance(image, str):
            from app.utils import imread
            img = imread(image)
            if img is None:
                logger.error(f"Failed to load image from {image}")
                raise ValueError(f"Could not load image from {image}")
            # Convert BGR to RGB
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            img = image.copy()

        # Handle grayscale images
        if len(img.shape) == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        elif img.shape[2] == 4:
            # RGBA to RGB
            img = img[:, :, :3]

        # Preprocess
        preprocessed, scale, orig_size = self._preprocess_image(img)

        # Check if model is available (use .model property to trigger lazy loading)
        if self.model is None:
            h, w = img.shape[:2]
            return {
                "mask": np.zeros((h, w), dtype=np.uint8),
                "probabilities": np.zeros((len(CLASS_NAMES), h, w), dtype=np.float32),
            }

        # Run inference
        try:
            import torch

            with torch.no_grad():
                input_tensor = torch.from_numpy(preprocessed).unsqueeze(0).float()
                output = self.model(input_tensor)
                output = output.squeeze(0).numpy()
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            h, w = img.shape[:2]
            return {
                "mask": np.zeros((h, w), dtype=np.uint8),
                "probabilities": np.zeros((len(CLASS_NAMES), h, w), dtype=np.float32),
            }

        # Postprocess
        mask, probabilities = self._postprocess_output(output, scale, orig_size)

        return {
            "mask": mask,
            "probabilities": probabilities,
        }

    def segment_batch(
        self, images: List[Union[str, np.ndarray]]
    ) -> List[Dict[str, np.ndarray]]:
        """
        Segment a batch of images.

        Args:
            images: List of image paths or RGB numpy arrays.

        Returns:
            List of result dictionaries, one per image.
        """
        results = []
        for img_path in images:
            try:
                result = self.segment(img_path)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to segment image {img_path}: {e}")
                # Return placeholder on failure
                results.append(
                    {
                        "mask": np.zeros((512, 512), dtype=np.uint8),
                        "probabilities": np.zeros(
                            (len(CLASS_NAMES), 512, 512), dtype=np.float32
                        ),
                    }
                )
        return results

    def visualize_segmentation(
        self, image: np.ndarray, mask: np.ndarray, alpha: float = 0.5
    ) -> np.ndarray:
        """
        Create a visualization of the segmentation mask overlaid on the image.

        Args:
            image: RGB image of shape (H, W, 3).
            mask: Segmentation mask of shape (H, W) with class IDs.
            alpha: Transparency factor for the overlay.

        Returns:
            RGB image with color-coded segmentation overlay.
        """
        if image is None or mask is None:
            raise ValueError("image and mask must be provided")

        # Ensure image is RGB
        if len(image.shape) == 2:
            vis_image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        elif image.shape[2] == 4:
            vis_image = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2RGB)
        elif image.shape[2] == 3 and image.dtype == np.uint8:
            # Check if BGR or RGB by looking at typical values
            # For safety, assume RGB as per docstring
            vis_image = image.copy()
        else:
            vis_image = image.copy()

        # Create color overlay
        overlay = np.zeros((*mask.shape, 3), dtype=np.uint8)
        for class_id, (class_name, color) in enumerate(CLASS_COLORS.items()):
            overlay[mask == class_id] = color

        # Resize overlay to match image if needed
        if overlay.shape[:2] != vis_image.shape[:2]:
            overlay = cv2.resize(
                overlay, (vis_image.shape[1], vis_image.shape[0])
            )

        # Blend with original image
        blended = cv2.addWeighted(vis_image, 1 - alpha, overlay, alpha, 0)

        return blended

    def extract_geographic_elements(
        self, mask: np.ndarray, min_area: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Extract geographic elements from a segmentation mask.

        Args:
            mask: Segmentation mask of shape (H, W) with class IDs.
            min_area: Minimum contour area to be considered an element.

        Returns:
            List of dictionaries, each containing:
                - 'class_id': Integer class ID (0-5).
                - 'class_name': String name of the class.
                - 'bbox': Bounding box as (x, y, w, h).
                - 'center': Center point as (cx, cy).
                - 'area': Area of the element in pixels.
        """
        elements = []

        for class_id, class_name in enumerate(CLASS_NAMES):
            # Create binary mask for this class
            class_mask = (mask == class_id).astype(np.uint8)

            # Find contours
            contours, _ = cv2.findContours(
                class_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )

            # Process each contour
            for contour in contours:
                area = cv2.contourArea(contour)
                if area < min_area:
                    continue

                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)

                # Get center using moments
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                else:
                    cx = x + w // 2
                    cy = y + h // 2

                elements.append(
                    {
                        "class_id": class_id,
                        "class_name": class_name,
                        "bbox": (x, y, w, h),
                        "center": (cx, cy),
                        "area": int(area),
                    }
                )

        # Sort by area (largest first)
        elements.sort(key=lambda e: e["area"], reverse=True)

        return elements
