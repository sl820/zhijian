"""
通用工具函数
"""
import numpy as np
import cv2
from PIL import Image
import logging

logger = logging.getLogger(__name__)


def imread(path: str, grayscale: bool = False) -> np.ndarray:
    """
    跨平台图像读取，支持中文路径。

    Windows上cv2.imread()无法处理包含中文的路径，
    此函数使用PIL作为回退方案。

    Args:
        path: 图像文件路径
        grayscale: 是否以灰度模式读取

    Returns:
        np.ndarray: OpenCV格式图像（BGR），读取失败返回None
    """
    # 尝试直接用cv2读取（非中文路径时优先使用，更快）
    try:
        if grayscale:
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        else:
            img = cv2.imread(path)
        if img is not None:
            return img
    except Exception:
        pass

    # 回退：使用PIL读取中文路径
    try:
        pil_img = Image.open(path)
        if grayscale:
            arr = np.array(pil_img.convert('L'))
        else:
            rgb = pil_img.convert('RGB')
            arr = np.array(rgb)
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        logger.debug(f"使用PIL读取图像: {path}")
        return arr
    except Exception as e:
        logger.warning(f"图像读取失败 {path}: {e}")
        return None


def imwrite(path: str, img: np.ndarray) -> bool:
    """
    跨平台图像写入，支持中文路径。

    Args:
        path: 输出文件路径
        img: OpenCV格式图像

    Returns:
        bool: 写入是否成功
    """
    try:
        # 尝试直接用cv2写入
        result = cv2.imwrite(path, img)
        if result:
            return True
    except Exception:
        pass

    # 回退：使用PIL写入
    try:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        pil_img.save(path)
        return True
    except Exception as e:
        logger.warning(f"图像写入失败 {path}: {e}")
        return False
