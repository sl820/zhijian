"""
批校痕迹检测伪标签生成脚本

使用规则-based颜色检测和轮廓分析为古籍批校图像生成COCO格式标注。

功能：
- HSV颜色检测：朱批(红色)、墨批(墨色)
- 轮廓分析：圈点、划线、批注区域
- 形态学操作：去噪、连通域分析
- COCO Format输出：可直接用于Faster R-CNN训练

Usage:
    # 生成所有图像的伪标签
    python scripts/generate_annotation_pseudo_labels.py --data data/annotations/dataset

    # 仅生成训练集
    python scripts/generate_annotation_pseudo_labels.py --data data/annotations/dataset --split train

    # 使用更高灵敏度
    python scripts/generate_annotation_pseudo_labels.py --data data/annotations/dataset --red-thresh 80
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
import numpy as np
import cv2
from PIL import Image
from tqdm import tqdm

# 添加项目根目录
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("annotation_pseudo_label.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# COCO类别定义（与 faster_rcnn_model.py 保持一致）
COCO_CATEGORIES = [
    {"id": 1, "name": "朱批", "supercategory": "annotation"},
    {"id": 2, "name": "墨批", "supercategory": "annotation"},
    {"id": 3, "name": "圈点", "supercategory": "annotation"},
    {"id": 4, "name": "划线", "supercategory": "annotation"},
    {"id": 5, "name": "批注区域", "supercategory": "annotation"},
]


def imread(path: str) -> np.ndarray:
    """读取图像，支持中文路径"""
    try:
        img = cv2.imread(path)
        if img is not None:
            return img
    except Exception:
        pass
    # PIL回退
    pil_img = Image.open(path).convert('RGB')
    arr = np.array(pil_img)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def detect_red_annotations(image: np.ndarray, min_area: int = 100) -> list:
    """检测红色批注（朱批）

    Args:
        image: BGR图像
        min_area: 最小连通域面积

    Returns:
        bbox列表 [(x, y, w, h), ...]
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # 红色范围1: hue 0-10
    lower1 = np.array([0, 80, 80])
    upper1 = np.array([10, 255, 255])
    mask1 = cv2.inRange(hsv, lower1, upper1)

    # 红色范围2: hue 160-180
    lower2 = np.array([160, 80, 80])
    upper2 = np.array([180, 255, 255])
    mask2 = cv2.inRange(hsv, lower2, upper2)

    mask = cv2.bitwise_or(mask1, mask2)

    # 形态学操作去噪
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # 找连通域
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    bboxes = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area >= min_area:
            x, y, w, h = cv2.boundingRect(cnt)
            # 排除过宽或过窄的区域（可能是文字行）
            if h > 5 and w > 5 and w / h < 50:
                bboxes.append((x, y, w, h))

    return bboxes


def detect_ink_annotations(image: np.ndarray, min_area: int = 100) -> list:
    """检测墨色批注（墨批、划线）

    Args:
        image: BGR图像
        min_area: 最小连通域面积

    Returns:
        bbox列表 [(x, y, w, h), ...]
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 阈值分割 - 深色区域
    _, binary = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)

    # 形态学操作
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    # 找连通域
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    bboxes = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area >= min_area:
            x, y, w, h = cv2.boundingRect(cnt)
            if h > 3 and w > 3:
                bboxes.append((x, y, w, h))

    return bboxes


def detect_circles_and_dots(image: np.ndarray, min_area: int = 50, max_area: int = 2000) -> list:
    """检测圈点（圆形标记）

    Args:
        image: BGR图像
        min_area: 最小面积
        max_area: 最大面积

    Returns:
        bbox列表 [(x, y, w, h), ...]
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 检测圆
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=10,
        param1=50,
        param2=20,
        minRadius=5,
        maxRadius=50
    )

    bboxes = []
    if circles is not None:
        for circle in circles[0]:
            cx, cy, r = circle
            area = np.pi * r * r
            if min_area <= area <= max_area:
                x, y = int(cx - r), int(cy - r)
                w, h = int(2 * r), int(2 * r)
                bboxes.append((x, y, w, h))

    return bboxes


def detect_underlines(image: np.ndarray, min_width: int = 30, min_height: int = 2, max_height: int = 10) -> list:
    """检测划线（细长的水平/对角线）

    Args:
        image: BGR图像
        min_width: 最小宽度
        min_height: 最大高度（薄的）
        max_height: 最大高度

    Returns:
        bbox列表 [(x, y, w, h), ...]
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 边缘检测
    edges = cv2.Canny(gray, 50, 150)

    # 霍夫变换检测直线
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=30,
        minLineLength=min_width,
        maxLineGap=5
    )

    bboxes = []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            # 计算边界框
            x = min(x1, x2)
            y = min(y1, y2)
            w = abs(x2 - x1)
            h = abs(y2 - y1)

            # 过滤太粗的线
            if h <= max_height:
                # 确保宽大于高（是横向划线）
                if w > min_width and h >= min_height:
                    bboxes.append((x, y, w, h))

    return bboxes


def detect_annotation_blocks(image: np.ndarray, min_area: int = 500) -> list:
    """检测大块批注区域

    Args:
        image: BGR图像
        min_area: 最小面积

    Returns:
        bbox列表 [(x, y, w, h), ...]
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # 合并红色和深色
    lower_red1 = np.array([0, 50, 50])
    upper_red1 = np.array([20, 255, 255])
    mask_red = cv2.inRange(hsv, lower_red1, upper_red1)

    lower_dark = np.array([0, 0, 0])
    upper_dark = np.array([180, 50, 100])
    mask_dark = cv2.inRange(hsv, lower_dark, upper_dark)

    mask = cv2.bitwise_or(mask_red, mask_dark)

    # 形态学闭操作连接邻近区域
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    bboxes = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area >= min_area:
            x, y, w, h = cv2.boundingRect(cnt)
            # 大块区域，宽高比不能太小
            if w > h and w > 50:
                bboxes.append((x, y, w, h))

    return bboxes


def classify_by_color(image: np.ndarray, bbox: tuple) -> str:
    """根据颜色分类bbox区域

    Args:
        image: BGR图像
        bbox: (x, y, w, h)

    Returns:
        '朱批' 或 '墨批'
    """
    x, y, w, h = bbox
    x, y = max(0, x), max(0, y)
    x2, y2 = min(image.shape[1], x + w), min(image.shape[0], y + h)

    region = image[y:y2, x2:x2]
    if region.size == 0:
        return '墨批'

    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    mean_hsv = np.mean(hsv, axis=(0, 1))

    h, s, v = mean_hsv

    # 红色判断
    is_red = (h <= 20 or h >= 160) and s >= 80 and v >= 80

    return '朱批' if is_red else '墨批'


def generate_coco_annotations(
    image_dir: str,
    output_dir: str,
    split: str = None,
    generate_all: bool = True
) -> dict:
    """生成COCO格式标注文件

    Args:
        image_dir: 图像目录
        output_dir: 输出目录
        split: 'train' 或 'val' 或 None（生成所有）
        generate_all: 是否生成所有标注类型

    Returns:
        COCO格式dict
    """
    image_dir = Path(image_dir)
    output_dir = Path(output_dir)

    if not image_dir.exists():
        logger.error(f"图像目录不存在: {image_dir}")
        return {}

    # 查找所有图像
    extensions = ['.png', '.jpg', '.jpeg', '.tif', '.tiff']
    image_files = []
    for ext in extensions:
        image_files.extend(image_dir.glob(f"*{ext}"))
        image_files.extend(image_dir.glob(f"*{ext.upper()}"))

    if not image_files:
        logger.warning(f"在 {image_dir} 中未找到图像")
        return {}

    logger.info(f"找到 {len(image_files)} 张图像")

    # COCO格式结构
    coco_output = {
        "info": {
            "year": datetime.now().year,
            "version": "1.0",
            "description": "Pseudo-labels for ancient Chinese gazetteer annotation detection",
            "contributor": "ZhiJian System",
            "date_created": datetime.now().isoformat()
        },
        "licenses": [{"id": 1, "name": "Unknown", "url": ""}],
        "categories": COCO_CATEGORIES,
        "images": [],
        "annotations": []
    }

    annotation_id = 1
    image_id = 1

    for img_file in tqdm(image_files, desc="处理图像"):
        # 读取图像
        image = imread(str(img_file))
        if image is None:
            logger.warning(f"无法读取图像: {img_file}")
            continue

        h, w = image.shape[:2]

        # 添加图像信息
        coco_output["images"].append({
            "id": image_id,
            "file_name": img_file.name,
            "width": w,
            "height": h,
            "license": 1,
            "date_captured": datetime.now().isoformat()
        })

        all_bboxes = []

        # 检测各种批注类型
        red_bboxes = detect_red_annotations(image, min_area=100)
        for bbox in red_bboxes:
            all_bboxes.append({"bbox": bbox, "category_id": 1})  # 朱批

        ink_bboxes = detect_ink_annotations(image, min_area=100)
        for bbox in ink_bboxes:
            # 跳过与红色重叠的
            is_duplicate = False
            for rbox in red_bboxes:
                iou = compute_iou(bbox, rbox)
                if iou > 0.3:
                    is_duplicate = True
                    break
            if not is_duplicate:
                all_bboxes.append({"bbox": bbox, "category_id": 2})  # 墨批

        circle_bboxes = detect_circles_and_dots(image, min_area=50, max_area=2000)
        for bbox in circle_bboxes:
            all_bboxes.append({"bbox": bbox, "category_id": 3})  # 圈点

        line_bboxes = detect_underlines(image, min_width=30)
        for bbox in line_bboxes:
            all_bboxes.append({"bbox": bbox, "category_id": 4})  # 划线

        if generate_all:
            block_bboxes = detect_annotation_blocks(image, min_area=500)
            for bbox in block_bboxes:
                all_bboxes.append({"bbox": bbox, "category_id": 5})  # 批注区域

        # 添加标注
        for bbox_info in all_bboxes:
            x, y, w, h = bbox_info["bbox"]
            area = w * h

            coco_output["annotations"].append({
                "id": annotation_id,
                "image_id": image_id,
                "category_id": bbox_info["category_id"],
                "bbox": [float(x), float(y), float(w), float(h)],
                "area": float(area),
                "iscrowd": 0,
                "segmentation": []
            })
            annotation_id += 1

        image_id += 1

    logger.info(f"生成 {len(coco_output['annotations'])} 个标注，{len(coco_output['images'])} 张图像")

    return coco_output


def compute_iou(box1: tuple, box2: tuple) -> float:
    """计算两个bbox的IoU

    Args:
        box1: (x, y, w, h)
        box2: (x, y, w, h)

    Returns:
        IoU值 [0, 1]
    """
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    xi1 = max(x1, x2)
    yi1 = max(y1, y2)
    xi2 = min(x1 + w1, x2 + w2)
    yi2 = min(y1 + h1, y2 + h2)

    inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)

    box1_area = w1 * h1
    box2_area = w2 * h2
    union_area = box1_area + box2_area - inter_area

    return inter_area / union_area if union_area > 0 else 0


def main():
    parser = argparse.ArgumentParser(
        description="批校痕迹伪标签生成脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--data",
        required=True,
        help="数据集根目录 (包含 images/train 和 images/val)"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="输出目录 (默认: data/annotations/dataset)"
    )
    parser.add_argument(
        "--split",
        choices=["train", "val"],
        default=None,
        help="只处理特定split (默认: 处理所有)"
    )
    parser.add_argument(
        "--no-blocks",
        action="store_true",
        help="不生成大块批注区域"
    )

    args = parser.parse_args()

    data_dir = Path(args.data)
    output_base = Path(args.output) if args.output else data_dir.parent / "annotations" / "dataset"

    logger.info("=" * 60)
    logger.info("批校痕迹伪标签生成")
    logger.info("=" * 60)
    logger.info(f"数据目录: {data_dir}")
    logger.info(f"输出目录: {output_base}")
    logger.info("=" * 60)

    generate_all_blocks = not args.no_blocks

    if args.split == "train" or args.split is None:
        train_img_dir = data_dir / "images" / "train"
        if train_img_dir.exists():
            logger.info("\n处理训练集...")
            train_output = output_base / "annotations"
            train_output.mkdir(parents=True, exist_ok=True)

            coco = generate_coco_annotations(
                str(train_img_dir),
                str(train_output),
                split="train",
                generate_all=generate_all_blocks
            )

            if coco:
                output_file = train_output / "train.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(coco, f, ensure_ascii=False, indent=2)
                logger.info(f"训练集标注已保存: {output_file}")

    if args.split == "val" or args.split is None:
        val_img_dir = data_dir / "images" / "val"
        if val_img_dir.exists():
            logger.info("\n处理验证集...")
            val_output = output_base / "annotations"
            val_output.mkdir(parents=True, exist_ok=True)

            coco = generate_coco_annotations(
                str(val_img_dir),
                str(val_output),
                split="val",
                generate_all=generate_all_blocks
            )

            if coco:
                output_file = val_output / "val.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(coco, f, ensure_ascii=False, indent=2)
                logger.info(f"验证集标注已保存: {output_file}")

    logger.info("\n伪标签生成完成!")


if __name__ == "__main__":
    main()
