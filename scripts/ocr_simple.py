"""
Simple OCR script for 固安县志 - processes at lower DPI for speed
"""

import os
import sys
import io
from pathlib import Path
from tqdm import tqdm

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
sys.stdout.reconfigure(encoding='utf-8')

import fitz
from PIL import Image
import numpy as np
import easyocr

BASE_DIR = Path("E:/文献学/固安县志")
OUTPUT_BASE = Path("C:/Users/hbusl/zhijian/data/raw")

VERSIONS = [
    "固安县志（咸丰）",
    "固安县志（98年版）",
    "固安县志（故宫博物院编）",
    "固安县志（康熙）",
    "固安县志（民国）",
]

def text_extract(pdf_path, output_path):
    """Extract text layer from PDF."""
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

def ocr_page(img_array, reader):
    """OCR a single image using EasyOCR."""
    result = reader.readtext(img_array, detail=1)
    texts = []
    for bbox, text, conf in result:
        if conf > 0.3 and text.strip():
            texts.append(text.strip())
    return " ".join(texts)

def main():
    print("Initializing EasyOCR...")
    reader = easyocr.Reader(['ch_sim', 'en'], gpu=True, verbose=False)

    for version_name in VERSIONS:
        version_dir = BASE_DIR / version_name
        output_dir = OUTPUT_BASE / version_name
        output_dir.mkdir(parents=True, exist_ok=True)

        if not version_dir.exists():
            continue

        pdfs = sorted(version_dir.glob("*.pdf"))
        if not pdfs:
            continue

        print(f"\n=== {version_name} ({len(pdfs)} PDFs) ===")

        for pdf_path in pdfs:
            out_file = output_dir / f"{pdf_path.stem}.txt"

            # Skip if already has content
            if out_file.exists() and out_file.stat().st_size > 1000:
                print(f"  Skipping {pdf_path.stem}")
                continue

            print(f"  Processing {pdf_path.name}...", end=" ", flush=True)

            # Try text extraction first
            chars = text_extract(pdf_path, out_file)
            if chars > 500:
                print(f"text ({chars} chars)")
                continue

            # Fall back to OCR at 150 DPI
            try:
                doc = fitz.open(str(pdf_path))
                all_pages = []

                for page_num in tqdm(range(len(doc)), desc=f"OCR {pdf_path.stem}", leave=False):
                    page = doc[page_num]
                    mat = fitz.Matrix(150/72, 150/72)  # 150 DPI
                    pix = page.get_pixmap(matrix=mat)
                    img_bytes = pix.tobytes("png")
                    img = Image.open(io.BytesIO(img_bytes))
                    img_array = np.array(img)

                    text = ocr_page(img_array, reader)
                    if text:
                        all_pages.append(f"[第{page_num + 1}页] " + text)

                doc.close()

                if all_pages:
                    full_text = "\n\n".join(all_pages)
                    out_file.write_text(full_text, encoding='utf-8')
                    print(f"ocr ({len(full_text)} chars)")
                else:
                    print("no text")
            except Exception as e:
                print(f"error: {e}")

    print("\n=== Done ===")

if __name__ == "__main__":
    main()
