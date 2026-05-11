"""
方志系统OCR训练数据准备脚本 v2
修复标签格式问题
"""

import os
import sys
import json
import fitz
from pathlib import Path
from PIL import Image
import io
from tqdm import tqdm

# 配置路径
SOURCE_DIR = Path("E:/文献学/固安县志")
OUTPUT_DIR = Path("C:/Users/hbusl/zhijian/data/ocr_training")
TRAIN_DIR = OUTPUT_DIR / "train"
FONT_PATH = "C:/Windows/Fonts/simhei.ttf"

# 确保输出目录存在
TRAIN_DIR.mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "images").mkdir(exist_ok=True)
(OUTPUT_DIR / "labels").mkdir(exist_ok=True)


def extract_text_from_pdf(pdf_path: Path) -> dict:
    """从98年版PDF提取文本，按页返回"""
    doc = fitz.open(str(pdf_path))
    pages_text = {}

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text", flags=0)
        if text.strip():
            pages_text[page_num] = text.strip()

    doc.close()
    return pages_text


def extract_images_from_pdf(pdf_path: Path, dpi: int = 200) -> dict:
    """从扫描版PDF提取图像，按页返回"""
    doc = fitz.open(str(pdf_path))
    pages_images = {}

    for page_num in tqdm(range(len(doc)), desc=f"Extracting"):
        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        pages_images[page_num] = img

    doc.close()
    return pages_images


def create_text_image(text: str, font_path: str = FONT_PATH, img_width: int = 800) -> Image.Image:
    """将文本渲染为图像"""
    from PIL import Image, ImageDraw, ImageFont

    try:
        font_size = 32
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()
        font_size = 20

    dummy_img = Image.new('RGB', (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    lines = text.split('\n')

    max_width = 0
    total_height = 0
    line_heights = []

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        line_height = bbox[3] - bbox[1]
        max_width = max(max_width, line_width)
        line_heights.append(line_height)
        total_height += line_height + 10

    padding = 40
    img_height = total_height + padding * 2
    max_width = min(max_width + padding * 2, img_width)

    img = Image.new('RGB', (max_width, img_height), color='white')
    draw = ImageDraw.Draw(img)

    y = padding
    for line, line_height in zip(lines, line_heights):
        draw.text((padding, y), line, font=font, fill='black')
        y += line_height + 10

    return img


def prepare_training_data():
    """
    准备OCR训练数据
    """
    print("=" * 60)
    print("方志系统OCR训练数据准备 v2")
    print("=" * 60)

    version_98_dir = SOURCE_DIR / "固安县志（98年版）"

    if not version_98_dir.exists():
        print(f"错误: 找不到98年版目录: {version_98_dir}")
        return

    pdf_files = sorted(version_98_dir.glob("*.pdf"))
    print(f"找到 {len(pdf_files)} 个PDF文件")

    all_texts = []

    for pdf_path in pdf_files:
        print(f"\n处理: {pdf_path.name}")
        try:
            pages_text = extract_text_from_pdf(pdf_path)
            print(f"  提取到 {len(pages_text)} 页文本")

            for page_num, text in pages_text.items():
                if len(text) < 10:
                    continue
                all_texts.append({
                    'source': pdf_path.stem,
                    'page': page_num,
                    'text': text
                })
        except Exception as e:
            print(f"  错误: {e}")

    print(f"\n共提取 {len(all_texts)} 页有效文本")

    # 生成训练图像 - 修复标签格式
    print("\n开始生成训练图像...")

    label_file = OUTPUT_DIR / "labels.txt"

    with open(label_file, 'w', encoding='utf-8') as f:
        for i, item in enumerate(tqdm(all_texts, desc="生成图像")):
            text = item['text']
            if len(text) > 500:
                text = text[:500]

            try:
                img = create_text_image(text)
                img_path = TRAIN_DIR / f"train_{i:05d}.png"
                img.save(img_path, "PNG")

                # 关键修复：使用制表符分隔图像名和标签，将文本中的换行符替换为空格
                clean_text = text.replace('\n', ' ').replace('\r', '')
                f.write(f"train_{i:05d}.png\t{clean_text}\n")

            except Exception as e:
                print(f"  图像生成错误: {e}")

    print(f"\n完成! 生成 {len(all_texts)} 个训练样本")
    print(f"标签文件: {label_file}")

    # 处理扫描版图像
    print("\n" + "=" * 60)
    print("处理扫描版图像")

    version_scan_dirs = [
        SOURCE_DIR / "固安县志（咸丰）",
        SOURCE_DIR / "固安县志（康熙）",
    ]

    scan_image_count = 0

    for scan_dir in version_scan_dirs:
        if not scan_dir.exists():
            continue

        pdf_files = list(scan_dir.glob("*.pdf"))
        if not pdf_files:
            continue

        print(f"\n处理: {scan_dir.name}")

        for pdf_path in pdf_files:
            try:
                pages_images = extract_images_from_pdf(pdf_path, dpi=150)

                for page_num, img in pages_images.items():
                    img_path = OUTPUT_DIR / "images" / f"{scan_dir.name}_{pdf_path.stem}_p{page_num}.png"
                    img.save(img_path, "PNG")
                    scan_image_count += 1

            except Exception as e:
                print(f"  错误: {e}")

    print(f"\n提取 {scan_image_count} 张扫描图像")

    # 生成数据统计
    stats = {
        'total_train_samples': len(all_texts),
        'total_scan_images': scan_image_count,
        'source_files': len(pdf_files),
        'label_file': str(label_file)
    }

    with open(OUTPUT_DIR / 'stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("数据准备完成!")
    print("=" * 60)

    return stats


if __name__ == "__main__":
    prepare_training_data()
