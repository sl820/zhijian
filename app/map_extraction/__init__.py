"""
舆图信息提取模块 - 古地图要素识别与矢量化

提供古籍舆图（古地图）的信息提取功能：
- U-Net语义分割识别地图要素
- 地理要素矢量化
- 地图标注OCR识别
- 地理坐标映射

主要组件:
- AncientMapUNet: U-Net深度学习分割模型
- MapSegmenter: 图像分割推理管道
- GeographicVectorizer: 要素矢量化
- MapLabelOCR: 地图标注OCR识别
- GeoCoordinateMapper: 地理坐标映射
- MapExtractionService: 服务整合
"""

from .unet_model import AncientMapUNet
from .segmenter import MapSegmenter, CLASS_COLORS
from .vectorizer import GeographicVectorizer
from .label_ocr import MapLabelOCR
from .geo_mapper import GeoCoordinateMapper

__all__ = [
    "AncientMapUNet",
    "MapSegmenter",
    "CLASS_COLORS",
    "GeographicVectorizer",
    "MapLabelOCR",
    "GeoCoordinateMapper",
]
