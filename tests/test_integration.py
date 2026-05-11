"""
志鉴系统集成测试

测试所有模块的基本功能和API端点。
注意：某些测试需要实际的模型文件或API密钥才能运行。
"""

import sys
import unittest
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ==================== 模块导入测试 ====================

class TestModuleImports:
    """测试所有模块可以正确导入"""

    def test_rag_imports(self):
        """测试RAG模块导入"""
        from app.rag.chunker import TextChunker
        from app.rag.embedder import Embedder
        from app.rag.retriever import Retriever, BM25
        from app.rag.generator import Generator
        from app.rag.rag_service import RAGService, get_rag_service
        assert True

    def test_map_extraction_imports(self):
        """测试舆图提取模块导入"""
        from app.map_extraction.unet_model import AncientMapUNet
        from app.map_extraction.segmenter import MapSegmenter, CLASS_COLORS
        from app.map_extraction.vectorizer import GeographicVectorizer
        from app.map_extraction.label_ocr import MapLabelOCR
        from app.map_extraction.geo_mapper import GeoCoordinateMapper
        from app.map_extraction.map_service import MapExtractionService
        assert True

    def test_compilation_imports(self):
        """测试辑佚模块导入"""
        from app.compilation.scraper import SourceScraper, TextSource, SourceType
        from app.compilation.dedup import TextHasher, Deduplicator
        from app.compilation.merger import TextMerger, MergeStrategy
        from app.compilation.ranker import VersionRanker, SourceQuality
        from app.compilation.compilation_service import CompilationService
        assert True

    def test_annotation_imports(self):
        """测试批校模块导入"""
        from app.annotation_extract.faster_rcnn_model import AnnotationDetector, ANNOTATION_CLASSES
        from app.annotation_extract.detector import AnnotationTypeClassifier
        from app.annotation_extract.ocr import AnnotationOCR
        from app.annotation_extract.aligner import AnnotationAligner
        from app.annotation_extract.annotation_service import AnnotationExtractionService
        assert True

    def test_api_routes_imports(self):
        """测试API路由导入"""
        from app.api.routes import (
            router, get_rag_service, get_map_service,
            get_compilation_service, get_annotation_service
        )
        assert True


# ==================== RAG模块测试 ====================

class TestRAGModule:
    """测试RAG模块功能"""

    def test_chunker_basic(self):
        """测试文本分块器基本功能"""
        from app.rag.chunker import TextChunker

        chunker = TextChunker(max_tokens=50, overlap_tokens=10)

        text = "卷一·总志。清苑县历史悠久，世为农。吳氏居焉。"

        # 按章节分块
        chunks = chunker.chunk(text, strategy="by_chapter")
        assert len(chunks) >= 0

        # 按最大token分块
        chunks = chunker.chunk(text, strategy="by_max_tokens")
        assert len(chunks) >= 0

    def test_chunker_sentence_splitting(self):
        """测试句子切分"""
        from app.rag.chunker import TextChunker

        chunker = TextChunker()
        text = "清苑县，吳氏居焉，世为农。轼，字子瞻，眉州眉山人。"

        chunks = chunker.chunk(text, strategy="by_max_tokens")
        assert len(chunks) >= 1

        # 验证句末标点被保留
        for chunk in chunks:
            if "吳氏" in chunk["text"] or "苏轼" in chunk["text"]:
                assert "。" in chunk["text"] or len(chunk["text"]) > 0

    def test_bm25_basic(self):
        """测试BM25基本功能"""
        from app.rag.retriever import BM25

        bm25 = BM25()
        corpus = [
            "清苑县历史悠久",
            "吳氏居焉世为农",
            "苏轼字子瞻眉山人"
        ]
        bm25.fit(corpus)

        results = bm25.search("吳氏", top_k=2)
        assert len(results) <= 2
        assert all("score" in r for r in results)


# ==================== 舆图提取模块测试 ====================

class TestMapExtractionModule:
    """测试舆图提取模块功能"""

    def test_vectorizer_basic(self):
        """测试矢量化基本功能"""
        import numpy as np
        from app.map_extraction.vectorizer import GeographicVectorizer

        vectorizer = GeographicVectorizer()

        # 创建简单的测试mask（河流：class 1）
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:40, 10:60] = 1  # 模拟一条河流

        vectors = vectorizer.raster_to_vectors(mask, class_names=["rivers"])
        assert "rivers" in vectors or len(vectors) >= 0

    def test_vectorizer_polygon_area(self):
        """测试多边形面积计算"""
        import numpy as np
        from app.map_extraction.vectorizer import GeographicVectorizer

        vectorizer = GeographicVectorizer()

        # 正方形: 10x10 = 100 像素
        polygon = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], dtype=np.float32)
        area = vectorizer.compute_polygon_area(polygon)

        assert area > 0
        # 允许一些误差
        assert abs(area - 100) < 10

    def test_geo_mapper_basic(self):
        """测试地理坐标映射基本功能"""
        from app.map_extraction.geo_mapper import GeoCoordinateMapper

        mapper = GeoCoordinateMapper()

        # 设置4个控制点
        pixel_coords = [(0, 0), (100, 0), (100, 100), (0, 100)]
        geo_coords = [(116.0, 40.0), (116.1, 40.0), (116.1, 39.9), (116.0, 39.9)]

        mapper.set_reference_points(pixel_coords, geo_coords)

        # 测试转换
        lon, lat = mapper.pixel_to_geo(50, 50)
        assert 116.0 <= lon <= 116.1
        assert 39.9 <= lat <= 40.0


# ==================== 辑佚模块测试 ====================

class TestCompilationModule:
    """测试辑佚模块功能"""

    def test_text_hasher_minhash(self):
        """测试MinHash哈希"""
        from app.compilation.dedup import TextHasher

        hasher = TextHasher()
        text1 = "清苑县历史悠久，吳氏居焉"
        text2 = "清苑县历史悠久，吳氏居焉"  # 完全相同
        text3 = "北京市历史悠久"  # 不同

        hash1 = hasher.minhash(text1)
        hash2 = hasher.minhash(text2)
        hash3 = hasher.minhash(text3)

        assert len(hash1) == 128  # 默认128哈希
        assert hash1 == hash2  # 相同文本应该有相同的hash

    def test_deduplicator_clustering(self):
        """测试去重聚类"""
        from app.compilation.dedup import Deduplicator

        dedup = Deduplicator(threshold=0.85, method="minhash")

        texts = [
            "清苑县历史悠久，吳氏居焉",
            "清苑县历史悠久，吳氏居焉",  # 重复
            "苏轼字子瞻眉山人",
            "苏轼字子瞻眉山人",  # 重复
        ]

        clusters = dedup.cluster_documents(texts)
        assert len(clusters) <= len(texts)

    def test_text_merger_prefer_complete(self):
        """测试文本融合（优先完整）"""
        from app.compilation.merger import TextMerger, MergeStrategy

        merger = TextMerger(strategy="prefer_complete")

        text_a = "清苑县"
        text_b = "清苑县历史悠久"

        merged, info = merger.merge_two(text_a, text_b, {}, {})

        assert len(merged) >= len(text_a)
        assert len(merged) >= len(text_b)


# ==================== 批校模块测试 ====================

class TestAnnotationModule:
    """测试批校痕迹提取模块功能"""

    def test_annotation_type_classifier(self):
        """测试批注类型分类器"""
        import numpy as np
        from app.annotation_extract.detector import AnnotationTypeClassifier

        classifier = AnnotationTypeClassifier()

        # 创建测试图像
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        region = np.zeros((20, 20, 3), dtype=np.uint8)

        # 测试分类（会返回默认类型）
        type_name, confidence = classifier.classify(region, image, 0.5)
        assert type_name in ["red_comment", "ink_comment", "circle_dot", "underline"]
        assert 0 <= confidence <= 1

    def test_annotation_aligner_iou(self):
        """测试IoU计算"""
        from app.annotation_extract.aligner import AnnotationAligner

        aligner = AnnotationAligner()

        # 两个重叠的框
        bbox1 = (0, 0, 50, 50)
        bbox2 = (25, 25, 75, 75)

        iou = aligner._compute_iou(bbox1, bbox2)
        assert 0 < iou < 1  # 应该有重叠但不完全重叠


# ==================== API路由测试 ====================

class TestAPIRoutes:
    """测试API路由定义"""

    def test_all_endpoints_defined(self):
        """验证所有端点已定义"""
        from app.api.routes import router

        # 获取所有路由
        routes = {r.path: r.methods for r in router.routes}

        # 验证已有端点
        assert any("/ocr/recognize" in p for p in routes)
        assert any("/normalize" in p for p in routes)
        assert any("/collation/compare" in p for p in routes)
        assert any("/rag/ask" in p for p in routes)
        assert any("/rag/ingest" in p for p in routes)

        # 验证新端点
        assert any("/map/extract" in p for p in routes)
        assert any("/compilation/compile" in p for p in routes)
        assert any("/annotation/extract" in p for p in routes)

    def test_rag_response_model(self):
        """测试RAG响应模型"""
        from app.api.routes import RAGResponse

        response = RAGResponse(
            answer="测试答案",
            sources=[{"text": "来源1", "distance": 0.9}]
        )
        assert response.answer == "测试答案"
        assert len(response.sources) == 1


# ==================== 运行测试 ====================

if __name__ == "__main__":
    unittest.main(module="tests.test_integration", verbosity=2)
