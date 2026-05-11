"""
U-Net 古舆图语义分割训练脚本

功能：
- 纯PyTorch实现，不依赖pycocotools/segmentation_models_pytorch
- COCO格式数据集加载
- 数据增强（torchvision transforms）
- Dice + BCE 多类损失函数
- 验证：mIoU / 每类IoU
- 自动混合精度训练（AMP）
- Checkpoint保存与恢复

Usage:
    python scripts/train_unet_maps.py --data data/maps/dataset --epochs 50 --batch-size 8
"""

import argparse
import json
import logging
import os
import random
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field

# 添加项目根目录到 sys.path
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torch.cuda.amp import autocast, GradScaler
import torchvision.transforms as T
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
        logging.FileHandler("train_unet_maps.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 类别定义（与 app/map_extraction/unet_model.py 保持一致）
# ─────────────────────────────────────────────────────────────────────────────
NUM_CLASSES = 6
CLASS_NAMES = ["背景", "河流", "山脉", "城市", "边界线", "文字标注"]


# ─────────────────────────────────────────────────────────────────────────────
# 损失函数
# ─────────────────────────────────────────────────────────────────────────────
class DiceLoss(nn.Module):
    """Dice Loss for multi-class segmentation"""

    def __init__(self, smooth=1.0):
        super().__init__()
        self.smooth = smooth

    def forward(self, logits, targets):
        """
        logits: (B, C, H, W) raw logits
        targets: (B, H, W) class indices
        """
        num_classes = logits.size(1)
        device = logits.device

        # One-hot encode targets
        targets_one_hot = F.one_hot(targets.long(), num_classes)  # (B, H, W, C)
        targets_one_hot = targets_one_hot.permute(0, 3, 1, 2).float()  # (B, C, H, W)

        probs = F.softmax(logits, dim=1)

        # Per-class Dice
        dims = (0, 2, 3)
        intersection = (probs * targets_one_hot).sum(dim=dims)
        cardinality = probs.sum(dim=dims) + targets_one_hot.sum(dim=dims)
        dice = (2.0 * intersection + self.smooth) / (cardinality + self.smooth)

        # Average Dice across classes (ignore background optionally)
        return 1.0 - dice.mean()


class CombinedLoss(nn.Module):
    """Dice + BCE for stable training"""

    def __init__(self, dice_weight=0.5, bce_weight=0.5):
        super().__init__()
        self.dice_weight = dice_weight
        self.bce_weight = bce_weight
        self.dice = DiceLoss()
        self.bce = nn.CrossEntropyLoss()

    def forward(self, logits, targets):
        return (
            self.dice_weight * self.dice(logits, targets)
            + self.bce_weight * self.bce(logits, targets)
        )


# ─────────────────────────────────────────────────────────────────────────────
# 数据集
# ─────────────────────────────────────────────────────────────────────────────
class MapSegmentationDataset(Dataset):
    """
    古舆图语义分割数据集

    支持两种格式:
    1. PNG mask格式（推荐）:
        images/train/*.png       # 原始图像
        masks/train/*_mask.png   # 预渲染的灰度mask (0-5 class indices)

    2. COCO格式:
        images/train/*.png       # 原始图像
        annotations/train.json   # COCO格式标注
    """

    # 训练时的图像尺寸
    TRAIN_SIZE = (512, 512)

    def __init__(self, image_dir: str, annotation_file: str = None, transform=None, training: bool = True, mask_dir: str = None):
        self._use_png_masks = False  # Will be set True if using PNG mask format
        self.image_dir = Path(image_dir)
        self.annotation_file = Path(annotation_file) if annotation_file else None
        self.mask_dir = Path(mask_dir) if mask_dir else None
        self.transform = transform
        self.training = training

        self.images = []

        # 优先使用PNG mask格式
        if self.mask_dir and self.mask_dir.exists():
            self._load_from_png_masks()
        elif self.annotation_file and self.annotation_file.exists():
            self._load_annotations()
            self._build_image_mask_map()
        else:
            # 尝试自动查找mask目录
            auto_mask_dir = Path(str(self.image_dir).replace("/images/", "/masks/"))
            if auto_mask_dir.exists():
                self.mask_dir = auto_mask_dir
                self._load_from_png_masks()
            else:
                logger.warning(f"未找到标注文件或mask目录")
                self.images = []

        # Transforms
        self.image_transform = T.Compose([
            T.Resize(self.TRAIN_SIZE),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def _load_from_png_masks(self):
        """从PNG mask文件加载数据集（推荐方式）"""
        img_dir = self.image_dir
        mask_dir = self.mask_dir

        self.images = []
        for img_path in sorted(img_dir.glob("*.png")):
            # 查找对应的mask文件
            mask_name = img_path.stem + "_mask.png"
            mask_path = mask_dir / mask_name
            if mask_path.exists():
                self.images.append((str(img_path), str(mask_path)))

        self._use_png_masks = True
        logger.info(f"从PNG mask加载 {len(self.images)} 张图像")

    def _load_annotations(self):
        """加载COCO格式标注"""
        if not self.annotation_file.exists():
            logger.warning(f"标注文件不存在: {self.annotation_file}")
            return

        try:
            # Try UTF-8 first, then GBK
            for enc in ["utf-8", "gbk", "gb2312"]:
                try:
                    with open(self.annotation_file, encoding=enc) as f:
                        data = json.load(f)
                    break
                except UnicodeDecodeError:
                    continue

            # 建立 image_id → image_info 映射
            self.image_info = {img["id"]: img for img in data.get("images", [])}

            # 建立 image_id → annotations 映射
            self.img_to_anns = {}
            for ann in data.get("annotations", []):
                img_id = ann["image_id"]
                if img_id not in self.img_to_anns:
                    self.img_to_anns[img_id] = []
                self.img_to_anns[img_id].append(ann)

            logger.info(f"加载 {len(self.image_info)} 张图像, {len(data.get('annotations', []))} 个标注")
        except Exception as e:
            logger.warning(f"COCO标注加载失败: {e}")

    def _build_image_mask_map(self):
        """构建图像路径列表"""
        self.images = []
        for img_id, img_data in self.image_info.items():
            img_path = self.image_dir / img_data["file_name"]
            if img_path.exists():
                self.images.append((img_id, str(img_path)))

        logger.info(f"有效图像: {len(self.images)} 张")

    def _render_mask(self, img_id: int, target_size: tuple) -> np.ndarray:
        """
        将COCO polygon标注渲染为(H,W) mask图像
        """
        h, w = target_size
        mask = np.zeros((h, w), dtype=np.uint8)

        anns = self.img_to_anns.get(img_id, [])
        if not anns:
            return mask

        scale_x = w / self.image_info[img_id]["width"]
        scale_y = h / self.image_info[img_id]["height"]

        import cv2

        for ann in anns:
            cat_id = ann["category_id"]
            seg = ann.get("segmentation")
            if not seg:
                continue

            for polygon in seg:
                if len(polygon) < 6:
                    continue
                pts = np.array(polygon).reshape(-1, 2)
                # Scale to target size
                pts[:, 0] *= scale_x
                pts[:, 1] *= scale_y
                pts = pts.astype(np.int32)
                cv2.fillPoly(mask, [pts], color=int(cat_id))

        return mask

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        if self._use_png_masks:
            img_path, mask_path = self.images[idx]
            pil_img = Image.open(img_path).convert("RGB")
            mask = np.array(Image.open(mask_path))
            # Resize mask to target size
            mask = np.array(Image.fromarray(mask).resize((self.TRAIN_SIZE[1], self.TRAIN_SIZE[0]), Image.NEAREST))
        else:
            img_id, img_path = self.images[idx]
            pil_img = Image.open(img_path).convert("RGB")
            mask = self._render_mask(img_id, self.TRAIN_SIZE)

        # 应用图像变换
        img_tensor = self.image_transform(pil_img)

        # Simple augmentation during training
        if self.training and random.random() > 0.5:
            # 随机水平翻转
            img_tensor = torch.flip(img_tensor, dims=[2])
            mask = np.flip(mask, axis=1).copy()

        mask_tensor = torch.from_numpy(mask).long()

        return img_tensor, mask_tensor


# ─────────────────────────────────────────────────────────────────────────────
# 指标计算
# ─────────────────────────────────────────────────────────────────────────────
def compute_iou(pred: torch.Tensor, target: torch.Tensor, num_classes: int) -> np.ndarray:
    """
    计算每类IoU

    pred: (B, H, W) predictions
    target: (B, H, W) targets
    returns: (num_classes,) IoU per class
    """
    ious = []
    pred = pred.cpu().numpy()
    target = target.cpu().numpy()

    for cls in range(num_classes):
        pred_cls = pred == cls
        target_cls = target == cls
        intersection = np.logical_and(pred_cls, target_cls).sum()
        union = np.logical_or(pred_cls, target_cls).sum()
        if union == 0:
            ious.append(float("nan"))
        else:
            ious.append(float(intersection / union))

    return np.array(ious)


def compute_metrics(pred_logits: torch.Tensor, targets: torch.Tensor, num_classes: int) -> dict:
    """计算验证指标"""
    preds = pred_logits.argmax(dim=1)  # (B, H, W)

    # Per-class IoU
    ious = compute_iou(preds, targets, num_classes)
    valid_ious = ious[~np.isnan(ious)]
    miou = float(valid_ious.mean()) if len(valid_ious) > 0 else 0.0

    # Pixel accuracy
    acc = (preds == targets).float().mean().item()

    return {
        "mIoU": miou,
        "pixel_acc": acc,
        "per_class_iou": {CLASS_NAMES[i]: float(v) for i, v in enumerate(ious)},
    }


# ─────────────────────────────────────────────────────────────────────────────
# U-Net 模型（使用 app/map_extraction/unet_model.py 中的实现）
# ─────────────────────────────────────────────────────────────────────────────
def build_unet_model(pretrained_encoder: bool = True):
    """构建U-Net模型"""
    try:
        from app.map_extraction.unet_model import AncientMapUNet
        logger.info("使用 AncientMapUNet (内置ResNet34编码器)")
        return AncientMapUNet(pretrained_encoder=pretrained_encoder)
    except ImportError:
        logger.warning("AncientMapUNet导入失败，使用简单U-Net")
        return SimpleUNet(in_channels=3, num_classes=NUM_CLASSES)


class SimpleUNet(nn.Module):
    """简化版U-Net（纯PyTorch，不依赖smp）"""

    def __init__(self, in_channels=3, num_classes=6):
        super().__init__()
        ch = [64, 128, 256, 512]

        # Encoder
        self.enc1 = self._conv_block(in_channels, ch[0])
        self.enc2 = self._conv_block(ch[0], ch[1])
        self.enc3 = self._conv_block(ch[1], ch[2])
        self.enc4 = self._conv_block(ch[2], ch[3])

        self.pool = nn.MaxPool2d(2)

        # Bottleneck
        self.bottleneck = self._conv_block(ch[3], ch[3] * 2)

        # Decoder
        self.up4 = nn.ConvTranspose2d(ch[3] * 2, ch[3], 2, stride=2)
        self.dec4 = self._conv_block(ch[3] * 2, ch[3])

        self.up3 = nn.ConvTranspose2d(ch[3], ch[2], 2, stride=2)
        self.dec3 = self._conv_block(ch[2] * 2, ch[2])

        self.up2 = nn.ConvTranspose2d(ch[2], ch[1], 2, stride=2)
        self.dec2 = self._conv_block(ch[1] * 2, ch[1])

        self.up1 = nn.ConvTranspose2d(ch[1], ch[0], 2, stride=2)
        self.dec1 = self._conv_block(ch[0] * 2, ch[0])

        self.final = nn.Conv2d(ch[0], num_classes, 1)

    def _conv_block(self, in_ch, out_ch):
        return nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        # Encoder
        e1 = self.enc1(x)
        e2 = self.enc2(self.pool(e1))
        e3 = self.enc3(self.pool(e2))
        e4 = self.enc4(self.pool(e3))

        # Bottleneck
        b = self.bottleneck(self.pool(e4))

        # Decoder with skip connections
        d4 = self.up4(b)
        d4 = self._pad_crop(d4, e4)
        d4 = self.dec4(torch.cat([d4, e4], dim=1))

        d3 = self.up3(d4)
        d3 = self._pad_crop(d3, e3)
        d3 = self.dec3(torch.cat([d3, e3], dim=1))

        d2 = self.up2(d3)
        d2 = self._pad_crop(d2, e2)
        d2 = self.dec2(torch.cat([d2, e2], dim=1))

        d1 = self.up1(d2)
        d1 = self._pad_crop(d1, e1)
        d1 = self.dec1(torch.cat([d1, e1], dim=1))

        return self.final(d1)

    def _pad_crop(self, x, target):
        """Pad or crop x to match target spatial dimensions"""
        diff_h = target.size(2) - x.size(2)
        diff_w = target.size(3) - x.size(3)
        if diff_h > 0:
            x = F.pad(x, [0, 0, diff_h // 2, diff_h - diff_h // 2])
        elif diff_h < 0:
            x = x[:, :, -diff_h // 2 : x.size(2) + diff_h // 2, :]
        if diff_w > 0:
            x = F.pad(x, [diff_w // 2, diff_w - diff_w // 2, 0, 0])
        elif diff_w < 0:
            x = x[:, :, :, -diff_w // 2 : x.size(3) + diff_w // 2]
        return x


# ─────────────────────────────────────────────────────────────────────────────
# 训练循环
# ─────────────────────────────────────────────────────────────────────────────
def train_one_epoch(
    model, loader, criterion, optimizer, scaler, device, epoch
):
    model.train()
    total_loss = 0.0
    pbar = tqdm(loader, desc=f"Epoch {epoch} [Train]")

    for images, masks in pbar:
        images = images.to(device)
        masks = masks.to(device)

        optimizer.zero_grad()

        with autocast():
            logits = model(images)
            loss = criterion(logits, masks)

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        total_loss += loss.item()
        pbar.set_postfix({"loss": f"{loss.item():.4f}"})

    return total_loss / len(loader)


@torch.no_grad()
def validate(model, loader, criterion, device):
    model.eval()
    total_loss = 0.0
    all_metrics = {"mIoU": [], "pixel_acc": []}

    pbar = tqdm(loader, desc="[Val]")

    for images, masks in pbar:
        images = images.to(device)
        masks = masks.to(device)

        logits = model(images)
        loss = criterion(logits, masks)
        total_loss += loss.item()

        metrics = compute_metrics(logits, masks, NUM_CLASSES)
        all_metrics["mIoU"].append(metrics["mIoU"])
        all_metrics["pixel_acc"].append(metrics["pixel_acc"])

        pbar.set_postfix({"loss": f"{loss.item():.4f}", "mIoU": f"{metrics['mIoU']:.3f}"})

    return {
        "val_loss": total_loss / len(loader),
        "mIoU": np.mean(all_metrics["mIoU"]),
        "pixel_acc": np.mean(all_metrics["pixel_acc"]),
    }


def save_checkpoint(model, optimizer, epoch, best_miou, checkpoint_path: Path):
    """保存checkpoint"""
    checkpoint = {
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "best_miou": best_miou,
    }
    torch.save(checkpoint, checkpoint_path)
    logger.info(f"Checkpoint已保存: {checkpoint_path}")


# ─────────────────────────────────────────────────────────────────────────────
# 主训练函数
# ─────────────────────────────────────────────────────────────────────────────
def train(
    data_dir: str,
    output_dir: str = "checkpoints",
    epochs: int = 50,
    batch_size: int = 8,
    lr: float = 1e-4,
    weight_decay: float = 1e-5,
    num_workers: int = 4,
    pretrained_encoder: bool = True,
    resume: str = None,
):
    """
    主训练函数
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 设备
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"设备: {device}")
    if torch.cuda.is_available():
        logger.info(f"GPU: {torch.cuda.get_device_name(0)}")

    # 数据集
    train_img_dir = Path(data_dir) / "images" / "train"
    val_img_dir = Path(data_dir) / "images" / "val"
    train_mask_dir = Path(data_dir) / "masks" / "train"
    val_mask_dir = Path(data_dir) / "masks" / "val"
    train_ann_file = Path(data_dir) / "annotations" / "train.json"
    val_ann_file = Path(data_dir) / "annotations" / "val.json"

    train_dataset = MapSegmentationDataset(
        str(train_img_dir), str(train_ann_file), training=True, mask_dir=str(train_mask_dir)
    )
    val_dataset = MapSegmentationDataset(
        str(val_img_dir), str(val_ann_file), training=False, mask_dir=str(val_mask_dir)
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
        drop_last=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
    )

    logger.info(f"训练集: {len(train_dataset)} 张, 验证集: {len(val_dataset)} 张")

    # 模型
    model = build_unet_model(pretrained_encoder=pretrained_encoder)
    model = model.to(device)

    # 损失、优化器
    criterion = CombinedLoss(dice_weight=0.5, bce_weight=0.5)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    scaler = GradScaler()

    # 恢复训练
    start_epoch = 0
    best_miou = 0.0
    if resume and Path(resume).exists():
        ckpt = torch.load(resume, map_location=device)
        model.load_state_dict(ckpt["model_state_dict"])
        optimizer.load_state_dict(ckpt["optimizer_state_dict"])
        start_epoch = ckpt["epoch"] + 1
        best_miou = ckpt.get("best_miou", 0.0)
        logger.info(f"从epoch {start_epoch} 恢复训练, best_miou={best_miou:.4f}")

    # 训练循环
    logger.info(f"开始训练: {epochs} epochs")
    for epoch in range(start_epoch, epochs):
        t0 = time.time()

        train_loss = train_one_epoch(model, train_loader, criterion, optimizer, scaler, device, epoch)
        val_metrics = validate(model, val_loader, criterion, device)

        scheduler.step()

        elapsed = time.time() - t0

        logger.info(
            f"Epoch {epoch} | "
            f"train_loss={train_loss:.4f} | "
            f"val_loss={val_metrics['val_loss']:.4f} | "
            f"mIoU={val_metrics['mIoU']:.4f} | "
            f"pix_acc={val_metrics['pixel_acc']:.4f} | "
            f"lr={scheduler.get_last_lr()[0]:.2e} | "
            f"time={elapsed:.1f}s"
        )

        # 每5个epoch打印per-class IoU
        if epoch % 5 == 0:
            logger.info(f"  Per-class IoU: {val_metrics.get('per_class_iou', {})}")

        # 保存best模型
        if val_metrics["mIoU"] > best_miou:
            best_miou = val_metrics["mIoU"]
            best_path = output_dir / "unet_ancient_map_best.pth"
            save_checkpoint(model, optimizer, epoch, best_miou, best_path)
            logger.info(f"  ★ New best mIoU: {best_miou:.4f}")

        # 定期保存checkpoint
        if epoch % 10 == 0:
            ckpt_path = output_dir / f"unet_epoch_{epoch}.pth"
            save_checkpoint(model, optimizer, epoch, best_miou, ckpt_path)

    logger.info(f"训练完成！ Best mIoU: {best_miou:.4f}")
    return best_miou


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="U-Net舆图分割训练")
    parser.add_argument("--data", default="data/maps/dataset", help="数据集目录")
    parser.add_argument("--output", default="checkpoints/unet_maps", help="输出目录")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--no-pretrained", action="store_true", help="不使用ImageNet预训练编码器")
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
        pretrained_encoder=not args.no_pretrained,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
