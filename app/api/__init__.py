"""
API 层入口

Why：从 routes.py 单文件 1200+ 行拆为 4 router + 共享层，让模块边界清晰。
How to apply：main.py 调 `register_routes(app)` 一次性挂载 4 个 router。
"""
import logging

from fastapi import FastAPI

from .system_router import router as system_router, trigger_warmup, get_warmup_state
from .system_health import router as system_health_router
from .rag_router import router as rag_router
from .ocr_router import router as ocr_router
from .kg_router import router as kg_router
from .research_router import router as research_router
from .demo_router import router as demo_router

logger = logging.getLogger(__name__)


def register_routes(app: FastAPI) -> None:
    """挂载全部 7 个 router 到 app。
    system + system_health + rag + ocr + kg + research + demo
    """
    app.include_router(system_router)
    app.include_router(system_health_router)
    app.include_router(rag_router)
    app.include_router(ocr_router)
    app.include_router(kg_router)
    app.include_router(research_router)
    app.include_router(demo_router)
    logger.info("Routes registered (7: system + system_health + rag + ocr + kg + research + demo)")


__all__ = [
    "register_routes",
    "trigger_warmup",
    "get_warmup_state",
]
