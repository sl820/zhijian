"""
PaddleOCR Provider - 百度开源 OCR
支持 PP-OCRv4 中文识别，适合古籍竖排文字

注意: PaddleOCR 需要 Python 3.12 环境
如遇兼容性问题，请使用 .venv_paddle 虚拟环境
"""
import os
import logging
from typing import List, Dict
import numpy as np
import cv2
from .base import BaseOCRProvider

logger = logging.getLogger(__name__)

# 全局 PaddleOCR 实例
_paddle_ocr = None


def _get_paddle_ocr(lang: str = "ch", use_angle_cls: bool = True):
    """获取或创建全局 PaddleOCR 实例"""
    global _paddle_ocr

    if _paddle_ocr is None:
        try:
            from paddleocr import PaddleOCR
        except (ImportError, Exception) as e:
            logger.error(f"无法导入 PaddleOCR: {e}")
            raise

        logger.info(f"Initializing PaddleOCR: lang={lang}")

        # 检测是否使用新版 PaddleOCR (3.x)
        try:
            _paddle_ocr = PaddleOCR(
                lang=lang,
                use_doc_orientation_classify=use_angle_cls,
            )
        except (ValueError, TypeError):
            # 旧版 PaddleOCR (2.x) 参数不同
            _paddle_ocr = PaddleOCR(
                lang=lang,
                use_angle_cls=use_angle_cls,
                use_gpu=False,
                show_log=False,
            )

        logger.info("PaddleOCR initialized successfully")

    return _paddle_ocr


class PaddleOCRProvider(BaseOCRProvider):
    """PaddleOCR 文字识别提供者"""

    def __init__(
        self,
        config: dict = None,
        lang: str = "ch",
        use_angle_cls: bool = True,
    ):
        """
        初始化 PaddleOCR Provider

        Args:
            config: 配置字典
            lang: 语言，'ch' 简体中文，'ch_tra' 繁体中文，'en' 英文
            use_angle_cls: 是否检测文字方向
        """
        super().__init__(config)
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self._reader = None

        # 竖排文字支持
        self.vertical_text = self.config.get("vertical_text", False)

        logger.info(
            f"PaddleOCRProvider initialized: lang={lang}, "
            f"vertical={self.vertical_text}"
        )

    def _get_reader(self):
        """延迟加载 PaddleOCR"""
        if self._reader is None:
            self._reader = _get_paddle_ocr(
                lang=self.lang,
                use_angle_cls=self.use_angle_cls,
            )
        return self._reader

    def recognize(self, image: np.ndarray) -> List[Dict]:
        """
        识别图片中的文字

        Args:
            image: numpy array, RGB 格式 (H, W, C)

        Returns:
            识别结果列表
        """
        reader = self._get_reader()

        # PaddleOCR 需要 BGR 格式
        if len(image.shape) == 3 and image.shape[2] == 3:
            img_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        else:
            img_bgr = image

        try:
            # 新版 PaddleOCR (3.x)
            if hasattr(reader, 'ocr'):
                results = reader.ocr(img_bgr)
            else:
                # 旧版 PaddleOCR (2.x)
                results = reader.ocr(img_bgr, cls=self.use_angle_cls)

            if not results or not results[0]:
                return []

            parsed_results = []
            for line in results[0]:
                if not line:
                    continue

                # PaddleOCR 返回格式: [ [bbox_points], (text, confidence) ]
                if len(line) < 2:
                    continue

                bbox_points = line[0]
                text_info = line[1]
                text = text_info[0] if isinstance(text_info, tuple) else text_info
                confidence = float(text_info[1]) if isinstance(text_info, tuple) and len(text_info) > 1 else 0.9

                # 计算边界框
                xs = [p[0] for p in bbox_points]
                ys = [p[1] for p in bbox_points]
                x1, y1 = min(xs), min(ys)
                x2, y2 = max(xs), max(ys)
                bbox = [float(x1), float(y1), float(x2), float(y2)]

                parsed_results.append({
                    "text": text.strip(),
                    "confidence": confidence,
                    "bbox": bbox,
                    "polygon": [[int(p[0]), int(p[1])] for p in bbox_points],
                })

            return parsed_results

        except Exception as e:
            logger.error(f"PaddleOCR recognition failed: {e}")
            return []

    def batch_recognize(self, images: List[np.ndarray]) -> List[List[Dict]]:
        """
        批量识别多张图片

        注意：PaddleOCR 不支持真正的批量，这里串行调用
        """
        results = []
        for img in images:
            results.append(self.recognize(img))
        return results
