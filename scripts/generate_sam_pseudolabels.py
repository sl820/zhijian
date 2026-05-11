"""
SAM伪标签生成脚本

使用 MobileSAM (sam_vit_tiny) 在舆图图像上自动生成分割伪标签。
然后用这些伪标签训练 U-Net 模型。

Usage:
    python scripts/generate_sam_pseudolabels.py --data data/maps/dataset --output data/maps/pseudo_labels
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from PIL import Image
import numpy as np
import cv2
import torch
import torch.nn.functional as F
from tqdm import tqdm

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("sam_pseudolabel.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Map classes (must match unet_model.py)
# ─────────────────────────────────────────────────────────────────────────────
NUM_CLASSES = 6
CLASS_NAMES = ["背景", "河流", "山脉", "城市", "边界线", "文字标注"]

# Class mapping from SAM coco stuff categories to our classes
# SAM categories: 0=background, 1=person, 2=sky, 3=terrain, etc.
# For maps, we approximate: terrain→mountains, building→cities, road→boundaries
SAM_TO_MAP_CLASSES = {
    0: 0,   # background
    3: 2,   # terrain → mountains
    4: 2,   # mountain → mountains
    8: 3,   # building → city/settlement
    9: 4,   # road → boundary/boundary-line
    10: 1,  # bicycle → (skip)
    11: 1,  # car → (skip)
    12: 1,  # dog → (skip)
    13: 1,  # person → (skip)
    # Use raw SAM masks with additional processing
}

# ─────────────────────────────────────────────────────────────────────────────
# SAM Model Loading
# ─────────────────────────────────────────────────────────────────────────────
def load_sam_model():
    """Load MobileSAM model via transformers."""
    try:
        from transformers import SamProcessor, SamModel
        logger.info("Loading MobileSAM (sam_vit_tiny)...")

        # Use the tiny version for speed and low memory
        model_id = "facebook/sam-vit-tiny"
        processor = SamProcessor.from_pretrained(model_id)
        model = SamModel.from_pretrained(model_id)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = model.to(device)
        model.eval()

        logger.info(f"SAM loaded on {device}")
        return processor, model, device
    except Exception as e:
        logger.error(f"Failed to load SAM: {e}")
        raise RuntimeError(
            "SAM not available. Install with: pip install 'transformers>=4.35' 'accelerate'"
        )


def generate_sam_masks(image: np.ndarray, processor, model, device, points_per_side: int = 16):
    """
    Generate segmentation masks using SAM.

    Args:
        image: (H, W, 3) RGB image
        processor: SAM processor
        model: SAM model
        device: torch device
        points_per_side: SAM parameter (lower = fewer masks, faster)

    Returns:
        binary_mask: (H, W) binary segmentation
    """
    # Prepare image for SAM
    inputs = processor(image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    # Get the segmentation mask (binary)
    # SAM outputs multiple masks, use the best one
    masks = processor.image_processor.post_process_masks(
        outputs.pred_masks,
        inputs["original_sizes"],
        inputs["reshaped_input_sizes"],
    )

    # Use the first (best) mask
    if isinstance(masks, (list, tuple)):
        mask = masks[0][0]  # (1, H, W)
    else:
        mask = masks[0]

    if len(mask.shape) == 3:
        mask = mask[0]  # (H, W)

    binary_mask = mask.cpu().numpy().astype(np.uint8)
    return binary_mask


def classify_map_elements(mask: np.ndarray, image: np.ndarray) -> np.ndarray:
    """
    Classify SAM mask regions into map element classes based on
    appearance features (grayscale intensity, edges, region size).

    Args:
        mask: (H, W) binary mask from SAM
        image: (H, W, 3) RGB image

    Returns:
        class_mask: (H, W) class indices (0-5)
    """
    h, w = mask.shape
    class_mask = np.zeros((h, w), dtype=np.uint8)  # default: background (0)

    if mask.sum() == 0:
        return class_mask

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if len(image.shape) == 3 else image

    # Find connected components in the SAM mask
    mask_uint8 = (mask * 255).astype(np.uint8)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask_uint8, connectivity=8)

    # Classify each region
    for i in range(1, num_labels):  # skip background (label 0)
        region_mask = (labels == i).astype(np.uint8)
        area = stats[i, cv2.CC_STAT_AREA]
        mean_intensity = (gray * region_mask).sum() / max(region_mask.sum(), 1)
        perimeter = cv2.arcLength(cv2.findContours(region_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[0], True) if region_mask.sum() > 0 else 0

        # Classify based on characteristics
        # Small bright regions → settlements (class 3)
        if mean_intensity > 180 and area < 5000:
            class_id = 3  # city/settlement
        # Thin elongated regions → boundaries/roads (class 4)
        elif area > 0 and perimeter > 0:
            circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
            if circularity < 0.2:
                class_id = 4  # boundary/road
            elif mean_intensity > 150:
                class_id = 3  # settlement
            else:
                class_id = 2  # mountain (default gray region)
        else:
            class_id = 2  # mountain

        class_mask[region_mask > 0] = class_id

    return class_mask


def resize_mask(mask: np.ndarray, target_size: tuple) -> np.ndarray:
    """Resize mask to target size using nearest neighbor."""
    import cv2
    return cv2.resize(mask, (target_size[1], target_size[0]), interpolation=cv2.INTER_NEAREST)


# ─────────────────────────────────────────────────────────────────────────────
# Generate pseudo-labels for a dataset
# ─────────────────────────────────────────────────────────────────────────────
def generate_pseudolabels_for_split(
    image_dir: Path,
    output_dir: Path,
    processor,
    model,
    device,
    split: str = "train",
    max_images: int = None,
    points_per_side: int = 16,
    target_size: tuple = (512, 512),
):
    """
    Generate pseudo-labels for all images in a split.
    """
    img_dir = image_dir / split
    out_img_dir = output_dir / "images" / split
    out_mask_dir = output_dir / "masks" / split
    out_img_dir.mkdir(parents=True, exist_ok=True)
    out_mask_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(img_dir.glob("*.png"))
    if max_images:
        images = images[:max_images]

    logger.info(f"Processing {len(images)} {split} images...")

    for img_path in tqdm(images, desc=f"SAM {split}"):
        try:
            # Load image with PIL (handles Chinese paths)
            pil_img = Image.open(img_path).convert("RGB")
            image_np = np.array(pil_img)

            # Generate SAM mask
            sam_mask = generate_sam_masks(image_np, processor, model, device, points_per_side)

            # Classify regions
            class_mask = classify_map_elements(sam_mask, image_np)

            # Resize to target size
            class_mask_resized = resize_mask(class_mask, target_size)

            # Save mask as PNG (single channel, 0-5 values)
            out_mask_path = out_mask_dir / f"{img_path.stem}_mask.png"
            Image.fromarray(class_mask_resized).save(out_mask_path)

            # Also save a colorized preview
            preview = colorize_mask(class_mask_resized)
            preview_path = out_mask_dir / f"{img_path.stem}_preview.png"
            Image.fromarray(preview).save(preview_path)

        except Exception as e:
            logger.warning(f"Failed on {img_path.name}: {e}")
            continue

    logger.info(f"Saved pseudo-labels to {output_dir}")


def colorize_mask(mask: np.ndarray) -> np.ndarray:
    """Convert class mask to RGB color visualization."""
    # Class colors: BGR format for cv2
    colors = {
        0: (0, 0, 0),       # background - black
        1: (255, 255, 0),   # rivers - yellow
        2: (139, 90, 43),   # mountains - brown
        3: (0, 0, 255),     # cities - red
        4: (0, 255, 0),     # boundaries - green
        5: (255, 255, 0),   # text labels - yellow
    }
    h, w = mask.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    for class_id, color in colors.items():
        rgb[mask == class_id] = color
    return rgb


# ─────────────────────────────────────────────────────────────────────────────
# Convert to COCO format for training
# ─────────────────────────────────────────────────────────────────────────────
def create_rle_mask(mask: np.ndarray) -> list:
    """Convert binary mask to RLE (run-length encoding) for COCO format."""
    # Flatten row-major
    pixels = mask.flatten()
    # Pad to detect changes
    pixels = np.concatenate([[0], pixels, [0]])
    runs = np.where(pixels[1:] != pixels[:-1])[0]
    runs = runs.reshape(-1, 2)
    return runs.flatten().tolist()


def build_coco_annotations(pseudo_dir: Path, split: str = "train") -> dict:
    """Build COCO-format annotations from pseudo-label masks."""
    mask_dir = pseudo_dir / "masks" / split
    img_dir = pseudo_dir / "images" / split

    masks = sorted(mask_dir.glob("*_mask.png"))
    if not masks:
        return None

    images = []
    annotations = []
    ann_id = 1

    for img_id, mask_path in enumerate(sorted(masks), start=1):
        img_name = mask_path.stem.replace("_mask", "")
        img_path = img_dir / f"{img_name}.png"

        if not img_path.exists():
            continue

        pil_img = Image.open(img_path)
        w, h = pil_img.size

        images.append({
            "id": img_id,
            "file_name": f"{img_name}.png",
            "width": w,
            "height": h,
        })

        mask = np.array(Image.open(mask_path))
        h_m, w_m = mask.shape

        # Create annotation for each class present
        for class_id in range(1, NUM_CLASSES):  # skip background (0)
            class_mask = (mask == class_id).astype(np.uint8)
            if class_mask.sum() == 0:
                continue

            # Get bounding box
            rows = np.any(class_mask, axis=1)
            cols = np.any(class_mask, axis=0)
            if not rows.any() or not cols.any():
                continue

            rmin, rmax = np.where(rows)[0][[0, -1]]
            cmin, cmax = np.where(cols)[0][[0, -1]]

            annotations.append({
                "id": ann_id,
                "image_id": img_id,
                "category_id": class_id,
                "bbox": [int(cmin), int(rmin), int(cmax - cmin + 1), int(rmax - rmin + 1)],
                "area": int(class_mask.sum()),
                "segmentation": [],  # using bbox instead
                "iscrowd": 0,
            })
            ann_id += 1

    return {
        "info": {"description": f"古舆图伪标签数据集 - {split}", "version": "1.0", "year": 2026},
        "licenses": [{"id": 1, "name": "志鉴项目"}],
        "categories": [
            {"id": i, "name": CLASS_NAMES[i], "supercategory": "map"}
            for i in range(NUM_CLASSES)
        ],
        "images": images,
        "annotations": annotations,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Quick test
# ─────────────────────────────────────────────────────────────────────────────
def test_on_single_image(processor, model, device):
    """Test SAM on one image."""
    img_path = Path("data/maps/dataset/images/train")
    images = sorted(img_path.glob("*.png"))
    if not images:
        logger.error("No images found!")
        return

    img_path = images[0]
    logger.info(f"Testing on: {img_path.name}")

    pil_img = Image.open(img_path).convert("RGB")
    image_np = np.array(pil_img)
    logger.info(f"Image: {image_np.shape}")

    # Generate SAM mask
    sam_mask = generate_sam_masks(image_np, processor, model, device, points_per_side=16)
    logger.info(f"SAM mask: {sam_mask.shape}, positive pixels: {sam_mask.sum()}")

    # Classify
    class_mask = classify_map_elements(sam_mask, image_np)
    unique_classes = np.unique(class_mask)
    logger.info(f"Classes found: {unique_classes}")

    for c in unique_classes:
        count = (class_mask == c).sum()
        logger.info(f"  Class {c} ({CLASS_NAMES[c]}): {count} pixels")

    return class_mask


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="SAM伪标签生成")
    parser.add_argument("--data", default="data/maps/dataset", help="原始数据集目录")
    parser.add_argument("--output", default="data/maps/pseudo_labels", help="伪标签输出目录")
    parser.add_argument("--split", default="train", choices=["train", "val"], help="处理哪个split")
    parser.add_argument("--max-images", type=int, default=None, help="最多处理图片数（默认全部）")
    parser.add_argument("--points-per-side", type=int, default=16, help="SAM points_per_side参数")
    parser.add_argument("--test", action="store_true", help="仅测试SAM单图")
    args = parser.parse_args()

    data_dir = Path(args.data)
    output_dir = Path(args.output)

    # Load SAM
    processor, model, device = load_sam_model()

    # Test on single image first
    test_on_single_image(processor, model, device)

    if args.test:
        logger.info("Test mode, exiting.")
        return

    # Generate for specified split
    generate_pseudolabels_for_split(
        image_dir=data_dir / "images",
        output_dir=output_dir,
        processor=processor,
        model=model,
        device=device,
        split=args.split,
        max_images=args.max_images,
        points_per_side=args.points_per_side,
    )

    # Build COCO annotations
    coco = build_coco_annotations(output_dir, args.split)
    if coco:
        ann_path = output_dir / "annotations" / f"{args.split}.json"
        ann_path.parent.mkdir(parents=True, exist_ok=True)
        ann_path.write_text(json.dumps(coco, ensure_ascii=False, indent=2))
        logger.info(f"COCO annotations saved: {ann_path}")
        logger.info(f"  Images: {len(coco['images'])}")
        logger.info(f"  Annotations: {len(coco['annotations'])}")

    logger.info("Done!")


if __name__ == "__main__":
    main()
