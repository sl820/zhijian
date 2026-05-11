"""
EnhancedOCR Provider - 带字典约束和上下文纠错的OCR
基于 PaddleOCR + 古文字典 + LLM风格纠错
"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Optional
import cv2
import numpy as np

from .base import BaseOCRProvider

logger = logging.getLogger(__name__)

# 全局 PaddleOCR reader 实例（延迟加载）
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

        logger.info(f"Initializing PaddleOCR with GPU: lang={lang}")

        # 检测是否使用新版 PaddleOCR (3.x)
        try:
            _paddle_ocr = PaddleOCR(
                lang=lang,
                use_doc_orientation_classify=use_angle_cls,
                use_gpu=True,
                show_log=False,
            )
        except (ValueError, TypeError):
            # 旧版 PaddleOCR (2.x) 参数不同
            _paddle_ocr = PaddleOCR(
                lang=lang,
                use_angle_cls=use_angle_cls,
                use_gpu=True,
                show_log=False,
            )

        logger.info("PaddleOCR initialized successfully")

    return _paddle_ocr


class EnhancedOCRProvider(BaseOCRProvider):
    """增强OCR Provider - 带字典约束和上下文纠错（基于PaddleOCR）"""

    def __init__(
        self,
        config: dict = None,
        lang: str = "ch",
        use_angle_cls: bool = True,
        use_dict_constraint: bool = True,
        use_contextual_correction: bool = True,
        dict_path: Optional[str] = None,
    ):
        """
        初始化 EnhancedOCR Provider

        Args:
            config: 配置字典
            lang: 语言，'ch' 简体中文，'ch_tra' 繁体中文
            use_angle_cls: 是否检测文字方向
            use_dict_constraint: 是否使用字典约束
            use_contextual_correction: 是否使用上下文纠错
            dict_path: 自定义字典路径
        """
        super().__init__(config)
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self.use_dict_constraint = use_dict_constraint
        self.use_contextual_correction = use_contextual_correction
        self._reader = None
        self.allowed_chars = self._load_dictionary(dict_path)

        # 古籍常用词汇（用于上下文纠错）
        self.ancient_words = self._load_ancient_words()

        logger.info(f"EnhancedOCRProvider initialized: lang={lang}, "
                   f"dict_constraint={use_dict_constraint}, "
                   f"contextual_correction={use_contextual_correction}")

    def _get_reader(self):
        """延迟加载 PaddleOCR reader"""
        if self._reader is None:
            self._reader = _get_paddle_ocr(
                lang=self.lang,
                use_angle_cls=self.use_angle_cls,
            )
        return self._reader

    def _load_dictionary(self, dict_path: Optional[str] = None) -> Optional[set]:
        """加载字符字典"""
        if not self.use_dict_constraint:
            return None

        # 尝试多个可能的字典路径
        possible_paths = []
        if dict_path:
            possible_paths.append(Path(dict_path))

        # 项目内的字典
        possible_paths.extend([
            Path("data/ocr_char_dict.json"),
            Path("app/ocr/char_dict.json"),
        ])

        for path in possible_paths:
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    char_set = set(data.get("char2idx", {}).keys())
                    logger.info(f"Dictionary loaded from {path}: {len(char_set)} characters")
                    return char_set
                except Exception as e:
                    logger.warning(f"Failed to load dictionary from {path}: {e}")

        logger.info("No dictionary found, using unconstrained recognition")
        return None

    def _load_ancient_words(self) -> List[str]:
        """加载古籍常用词汇"""
        return [
            # 古籍经典
            "尚书", "礼记", "周易", "诗经", "春秋", "论语", "大学", "中庸",
            # 青铜器相关
            "青铜", "铭文", "钟鼎", "玉器", "石器", "瓦当", "吉金", "铸器",
            # 古文字体
            "甲骨", "金文", "篆书", "楷书", "隶书", "行书", "草书",
            # 官职
            "天子", "诸侯", "大夫", "士", "君", "臣", "民", "公", "侯",
            # 社会活动
            "祭祀", "征伐", "册命", "赏赐", "功劳", "德行",
            # 祈愿语
            "万年", "永昌", "子孙", "保用", "无疆", "眉寿", "遗留", "后世",
            # 常见人名、地名
            "周公", "成王", "康王", "昭王", "穆王",
        ]

    def recognize(self, image: np.ndarray) -> List[Dict]:
        """识别图片中的文字（带字典约束和纠错）"""
        reader = self._get_reader()

        # PaddleOCR 需要 BGR 格式
        if len(image.shape) == 3 and image.shape[2] == 3:
            img_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        else:
            img_bgr = image

        try:
            # PaddleOCR 3.x
            if hasattr(reader, 'ocr'):
                results = reader.ocr(img_bgr)
            else:
                # PaddleOCR 2.x
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

                # 应用字典约束
                if self.use_dict_constraint and self.allowed_chars:
                    text = self._constrain_text(text)

                # 上下文纠错
                if self.use_contextual_correction:
                    text = self._contextual_correct(text)

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
                    "normalized_text": self._normalize_text(text),
                })

            return parsed_results

        except Exception as e:
            logger.error(f"EnhancedOCR recognition failed: {e}")
            return []

    def _constrain_text(self, text: str) -> str:
        """字典约束：移除不在字典中的字符"""
        if not self.allowed_chars:
            return text

        constrained = ""
        for char in text:
            if char in self.allowed_chars or char in " \t\n，。、；：！？""''（）【】《》":
                constrained += char
            else:
                # 未知字符标记
                constrained += "□"

        return constrained

    def _contextual_correct(self, text: str) -> str:
        """基于上下文的简单纠错"""
        if not text:
            return text

        text = text.strip()

        # 检查是否匹配常见词汇
        for word in self.ancient_words:
            if len(word) >= 2 and len(text) >= 2:
                # 检查编辑距离
                if self._is_similar(text, word, max_distance=1):
                    return word

        return text

    def _is_similar(self, text: str, word: str, max_distance: int = 1) -> bool:
        """计算编辑距离判断相似性"""
        if text == word:
            return True

        if abs(len(text) - len(word)) > max_distance:
            return False

        # 简化的编辑距离计算
        dp = [[0] * (len(word) + 1) for _ in range(len(text) + 1)]

        for i in range(len(text) + 1):
            dp[i][0] = i
        for j in range(len(word) + 1):
            dp[0][j] = j

        for i in range(1, len(text) + 1):
            for j in range(1, len(word) + 1):
                if text[i-1] == word[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])

        return dp[len(text)][len(word)] <= max_distance

    def _normalize_text(self, text: str) -> str:
        """文本规范化"""
        import re
        # 移除多余空格
        text = re.sub(r'\s+', '', text)
        # 统一标点
        text = text.replace(' ', '').replace('　', '')
        return text

    def batch_recognize(self, images: List[np.ndarray]) -> List[List[Dict]]:
        """批量识别多张图片"""
        results = []
        for img in images:
            results.append(self.recognize(img))
        return results
