"""
Tesseract OCR Provider
支持中文（简体/繁体）和古籍竖排文字识别
"""

import os
import logging
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np
import cv2
import pytesseract
from PIL import Image

from .base import BaseOCRProvider

logger = logging.getLogger(__name__)

# Tesseract路径（Windows）
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class TesseractOCRProvider(BaseOCRProvider):
    """Tesseract OCR 文字识别提供者"""

    def __init__(
        self,
        config: dict = None,
        lang: str = "chi_sim",
        tessdata_path: Optional[str] = None,
        vertical_mode: bool = False,
    ):
        """
        初始化 Tesseract OCR Provider

        Args:
            config: 配置字典
            lang: 语言，'chi_sim' 简体中文，'chi_tra' 繁体中文，'eng' 英文
                  可组合：'chi_sim+eng' 表示中文英文混合
            tessdata_path: tessdata目录路径，默认使用Tesseract内置路径
            vertical_mode: 是否为竖排文字模式
        """
        super().__init__(config)
        self.lang = lang
        self.vertical_mode = vertical_mode or self.config.get("vertical_mode", False)
        self.tessdata_path = tessdata_path

        # 设置Tesseract路径（如果pytesseract无法自动找到）
        if os.path.exists(TESSERACT_PATH):
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
            logger.info(f"Tesseract path set to: {TESSERACT_PATH}")

        # 如果有自定义tessdata路径，设置环境变量
        if tessdata_path:
            os.environ["TESSDATA_PREFIX"] = tessdata_path

        # Tesseract配置
        self.psm_mode = self._get_psm_mode()

        logger.info(f"TesseractOCRProvider initialized: lang={lang}, "
                   f"vertical={self.vertical_mode}, psm={self.psm_mode}")

    def _get_psm_mode(self) -> str:
        """
        获取Tesseract页面分割模式

        PSM modes:
        0: Orientation and script detection (OSD) only
        1: Automatic page segmentation with OSD
        3: Fully automatic page segmentation, but no OSD (default)
        4: Assume a single column of text of variable sizes
        5: Assume a single uniform block of vertically aligned text
        6: Assume a single uniform block of text
        7: Treat the image as a single text line
        8: Treat the image as a single word
        9: Treat the image as a single word in a circle
        10: Treat the image as a single character
        11: Sparse text. Find as much text as possible in no particular order
        12: Sparse text with OSD
        13: Raw line. Treat the image as a single text line, bypassing hacks
        """
        if self.vertical_mode:
            return "--psm 5"  # 竖排文字
        return "--psm 3"  # 自动分割

    def recognize(self, image: np.ndarray) -> List[Dict]:
        """
        识别图片中的文字

        Args:
            image: numpy array, RGB 格式 (H, W, C)

        Returns:
            识别结果列表
        """
        try:
            # 转换为PIL Image
            if len(image.shape) == 3:
                pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            else:
                pil_image = Image.fromarray(image)

            # Tesseract配置
            config = f"{self.psm_mode} -l {self.lang}"

            # 执行OCR
            data = pytesseract.image_to_data(
                pil_image,
                config=config,
                output_type=pytesseract.Output.DICT,
                pandas_config=None
            )

            # 解析结果
            parsed_results = []
            n_boxes = len(data['text'])

            for i in range(n_boxes):
                text = data['text'][i].strip()
                conf = float(data['conf'][i])

                # 跳过空文本和低置信度
                if not text or conf < 30:
                    continue

                # 获取边界框
                x = data['left'][i]
                y = data['top'][i]
                w = data['width'][i]
                h = data['height'][i]

                parsed_results.append({
                    "text": text,
                    "confidence": conf / 100.0,  # 转换为0-1
                    "bbox": [x, y, x + w, y + h],
                    "polygon": [[x, y], [x + w, y], [x + w, y + h], [x, y + h]],
                })

            return parsed_results

        except Exception as e:
            logger.error(f"TesseractOCR recognition failed: {e}")
            return []

    def recognize_to_text(self, image: np.ndarray) -> str:
        """
        识别图片中的文字，直接返回纯文本

        Args:
            image: numpy array, RGB 格式

        Returns:
            识别的文本
        """
        try:
            if len(image.shape) == 3:
                pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            else:
                pil_image = Image.fromarray(image)

            config = f"{self.psm_mode} -l {self.lang}"
            text = pytesseract.image_to_string(pil_image, config=config)
            return text.strip()

        except Exception as e:
            logger.error(f"TesseractOCR text extraction failed: {e}")
            return ""

    def batch_recognize(self, images: List[np.ndarray]) -> List[List[Dict]]:
        """批量识别多张图片"""
        results = []
        for img in images:
            results.append(self.recognize(img))
        return results
