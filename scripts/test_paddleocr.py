"""Test PaddleOCR on Kangxi gazetteer PDF - CPU version"""
import os
import sys

# Set environment
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

from paddleocr import PaddleOCR

test_pdf = r"E:\文献学\固安县志\固安县志（康熙）\卷一 封域志（星野 疆界 沿革 县名 形胜 川凟 风俗 祥异）.pdf"

print(f"Testing PaddleOCR on Kangxi gazetteer PDF...")
print(f"File exists: {os.path.exists(test_pdf)}")

# PaddleOCR 3.4.0 - auto device selection, no explicit use_gpu
ocr = PaddleOCR(lang='ch', det_limit_side_len=960)
print("PaddleOCR initialized")

result = ocr.ocr(test_pdf)
print(f"OCR complete!")
print(f"Number of pages: {len(result) if result else 0}")

if result:
    total_lines = 0
    total_chars = 0
    for page_idx, page in enumerate(result):
        if page is None:
            continue
        page_lines = len(page)
        page_chars = sum(len(line[1][0]) for line in page)
        total_lines += page_lines
        total_chars += page_chars
        print(f"  Page {page_idx+1}: {page_lines} lines, ~{page_chars} chars")
        # Show first 3 lines
        for line_idx, line in enumerate(page[:3]):
            text = line[1][0]
            confidence = line[1][1]
            print(f"    [{line_idx+1}] {text[:50]}... (conf: {confidence:.2f})")

    print(f"\nTotal: {total_lines} lines, ~{total_chars} chars")
