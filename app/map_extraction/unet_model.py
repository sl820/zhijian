"""
U-Net model for semantic segmentation of ancient Chinese maps.
Supports 6 classes: background, rivers, mountains, cities/settlements, boundaries/roads, text labels.
"""

import logging
from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models

logger = logging.getLogger(__name__)

# Try to import segmentation_models_pytorch, fall back to scratch implementation
try:
    import segmentation_models_pytorch as smp

    HAS_SMP = True
    logger.info("segmentation_models_pytorch available, using ResNet34 encoder from smp")
except ImportError:
    HAS_SMP = False
    logger.info("segmentation_models_pytorch not available, building ResNet34 encoder from scratch")


# ─────────────────────────────────────────────────────────────────────────────
# Helper modules
# ─────────────────────────────────────────────────────────────────────────────

class ConvBlock(nn.Module):
    """Two consecutive 3x3 convolutions with BatchNorm and ReLU."""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.conv(x)


class UpBlock(nn.Module):
    """Upsampling block: 2x upsample concatenated with skip connection."""

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.up = nn.ConvTranspose2d(in_channels, in_channels // 2, kernel_size=2, stride=2)
        self.conv = ConvBlock(in_channels, out_channels)

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = self.up(x)
        # Handle size mismatch (when spatial dimensions don't align)
        if x.shape != skip.shape:
            # Crop skip to match x
            diff_h = skip.shape[2] - x.shape[2]
            diff_w = skip.shape[3] - x.shape[3]
            skip = skip[
                :,
                :,
                diff_h // 2 : skip.shape[2] - diff_h + diff_h // 2,
                diff_w // 2 : skip.shape[3] - diff_w + diff_w // 2,
            ]
        x = torch.cat([x, skip], dim=1)
        return self.conv(x)


# ─────────────────────────────────────────────────────────────────────────────
# ResNet34 Encoder (built from scratch)
# ─────────────────────────────────────────────────────────────────────────────

class ResNet34Encoder(nn.Module):
    """ResNet34 encoder returning list of feature maps at multiple scales."""

    def __init__(self, pretrained: bool = True):
        super().__init__()
        base = models.resnet34(weights=models.ResNet34_Weights.IMAGENET1K_V1 if pretrained else None)

        # Stem
        self.conv1 = base.conv1
        self.bn1 = base.bn1
        self.relu = base.relu
        self.maxpool = base.maxpool

        # Residual blocks
        self.layer1 = base.layer1  # 64 channels, 1/4 resolution
        self.layer2 = base.layer2  # 128 channels, 1/8 resolution
        self.layer3 = base.layer3  # 256 channels, 1/16 resolution
        self.layer4 = base.layer4  # 512 channels, 1/32 resolution

    def forward(self, x: torch.Tensor):
        outputs = []

        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        outputs.append(x)  # stem output (64, H/2, W/2)

        x = self.maxpool(x)
        x = self.layer1(x)
        outputs.append(x)  # layer1 (64, H/4, W/4)

        x = self.layer2(x)
        outputs.append(x)  # layer2 (128, H/8, W/8)

        x = self.layer3(x)
        outputs.append(x)  # layer3 (256, H/16, W/16)

        x = self.layer4(x)
        outputs.append(x)  # layer4 (512, H/32, W/32)

        return outputs


# ─────────────────────────────────────────────────────────────────────────────
# U-Net Decoder
# ─────────────────────────────────────────────────────────────────────────────

class UNetDecoder(nn.Module):
    """U-Net decoder with skip connections from encoder."""

    def __init__(self, encoder_channels=(64, 64, 128, 256, 512), num_classes: int = 6):
        super().__init__()
        # channels at each decoder level (from deep to shallow)
        # encoder_channels: [stem, layer1, layer2, layer3, layer4]
        # We use layer1..layer4 + stem as skip connections, deepest first
        self.up_blocks = nn.ModuleList()
        in_ch = encoder_channels[-1]  # 512

        for i, enc_ch in enumerate(reversed(encoder_channels[1:-1])):  # 256, 128, 64
            self.up_blocks.append(UpBlock(in_ch, enc_ch))
            in_ch = enc_ch

        # Final 2x upsample to recover original resolution
        self.final_up = nn.ConvTranspose2d(in_ch, in_ch // 2, kernel_size=2, stride=2)
        self.final_conv = ConvBlock(in_ch // 2 + encoder_channels[0], encoder_channels[0])

        self.segmentation_head = nn.Conv2d(encoder_channels[0], num_classes, kernel_size=1)

    def forward(self, encoder_outputs: list[torch.Tensor]):
        # encoder_outputs: [stem, layer1, layer2, layer3, layer4]
        # skip connections:   [None,   s0,    s1,    s2,    s3  ]
        # deep = layer4, then upsampling through layer3, layer2, layer1, stem

        x = encoder_outputs[-1]  # start from deepest (512, H/32, W/32)

        skip_idx = 3  # start pairing with layer3
        for up_block in self.up_blocks:
            skip = encoder_outputs[skip_idx]
            x = up_block(x, skip)
            skip_idx -= 1

        # Final up to match stem resolution
        x = self.final_up(x)  # (64, H/2, W/2)
        # pad to exactly match stem
        skip = encoder_outputs[0]  # stem output
        if x.shape != skip.shape:
            diff_h = skip.shape[2] - x.shape[2]
            diff_w = skip.shape[3] - x.shape[3]
            x = F.pad(x, [diff_w // 2, diff_w - diff_w // 2, diff_h // 2, diff_h - diff_h // 2])
        x = self.final_conv(torch.cat([x, skip], dim=1))

        return self.segmentation_head(x)


# ─────────────────────────────────────────────────────────────────────────────
# U-Net Model
# ─────────────────────────────────────────────────────────────────────────────

class AncientMapUNet(nn.Module):
    """
    U-Net for semantic segmentation of ancient Chinese maps.

    Classes:
        0: 背景 (background)
        1: 河流 (rivers)
        2: 山脉 (mountains)
        3: 城市/聚落 (cities/settlements)
        4: 边界线/道路 (boundaries/roads)
        5: 文字标注 (text labels)

    Input:  (B, 3, H, W) RGB image
    Output: (B, 6, H, W) class logits
    """

    CLASSES = 6

    def __init__(self, pretrained_encoder: bool = True):
        super().__init__()
        logger.info("Initializing AncientMapUNet with ResNet34 encoder")

        if HAS_SMP:
            # Use segmentation_models_pytorch for a proven U-Net with ResNet34
            self.model = smp.Unet(
                encoder_name="resnet34",
                encoder_weights="imagenet" if pretrained_encoder else None,
                in_channels=3,
                classes=self.CLASSES,
            )
            self._use_smp = True
            logger.info("Using SMP U-Net with ResNet34 encoder")
        else:
            # Build U-Net from scratch with ResNet34 encoder
            self.encoder = ResNet34Encoder(pretrained=pretrained_encoder)
            self.decoder = UNetDecoder(
                encoder_channels=(64, 64, 128, 256, 512),
                num_classes=self.CLASSES,
            )
            self._use_smp = False
            logger.info("Using custom U-Net with ResNet34 encoder built from scratch")

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self._use_smp:
            return self.model(x)
        else:
            encoder_outputs = self.encoder(x)
            return self.decoder(encoder_outputs)

    def train(self, mode: bool = True) -> "AncientMapUNet":
        """Set the model to training mode."""
        super().train(mode)
        if not self._use_smp:
            self.encoder.train(mode)
            self.decoder.train(mode)
        return self

    def eval(self) -> "AncientMapUNet":
        """Set the model to evaluation mode."""
        return super().eval()

    def predict(self, image_tensor: torch.Tensor) -> torch.Tensor:
        """
        Run inference on an image tensor.

        Args:
            image_tensor: (B, 3, H, W) RGB image tensor (values should be normalized
                          to ImageNet range or the same range the model was trained with)

        Returns:
            (B, 6, H, W) class probabilities (after softmax)
        """
        self.eval()
        with torch.no_grad():
            logits = self.forward(image_tensor)
            # logits shape: (B, 6, H, W)
            probs = F.softmax(logits, dim=1)
        return probs

    def predict_with_logits(self, image_tensor: torch.Tensor) -> torch.Tensor:
        """
        Run inference returning raw logits (no softmax).

        Args:
            image_tensor: (B, 3, H, W) RGB image tensor

        Returns:
            (B, 6, H, W) raw logits
        """
        self.eval()
        with torch.no_grad():
            return self.forward(image_tensor)

    @staticmethod
    def get_criterion() -> nn.Module:
        """Return the loss function for training (BCEWithLogitsLoss)."""
        return nn.BCEWithLogitsLoss()

    @staticmethod
    def class_names() -> list[str]:
        return [
            "背景 (background)",
            "河流 (rivers)",
            "山脉 (mountains)",
            "城市/聚落 (cities/settlements)",
            "边界线/道路 (boundaries/roads)",
            "文字标注 (text labels)",
        ]
