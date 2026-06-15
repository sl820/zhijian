"""
RapidOCR Provider - 基于 ONNX 的跨平台 OCR

相比 EasyOCR：
- 中文识别更准（PP-OCRv3/v4 后端，多语言模型含繁简）
- 体积小（onnxruntime ~30MB，无 paddlepaddle 500MB+ 依赖）
- 跨平台稳（Windows / Linux / Mac 都能装）
- 支持繁體中文

相比 PaddleOCR：
- 无需 paddlepaddle（避免 500MB+ 依赖和 langchain 兼容问题）
- 模型 ONNX 格式，启动更快
- 准确度与 PaddleOCR 相当
"""
import logging
import os
from typing import Dict, List

import numpy as np

from .base import BaseOCRProvider

logger = logging.getLogger(__name__)

# 抑制 RapidOCR 内部冗余日志
os.environ.setdefault("RAPIDOCR_LOG_LEVEL", "WARN")


class RapidOCRProvider(BaseOCRProvider):
    """RapidOCR（ONNX 后端）Provider"""

    def __init__(self, config: dict = None):
        super().__init__(config)
        self._engine = None

        # 配置项
        self.lang = self.config.get("lang", "ch")  # ch = 简繁通用
        self.use_angle_cls = self.config.get("use_angle_cls", True)
        self.text_score = self.config.get("text_score", 0.5)

        try:
            from rapidocr_onnxruntime import RapidOCR
            self._engine = RapidOCR(
                lang=self.lang,
                use_angle_cls=self.use_angle_cls,
                text_score=self.text_score,
            )
            logger.info(
                f"RapidOCR 初始化完成: lang={self.lang}, "
                f"angle_cls={self.use_angle_cls}, score={self.text_score}"
            )
        except Exception as e:
            logger.error(f"RapidOCR 初始化失败: {e}")
            self._engine = None

    def recognize(self, image: np.ndarray) -> List[Dict]:
        """
        识别图片中的文字

        Args:
            image: numpy array, RGB 格式 (H, W, C)

        Returns:
            List[Dict]，每项含 {text, confidence, bbox, polygon}
        """
        if self._engine is None:
            raise RuntimeError("RapidOCR 未初始化")

        # 古籍竖排：H > W 时旋转 90°，让文字变横排以提高识别率
        # 旋转后右侧首列（原图最右）变成顶行，符合「从右到左」的阅读顺序
        h, w = image.shape[:2]
        rotated = False
        if h > w * 1.2:
            image = np.rot90(image, k=-1).copy()  # 顺时针 90°
            rotated = True
            logger.info(f"Vertical text detected ({h}x{w}), rotated to {image.shape[1]}x{image.shape[0]}")

        # RapidOCR 接受 numpy array (BGR) 或文件路径
        # EasyOCR 输入是 RGB；OpenCV 通常 BGR —— 这里 image 已是 RGB（来自 preprocess.load_image）
        result, _elapse = self._engine(image)

        if not result:
            return []

        # 如果旋转过，把 bbox 旋转回原坐标系
        if rotated:
            new_h, new_w = image.shape[:2]
            result = self._rotate_bboxes_back(result, (new_w, new_h))

        lines: List[Dict] = []
        for item in result:
            if not item or len(item) < 3:
                continue
            bbox, text, conf = item[0], item[1], float(item[2])
            if not text or conf < self.text_score:
                continue
            lines.append({
                "text": text,
                "confidence": conf,
                "bbox": bbox,
                "polygon": bbox,
            })
        return lines

    @staticmethod
    def _rotate_bboxes_back(result, orig_shape):
        """把旋转 90° 后的 bbox 旋转回原图坐标系"""
        new_w, new_h = orig_shape
        rotated = []
        for item in result:
            if not item or len(item) < 3:
                rotated.append(item)
                continue
            bbox, text, conf = item[0], item[1], float(item[2])
            new_bbox = []
            for pt in bbox:
                x, y = pt[0], pt[1]
                # 顺时针 90° 旋转的逆变换：(x, y) -> (h - y, x)
                new_bbox.append([float(new_h - y), float(x)])
            rotated.append([new_bbox, text, conf])
        return rotated

    def batch_recognize(self, images: List[np.ndarray]) -> List[List[Dict]]:
        """批量识别"""
        return [self.recognize(img) for img in images]
