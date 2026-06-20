"""
System 路由：health / status / warmup

Why：拆出独立 router 让 M1 OCR 默认关的 warmup 逻辑集中可改。
How to apply：app.include_router(system_router.router)
"""
import asyncio
import logging
import time
from typing import Dict

from fastapi import APIRouter

from ._shared import _ocr_enabled, get_kg_service, get_rag_service, get_ocr_processor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

_warmup_state: Dict = {
    "running": False,
    "completed": False,
    "started_at": None,
    "completed_at": None,
    "modules": {
        "ocr": {"status": "pending", "duration_sec": None, "error": None},
        "kg": {"status": "pending", "duration_sec": None, "error": None},
        "rag": {"status": "pending", "duration_sec": None, "error": None},
    },
    "last_error": None,
}


def get_warmup_state() -> Dict:
    return _warmup_state


def _warmup_ocr() -> None:
    """初始化 OCR processor（含 RapidOCR ONNX 模型）。模型在 __init__ 时已加载。"""
    proc = get_ocr_processor()
    if proc is None or proc.ocr is None:
        raise RuntimeError("OCR processor/provider not initialized")
    engine_attr = getattr(proc.ocr, "_engine", None) or getattr(proc.ocr, "reader", None)
    if engine_attr is None and not hasattr(proc.ocr, "recognize"):
        raise RuntimeError(f"OCR provider {type(proc.ocr).__name__} has no engine/recognize")


def _warmup_kg() -> None:
    """初始化 KG service（读 kg_state.json 入内存）。在 __init__ 时已加载。"""
    svc = get_kg_service()
    _ = len(svc._persons)


def _warmup_rag() -> None:
    """初始化 RAG 三件套：
    - embedder（BGE 模型 → CUDA，最慢 ~30s 首次加载）
    - generator（Ollama 客户端，5s 内可达）
    - retriever（ChromaDB 连接）
    """
    rag = get_rag_service()
    rag._get_embedder()
    rag._get_generator()
    rag._get_retriever()


async def trigger_warmup() -> None:
    """异步顺序预热启用的模块。失败不抛，只记录到 _warmup_state。"""
    if _warmup_state["running"]:
        logger.info("[warmup] 已在进行中，跳过")
        return

    _warmup_state["running"] = True
    _warmup_state["started_at"] = time.time()
    _warmup_state["completed"] = False
    for mod in _warmup_state["modules"].values():
        mod["status"] = "pending"
        mod["duration_sec"] = None
        mod["error"] = None
    _warmup_state["last_error"] = None

    plan = [
        ("ocr", _warmup_ocr, _ocr_enabled()),
        ("kg", _warmup_kg, True),
        ("rag", _warmup_rag, True),
    ]
    enabled_modules = [m for m, _, ok in plan if ok]
    logger.info(f"[warmup] 开始预热模块: {enabled_modules}（OCR={_ocr_enabled()}）")

    for module_name, fn, enabled in plan:
        mod_state = _warmup_state["modules"][module_name]
        if not enabled:
            mod_state["status"] = "disabled"
            mod_state["duration_sec"] = 0
            logger.info(f"[warmup] {module_name} 已禁用，跳过")
            continue
        mod_state["status"] = "loading"
        start = time.time()
        try:
            logger.info(f"[warmup] {module_name} 预热中...")
            await asyncio.to_thread(fn)
            mod_state["status"] = "loaded"
            mod_state["duration_sec"] = round(time.time() - start, 2)
            logger.info(f"[warmup] {module_name} 预热完成 ({mod_state['duration_sec']}s)")
        except Exception as e:
            mod_state["status"] = "failed"
            mod_state["error"] = str(e)[:200]
            mod_state["duration_sec"] = round(time.time() - start, 2)
            _warmup_state["last_error"] = f"{module_name}: {e}"
            logger.error(f"[warmup] {module_name} 预热失败: {e}")

    _warmup_state["running"] = False
    _warmup_state["completed_at"] = time.time()
    _warmup_state["completed"] = True
    logger.info("[warmup] 全部预热结束")


# ============================================================
# System endpoints
# ============================================================

@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "zhijian-api"}


@router.get("/status")
async def api_status():
    warm = _warmup_state
    ocr_on = _ocr_enabled()
    return {
        "api_version": "v1",
        "endpoints": ["/ocr", "/kg", "/rag"] if ocr_on else ["/kg", "/rag"],
        "ocr": {
            "enabled": ocr_on,
            "warmup_status": warm["modules"]["ocr"]["status"],
        },
        "warmup": {
            "completed": warm["completed"],
            "running": warm["running"],
            "last_error": warm["last_error"],
        },
    }


@router.get("/warmup/status")
async def warmup_status():
    """查看三大模块预热进度。BGE 首次加载 ~30s，期间此端点会反映 loading 状态。"""
    return _warmup_state


@router.post("/warmup")
async def warmup_trigger():
    """手动触发预热（启动时已自动跑；失败时可用此端点重试）。"""
    if _warmup_state["running"]:
        return {"status": "already_running", "state": _warmup_state}
    asyncio.create_task(trigger_warmup())
    return {"status": "started", "state": _warmup_state}
