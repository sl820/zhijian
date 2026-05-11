"""
舆图提取端到端测试脚本

测试MapExtractionService的完整流程。

Usage:
    python scripts/test_map_pipeline.py
"""

import sys
from pathlib import Path

# 添加项目根目录
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import torch
import numpy as np
from PIL import Image

# 测试1: 直接加载模型进行推理
print("=" * 60)
print("测试1: U-Net模型加载和推理")
print("=" * 60)

model_path = _project_root / "models" / "map_unet_best.pth"
if not model_path.exists():
    print(f"❌ 模型文件不存在: {model_path}")
    print("尝试使用 unet_ancient_map_best.pth...")
    model_path = _project_root / "models" / "unet_ancient_map_best.pth"

if model_path.exists():
    print(f"✓ 找到模型: {model_path}")

    # 尝试加载
    try:
        checkpoint = torch.load(model_path, map_location="cpu")
        print(f"✓ 模型加载成功")

        # 检查checkpoint结构
        if isinstance(checkpoint, dict):
            if "model_state_dict" in checkpoint:
                print(f"  - 包含 model_state_dict")
            if "epoch" in checkpoint:
                print(f"  - Epoch: {checkpoint.get('epoch')}")
            if "mIoU" in checkpoint:
                print(f"  - mIoU: {checkpoint.get('mIoU')}")

        # 尝试直接加载模型
        from app.map_extraction.unet_model import AncientMapUNet

        try:
            model = AncientMapUNet(pretrained_encoder=False)
            # 尝试加载权重
            if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
                model.load_state_dict(checkpoint["model_state_dict"])
            else:
                model.load_state_dict(checkpoint)
            print(f"✓ 模型权重加载成功")
            model.eval()
            print(f"✓ 模型进入eval模式")

            # 测试推理
            dummy_input = torch.randn(1, 3, 256, 256)
            with torch.no_grad():
                output = model(dummy_input)
            print(f"✓ 推理成功: output shape = {output.shape}")

        except Exception as e:
            print(f"❌ 加载AncientMapUNet失败: {e}")

            # 回退到SimpleUNet
            from scripts.train_unet_maps import SimpleUNet
            try:
                model = SimpleUNet(in_channels=3, num_classes=6)
                if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
                    model.load_state_dict(checkpoint["model_state_dict"])
                else:
                    model.load_state_dict(checkpoint)
                print(f"✓ SimpleUNet加载成功")
                model.eval()

                dummy_input = torch.randn(1, 3, 256, 256)
                with torch.no_grad():
                    output = model(dummy_input)
                print(f"✓ SimpleUNet推理成功: output shape = {output.shape}")
            except Exception as e2:
                print(f"❌ SimpleUNet也失败: {e2}")

    except Exception as e:
        print(f"❌ 模型加载失败: {e}")
else:
    print(f"❌ 模型文件不存在: {model_path}")

print()

# 测试2: MapExtractionService端到端测试
print("=" * 60)
print("测试2: MapExtractionService端到端")
print("=" * 60)

try:
    from app.map_extraction.map_service import MapExtractionService

    # 找到一张测试图
    train_dir = _project_root / "data" / "maps" / "dataset" / "images" / "train"
    if train_dir.exists():
        map_images = list(train_dir.glob("*.png"))
        if map_images:
            test_image = map_images[0]
            print(f"✓ 使用测试图像: {test_image.name}")

            service = MapExtractionService(model_path=str(model_path) if model_path.exists() else None)

            # 运行端到端处理
            print("运行 MapExtractionService.process()...")
            result = service.process(
                image_path=str(test_image),
                perform_ocr=True,
                georeference=False,
                reference_points=None
            )

            print(f"✓ 处理完成!")
            print(f"  - 图像路径: {result.get('image_path', '')}")
            print(f"  - 要素统计: {result.get('statistics', {})}")
            print(f"  - 河流数量: {len(result.get('elements', {}).get('rivers', []))}")
            print(f"  - 山脉数量: {len(result.get('elements', {}).get('mountains', []))}")
            print(f"  - 城市数量: {len(result.get('elements', {}).get('cities', []))}")
            print(f"  - 标注数量: {len(result.get('text_labels', []))}")

            if result.get('geojson'):
                print(f"  - GeoJSON: 可用")

            print("\n✓ 舆图提取端到端测试通过!")
        else:
            print(f"❌ 未找到测试图像")
    else:
        print(f"❌ 训练图像目录不存在: {train_dir}")

except Exception as e:
    import traceback
    print(f"❌ MapExtractionService测试失败: {e}")
    traceback.print_exc()

print()
print("=" * 60)
print("舆图提取模块测试完成")
print("=" * 60)
