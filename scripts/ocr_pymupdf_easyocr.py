"""
OCR pipeline for classical Chinese gazetteer PDFs.
Uses PyMuPDF to convert PDF pages to images, then EasyOCR for text recognition.
"""
import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import easyocr
import fitz  # PyMuPDF


def pdf_to_images(pdf_path, dpi=300):
    """Convert PDF pages to images using PyMuPDF."""
    doc = fitz.open(pdf_path)
    images = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        # Render at high DPI for better OCR quality
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("png")
        images.append(img_data)
    doc.close()
    return images


def ocr_images(images, reader):
    """Run EasyOCR on a list of image bytes."""
    results = []
    for i, img_data in enumerate(images):
        # Write to temp file since EasyOCR works better with files
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(img_data)
            temp_path = f.name

        try:
            ocr_result = reader.readtext(temp_path, detail=1)
            text_lines = []
            for bbox, text, confidence in ocr_result:
                if confidence > 0.3:  # Filter low-confidence results
                    text_lines.append({
                        'text': text,
                        'confidence': float(confidence),
                        'bbox': bbox
                    })
            results.append({
                'page': i,
                'lines': text_lines,
                'full_text': ' '.join([l['text'] for l in text_lines])
            })
            print(f"  Page {i+1}: {len(text_lines)} text lines, {sum(l['confidence'] for l in text_lines)/max(len(text_lines),1):.2f} avg confidence")
        finally:
            os.unlink(temp_path)

    return results


def main():
    # Test PDF path
    pdf_path = "E:/文献学/固安县志/固安县志（咸丰）/凡例 (1).pdf"
    print(f"Processing: {pdf_path}")

    # Convert PDF to images
    print("Converting PDF to images at 300 DPI...")
    images = pdf_to_images(pdf_path, dpi=300)
    print(f"  Extracted {len(images)} pages")

    # Initialize EasyOCR reader with Chinese simplified + English
    print("Initializing EasyOCR reader...")
    reader = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)

    # Run OCR
    print("Running OCR...")
    results = ocr_images(images, reader)

    # Print results
    print("\n=== OCR Results ===")
    for page_result in results:
        print(f"\n--- Page {page_result['page']+1} ---")
        print(page_result['full_text'][:500] if page_result['full_text'] else "(no text)")
        if page_result['full_text']:
            print(f"  Total chars: {len(page_result['full_text'])}")


if __name__ == "__main__":
    main()
