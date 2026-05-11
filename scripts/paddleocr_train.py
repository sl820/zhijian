"""
方志系统OCR识别模型 - PaddleOCR标准训练流程
"""

import os
import sys
import random
from pathlib import Path

# 配置路径
PROJECT_ROOT = Path("C:/Users/hbusl/zhijian")
MODEL_DIR = PROJECT_ROOT / "models" / "ocr_recognizer"
DATA_ROOT = PROJECT_ROOT / "data" / "ocr_training"
TRAIN_DIR = MODEL_DIR / "images"
LABEL_FILE = MODEL_DIR / "train_labels.txt"

# 训练参数
CONFIG = {
    # 模型配置
    "Global": {
        "model_name": "rec",
        "save_model_dir": str(MODEL_DIR / "output"),
        "data_dir": str(TRAIN_DIR),
        "label_file": str(LABEL_FILE),
    },
    # 训练配置
    "Train": {
        "batch_size": 16,
        "num_workers": 0,
        "epochs": 50,
        "image_shape": "3, 48, 320",  # 高, 宽
        "max_text_length": 25,
        "rec_image_shape": "3, 48, 320",
        "rec_char_type": "ch",
        "rec_batch_num": 16,
    },
    # 优化器
    "Optimizer": {
        "name": "Adam",
        "lr": 0.0001,
    },
}


def prepare_ppocr_training_format():
    """
    准备PaddleOCR标准训练格式
    """
    print("=" * 60)
    print("准备PaddleOCR标准训练格式")
    print("=" * 60)

    # 检查数据
    if not TRAIN_DIR.exists():
        print(f"错误: 训练图像目录不存在: {TRAIN_DIR}")
        return False

    if not LABEL_FILE.exists():
        print(f"错误: 标签文件不存在: {LABEL_FILE}")
        return False

    # 读取并验证标签
    valid_samples = []
    with open(LABEL_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 2:
                img_name = parts[0]
                text = parts[1]
                if len(text) > 0:
                    valid_samples.append((img_name, text))

    print(f"有效训练样本: {len(valid_samples)}")

    # 划分训练集和验证集 (9:1)
    random.seed(42)
    random.shuffle(valid_samples)
    split_idx = int(len(valid_samples) * 0.9)
    train_samples = valid_samples[:split_idx]
    val_samples = valid_samples[split_idx:]

    # 写入训练集标签
    train_label_file = MODEL_DIR / "train_list.txt"
    with open(train_label_file, 'w', encoding='utf-8') as f:
        for img_name, text in train_samples:
            f.write(f"{img_name}\t{text}\n")

    # 写入验证集标签
    val_label_file = MODEL_DIR / "val_list.txt"
    with open(val_label_file, 'w', encoding='utf-8') as f:
        for img_name, text in val_samples:
            f.write(f"{img_name}\t{text}\n")

    print(f"训练集: {len(train_samples)} 样本")
    print(f"验证集: {len(val_samples)} 样本")
    print(f"训练标签: {train_label_file}")
    print(f"验证标签: {val_label_file}")

    return True


def create_training_shell_script():
    """
    创建PaddleOCR训练Shell脚本
    """
    script_content = '''#!/bin/bash
# 方志系统OCR识别模型训练脚本

# 设置环境变量
export HF_ENDPOINT=https://hf-mirror.com
export FLAGS_use_cuda_managed_memory=False

# 训练参数
MODEL_DIR="C:/Users/hbusl/zhijian/models/ocr_recognizer"
DATA_ROOT="C:/Users/hbusl/zhijian/data/ocr_training"

# 训练命令 (CPU训练)
python -m paddle.distributed.launch \\
    --server_num 1 \\
    train.py \\
    -c configs/rec/rec_chinese_lite_v1.yml \\
    -o Global.character_type=ch \\
    -o Global.pretrained_model=null \\
    -o Train.dataset.data_dir=$DATA_ROOT \\
    -o Train.dataset.label_file_list=["$MODEL_DIR/train_list.txt"] \\
    -o Train.batch_size_per_card=16 \\
    -o Global.model_save_dir=$MODEL_DIR/output \\
    -o Global.device=cpu

echo "训练完成! 模型保存在: $MODEL_DIR/output"
'''

    script_file = MODEL_DIR / "train.sh"
    with open(script_file, 'w', encoding='utf-8') as f:
        f.write(script_content)

    print(f"训练脚本: {script_file}")
    return script_file


def create_paddleocr_rec_config():
    """
    创建PaddleOCR识别模型配置文件
    """
    config_content = '''
Global:
  model_save_dir: "./output"
  device: cpu
  epoch: 50
  save_epoch: 10
  eval_epoch: 5
  print_batch_step: 10
  save_metric_opt_freq: 1000

Train:
  dataset:
    name: SimpleDataset
    data_dir: "./images"
    label_file_list: ["./train_list.txt"]
    transforms:
      - RecAug:
      - KeepKeys:
          keep_keys: ["image", "label", "valid_ratio"]
  loader:
    batch_size_per_card: 16
    num_workers: 0
    shuffle: true
    drop_last: true

Eval:
  dataset:
    name: SimpleDataset
    data_dir: "./images"
    label_file_list: ["./val_list.txt"]
    transforms:
      - RecAug:
      - KeepKeys:
          keep_keys: ["image", "label", "valid_ratio"]
  loader:
    batch_size_per_card: 16
    num_workers: 0

Optimizer:
  name: Adam
  beta1: 0.9
  beta2: 0.999
  lr:
    name: Cosine
    learning_rate: 0.0001

RecModel:
  name: CRNNRecognizer
  backbone:
    name: MobileNetV3
    scale: 0.5
  neck:
    name: SequenceEncoder
    encoder_type: rnn
    hidden_size: 128
  head:
    name: CTCHead
    fc:
      - 64
      - 6625

PreProcess:
  - RecResizeImg:
      image_shape: "3, 48, 320"
  - LabelSchema:
      max_text_length: 25
'''

    config_file = MODEL_DIR / "rec_config.yml"
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(config_content)

    print(f"PaddleOCR配置: {config_file}")
    return config_file


def main():
    import random

    print("=" * 60)
    print("方志系统OCR识别模型训练准备")
    print("=" * 60)

    # 1. 准备训练数据格式
    success = prepare_ppocr_training_format()
    if not success:
        return

    # 2. 创建训练配置
    config_file = create_paddleocr_rec_config()

    # 3. 创建训练脚本
    script_file = create_training_shell_script()

    print("\n" + "=" * 60)
    print("训练数据准备完成!")
    print("=" * 60)
    print(f"\n模型目录: {MODEL_DIR}")
    print(f"图像目录: {TRAIN_DIR}")
    print(f"训练标签: {MODEL_DIR / 'train_list.txt'}")
    print(f"验证标签: {MODEL_DIR / 'val_list.txt'}")
    print(f"配置文件: {config_file}")
    print(f"训练脚本: {script_file}")

    print("\n" + "=" * 60)
    print("下一步操作:")
    print("=" * 60)
    print("""
方案1: 在本机训练 (CPU模式，较慢)
    cd {model_dir}
    python train.py -c rec_config.yml

方案2: 在Google Colab训练 (推荐，速度快)
    1. 上传images目录和配置文件到Google Drive
    2. 在Colab中运行训练

方案3: 使用PaddleX可视化训练
    pip install paddlex
    paddlex --platform cd 启动可视化界面
    """.format(model_dir=MODEL_DIR))

    # 4. 尝试使用PaddleOCR进行简单微调
    print("\n" + "=" * 60)
    print("尝试使用PaddleOCR在线微调...")
    print("=" * 60)

    try:
        from paddleocr import PaddleOCR

        # 检查模型是否可以加载
        print("正在检查PaddleOCR模型...")
        ocr = PaddleOCR(
            lang='ch',
            use_angle_cls=False,
            show_log=False
        )
        print("PaddleOCR模型加载成功!")

        # 测试几张图像
        test_images = list(TRAIN_DIR.glob("*.png"))[:3]
        for img_path in test_images:
            result = ocr.ocr(str(img_path), cls=False)
            print(f"  测试图像: {img_path.name}")

    except Exception as e:
        print(f"PaddleOCR测试错误: {e}")

    return MODEL_DIR


if __name__ == "__main__":
    main()
