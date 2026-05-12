# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

# 注册API路由
from app.api.routes import register_routes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("「志鉴」系统启动中...")
    # 这里添加数据库连接初始化
    # neo4j_driver = Neo4jDriver()
    # milvus_client = MilvusClient()
    yield
    # 清理资源
    logger.info("「志鉴」系统关闭...")

app = FastAPI(
    title="志鉴 — 古籍方志智能化整理平台",
    version="1.0.0",
    description="古籍方志智能化整理与知识服务平台",
    lifespan=lifespan
)

# CORS配置（允许公网访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册API路由
register_routes(app)

@app.get("/")
async def root():
    return {"message": "「志鉴」古籍方志智能化整理平台 API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """健康检查端点"""
    from app.database.kg_service import KnowledgeGraphService

    kg_service = KnowledgeGraphService()

    # 检测 Neo4j 连接状态
    try:
        neo4j_available = kg_service.is_neo4j_available()
        neo4j_status = "connected" if neo4j_available else "disconnected"
    except Exception as e:
        neo4j_status = f"error: {str(e)[:50]}"

    # 检测 Milvus 连接状态
    milvus_status = "unknown"
    try:
        milvus_client = kg_service.milvus_client
        milvus_status = "connected"
    except Exception as e:
        milvus_status = f"error: {str(e)[:50]}"

    # 整体状态
    overall = "healthy" if neo4j_status == "connected" or milvus_status == "connected" else "degraded"

    return {
        "status": overall,
        "services": {
            "neo4j": neo4j_status,
            "milvus": milvus_status,
            "in_memory_kg": kg_service._use_in_memory
        }
    }

@app.get("/api/v1/status")
async def api_status():
    """API状态端点"""
    return {"api_version": "v1", "endpoints": ["/ocr", "/normalize", "/collation", "/kg", "/rag"]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
