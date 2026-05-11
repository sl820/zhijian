import pytest
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ocr.variant_map import VARIANT_CHAR_MAP, TABOO_RULES, normalize_variant_text
from app.ocr.preprocess import ImagePreprocessor


class TestVariantMap:
    """异体字映射表测试"""

    def test_variant_map_not_empty(self):
        assert len(VARIANT_CHAR_MAP) > 0

    def test_吴_异体字映射(self):
        assert "吳" in VARIANT_CHAR_MAP
        assert "吴" in VARIANT_CHAR_MAP["吳"]
        assert "呉" in VARIANT_CHAR_MAP["吳"]

    def test_考_异体字映射(self):
        assert "考" in VARIANT_CHAR_MAP
        assert "攷" in VARIANT_CHAR_MAP["考"]

    def test_normalize_吴_to_标准(self):
        text = "吳氏居焉"
        normalized = normalize_variant_text(text)
        assert "吳" not in normalized
        assert "吴" in normalized

    def test_normalize_攷_to_考(self):
        text = "攷古文字"
        normalized = normalize_variant_text(text)
        assert "考" in normalized

    def test_taboo_rules_康熙(self):
        assert "qing" in TABOO_RULES
        assert "康熙" in TABOO_RULES["qing"]["皇帝"]
        assert TABOO_RULES["qing"]["皇帝"]["康熙"]["玄"] == "元"

    def test_taboo_rules_孔子讳(self):
        assert "confucius" in TABOO_RULES
        assert TABOO_RULES["confucius"]["孔子"]["丘"] == "邱"


class TestImagePreprocessor:
    """图像预处理器测试"""

    def setup_method(self):
        self.preprocessor = ImagePreprocessor()

    def test_preprocessor_init(self):
        assert self.preprocessor.max_dimension == 4096

    def test_load_image_creates_rgb(self):
        import cv2
        # Create a test image
        test_img = np.ones((100, 200, 3), dtype=np.uint8) * 255
        # Simulate loading by just returning it
        loaded = self.preprocessor.load_image_from_array(test_img)
        assert loaded.shape == (100, 200, 3)

    def test_resize_large_image(self):
        large_image = np.ones((5000, 3000), dtype=np.uint8) * 255
        resized = self.preprocessor._resize_if_needed(large_image)
        assert max(resized.shape[:2]) <= 4096


class TestOCRProcessor:
    """OCR处理器测试"""

    def test_processor_init(self):
        from app.ocr import OCRProcessor
        processor = OCRProcessor()
        assert processor.preprocessor is not None
        assert processor.recognizer is not None

    def test_dynasty_config(self):
        from app.ocr import OCRProcessor
        processor = OCRProcessor(default_dynasty="qing")
        assert processor.default_dynasty == "qing"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
