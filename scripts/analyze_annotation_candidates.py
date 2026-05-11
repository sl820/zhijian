"""
图像质量分析 + 预标注候选生成

支持中文路径，使用 PIL 读取图像后转为 OpenCV 格式。
解决 Windows 上 cv2.imread() 中文路径失败问题。

Usage:
    python scripts/analyze_annotation_candidates.py --mode map
    python scripts/analyze_annotation_candidates.py --mode annotation
"""

import argparse
import json
import logging
from pathlib import Path
import numpy as np
import cv2
from PIL import Image

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def pil_imread(path: str) -> np.ndarray:
    """使用PIL读取中文路径图像，转换为OpenCV格式（BGR）"""
    try:
        pil_img = Image.open(path)
        rgb = pil_img.convert('RGB')
        arr = np.array(rgb)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    except Exception as e:
        logger.warning(f"PIL读取失败 {path}: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 舆图预标注（颜色规则）
# ─────────────────────────────────────────────────────────────────────────────
def analyze_map_candidates(image_path: str) -> dict:
    """分析舆图地理要素候选区域"""
    img = pil_imread(image_path)
    if img is None:
        return {"error": "无法读取图像"}

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    candidates = {}

    # 河流（蓝色色调，HSV: H=90-130）
    blue_mask = cv2.inRange(hsv, (90, 50, 50), (130, 255, 255))
    blue_contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates["河流"] = [
        list(cv2.boundingRect(c)) for c in blue_contours
        if 200 < cv2.contourArea(c) < 500000
    ]

    # 山脉（棕色，HSV: H=10-30）
    brown_mask = cv2.inRange(hsv, (10, 50, 20), (30, 255, 150))
    brown_contours, _ = cv2.findContours(brown_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates["山脉"] = [
        list(cv2.boundingRect(c)) for c in brown_contours
        if 100 < cv2.contourArea(c) < 300000
    ]

    # 城市（红色标记，紧凑区域）
    red_mask1 = cv2.inRange(hsv, (0, 100, 50), (20, 255, 255))
    red_mask2 = cv2.inRange(hsv, (340, 100, 50), (360, 255, 255))
    red_mask = red_mask1 + red_mask2
    red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates["城市"] = [
        list(cv2.boundingRect(c)) for c in red_contours
        if 50 < cv2.contourArea(c) < 50000
    ]

    # 边界线/道路（HoughLinesP）
    edges = cv2.Canny(gray, 30, 100)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50,
                             minLineLength=80, maxLineGap=20)
    line_boxes = []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = abs(np.arctan2(y2-y1, x2-x1) * 180 / np.pi)
            if angle < 30 or angle > 150:  # 近似水平/垂直
                pad = 5
                rx1 = max(0, min(x1, x2) - pad)
                ry1 = max(0, min(y1, y2) - pad)
                rx2 = min(w, max(x1, x2) + pad)
                ry2 = min(h, max(y1, y2) + pad)
                line_boxes.append([rx1, ry1, rx2, ry2])
    candidates["边界线"] = line_boxes

    # 文字（高对比度小块）
    _, bright_text = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    text_contours, _ = cv2.findContours(bright_text, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates["文字标注"] = [
        list(cv2.boundingRect(c)) for c in text_contours
        if 20 < cv2.contourArea(c) < 5000 and 0.2 < cv2.boundingRect(c)[2]/max(1,cv2.boundingRect(c)[3]) < 8
    ]

    total = sum(len(v) for v in candidates.values())
    logger.info(f"  {Path(image_path).name}: {total} 个候选区域")

    return candidates


# ─────────────────────────────────────────────────────────────────────────────
# 批校预标注（HSV颜色规则）
# ─────────────────────────────────────────────────────────────────────────────
def analyze_annotation_candidates(image_path: str) -> dict:
    """分析批校痕迹候选区域"""
    img = pil_imread(image_path)
    if img is None:
        return {"error": "无法读取图像"}

    h, w = img.shape[:2]

    # 对比度增强（褪色批注）
    enhanced = cv2.convertScaleAbs(img, alpha=1.8, beta=0)
    enhanced_gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
    enhanced_hsv = cv2.cvtColor(enhanced, cv2.COLOR_BGR2HSV)

    candidates = {}

    # 朱批（红色）
    red_mask1 = cv2.inRange(enhanced_hsv, (0, 100, 50), (20, 255, 255))
    red_mask2 = cv2.inRange(enhanced_hsv, (340, 100, 50), (360, 255, 255))
    red_mask = red_mask1 + red_mask2
    red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates["朱批"] = [
        list(cv2.boundingRect(c)) for c in red_contours
        if 30 < cv2.contourArea(c) < 100000
    ]

    # 墨批（深色）
    ink_mask = cv2.inRange(enhanced_hsv, (0, 0, 0), (180, 80, 80))
    ink_contours, _ = cv2.findContours(ink_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates["墨批"] = [
        list(cv2.boundingRect(c)) for c in ink_contours
        if 50 < cv2.contourArea(c) < 50000
    ]

    # 圈点（HoughCircles）
    circles = cv2.HoughCircles(
        enhanced_gray, cv2.HOUGH_GRADIENT, dp=1.5, minDist=8,
        param1=50, param2=20, minRadius=3, maxRadius=30
    )
    circle_boxes = []
    if circles is not None:
        for cx, cy, r in circles[0]:
            pad = 3
            x1 = max(0, int(cx - r - pad))
            y1 = max(0, int(cy - r - pad))
            x2 = min(w, int(cx + r + pad))
            y2 = min(h, int(cy + r + pad))
            circle_boxes.append([x1, y1, x2, y2])
    candidates["圈点"] = circle_boxes

    # 划线（水平HoughLinesP）
    edges = cv2.Canny(enhanced_gray, 30, 100)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30,
                             minLineLength=40, maxLineGap=10)
    underline_boxes = []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = abs(np.arctan2(y2-y1, x2-x1) * 180 / np.pi)
            if angle < 25 or angle > 155:
                pad_y = 8
                rx1 = max(0, min(x1, x2) - 2)
                ry1 = max(0, min(y1, y2) - pad_y)
                rx2 = min(w, max(x1, x2) + 2)
                ry2 = min(h, max(y1, y2) + pad_y)
                underline_boxes.append([rx1, ry1, rx2, ry2])
    candidates["划线"] = underline_boxes

    total = sum(len(v) for v in candidates.values())
    logger.info(f"  {Path(image_path).name}: {total} 个候选区域")

    return candidates


# ─────────────────────────────────────────────────────────────────────────────
# 批量处理
# ─────────────────────────────────────────────────────────────────────────────
def batch_process(input_json: str, output_dir: str, mode: str):
    """从Label Studio导入列表批量生成预标注"""
    with open(input_json, encoding="utf-8") as f:
        images = json.load(f)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    analyze_func = analyze_map_candidates if mode == "map" else analyze_annotation_candidates

    total_candidates = 0
    for item in images:
        img_path = item["image"]
        candidates = analyze_func(img_path)
        if "error" in candidates:
            continue

        stem = Path(img_path).stem
        out_path = output / f"{stem}_preann.json"
        out_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2))
        total_candidates += sum(len(v) for v in candidates.values())

    logger.info(f"=== 完成: 处理 {len(images)} 张图像，生成 {total_candidates} 个候选区域 ===")
    logger.info(f"输出目录: {output}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="批校/舆图预标注候选生成")
    parser.add_argument("--mode", choices=["map", "annotation"], required=True,
                        help="map=舆图预标注, annotation=批校预标注")
    parser.add_argument("--input", help="Label Studio import JSON文件路径")
    parser.add_argument("--output", default="data/preannotations",
                        help="预标注输出目录")
    args = parser.parse_args()

    if args.input:
        batch_process(args.input, args.output, args.mode)
        return

    # 默认分析
    if args.mode == "map":
        input_path = "data/maps/label_studio/import_images.json"
        output_dir = "data/maps/preannotations"
    else:
        input_path = "data/annotations/label_studio/import_images.json"
        output_dir = "data/annotations/preannotations"

    if Path(input_path).exists():
        batch_process(input_path, output_dir, args.mode)
    else:
        logger.warning(f"未找到导入文件: {input_path}")
        logger.info("使用 --input 参数指定Label Studio导入JSON")


if __name__ == "__main__":
    main()
