#!/usr/bin/env python3
"""
舆图分割数据集快速准备工具

功能：
1. 从源图像目录扫描并复制到数据集目录
2. 使用规则预标注（颜色/边缘检测）生成半自动掩膜
3. 人工在 Labelme/CVAT 中精修

Usage:
    # 从现有图像生成数据集（自动预标注）
    python scripts/prepare_map_dataset.py --source data/raw/kangxi --output data/map_segmentation

    # 仅创建空掩膜（纯人工标注）
    python scripts/prepare_map_dataset.py --source data/raw/kangxi --output data/map_segmentation --empty-masks
"""

import argparse
import logging
import shutil
import cv2
import numpy as np
from pathlib import Path
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 舆图类别（与 unet_model.py 一致）
CLASS_IDS = {
    'background': 0,
    'river': 1,
    'mountain': 2,
    'city': 3,
    'boundary': 4,
    'text': 5,
}

# HSV颜色范围
COLOR_RANGES = {
    'river': {  # 青色/蓝色
        'lower': (90, 50, 50),
        'upper': (130, 255, 255),
    },
    'mountain': {  # 棕色
        'lower': (8, 30, 20),
        'upper': (35, 200, 180),
    },
    'city': {  # 红色/橙色
        'lower': (0, 50, 50),
        'upper': (20, 255, 255),
    },
}


def create_blank_mask(width, height):
    """创建空白掩膜（全为背景0）"""
    return np.zeros((height, width), dtype=np.uint8)


def auto_annotate_image(image_path, min_area=200):
    """
    基于颜色规则的半自动掩膜生成

    Args:
        image_path: 源图像路径
        min_area: 最小区域面积阈值

    Returns:
        mask: 单通道掩膜 (H, W) uint8, 0-5 类别值
    """
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"无法读取图像: {image_path}")

    h, w = img.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 1. 河流（蓝青色区域）
    river_lower = np.array([90, 50, 50])
    river_upper = np.array([130, 255, 255])
    river_mask = cv2.inRange(hsv, river_lower, river_upper)
    river_mask = cv2.morphologyEx(river_mask, cv2.MORPH_OPEN, np.ones((3, 3)))
    river_mask = cv2.morphologyEx(river_mask, cv2.MORPH_CLOSE, np.ones((5, 5)))
    mask[river_mask > 0] = CLASS_IDS['river']
    logger.debug(f"  河流候选: {(river_mask > 0).sum()} 像素")

    # 2. 山脉（棕色区域）
    brown_lower = np.array([8, 30, 20])
    brown_upper = np.array([35, 200, 180])
    mountain_mask = cv2.inRange(hsv, brown_lower, brown_upper)
    mountain_mask = cv2.morphologyEx(mountain_mask, cv2.MORPH_OPEN, np.ones((3, 3)))
    mask[mountain_mask > 0] = CLASS_IDS['mountain']
    logger.debug(f"  山脉候选: {(mountain_mask > 0).sum()} 像素")

    # 3. 城市（红/橙色小区域 - 点状）
    red_lower1 = np.array([0, 50, 50])
    red_upper1 = np.array([10, 255, 255])
    red_lower2 = np.array([160, 50, 50])
    red_upper2 = np.array([180, 255, 255])
    city_mask1 = cv2.inRange(hsv, red_lower1, red_upper1)
    city_mask2 = cv2.inRange(hsv, red_lower2, red_upper2)
    city_mask = cv2.bitwise_or(city_mask1, city_mask2)
    # 去除小噪点
    city_mask = cv2.morphologyEx(city_mask, cv2.MORPH_OPEN, np.ones((3, 3)))
    mask[city_mask > 0] = CLASS_IDS['city']
    logger.debug(f"  城市候选: {(city_mask > 0).sum()} 像素")

    # 4. 边界线（边缘检测 + 霍夫变换）
    edges = cv2.Canny(gray, 30, 100)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                              minLineLength=50, maxLineGap=20)
    if lines is not None:
        boundary_mask = np.zeros((h, w), dtype=np.uint8)
        for line in lines:
            x1, y1, x2, y2 = line[0]
            cv2.line(boundary_mask, (x1, y1), (x2, y2), 255, 2)
        # 膨胀连接断点
        boundary_mask = cv2.dilate(boundary_mask, np.ones((3, 3)), iterations=1)
        mask[boundary_mask > 0] = CLASS_IDS['boundary']
        logger.debug(f"  边界线候选: {(boundary_mask > 0).sum()} 像素")

    # 5. 文字标注（高对比度区域/连通组件分析）
    # 使用 MSER 检测文字区域
    try:
        mser = cv2.MSER_create(min_area=30, max_area=500)
        regions, _ = mser.detectRegions(gray)
        text_mask = np.zeros((h, w), dtype=np.uint8)
        for region in regions:
            x, y, w_region, h_region = cv2.boundingRect(region)
            if h_region < 50 and w_region < 100:  # 文字大小约束
                cv2.rectangle(text_mask, (x, y), (x + w_region, y + h_region), 255, -1)
        text_mask = cv2.morphologyEx(text_mask, cv2.MORPH_CLOSE, np.ones((2, 2)))
        mask[text_mask > 0] = CLASS_IDS['text']
        logger.debug(f"  文字候选: {(text_mask > 0).sum()} 像素")
    except Exception:
        pass

    return mask


def prepare_dataset(source_dir, output_dir, empty_masks=False, split_ratio=0.8):
    """
    准备数据集目录结构

    Args:
        source_dir: 源图像目录
        output_dir: 输出根目录
        empty_masks: 是否创建空掩膜（而非自动标注）
        split_ratio: 训练/验证划分比例
    """
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)

    # 扫描图像
    image_files = sorted([
        f for f in source_dir.glob('*.png')
        if f.suffix.lower() == '.png'
    ])

    if not image_files:
        # 尝试jpg
        image_files = sorted([
            f for f in source_dir.glob('*.jpg')
        ])

    if not image_files:
        logger.error(f"未找到PNG/JPG图像: {source_dir}")
        return

    logger.info(f"扫描到 {len(image_files)} 张图像")

    # 创建目录
    (output_dir / 'images' / 'train').mkdir(parents=True, exist_ok=True)
    (output_dir / 'images' / 'val').mkdir(parents=True, exist_ok=True)
    (output_dir / 'annotations' / 'train').mkdir(parents=True, exist_ok=True)
    (output_dir / 'annotations' / 'val').mkdir(parents=True, exist_ok=True)

    # 划分
    n_train = int(len(image_files) * split_ratio)
    train_files = image_files[:n_train]
    val_files = image_files[n_train:]

    logger.info(f"训练集: {len(train_files)} 张")
    logger.info(f"验证集: {len(val_files)} 张")

    for files, split in [(train_files, 'train'), (val_files, 'val')]:
        for img_path in files:
            # 复制图像
            dst_img = output_dir / 'images' / split / img_path.name
            if not dst_img.exists():
                shutil.copy(img_path, dst_img)

            # 生成掩膜
            if empty_masks:
                # 创建空掩膜
                pil_img = __import__('PIL').Image.open(img_path)
                w, h = pil_img.size
                mask = np.zeros((h, w), dtype=np.uint8)
            else:
                # 自动预标注
                mask = auto_annotate_image(img_path)

            # 保存掩膜（PNG格式，类别值编码）
            mask_path = output_dir / 'annotations' / split / img_path.name
            cv2.imwrite(str(mask_path), mask)
            logger.info(f"  {img_path.name}: 掩膜已生成 (非零像素: {(mask > 0).sum()})")

    # 生成数据集元信息
    meta = {
        'num_train': len(train_files),
        'num_val': len(val_files),
        'num_classes': 6,
        'classes': CLASS_IDS,
        'created': str(Path(__file__).resolve()),
    }
    meta_path = output_dir / 'dataset_meta.json'
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    logger.info(f"""
{'='*60}
数据集准备完成！

目录结构:
{output_dir}
├── images/
│   ├── train/   ({len(train_files)} 张)
│   └── val/     ({len(val_files)} 张)
└── annotations/
    ├── train/
    └── val/

训练命令:
    python scripts/train_map_segmenter.py --data {output_dir} --epochs 50 --batch 4

如需精修标注（推荐 Labelme）:
    pip install labelme
    labelme {output_dir / 'images' / 'train'}

或使用 CVAT 进行高效标注。
""")

    # 生成可视化对比图
    vis_dir = output_dir / 'preannotation_preview'
    vis_dir.mkdir(parents=True, exist_ok=True)
    for img_path in (train_files + val_files)[:3]:  # 只预览前3张
        img = cv2.imread(str(img_path))
        mask = auto_annotate_image(img_path)
        # 彩色掩膜
        color_mask = np.zeros((*mask.shape, 3), dtype=np.uint8)
        color_map = {
            1: (0, 255, 255),    # 河流 - 青色
            2: (139, 90, 43),     # 山脉 - 棕色
            3: (255, 0, 0),      # 城市 - 红色
            4: (0, 255, 0),      # 边界 - 绿色
            5: (255, 255, 0),    # 文字 - 黄色
        }
        for cls_id, color in color_map.items():
            color_mask[mask == cls_id] = color

        # 叠加可视化
        vis = cv2.addWeighted(img, 0.6, color_mask, 0.4, 0)
        # 添加图例
        legend = np.full((60, vis.shape[1], 3), 255, dtype=np.uint8)
        y = 20
        for cls_id, (name, color) in enumerate(zip(
            ['河流', '山脉', '城市', '边界线', '文字'],
            [(0, 255, 255), (139, 90, 43), (255, 0, 0), (0, 255, 0), (255, 255, 0)]
        )):
            cv2.rectangle(legend, (cls_id * 120 + 10, y - 10), (cls_id * 120 + 30, y + 10), color, -1)
            cv2.putText(legend, name, (cls_id * 120 + 35, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        vis_legend = np.vstack([vis, legend])

        out_path = vis_dir / f'{img_path.stem}_preview.png'
        cv2.imwrite(str(out_path), vis_legend)
        logger.info(f"预览图: {out_path}")

    logger.info(f"预标注预览图已保存: {vis_dir}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="舆图分割数据集准备工具")
    parser.add_argument('--source', required=True, help='源图像目录（如 data/raw/kangxi）')
    parser.add_argument('--output', default='data/map_segmentation', help='输出数据集目录')
    parser.add_argument('--empty-masks', action='store_true', help='创建空白掩膜（纯人工标注）')
    parser.add_argument('--split', type=float, default=0.8, help='训练集划分比例')
    args = parser.parse_args()

    prepare_dataset(args.source, args.output, args.empty_masks, args.split)
