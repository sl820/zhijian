#!/usr/bin/env python3
"""
舆图U-Net语义分割训练脚本

支持:
- 图像/掩码数据加载
- 数据增强（albumentations）
- 多类别IoU评估
- Checkpoint保存/加载
- 预训练encoder迁移学习

数据集格式:
    data_dir/
    ├── images/
    │   ├── train/          # 原始RGB图像 .png
    │   └── val/
    └── annotations/
        ├── train/          # 单通道掩码 .png，像素值=类别ID (0-5)
        └── val/

Usage:
    # 训练（从头）
    python scripts/train_map_segmenter.py --data data/map_segmentation --epochs 50 --batch 4

    # 继续训练
    python scripts/train_map_segmenter.py --data data/map_segmentation --resume models/map_unet_best.pth

    # 评估
    python scripts/train_map_segmenter.py --data data/map_segmentation --eval-only --checkpoint models/map_unet_best.pth
"""

import argparse
import logging
import os
import sys
import json
from pathlib import Path
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.optim.lr_scheduler import CosineAnnealingLR
import cv2
from PIL import Image
import random

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('train_map_segmenter.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 类别定义（与 app/map_extraction/ 保持一致）
# ─────────────────────────────────────────────────────────────────────────────
NUM_CLASSES = 6
CLASS_NAMES = ['背景', '河流', '山脉', '城市', '边界线', '文字标注']

# ImageNet 标准化
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

# 输入尺寸（训练时随机裁剪到此大小）
TRAIN_INPUT_SIZE = (512, 512)
VAL_INPUT_SIZE   = (512, 512)

# ─────────────────────────────────────────────────────────────────────────────
# 数据增强
# ─────────────────────────────────────────────────────────────────────────────
try:
    import albumentations as A
    HAS_ALBUMENTATIONS = True
except ImportError:
    HAS_ALBUMENTATIONS = False
    logger.warning("albumentations 未安装，数据增强将使用简陋版本。请运行: pip install albumentations")


def get_train_transform(input_size=TRAIN_INPUT_SIZE):
    """训练时数据增强"""
    if HAS_ALBUMENTATIONS:
        return A.Compose([
            A.RandomCrop(height=input_size[0], width=input_size[1], p=1.0),
            A.HorizontalFlip(p=0.5),
            A.VerticalFlip(p=0.3),
            A.Rotate(limit=15, p=0.5, border_mode=cv2.BORDER_CONSTANT),
            A.OneOf([
                A.GaussianBlur(blur_limit=(3, 5), p=1.0),
            ], p=0.3),
            A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.05, p=0.5),
            A.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            A.ToTensorV2(),
        ])
    else:
        # 简陋版增强（无albumentations）
        return None


def get_val_transform(input_size=VAL_INPUT_SIZE):
    if HAS_ALBUMENTATIONS:
        return A.Compose([
            A.CenterCrop(height=input_size[0], width=input_size[1], p=1.0),
            A.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
            A.ToTensorV2(),
        ])
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 数据集
# ─────────────────────────────────────────────────────────────────────────────
class MapSegmentationDataset(Dataset):
    """舆图语义分割数据集"""

    def __init__(self, images_dir, annotations_dir, transform=None, extend_prefix=''):
        """
        Args:
            images_dir: 图像目录
            annotations_dir: 掩码目录
            transform: albumentations transform
            extend_prefix: 文件名前缀（如 '' 或 'ext_'）
        """
        self.images_dir = Path(images_dir)
        self.annotations_dir = Path(annotations_dir)
        self.transform = transform

        # 查找所有图像文件
        self.image_files = sorted([
            f for f in self.images_dir.iterdir()
            if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.tif', '.tiff']
        ])
        logger.info(f"数据集: 找到 {len(self.image_files)} 张图像")

        if len(self.image_files) == 0:
            logger.error(f"未找到图像文件: {self.images_dir}")

    def __len__(self):
        return len(self.image_files)

    def __getitem__(self, idx):
        img_path = self.image_files[idx]
        ann_path = self.annotations_dir / img_path.name

        # 读取图像 (RGB)
        image = cv2.imread(str(img_path))
        if image is None:
            raise FileNotFoundError(f"无法读取图像: {img_path}")
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # 读取掩码 (单通道, 0-5)
        if ann_path.exists():
            mask = cv2.imread(str(ann_path), cv2.IMREAD_GRAYSCALE)
        else:
            logger.warning(f"掩码不存在，使用空白掩码: {ann_path}")
            mask = np.zeros(image.shape[:2], dtype=np.uint8)

        # 应用增强
        if self.transform:
            augmented = self.transform(image=image, mask=mask)
            image = augmented['image']
            mask = augmented['mask']
        else:
            # 简陋处理：缩放 + 归一化
            image = cv2.resize(image, TRAIN_INPUT_SIZE)
            mask = cv2.resize(mask, TRAIN_INPUT_SIZE, interpolation=cv2.INTER_NEAREST)
            image = image.astype(np.float32) / 255.0
            for i in range(3):
                image[:, :, i] = (image[:, :, i] - IMAGENET_MEAN[i]) / IMAGENET_STD[i]
            image = torch.from_numpy(image.transpose(2, 0, 1)).float()
            mask = torch.from_numpy(mask).long()

        # 确保mask是LongTensor（CrossEntropyLoss要求）
        if isinstance(mask, torch.Tensor):
            mask = mask.long()
        else:
            mask = torch.from_numpy(mask).long()

        return {
            'image': image,
            'mask': mask,
            'image_path': str(img_path),
        }


# ─────────────────────────────────────────────────────────────────────────────
# 损失函数
# ─────────────────────────────────────────────────────────────────────────────
class DiceLoss(nn.Module):
    def __init__(self, num_classes=NUM_CLASSES, smooth=1e-6):
        super().__init__()
        self.num_classes = num_classes
        self.smooth = smooth

    def forward(self, logits, targets):
        """
        Args:
            logits: (B, C, H, W) 未经softmax的原始logits
            targets: (B, H, W) 类别ID
        """
        probs = torch.softmax(logits, dim=1)  # (B, C, H, W)
        targets_one_hot = torch.zeros_like(probs).scatter_(
            1, targets.unsqueeze(1), 1  # (B, C, H, W)
        )

        # Dice per class
        dims = (0, 2, 3)  # B, H, W
        intersection = (probs * targets_one_hot).sum(dims)
        cardinality = probs.sum(dims) + targets_one_hot.sum(dims)
        dice = (2.0 * intersection + self.smooth) / (cardinality + self.smooth)
        return 1.0 - dice.mean()


class CombinedLoss(nn.Module):
    """BCE + Dice 组合损失"""

    def __init__(self, bce_weight=0.5, dice_weight=0.5):
        super().__init__()
        self.bce = nn.CrossEntropyLoss()
        self.dice = DiceLoss()
        self.bce_weight = bce_weight
        self.dice_weight = dice_weight

    def forward(self, logits, targets):
        bce_loss = self.bce(logits, targets)
        dice_loss = self.dice(logits, targets)
        return self.bce_weight * bce_loss + self.dice_weight * dice_loss


# ─────────────────────────────────────────────────────────────────────────────
# 评估指标
# ─────────────────────────────────────────────────────────────────────────────
def compute_iou(pred, target, num_classes=NUM_CLASSES):
    """
    计算每个类别的IoU
    Args:
        pred: (B, H, W) 预测类别ID
        target: (B, H, W) 真实类别ID
    Returns: dict {class_id: iou}
    """
    ious = {}
    for cls in range(num_classes):
        pred_cls = (pred == cls)
        target_cls = (target == cls)
        intersection = (pred_cls & target_cls).sum().item()
        union = (pred_cls | target_cls).sum().item()
        if union == 0:
            ious[cls] = 1.0  # 此类不存在于ground truth也不存在于预测
        else:
            ious[cls] = intersection / union
    return ious


def compute_mIoU(pred, target, num_classes=NUM_CLASSES):
    ious = compute_iou(pred, target, num_classes)
    return np.mean([v for v in ious.values()])


@torch.no_grad()
def evaluate(model, dataloader, device, num_classes=NUM_CLASSES):
    """在验证集上评估模型"""
    model.eval()
    total_loss = 0.0
    criterion = CombinedLoss()

    all_ious = {cls: [] for cls in range(num_classes)}
    count = 0

    for batch in dataloader:
        images = batch['image'].to(device)
        masks = batch['mask'].to(device)

        logits = model(images)
        loss = criterion(logits, masks)
        total_loss += loss.item()

        preds = torch.argmax(logits, dim=1)  # (B, H, W)

        for b in range(preds.shape[0]):
            ious = compute_iou(preds[b], masks[b], num_classes)
            for cls, iou_val in ious.items():
                all_ious[cls].append(iou_val)
            count += 1

    avg_loss = total_loss / max(count, 1)
    mean_ious = {cls: np.mean(vals) if vals else 0.0 for cls, vals in all_ious.items()}
    mIoU = np.mean(list(mean_ious.values()))

    return avg_loss, mean_ious, mIoU


# ─────────────────────────────────────────────────────────────────────────────
# 训练
# ─────────────────────────────────────────────────────────────────────────────
def train_one_epoch(model, dataloader, optimizer, criterion, device, scaler=None):
    model.train()
    total_loss = 0.0
    n_batches = 0

    for batch in dataloader:
        images = batch['image'].to(device)
        masks = batch['mask'].to(device)

        optimizer.zero_grad()

        if scaler:  # AMP
            with torch.cuda.amp.autocast():
                logits = model(images)
                loss = criterion(logits, masks)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            logits = model(images)
            loss = criterion(logits, masks)
            loss.backward()
            optimizer.step()

        total_loss += loss.item()
        n_batches += 1

    return total_loss / max(n_batches, 1)


def train(
    data_dir,
    epochs=50,
    batch_size=4,
    lr=1e-4,
    weight_decay=1e-5,
    device=None,
    resume=None,
    output_dir='models',
    num_workers=2,
):
    """完整训练流程"""

    # Device
    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"使用设备: {device}")

    # 数据目录
    data_dir = Path(data_dir)
    train_img_dir = data_dir / 'images' / 'train'
    train_ann_dir = data_dir / 'annotations' / 'train'
    val_img_dir = data_dir / 'images' / 'val'
    val_ann_dir = data_dir / 'annotations' / 'val'

    # 检查数据
    if not train_img_dir.exists():
        logger.error(f"训练图像目录不存在: {train_img_dir}")
        logger.error("请创建目录结构: data_dir/images/train/ 和 data_dir/annotations/train/")
        logger.error("或将图像放在 data_dir/images/（自动查找）")
        # 尝试查找图像
        for subdir in [data_dir / 'images', data_dir]:
            if subdir.exists():
                pngs = list(subdir.glob('*.png'))
                if pngs:
                    logger.info(f"在 {subdir} 找到 {len(pngs)} 张PNG图像")
                    train_img_dir = subdir
                    train_ann_dir = subdir.parent / 'annotations' / 'train'
                    break

    # 数据集
    train_transform = get_train_transform()
    val_transform = get_val_transform()

    try:
        train_dataset = MapSegmentationDataset(
            train_img_dir, train_ann_dir, transform=train_transform
        )
    except Exception as e:
        logger.error(f"训练数据集加载失败: {e}")
        return

    val_dataset = None
    if val_img_dir.exists() and val_ann_dir.exists():
        try:
            val_dataset = MapSegmentationDataset(
                val_img_dir, val_ann_dir, transform=val_transform
            )
        except Exception as e:
            logger.warning(f"验证数据集加载失败: {e}")

    if len(train_dataset) == 0:
        logger.error("训练集为空！请检查数据目录结构。")
        logger.info(f"""
数据目录结构应为:
{data_dir}/
├── images/
│   ├── train/          ← 放入训练图像(.png/.jpg)
│   └── val/            ← 放入验证图像
└── annotations/
    ├── train/          ← 放入对应掩码(.png, 0-5类别值)
    └── val/

掩码要求: 单通道PNG，像素值=类别ID (0=背景, 1=河流, 2=山脉, 3=城市, 4=边界线, 5=文字标注)
""")
        return

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True,
        drop_last=True,
    )

    val_loader = None
    if val_dataset:
        val_loader = DataLoader(
            val_dataset,
            batch_size=batch_size,
            shuffle=False,
            num_workers=num_workers,
            pin_memory=True,
        )

    logger.info(f"训练集: {len(train_dataset)} 张图像, batch_size={batch_size}")
    if val_loader:
        logger.info(f"验证集: {len(val_dataset)} 张图像")

    # 模型
    logger.info("初始化 AncientMapUNet 模型...")
    try:
        from app.map_extraction.unet_model import AncientMapUNet
        model = AncientMapUNet(pretrained_encoder=True)
    except ImportError:
        logger.warning("无法从 app.map_extraction 导入，使用本地定义")
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from app.map_extraction.unet_model import AncientMapUNet
        model = AncientMapUNet(pretrained_encoder=True)

    model = model.to(device)

    # 检查是否有GPU显存
    if device.type == 'cuda':
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
        logger.info(f"显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")

    # 优化器
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=lr * 0.01)

    # 损失函数
    criterion = CombinedLoss(bce_weight=0.5, dice_weight=0.5)

    # AMP scaler
    scaler = torch.cuda.amp.GradScaler() if device.type == 'cuda' else None

    # 恢复训练
    start_epoch = 0
    best_mIoU = 0.0
    if resume and Path(resume).exists():
        logger.info(f"从 checkpoint 恢复: {resume}")
        checkpoint = torch.load(resume, map_location=device)
        if 'model_state_dict' in checkpoint:
            model.load_state_dict(checkpoint['model_state_dict'])
            optimizer.load_state_dict(checkpoint.get('optimizer_state_dict', optimizer.state_dict()))
            start_epoch = checkpoint.get('epoch', 0) + 1
            best_mIoU = checkpoint.get('best_mIoU', 0.0)
            logger.info(f"恢复 epoch={start_epoch}, best_mIoU={best_mIoU:.4f}")
        else:
            model.load_state_dict(checkpoint)

    # 输出目录
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 训练循环
    logger.info(f"开始训练: {epochs} epochs")
    logger.info("=" * 60)

    history = {'train_loss': [], 'val_loss': [], 'mIoU': [], 'per_class_iou': []}

    for epoch in range(start_epoch, epochs):
        epoch_start = datetime.now()

        # 训练
        train_loss = train_one_epoch(model, train_loader, optimizer, criterion, device, scaler)

        # 验证
        if val_loader:
            val_loss, per_class_ious, mIoU = evaluate(model, val_loader, device)
            scheduler.step()

            epoch_time = (datetime.now() - epoch_start).total_seconds()

            logger.info(
                f"Epoch {epoch+1}/{epochs} | "
                f"train_loss={train_loss:.4f} | "
                f"val_loss={val_loss:.4f} | "
                f"mIoU={mIoU:.4f} | "
                f"per-class IoU: " + ", ".join([f"{CLASS_NAMES[c]}={v:.3f}" for c, v in per_class_ious.items()]) + " | "
                f"{epoch_time:.1f}s"
            )

            history['train_loss'].append(train_loss)
            history['val_loss'].append(val_loss)
            history['mIoU'].append(mIoU)
            history['per_class_iou'].append(per_class_ious)

            # 保存 best
            if mIoU > best_mIoU:
                best_mIoU = mIoU
                best_path = output_dir / 'map_unet_best.pth'
                torch.save({
                    'epoch': epoch,
                    'model_state_dict': model.state_dict(),
                    'optimizer_state_dict': optimizer.state_dict(),
                    'best_mIoU': best_mIoU,
                    'config': {
                        'num_classes': NUM_CLASSES,
                        'class_names': CLASS_NAMES,
                        'input_size': TRAIN_INPUT_SIZE,
                    }
                }, best_path)
                logger.info(f"  ★ New best mIoU: {best_mIoU:.4f} → {best_path}")

            # 定期保存
            if (epoch + 1) % 10 == 0:
                ckpt_path = output_dir / f'map_unet_epoch_{epoch+1}.pth'
                torch.save({
                    'epoch': epoch,
                    'model_state_dict': model.state_dict(),
                    'optimizer_state_dict': optimizer.state_dict(),
                    'best_mIoU': best_mIoU,
                }, ckpt_path)
                logger.info(f"  Checkpoint saved: {ckpt_path}")

        else:
            # 无验证集时用训练损失
            logger.info(f"Epoch {epoch+1}/{epochs} | train_loss={train_loss:.4f}")

    # 最终保存
    final_path = output_dir / 'map_unet_final.pth'
    torch.save({
        'epoch': epochs - 1,
        'model_state_dict': model.state_dict(),
        'best_mIoU': best_mIoU,
        'config': {
            'num_classes': NUM_CLASSES,
            'class_names': CLASS_NAMES,
            'input_size': TRAIN_INPUT_SIZE,
        }
    }, final_path)

    # 保存历史
    hist_path = output_dir / 'training_history.json'
    # Convert numpy types for JSON serialization
    hist_serializable = {}
    for k, v in history.items():
        if k == 'per_class_iou':
            hist_serializable[k] = [
                {str(cls): float(val) for cls, val in item.items()}
                for item in v
            ]
        else:
            hist_serializable[k] = [float(x) for x in v]
    with open(hist_path, 'w', encoding='utf-8') as f:
        json.dump(hist_serializable, f, indent=2, ensure_ascii=False)

    logger.info("=" * 60)
    logger.info(f"训练完成！ Best mIoU: {best_mIoU:.4f}")
    logger.info(f"模型保存: {output_dir}")
    return best_mIoU


# ─────────────────────────────────────────────────────────────────────────────
# 评估模式
# ─────────────────────────────────────────────────────────────────────────────
def eval_only(data_dir, checkpoint, device=None, num_workers=2):
    """仅评估模式"""
    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    data_dir = Path(data_dir)
    val_img_dir = data_dir / 'images' / 'val'
    val_ann_dir = data_dir / 'annotations' / 'val'

    val_transform = get_val_transform()
    val_dataset = MapSegmentationDataset(val_img_dir, val_ann_dir, transform=val_transform)
    val_loader = DataLoader(val_dataset, batch_size=2, shuffle=False, num_workers=num_workers, pin_memory=True)

    # 加载模型
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from app.map_extraction.unet_model import AncientMapUNet
    model = AncientMapUNet(pretrained_encoder=False)
    checkpoint_dict = torch.load(checkpoint, map_location=device)
    if 'model_state_dict' in checkpoint_dict:
        model.load_state_dict(checkpoint_dict['model_state_dict'])
    else:
        model.load_state_dict(checkpoint_dict)
    model = model.to(device)
    logger.info(f"模型已加载: {checkpoint}")

    # 评估
    val_loss, per_class_ious, mIoU = evaluate(model, val_loader, device)

    logger.info("=" * 60)
    logger.info(f"评估结果:")
    logger.info(f"  Val Loss: {val_loss:.4f}")
    logger.info(f"  mIoU:     {mIoU:.4f}")
    logger.info(f"  Per-class IoU:")
    for cls, iou_val in per_class_ious.items():
        bar = '█' * int(iou_val * 20)
        logger.info(f"    {CLASS_NAMES[cls]:10s}: {iou_val:.4f} {bar}")

    return mIoU, per_class_ious


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="舆图U-Net训练脚本")
    parser.add_argument('--data', default='data/map_segmentation', help='数据集根目录')
    parser.add_argument('--epochs', type=int, default=50, help='训练轮数')
    parser.add_argument('--batch', type=int, default=4, help='Batch size')
    parser.add_argument('--lr', type=float, default=1e-4, help='学习率')
    parser.add_argument('--wd', type=float, default=1e-5, help='Weight decay')
    parser.add_argument('--device', default=None, help='设备 (cuda/cpu)')
    parser.add_argument('--resume', default=None, help='恢复训练的checkpoint路径')
    parser.add_argument('--checkpoint', default=None, help='评估用的checkpoint路径')
    parser.add_argument('--output', default='models', help='模型输出目录')
    parser.add_argument('--num-workers', type=int, default=2, help='DataLoader worker数量')
    parser.add_argument('--eval-only', action='store_true', help='仅评估模式')
    args = parser.parse_args()

    if args.eval_only:
        if not args.checkpoint:
            logger.error("--eval-only 需要指定 --checkpoint")
            return
        eval_only(args.data, args.checkpoint, args.device, args.num_workers)
    else:
        train(
            data_dir=args.data,
            epochs=args.epochs,
            batch_size=args.batch,
            lr=args.lr,
            weight_decay=args.wd,
            device=args.device,
            resume=args.resume,
            output_dir=args.output,
            num_workers=args.num_workers,
        )


if __name__ == '__main__':
    main()
