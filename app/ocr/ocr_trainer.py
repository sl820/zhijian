"""
EasyOCR微调训练模块
针对古籍/文物铭文进行模型微调
"""

import os
import json
import easyocr
import torch
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import random
import numpy as np
from PIL import Image
import cv2


class AncientTextOCRTrainer:
    """古籍OCR训练器（基于EasyOCR微调）"""

    def __init__(self, model_dir: str = None):
        """
        初始化训练器

        Args:
            model_dir: 自定义模型保存目录
        """
        self.model_dir = Path(model_dir) if model_dir else Path("C:/Users/hbusl/qi_wu_bo_yan/models/ocr")
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # EasyOCR支持的语言
        # ch_tra: 中文繁体, ch_sim: 中文简体, en: 英文
        self.supported_langs = ['ch_tra', 'ch_sim', 'en', 'ja', 'ko']

        # 字符集统计
        self.char_stats = {}

    def build_character_set(self, training_data: List[Dict]) -> set:
        """
        从训练数据构建字符集

        Args:
            training_data: [{"image_path": str, "text": str}, ...]

        Returns:
            字符集合
        """
        char_set = set()

        for item in training_data:
            text = item.get("text", "")
            char_set.update(list(text))

        self.char_stats = {
            "total_chars": len(char_set),
            "unique_chars": list(char_set)
        }

        print(f"Character set built: {len(char_set)} unique characters")

        return char_set

    def prepare_training_images(self, image_dir: Path, annotations: List[Dict],
                                 output_dir: Path, img_size: Tuple[int, int] = (320, 64)) -> Tuple[List, List]:
        """
        准备训练图像（裁剪文本区域）

        Args:
            image_dir: 原始图像目录
            annotations: 标注数据 [{"image_path": str, "bbox": [...], "text": str}, ...]
            output_dir: 输出目录
            img_size: 统一输出尺寸 (width, height)

        Returns:
            (image_paths, labels)
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        image_paths = []
        labels = []

        for idx, ann in enumerate(annotations):
            img_path = image_dir / ann["image_path"]
            if not img_path.exists():
                continue

            img = cv2.imread(str(img_path))
            if img is None:
                continue

            # 如果有bbox，裁剪文本区域
            if "bbox" in ann:
                x1, y1, x2, y2 = ann["bbox"]
                text_img = img[y1:y2, x1:x2]
            else:
                text_img = img

            # 统一尺寸
            resized = cv2.resize(text_img, img_size)

            # 保存
            output_path = output_dir / f"train_{idx:05d}.jpg"
            cv2.imwrite(str(output_path), resized)

            image_paths.append(str(output_path))
            labels.append(ann.get("text", ""))

            if (idx + 1) % 100 == 0:
                print(f"  Processed {idx + 1}/{len(annotations)}")

        return image_paths, labels

    def fine_tune_with_synthetic_data(self, base_model: str = "ch_tra_en",
                                       num_epochs: int = 10,
                                       learning_rate: float = 1e-4) -> str:
        """
        使用合成数据微调模型

        注意: EasyOCR的真正微调需要自定义训练循环
        这里提供的是数据准备和模型选择框架

        Args:
            base_model: 基础模型 ('ch_tra_en', 'ch_sim_en', etc.)
            num_epochs: 训练轮数
            learning_rate: 学习率

        Returns:
            模型路径
        """
        print(f"Fine-tuning EasyOCR with {num_epochs} epochs")
        print(f"Base model: {base_model}")
        print(f"Learning rate: {learning_rate}")

        # EasyOCR本身不支持直接微调，需要使用其预训练模型
        # 对于古籍OCR，推荐使用以下策略：
        # 1. 使用ch_tra（繁体中文）模型作为基础
        # 2. 通过后处理优化结果（词典约束、LM纠错）
        # 3. 或使用TrOCR进行微调

        model_path = self.model_dir / f"fine_tuned_{base_model}"

        print("\n" + "="*60)
        print("EasyOCR微调说明:")
        print("="*60)
        print("""
EasyOCR本身是预训练模型，不支持端到端微调。
推荐以下替代方案进行古籍OCR优化：

方案1: TrOCR微调（推荐）
- 使用Hugging Face TrOCR
- 支持自定义数据集微调
- 基于Transformer，端到端训练

方案2: PaddleOCR微调
- 支持检测+识别两阶段微调
- 提供古籍/竖排专用模型

方案3: 后处理优化
- 使用古文字典约束输出
- LLM辅助纠错
- 规则化后处理

请选择合适的方案继续。
""")

        return str(model_path)

    def create_character_dictionary(self, char_set: set, output_path: Path) -> Dict:
        """创建字符字典，用于后处理约束"""
        char_list = sorted(list(char_set))

        # 添加特殊字符
        special_chars = ["<blank>", "<unk>", " "]
        char_list = special_chars + char_list

        char_dict = {
            "idx2char": {i: c for i, c in enumerate(char_list)},
            "char2idx": {c: i for i, c in enumerate(char_list)},
            "num_classes": len(char_list)
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(char_dict, f, ensure_ascii=False, indent=2)

        print(f"Character dictionary saved to {output_path}")
        return char_dict


class TirocrFineTuner:
    """TrOCR微调器（用于真正可训练的OCR）"""

    def __init__(self, model_dir: str = None):
        self.model_dir = Path(model_dir) if model_dir else Path("C:/Users/hbusl/qi_wu_bo_yan/models/ocr/trocr")
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def prepare_dataset(self, images: List[Path], labels: List[str], output_dir: Path):
        """准备TrOCR格式数据集"""
        from torch.utils.data import Dataset
        from PIL import Image
        import torch

        output_dir.mkdir(parents=True, exist_ok=True)

        dataset_info = {
            "images": [],
            "labels": []
        }

        for idx, (img_path, label) in enumerate(zip(images, labels)):
            # 复制图像
            img = Image.open(img_path)
            img.save(output_dir / f"img_{idx:05d}.png")

            dataset_info["images"].append(f"img_{idx:05d}.png")
            dataset_info["labels"].append(label)

        with open(output_dir / "labels.json", "w", encoding="utf-8") as f:
            json.dump(dataset_info, f, ensure_ascii=False, indent=2)

        return output_dir

    @staticmethod
    def get_training_config() -> Dict:
        """获取TrOCR训练配置"""
        return {
            "model_name": "microsoft/trocr-base-handwritten",
            "epochs": 10,
            "batch_size": 4,
            "learning_rate": 3e-5,
            "warmup_steps": 500,
            "max_seq_length": 128,
            "image_size": [384, 384],
            "augmentation": True,
            "use_gpu": True
        }


if __name__ == "__main__":
    # 测试训练器
    trainer = AncientTextOCRTrainer(
        model_dir="C:/Users/hbusl/qi_wu_bo_yan/models/ocr"
    )

    # 测试字符集构建
    test_data = [
        {"text": "故宮文物"},
        {"text": "青銅器銘文"},
        {"text": "石刻文字"}
    ]

    char_set = trainer.build_character_set(test_data)
    print(f"Built character set with {len(char_set)} characters")
