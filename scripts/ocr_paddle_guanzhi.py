"""
OCR processing for 固安县志 using PaddleOCR.
PaddleOCR PP-OCRv4 for fast and accurate Chinese text recognition.
"""

import os
import sys
import io
import tempfile
from pathlib import Path
from tqdm import tqdm

# HF mirror
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
sys.stdout.reconfigure(encoding='utf-8')

import fitz
import numpy as np
from PIL import Image

# Disable model source check
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"

from paddleocr import PaddleOCR


# 配置路径
BASE_DIR = Path("E:/文献学/固安县志")
OUTPUT_BASE = Path("C:/Users/hbusl/zhijian/data/raw")

# 要处理的版本
VERSIONS = [
    "固安县志（咸丰）",
    "固安县志（98年版）",
    "固安县志（故宫博物院编）",
    "固安县志（康熙）",
    "固安县志（民国）",
]


def text_extract(pdf_path: Path, output_path: Path):
    """提取文本层PDF的文字。"""
    doc = fitz.open(str(pdf_path))
    all_pages = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text", flags=0)
        if text.strip():
            all_pages.append(f"[第{page_num + 1}页] " + text.strip())

    doc.close()

    if all_pages:
        full_text = "\n\n".join(all_pages)
        output_path.write_text(full_text, encoding='utf-8')
        return len(full_text)
    return 0


def ocr_pdf_paddle(pdf_path: Path, ocr, dpi: int = 300) -> str:
    """用PaddleOCR识别PDF所有页面。"""
    doc = fitz.open(str(pdf_path))
    all_pages = []

    for page_num in tqdm(range(len(doc)), desc=f"OCR {pdf_path.stem}"):
        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")

        # PaddleOCR需要numpy数组
        img = Image.open(io.BytesIO(img_bytes))
        img_array = np.array(img)

        # 使用PaddleOCR识别
        result = ocr.ocr(img_array)

        if result and result[0]:
            page_lines = []
            for line in result[0]:
                text = line[1][0]
                conf = line[1][1]
                if conf >= 0.5 and text.strip():
                    page_lines.append(text.strip())

            if page_lines:
                all_pages.append(f"[第{page_num + 1}页] " + " ".join(page_lines))

    doc.close()
    return "\n\n".join(all_pages)


def main():
    # 初始化PaddleOCR (使用CPU，v4版本)
    print("Initializing PaddleOCR PP-OCRv4...")
    ocr = PaddleOCR(
        use_textline_orientation=True,
        lang='ch',
        text_det_thresh=0.3,
        text_recognition_batch_size=16
    )
    print("PaddleOCR initialized!")

    for version_name in VERSIONS:
        version_dir = BASE_DIR / version_name
        output_dir = OUTPUT_BASE / version_name
        output_dir.mkdir(parents=True, exist_ok=True)

        if not version_dir.exists():
            print(f"\n=== {version_name}: Directory not found, skipping ===")
            continue

        pdfs = sorted(version_dir.glob("*.pdf"))
        if not pdfs:
            # 也检查单文件情况
            pdf_files = [f for f in version_dir.iterdir() if f.suffix.lower() == '.pdf']
            if not pdf_files:
                print(f"\n=== {version_name}: No PDFs found ===")
                continue
            pdfs = pdf_files

        print(f"\n=== Processing {version_name} ({len(pdfs)} PDFs) ===")

        for pdf_path in pdfs:
            out_file = output_dir / f"{pdf_path.stem}.txt"

            # 跳过已有大文件的OCR结果
            if out_file.exists() and out_file.stat().st_size > 10000:
                print(f"  Skipping {pdf_path.stem} (already processed)")
                continue

            print(f"\n  Processing: {pdf_path.name}")

            # 首先尝试文本提取
            text = None
            try:
                doc = fitz.open(str(pdf_path))
                # 检查前几页是否有可提取文本
                sample_pages = min(3, len(doc))
                has_text = False
                for i in range(sample_pages):
                    page_text = doc[i].get_text("text", flags=0)
                    if len(page_text.strip()) > 100:
                        has_text = True
                        break
                doc.close()

                if has_text:
                    print(f"    Using text extraction...")
                    chars = text_extract(pdf_path, out_file)
                    if chars > 100:
                        print(f"    -> {chars:,} chars saved to {out_file.name}")
                        continue
            except Exception as e:
                print(f"    Text extract failed: {e}")

            # 文本提取失败，使用OCR
            print(f"    Using PaddleOCR...")
            try:
                text = ocr_pdf_paddle(pdf_path, ocr, dpi=300)
                if text and len(text) > 50:
                    out_file.write_text(text, encoding='utf-8')
                    print(f"    -> {len(text):,} chars saved to {out_file.name}")
                else:
                    print(f"    -> No text recognized")
            except Exception as e:
                print(f"    OCR ERROR: {e}")

    print("\n=== All done! ===")


if __name__ == "__main__":
    main()
