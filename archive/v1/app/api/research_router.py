"""
研究路由（research_router.py）— R9 数字人文研究系统

端点：
  GET /api/v1/research/insights                      → 3 类 insights 聚合（5min cache）
  GET /api/v1/research/insights/{type}               → 单类（kinship|graph|audit）
  GET /api/v1/research/person/{uri}/narrative        → 单人物研究叙事
  GET /api/v1/research/health                        → 研究引擎健康自检

Why：把「数据可计算」显式暴露给前端叙事视图。
How to apply：app.include_router(research_router.router)
"""
import logging
import time
from typing import Dict, Optional

from fastapi import APIRouter

from ..research.insights_engine import InsightsEngine
from ._shared import get_kg_service, get_rag_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

_engine: Optional[InsightsEngine] = None


def get_engine() -> InsightsEngine:
    """单例懒加载。"""
    global _engine
    if _engine is None:
        _engine = InsightsEngine()
    return _engine


@router.get("/research/insights")
async def research_insights_all():
    """聚合 3 类 insights。

    任何计算失败 → 单类降级为 fallback structure，整体仍 200 OK。
    """
    try:
        engine = get_engine()
        return {
            "status": "success",
            "computed_at": time.time(),
            "kinship": engine.kinship_insights(),
            "graph_structure": engine.graph_structure_insights(),
            "data_audit": engine.data_audit_insights(),
            "top_insights": engine.top_insights_for_jury(limit=6),
        }
    except Exception as e:
        logger.error(f"[research] 聚合 insights 失败: {e}")
        return {
            "status": "degraded",
            "message": "research engine in fallback mode",
            "data": {},
            "kinship": {"type": "kinship_insight", "findings": [], "fallback": True, "computed_at": time.time()},
            "graph_structure": {"type": "graph_structure", "findings": [], "fallback": True, "computed_at": time.time()},
            "data_audit": {"type": "data_audit", "findings": [], "fallback": True, "computed_at": time.time()},
            "top_insights": [],
            "error": str(e)[:200],
        }


@router.get("/research/insights/{kind}")
async def research_insights_one(kind: str):
    """单类 insights。kind ∈ {kinship, graph, audit}。"""
    if kind not in ("kinship", "graph", "audit"):
        return {
            "status": "degraded",
            "message": f"unknown insight kind: {kind}",
            "data": {},
            "valid_kinds": ["kinship", "graph", "audit"],
        }
    try:
        engine = get_engine()
        if kind == "kinship":
            return engine.kinship_insights()
        if kind == "graph":
            return engine.graph_structure_insights()
        return engine.data_audit_insights()
    except Exception as e:
        logger.error(f"[research] {kind} insights 失败: {e}")
        return {
            "type": f"{kind}_insight" if kind != "graph" else "graph_structure",
            "findings": [],
            "metrics": {},
            "computed_at": time.time(),
            "fallback": True,
            "error": str(e)[:200],
        }


@router.get("/research/person/{uri}/narrative")
async def research_person_narrative(uri: str):
    """单人物研究叙事 — 详情 + 关系 + 证据 + 所在家族统计。

    永不 500：任何子步骤失败 → 该字段填 fallback structure，整体仍 200 OK。
    """
    from ..database import jiapu_query
    from ..kg.classifier import classify_person
    from ..api._shared import EvidenceItem

    result: Dict = {
        "status": "success",
        "computed_at": time.time(),
        "uri": uri,
        "person": {},
        "relations": [],
        "evidence": [],
        "family_stats": {},
        "method": "graph_traversal + retrieval + heuristic",
        "fallback": False,
    }

    # 1. 人物详情（jiapu 源）
    try:
        p = jiapu_query.get_person(uri, source="jiapu")
        if p:
            result["person"] = {
                "uri": p.get("uri"),
                "name": p.get("name"),
                "family_name": p.get("family_name"),
                "role_of_family": p.get("role_of_family"),
                "courtesy_name": p.get("courtesy_name"),
                "biography": (p.get("biography") or "")[:300],
                "person_type": p.get("person_type"),
                "source": "jiapu",
            }
            # 所在姓的家族规模
            fn = p.get("family_name")
            if fn:
                try:
                    top = jiapu_query.top_surnames(limit=200)
                    hit = next((s for s in top if s["family_name"] == fn), None)
                    if hit:
                        result["family_stats"] = {
                            "family_name": fn,
                            "family_size": hit["cnt"],
                            "rank": next((i for i, s in enumerate(top, 1) if s["family_name"] == fn), None),
                        }
                except Exception as e:
                    logger.warning(f"[narrative] family_stats 失败: {e}")
    except Exception as e:
        logger.warning(f"[narrative] get_person 失败: {e}")
        result["person"] = {"uri": uri, "error": "人物详情加载失败（数据源未激活）", "fallback": True}
        result["fallback"] = True

    # 2. 关系
    try:
        rels = jiapu_query.get_person_relations(uri, source="jiapu")
        result["relations"] = rels[:20]  # 限 20
    except Exception as e:
        logger.warning(f"[narrative] get_person_relations 失败: {e}")
        result["relations"] = []

    # 3. 证据（RAG top 3）
    try:
        rag = get_rag_service()
        name = result["person"].get("name") or uri.split("/")[-1]
        rag_res = rag.ask_by_source(question=f"{name}：生平简介", source="jiapu", top_k=3)
        chunks = rag_res.get("sources", []) or []
        for c in chunks[:5]:
            result["evidence"].append(EvidenceItem(
                source="rag",
                node_ids=[uri],
                confidence=max(0.0, 1.0 - float(c.get("score", 0))),
                snippet=(c.get("text") or "")[:200],
                title=c.get("source"),
            ).model_dump())
    except Exception as e:
        logger.warning(f"[narrative] RAG 失败: {e}")

    # 4. KG in-memory 补充
    try:
        kg = get_kg_service()
        name = result["person"].get("name") or uri.split("/")[-1]
        p_in_kg = kg.get_person_with_relations(name) if hasattr(kg, "get_person_with_relations") else None
        if p_in_kg:
            result["evidence"].append(EvidenceItem(
                source="kg",
                node_ids=[uri],
                confidence=0.6,
                snippet=(p_in_kg.get("biography") or "")[:200],
                title="基础知识库",
            ).model_dump())
    except Exception as e:
        logger.warning(f"[narrative] KG 补充失败: {e}")

    # 兜底：evidence 为空时塞 1 条 fallback
    if not result["evidence"]:
        result["evidence"].append(EvidenceItem(
            source="fallback",
            node_ids=[uri],
            confidence=0.0,
            snippet="暂无证据（数据源未就绪或 RAG collection 为空）",
            title="兜底证据",
        ).model_dump())
        result["fallback"] = True

    return result


@router.get("/research/health")
async def research_health():
    """研究引擎健康自检。"""
    try:
        engine = get_engine()
        # 触发一次 kinship 计算以确认引擎可达
        k = engine.kinship_insights()
        return {
            "status": "ok",
            "engine": "ready",
            "cache_ttl_sec": engine.CACHE_TTL_SEC,
            "cache_hits": len(engine._cache),
            "last_kin_fallback": k.get("fallback", False),
            "computed_at": time.time(),
        }
    except Exception as e:
        logger.error(f"[research] health 失败: {e}")
        return {
            "status": "degraded",
            "engine": "fallback",
            "error": str(e)[:200],
            "computed_at": time.time(),
        }
