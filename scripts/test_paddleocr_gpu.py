"""Test PaddleOCR GPU on Kangxi gazetteer PDF page"""
import os
import time
import paddle
paddle.device.set_device('gpu:0')

from paddleocr import PaddleOCR
from PIL import Image
import fitz  # PyMuPDF

# Test file
test_pdf = r"E:\文献学\固安县志\固安县志（康熙）\卷一 封域志（星野 疆界 沿革 县名 形胜 川凟 风俗 祥异）.pdf"
output_dir = r"C:\Users\hbusl\zhijian\data\raw\kangxi"
os.makedirs(output_dir, exist_ok=True)

print(f"File exists: {os.path.exists(test_pdf)}")

# Initialize OCR
print("Initializing PaddleOCR GPU...")
ocr = PaddleOCR(use_gpu=True, use_angle_cls=True, lang='ch', rec_batch_num=32)
print("PaddleOCR initialized!")

# Open PDF and extract first 3 pages as images
doc = fitz.open(test_pdf)
print(f"PDF pages: {len(doc)}")

for page_idx in range(min(3, len(doc))):
    page = doc[page_idx]
    # Render at higher resolution for better OCR
    mat = fitz.Matrix(3, 3)  # 3x zoom = ~216 DPI
    pix = page.get_pixmap(matrix=mat)
    img_path = os.path.join(output_dir, f"page_{page_idx+1:03d}.png")
    pix.save(img_path)
    print(f"  Page {page_idx+1} saved: {img_path} ({pix.width}x{pix.height})")

doc.close()

# Run OCR on the extracted pages
print("\nRunning OCR on pages...")
total_chars = 0
total_time = 0

for page_idx in range(1, 4):
    img_path = os.path.join(output_dir, f"page_{page_idx:03d}.png")
    if not os.path.exists(img_path):
        continue

    start = time.time()
    result = ocr.ocr(img_path, cls=True)
    elapsed = time.time() - start

    if result and result[0]:
        page_chars = sum(len(line[1][0]) for line in result[0])
        total_chars += page_chars
        print(f"\nPage {page_idx}: {len(result[0])} lines, ~{page_chars} chars in {elapsed:.1f}s")
        for line_idx, line in enumerate(result[0][:5]):
            text = line[1][0]
            confidence = line[1][1]
            print(f"  [{line_idx+1}] {text[:60]} (conf: {confidence:.2f})")
    else:
        print(f"\nPage {page_idx}: No text detected in {elapsed:.1f}s")

    total_time += elapsed

print(f"\nTotal: ~{total_chars} chars in {total_time:.1f}s")
