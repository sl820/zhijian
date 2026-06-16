"""
API 层入口

Why：从 routes.py 单文件 1200+ 行拆为 4 router + 共享层，让模块边界清晰。
How to apply：main.py 调 `register_routes(app)` 一次性挂载 4 个 router。
"""
import logging

from fastapi import FastAPI

from .system_router import router as system_router, trigger_warmup, get_warmup_state
from .rag_router import router as rag_router
from .ocr_router import router as ocr_router
from .kg_router import router as kg_router

logger = logging.getLogger(__name__)


def register_routes(app: FastAPI) -> None:
    """挂载全部 4 个 router 到 app。"""
    app.include_router(system_router)
    app.include_router(rag_router)
    app.include_router(ocr_router)
    app.include_router(kg_router)
    logger.info("Routes registered (system + rag + ocr + kg)")


__all__ = [
    "register_routes",
    "trigger_warmup",
    "get_warmup_state",
]
