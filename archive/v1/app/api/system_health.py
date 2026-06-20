"""
System Health Gate（系统健康自检）

Why：竞赛交付阶段必须保证"系统不会炸"。
    启动时自检关键依赖（KG / RAG / 布局 / API），任一失败 → 返回 FAIL → 前端进入 SAFE MODE。
How to apply：app.include_router(health_router.router)
              前端 useSystemHealthStore.checkHealth() 轮询 / 启动时拉一次

评估规则：
  - PASS  一切正常
  - WARN  部分功能降级（如 RAG LLM 不可用、布局 .npz 缺失但可 CPU 兜底）
  - FAIL  关键路径不可用（KG 加载失败 / 布局无法兜底 → SAFE MODE 触发）

SAFE MODE：
  - 前端隐藏 OCR / 智能问答入口
  - 知识图谱页展示降级版（5000 节点上限 + 静态兜底图）
  - RAG 静默返回 fallback 答案
"""
import logging
import time
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter

from ..config import DEMO_MODE, DEMO_NODE_LIMIT
from ._shared import get_kg_service, get_rag_service
from .system_router import get_warmup_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


def _check_layout_file() -> Dict:
    """检查布局 .npz 是否存在（任何源有一个就 PASS，否则进入 CPU fallback）。"""
    layouts_path = Path(__file__).resolve().parents[2] / "data" / "layouts"
    if not layouts_path.exists():
        return {
            "name": "layout",
            "status": "WARN",
            "message": f"布局目录不存在: {layouts_path}，将使用 CPU fallback（random + cluster）",
            "details": {"fallback": "cpu_random_cluster", "path": str(layouts_path)},
        }
    npz_files = list(layouts_path.glob("*_v1.npz"))
    if not npz_files:
        return {
            "name": "layout",
            "status": "WARN",
            "message": f"布局目录无 .npz 文件: {layouts_path}，将使用 CPU fallback",
            "details": {"fallback": "cpu_random_cluster", "files": []},
        }
    return {
        "name": "layout",
        "status": "PASS",
        "message": f"已发现 {len(npz_files)} 个布局文件",
        "details": {"files": [f.name for f in npz_files[:5]]},
    }


def _check_kg_service() -> Dict:
    """检查 KG service 是否加载（persons 字典非空）。"""
    try:
        svc = get_kg_service()
        n = len(getattr(svc, "_persons", {}))
        if n == 0:
            return {
                "name": "kg",
                "status": "FAIL",
                "message": "KG service 已加载但 persons 字典为空（数据未入库）",
                "details": {"persons": 0},
            }
        return {
            "name": "kg",
            "status": "PASS",
            "message": f"KG service 已加载，persons={n}",
            "details": {"persons": n},
        }
    except Exception as e:
        return {
            "name": "kg",
            "status": "FAIL",
            "message": f"KG service 加载失败: {str(e)[:200]}",
            "details": {"error": str(e)[:200]},
        }


def _check_rag_embedder() -> Dict:
    """检查 RAG embedder 是否可用（BGE 首次加载 30s）。"""
    try:
        rag = get_rag_service()
        embedder = rag._get_embedder()
        if embedder is None:
            return {
                "name": "rag_embedder",
                "status": "WARN",
                "message": "RAG embedder 未初始化（首次 /rag/ask 时会触发）",
                "details": {},
            }
        return {
            "name": "rag_embedder",
            "status": "PASS",
            "message": f"RAG embedder 已就绪（{getattr(embedder, 'model_name', 'unknown')}）",
            "details": {"model": getattr(embedder, "model_name", "unknown")},
        }
    except Exception as e:
        return {
            "name": "rag_embedder",
            "status": "WARN",
            "message": f"RAG embedder 加载失败: {str(e)[:200]}，将降级为 tfidf fallback",
            "details": {"error": str(e)[:200], "fallback": "tfidf"},
        }


def _check_rag_llm() -> Dict:
    """检查 RAG LLM（Ollama）是否可用。"""
    try:
        rag = get_rag_service()
        gen = getattr(rag, "generator", None)
        if gen is None:
            return {
                "name": "rag_llm",
                "status": "WARN",
                "message": "RAG generator 未初始化",
                "details": {},
            }
        ollama = getattr(gen, "_ollama", None)
        if ollama is None:
            return {
                "name": "rag_llm",
                "status": "WARN",
                "message": f"RAG generator 类型: {type(gen).__name__}（无 Ollama 客户端）",
                "details": {"type": type(gen).__name__},
            }
        available = ollama.is_available()
        if not available:
            return {
                "name": "rag_llm",
                "status": "WARN",
                "message": "Ollama 不可用（11434 端口无响应），RAG 将返回兜底答案",
                "details": {"provider": "ollama", "available": False},
            }
        return {
            "name": "rag_llm",
            "status": "PASS",
            "message": "Ollama 已就绪",
            "details": {"provider": "ollama", "available": True},
        }
    except Exception as e:
        return {
            "name": "rag_llm",
            "status": "WARN",
            "message": f"LLM 检查异常: {str(e)[:200]}，RAG 将返回兜底答案",
            "details": {"error": str(e)[:200]},
        }


def _check_rag_collections() -> Dict:
    """检查 RAG 是否有 collection（数据是否已灌库）。"""
    try:
        rag = get_rag_service()
        collections = rag.list_collections() or []
        zhijian = [c for c in collections if str(c).startswith("zhijian_") or str(c).startswith("gazetteer_")]
        if not zhijian:
            return {
                "name": "rag_collections",
                "status": "WARN",
                "message": "未发现 zhijian_/gazetteer_ collection，RAG 检索将无结果（不影响问答 fallback）",
                "details": {"collections": collections[:5]},
            }
        return {
            "name": "rag_collections",
            "status": "PASS",
            "message": f"已发现 {len(zhijian)} 个 zhijian collection",
            "details": {"collections": [c for c in zhijian[:5]]},
        }
    except Exception as e:
        return {
            "name": "rag_collections",
            "status": "WARN",
            "message": f"collection 列表拉取失败: {str(e)[:200]}",
            "details": {"error": str(e)[:200]},
        }


def compute_health() -> Dict:
    """聚合所有检查项 → 给出 overall status + 各项明细。

    Returns:
        {
            "overall": "PASS" | "WARN" | "FAIL",
            "demo_mode": bool,
            "demo_node_limit": int,
            "checks": [...],
            "summary": {pass: int, warn: int, fail: int},
            "checked_at": ISO timestamp,
        }
    """
    checks: List[Dict] = [
        _check_kg_service(),
        _check_layout_file(),
        _check_rag_embedder(),
        _check_rag_llm(),
        _check_rag_collections(),
    ]

    # 顺便挂上 warmup 状态（启动期 KG 还未加载完时可能正在跑）
    warm = get_warmup_state()
    checks.append({
        "name": "warmup",
        "status": "PASS" if warm.get("completed") and not warm.get("last_error") else ("WARN" if warm.get("running") else "PASS"),
        "message": "已就绪" if warm.get("completed") else ("预热中..." if warm.get("running") else "未启动"),
        "details": {
            "completed": warm.get("completed"),
            "running": warm.get("running"),
            "last_error": warm.get("last_error"),
        },
    })

    fail_count = sum(1 for c in checks if c["status"] == "FAIL")
    warn_count = sum(1 for c in checks if c["status"] == "WARN")
    pass_count = sum(1 for c in checks if c["status"] == "PASS")

    if fail_count > 0:
        overall = "FAIL"
    elif warn_count > 0:
        overall = "WARN"
    else:
        overall = "PASS"

    return {
        "overall": overall,
        "demo_mode": DEMO_MODE,
        "demo_node_limit": DEMO_NODE_LIMIT,
        "checks": checks,
        "summary": {
            "pass": pass_count,
            "warn": warn_count,
            "fail": fail_count,
            "total": len(checks),
        },
        "checked_at": time.time(),
    }


@router.get("/system/health")
async def system_health():
    """系统健康检查：KG / RAG / 布局 / API 连通性。

    前端 useSystemHealthStore.checkHealth() 调此端点：
      - overall === 'FAIL'  → SAFE MODE 横幅
      - overall === 'WARN'  → 黄条提示但可继续
      - overall === 'PASS'  → 全绿
    """
    try:
        result = compute_health()
        return result
    except Exception as e:
        logger.error(f"[health] compute_health 失败: {e}")
        return {
            "overall": "FAIL",
            "demo_mode": DEMO_MODE,
            "demo_node_limit": DEMO_NODE_LIMIT,
            "checks": [],
            "summary": {"pass": 0, "warn": 0, "fail": 1, "total": 1},
            "error": str(e)[:200],
        }
