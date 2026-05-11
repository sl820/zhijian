"""
OCR pipeline for scanned ancient book PDFs.
Uses PyMuPDF for PDF→image and EasyOCR for text recognition.
"""

import os
import sys
from pathlib import Path

# Use Chinese mirror for HuggingFace
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import fitz  # PyMuPDF
import easyocr
from tqdm import tqdm


class AncientBookOCR:
    """OCR pipeline for ancient Chinese gazetteer PDFs."""

    def __init__(self, langs: list = None, use_gpu: bool = False):
        """Initialize OCR with specified languages.

        Args:
            langs: List of language codes for EasyOCR. Default: ['ch_sim', 'en']
            use_gpu: Whether to use GPU acceleration.
        """
        self.langs = langs or ['ch_sim', 'en']
        self.use_gpu = use_gpu
        self._reader = None

    @property
    def reader(self):
        """Lazy-load EasyOCR reader."""
        if self._reader is None:
            print(f"Initializing EasyOCR with languages: {self.langs}")
            self._reader = easyocr.Reader(
                self.langs,
                gpu=self.use_gpu,
                verbose=True,
                model_storage_directory=str(Path.home() / '.easyocr' / 'model')
            )
        return self._reader

    def pdf_to_images(self, pdf_path: str, dpi: int = 300, max_pages: int = None) -> list:
        """Convert PDF pages to images.

        Args:
            pdf_path: Path to PDF file.
            dpi: Resolution for rendering (default 300).
            max_pages: Maximum number of pages to convert (None = all).

        Returns:
            List of PIL Image objects.
        """
        images = []
        doc = fitz.open(pdf_path)
        page_count = min(len(doc), max_pages) if max_pages else len(doc)

        for page_num in range(page_count):
            page = doc[page_num]
            # Use a matrix for resolution scaling
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(img_data))
            images.append(img)

        doc.close()
        return images

    def ocr_image(self, image, detail: int = 1):
        """Run OCR on a single image.

        Args:
            image: PIL Image or path to image file.
            detail: 0=no detail, 1=line detail, 2=word detail.

        Returns:
            List of (bbox, text, confidence) tuples.
        """
        if isinstance(image, (str, Path)):
            result = self.reader.readtext(str(image), detail=detail)
        else:
            import io
            img_bytes = io.BytesIO()
            image.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            result = self.reader.readtext(img_bytes, detail=detail)
        return result

    def ocr_pdf(self, pdf_path: str, dpi: int = 300, max_pages: int = None,
                min_confidence: float = 0.3) -> str:
        """OCR an entire PDF and return concatenated text.

        Args:
            pdf_path: Path to PDF file.
            dpi: Resolution for rendering (default 300).
            max_pages: Maximum pages to process (None = all).
            min_confidence: Minimum confidence threshold (0-1).

        Returns:
            Extracted text as string.
        """
        images = self.pdf_to_images(pdf_path, dpi=dpi, max_pages=max_pages)
        all_text = []

        print(f"OCR processing {len(images)} pages...")
        for i, img in enumerate(images):
            result = self.ocr_image(img, detail=1)
            page_text = []
            for bbox, text, conf in result:
                if conf >= min_confidence and text.strip():
                    page_text.append(text.strip())
            if page_text:
                all_text.append(f"[Page {i+1}] " + " ".join(page_text))

        return "\n\n".join(all_text)


def get_version_dirs(base_dir: str = None) -> dict:
    """Get paths to all gazetteer version directories.

    Returns:
        Dict mapping version name to list of PDF paths.
    """
    if base_dir is None:
        base_dir = os.path.join(os.path.expanduser('~'), '文献学', '固安县志')

    versions = {}
    if os.path.exists(base_dir):
        for name in os.listdir(base_dir):
            vpath = os.path.join(base_dir, name)
            if os.path.isdir(vpath):
                pdfs = sorted([
                    os.path.join(vpath, f)
                    for f in os.listdir(vpath)
                    if f.lower().endswith('.pdf')
                ])
                if pdfs:
                    versions[name] = pdfs

    return versions


def extract_version(ocr: AncientBookOCR, version_name: str, pdf_paths: list,
                    output_dir: Path, max_pages_per_pdf: int = None):
    """Extract text from all PDFs of a single version.

    Args:
        ocr: AncientBookOCR instance.
        version_name: Name of the version (e.g., 'kangxi').
        pdf_paths: List of PDF file paths.
        output_dir: Directory to save extracted text files.
        max_pages_per_pdf: Max pages to OCR per PDF (None = all).

    Returns:
        Tuple of (success_count, failed_count, total_chars)
    """
    out_version_dir = output_dir / version_name
    out_version_dir.mkdir(parents=True, exist_ok=True)

    success = 0
    failed = 0
    total_chars = 0

    for pdf_path in tqdm(pdf_paths, desc=version_name):
        pdf_name = Path(pdf_path).stem
        out_file = out_version_dir / f"{pdf_name}.txt"

        try:
            text = ocr.ocr_pdf(pdf_path, max_pages=max_pages_per_pdf)
            out_file.write_text(text, encoding='utf-8')
            total_chars += len(text)
            success += 1
            print(f"  {pdf_name}: {len(text)} chars")
        except Exception as e:
            print(f"  ERROR {pdf_name}: {e}")
            failed += 1

    return success, failed, total_chars


def main():
    """Main extraction routine."""
    import argparse

    parser = argparse.ArgumentParser(description='OCR ancient book PDFs')
    parser.add_argument('--base-dir', default=r'E:\文献学\固安县志',
                        help='Base directory containing version subdirs')
    parser.add_argument('--output-dir', default=None,
                        help='Output directory (default: data/raw/{version})')
    parser.add_argument('--dpi', type=int, default=300,
                        help='PDF rendering DPI (default: 300)')
    parser.add_argument('--max-pages', type=int, default=None,
                        help='Max pages per PDF (default: all)')
    parser.add_argument('--gpu', action='store_true',
                        help='Use GPU acceleration')
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    output_dir = Path(args.output_dir) if args.output_dir else project_root / 'data' / 'raw'

    # Initialize OCR
    ocr = AncientBookOCR(use_gpu=args.gpu)

    # Get version directories
    versions = get_version_dirs(args.base_dir)
    print(f"\nFound {len(versions)} versions:")
    for name, paths in versions.items():
        print(f"  {name}: {len(paths)} PDFs")

    # Process each version
    for version_name, pdf_paths in versions.items():
        print(f"\n{'='*60}")
        print(f"Processing {version_name} ({len(pdf_paths)} PDFs)")
        print(f"{'='*60}")

        success, failed, total_chars = extract_version(
            ocr, version_name, pdf_paths, output_dir, args.max_pages
        )

        print(f"\n{version_name} results:")
        print(f"  Success: {success}")
        print(f"  Failed: {failed}")
        print(f"  Total chars: {total_chars:,}")

    print(f"\n{'='*60}")
    print("All versions processed!")
    print(f"Output directory: {output_dir}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
