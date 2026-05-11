"""
舆图U-Net语义分割训练数据集准备脚本

功能：
1. 从咸丰版固安县志舆地志章节中筛选出地图页
2. 生成Label Studio项目配置文件
3. 生成COCO格式数据集结构
4. 提供预标注辅助（基于规则的颜色/边缘检测）

Usage:
    python scripts/prepare_unet_annotation_dataset.py --output data/maps
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
# 类别定义（与 app/map_extraction/unet_model.py 保持一致）
# ─────────────────────────────────────────────────────────────────────────────
MAP_CLASSES = {
    0: {"name": "背景", "supercategory": "map", "color": (0, 0, 0)},
    1: {"name": "河流", "supercategory": "map", "color": (0, 255, 255)},
    2: {"name": "山脉", "supercategory": "map", "color": (139, 90, 43)},
    3: {"name": "城市", "supercategory": "map", "color": (255, 0, 0)},
    4: {"name": "边界线", "supercategory": "map", "color": (0, 255, 0)},
    5: {"name": "文字标注", "supercategory": "map", "color": (255, 255, 0)},
}

# ─────────────────────────────────────────────────────────────────────────────
# Label Studio 配置文件生成
# ─────────────────────────────────────────────────────────────────────────────
LABEL_STUDIO_MAP_CONFIG = """<View>
  <Header value="舆图分割标注 - 古地图地理要素"/>
  <Image name="image" value="$image" zoom="true"/>
  <PolygonLabels name="map_labels" toName="image" showInline="false">
    <Label value="河流" stroke="#FFFF00" fill="#FFFF00" fillOpacity="0.3" strokeWidth="3"/>
    <Label value="山脉" stroke="#8B5A2B" fill="#8B5A2B" fillOpacity="0.3" strokeWidth="3"/>
    <Label value="城市" stroke="#FF0000" fill="#FF0000" fillOpacity="0.3" strokeWidth="3"/>
    <Label value="边界线" stroke="#00FF00" fill="#00FF00" fillOpacity="0.3" strokeWidth="3"/>
    <Label value="文字标注" stroke="#FFFF00" fill="#FFFF00" fillOpacity="0.2" strokeWidth="2"/>
  </PolygonLabels>
  <Text name="metadata" value="$metadata"/>
</View>
"""


def scan_gazetteer_images(base_dir: str) -> list:
    """扫描固安县志OCR训练图像目录，分类出舆图页和人物页"""
    base = Path(base_dir)
    if not base.exists():
        raise FileNotFoundError(f"目录不存在: {base_dir}")

    images = {}
    for f in sorted(base.glob("*.png")):
        # 提取章节名（去掉页码后缀）
        name = f.name
        # 识别章节类型
        if "舆地志" in name or "舆图" in name or "图" in name.split("_p")[0]:
            chapter = "map"
        elif "人物志" in name:
            chapter = "biography"
        elif "凡例" in name or "序" in name.split("_p")[0]:
            chapter = " preface"
        elif "目录" in name:
            chapter = "toc"
        else:
            chapter = "other"

        if chapter not in images:
            images[chapter] = []
        images[chapter].append(str(f))

    return images


def analyze_image_map_potential(image_path: str) -> dict:
    """
    分析图像是否为地图页（基于简单规则）
    返回：是否可能是地图页 + 置信度
    """
    img = cv2.imread(image_path)
    if img is None:
        return {"is_map": False, "confidence": 0.0, "reason": "无法读取图像"}

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 计算图像统计
    # 1. 线条密度（地图有更多线条）
    edges = cv2.Canny(gray, 50, 150)
    line_density = np.sum(edges > 0) / (h * w)

    # 2. 颜色分布（地图可能有更多蓝色/绿色成分）
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    blue_ratio = np.sum(hsv[:, :, 0] < 100) / (h * w)  # 蓝色色调比例

    # 3. 纹理复杂度
    # 使用Laplacian方差（图像锐度/纹理）
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    # 简单规则判断
    score = 0.0
    reasons = []

    if line_density > 0.15:
        score += 0.4
        reasons.append(f"线条密度高({line_density:.3f})")
    elif line_density > 0.08:
        score += 0.2
        reasons.append(f"线条密度中({line_density:.3f})")

    if laplacian_var > 500:
        score += 0.3
        reasons.append(f"纹理丰富({laplacian_var:.0f})")

    if blue_ratio > 0.1:
        score += 0.3
        reasons.append(f"蓝色成分({blue_ratio:.3f})")

    # 舆地志页面通常p0-p3是地图
    filename = Path(image_path).name
    if "_p0" in filename or "_p1" in filename:
        score += 0.2
        reasons.append("首几页（可能是地图）")

    is_map = score > 0.4

    return {
        "is_map": is_map,
        "confidence": min(score, 1.0),
        "reasons": reasons,
        "line_density": float(line_density),
        "laplacian_var": float(laplacian_var),
        "blue_ratio": float(blue_ratio)
    }


def select_map_pages_for_annotation(image_dir: str, min_confidence: float = 0.35) -> list:
    """
    从舆地志图像中筛选出最可能是地图的页面
    """
    images = scan_gazetteer_images(image_dir)
    all_map_candidates = []

    for f in images.get("map", []):
        result = analyze_image_map_potential(f)
        result["image_path"] = f
        result["filename"] = Path(f).name
        all_map_candidates.append(result)

    # 按置信度排序
    all_map_candidates.sort(key=lambda x: x["confidence"], reverse=True)

    selected = [c for c in all_map_candidates if c["confidence"] >= min_confidence]

    logger.info(f"分析 {len(all_map_candidates)} 张图像")
    logger.info(f"筛选出 {len(selected)} 张（置信度≥{min_confidence}）")

    for c in selected[:10]:
        logger.info(f"  ✓ {c['filename']}: {c['confidence']:.2f} — {', '.join(c['reasons'])}")

    return selected


def generate_label_studio_project(output_dir: str, image_paths: list):
    """
    生成Label Studio项目文件和图像链接
    """
    output = Path(output_dir)
    ls_dir = output / "label_studio"
    ls_dir.mkdir(parents=True, exist_ok=True)

    # 保存配置
    config_path = ls_dir / "label_studio_config.xml"
    config_path.write_text(LABEL_STUDIO_MAP_CONFIG, encoding="utf-8")
    logger.info(f"Label Studio配置已保存: {config_path}")

    # 生成图像列表（用于导入Label Studio）
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
    logger.info(f"图像列表已保存: {import_path}")

    # 生成README
    readme = f"""# 舆图标注项目

## Label Studio 导入步骤

1. 启动 Label Studio:
   ```bash
   label-studio start --init maps_annotation
   cd maps_annotation
   ```

2. 在 Label Studio Web界面中:
   - 创建新项目 "古舆图分割标注"
   - 导入标注配置: 将 `{config_path.name}` 内容粘贴到 "Labeling Interface" XML编辑器
   - 上传图像: 将以下图像导入项目

3. 标注 {len(image_paths)} 张图像（建议分批次标注）

## 图像来源
- 咸丰版《固安县志》卷一·舆地志

## 图像路径列表
```json
{json.dumps(import_list, ensure_ascii=False, indent=2)}
```
"""
    readme_path = ls_dir / "README.md"
    readme_path.write_text(readme, encoding="utf-8")

    return ls_dir


def create_dataset_structure(output_dir: str, selected_images: list, train_ratio: float = 0.8):
    """
    创建COCO格式数据集目录结构
    """
    output = Path(output_dir)
    ds_dir = output / "dataset"
    ds_dir.mkdir(parents=True, exist_ok=True)

    # 目录结构
    img_dir = ds_dir / "images"
    ann_dir = ds_dir / "annotations"
    for sub in ["train", "val"]:
        (img_dir / sub).mkdir(parents=True, exist_ok=True)

    ann_dir.mkdir(exist_ok=True)

    # 划分训练/验证集
    n_train = int(len(selected_images) * train_ratio)
    train_imgs = selected_images[:n_train]
    val_imgs = selected_images[n_train:]

    logger.info(f"数据集划分: 训练集 {len(train_imgs)} 张, 验证集 {len(val_imgs)} 张")

    # 复制图像（创建symlink避免占用空间）
    for img_info in train_imgs:
        src = Path(img_info["image_path"])
        dst = img_dir / "train" / src.name
        if not dst.exists():
            try:
                os.link(src, dst)  # 硬链接节省空间
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

    # 生成空COCO标注文件（待标注后填充）
    for split, imgs in [("train", train_imgs), ("val", val_imgs)]:
        coco = create_empty_coco_annotations(split, imgs, img_dir / split)
        ann_file = ann_dir / f"{split}.json"
        ann_file.write_text(json.dumps(coco, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"COCO标注模板已生成: {ann_file}")

    return ds_dir


def create_empty_coco_annotations(split: str, images_info: list, image_dir: Path) -> dict:
    """创建空的COCO标注结构（供Label Studio填充）"""
    images = []
    for idx, img_info in enumerate(images_info):
        img_path = image_dir / Path(img_info["image_path"]).name
        if img_path.exists():
            pil_img = Image.open(img_path)
            w, h = pil_img.size
        else:
            w, h = 1240, 1755  # 默认尺寸

        images.append({
            "id": idx + 1,
            "file_name": Path(img_info["image_path"]).name,
            "width": w,
            "height": h,
            "license": 1,
            "confidence": img_info["confidence"],
            "reasons": img_info.get("reasons", [])
        })

    return {
        "info": {
            "description": f"古舆图分割数据集 - {split}集",
            "version": "1.0",
            "year": 2026,
            "contributor": "志鉴团队",
            "split": split
        },
        "licenses": [{"id": 1, "name": "志鉴项目", "url": ""}],
        "categories": [
            {"id": cid, "name": info["name"], "supercategory": info["supercategory"]}
            for cid, info in MAP_CLASSES.items()
        ],
        "images": images,
        "annotations": []  # 待Label Studio填充
    }


def generate_preannotation_helpers(image_path: str) -> dict:
    """
    生成基于规则的预标注辅助数据
    用于在Label Studio中预加载标注，减少人工劳动

    Returns: 预检测到的候选区域
    """
    img = cv2.imread(image_path)
    if img is None:
        return {}

    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    candidates = {}

    # 1. 蓝色区域 → 可能是河流
    blue_mask = cv2.inRange(hsv, (90, 50, 50), (130, 255, 255))
    blue_contours, _ = cv2.findContours(blue_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates["河流"] = [
        cv2.boundingRect(c) for c in blue_contours
        if cv2.contourArea(c) > 500
    ]

    # 2. 棕色区域 → 可能是山脉
    brown_mask = cv2.inRange(hsv, (10, 50, 20), (30, 255, 150))
    brown_contours, _ = cv2.findContours(brown_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates["山脉"] = [
        cv2.boundingRect(c) for c in brown_contours
        if cv2.contourArea(c) > 300
    ]

    # 3. 边缘检测 → 可能是边界线/道路
    edges = cv2.Canny(gray, 30, 100)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50, minLineLength=100, maxLineGap=20)
    if lines is not None:
        line_boxes = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            x = min(x1, x2); y = min(y1, y2)
            w = abs(x2-x1) + 1; h = abs(y2-y1) + 1
            if h < 20 or w < 20:  # 可能是边界/道路
                line_boxes.append((x, y, x+w, y+h))
        candidates["边界线"] = line_boxes

    return candidates


# ─────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="舆图U-Net训练数据集准备")
    parser.add_argument("--source", default="data/ocr_training/images",
                        help="OCR训练图像目录")
    parser.add_argument("--output", default="data/maps",
                        help="输出目录")
    parser.add_argument("--min-confidence", type=float, default=0.35,
                        help="地图页筛选置信度阈值")
    parser.add_argument("--max-images", type=int, default=20,
                        help="最多选取图像数")
    parser.add_argument("--analyze-only", action="store_true",
                        help="仅分析不生成数据集")
    args = parser.parse_args()

    source_dir = args.source
    if not os.path.isabs(source_dir):
        # 相对于项目根目录
        project_root = Path(__file__).parent.parent
        source_dir = project_root / source_dir

    logger.info(f"扫描图像目录: {source_dir}")
    images = scan_gazetteer_images(str(source_dir))

    logger.info("=== 图像分类统计 ===")
    for chapter, files in images.items():
        logger.info(f"  {chapter}: {len(files)} 张")

    # 筛选舆图页
    candidates = select_map_pages_for_annotation(str(source_dir), args.min_confidence)
    selected = candidates[:args.max_images]

    if args.analyze_only:
        logger.info("=== 分析完成（--analyze-only 模式）===")
        return

    # 生成数据集
    logger.info("=== 生成数据集结构 ===")
    ds_dir = create_dataset_structure(args.output, selected)

    # 生成Label Studio项目文件
    logger.info("=== 生成Label Studio项目文件 ===")
    ls_dir = generate_label_studio_project(args.output, [c["image_path"] for c in selected])

    # 生成预标注报告
    logger.info("=== 预标注辅助分析 ===")
    preann_dir = Path(args.output) / "preannotations"
    preann_dir.mkdir(exist_ok=True)

    for candidate in selected[:5]:  # 只分析前5张
        img_path = candidate["image_path"]
        preann = generate_preannotation_helpers(img_path)
        out_path = preann_dir / f"{Path(img_path).stem}_preann.json"
        out_path.write_text(json.dumps(preann, ensure_ascii=False, indent=2))
        logger.info(f"  预标注候选: {Path(img_path).name} → {sum(len(v) for v in preann.values())} 个候选区域")

    logger.info(f"""
=== 完成！ ===

数据集目录: {ds_dir}
Label Studio项目: {ls_dir}
预标注候选: {preann_dir}

下一步：
1. 启动 Label Studio: label-studio start
2. 导入配置: {ls_dir / 'label_studio_config.xml'}
3. 导入图像: {ls_dir / 'import_images.json'}
4. 标注 {len(selected)} 张舆图
5. 导出COCO格式标注到: {ds_dir / 'annotations'}
""")


if __name__ == "__main__":
    main()
