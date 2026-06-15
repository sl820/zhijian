"""OCR Provider 适配器架构

AliyunOCRProvider 是云端 API，需要 ALIYUN_OCR_APP_CODE / ALIYUN_ACCESS_KEY
环境变量才能实例化。缺少时仅导出本地引擎，避免 import 阶段报错。
"""
import logging
import os

from .base import BaseOCRProvider
from .easyocr import EasyOCRProvider
from .paddleocr import PaddleOCRProvider

# RapidOCR（ONNX 后端，推荐默认：质量好 + 体积小 + 跨平台）
try:
    from .rapidocr import RapidOCRProvider
    _RAPIDOCR_OK = True
except Exception as e:
    logger.warning(f"RapidOCR 不可用: {e}")
    RapidOCRProvider = None
    _RAPIDOCR_OK = False

logger = logging.getLogger(__name__)

ALIYUN_AVAILABLE = bool(
    os.environ.get("ALIYUN_OCR_APP_CODE")
    or (os.environ.get("ALIYUN_ACCESS_KEY_ID") and os.environ.get("ALIYUN_ACCESS_KEY_SECRET"))
)

if ALIYUN_AVAILABLE:
    try:
        from .aliyun import AliyunOCRProvider
        logger.info("AliyunOCRProvider 已加载（云端 OCR 可用）")
    except Exception as e:
        logger.warning(f"AliyunOCRProvider 加载失败: {e}")
        AliyunOCRProvider = None
else:
    AliyunOCRProvider = None
    logger.info("AliyunOCRProvider 未配置（需 ALIYUN_OCR_APP_CODE 或 ALIYUN_ACCESS_KEY_*）")


def get_default_provider() -> str:
    """按可用性返回最佳默认 provider"""
    if RapidOCRProvider is not None:
        return "rapidocr"
    if PaddleOCRProvider is not None:
        return "paddleocr"
    if EasyOCRProvider is not None:
        return "easyocr"
    return "easyocr"


def provider_availability() -> dict:
    """返回每个 provider 的可用性状态（前端展示用）"""
    return {
        "easyocr": EasyOCRProvider is not None,
        "paddleocr": PaddleOCRProvider is not None,
        "rapidocr": RapidOCRProvider is not None,
        "aliyun": ALIYUN_AVAILABLE and AliyunOCRProvider is not None,
    }


DEFAULT_PROVIDER = get_default_provider()

__all__ = [
    "BaseOCRProvider",
    "EasyOCRProvider",
    "PaddleOCRProvider",
    "RapidOCRProvider",
    "AliyunOCRProvider",
    "ALIYUN_AVAILABLE",
    "DEFAULT_PROVIDER",
    "get_default_provider",
    "provider_availability",
]
