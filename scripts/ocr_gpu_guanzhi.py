"""
OCR GPU processing for 固安县志 scanned PDFs.
Uses EasyOCR with GPU acceleration.
"""

import os
import sys
import tempfile
import io
from pathlib import Path
from tqdm import tqdm

# HF mirror
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
sys.stdout.reconfigure(encoding='utf-8')

import fitz
from PIL import Image
import easyocr


# 配置路径
BASE_DIR = Path("E:/文献学/固安县志")
OUTPUT_BASE = Path("C:/Users/hbusl/zhijian/data/raw")

# 要处理的版本（扫描版，需要OCR）
SCANNED_VERSIONS = [
    "固安县志（咸丰）",
    "固安县志（康熙）",
    "固安县志（民国）",
]

# 98年版有文本层，用文本提取
TEXT_VERSION = "固安县志（98年版）"


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


def ocr_pdf_easyocr(pdf_path: Path, reader, dpi: int = 300) -> str:
    """用EasyOCR识别PDF所有页面。"""
    doc = fitz.open(str(pdf_path))
    all_pages = []

    for page_num in tqdm(range(len(doc)), desc=f"OCR {pdf_path.stem}"):
        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")

        img = Image.open(io.BytesIO(img_bytes))
        temp_path = Path(tempfile.gettempdir()) / f"ocr_{page_num}.png"
        img.save(temp_path)

        # EasyOCR识别
        results = reader.readtext(str(temp_path))

        page_lines = []
        for _, text, conf in results:
            if conf >= 0.3 and text.strip():
                page_lines.append(text.strip())

        if page_lines:
            all_pages.append(f"[第{page_num + 1}页] " + " ".join(page_lines))

        # 清理
        try:
            temp_path.unlink()
        except:
            pass

    doc.close()
    return "\n\n".join(all_pages)


def main():
    import io

    # 初始化EasyOCR GPU
    print("Initializing EasyOCR with GPU...")
    reader = easyocr.Reader(['ch_sim', 'en'], gpu=True, verbose=True)

    # 处理98年版（文本提取）
    print(f"\n=== Processing {TEXT_VERSION} (text extraction) ===")
    text_dir = OUTPUT_BASE / TEXT_VERSION
    text_dir.mkdir(parents=True, exist_ok=True)

    text_pdf = BASE_DIR / TEXT_VERSION / "固安县志.pdf"
    if text_pdf.exists():
        out_file = text_dir / "固安县志.txt"
        chars = text_extract(text_pdf, out_file)
        print(f"  Extracted: {chars:,} chars -> {out_file}")

    # 处理扫描版（OCR）
    for version_name in SCANNED_VERSIONS:
        version_dir = BASE_DIR / version_name
        output_dir = OUTPUT_BASE / version_name
        output_dir.mkdir(parents=True, exist_ok=True)

        pdfs = sorted(version_dir.glob("*.pdf"))
        if not pdfs:
            print(f"\n=== {version_name}: No PDFs found ===")
            continue

        print(f"\n=== Processing {version_name} ({len(pdfs)} PDFs) ===")

        for pdf_path in pdfs:
            out_file = output_dir / f"{pdf_path.stem}.txt"

            # 跳过已有大文件的OCR结果
            if out_file.exists() and out_file.stat().st_size > 10000:
                print(f"  Skipping {pdf_path.stem} (already processed)")
                continue

            print(f"\n  Processing: {pdf_path.name}")
            try:
                text = ocr_pdf_easyocr(pdf_path, reader, dpi=300)
                if text:
                    out_file.write_text(text, encoding='utf-8')
                    print(f"  -> {len(text):,} chars saved to {out_file.name}")
                else:
                    print(f"  -> No text recognized")
            except Exception as e:
                print(f"  ERROR: {e}")

    print("\n=== All done! ===")


if __name__ == "__main__":
    main()
