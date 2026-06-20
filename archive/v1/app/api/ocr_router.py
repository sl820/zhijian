"""
OCR 路由：古籍识别 + 异体字 + 样本（默认关）

Why：从 routes.py 拆出，M1 OCR 默认关的 503 门控集中。
How to apply：app.include_router(ocr_router.router)
"""
import logging
import os
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from ._shared import _ocr_enabled, get_ocr_processor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

# OCR (古籍识别)
# ============================================================

@router.get("/ocr/status")
async def ocr_status():
    """OCR 服务状态（不触发模型下载）"""
    if not _ocr_enabled():
        return {
            "status": "disabled",
            "enabled": False,
            "message": "OCR 模块已禁用（ZHIJIAN_OCR_ENABLED=false）",
        }
    try:
        from ..ocr.providers import ALIYUN_AVAILABLE, DEFAULT_PROVIDER, provider_availability
        avail = provider_availability()
        return {
            "status": "operational",
            "enabled": True,
            "providers": avail,
            "default_provider": DEFAULT_PROVIDER,
            "model_load": "lazy",
            "ready": True,
        }
    except Exception as e:
        logger.error(f"Error in OCR status: {e}")
        return {"status": "error", "enabled": True, "error": str(e)}


@router.get("/ocr/providers")
async def ocr_providers():
    """详细列出每个 provider 的能力与可用性"""
    from ..ocr.providers import (
        ALIYUN_AVAILABLE,
        DEFAULT_PROVIDER,
        provider_availability,
    )
    avail = provider_availability()
    details = {
        "easyocr": {
            "available": avail["easyocr"],
            "tier": "fallback",
            "quality": "low",
            "languages": ["ch_sim", "en"],
            "size_mb": 100,
            "note": "竖排繁体古籍识别效果差",
        },
        "paddleocr": {
            "available": avail["paddleocr"],
            "tier": "local",
            "quality": "high",
            "languages": ["ch_sim", "ch_cht", "en"],
            "size_mb": 200,
            "note": "Windows 兼容性差（paddlepaddle + langchain 冲突）",
        },
        "rapidocr": {
            "available": avail["rapidocr"],
            "tier": "local",
            "quality": "high",
            "languages": ["ch_sim", "ch_cht", "en"],
            "size_mb": 50,
            "note": "推荐默认：ONNX 后端、跨平台稳",
        },
        "aliyun": {
            "available": avail["aliyun"],
            "tier": "cloud",
            "quality": "best",
            "languages": ["ch_sim", "ch_cht", "ancient"],
            "size_mb": None,
            "note": "古籍识别最强，需 ALIYUN_OCR_APP_CODE 环境变量",
        },
    }
    return {
        "default": DEFAULT_PROVIDER,
        "providers": details,
    }


@router.post("/ocr/recognize")
async def ocr_recognize(
    file: UploadFile = File(...),
    provider: str = None,  # None 时走默认（rapidocr）
    detect_variants: bool = True,
    detect_taboo: bool = True,
):
    """OCR 识别单张图片"""
    if not _ocr_enabled():
        raise HTTPException(
            status_code=503,
            detail="OCR 模块已禁用（ZHIJIAN_OCR_ENABLED=false）。如需启用扫描录入功能，请设置环境变量后重启服务。",
        )
    from ..ocr.providers import ALIYUN_AVAILABLE, DEFAULT_PROVIDER, provider_availability

    # 缺省 provider
    if not provider:
        provider = DEFAULT_PROVIDER

    avail = provider_availability()

    if provider == "aliyun" and not avail["aliyun"]:
        raise HTTPException(
            status_code=400,
            detail="Aliyun OCR 未配置（需 ALIYUN_OCR_APP_CODE 或 ALIYUN_ACCESS_KEY_* 环境变量）",
        )
    if provider not in ("easyocr", "paddleocr", "rapidocr", "aliyun"):
        raise HTTPException(status_code=400, detail=f"未知 provider: {provider}")
    if not avail.get(provider, False):
        raise HTTPException(
            status_code=400,
            detail=f"provider '{provider}' 当前不可用（未安装 / 未配置）",
        )

    suffix = Path(file.filename or "image.png").suffix.lower() or ".png"
    if suffix not in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"):
        raise HTTPException(status_code=400, detail=f"不支持的图片格式: {suffix}")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件超过 20MB")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if provider == "easyocr":
            processor = get_ocr_processor()
        else:
            from ..ocr.processor import OCRProcessor
            processor = OCRProcessor(provider=provider)
        result = processor.process_image(
            tmp_path,
            detect_variants=detect_variants,
            detect_taboo=detect_taboo,
        )
        return result
    except Exception as e:
        logger.error(f"OCR recognize error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


@router.post("/ocr/batch")
async def ocr_batch(
    files: List[UploadFile] = File(...),
    provider: str = "easyocr",
):
    """批量 OCR 识别（≤10 张，总大小 ≤20MB）"""
    if not _ocr_enabled():
        raise HTTPException(
            status_code=503,
            detail="OCR 模块已禁用（ZHIJIAN_OCR_ENABLED=false）",
        )
    from ..ocr.providers import ALIYUN_AVAILABLE

    if provider == "aliyun" and not ALIYUN_AVAILABLE:
        raise HTTPException(status_code=400, detail="Aliyun OCR 未配置")
    if provider not in ("easyocr", "paddleocr", "aliyun"):
        raise HTTPException(status_code=400, detail=f"未知 provider: {provider}")
    if len(files) > 10:
        raise HTTPException(status_code=413, detail=f"批量最多 10 张（收到 {len(files)}）")

    blobs = []
    total = 0
    for f in files:
        content = await f.read()
        total += len(content)
        blobs.append((f.filename or "image.png", content))
    if total > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"批量总大小超 20MB（{total/1024/1024:.1f}MB）")

    results = []
    for filename, content in blobs:
        suffix = Path(filename).suffix.lower() or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            if provider == "easyocr":
                processor = get_ocr_processor()
            else:
                from ..ocr.processor import OCRProcessor
                processor = OCRProcessor(provider=provider)
            result = processor.process_image(tmp_path)
            result["filename"] = filename
            results.append(result)
        except Exception as e:
            logger.error(f"OCR batch error on {filename}: {e}")
            results.append({"filename": filename, "error": str(e), "pages": []})
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    return {"status": "success", "count": len(results), "results": results}


@router.get("/ocr/variants")
async def ocr_variants(limit: int = 100):
    """异体字映射表统计 + 前 N 条样本"""
    try:
        from ..ocr.variant_map import VARIANT_CHAR_MAP, TABOO_RULES
        sample = [
            {"standard": std, "variants": sorted(list(variants))}
            for std, variants in list(VARIANT_CHAR_MAP.items())[:limit]
        ]
        return {
            "total_variants": len(VARIANT_CHAR_MAP),
            "total_taboo_rules": len(TABOO_RULES),
            "sample_size": len(sample),
            "sample": sample,
        }
    except Exception as e:
        logger.error(f"Error in OCR variants: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ocr/samples")
async def ocr_samples():
    """列出样本图（kangxi 系列）"""
    try:
        project_root = Path(__file__).resolve().parents[2]
        sample_dirs = [
            project_root / "data" / "raw" / "kangxi",
            project_root / "data" / "raw",
        ]
        samples = []
        seen = set()
        for sample_dir in sample_dirs:
            if not sample_dir.exists():
                continue
            for ext in ("*.png", "*.jpg", "*.jpeg"):
                for img in sorted(sample_dir.glob(ext)):
                    if img.name in seen or not img.name.startswith("kangxi"):
                        continue
                    seen.add(img.name)
                    samples.append({
                        "name": img.name,
                        "path": str(img.relative_to(project_root)),
                        "size_kb": img.stat().st_size // 1024,
                        "url": f"/api/v1/ocr/samples/{img.name}",
                    })
        return {"count": len(samples), "samples": samples}
    except Exception as e:
        logger.error(f"Error in OCR samples: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ocr/samples/{filename}")
async def ocr_sample_file(filename: str):
    """直出样本图 PNG/JPG bytes"""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    project_root = Path(__file__).resolve().parents[2]
    candidates = [
        project_root / "data" / "raw" / "kangxi" / filename,
        project_root / "data" / "raw" / filename,
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            if candidate.suffix.lower() in (".png", ".jpg", ".jpeg"):
                return FileResponse(candidate)
    raise HTTPException(status_code=404, detail=f"样本图不存在: {filename}")


# ============================================================
