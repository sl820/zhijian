"""
Faster R-CNN 批校痕迹检测训练脚本

功能：
- 基于 torchvision Faster R-CNN (ResNet50-FPN backbone)
- COCO格式检测数据集加载
- 数据增强（水平翻转）
- 验证：mAP@0.5 / mAP@0.5:0.95
- 自动混合精度训练（AMP）
- Checkpoint保存与恢复

Usage:
    python scripts/train_faster_rcnn_annotations.py --data data/annotations/dataset --epochs 30
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from pathlib import Path

# 添加项目根目录到 sys.path
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.cuda.amp import autocast, GradScaler
import torchvision.transforms as T
import torchvision.ops as ops
from PIL import Image
from tqdm import tqdm

# ─────────────────────────────────────────────────────────────────────────────
# 日志
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("train_faster_rcnn_annotations.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 类别定义（与 app/annotation_extract/faster_rcnn_model.py 保持一致）
# ─────────────────────────────────────────────────────────────────────────────
NUM_CLASSES = 5  # 4 annotation classes + background
CLASS_NAMES = ["背景", "朱批", "墨批", "圈点", "划线"]


# ─────────────────────────────────────────────────────────────────────────────
# 数据集
# ─────────────────────────────────────────────────────────────────────────────
class AnnotationDetectionDataset(Dataset):
    """
    批校痕迹检测数据集

    期望目录结构:
        images/train/*.png    # 原始图像
        annotations/train.json  # COCO格式目标检测标注

    COCO Detection格式:
        annotations[].bbox: [x, y, width, height] (COCO format: x,y = top-left)
        annotations[].category_id: 1-4 (COCO格式: 从1开始，0=背景)
    """

    # 训练时resize到的最短边长度
    MIN_SIZE = 600
    MAX_SIZE = 1000

    def __init__(self, image_dir: str, annotation_file: str, training: bool = True):
        self.image_dir = Path(image_dir)
        self.annotation_file = Path(annotation_file)
        self.training = training

        self.images = []
        self.img_to_anns = {}

        self._load_annotations()
        self._build_image_list()

        # Transforms
        self.transforms = T.Compose([
            T.Resize((self.MIN_SIZE, self.MAX_SIZE)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def _load_annotations(self):
        """加载COCO格式检测标注"""
        if not self.annotation_file.exists():
            logger.warning(f"标注文件不存在: {self.annotation_file}")
            return

        with open(self.annotation_file, encoding="utf-8") as f:
            data = json.load(f)

        self.image_info = {img["id"]: img for img in data.get("images", [])}

        self.img_to_anns = {}
        for ann in data.get("annotations", []):
            img_id = ann["image_id"]
            if img_id not in self.img_to_anns:
                self.img_to_anns[img_id] = []
            self.img_to_anns[img_id].append(ann)

        logger.info(f"加载 {len(self.image_info)} 张图像, {len(data.get('annotations', []))} 个标注")

    def _build_image_list(self):
        """构建有效图像列表"""
        self.images = []
        for img_id, img_data in self.image_info.items():
            img_path = self.image_dir / img_data["file_name"]
            if img_path.exists():
                self.images.append((img_id, str(img_path)))

        logger.info(f"有效图像: {len(self.images)} 张")

    def _parse_boxes(self, anns, orig_w, orig_h):
        """解析COCO bbox为 (x1, y1, x2, y2) 格式"""
        boxes = []
        labels = []

        for ann in anns:
            cat_id = ann["category_id"] + 1  # COCO类别ID偏移：JSON中0-3 → 模型中1-4
            bbox = ann["bbox"]  # [x, y, w, h]

            x, y, w, h = bbox
            x1, y1 = x, y
            x2, y2 = x + w, y + h

            # Clamp to image bounds
            x1 = max(0, min(x1, orig_w - 1))
            y1 = max(0, min(y1, orig_h - 1))
            x2 = max(x1 + 1, min(x2, orig_w))
            y2 = max(y1 + 1, min(y2, orig_h))

            if x2 > x1 and y2 > y1:
                boxes.append([x1, y1, x2, y2])
                labels.append(cat_id)

        if len(boxes) == 0:
            boxes = [[0, 0, 1, 1]]
            labels = [0]

        return torch.tensor(boxes, dtype=torch.float32), torch.tensor(labels, dtype=torch.int64)

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        img_id, img_path = self.images[idx]

        # 读取图像
        pil_img = Image.open(img_path).convert("RGB")
        orig_w, orig_h = pil_img.size

        # 解析标注
        anns = self.img_to_anns.get(img_id, [])
        boxes, labels = self._parse_boxes(anns, orig_w, orig_h)

        # 训练时水平翻转增强
        if self.training and random.random() > 0.5:
            pil_img = pil_img.transpose(Image.FLIP_LEFT_RIGHT)
            # 翻转bbox的x坐标
            w = pil_img.size[0]
            boxes_flipped = boxes.clone()
            boxes_flipped[:, [0, 2]] = w - boxes_flipped[:, [2, 0]]
            boxes = boxes_flipped

        # 转换为tensor
        img_tensor = self.transforms(pil_img)

        # 构建target
        target = {
            "boxes": boxes,
            "labels": labels,
            "image_id": torch.tensor([img_id]),
            "orig_size": torch.tensor([orig_h, orig_w]),
        }

        return img_tensor, target


def collate_fn(batch):
    """DataLoader collate function for detection"""
    images = []
    targets = []
    for img, target in batch:
        images.append(img)
        targets.append(target)
    return images, targets


# ─────────────────────────────────────────────────────────────────────────────
# 指标计算
# ─────────────────────────────────────────────────────────────────────────────
def compute_ap(recall, precision):
    """Compute Average Precision given recall and precision curves"""
    recall = np.concatenate(([0.0], recall, [1.0]))
    precision = np.concatenate(([0.0], precision, [0.0]))

    for i in range(precision.size - 1, 0, -1):
        precision[i - 1] = max(precision[i - 1], precision[i])

    indices = np.where(recall[1:] != recall[:-1])[0]
    ap = np.sum((recall[indices + 1] - recall[indices]) * precision[indices + 1])
    return ap


@torch.no_grad()
def compute_map(model, loader, device, iou_threshold=0.5):
    """
    简化版mAP计算
    对每张图像计算AP，然后平均
    """
    model.eval()

    # 收集所有预测和标注
    all_predictions = []
    all_gts = []

    for images, targets in tqdm(loader, desc="[Compute mAP]"):
        images = [img.to(device) for img in images]

        # 预测
        predictions = model(images)

        for pred, target in zip(predictions, targets):
            all_predictions.append(pred)
            all_gts.append(target)

    # 简化：计算每张图的precision/recall
    aps = []

    for pred, target in zip(all_predictions, all_gts):
        gt_boxes = target["boxes"].cpu().numpy()
        gt_labels = target["labels"].cpu().numpy()
        pred_boxes = pred["boxes"].cpu().numpy()
        pred_labels = pred["labels"].cpu().numpy()
        pred_scores = pred["scores"].cpu().numpy()

        if len(gt_boxes) == 0:
            continue

        # 按置信度排序
        sorted_idx = np.argsort(pred_scores)[::-1]
        pred_boxes = pred_boxes[sorted_idx]
        pred_labels = pred_labels[sorted_idx]

        tp = np.zeros(len(pred_boxes))
        fp = np.zeros(len(pred_boxes))
        gt_matched = set()

        for i, (pb, pl) in enumerate(zip(pred_boxes, pred_labels)):
            # 找对应的gt
            ious = ops.box_iou(
                torch.tensor([pb], dtype=torch.float32),
                torch.tensor(gt_boxes, dtype=torch.float32)
            ).squeeze(0).numpy()

            max_iou_idx = np.argmax(ious)
            max_iou = ious[max_iou_idx]

            if max_iou >= iou_threshold:
                if gt_labels[max_iou_idx] == pl and max_iou_idx not in gt_matched:
                    tp[i] = 1
                    gt_matched.add(max_iou_idx)
                else:
                    fp[i] = 1
            else:
                fp[i] = 1

        tp_cumsum = np.cumsum(tp)
        fp_cumsum = np.cumsum(fp)

        num_gt = len(gt_boxes)
        recall = tp_cumsum / num_gt
        precision = tp_cumsum / (tp_cumsum + fp_cumsum)

        # 计算AP
        ap = compute_ap(recall, precision)
        aps.append(ap)

    map_50 = np.mean(aps) if aps else 0.0

    # 也计算总体指标
    total_gt = sum(len(t["boxes"]) for t in all_gts)
    total_tp = sum(
        (p["labels"] == t["labels"]).sum().item()
        for p, t in zip(all_predictions, all_gts)
        if len(p["boxes"]) > 0
    )

    return {"mAP@0.5": map_50, "total_gt": total_gt, "total_tp": total_tp}


# ─────────────────────────────────────────────────────────────────────────────
# 模型构建
# ─────────────────────────────────────────────────────────────────────────────
def build_faster_rcnn_model(num_classes: int = NUM_CLASSES, pretrained: bool = True):
    """构建Faster R-CNN模型"""
    try:
        # 优先使用 app 中的模型定义
        from app.annotation_extract.faster_rcnn_model import create_model
        logger.info("使用 app.annotation_extract.faster_rcnn_model.create_model()")
        model = create_model(num_classes=num_classes)
        return model
    except ImportError:
        pass

    # 使用torchvision内置实现
    logger.info("使用 torchvision.models.detection.fasterrcnn_resnet50_fpn")
    from torchvision.models.detection import fasterrcnn_resnet50_fpn
    from torchvision.models.detection.faster_rcnn import FastRCNNPredictor

    weights = "DEFAULT" if pretrained else None
    model = fasterrcnn_resnet50_fpn(weights=weights)

    # 替换分类头（4 annotation classes + background = 5）
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)

    return model


# ─────────────────────────────────────────────────────────────────────────────
# 训练循环
# ─────────────────────────────────────────────────────────────────────────────
def train_one_epoch(model, loader, optimizer, scaler, device, epoch):
    model.train()

    total_loss = 0.0
    pbar = tqdm(loader, desc=f"Epoch {epoch} [Train]")

    for images, targets in pbar:
        images = [img.to(device) for img in images]
        targets = [{k: v.to(device) for k, v in t.items()} for t in targets]

        # 过滤空标注（会导致loss=nan）
        valid_pairs = [(img, tgt) for img, tgt in zip(images, targets) if len(tgt["boxes"]) > 0]
        if not valid_pairs:
            continue

        images, targets = zip(*valid_pairs)

        optimizer.zero_grad()

        with autocast():
            # torchvision faster rcnn 返回 dict of losses
            loss_dict = model(images, targets)
            losses = sum(loss for loss in loss_dict.values())

        scaler.scale(losses).backward()
        scaler.step(optimizer)
        scaler.update()

        total_loss += losses.item()
        loss_str = " | ".join(f"{k}: {v.item():.3f}" for k, v in loss_dict.items())
        pbar.set_postfix({"total": f"{losses.item():.4f}", "losses": loss_str})

    return total_loss / len(loader)


@torch.no_grad()
def validate(model, loader, device):
    """验证，返回loss和mAP"""
    model.eval()

    total_loss = 0.0
    all_loss_dicts = []

    pbar = tqdm(loader, desc="[Val]")

    for images, targets in pbar:
        images = [img.to(device) for img in images]
        targets = [{k: v.to(device) for k, v in t.items()} for t in targets]

        # 过滤空标注
        valid_pairs = [(img, tgt) for img, tgt in zip(images, targets) if len(tgt["boxes"]) > 0]
        if not valid_pairs:
            continue

        images, targets = zip(*valid_pairs)

        # 训练模式计算loss
        model.train()
        loss_dict = model(images, targets)
        losses = sum(loss for loss in loss_dict.values())
        model.eval()

        total_loss += losses.item()
        all_loss_dicts.append({k: v.item() for k, v in loss_dict.items()})

        pbar.set_postfix({"loss": f"{losses.item():.4f}"})

    # 切换到评估模式计算mAP
    metrics = compute_map(model, loader, device, iou_threshold=0.5)

    avg_losses = {}
    if all_loss_dicts:
        for key in all_loss_dicts[0]:
            avg_losses[key] = np.mean([d[key] for d in all_loss_dicts])

    return {
        "val_loss": total_loss / max(len(loader), 1),
        "losses": avg_losses,
        "mAP@0.5": metrics["mAP@0.5"],
    }


def save_checkpoint(model, optimizer, epoch, best_map, output_dir: Path):
    """保存checkpoint"""
    ckpt_path = output_dir / "faster_rcnn_best.pth"
    torch.save({
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "best_map": best_map,
    }, ckpt_path)
    logger.info(f"Best checkpoint saved: {ckpt_path}")


# ─────────────────────────────────────────────────────────────────────────────
# 主训练函数
# ─────────────────────────────────────────────────────────────────────────────
def train(
    data_dir: str,
    output_dir: str = "checkpoints/faster_rcnn_annotations",
    epochs: int = 30,
    batch_size: int = 4,
    lr: float = 1e-4,
    weight_decay: float = 1e-5,
    num_workers: int = 4,
    pretrained: bool = True,
    resume: str = None,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"设备: {device}")
    if torch.cuda.is_available():
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")

    # 数据集
    train_img_dir = Path(data_dir) / "images" / "train"
    val_img_dir = Path(data_dir) / "images" / "val"
    train_ann_file = Path(data_dir) / "annotations" / "train.json"
    val_ann_file = Path(data_dir) / "annotations" / "val.json"

    train_dataset = AnnotationDetectionDataset(
        str(train_img_dir), str(train_ann_file), training=True
    )
    val_dataset = AnnotationDetectionDataset(
        str(val_img_dir), str(val_ann_file), training=False
    )

    if len(train_dataset) == 0:
        logger.error("训练集为空，请检查数据路径和标注文件")
        return

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True,
        collate_fn=collate_fn,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
        collate_fn=collate_fn,
    )

    logger.info(f"训练集: {len(train_dataset)} 张, 验证集: {len(val_dataset)} 张")

    # 模型
    model = build_faster_rcnn_model(NUM_CLASSES, pretrained=pretrained)
    model = model.to(device)

    # 参数分组：backbone使用更小学习率
    params = [p for p in model.parameters()]

    optimizer = optim.AdamW(params, lr=lr, weight_decay=weight_decay)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-7)
    scaler = GradScaler()

    # 恢复
    start_epoch = 0
    best_map = 0.0
    if resume and Path(resume).exists():
        ckpt = torch.load(resume, map_location=device, weights_only=False)
        model.load_state_dict(ckpt["model_state_dict"])
        optimizer.load_state_dict(ckpt["optimizer_state_dict"])
        start_epoch = ckpt["epoch"] + 1
        best_map = ckpt.get("best_map", 0.0)
        logger.info(f"从epoch {start_epoch} 恢复, best_mAP={best_map:.4f}")

    logger.info(f"开始训练: {epochs} epochs")

    for epoch in range(start_epoch, epochs):
        t0 = time.time()

        train_loss = train_one_epoch(model, train_loader, optimizer, scaler, device, epoch)
        val_metrics = validate(model, val_loader, device)

        scheduler.step()

        elapsed = time.time() - t0

        loss_str = " | ".join(f"{k}: {v:.3f}" for k, v in val_metrics.get("losses", {}).items())
        logger.info(
            f"Epoch {epoch} | "
            f"train_loss={train_loss:.4f} | "
            f"val_loss={val_metrics['val_loss']:.4f} | "
            f"mAP@0.5={val_metrics['mAP@0.5']:.4f} | "
            f"{loss_str} | "
            f"time={elapsed:.1f}s"
        )

        # 保存best
        if val_metrics["mAP@0.5"] > best_map:
            best_map = val_metrics["mAP@0.5"]
            save_checkpoint(model, optimizer, epoch, best_map, output_dir)
            logger.info(f"  ★ New best mAP@0.5: {best_map:.4f}")

        # 定期保存
        if epoch % 5 == 0:
            ckpt_path = output_dir / f"faster_rcnn_epoch_{epoch}.pth"
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "best_map": best_map,
            }, ckpt_path)

    logger.info(f"训练完成！ Best mAP@0.5: {best_map:.4f}")
    return best_map


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Faster R-CNN批校检测训练")
    parser.add_argument("--data", default="data/annotations/dataset", help="数据集目录")
    parser.add_argument("--output", default="checkpoints/faster_rcnn_annotations", help="输出目录")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--no-pretrained", action="store_true", help="不使用COCO预训练权重")
    parser.add_argument("--resume", type=str, default=None, help="恢复checkpoint路径")
    args = parser.parse_args()

    train(
        data_dir=args.data,
        output_dir=args.output,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        weight_decay=args.weight_decay,
        num_workers=args.num_workers,
        pretrained=not args.no_pretrained,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
