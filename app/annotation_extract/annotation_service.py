"""
批校痕迹提取服务 - 整合检测、分类、OCR、对齐全流程

提供古籍批校痕迹的端到端提取流程：
1. Faster R-CNN检测批注区域
2. 批注类型分类（朱批/墨批/圈点/划线）
3. OCR识别批注文字
4. 与正文章节对齐
"""

import logging
from typing import Dict, List, Optional, Tuple
import numpy as np

from .detector import AnnotationDetector, AnnotationTypeClassifier
from .ocr import AnnotationOCR
from .aligner import AnnotationAligner

logger = logging.getLogger(__name__)


# 批注类型名称映射
ANNOTATION_TYPE_NAMES = {
    0: "朱批",     # 红色批注
    1: "墨批",     # 墨色批注
    2: "圈点",     # 圈点标记
    3: "划线",     # 划线标记
    4: "批注区域"   # 批注区域框
}


class AnnotationExtractionService:
    """
    批校痕迹提取服务

    整合检测、分类、OCR、对齐全流程
    """

    def __init__(self, model_path: str = None, config: dict = None):
        """
        初始化批校提取服务

        Args:
            model_path: Faster R-CNN模型权重路径（可选）
            config: 额外配置参数
        """
        self.config = config or {}

        # 延迟加载各组件
        self.detector = None
        self.classifier = None
        self.ocr = None
        self.aligner = None

        self.model_path = model_path
        self.min_confidence = self.config.get("min_confidence", 0.5)

        logger.info("AnnotationExtractionService初始化完成")

    def _get_detector(self) -> AnnotationDetector:
        """延迟加载检测器"""
        if self.detector is None:
            logger.info("正在加载批注检测模型...")
            self.detector = AnnotationDetector(model_path=self.model_path)
        return self.detector

    def _get_classifier(self) -> AnnotationTypeClassifier:
        """延迟加载分类器"""
        if self.classifier is None:
            self.classifier = AnnotationTypeClassifier()
        return self.classifier

    def _get_ocr(self) -> AnnotationOCR:
        """延迟加载OCR"""
        if self.ocr is None:
            logger.info("正在初始化批注OCR...")
            self.ocr = AnnotationOCR()
        return self.ocr

    def _get_aligner(self) -> AnnotationAligner:
        """延迟加载对齐器"""
        if self.aligner is None:
            self.aligner = AnnotationAligner()
        return self.aligner

    def process(self, image_path: str,
                text_blocks: List[Dict] = None,
                perform_ocr: bool = True) -> Dict:
        """
        端到端处理古籍页面

        Args:
            image_path: 古籍页面图像路径
            text_blocks: 正文章节列表，每项包含bbox和text（可选）
            perform_ocr: 是否执行OCR识别

        Returns:
            {
                "image_path": "...",
                "annotations": [
                    {
                        "bbox": (x1,y1,x2,y2),
                        "type": "朱批",
                        "type_id": 0,
                        "confidence": 0.95,
                        "text": "此处有误",
                        "aligned_text": "原文对应文字",
                        "position_type": "页眉批注"
                    },
                    ...
                ],
                "statistics": {
                    "total": 10,
                    "by_type": {"朱批": 3, "墨批": 5, "圈点": 1, "划线": 1}
                }
            }
        """
        logger.info(f"开始处理古籍页面: {image_path}")

        result = {
            "image_path": image_path,
            "annotations": [],
            "statistics": {}
        }

        # 解析图像路径 - 支持相对路径和绝对路径
        import os
        from pathlib import Path
        original_image_path = image_path
        if not os.path.isabs(image_path):
            # 相对路径，解析为相对于项目根目录
            project_root = Path(__file__).parent.parent.parent
            image_path = str(project_root / image_path)
            logger.info(f"Resolved image path: {image_path}")

        # Step 1: 检测批注
        logger.info("Step 1: 检测批注区域...")
        detector = self._get_detector()
        detections = detector.detect(image_path)

        logger.info(f"  检测到 {len(detections)} 个候选区域")

        # 过滤低置信度
        detections = [d for d in detections if d.get("confidence", 0) >= self.min_confidence]
        logger.info(f"  过滤后剩余 {len(detections)} 个（置信度>={self.min_confidence}）")

        # Step 2: 分类批注类型
        logger.info("Step 2: 分类批注类型...")
        from app.utils import imread
        image = imread(image_path)
        if image is None:
            logger.error(f"无法读取图像: {image_path}")
            # 尝试使用原始路径
            if os.path.isabs(original_image_path):
                image = imread(original_image_path)
        if image is None:
            logger.error("无法读取图像，跳过分类步骤")
        else:
            logger.info(f"图像已加载: {image.shape}")
            classifier = self._get_classifier()

            for det in detections:
                try:
                    bbox = det.get("bbox", (0, 0, 100, 100))
                    x, y, w, h = [int(v) for v in bbox]
                    x1, y1, x2, y2 = x, y, x + w, y + h
                    # 确保坐标在图像范围内
                    x1 = max(0, min(x1, image.shape[1] - 1))
                    y1 = max(0, min(y1, image.shape[0] - 1))
                    x2 = max(x1 + 1, min(x2, image.shape[1]))
                    y2 = max(y1 + 1, min(y2, image.shape[0]))
                    region = image[y1:y2, x1:x2] if y2 > y1 and x2 > x1 else None

                    # 使用颜色和形状分类
                    type_name, type_confidence = classifier.classify(
                        region, image, det.get("confidence", 0.5)
                    )

                    det["type"] = type_name
                    det["type_confidence"] = type_confidence
                except Exception as e:
                    logger.warning(f"分类失败 for detection: {e}")
                    det["type"] = "unknown"
                    det["type_confidence"] = 0.0

        # Step 3: OCR识别
        if perform_ocr:
            logger.info("Step 3: 识别批注文字...")
            try:
                ocr = self._get_ocr()

                for det in detections:
                    bbox = det.get("bbox", (0, 0, 100, 100))
                    x1, y1, x2, y2 = [int(v) for v in bbox]

                    # 扩大bbox以包含完整批注
                    padding = 5
                    padded_bbox = (
                        max(0, x1 - padding),
                        max(0, y1 - padding),
                        min(image.shape[1] if image is not None else 1000, x2 + padding),
                        min(image.shape[0] if image is not None else 1000, y2 + padding)
                    )

                    # OCR识别
                    ocr_results = ocr.recognize_text(image, [padded_bbox])
                    if ocr_results:
                        det["text"] = ocr_results[0].get("text", "")
                        det["ocr_confidence"] = ocr_results[0].get("confidence", 0)
                    else:
                        det["text"] = ""
                        det["ocr_confidence"] = 0.0

            except Exception as e:
                logger.warning(f"OCR识别失败: {e}")

        # Step 4: 与正文对齐
        if text_blocks:
            logger.info("Step 4: 与正文章节对齐...")
            aligner = self._get_aligner()

            for det in detections:
                bbox = det.get("bbox", (0, 0, 100, 100))
                aligned = aligner.align_annotation_to_text(bbox, None, text_blocks)

                if aligned:
                    det["aligned_text"] = aligned.get("text", "")
                    det["aligned_block_index"] = aligned.get("block_index", -1)
                else:
                    det["aligned_text"] = ""
                    det["aligned_block_index"] = -1

                # 推断位置类型
                det["position_type"] = aligner.infer_annotation_type_by_position(
                    bbox, None, aligned
                )

        result["annotations"] = detections

        # Step 5: 统计
        stats = {"total": len(detections), "by_type": {}}
        for det in detections:
            type_name = det.get("type", "未知")
            stats["by_type"][type_name] = stats["by_type"].get(type_name, 0) + 1
        result["statistics"] = stats

        logger.info(f"批校提取完成: 共 {stats['total']} 个批注")

        return result

    def detect_only(self, image_path: str) -> Dict:
        """
        仅检测批注（不进行OCR和对齐）

        Args:
            image_path: 古籍页面图像路径

        Returns:
            检测结果
        """
        return self.process(image_path, text_blocks=None, perform_ocr=False)

    def visualize_result(self, image_path: str, result: Dict,
                        output_path: str = None) -> np.ndarray:
        """
        可视化批注检测结果

        Args:
            image_path: 原图路径
            result: process()返回的结果
            output_path: 输出路径（可选）

        Returns:
            可视化图像
        """
        from app.utils import imread

        image = imread(image_path)
        if image is None:
            raise ValueError(f"无法读取图像: {image_path}")

        # 颜色映射
        type_colors = {
            "朱批": (0, 0, 255),       # 红色 BGR
            "墨批": (128, 128, 128),   # 灰色
            "圈点": (0, 255, 0),       # 绿色
            "划线": (255, 0, 0),       # 蓝色
            "批注区域": (0, 255, 255), # 黄色
        }

        for ann in result.get("annotations", []):
            bbox = ann.get("bbox", (0, 0, 100, 100))
            x1, y1, x2, y2 = [int(v) for v in bbox]
            type_name = ann.get("type", "批注")
            confidence = ann.get("confidence", 0)
            text = ann.get("text", "")

            color = type_colors.get(type_name, (255, 255, 255))

            # 绘制边界框
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)

            # 绘制标签
            label = f"{type_name} {confidence:.2f}"
            if text:
                label += f": {text[:15]}"

            cv2.putText(image, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        if output_path:
            cv2.imwrite(output_path, image)
            logger.info(f"可视化结果已保存: {output_path}")

        return image


# 全局单例
_annotation_service: Optional[AnnotationExtractionService] = None


def get_annotation_service(model_path: str = None) -> AnnotationExtractionService:
    """获取批校提取服务单例"""
    global _annotation_service
    if _annotation_service is None:
        _annotation_service = AnnotationExtractionService(model_path=model_path)
    return _annotation_service
