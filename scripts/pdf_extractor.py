"""
PDF文本提取器 - 从固安县志PDF中提取文本
支持：PDF文本提取、PDF转图像（用于OCR）、页数统计
"""

import logging
import os
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PDFExtractor:
    """PDF文本提取器，支持文本提取、图像转换和元数据获取"""

    def __init__(self):
        """初始化PDF提取器"""
        self.logger = logging.getLogger(self.__class__.__name__)

    def extract_text(self, pdf_path: str, start_page: int = 0, end_page: Optional[int] = None) -> str:
        """
        从PDF中提取文本

        Args:
            pdf_path: PDF文件路径
            start_page: 起始页码（从0开始）
            end_page: 结束页码（不包含），None表示到最后一页

        Returns:
            提取的文本内容
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        self.logger.info(f"开始提取PDF文本: {pdf_path}")
        self.logger.debug(f"页码范围: {start_page} - {end_page}")

        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)

            if start_page < 0 or start_page >= total_pages:
                raise ValueError(f"起始页码 {start_page} 超出有效范围 (0-{total_pages-1})")

            if end_page is None:
                end_page = total_pages
            elif end_page > total_pages:
                self.logger.warning(f"结束页码 {end_page} 超出总页数 {total_pages}，调整为 {total_pages}")
                end_page = total_pages

            text_parts = []
            for page_num in range(start_page, end_page):
                page = doc[page_num]
                text = page.get_text()
                text_parts.append(text)

            doc.close()

            result = "\n".join(text_parts)
            self.logger.info(f"成功提取 {len(text_parts)} 页文本，共 {len(result)} 字符")
            return result

        except Exception as e:
            self.logger.error(f"提取PDF文本失败: {e}")
            raise

    def extract_all_pages_text(self, pdf_path: str) -> list[dict]:
        """
        提取PDF所有页面的文本

        Args:
            pdf_path: PDF文件路径

        Returns:
            包含每页文本的字典列表 [{"page_num": int, "text": str}, ...]
            会跳过文本量少于50字符的页面
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        self.logger.info(f"开始提取PDF所有页面文本: {pdf_path}")

        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            self.logger.info(f"PDF总页数: {total_pages}")

            results = []
            skipped_pages = 0

            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text().strip()

                # 跳过文本量少于50字符的页面
                if len(text) < 50:
                    skipped_pages += 1
                    self.logger.debug(f"跳过页面 {page_num + 1}（仅 {len(text)} 字符）")
                    continue

                results.append({
                    "page_num": page_num + 1,  # 1-indexed for human readability
                    "text": text
                })

            doc.close()

            self.logger.info(f"成功提取 {len(results)} 页文本，跳过 {skipped_pages} 页（<50字符）")
            return results

        except Exception as e:
            self.logger.error(f"提取PDF所有页面文本失败: {e}")
            raise

    def pdf_to_images(self, pdf_path: str, output_dir: str, dpi: int = 300) -> list[str]:
        """
        将PDF页面转换为图像

        Args:
            pdf_path: PDF文件路径
            output_dir: 输出目录
            dpi: 图像分辨率，默认300

        Returns:
            生成的图像文件路径列表
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        self.logger.info(f"开始将PDF转换为图像: {pdf_path}, DPI: {dpi}")

        try:
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)

            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            self.logger.info(f"PDF总页数: {total_pages}")

            image_paths = []

            for page_num in range(total_pages):
                page = doc[page_num]

                # 计算缩放因子
                zoom = dpi / 72
                mat = fitz.Matrix(zoom, zoom)

                # 渲染页面为Pixmap
                pix = page.get_pixmap(matrix=mat)

                # 生成输出文件名
                output_filename = f"page_{page_num + 1:04d}.png"
                output_path = os.path.join(output_dir, output_filename)

                # 保存图像
                pix.save(output_path)
                image_paths.append(output_path)

                if (page_num + 1) % 10 == 0 or page_num == total_pages - 1:
                    self.logger.info(f"已转换 {page_num + 1}/{total_pages} 页")

            doc.close()

            self.logger.info(f"成功转换 {len(image_paths)} 页为图像")
            return image_paths

        except Exception as e:
            self.logger.error(f"PDF转图像失败: {e}")
            raise

    def get_page_count(self, pdf_path: str) -> int:
        """
        获取PDF页数

        Args:
            pdf_path: PDF文件路径

        Returns:
            PDF页数
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        try:
            doc = fitz.open(pdf_path)
            count = len(doc)
            doc.close()
            self.logger.debug(f"PDF {pdf_path} 页数: {count}")
            return count
        except Exception as e:
            self.logger.error(f"获取PDF页数失败: {e}")
            raise

    def get_metadata(self, pdf_path: str) -> dict:
        """
        获取PDF元数据

        Args:
            pdf_path: PDF文件路径

        Returns:
            包含元数据的字典
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

        self.logger.info(f"获取PDF元数据: {pdf_path}")

        try:
            doc = fitz.open(pdf_path)

            metadata = doc.metadata
            page_count = len(doc)

            result = {
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "subject": metadata.get("subject", ""),
                "creator": metadata.get("creator", ""),
                "producer": metadata.get("producer", ""),
                "creation_date": metadata.get("creationDate", ""),
                "mod_date": metadata.get("modDate", ""),
                "page_count": page_count
            }

            doc.close()

            self.logger.info(f"成功获取元数据: {result['title'] or '无标题'}, {page_count} 页")
            return result

        except Exception as e:
            self.logger.error(f"获取PDF元数据失败: {e}")
            raise


if __name__ == "__main__":
    # 测试代码
    import sys

    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        extractor = PDFExtractor()

        print(f"=== PDF信息: {pdf_path} ===")
        metadata = extractor.get_metadata(pdf_path)
        for key, value in metadata.items():
            print(f"  {key}: {value}")

        print(f"\n页数: {extractor.get_page_count(pdf_path)}")
    else:
        print("用法: python pdf_extractor.py <pdf_path>")
