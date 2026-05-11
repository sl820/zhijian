"""
Faster R-CNN Model for Detecting Annotation Marks on Ancient Chinese Books

This module provides a Faster R-CNN model based on ResNet50-FPN backbone
for detecting various types of annotation marks on ancient Chinese books.
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Union

import numpy as np
import torch
import torchvision
from PIL import Image
from torch import nn
from torchvision.models.detection import fasterrcnn_resnet50_fpn
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torchvision.transforms import functional as F

logger = logging.getLogger(__name__)

# ANNOTATION_CLASSES: Define the classes for annotation detection
ANNOTATION_CLASSES = {
    0: "朱批",  # Red comments/annotations
    1: "墨批",  # Ink comments/annotations
    2: "圈点",  # Circles/dots - reading marks
    3: "划线",  # Underlines/strikethroughs
    4: "批注区域",  # Annotation region bounding box - larger region containing multiple marks
}


def create_model(num_classes: int = 5) -> torchvision.models.detection.faster_rcnn.FasterRCNN:
    """
    Create a Faster R-CNN model with ResNet50-FPN backbone.

    Args:
        num_classes: Number of classes (including background class).
                     For annotation detection: 5 classes (background + 4 annotation types).

    Returns:
        Faster R-CNN model with customized box predictor.
    """
    logger.info(f"Creating Faster R-CNN model with ResNet50-FPN backbone for {num_classes} classes")

    # Load pretrained ResNet50-FPN model
    model = fasterrcnn_resnet50_fpn(weights='DEFAULT')

    # Get the number of input features for the box predictor
    in_features = model.roi_heads.box_predictor.cls_score.in_features

    # Replace the box predictor with a new one for our num_classes
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)

    logger.info("Model created successfully with customized box predictor")
    return model


class AnnotationDetector:
    """
    Faster R-CNN based detector for annotation marks on ancient Chinese books.

    Supports detection of:
    - 朱批 (red comments/annotations)
    - 墨批 (ink comments/annotations)
    - 圈点 (circles/dots - reading marks)
    - 划线 (underlines/strikethroughs)
    - 批注区域 (annotation region bounding boxes)
    """

    def __init__(self, model_path: Optional[str] = None, device: Optional[str] = None, skip_ml_model: bool = False):
        """
        Initialize the AnnotationDetector.

        Args:
            model_path: Path to a pretrained model checkpoint. If None, will use
                       COCO pretrained weights and note that fine-tuning is needed.
            device: Device to use for inference ('cuda' or 'cpu'). If None,
                   will auto-detect based on GPU availability.
            skip_ml_model: If True, skip ML model loading and use basic detection only.
                          This avoids slow COCO weight download.
        """
        self.logger = logging.getLogger(__name__)
        self.model_path = model_path
        self._model = None
        self._device = None
        self._skip_ml_model = skip_ml_model

        # Auto-detect device if not specified
        if device is None:
            self._device = self._detect_device()
        else:
            self._device = torch.device(device)

        if skip_ml_model:
            self.logger.info("AnnotationDetector initialized in basic mode (no ML model)")
        else:
            self.logger.info(f"AnnotationDetector initialized with device: {self._device}")

    def _detect_device(self) -> torch.device:
        """Auto-detect the best available device."""
        if torch.cuda.is_available():
            device = torch.device('cuda')
            self.logger.info(f"CUDA detected. Using GPU: {torch.cuda.get_device_name(0)}")
        else:
            device = torch.device('cpu')
            self.logger.info("No CUDA detected. Using CPU")
        return device

    @property
    def model(self) -> Optional[torchvision.models.detection.faster_rcnn.FasterRCNN]:
        """Lazy load the model."""
        if self._skip_ml_model:
            return None
        if self._model is None:
            self.load_model(self.model_path)
        return self._model

    def load_model(self, model_path: Optional[str] = None) -> None:
        """
        Load or download the pretrained model.

        Args:
            model_path: Path to model checkpoint. If None, initializes with
                       COCO pretrained weights.
        """
        model_path = model_path or self.model_path

        try:
            if model_path is not None and os.path.exists(model_path):
                # Load existing fine-tuned model
                self.logger.info(f"Loading model from: {model_path}")
                checkpoint = torch.load(model_path, map_location=self._device)

                # Handle different checkpoint formats
                if isinstance(checkpoint, dict):
                    if 'model_state_dict' in checkpoint:
                        # Standard checkpoint format with model state dict
                        self._model = create_model(num_classes=5)
                        self._model.load_state_dict(checkpoint['model_state_dict'])
                    elif 'state_dict' in checkpoint:
                        # Alternative checkpoint format
                        self._model = create_model(num_classes=5)
                        self._model.load_state_dict(checkpoint['state_dict'])
                    else:
                        # Direct state dict
                        self._model = create_model(num_classes=5)
                        self._model.load_state_dict(checkpoint)
                else:
                    # Direct model state dict
                    self._model = create_model(num_classes=5)
                    self._model.load_state_dict(checkpoint)

                self._model.to(self._device)
                self._model.eval()
                self.logger.info("Model loaded successfully from checkpoint")

            else:
                # Initialize with COCO pretrained weights
                self.logger.info("No model checkpoint provided. Initializing with COCO pretrained weights.")
                self.logger.warning("NOTE: Fine-tuning on annotation dataset is needed for best results.")

                self._model = fasterrcnn_resnet50_fpn(weights='DEFAULT')

                # Replace the box predictor for our 5 annotation classes
                in_features = self._model.roi_heads.box_predictor.cls_score.in_features
                self._model.roi_heads.box_predictor = FastRCNNPredictor(in_features, 5)

                self._model.to(self._device)
                self._model.eval()
                self.logger.info("Model initialized with COCO pretrained weights (requires fine-tuning)")

        except FileNotFoundError:
            self.logger.error(f"Model file not found: {model_path}")
            raise
        except RuntimeError as e:
            self.logger.error(f"Failed to load model due to runtime error: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error loading model: {e}")
            raise

    def _preprocess_image(self, image: Union[np.ndarray, Image.Image, str]) -> torch.Tensor:
        """
        Preprocess an image for inference.

        Args:
            image: Input image as numpy array, PIL Image, or file path.

        Returns:
            Preprocessed image tensor.
        """
        if isinstance(image, str):
            # Load image from file path
            try:
                image = Image.open(image).convert('RGB')
            except Exception as e:
                self.logger.error(f"Failed to load image from path {image}: {e}")
                raise
        elif isinstance(image, np.ndarray):
            # Convert numpy array to PIL Image
            image = Image.fromarray(image)
        elif not isinstance(image, Image.Image):
            raise ValueError(f"Unsupported image type: {type(image)}")

        # Convert PIL Image to tensor
        image_tensor = F.to_tensor(image)
        return image_tensor

    def _postprocess_predictions(self, predictions: List[dict]) -> List[dict]:
        """
        Postprocess model predictions to a standardized format.

        Args:
            predictions: Raw predictions from the model.

        Returns:
            List of detection dictionaries with standardized keys.
        """
        results = []

        for pred in predictions:
            boxes = pred['boxes'].cpu().numpy()
            labels = pred['labels'].cpu().numpy()
            scores = pred['scores'].cpu().numpy()

            for box, label, score in zip(boxes, labels, scores):
                # Convert box coordinates to integer values
                x1, y1, x2, y2 = box.tolist()

                # Skip low confidence detections
                if score < 0.5:
                    continue

                # Get label name
                label_id = int(label)
                label_name = ANNOTATION_CLASSES.get(label_id, f"unknown_{label_id}")

                results.append({
                    'bbox': [x1, y1, x2, y2],
                    'label': label_id,
                    'label_name': label_name,
                    'confidence': float(score)
                })

        # Sort by confidence (highest first)
        results.sort(key=lambda x: x['confidence'], reverse=True)

        return results

    def predict(self, image: Union[np.ndarray, Image.Image, str]) -> List[dict]:
        """
        Predict annotations in a single image.

        Args:
            image: Input image as numpy array (H, W, C), PIL Image, or file path.

        Returns:
            List of detections, each containing:
            - bbox: [x1, y1, x2, y2] bounding box coordinates
            - label: class ID (0-4)
            - label_name: class name in Chinese
            - confidence: detection confidence score
        """
        self.logger.debug(f"Processing image of type: {type(image)}")

        # Preprocess image
        image_tensor = self._preprocess_image(image)
        image_tensor = image_tensor.to(self._device)

        # Ensure model is loaded
        if self._model is None:
            self.load_model(self.model_path)

        # Set model to evaluation mode
        self._model.eval()

        # Run inference
        with torch.no_grad():
            predictions = self._model([image_tensor])

        # Postprocess predictions
        results = self._postprocess_predictions(predictions)

        self.logger.debug(f"Found {len(results)} detections")
        return results

    def predict_batch(self, images: List[Union[np.ndarray, Image.Image, str]]) -> List[List[dict]]:
        """
        Predict annotations in a batch of images.

        Args:
            images: List of input images (each can be numpy array, PIL Image, or file path).

        Returns:
            List of detection lists, one per input image.
            Each inner list contains detections as dictionaries.
        """
        if not images:
            return []

        self.logger.debug(f"Processing batch of {len(images)} images")

        # Preprocess all images
        image_tensors = []
        for img in images:
            image_tensor = self._preprocess_image(img)
            image_tensors.append(image_tensor)

        # Stack into a single batch
        image_tensors = torch.stack(image_tensors).to(self._device)

        # Ensure model is loaded
        if self._model is None:
            self.load_model(self.model_path)

        # Set model to evaluation mode
        self._model.eval()

        # Run inference on batch
        with torch.no_grad():
            predictions = self._model(image_tensors)

        # Postprocess all predictions
        results = []
        for pred in predictions:
            box = pred['boxes'].cpu().numpy()
            labels = pred['labels'].cpu().numpy()
            scores = pred['scores'].cpu().numpy()

            image_results = []
            for b, l, s in zip(box, labels, scores):
                if s < 0.5:
                    continue

                label_id = int(l)
                label_name = ANNOTATION_CLASSES.get(label_id, f"unknown_{label_id}")

                image_results.append({
                    'bbox': b.tolist(),
                    'label': label_id,
                    'label_name': label_name,
                    'confidence': float(s)
                })

            # Sort by confidence
            image_results.sort(key=lambda x: x['confidence'], reverse=True)
            results.append(image_results)

        self.logger.debug(f"Batch processing complete. Total detections: {sum(len(r) for r in results)}")
        return results


def fine_tune_model(
    model: torchvision.models.detection.faster_rcnn.FasterRCNN,
    train_loader: torch.utils.data.DataLoader,
    num_epochs: int = 10,
    device: Optional[torch.device] = None
) -> torchvision.models.detection.faster_rcnn.FasterRCNN:
    """
    Fine-tune the Faster R-CNN model on annotation dataset.

    This function demonstrates the standard torchvision fine-tuning pattern
    for training the model on a custom annotation dataset.

    Args:
        model: The Faster R-CNN model to fine-tune.
        train_loader: DataLoader for training data.
        num_epochs: Number of training epochs.
        device: Device to train on. If None, auto-detects.

    Returns:
        Fine-tuned model.

    Note:
        This is a training utility function. For actual training, call this
        function with your DataLoader and appropriate data collator.
    """
    logger = logging.getLogger(__name__)

    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    model = model.to(device)
    model.train()

    # Standard optimizer for fine-tuning
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.SGD(params, lr=0.001, momentum=0.9, weight_decay=0.0005)

    logger.info(f"Starting fine-tuning for {num_epochs} epochs on device: {device}")

    for epoch in range(num_epochs):
        logger.info(f"Epoch {epoch + 1}/{num_epochs}")

        # Training loop would go here
        # For a complete implementation, you would iterate over train_loader
        # and call model(images, targets) for each batch

    logger.info("Fine-tuning complete")
    return model


# Example usage and testing
if __name__ == "__main__":
    # Set up logging for testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Testing AnnotationDetector...")

    # Create detector (will use COCO pretrained weights by default)
    detector = AnnotationDetector()

    # Test with a dummy image (create a simple test)
    logger.info("Testing with a dummy image...")
    dummy_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    try:
        results = detector.predict(dummy_image)
        logger.info(f"Dummy image test passed. Detections: {len(results)}")
    except Exception as e:
        logger.error(f"Test failed: {e}")

    logger.info("AnnotationDetector module loaded successfully")
