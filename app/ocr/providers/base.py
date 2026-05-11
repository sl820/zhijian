"""OCR Provider 基类 - 定义统一接口"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import numpy as np


class BaseOCRProvider(ABC):
    """OCR Provider 基类，定义统一接口"""

    def __init__(self, config: dict = None):
        """
        初始化 OCR Provider

        Args:
            config: 配置字典，包含 provider 特定的配置
        """
        self.config = config or {}

    @abstractmethod
    def recognize(self, image: np.ndarray) -> List[Dict]:
        """
        识别图片中的文字

        Args:
            image: numpy array, RGB 格式 (H, W, C)

        Returns:
            List of Dict, 每个包含:
                - text: str, 识别的文本
                - confidence: float, 置信度 0-1
                - bbox: List[float], 边界框 [x1, y1, x2, y2]
                - polygon: List[List[int]], 4个角点坐标
        """
        pass

    def recognize_with_chars(self, image: np.ndarray) -> List[Dict]:
        """
        带字符级信息的识别（可选实现）

        Args:
            image: numpy array, RGB 格式

        Returns:
            List of Dict，每个包含 chars 字段
        """
        # 默认实现：调用 recognize，然后按字符均分 bbox
        line_results = self.recognize(image)

        for line in line_results:
            text = line.get("text", "")
            bbox = line.get("bbox", [])

            if not text or len(bbox) < 4:
                line["chars"] = []
                continue

            line_width = bbox[2] - bbox[0]
            char_width = line_width / len(text) if len(text) > 0 else 10

            chars = []
            for i, char in enumerate(text):
                char_bbox = [
                    int(bbox[0] + i * char_width),
                    bbox[1],
                    int(bbox[0] + (i + 1) * char_width),
                    bbox[3],
                ]
                chars.append({
                    "char": char,
                    "bbox": char_bbox,
                    "confidence": line["confidence"],
                })
            line["chars"] = chars

        return line_results

    @abstractmethod
    def batch_recognize(self, images: List[np.ndarray]) -> List[List[Dict]]:
        """
        批量识别多张图片

        Args:
            images: numpy array 列表

        Returns:
            批量识别结果
        """
        pass

    @property
    def name(self) -> str:
        """Provider 名称"""
        return self.__class__.__name__.replace("OCRProvider", "").lower()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"
