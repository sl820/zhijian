"""
古籍批量OCR识别脚本

支持多版本、多PDF批量处理，带进度显示和断点续传。

Usage:
    # 处理康熙版所有PDF
    python scripts/batch_ocr.py --dir "data/raw/固安县志（康熙）" --provider easyocr --output data/processed/kangxi

    # 处理咸丰版所有PDF
    python scripts/batch_ocr.py --dir "data/raw/固安县志（咸丰）" --provider easyocr --output data/processed/xianfeng

    # 单个PDF处理
    python scripts/batch_ocr.py --file "data/raw/kangxi.pdf" --provider easyocr --output data/processed/kangxi

    # 使用PaddleOCR (需要GPU)
    python scripts/batch_ocr.py --dir "data/raw/固安县志（康熙）" --provider paddleocr --output data/processed/kangxi

    # 断点续传（跳过已处理页面）
    python scripts/batch_ocr.py --dir "data/raw/固安县志（康熙）" --provider easyocr --output data/processed/kangxi --resume
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ocr.processor import OCRProcessor
from app.utils import imread

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("batch_ocr.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def process_pdf(
    pdf_path: str,
    output_dir: str,
    provider: str = "easyocr",
    start_page: int = 0,
    end_page: int = None,
    detect_variants: bool = True,
    detect_taboo: bool = True,
    dynasty: str = "qing"
) -> dict:
    """处理单个PDF文件

    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录
        provider: OCR provider (easyocr 或 paddleocr)
        start_page: 起始页（0索引）
        end_page: 结束页（None表示处理到最后一页）
        detect_variants: 是否检测异体字
        detect_taboo: 是否检测避讳字
        dynasty: 朝代（用于避讳字检测）

    Returns:
        dict: 处理结果统计
    """
    processor = OCRProcessor(provider=provider)
    pdf_name = Path(pdf_path).stem
    pdf_output_dir = Path(output_dir) / pdf_name
    pdf_output_dir.mkdir(parents=True, exist_ok=True)

    result_file = pdf_output_dir / "result.json"
    done_file = pdf_output_dir / "done.txt"

    # 检查是否已完成
    if done_file.exists():
        with open(done_file, encoding="utf-8") as f:
            completed_pages = int(f.read().strip())
        logger.info(f"PDF {pdf_name} 已完成 {completed_pages} 页，跳过")
        return {"status": "skipped", "pages": completed_pages}

    # 加载已有结果（断点续传）
    existing_result = {}
    if result_file.exists():
        with open(result_file, encoding="utf-8") as f:
            existing_result = json.load(f)
        logger.info(f"从断点恢复，已处理 {len(existing_result.get('pages', []))} 页")

    start_time = time.time()

    try:
        result = processor.process_pdf(
            pdf_path,
            start_page=start_page,
            end_page=end_page,
            detect_variants=detect_variants,
            detect_taboo=detect_taboo,
            dynasty=dynasty
        )

        # 合并结果
        if existing_result:
            existing_result["pages"].extend(result.get("pages", []))
            result = existing_result

        # 保存结果
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # 标记完成
        page_count = len(result.get("pages", []))
        with open(done_file, "w", encoding="utf-8") as f:
            f.write(str(page_count))

        elapsed = time.time() - start_time
        logger.info(
            f"PDF {pdf_name} 处理完成: {page_count} 页, "
            f"耗时 {elapsed:.1f}秒, "
            f"平均 {elapsed/max(page_count, 1):.1f}秒/页"
        )

        return {
            "status": "success",
            "pages": page_count,
            "elapsed": elapsed,
            "pdf": pdf_name
        }

    except Exception as e:
        logger.error(f"PDF {pdf_name} 处理失败: {e}")
        return {"status": "error", "error": str(e), "pdf": pdf_name}


def process_directory(
    input_dir: str,
    output_dir: str,
    provider: str = "easyocr",
    resume: bool = False,
    **kwargs
) -> dict:
    """批量处理目录中的所有PDF

    Args:
        input_dir: 输入目录
        output_dir: 输出目录
        provider: OCR provider
        resume: 是否断点续传
        **kwargs: 其他参数传递给process_pdf

    Returns:
        dict: 批量处理统计
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 查找所有PDF文件
    pdf_files = list(input_path.glob("**/*.pdf"))
    logger.info(f"在 {input_dir} 中找到 {len(pdf_files)} 个PDF文件")

    if not pdf_files:
        # 尝试查找PNG/JPG图片
        image_files = []
        for ext in ["*.png", "*.jpg", "*.jpeg", "*.tif", "*.tiff"]:
            image_files.extend(input_path.glob(f"**/{ext}"))
        logger.info(f"找到 {len(image_files)} 个图片文件")

        if image_files:
            # 处理单张图片
            return process_images(
                image_files,
                output_dir,
                provider,
                resume,
                **kwargs
            )

        logger.warning("未找到PDF或图片文件")
        return {"status": "no_files", "total": 0}

    # 批量处理PDF
    stats = {
        "total": len(pdf_files),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "total_pages": 0,
        "total_time": 0
    }

    for pdf_file in tqdm(pdf_files, desc="处理PDF"):
        result = process_pdf(
            str(pdf_file),
            str(output_path),
            provider,
            **kwargs
        )

        if result["status"] == "success":
            stats["success"] += 1
            stats["total_pages"] += result.get("pages", 0)
            stats["total_time"] += result.get("elapsed", 0)
        elif result["status"] == "skipped":
            stats["skipped"] += 1
            stats["total_pages"] += result.get("pages", 0)
        else:
            stats["failed"] += 1

    # 生成报告
    report = {
        "timestamp": datetime.now().isoformat(),
        "input_dir": input_dir,
        "output_dir": output_dir,
        "provider": provider,
        "stats": stats
    }

    report_file = output_path / "batch_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(
        f"批量处理完成: "
        f"成功 {stats['success']}, 失败 {stats['failed']}, 跳过 {stats['skipped']}, "
        f"共 {stats['total_pages']} 页, 耗时 {stats['total_time']:.1f}秒"
    )

    return report


def process_images(
    image_files: list,
    output_dir: str,
    provider: str = "easyocr",
    resume: bool = False,
    **kwargs
) -> dict:
    """批量处理图片文件

    Args:
        image_files: 图片文件列表
        output_dir: 输出目录
        provider: OCR provider
        resume: 是否断点续传
        **kwargs: 其他参数

    Returns:
        dict: 处理统计
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    processor = OCRProcessor(provider=provider)

    stats = {
        "total": len(image_files),
        "success": 0,
        "failed": 0,
        "total_chars": 0
    }

    for img_file in tqdm(image_files, desc="处理图片"):
        img_name = Path(img_file).stem
        result_file = output_path / f"{img_name}_result.json"

        # 检查是否跳过
        if resume and result_file.exists():
            logger.info(f"跳过已处理的图片: {img_name}")
            stats["success"] += 1
            continue

        try:
            result = processor.process_image(
                str(img_file),
                detect_variants=kwargs.get("detect_variants", True),
                detect_taboo=kwargs.get("detect_taboo", True),
                dynasty=kwargs.get("dynasty", "qing")
            )

            with open(result_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            stats["success"] += 1
            for page in result.get("pages", []):
                stats["total_chars"] += len(page.get("text", ""))

        except Exception as e:
            logger.error(f"图片 {img_name} 处理失败: {e}")
            stats["failed"] += 1

    logger.info(
        f"图片处理完成: 成功 {stats['success']}, 失败 {stats['failed']}, "
        f"共识别 {stats['total_chars']} 字符"
    )

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="古籍批量OCR识别脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/batch_ocr.py --dir "data/raw/固安县志（康熙）" --provider easyocr
  python scripts/batch_ocr.py --file "data/raw/test.pdf" --provider paddleocr
  python scripts/batch_ocr.py --dir "data/raw/咸丰版" --provider easyocr --resume
        """
    )

    # 输入选项（互斥）
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--dir", help="输入目录路径")
    input_group.add_argument("--file", help="单个文件路径")

    # 输出选项
    parser.add_argument("--output", "-o", required=True, help="输出目录路径")

    # OCR选项
    parser.add_argument(
        "--provider", "-p",
        choices=["easyocr", "paddleocr"],
        default="easyocr",
        help="OCR引擎 (默认: easyocr)"
    )
    parser.add_argument(
        "--dynasty",
        default="qing",
        choices=["qing", "ming", "song", "tang", "han"],
        help="朝代（用于避讳字检测，默认: qing）"
    )

    # 处理选项
    parser.add_argument("--start-page", type=int, default=0, help="起始页（0索引）")
    parser.add_argument("--end-page", type=int, default=None, help="结束页")
    parser.add_argument("--no-variants", action="store_true", help="禁用异体字检测")
    parser.add_argument("--no-taboo", action="store_true", help="禁用避讳字检测")
    parser.add_argument("--resume", "-r", action="store_true", help="断点续传")

    args = parser.parse_args()

    # 构建kwargs
    kwargs = {
        "detect_variants": not args.no_variants,
        "detect_taboo": not args.no_taboo,
        "dynasty": args.dynasty,
        "start_page": args.start_page,
        "end_page": args.end_page
    }

    logger.info(f"=" * 60)
    logger.info(f"古籍批量OCR识别")
    logger.info(f"=" * 60)
    logger.info(f"Provider: {args.provider}")
    logger.info(f"Dynasty: {args.dynasty}")
    logger.info(f"异体字检测: {kwargs['detect_variants']}")
    logger.info(f"避讳字检测: {kwargs['detect_taboo']}")
    logger.info(f"断点续传: {args.resume}")
    logger.info(f"=" * 60)

    start_time = time.time()

    if args.file:
        result = process_pdf(
            args.file,
            args.output,
            args.provider,
            **kwargs
        )
    else:
        result = process_directory(
            args.dir,
            args.output,
            args.provider,
            args.resume,
            **kwargs
        )

    elapsed = time.time() - start_time
    logger.info(f"总耗时: {elapsed:.1f}秒")

    return 0 if result.get("status") != "error" else 1


if __name__ == "__main__":
    sys.exit(main())
