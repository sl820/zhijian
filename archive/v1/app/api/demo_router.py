"""
Demo / Jury Pack 路由（demo_router.py）— R9 一键评委包

端点：
  GET /demo/jury_pack           → 一键评委包（系统能力 + 关键可视化 + 核心发现 + 示范问题）
  GET /demo/system_summary      → 系统整体能力说明

Why：竞赛答辩时评委可能问"你们的系统能做什么？"
     /demo/jury_pack 用一次调用聚合所有可展示的能力、关键发现、示范问题。
How to apply：app.include_router(demo_router.router)

强约束：永不 500。所有子模块失败 → 该字段填 fallback structure。
"""
import logging
import time
from typing import Dict, List

from fastapi import APIRouter

from ..config import DEMO_MODE, DEMO_NODE_LIMIT
from ..research.insights_engine import InsightsEngine
from ._shared import get_kg_service, get_rag_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


def _safe_call(fn, fallback):
    """调 fn，失败返 fallback，**绝不抛**。"""
    try:
        return fn()
    except Exception as e:
        logger.error(f"[demo] {fn.__name__} 失败: {e}")
        return fallback


@router.get("/demo/jury_pack")
async def jury_pack():
    """一键评委包：系统能力 + 关键可视化 + 核心发现 + 示范问题。

    任何子项失败 → 整个端点仍 200 OK，failed 字段标注降级。
    """
    # 1. 系统能力摘要
    system_summary = _safe_call(
        lambda: {
            "name": "志鉴·星野图考",
            "english_name": "ZhiJian · XingYe Atlas",
            "tagline": "基于真实家谱数据的数字人文研究系统",
            "demo_mode": DEMO_MODE,
            "demo_node_limit": DEMO_NODE_LIMIT,
            "core_capabilities": [
                "Graph Construction（多源异构知识图谱）",
                "ForceAtlas2 预布局 + 视锥裁剪 + LOD（30k 节点 60FPS）",
                "RAG Cross-source Retrieval（BGE + Qwen2.5-3B + ChromaDB）",
                "Research Insights Engine（零 LLM 研究结论）",
                "Unified Evidence Chain（所有回答可追溯）",
            ],
        },
        fallback={
            "name": "志鉴·星野图考",
            "english_name": "ZhiJian · XingYe Atlas",
            "tagline": "数字人文研究系统",
            "fallback": True,
        },
    )

    # 2. 关键可视化
    key_visualizations = [
        {"id": "nebula", "name": "星云图谱 3D 视图", "route": "/knowledge", "description": "FA2 布局 + 30k 节点 + 视锥裁剪"},
        {"id": "timeline", "name": "朝代时间轴", "route": "/knowledge", "description": "11 朝代筛选 + 节点计数"},
        {"id": "subgraph", "name": "1-2 跳关系子图", "route": "/knowledge", "description": "ECharts 力导向 + 跨源关系"},
        {"id": "narrative", "name": "研究叙事模式", "route": "/narrative", "description": "4-step 研究问题 + 核心发现"},
        {"id": "qa", "name": "RAG 智能问答", "route": "/qa", "description": "跨源检索 + Qwen2.5 本地生成"},
    ]

    # 3. 核心发现
    top_insights: List[Dict] = _safe_call(
        lambda: InsightsEngine().top_insights_for_jury(limit=6),
        fallback=[{
            "text": "暂无研究结论（research engine 未就绪）",
            "source": "fallback",
            "metrics": {},
            "computation": "no_op",
        }],
    )

    # 4. 示范问题
    example_questions = [
        "这个系统发现了什么规律？",
        "家族结构有什么统计特征？",
        "数据覆盖度如何？哪些是已知缺口？",
        "你的研究结论可信吗？证据从哪来？",
        "如果 LLM 宕机系统会怎样？",
        "30k 节点能跑 60FPS 吗？",
        "为什么不直接用 LangChain / LlamaIndex？",
        "数据从哪来？完整度多少？",
    ]

    # 5. 数据规模
    data_scale = _safe_call(
        lambda: {
            "jiapu_persons": _get_jiapu_count_safe(),
            "sources_registered": _count_sources(),
            "sources_enabled": _count_enabled_sources(),
            "demo_node_limit": DEMO_NODE_LIMIT,
            "rag_provider": "BGE-base-chinese-v1.5 + Qwen2.5-3B + ChromaDB",
            "graph_relations": "见 /api/v1/research/insights 的 graph_structure.metrics",
        },
        fallback={"error": "data scale unavailable", "fallback": True},
    )

    # 6. 方法栈
    method_stack = [
        {"step": 1, "name": "Graph Construction", "tech": "SQLite + Pydantic + 异构源合并"},
        {"step": 2, "name": "Layout", "tech": "ForceAtlas2 (FA2) + numpy 预计算 + bbox 子集"},
        {"step": 3, "name": "3D Render", "tech": "Three.js + InstancedMesh + 视锥裁剪 + typed-array pool"},
        {"step": 4, "name": "RAG Retrieval", "tech": "BGE embedder + ChromaDB + Ollama Qwen2.5-3B"},
        {"step": 5, "name": "Insights", "tech": "纯 SQL + numpy（零 LLM）"},
    ]

    # 7. Fallback 证据（防评委问"会崩吗"）
    fallback_evidence = [
        "/api/v1/system/health 启动自检 → PASS/WARN/FAIL",
        "/api/v1/rag/ask 任何异常 → 兜底文案 + 200 OK（不 500）",
        "/api/v1/kg/layout .npz 缺失 → CPU fallback (random + cluster)",
        "前端 AppErrorBoundary 拦截 Three.js 崩溃 → 降级 UI",
    ]

    return {
        "status": "success",
        "computed_at": time.time(),
        "system_summary": system_summary,
        "key_visualizations": key_visualizations,
        "top_insights": top_insights,
        "example_questions": example_questions,
        "data_scale": data_scale,
        "method_stack": method_stack,
        "fallback_evidence": fallback_evidence,
        "method": "system_aggregate + research_engine + static_template",
    }


@router.get("/demo/system_summary")
async def demo_system_summary():
    """系统整体能力说明（更轻量，无 insights 聚合）。"""
    return {
        "status": "success",
        "computed_at": time.time(),
        "summary": {
            "name": "志鉴·星野图考",
            "english_name": "ZhiJian · XingYe Atlas",
            "tagline": "基于真实家谱数据的数字人文研究系统",
            "demo_mode": DEMO_MODE,
            "demo_node_limit": DEMO_NODE_LIMIT,
            "data_sources": _count_sources(),
            "data_sources_enabled": _count_enabled_sources(),
            "capabilities": [
                "多源异构知识图谱（jiapu / base / dimingzhi / gmwx / wkl）",
                "3D 星云可视化（FA2 + Three.js + 视锥裁剪）",
                "RAG 跨源问答（BGE + Qwen2.5-3B + Chroma）",
                "研究结论自动生成（insights_engine 零 LLM）",
                "统一证据链（所有回答可追溯）",
            ],
        },
    }


def _get_jiapu_count_safe() -> int:
    try:
        from ..database import jiapu_query
        return jiapu_query.count_persons("jiapu")
    except Exception as e:
        logger.warning(f"[demo] count_persons 失败: {e}")
        return 0


def _count_sources() -> int:
    try:
        from ..database import source_router
        return len(source_router.list_sources())
    except Exception:
        return 0


def _count_enabled_sources() -> int:
    try:
        from ..database import source_router
        return sum(1 for s in source_router.list_sources().values() if s.get("enabled"))
    except Exception:
        return 0
