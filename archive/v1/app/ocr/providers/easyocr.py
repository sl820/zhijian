"""
EasyOCR Provider - 基于现有 AncientBookOCR 重构
"""
import logging
from typing import List, Dict
import cv2
import numpy as np
from .base import BaseOCRProvider

logger = logging.getLogger(__name__)

# 全局 EasyOCR reader 实例（延迟加载）
_easyocr_reader = None


def _get_easyocr_reader(gpu: bool = True, languages: List[str] = None):
    """获取或创建全局 EasyOCR reader 实例"""
    global _easyocr_reader

    if _easyocr_reader is None:
        import easyocr

        languages = languages or ['ch_sim', 'en']
        logger.info(f"Initializing EasyOCR with GPU={gpu}, languages={languages}")

        _easyocr_reader = easyocr.Reader(
            languages,
            gpu=gpu,
            model_storage_directory=None,
            download_enabled=True,
            detector=True,
            recognizer=True,
            verbose=False,
        )
        logger.info("EasyOCR initialized successfully")

    return _easyocr_reader


class EasyOCRProvider(BaseOCRProvider):
    """EasyOCR 文字识别提供者"""

    def __init__(
        self,
        config: dict = None,
        lang: str = "ch_sim",
        gpu: bool = True,
    ):
        """
        初始化 EasyOCR Provider

        Args:
            config: 配置字典
            lang: 语言代码，'ch_sim' 简体中文，'ch_tra' 繁体中文
            gpu: 是否使用 GPU 加速
        """
        super().__init__(config)
        self.lang = lang
        self.gpu = gpu
        self._reader = None

        if '+' in lang:
            self.languages = lang.split('+')
        else:
            self.languages = [lang]

        logger.info(f"EasyOCRProvider initialized: lang={lang}, gpu={gpu}")

    def _get_reader(self):
        """延迟加载 EasyOCR reader"""
        if self._reader is None:
            self._reader = _get_easyocr_reader(gpu=self.gpu, languages=self.languages)
        return self._reader

    def recognize(self, image: np.ndarray) -> List[Dict]:
        """识别图片中的文字"""
        reader = self._get_reader()

        # 转换为 RGB 格式
        if len(image.shape) == 3 and image.shape[2] == 3:
            img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            img_rgb = image

        try:
            results = reader.readtext(img_rgb)

            if not results:
                return []

            parsed_results = []
            for item in results:
                if item is None or len(item) < 3:
                    continue

                bbox_points = item[0]
                text = item[1]
                confidence = float(item[2]) if len(item) > 2 else 0.0

                # 4点 polygon 转 bounding box [x1, y1, x2, y2]
                xs = [p[0] for p in bbox_points]
                ys = [p[1] for p in bbox_points]
                x1, y1 = min(xs), min(ys)
                x2, y2 = max(xs), max(ys)
                bbox = [int(x1), int(y1), int(x2), int(y2)]

                parsed_results.append({
                    "text": text.strip(),
                    "confidence": confidence,
                    "bbox": bbox,
                    "polygon": [[int(p[0]), int(p[1])] for p in bbox_points],
                })

            return parsed_results

        except Exception as e:
            logger.error(f"EasyOCR recognition failed: {e}")
            return []

    def batch_recognize(self, images: List[np.ndarray]) -> List[List[Dict]]:
        """批量识别多张图片"""
        reader = self._get_reader()

        rgb_images = []
        for img in images:
            if len(img.shape) == 3 and img.shape[2] == 3:
                rgb_images.append(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            else:
                rgb_images.append(img)

        try:
            batch_results = reader.readtext_batch(rgb_images)

            all_parsed = []
            for results in batch_results:
                if not results:
                    all_parsed.append([])
                    continue

                parsed_results = []
                for item in results:
                    if item is None or len(item) < 3:
                        continue

                    bbox_points = item[0]
                    text = item[1]
                    confidence = float(item[2]) if len(item) > 2 else 0.0

                    xs = [p[0] for p in bbox_points]
                    ys = [p[1] for p in bbox_points]
                    x1, y1 = min(xs), min(ys)
                    x2, y2 = max(xs), max(ys)
                    bbox = [int(x1), int(y1), int(x2), int(y2)]

                    parsed_results.append({
                        "text": text.strip(),
                        "confidence": confidence,
                        "bbox": bbox,
                        "polygon": [[int(p[0]), int(p[1])] for p in bbox_points],
                    })

                all_parsed.append(parsed_results)

            return all_parsed

        except Exception as e:
            logger.error(f"EasyOCR batch recognition failed: {e}")
            return [[] for _ in images]
