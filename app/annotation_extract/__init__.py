"""
批校痕迹提取模块 - 古籍手写批注检测与识别

功能：识别古籍上的手写批注、校对痕迹、圈点标记，并提取其内容

主要组件:
- AnnotationDetector: Faster R-CNN目标检测
- AnnotationTypeClassifier: 批注类型分类
- AnnotationOCR: 批注文字OCR识别
- AnnotationAligner: 批注与正文对齐
- AnnotationExtractionService: 服务整合
"""

from .faster_rcnn_model import AnnotationDetector, ANNOTATION_CLASSES, create_model
from .detector import AnnotationDetector as HighLevelDetector
from .ocr import AnnotationOCR
from .aligner import AnnotationAligner

__all__ = [
    "AnnotationDetector",
    "HighLevelDetector",
    "ANNOTATION_CLASSES",
    "create_model",
    "AnnotationOCR",
    "AnnotationAligner",
]
