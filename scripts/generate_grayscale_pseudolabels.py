"""
规则伪标签生成脚本 - 适用于灰度扫描舆图

利用边缘检测、形态学操作、连通域分析在黑白扫描图像上生成伪标签。
无需网络下载，不依赖预训练模型。

Classes:
    0: 背景 (白色区域)
    1: 河流 (蓝色线/深色细线)
    2: 山脉 (棕色/深色块状)
    3: 城市/聚落 (小方块/圆点)
    4: 边界线/道路 (线条)
    5: 文字标注 (密集小块文字区)

Usage:
    python scripts/generate_grayscale_pseudolabels.py --data data/maps/dataset --output data/maps/pseudo_labels
"""

import argparse
import json
import logging
import os
from pathlib import Path
from PIL import Image
import numpy as np
import cv2
from tqdm import tqdm

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("grayscale_pseudolabel.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

NUM_CLASSES = 6
CLASS_NAMES = ["背景", "河流", "山脉", "城市", "边界线", "文字标注"]
TARGET_SIZE = (512, 512)


# ─────────────────────────────────────────────────────────────────────────────
# Core: Rule-based mask generation for grayscale maps
# ─────────────────────────────────────────────────────────────────────────────
def load_image_as_gray(img_path: Path) -> np.ndarray:
    """Load image as grayscale using PIL (handles Chinese paths)."""
    pil_img = Image.open(img_path).convert("L")  # Force grayscale
    return np.array(pil_img)


def detect_boundaries_lines(gray: np.ndarray) -> np.ndarray:
    """
    Detect boundary lines and roads using Canny + HoughLinesP.
    Returns binary mask of thin lines.
    """
    # Denoise
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)

    # Edge detection
    edges = cv2.Canny(blurred, 30, 100)

    # Morphological closing to connect broken lines
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)

    return closed


def detect_settlements(gray: np.ndarray, binary_mask: np.ndarray) -> np.ndarray:
    """
    Detect settlements (small solid blocks) using contour analysis.
    """
    mask = np.zeros_like(gray)

    # Find white regions (settlements appear as light squares/circles)
    _, bright = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

    # Find contours of bright regions
    contours, _ = cv2.findContours(bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        # Settlements are small to medium bright regions
        if 100 < area < 5000:
            perimeter = cv2.arcLength(cnt, True)
            if perimeter > 0:
                # Approximate shape
                circularity = 4 * np.pi * area / (perimeter * perimeter)
                # Squareness (check if roughly rectangular)
                x, y, w, h = cv2.boundingRect(cnt)
                aspect = w / max(h, 1)
                if 0.5 < aspect < 2.0:  # roughly square
                    cv2.drawContours(mask, [cnt], -1, 255, -1)

    return mask


def detect_rivers(gray: np.ndarray) -> np.ndarray:
    """
    Detect rivers - typically thin, winding dark lines.
    Uses skeletonization + curvature analysis.
    """
    mask = np.zeros_like(gray)

    # Detect thin dark lines (potential rivers)
    _, dark = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)

    # Skeletonize to get center lines
    skeleton = skeletonize(dark)

    # Find long thin structures
    kernel_line = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 15))
    line_mask = cv2.morphologyEx(skeleton, cv2.MORPH_OPEN, kernel_line)

    mask[line_mask > 0] = 255

    return mask


def skeletonize(img: np.ndarray) -> np.ndarray:
    """Skeletonize binary image using Zhang-Suen algorithm."""
    img = (img > 0).astype(np.uint8)
    skeleton = np.zeros_like(img)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    done = False

    while not done:
        eroded = cv2.erode(img, element)
        temp = cv2.dilate(eroded, element)
        temp = cv2.subtract(img, temp)
        skeleton = cv2.bitwise_or(skeleton, temp)
        img = eroded.copy()
        done = cv2.countNonZero(img) == 0

    return skeleton


def detect_mountains(gray: np.ndarray, boundary_mask: np.ndarray, settlement_mask: np.ndarray) -> np.ndarray:
    """
    Detect mountains/hills - typically large irregular dark regions.
    Exclude boundaries and settlements.
    """
    mask = np.zeros_like(gray)

    # Large dark regions
    _, dark = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY_INV)

    # Find contours
    contours, _ = cv2.findContours(dark, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 2000:  # Large enough to be a mountain region
            # Exclude if it overlaps too much with boundary lines
            x, y, w, h = cv2.boundingRect(cnt)
            roi = boundary_mask[y:y+h, x:x+w]
            line_ratio = cv2.countNonZero(roi) / max(area, 1)
            if line_ratio < 0.3:  # Not mostly lines
                cv2.drawContours(mask, [cnt], -1, 255, -1)

    return mask


def detect_text_regions(gray: np.ndarray) -> np.ndarray:
    """
    Detect text label regions - dense small structures.
    Uses MSER (Maximally Stable Extremal Regions).
    """
    mask = np.zeros_like(gray)

    # Use MSER to detect text-like regions
    mser = cv2.MSER_create(min_area=20, max_area=500)
    regions, _ = mser.detectRegions(gray)

    if regions is not None:
        for region in regions:
            hull = cv2.convexHull(region.reshape(-1, 1, 2))
            cv2.fillConvexPoly(mask, hull.astype(int), 255)

    return mask


def combine_masks(
    boundary: np.ndarray,
    settlements: np.ndarray,
    rivers: np.ndarray,
    mountains: np.ndarray,
    text: np.ndarray,
) -> np.ndarray:
    """
    Combine individual masks into final class segmentation.
    Priority: settlements > boundaries > rivers > mountains > text > background
    """
    h, w = boundary.shape
    class_mask = np.zeros((h, w), dtype=np.uint8)

    # Class 2: Mountains (large dark regions)
    class_mask[mountains > 0] = 2

    # Class 1: Rivers (thin lines)
    class_mask[rivers > 0] = 1

    # Class 4: Boundaries/Roads (thin lines)
    class_mask[boundary > 0] = 4

    # Class 5: Text regions
    class_mask[text > 0] = 5

    # Class 3: Settlements (priority)
    class_mask[settlements > 0] = 3

    # Class 0: Background (remaining - white/bright areas)
    # Already 0 by default

    return class_mask


def generate_pseudo_mask(gray: np.ndarray) -> np.ndarray:
    """Generate complete pseudo-label mask for a grayscale image."""
    h, w = gray.shape

    # Resize to standard size for consistency
    gray_resized = cv2.resize(gray, (w, h))

    # Detect each class
    boundary = detect_boundaries_lines(gray_resized)
    settlements = detect_settlements(gray_resized, boundary)
    rivers = detect_rivers(gray_resized)
    mountains = detect_mountains(gray_resized, boundary, settlements)
    text = detect_text_regions(gray_resized)

    # Combine
    class_mask = combine_masks(boundary, settlements, rivers, mountains, text)

    return class_mask


# ─────────────────────────────────────────────────────────────────────────────
# Visualize
# ─────────────────────────────────────────────────────────────────────────────
def colorize_mask(mask: np.ndarray) -> np.ndarray:
    """Convert class mask to RGB color for visualization."""
    colors = {
        0: (255, 255, 255),   # background - white
        1: (255, 255, 0),     # rivers - yellow
        2: (139, 90, 43),     # mountains - brown
        3: (255, 0, 0),       # cities - red
        4: (0, 255, 0),       # boundaries - green
        5: (0, 255, 255),     # text - cyan
    }
    h, w = mask.shape
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    for class_id, color in colors.items():
        rgb[mask == class_id] = color
    return rgb


# ─────────────────────────────────────────────────────────────────────────────
# Process dataset
# ─────────────────────────────────────────────────────────────────────────────
def process_split(
    image_dir: Path,
    output_dir: Path,
    split: str,
    max_images: int = None,
):
    """Process all images in a split and generate pseudo-labels."""
    img_dir = image_dir / split
    out_mask_dir = output_dir / "masks" / split
    out_preview_dir = output_dir / "previews" / split
    out_mask_dir.mkdir(parents=True, exist_ok=True)
    out_preview_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(img_dir.glob("*.png"))
    if max_images:
        images = images[:max_images]

    logger.info(f"Processing {len(images)} {split} images...")

    class_stats = {i: 0 for i in range(NUM_CLASSES)}

    for img_path in tqdm(images, desc=f"Generating {split} masks"):
        try:
            gray = load_image_as_gray(img_path)
            class_mask = generate_pseudo_mask(gray)

            # Resize to target size
            class_mask_resized = cv2.resize(
                class_mask, TARGET_SIZE, interpolation=cv2.INTER_NEAREST
            )

            # Save mask
            mask_name = img_path.stem + "_mask.png"
            Image.fromarray(class_mask_resized).save(out_mask_dir / mask_name)

            # Save color preview
            preview = colorize_mask(class_mask_resized)
            Image.fromarray(preview).save(out_preview_dir / mask_name.replace("_mask.png", "_preview.png"))

            # Stats
            for c in range(NUM_CLASSES):
                class_stats[c] += (class_mask_resized == c).sum()

        except Exception as e:
            logger.warning(f"Failed on {img_path.name}: {e}")

    # Print statistics
    total_pixels = sum(class_stats.values())
    logger.info(f"Class distribution for {split}:")
    for c in range(NUM_CLASSES):
        pct = 100 * class_stats[c] / max(total_pixels, 1)
        logger.info(f"  Class {c} ({CLASS_NAMES[c]}): {class_stats[c]:,} pixels ({pct:.1f}%)")

    return class_stats


# ─────────────────────────────────────────────────────────────────────────────
# Build COCO annotations from pseudo-labels
# ─────────────────────────────────────────────────────────────────────────────
def build_coco_from_masks(pseudo_dir: Path, split: str) -> dict:
    """Build COCO format annotations from pseudo-label masks."""
    mask_dir = pseudo_dir / "masks" / split
    img_dir = Path("data/maps/dataset/images") / split

    masks = sorted(mask_dir.glob("*.png"))
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

        for class_id in range(1, NUM_CLASSES):
            class_mask = (mask == class_id).astype(np.uint8)
            if class_mask.sum() == 0:
                continue

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
                "segmentation": [],
                "iscrowd": 0,
            })
            ann_id += 1

    return {
        "info": {"description": f"古舆图规则伪标签 - {split}", "version": "1.0", "year": 2026},
        "licenses": [{"id": 1, "name": "志鉴项目"}],
        "categories": [
            {"id": i, "name": CLASS_NAMES[i], "supercategory": "map"}
            for i in range(NUM_CLASSES)
        ],
        "images": images,
        "annotations": annotations,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Copy images to pseudo-label dataset structure
# ─────────────────────────────────────────────────────────────────────────────
def copy_images_to_dataset(image_dir: Path, output_dir: Path, split: str):
    """Copy source images to pseudo-label dataset structure."""
    src_dir = image_dir / split
    dst_dir = output_dir / "images" / split
    dst_dir.mkdir(parents=True, exist_ok=True)

    for img_path in src_dir.glob("*.png"):
        dst_path = dst_dir / img_path.name
        if not dst_path.exists():
            try:
                import os
                os.link(img_path, dst_path)
            except OSError:
                import shutil
                shutil.copy(img_path, dst_path)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="灰度舆图规则伪标签生成")
    parser.add_argument("--data", default="data/maps/dataset", help="原始数据集目录")
    parser.add_argument("--output", default="data/maps/pseudo_labels", help="伪标签输出目录")
    parser.add_argument("--split", default="train", choices=["train", "val"], help="处理哪个split")
    parser.add_argument("--max-images", type=int, default=None, help="最多处理图片数")
    args = parser.parse_args()

    data_dir = Path(args.data)
    output_dir = Path(args.output)

    # Copy images
    logger.info("Copying images to output directory...")
    copy_images_to_dataset(data_dir / "images", output_dir, args.split)

    # Generate masks
    class_stats = process_split(
        image_dir=data_dir / "images",
        output_dir=output_dir,
        split=args.split,
        max_images=args.max_images,
    )

    # Build COCO annotations
    coco = build_coco_from_masks(output_dir, args.split)
    if coco:
        ann_path = output_dir / "annotations" / f"{args.split}.json"
        ann_path.parent.mkdir(parents=True, exist_ok=True)
        ann_path.write_text(json.dumps(coco, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"COCO annotations saved: {ann_path}")
        logger.info(f"  Images: {len(coco['images'])}")
        logger.info(f"  Annotations: {len(coco['annotations'])}")

    # Summary
    total_pixels = sum(class_stats.values())
    logger.info(f"""
=== 完成！ ===

伪标签目录: {output_dir}
- images/{args.split}/     - 原始图像
- masks/{args.split}/       - 伪标签掩码 (PNG)
- previews/{args.split}/   - 彩色预览图
- annotations/{args.split}.json - COCO格式标注

下一步:
1. 训练 U-Net: python scripts/train_unet_maps.py --data {output_dir} --epochs 50
2. 人工修正: 在 previews/ 中检查并修正 mask PNG 文件
""")


if __name__ == "__main__":
    main()
