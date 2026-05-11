"""Test PaddleOCR CPU on Kangxi gazetteer PDF pages"""
import os
import time
import sys

from paddleocr import PaddleOCR

# Pages already extracted
page_dir = r"C:\Users\hbusl\zhijian\data\raw\kangxi"

print("Initializing PaddleOCR CPU...")
ocr = PaddleOCR(use_gpu=False, use_angle_cls=True, lang='ch', rec_batch_num=32)
print("PaddleOCR initialized!")

# Run OCR on the extracted pages
print("\nRunning OCR on Kangxi gazetteer pages...")
total_chars = 0
total_lines = 0
total_time = 0

pages = sorted([f for f in os.listdir(page_dir) if f.endswith('.png')])
for page_file in pages[:5]:  # First 5 pages
    img_path = os.path.join(page_dir, page_file)
    start = time.time()
    result = ocr.ocr(img_path, cls=True)
    elapsed = time.time() - start

    if result and result[0]:
        page_lines = len(result[0])
        page_chars = sum(len(line[1][0]) for line in result[0])
        total_chars += page_chars
        total_lines += page_lines
        print(f"\n{page_file}: {page_lines} lines, ~{page_chars} chars in {elapsed:.1f}s")
        for line_idx, line in enumerate(result[0][:5]):
            text = line[1][0]
            confidence = line[1][1]
            print(f"  [{line_idx+1}] {text[:60]} (conf: {confidence:.2f})")
    else:
        print(f"\n{page_file}: No text detected in {elapsed:.1f}s")

    total_time += elapsed

print(f"\nTotal for 5 pages: {total_lines} lines, ~{total_chars} chars in {total_time:.1f}s")
