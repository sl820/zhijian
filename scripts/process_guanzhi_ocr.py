"""
固安县志多版本数据处理脚本 - 支持文本提取和OCR双模式

对于有文字层的PDF（98年版）：直接用PyMuPDF提取
对于扫描版PDF（康熙、咸丰等）：用EasyOCR识别

使用方式:
    # 文本提取（1998版等）
    python scripts/process_guanzhi_ocr.py --mode text

    # OCR识别（康熙、咸丰等扫描版）
    python scripts/process_guanzhi_ocr.py --mode ocr

    # 全部处理
    python scripts/process_guanzhi_ocr.py --mode all
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# HF mirror for BERT models
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# UTF-8 stdout for Chinese logging
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent.parent))

from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"

# 数据目录（需要根据实际情况调整）
DEFAULT_BASE_DIR = Path(os.path.expanduser("E:/文献学/固安县志"))


def scan_versions(base_dir: Path) -> Dict[str, List[Path]]:
    """扫描目录下的所有版本子目录和PDF文件。"""
    versions = {}
    if not base_dir.exists():
        logger.error(f"Base directory not found: {base_dir}")
        return versions

    for entry in sorted(base_dir.iterdir()):
        if entry.is_dir():
            pdfs = sorted([p for p in entry.glob("*.pdf") if p.is_file()])
            if pdfs:
                versions[entry.name] = pdfs
                logger.info(f"Found version '{entry.name}': {len(pdfs)} PDFs")
    return versions


def text_extract_pdf(pdf_path: Path, min_chars: int = 50) -> Tuple[str, int]:
    """用PyMuPDF提取PDF文本层。

    Returns:
        (text, page_count_with_text)
    """
    import fitz

    doc = fitz.open(str(pdf_path))
    page_texts = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text", flags=0)
        if len(text.strip()) >= min_chars:
            page_texts.append({
                'page_num': page_num + 1,
                'text': text.strip()
            })

    doc.close()

    if not page_texts:
        return "", 0

    full_text = "\n\n".join([
        f"[第{page['page_num']}页] " + page['text']
        for page in page_texts
    ])
    return full_text, len(page_texts)


def ocr_image_with_easyocr(image_path: str, reader) -> List[Tuple[str, float]]:
    """用EasyOCR识别图片中的文字。

    Returns:
        List of (text, confidence) tuples
    """
    result = reader.readtext(image_path)
    return [(text.strip(), conf) for _, text, conf in result if text.strip()]


def ocr_pdf_pages(pdf_path: Path, reader, dpi: int = 300,
                  min_conf: float = 0.3) -> str:
    """OCR所有页面并返回合并文本。"""
    import fitz
    from PIL import Image
    import io

    doc = fitz.open(str(pdf_path))
    all_lines = []

    logger.info(f"  Converting {len(doc)} pages at {dpi} DPI...")

    for page_num in range(len(doc)):
        page = doc[page_num]
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")

        img = Image.open(io.BytesIO(img_bytes))

        # Save temp image for OCR
        temp_path = Path(tempfile.gettempdir()) / f"ocr_page_{page_num}.png"
        img.save(temp_path)

        results = ocr_image_with_easyocr(str(temp_path), reader)

        page_lines = []
        for text, conf in results:
            if conf >= min_conf:
                page_lines.append(text)

        if page_lines:
            all_lines.append(f"[第{page_num + 1}页] " + " ".join(page_lines))

        # Clean up temp
        try:
            temp_path.unlink()
        except:
            pass

    doc.close()
    return "\n\n".join(all_lines)


def process_version_text(version_name: str, pdf_paths: List[Path],
                         output_dir: Path) -> Dict[str, int]:
    """处理单一版本的文本提取。"""
    output_version_dir = output_dir / version_name
    output_version_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for pdf_path in tqdm(pdf_paths, desc=f"Text {version_name}"):
        name = pdf_path.stem
        out_file = output_version_dir / f"{name}.txt"

        text, pages_with_text = text_extract_pdf(pdf_path)

        if text:
            out_file.write_text(text, encoding='utf-8')
            results[name] = len(text)
            logger.info(f"  {name}: {len(text):,} chars ({pages_with_text} pages)")
        else:
            results[name] = 0
            logger.warning(f"  {name}: no text extracted ({pages_with_text} pages with text)")

    return results


def process_version_ocr(version_name: str, pdf_paths: List[Path],
                        output_dir: Path, dpi: int = 300) -> Dict[str, int]:
    """处理单一版本的OCR识别。"""
    import easyocr
    import tempfile

    output_version_dir = output_dir / version_name
    output_version_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"  Initializing EasyOCR (ch_sim, en)...")
    reader = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)

    results = {}
    for pdf_path in tqdm(pdf_paths, desc=f"OCR {version_name}"):
        name = pdf_path.stem
        out_file = output_version_dir / f"{name}.txt"

        try:
            text = ocr_pdf_pages(pdf_path, reader, dpi=dpi)

            if text:
                out_file.write_text(text, encoding='utf-8')
                results[name] = len(text)
                logger.info(f"  {name}: {len(text):,} chars")
            else:
                results[name] = 0
                logger.warning(f"  {name}: no text recognized")

        except Exception as e:
            logger.error(f"  ERROR {name}: {e}")
            results[name] = 0

    return results


def print_summary(all_results: Dict[str, Dict[str, int]]):
    """打印汇总信息。"""
    logger.info("\n" + "=" * 60)
    logger.info("All versions summary")
    logger.info("=" * 60)

    for version_name, results in all_results.items():
        total_chars = sum(results.values())
        successful = len([v for v in results.values() if v > 0])

        logger.info(f"\n{version_name}:")
        logger.info(f"  Total volumes: {len(results)}")
        logger.info(f"  Successful: {successful}")
        logger.info(f"  Total chars: {total_chars:,}")

        for vol_name, char_count in sorted(results.items()):
            marker = "OK" if char_count > 0 else "EMPTY"
            logger.info(f"    [{marker}] {vol_name}: {char_count:,} chars")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='固安县志多版本数据处理')
    parser.add_argument('--base-dir', type=Path, default=DEFAULT_BASE_DIR,
                        help='Base directory containing version subdirs')
    parser.add_argument('--output-dir', type=Path, default=DATA_RAW_DIR,
                        help='Output directory')
    parser.add_argument('--mode', choices=['text', 'ocr', 'all'], default='all',
                        help='Processing mode: text (text-layer PDFs), ocr (scanned PDFs), all (both)')
    parser.add_argument('--dpi', type=int, default=300,
                        help='OCR rendering DPI (default: 300)')
    parser.add_argument('--version', type=str, default=None,
                        help='Process only a specific version (e.g., "kangxi")')
    args = parser.parse_args()

    # Scan versions
    versions = scan_versions(args.base_dir)
    if not versions:
        logger.error("No versions found!")
        return

    # Filter by version if specified
    if args.version:
        versions = {k: v for k, v in versions.items() if args.version in k.lower()}
        logger.info(f"Filtered to versions containing '{args.version}': {list(versions.keys())}")

    all_results = {}

    for version_name, pdf_paths in versions.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing: {version_name} ({len(pdf_paths)} PDFs)")
        logger.info(f"{'='*60}")

        if args.mode == 'text':
            results = process_version_text(version_name, pdf_paths, args.output_dir)
        elif args.mode == 'ocr':
            results = process_version_ocr(version_name, pdf_paths, args.output_dir, dpi=args.dpi)
        else:  # all - auto-detect based on first PDF
            # Try text extraction first; if mostly empty, fall back to OCR
            sample_text, _ = text_extract_pdf(pdf_paths[0])
            if sum(len(text_extract_pdf(p, min_chars=50)[0]) for p in pdf_paths) < 1000:
                logger.info(f"  Text extraction yielded little/no text - using OCR")
                results = process_version_ocr(version_name, pdf_paths, args.output_dir, dpi=args.dpi)
            else:
                logger.info(f"  Text extraction available - using text mode")
                results = process_version_text(version_name, pdf_paths, args.output_dir)

        all_results[version_name] = results

    print_summary(all_results)

    logger.info(f"\nOutput saved to: {args.output_dir}")
    logger.info("\nDone! Next steps:")
    logger.info("  1. Test collation: python scripts/quick_collate.py")
    logger.info("  2. Run API server: python -m app.main")


if __name__ == "__main__":
    import tempfile
    main()
