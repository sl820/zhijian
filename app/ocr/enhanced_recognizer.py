"""
OCR推理与后处理模块
结合EasyOCR + 古文字典约束 + LLM纠错
"""

import cv2
import numpy as np
import easyocr
import torch
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import json
import re


class AncientTextRecognizer:
    """古籍文字识别器"""

    def __init__(self, gpu: bool = True, use_dict_constraint: bool = True,
                 dict_path: Optional[str] = None):
        """
        初始化识别器

        Args:
            gpu: 是否使用GPU
            use_dict_constraint: 是否使用字典约束
            dict_path: 自定义字典路径
        """
        self.gpu = gpu and torch.cuda.is_available()

        # 初始化EasyOCR Reader
        # ch_tra: 繁体中文, en: 英文
        self.reader = easyocr.Reader(['ch_tra', 'en'], gpu=self.gpu, verbose=False)

        # 字符约束
        self.use_dict_constraint = use_dict_constraint
        self.allowed_chars = self._load_dictionary(dict_path)

        # 古籍常用词汇（用于纠错）
        self.ancient_words = self._load_ancient_words()

    def _load_dictionary(self, dict_path: Optional[str] = None) -> Optional[set]:
        """加载字符字典"""
        if not self.use_dict_constraint:
            return None

        default_dict_path = Path("C:/Users/hbusl/qi_wu_bo_yan/dataset/ocr_training/char_dict.json")

        if dict_path and Path(dict_path).exists():
            path = Path(dict_path)
        elif default_dict_path.exists():
            path = default_dict_path
        else:
            print("No dictionary found, using unconstrained recognition")
            return None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        char_set = set(data.get("char2idx", {}).keys())
        print(f"Dictionary loaded: {len(char_set)} characters")
        return char_set

    def _load_ancient_words(self) -> List[str]:
        """加载古籍常用词汇（用于上下文纠错）"""
        # 常见古籍词汇
        return [
            "尚書", "禮記", "周易", "詩經", "春秋", "論語",
            "青銅", "銘文", "鐘鼎", "玉器", "石器", "瓦當",
            "甲骨", "金文", "篆書", "楷書", "隸書", "行書",
            "天子", "諸侯", "大夫", "士", "君", "臣", "民",
            "祭祀", "征伐", "冊命", "賞賜", "功勞", "德行",
            "萬年", "永昌", "子孫", "保用", "無疆", "，眉寿",
            "吉金", "鑄器", "遺留", "後世", "昭我", "孝享",
            "的感受", "的", "是", "在", "有", "之", "為", "與"
        ]

    def recognize(self, image_path: str, detail: bool = True) -> List[Dict]:
        """
        识别图像中的文字

        Args:
            image_path: 图像路径
            detail: 是否返回详细信息

        Returns:
            识别结果列表
        """
        results = self.reader.readtext(image_path)

        processed_results = []
        for (bbox, text, confidence) in results:
            # 应用字典约束
            if self.use_dict_constraint and self.allowed_chars:
                text = self._constrain_text(text)

            # LLM风格的上下文纠错
            text = self._contextual_correct(text)

            result = {
                "text": text,
                "confidence": confidence,
                "bbox": bbox
            }

            if detail:
                result["normalized_text"] = self._normalize_text(text)

            processed_results.append(result)

        return processed_results

    def recognize_batched(self, image_paths: List[str], detail: bool = True) -> List[List[Dict]]:
        """批量识别"""
        all_results = []
        for path in image_paths:
            results = self.recognize(path, detail=detail)
            all_results.append(results)
        return all_results

    def _constrain_text(self, text: str) -> str:
        """字典约束：移除不在字典中的字符"""
        if not self.allowed_chars:
            return text

        constrained = ""
        for char in text:
            if char in self.allowed_chars or char in " \t\n":
                constrained += char
            else:
                # 未知字符标记
                constrained += "□"

        return constrained

    def _contextual_correct(self, text: str) -> str:
        """基于上下文的简单纠错"""
        # 常见OCR错误模式
        error_patterns = [
            (r"眉寿", "眉寿"),  # 保持正确
            (r"無疆", "無疆"),
            (r"萬年", "萬年"),
        ]

        # 简单纠错：检查是否匹配常见词汇
        for word in self.ancient_words:
            if len(word) >= 2:
                # 检查文本中是否有相似词（编辑距离<2）
                if self._is_similar(text.strip(), word):
                    return word

        return text

    def _is_similar(self, text: str, word: str, max_distance: int = 2) -> bool:
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
        # 移除多余空格
        text = re.sub(r'\s+', '', text)
        # 统一标点
        text = text.replace(' ', '').replace('　', '')
        return text

    def get_full_text(self, results: List[Dict], join_str: str = "") -> str:
        """合并所有识别结果"""
        return join_str.join([r["text"] for r in results])


class OCRBenchmark:
    """OCR性能基准测试"""

    def __init__(self, recognizer: AncientTextRecognizer):
        self.recognizer = recognizer

    def evaluate(self, test_images: List[Tuple[str, str]]) -> Dict:
        """
        评估识别器性能

        Args:
            test_images: [(image_path, ground_truth), ...]

        Returns:
            评估指标
        """
        total_samples = len(test_images)
        correct_samples = 0
        total_chars = 0
        correct_chars = 0

        char_errors = {}

        for img_path, ground_truth in test_images:
            results = self.recognizer.recognize(img_path, detail=False)
            predicted = self.recognizer.get_full_text(results)

            # 字符级准确率
            for i, (gt_char, pred_char) in enumerate(zip(ground_truth, predicted)):
                total_chars += 1
                if gt_char == pred_char:
                    correct_chars += 1
                else:
                    error_type = f"{gt_char}->{pred_char}"
                    char_errors[error_type] = char_errors.get(error_type, 0) + 1

            # 样本级准确率
            if predicted.strip() == ground_truth.strip():
                correct_samples += 1

        metrics = {
            "sample_accuracy": correct_samples / total_samples if total_samples > 0 else 0,
            "char_accuracy": correct_chars / total_chars if total_chars > 0 else 0,
            "total_samples": total_samples,
            "total_chars": total_chars,
            "top_errors": sorted(char_errors.items(), key=lambda x: -x[1])[:10]
        }

        return metrics

    def print_report(self, metrics: Dict):
        """打印评估报告"""
        print("\n" + "="*60)
        print("OCR 性能评估报告")
        print("="*60)
        print(f"样本准确率: {metrics['sample_accuracy']:.2%}")
        print(f"字符准确率: {metrics['char_accuracy']:.2%}")
        print(f"测试样本数: {metrics['total_samples']}")
        print(f"测试字符数: {metrics['total_chars']}")
        print("\n常见错误:")
        for error, count in metrics.get("top_errors", []):
            print(f"  {error}: {count}次")
        print("="*60)


if __name__ == "__main__":
    # 测试识别器
    recognizer = AncientTextRecognizer(gpu=True, use_dict_constraint=False)

    # 测试图像
    test_image = "C:/Users/hbusl/qi_wu_bo_yan/dataset/ocr_raw"
    if Path(test_image).exists():
        images = list(Path(test_image).glob("*.jpg"))[:1]
        if images:
            results = recognizer.recognize(str(images[0]))
            print(f"Recognized {len(results)} text regions")
            for r in results:
                print(f"  '{r['text']}' (confidence: {r['confidence']:.2f})")
