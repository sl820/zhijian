"""
志鉴 FastAPI 入口
精简版：OCR + KG + RAG 三大模块
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import register_routes, trigger_warmup, get_warmup_state

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("「志鉴」系统启动中...")
    # 后台异步预热三大模块（BGE 首次加载 ~30s 慢路径）；不阻塞 startup
    warmup_task = asyncio.create_task(trigger_warmup())
    try:
        yield
    finally:
        if not warmup_task.done():
            warmup_task.cancel()
        logger.info("「志鉴」系统关闭...")


app = FastAPI(
    title="志鉴 — 古籍方志智能化整理平台",
    version="2.0.0",
    description="古籍方志智能化整理与知识服务平台（精简版：OCR + KG + RAG）",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_routes(app)


@app.get("/")
async def root():
    return {
        "message": "「志鉴」古籍方志智能化整理平台 API",
        "version": "2.0.0",
        "modules": ["ocr", "rag", "kg"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
