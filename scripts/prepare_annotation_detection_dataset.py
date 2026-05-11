"""
批校痕迹Faster R-CNN目标检测训练数据集准备脚本

功能：
1. 从咸丰版固安县志人物志章节中筛选出可能有批校的页面
2. 生成基于HSV颜色规则的预检测候选区域
3. 生成Label Studio项目配置文件
4. 生成COCO格式检测数据集

Usage:
    python scripts/prepare_annotation_detection_dataset.py --output data/annotations
"""

import argparse
import json
import os
import shutil
import logging
from pathlib import Path
from PIL import Image
import numpy as np
import cv2

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 类别定义（与 app/annotation_extract/faster_rcnn_model.py 保持一致）
# ─────────────────────────────────────────────────────────────────────────────
ANNOTATION_CLASSES = {
    0: {"Name": "朱批", "supercategory": "annotation", "color_hsv": (0, 100, 50, 20, 255, 255)},
    1: {"Name": "墨批", "supercategory": "annotation", "color_hsv": (0, 0, 0, 180, 80, 80)},
    2: {"Name": "圈点", "supercategory": "annotation", "color_hsv": (0, 80, 50, 20, 255, 255)},
    3: {"Name": "划线", "supercategory": "annotation", "color_hsv": (0, 80, 50, 20, 255, 255)},
}

# ─────────────────────────────────────────────────────────────────────────────
# Label Studio BBOX 配置
# ─────────────────────────────────────────────────────────────────────────────
LABEL_STUDIO_BBOX_CONFIG = """<View>
  <Header value="批校痕迹检测标注 - 古籍朱墨批圈点划线"/>
  <Image name="image" value="$image" zoom="true"/>
  <RectangleLabels name="annotation_labels" toName="image">
    <Label value="朱批" background="#FF0000"/>
    <Label value="墨批" background="#333333"/>
    <Label value="圈点" background="#FFA500"/>
    <Label value="划线" background="#0000FF"/>
  </RectangleLabels>
</View>
"""


def scan_gazetteer_images(base_dir: str) -> dict:
    """扫描固安县志OCR训练图像目录，按章节分类"""
    base = Path(base_dir)
    if not base.exists():
        raise FileNotFoundError(f"目录不存在: {base_dir}")

    categories = {}
    for f in sorted(base.glob("*.png")):
        name = f.name
        # 识别章节
        if "人物志" in name:
            chapter = "biography"
        elif "舆地志" in name or "舆图" in name:
            chapter = "geography"
        elif "凡例" in name or "序" in name.split("_p")[0]:
            chapter = "preface"
        elif "目录" in name:
            chapter = "toc"
        else:
            chapter = "other"

        if chapter not in categories:
            categories[chapter] = []
        categories[chapter].append(str(f))

    return categories


def analyze_annotation_potential(image_path: str) -> dict:
    """
    分析图像是否可能包含批校痕迹
    使用HSV颜色检测辅助判断
    """
    img = cv2.imread(image_path)
    if img is None:
        return {"has_annotation": False, "confidence": 0.0, "counts": {}}

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    results = {"counts": {}, "confidence": 0.0, "reasons": []}

    # 1. 检测红色（朱批候选）
    red_mask1 = cv2.inRange(hsv, (0, 80, 50), (20, 255, 255))
    red_mask2 = cv2.inRange(hsv, (340, 80, 50), (360, 255, 255))
    red_mask = red_mask1 + red_mask2
    red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    red_count = len([c for c in red_contours if 50 < cv2.contourArea(c) < 50000])
    results["counts"]["朱批"] = red_count

    # 2. 检测深色（墨批候选）
    ink_mask = cv2.inRange(hsv, (0, 0, 0), (180, 80, 80))
    ink_contours, _ = cv2.findContours(ink_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    ink_count = len([c for c in ink_contours if 100 < cv2.contourArea(c) < 100000])
    results["counts"]["墨批"] = ink_count

    # 3. 检测圆形（圈点候选）
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=1.5, minDist=10,
        param1=50, param2=20, minRadius=3, maxRadius=30
    )
    circle_count = 0 if circles is None else len(circles[0])
    results["counts"]["圈点"] = circle_count

    # 4. 检测线段（划线候选）
    edges = cv2.Canny(gray, 30, 100)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30,
                             minLineLength=50, maxLineGap=10)
    line_count = 0 if lines is None else len(lines)
    # 过滤水平线
    h_lines = 0
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = abs(np.arctan2(y2-y1, x2-x1) * 180 / np.pi)
            if angle < 20 or angle > 160:  # 接近水平
                h_lines += 1
    results["counts"]["划线"] = h_lines

    # 计算综合置信度
    score = 0.0
    total_candidates = red_count + ink_count + circle_count + h_lines

    if red_count >= 3:
        score += 0.4
        results["reasons"].append(f"红批候选:red={red_count}")
    elif red_count >= 1:
        score += 0.2

    if ink_count >= 5:
        score += 0.3
        results["reasons"].append(f"墨批候选:ink={ink_count}")
    elif ink_count >= 2:
        score += 0.15

    if circle_count >= 5:
        score += 0.3
        results["reasons"].append(f"圈点候选:circle={circle_count}")
    elif circle_count >= 1:
        score += 0.15

    if h_lines >= 3:
        score += 0.2
        results["reasons"].append(f"划线候选:line={h_lines}")

    results["confidence"] = min(score, 1.0)
    results["total_candidates"] = total_candidates

    return results


def select_annotation_pages(image_dir: str, min_confidence: float = 0.2) -> list:
    """从人物志中筛选出可能包含批校的页面"""
    images = scan_gazetteer_images(image_dir)

    all_candidates = []

    for img_path in images.get("biography", []):
        result = analyze_annotation_potential(img_path)
        result["image_path"] = img_path
        result["filename"] = Path(img_path).name
        all_candidates.append(result)

    all_candidates.sort(key=lambda x: x["confidence"], reverse=True)

    selected = [c for c in all_candidates if c["confidence"] >= min_confidence]

    logger.info(f"分析 {len(all_candidates)} 张人物志图像")
    logger.info(f"筛选出 {len(selected)} 张（置信度≥{min_confidence}）")

    for c in selected[:10]:
        counts_str = ", ".join(f"{k}={v}" for k, v in c["counts"].items())
        logger.info(f"  ✓ {c['filename']}: conf={c['confidence']:.2f} [{counts_str}]")

    return selected


def generate_preannotation_candidates(image_path: str, enhance_contrast: bool = True) -> dict:
    """
    生成批校候选区域用于预标注辅助

    Args:
        image_path: 图像路径
        enhance_contrast: 是否增强对比度后再检测

    Returns:
        dict: 每个类别的候选bbox列表
    """
    img = cv2.imread(image_path)
    if img is None:
        return {}

    if enhance_contrast:
        # 线性对比度增强（帮助看清褪色批注）
        img = cv2.convertScaleAbs(img, alpha=1.5, beta=0)

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    candidates = {}

    # 1. 朱批（红色）→ bounding boxes
    red_mask1 = cv2.inRange(hsv, (0, 100, 50), (20, 255, 255))
    red_mask2 = cv2.inRange(hsv, (340, 100, 50), (360, 255, 255))
    red_mask = red_mask1 + red_mask2
    red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    red_boxes = []
    for c in red_contours:
        area = cv2.contourArea(c)
        if 50 < area < 50000:
            x, y, cw, ch = cv2.boundingRect(c)
            # 扩大bbox确保包含完整批注
            pad = 5
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(w, x + cw + pad)
            y2 = min(h, y + ch + pad)
            red_boxes.append([x1, y1, x2, y2])
    candidates["朱批"] = red_boxes

    # 2. 墨批（深色）→ bounding boxes
    ink_mask = cv2.inRange(hsv, (0, 0, 0), (180, 80, 80))
    ink_contours, _ = cv2.findContours(ink_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    ink_boxes = []
    for c in ink_contours:
        area = cv2.contourArea(c)
        if 100 < area < 100000:
            x, y, cw, ch = cv2.boundingRect(c)
            # 过滤太大（整段文字）的区域
            if ch < h * 0.3:  # 高度不超过图像30%
                pad = 3
                x1 = max(0, x - pad)
                y1 = max(0, y - pad)
                x2 = min(w, x + cw + pad)
                y2 = min(h, y + ch + pad)
                ink_boxes.append([x1, y1, x2, y2])
    candidates["墨批"] = ink_boxes

    # 3. 圈点 → 圆形检测
    circles = cv2.HoughCircles(
        gray, cv2.HOUGH_GRADIENT, dp=1.5, minDist=8,
        param1=50, param2=20, minRadius=3, maxRadius=30
    )
    circle_boxes = []
    if circles is not None:
        for circle in circles[0]:
            cx, cy, r = circle
            x1 = max(0, int(cx - r - 2))
            y1 = max(0, int(cy - r - 2))
            x2 = min(w, int(cx + r + 2))
            y2 = min(h, int(cy + r + 2))
            circle_boxes.append([x1, y1, x2, y2])
    candidates["圈点"] = circle_boxes

    # 4. 划线 → 水平线段
    edges = cv2.Canny(gray, 30, 100)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30,
                             minLineLength=40, maxLineGap=10)
    underline_boxes = []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            angle = abs(np.arctan2(y2-y1, x2-x1) * 180 / np.pi)
            if angle < 25 or angle > 155:  # 水平线
                # 扩展为小矩形
                pad_y = 8
                rx1 = max(0, min(x1, x2) - 2)
                ry1 = max(0, min(y1, y2) - pad_y)
                rx2 = min(w, max(x1, x2) + 2)
                ry2 = min(h, max(y1, y2) + pad_y)
                if rx2 > rx1 and ry2 > ry1:
                    underline_boxes.append([rx1, ry1, rx2, ry2])
    candidates["划线"] = underline_boxes

    # 汇总
    total = sum(len(v) for v in candidates.values())
    logger.debug(f"预检测: {Path(image_path).name} → {total} 个候选区域")
    for cls, boxes in candidates.items():
        if boxes:
            logger.debug(f"  {cls}: {len(boxes)} 个")

    return candidates


def create_detection_dataset_structure(output_dir: str, selected_images: list,
                                       train_ratio: float = 0.8) -> Path:
    """创建检测数据集目录结构"""
    output = Path(output_dir)
    ds_dir = output / "dataset"
    img_dir = ds_dir / "images"
    ann_dir = ds_dir / "annotations"

    for sub in ["train", "val"]:
        (img_dir / sub).mkdir(parents=True, exist_ok=True)
    ann_dir.mkdir(exist_ok=True)

    n_train = int(len(selected_images) * train_ratio)
    train_imgs = selected_images[:n_train]
    val_imgs = selected_images[n_train:]

    logger.info(f"数据集划分: 训练集 {len(train_imgs)} 张, 验证集 {len(val_imgs)} 张")

    # 硬链接图像
    for img_info in train_imgs:
        src = Path(img_info["image_path"])
        dst = img_dir / "train" / src.name
        if not dst.exists():
            try:
                os.link(src, dst)
            except OSError:
                shutil.copy(src, dst)

    for img_info in val_imgs:
        src = Path(img_info["image_path"])
        dst = img_dir / "val" / src.name
        if not dst.exists():
            try:
                os.link(src, dst)
            except OSError:
                shutil.copy(src, dst)

    # 生成空COCO检测标注
    for split, imgs in [("train", train_imgs), ("val", val_imgs)]:
        coco = create_empty_detection_coco(split, imgs, img_dir / split)
        ann_file = ann_dir / f"{split}.json"
        ann_file.write_text(json.dumps(coco, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"COCO检测标注模板: {ann_file}")

    return ds_dir


def create_empty_detection_coco(split: str, images_info: list, image_dir: Path) -> dict:
    """创建空的COCO检测标注结构"""
    images = []
    for idx, img_info in enumerate(images_info):
        img_path = image_dir / Path(img_info["image_path"]).name
        if img_path.exists():
            pil_img = Image.open(img_path)
            w, h = pil_img.size
        else:
            w, h = 1240, 1755

        images.append({
            "id": idx + 1,
            "file_name": Path(img_info["image_path"]).name,
            "width": w,
            "height": h,
            "license": 1,
            "confidence": img_info["confidence"],
            "counts": img_info["counts"]
        })

    return {
        "info": {
            "description": f"古籍批校检测数据集 - {split}集",
            "version": "1.0",
            "year": 2026,
            "contributor": "志鉴团队",
            "split": split
        },
        "licenses": [{"id": 1, "name": "志鉴项目", "url": ""}],
        "categories": [
            {"id": cid, "name": info["Name"], "supercategory": info["supercategory"]}
            for cid, info in ANNOTATION_CLASSES.items()
        ],
        "images": images,
        "annotations": []  # 待Label Studio填充
    }


def generate_label_studio_project(output_dir: str, image_paths: list):
    """生成Label Studio BBOX项目文件"""
    output = Path(output_dir)
    ls_dir = output / "label_studio"
    ls_dir.mkdir(parents=True, exist_ok=True)

    # 保存配置
    config_path = ls_dir / "label_studio_bbox_config.xml"
    config_path.write_text(LABEL_STUDIO_BBOX_CONFIG, encoding="utf-8")
    logger.info(f"Label Studio BBOX配置: {config_path}")

    # 图像导入列表
    import_list = []
    for img_path in image_paths:
        import_list.append({
            "image": str(Path(img_path).resolve()),
            "metadata": {
                "chapter": Path(img_path).stem.split("_p")[0],
                "page": Path(img_path).stem.split("_p")[-1] if "_p" in Path(img_path).stem else "0"
            }
        })

    import_path = ls_dir / "import_images.json"
    import_path.write_text(json.dumps(import_list, ensure_ascii=False, indent=2), encoding="utf-8")

    # README
    readme = f"""# 批校痕迹检测标注项目

## Label Studio 导入步骤

1. 启动 Label Studio:
   ```bash
   label-studio start --init annotation_detection
   cd annotation_detection
   ```

2. 创建新项目 "古籍批校痕迹检测":
   - 标注配置: 粘贴 `{config_path.name}` 内容到 XML编辑器
   - 上传 {len(image_paths)} 张人物志图像

3. 导出标注: Settings → Export → COCO

## 标注规范

| 类别 | 颜色 | 说明 |
|------|------|------|
| 朱批 | 红色框 | 红色毛笔批语 |
| 墨批 | 黑色框 | 墨色手写批注 |
| 圈点 | 橙色框 | 圈点阅读标记 |
| 划线 | 蓝色框 | 下划线/删除线 |

## 注意事项

- 使用 **tight bounding box** 紧贴批注边缘
- 褪色批注：增强对比度后标注
- 重叠批注：仅标注最上层
- 最小框: 10×10 像素
"""
    (ls_dir / "README.md").write_text(readme, encoding="utf-8")

    return ls_dir


# ─────────────────────────────────────────────────────────────────────────────
# COCO→YOLO 格式转换（用于YOLOv8等）
# ─────────────────────────────────────────────────────────────────────────────
def coco_to_yolo_converter(annotations_path: str, output_dir: str):
    """
    将COCO格式标注转换为YOLO txt格式

    YOLO格式: class_id x_center y_center width height (归一化到0-1)
    """
    import json
    from pathlib import Path

    with open(annotations_path, encoding="utf-8") as f:
        coco = json.load(f)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    # 建立image_id → image_info映射
    img_map = {img["id"]: img for img in coco["images"]}

    # 按图像分组标注
    ann_by_image = {}
    for ann in coco["annotations"]:
        img_id = ann["image_id"]
        if img_id not in ann_by_image:
            ann_by_image[img_id] = []
        ann_by_image[img_id].append(ann)

    for img_id, anns in ann_by_image.items():
        img_info = img_map[img_id]
        w, h = img_info["width"], img_info["height"]

        yolo_lines = []
        for ann in anns:
            cat_id = ann["category_id"]
            bbox = ann["bbox"]  # [x, y, width, height]

            # 转换为YOLO中心点+宽高格式
            x_center = (bbox[0] + bbox[2] / 2) / w
            y_center = (bbox[1] + bbox[3] / 2) / h
            nw = bbox[2] / w
            nh = bbox[3] / h

            yolo_lines.append(f"{cat_id} {x_center:.6f} {y_center:.6f} {nw:.6f} {nh:.6f}")

        # 保存txt
        txt_name = Path(img_info["file_name"]).stem + ".txt"
        (output / txt_name).write_text("\n".join(yolo_lines), encoding="utf-8")

    logger.info(f"YOLO格式转换完成: {len(ann_by_image)} 张图像 → {output_dir}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="批校Faster R-CNN训练数据集准备")
    parser.add_argument("--source", default="data/ocr_training/images",
                        help="OCR训练图像目录")
    parser.add_argument("--output", default="data/annotations",
                        help="输出目录")
    parser.add_argument("--min-confidence", type=float, default=0.2,
                        help="批校页筛选置信度阈值")
    parser.add_argument("--max-images", type=int, default=30,
                        help="最多选取图像数")
    parser.add_argument("--generate-preann", action="store_true",
                        help="生成预标注候选区域")
    parser.add_argument("--analyze-only", action="store_true",
                        help="仅分析不生成数据集")
    args = parser.parse_args()

    source_dir = args.source
    if not os.path.isabs(source_dir):
        project_root = Path(__file__).parent.parent
        source_dir = project_root / source_dir

    logger.info(f"扫描图像目录: {source_dir}")
    categories = scan_gazetteer_images(str(source_dir))

    logger.info("=== 图像分类统计 ===")
    for chapter, files in categories.items():
        logger.info(f"  {chapter}: {len(files)} 张")

    # 筛选批校页
    selected = select_annotation_pages(str(source_dir), args.min_confidence)
    selected = selected[:args.max_images]

    if args.analyze_only:
        logger.info("=== 分析完成（--analyze-only 模式）===")
        return

    # 生成数据集
    logger.info("=== 生成数据集结构 ===")
    ds_dir = create_detection_dataset_structure(args.output, selected)

    # 生成Label Studio项目
    logger.info("=== 生成Label Studio项目文件 ===")
    ls_dir = generate_label_studio_project(args.output, [c["image_path"] for c in selected])

    # 生成预标注候选
    if args.generate_preann:
        logger.info("=== 生成预标注候选区域 ===")
        preann_dir = Path(args.output) / "preannotations"
        preann_dir.mkdir(exist_ok=True)

        for candidate in selected:
            img_path = candidate["image_path"]
            preann = generate_preannotation_candidates(img_path)
            out_path = preann_dir / f"{Path(img_path).stem}_preann.json"
            out_path.write_text(json.dumps(preann, ensure_ascii=False, indent=2))
            total = sum(len(v) for v in preann.values())
            logger.info(f"  预标注: {Path(img_path).name} → {total} 个候选区域")

    logger.info(f"""
=== 完成！ ===

数据集目录: {ds_dir}
Label Studio项目: {ls_dir}

下一步：
1. 启动 Label Studio: label-studio start
2. 导入配置: {ls_dir / 'label_studio_bbox_config.xml'}
3. 导入图像: {ls_dir / 'import_images.json'}
4. 标注 {len(selected)} 张人物志
5. 导出COCO格式 → {ds_dir / 'annotations'}
6. 可选转换YOLO格式:
   python scripts/prepare_annotation_detection_dataset.py --generate-preann \\
       --source {source_dir} --output {args.output}
""")

    # 提供格式转换示例
    logger.info("=== 格式转换示例 ===")
    logger.info(f"  COCO → YOLO: 调用 coco_to_yolo_converter('{ds_dir / 'annotations' / 'train.json'}' , '{ds_dir / 'labels' / 'train'}')")


if __name__ == "__main__":
    main()
