"""
Aliyun OCR Provider - 阿里云文字识别
支持通用文字识别、古籍竖排识别等
"""
import os
import base64
import json
import logging
from typing import List, Dict, Optional
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import numpy as np
import cv2
from .base import BaseOCRProvider

logger = logging.getLogger(__name__)


class AliyunOCRProvider(BaseOCRProvider):
    """阿里云 OCR 文字识别提供者"""

    def __init__(
        self,
        config: dict = None,
        app_code: str = None,
        access_key_id: str = None,
        access_key_secret: str = None,
    ):
        """
        初始化阿里云 OCR Provider

        Args:
            config: 配置字典
            app_code: AppCode (API 网关认证)
            access_key_id: 访问密钥 ID
            access_key_secret: 访问密钥 Secret
        """
        super().__init__(config)

        # 优先使用传入参数，其次 config，再次环境变量
        self.app_code = (
            app_code
            or self.config.get("app_code")
            or os.environ.get("ALIYUN_OCR_APP_CODE", "")
        )
        self.access_key_id = (
            access_key_id
            or self.config.get("access_key_id")
            or os.environ.get("ALIYUN_ACCESS_KEY_ID", "")
        )
        self.access_key_secret = (
            access_key_secret
            or self.config.get("access_key_secret")
            or os.environ.get("ALIYUN_ACCESS_KEY_SECRET", "")
        )

        # API 配置
        self.region = self.config.get("region", "cn-shanghai")
        self.scene = self.config.get("scene", "general")  # general, handwriting, ancient
        self.use_ancient_mode = self.config.get("use_ancient_mode", False)

        # 端点
        self.endpoint = self.config.get(
            "endpoint",
            f"https://ocrapi-{self.region}.aliyuncs.com"
        )

        logger.info(
            f"AliyunOCRProvider initialized: region={self.region}, "
            f"scene={self.scene}, ancient_mode={self.use_ancient_mode}, "
            f"has_app_code={bool(self.app_code)}"
        )

    def _prepare_image(self, image: np.ndarray) -> str:
        """
        将 numpy 图像转为 base64 字符串

        Args:
            image: RGB 格式图像

        Returns:
            base64 编码的图像字符串
        """
        # 转为 BGR 再编码
        if len(image.shape) == 3 and image.shape[2] == 3:
            img_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        else:
            img_bgr = image

        # 编码为 PNG
        _, buffer = cv2.imencode('.png', img_bgr)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        return img_base64

    def _call_api(self, image_base64: str) -> Optional[Dict]:
        """
        调用阿里云 OCR API

        Args:
            image_base64: base64 编码的图像

        Returns:
            API 响应字典
        """
        # 构建请求
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if self.app_code:
            headers["Authorization"] = f"APPCODE {self.app_code}"

        # 请求体
        body = {
            "image": image_base64,
            "configure": {
                "outputProbability": True,
            }
        }

        # 根据场景设置识别类型
        if self.scene == "handwriting":
            body["configure"]["recognize"] = "handwriting"
        elif self.use_ancient_mode:
            # 阿里云古籍模式
            body["configure"]["recognize"] = "ancient"

        try:
            req = Request(
                self.endpoint,
                data=json.dumps(body).encode('utf-8'),
                headers=headers,
                method="POST"
            )

            with urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result

        except HTTPError as e:
            logger.error(f"阿里云 OCR API HTTP 错误: {e.code} - {e.read().decode('utf-8')}")
            return None
        except URLError as e:
            logger.error(f"阿里云 OCR API URL 错误: {e.reason}")
            return None
        except Exception as e:
            logger.error(f"阿里云 OCR API 调用失败: {e}")
            return None

    def recognize(self, image: np.ndarray) -> List[Dict]:
        """
        识别图片中的文字

        Args:
            image: numpy array, RGB 格式 (H, W, C)

        Returns:
            识别结果列表
        """
        if not self.app_code and not (self.access_key_id and self.access_key_secret):
            logger.error("阿里云 OCR 未配置认证信息")
            return []

        # 转换为 base64
        image_base64 = self._prepare_image(image)

        # 调用 API
        result = self._call_api(image_base64)

        if not result:
            return []

        # 解析响应
        return self._parse_response(result)

    def _parse_response(self, response: Dict) -> List[Dict]:
        """
        解析阿里云 OCR API 响应

        Args:
            response: API 响应字典

        Returns:
            标准化后的识别结果
        """
        results = []

        try:
            # 检查是否成功
            if response.get("success"):
                # 新版 API 格式
                if "data" in response:
                    data = response["data"]
                    if "results" in data:
                        for item in data["results"]:
                            results.append(self._parse_item(item))
                    elif "text" in data:
                        # 单文本结果
                        results.append({
                            "text": data["text"],
                            "confidence": data.get("probability", {}).get("average", 0.9),
                            "bbox": [0, 0, 0, 0],
                            "polygon": [[0, 0], [0, 0], [0, 0], [0, 0]],
                        })
            else:
                # 兼容旧版格式
                error_code = response.get("error_code")
                error_msg = response.get("error_msg", "未知错误")
                logger.warning(f"阿里云 OCR 返回错误: {error_code} - {error_msg}")

        except Exception as e:
            logger.error(f"解析阿里云 OCR 响应失败: {e}")

        return results

    def _parse_item(self, item: Dict) -> Dict:
        """解析单个识别结果项"""
        text = item.get("text", "")
        probability = item.get("probability", {})

        # 边界框
        bbox = item.get("rect", {})
        if bbox:
            x, y, w, h = bbox.get("x", 0), bbox.get("y", 0), bbox.get("width", 0), bbox.get("height", 0)
            bbox_list = [x, y, x + w, y + h]
        else:
            bbox_list = [0, 0, 0, 0]

        # 多边形（如果有）
        polygon = item.get("polygon", [])
        if not polygon:
            polygon = [
                [bbox_list[0], bbox_list[1]],
                [bbox_list[2], bbox_list[1]],
                [bbox_list[2], bbox_list[3]],
                [bbox_list[0], bbox_list[3]],
            ]

        return {
            "text": text,
            "confidence": probability.get("average", probability.get("max", 0.9)),
            "bbox": bbox_list,
            "polygon": polygon,
        }

    def batch_recognize(self, images: List[np.ndarray]) -> List[List[Dict]]:
        """
        批量识别多张图片

        注意：阿里云 API 不支持真正的批量，这里串行调用
        """
        results = []
        for img in images:
            results.append(self.recognize(img))
        return results
