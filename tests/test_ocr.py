"""
OCR 古籍识别端到端测试

测试范围（不依赖真实 EasyOCR 引擎）：
- /ocr/status 结构
- /ocr/variants 返回非空异体字表
- /ocr/samples 列出 kangxi 样本图
- 错误路径：超大文件 / 非法 provider
- /ocr/recognize：mock 一个极小 PNG，确认 400/422 错误处理路径
- 真实 OCR 跑在 @pytest.mark.slow 下

跑全部：`pytest -m "" tests/test_ocr.py`
"""
import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ============================================================
# 状态 / Schema
# ============================================================

def test_ocr_status_structure(client):
    """OCR 状态应返回 enabled 字段 + 状态。"""
    r = client.get("/api/v1/ocr/status")
    assert r.status_code == 200
    body = r.json()
    # OCR 默认关（ZHIJIAN_OCR_ENABLED=False）
    if not body.get("enabled", True):
        assert body["status"] == "disabled"
        assert "message" in body
    else:
        assert body["status"] in ("operational", "error")
        assert "providers" in body
        providers = body["providers"]
        assert providers["easyocr"] is True
        assert providers["paddleocr"] is True
        assert "aliyun" in providers
        assert body["default_provider"] in ("rapidocr", "easyocr", "paddleocr", "aliyun")
        assert body["model_load"] == "lazy"


def test_status_includes_ocr_endpoint(client):
    """status endpoints 含 /ocr 仅当 OCR 启用。"""
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    body = r.json()
    ocr_on = body.get("ocr", {}).get("enabled", False)
    if ocr_on:
        assert "/ocr" in body["endpoints"]
    else:
        assert "/ocr" not in body["endpoints"]
        assert "/kg" in body["endpoints"]
        assert "/rag" in body["endpoints"]


# ============================================================
# 异体字 + 避讳
# ============================================================

def test_variants_returns_nonempty_map(client):
    r = client.get("/api/v1/ocr/variants", params={"limit": 50})
    assert r.status_code == 200
    body = r.json()
    assert body["total_variants"] > 500, f"期望异体字 >500，实际 {body['total_variants']}"
    assert body["total_taboo_rules"] > 0
    assert isinstance(body["sample"], list)
    assert body["sample_size"] == min(50, body["total_variants"])
    # 每个 sample 形如 {standard, variants: [...]}
    first = body["sample"][0]
    assert "standard" in first
    assert "variants" in first
    assert isinstance(first["variants"], list)
    assert len(first["variants"]) >= 1


def test_variants_limit_clamped(client):
    """limit > total 不报错；limit=0 时仍返回 total 但 sample 为空"""
    r = client.get("/api/v1/ocr/variants", params={"limit": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["total_variants"] > 0
    assert body["sample_size"] == 0


# ============================================================
# 样本图
# ============================================================

def test_samples_lists_kangxi_images(client):
    r = client.get("/api/v1/ocr/samples")
    assert r.status_code == 200
    body = r.json()
    assert "samples" in body
    assert "count" in body
    if body["count"] > 0:
        first = body["samples"][0]
        assert "name" in first
        assert first["name"].startswith("kangxi")
        assert first["url"].startswith("/api/v1/ocr/samples/")


def test_sample_file_serves_png(client):
    """如存在 kangxi page_001.png，应能 GET 拿回 bytes"""
    samples = client.get("/api/v1/ocr/samples").json()["samples"]
    if not samples:
        pytest.skip("data/raw/kangxi 暂无样本图")
    sample = samples[0]
    r = client.get(sample["url"])
    assert r.status_code == 200
    # PNG magic: 89 50 4E 47
    assert r.content[:4] == b"\x89PNG", "返回的不是 PNG bytes"


def test_sample_file_rejects_path_traversal(client):
    r = client.get("/api/v1/ocr/samples/..%2F..%2Fconfig.py")
    assert r.status_code in (400, 404)


# ============================================================
# 错误路径
# ============================================================

def test_recognize_missing_file_returns_422_or_503(client):
    """缺文件 → 422 (OCR 启用) 或 503 (OCR 默认关)。"""
    r = client.post("/api/v1/ocr/recognize")
    assert r.status_code in (422, 503)


def test_recognize_unknown_provider_returns_400_or_503(client):
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
        b"\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03"
        b"\x00\x01\x5c\xcd\xff\x69\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    r = client.post(
        "/api/v1/ocr/recognize",
        params={"provider": "unknown_ocr"},
        files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
    )
    # OCR 默认关 → 503；OCR 启用 + unknown provider → 400
    assert r.status_code in (400, 503)
    if r.status_code == 400:
        assert "provider" in r.json().get("detail", "")


def test_recognize_unsupported_extension_returns_400_or_503(client):
    r = client.post(
        "/api/v1/ocr/recognize",
        params={"provider": "easyocr"},
        files={"file": ("test.txt", io.BytesIO(b"not an image"), "text/plain")},
    )
    assert r.status_code in (400, 503)


def test_recognize_oversize_returns_413_or_503(client):
    big = b"\x00" * (21 * 1024 * 1024)
    r = client.post(
        "/api/v1/ocr/recognize",
        params={"provider": "easyocr"},
        files={"file": ("big.png", io.BytesIO(big), "image/png")},
    )
    assert r.status_code in (413, 503)


def test_batch_too_many_files_returns_413_or_503(client):
    files = [
        ("files", (f"img_{i}.png", io.BytesIO(b"x" * 100), "image/png"))
        for i in range(11)
    ]
    r = client.post(
        "/api/v1/ocr/batch",
        params={"provider": "easyocr"},
        files=files,
    )
    assert r.status_code in (413, 503)


def test_recognize_disabled_returns_503_when_off(client):
    """OCR 默认关时，所有 POST 都应返回 503。"""
    status = client.get("/api/v1/ocr/status").json()
    if status.get("enabled", True):
        pytest.skip("OCR 已启用，跳过 503 测试")
    r = client.post(
        "/api/v1/ocr/recognize",
        files={"file": ("test.png", io.BytesIO(b"x"), "image/png")},
    )
    assert r.status_code == 503
    assert "禁用" in r.json().get("detail", "")


# ============================================================
# 真实 OCR 引擎（@pytest.mark.slow）
# ============================================================

@pytest.mark.slow
def test_real_recognize_kangxi_page(client):
    """真跑一次：上传 kangxi/page_001.png，验证响应结构"""
    sample = project_root / "data" / "raw" / "kangxi" / "page_001.png"
    if not sample.exists():
        pytest.skip(f"样本图不存在: {sample}")

    with open(sample, "rb") as f:
        r = client.post(
            "/api/v1/ocr/recognize",
            params={"provider": "easyocr", "detect_variants": "true"},
            files={"file": ("page_001.png", f, "image/png")},
            timeout=300,
        )
    if r.status_code != 200:
        pytest.skip(f"EasyOCR 不可用: {r.status_code} - {r.text[:200]}")
    body = r.json()
    assert "pages" in body
    assert isinstance(body["pages"], list)
    assert len(body["pages"]) >= 1
    page = body["pages"][0]
    assert "text" in page
    # OCR 至少应识别出一些字符（康熙志页面含大量汉字）
    assert len(page.get("text", "")) > 0
