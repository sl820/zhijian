"""
舆图信息提取服务 - 整合地图分割、矢量化、OCR和坐标映射

提供古籍舆图的端到端信息提取流程：
1. 加载古地图图像
2. U-Net语义分割识别地理要素
3. 要素矢量化（GeoJSON格式）
4. OCR识别地图标注文字
5. 地理坐标映射（可选）
"""

import logging
from typing import Dict, List, Optional, Tuple
import numpy as np

from .segmenter import MapSegmenter, CLASS_COLORS
from .vectorizer import GeographicVectorizer
from .label_ocr import MapLabelOCR
from .geo_mapper import GeoCoordinateMapper

logger = logging.getLogger(__name__)


# 要素类型名称映射
ELEMENT_TYPES = {
    0: "背景",
    1: "河流",
    2: "山脉",
    3: "城市",
    4: "边界线",
    5: "文字标注"
}


class MapExtractionService:
    """
    舆图信息提取服务

    整合分割、矢量化、OCR和坐标映射全流程
    """

    def __init__(self, model_path: str = None, config: dict = None):
        """
        初始化舆图提取服务

        Args:
            model_path: U-Net模型权重路径（可选）
            config: 额外配置参数
        """
        self.config = config or {}

        # 延迟加载各组件
        self.segmenter = None
        self.vectorizer = None
        self.label_ocr = None
        self.geo_mapper = None

        self.model_path = model_path
        self.element_min_area = self.config.get("element_min_area", 100)
        self.text_min_area = self.config.get("text_min_area", 50)

        logger.info("MapExtractionService初始化完成")

    def _get_segmenter(self) -> MapSegmenter:
        """延迟加载分割器"""
        if self.segmenter is None:
            logger.info("正在加载分割模型...")
            self.segmenter = MapSegmenter(model_path=self.model_path)
        return self.segmenter

    def _get_vectorizer(self) -> GeographicVectorizer:
        """延迟加载矢量化器"""
        if self.vectorizer is None:
            self.vectorizer = GeographicVectorizer()
        return self.vectorizer

    def _get_label_ocr(self) -> MapLabelOCR:
        """延迟加载OCR"""
        if self.label_ocr is None:
            logger.info("正在初始化地图标注OCR...")
            self.label_ocr = MapLabelOCR()
        return self.label_ocr

    def _get_geo_mapper(self) -> GeoCoordinateMapper:
        """延迟加载坐标映射器"""
        if self.geo_mapper is None:
            self.geo_mapper = GeoCoordinateMapper()
        return self.geo_mapper

    def process(self, image_path: str,
                perform_ocr: bool = True,
                georeference: bool = False,
                reference_points: List[Tuple] = None) -> Dict:
        """
        端到端处理舆图图像

        Args:
            image_path: 舆图图像路径
            perform_ocr: 是否执行OCR识别标注文字
            georeference: 是否进行地理坐标映射
            reference_points: 参考点列表 [(pixel_x, pixel_y, lon, lat), ...]

        Returns:
            处理结果字典
            {
                "image_path": "...",
                "elements": {
                    "rivers": [...],    # 河流要素列表
                    "mountains": [...], # 山脉要素列表
                    "cities": [...],    # 城市要素列表
                    "boundaries": [...],# 边界线要素列表
                },
                "text_labels": [...],    # OCR识别结果
                "geojson": {...},        # GeoJSON格式的矢量数据
                "statistics": {
                    "total_elements": 100,
                    "by_type": {...}
                }
            }
        """
        logger.info(f"开始处理舆图: {image_path}")

        result = {
            "image_path": image_path,
            "elements": {},
            "text_labels": [],
            "geojson": None,
            "statistics": {}
        }

        # Step 1: 语义分割
        logger.info("执行语义分割...")
        segmenter = self._get_segmenter()
        seg_result = segmenter.segment(image_path)
        mask = seg_result["mask"]
        probabilities = seg_result.get("probabilities")

        logger.info(f"分割完成，检测到要素类型: {np.unique(mask)}")

        # Step 2: 提取地理要素
        logger.info("提取地理要素...")
        vectorizer = self._get_vectorizer()

        elements = {}
        for class_id, class_name in [(1, "rivers"), (2, "mountains"), (3, "cities"), (4, "boundaries")]:
            class_mask = (mask == class_id).astype(np.uint8)
            vectors = vectorizer.raster_to_vectors(class_mask, class_names={class_id: class_name})

            # 过滤太小区域
            filtered = []
            for poly in vectors.get(class_name, []):
                area = vectorizer.compute_polygon_area(poly)
                if area >= self.element_min_area:
                    filtered.append({
                        "polygon": poly.tolist() if hasattr(poly, 'tolist') else poly,
                        "area_pixels": float(area),
                        "type": ELEMENT_TYPES[class_id]
                    })

            elements[class_name] = filtered
            logger.info(f"  {class_name}: {len(filtered)} 个要素")

        result["elements"] = elements

        # Step 3: OCR识别标注文字
        if perform_ocr:
            logger.info("识别地图标注文字...")
            try:
                label_ocr = self._get_label_ocr()

                # 读取原图
                from app.utils import imread
                image = imread(image_path)
                if image is not None:
                    # 检测文字区域
                    text_mask = (mask == 5).astype(np.uint8)
                    text_regions = label_ocr.detect_text_regions(text_mask, min_area=self.text_min_area)

                    # OCR识别
                    labels = label_ocr.recognize_labels(image, text_regions)
                    result["text_labels"] = labels
                    logger.info(f"  识别到 {len(labels)} 个标注")
            except Exception as e:
                logger.warning(f"OCR识别失败: {e}")
                result["text_labels"] = []

        # Step 4: 地理坐标映射
        if georeference and reference_points:
            logger.info("执行地理坐标映射...")
            try:
                geo_mapper = self._get_geo_mapper()

                pixel_coords = [(p[0], p[1]) for p in reference_points]
                geo_coords = [(p[2], p[3]) for p in reference_points]

                geo_mapper.set_reference_points(pixel_coords, geo_coords)

                # 转换各要素的坐标
                for class_name, feature_list in elements.items():
                    for feature in feature_list:
                        poly = feature.get("polygon", [])
                        if isinstance(poly, list) and len(poly) > 0:
                            geo_poly = []
                            for point in poly:
                                if len(point) >= 2:
                                    lon, lat = geo_mapper.pixel_to_geo(point[0], point[1])
                                    geo_poly.append([lon, lat])
                            feature["geo_polygon"] = geo_poly

                # 生成GeoJSON
                result["geojson"] = geo_mapper.create_geojson(elements, metadata={
                    "source": image_path,
                    "type": "ancient_map"
                })
                logger.info("GeoJSON生成完成")
            except Exception as e:
                logger.warning(f"地理坐标映射失败: {e}")

        # Step 5: 统计信息
        stats = {"total_elements": 0, "by_type": {}}
        for class_name, feature_list in elements.items():
            count = len(feature_list)
            stats["total_elements"] += count
            stats["by_type"][class_name] = count
        stats["by_type"]["text_labels"] = len(result.get("text_labels", []))
        result["statistics"] = stats

        logger.info(f"舆图处理完成: 共 {stats['total_elements']} 个要素")

        return result

    def extract_elements_only(self, image_path: str) -> Dict:
        """
        仅提取地理要素（不进行OCR和坐标映射）

        Args:
            image_path: 舆图图像路径

        Returns:
            要素提取结果
        """
        return self.process(image_path, perform_ocr=False, georeference=False)

    def visualize_result(self, image_path: str, result: Dict,
                        output_path: str = None) -> np.ndarray:
        """
        可视化提取结果

        Args:
            image_path: 原图路径
            result: process()返回的结果
            output_path: 输出路径（可选）

        Returns:
            可视化图像（numpy数组）
        """
        import cv2

        segmenter = self._get_segmenter()
        seg_result = segmenter.segment(image_path)
        mask = seg_result["mask"]

        # 读取原图
        from app.utils import imread
        image = imread(image_path)
        if image is None:
            raise ValueError(f"无法读取图像: {image_path}")

        # 生成彩色分割图
        vis_image = segmenter.visualize_segmentation(image, mask)

        # 绘制文字标注
        for label in result.get("text_labels", []):
            bbox = label.get("bbox")
            text = label.get("text", "")
            if bbox and text:
                x, y, w, h = bbox
                cv2.rectangle(vis_image, (x, y), (x + w, y + h), (0, 255, 255), 2)
                cv2.putText(vis_image, text[:10], (x, y - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        # 绘制要素边界
        for class_name, features in result.get("elements", {}).items():
            color = CLASS_COLORS.get(class_name, (255, 255, 255))[:3]
            for feature in features:
                poly = feature.get("polygon", [])
                if isinstance(poly, list) and len(poly) > 2:
                    pts = np.array([[p[0], p[1]] for p in poly], dtype=np.int32)
                    cv2.polylines(vis_image, [pts], isClosed=True, color=color, thickness=2)

        if output_path:
            cv2.imwrite(output_path, vis_image)
            logger.info(f"可视化结果已保存: {output_path}")

        return vis_image


# 全局单例
_map_service: Optional[MapExtractionService] = None


def get_map_service(model_path: str = None) -> MapExtractionService:
    """获取舆图提取服务单例"""
    global _map_service
    if _map_service is None:
        _map_service = MapExtractionService(model_path=model_path)
    return _map_service
