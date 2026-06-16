"""
KG 路由：知识图谱 CRUD + 图谱可视化 + 预布局 + 初始化

Why：从 routes.py 拆出，M3 归类 / M5 jiapu 数据接入 / FA2 布局的端点集中。
How to apply：app.include_router(kg_router.router)
"""
import logging
from pathlib import Path
from typing import Optional, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ._shared import (
    KGEntityExtractRequest, KGPipelineRequest, KGEntityStoreRequest,
    KGRelationRequest, KGInitResponse, KGInitStatusResponse,
    get_kg_service,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")

# KG (知识图谱)
# ============================================================

@router.get("/kg/sources")
async def kg_sources():
    """列出所有可用数据源"""
    from ..database import source_router
    sources = source_router.list_sources()
    return {
        "status": "success",
        "sources": [
            {"name": k, "label": v.get("label", k), "enabled": v.get("enabled", False)}
            for k, v in sources.items()
        ],
    }


@router.get("/kg/status")
async def kg_status():
    """获取知识图谱系统状态"""
    try:
        return get_kg_service().get_kg_status()
    except Exception as e:
        logger.error(f"Error getting KG status: {e}")
        return {"status": "error", "error": str(e)}


@router.get("/kg/persons")
async def kg_list_persons(
    limit: int = 200,
    offset: int = 0,
    source: str = None,
    surname: str = None,
    has_relations: bool = False,
):
    """获取所有人物列表

    Args:
        limit: 返回上限
        offset: 跳过
        source: 数据源标识（如 "jiapu"），None 用 in-memory
        surname: 按姓过滤（拼音，仅 SQLite 源）
        has_relations: 仅返回在关系中出现的（仅 SQLite 源）
    """
    try:
        if source:
            # SQLite 数据源路径
            from ..database import jiapu_query
            persons, total = jiapu_query.list_persons(
                source=source,
                limit=limit,
                offset=offset,
                surname=surname,
                has_relations=has_relations,
            )
            return {
                "status": "success",
                "source": source,
                "persons": persons,
                "count": len(persons),
                "total": total,
            }
        # in-memory 默认路径
        service = get_kg_service()
        persons = service.get_all_persons(limit=limit)
        return {"status": "success", "source": "memory", "persons": persons, "count": len(persons)}
    except Exception as e:
        logger.error(f"Error listing persons: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kg/persons/{name}")
async def kg_get_person(name: str, depth: int = 1, source: str = None):
    """获取单个人物详情（含关系）

    注：SQLite 源时 name 应为 uri（如 p:jiapu/xxx）
    """
    try:
        if source:
            from ..database import jiapu_query
            person = jiapu_query.get_person(name, source=source)
            if not person:
                raise HTTPException(status_code=404, detail=f"人物 '{name}' 在 {source} 中未找到")
            relations = jiapu_query.get_person_relations(name, source=source)
            person["relations"] = relations
            return {"status": "success", "source": source, "person": person}
        service = get_kg_service()
        person = service.get_person_with_relations(name, depth=depth)
        if not person:
            raise HTTPException(status_code=404, detail=f"人物 '{name}' 未找到")
        return {"status": "success", "person": person}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting person {name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kg/graph")
async def kg_get_graph(limit: int = 200, offset: int = 0, source: str = None):
    """获取图谱可视化数据（ECharts 格式：nodes + links）

    SQLite 源：取一段关系 + 涉及的 person
    in-memory：取全部
    """
    try:
        if source:
            from ..database import jiapu_query
            data = jiapu_query.get_graph_subset(source=source, limit=limit, offset=offset)
        else:
            service = get_kg_service()
            data = service.get_graph_data(limit=limit)
        nodes = data.get("nodes", [])
        links = data.get("links", [])
        return {
            "status": "success",
            "source": source or "memory",
            "nodes": nodes,
            "links": links,
            "total_persons": data.get("total_persons", len(nodes)),
            "total_links": data.get("total_links", len(links)),
        }
    except Exception as e:
        logger.error(f"Error getting graph data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kg/surnames")
async def kg_top_surnames(source: str = "jiapu", limit: int = 20):
    """按姓统计 top N（仅 SQLite 源）"""
    try:
        from ..database import jiapu_query
        rows = jiapu_query.top_surnames(source=source, limit=limit)
        return {"status": "success", "source": source, "surnames": rows}
    except Exception as e:
        logger.error(f"Error getting top surnames: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kg/layout")
async def kg_layout(
    source: str = "jiapu",
    bbox: str = None,  # "xmin,ymin,xmax,ymax"
    limit: int = 500,
    offset: int = 0,
):
    """取预布局坐标子集（M6 前端星云图谱用）。

    Args:
        source: 数据源
        bbox: 视锥 bbox "xmin,ymin,xmax,ymax"（可选）
        limit: 返回节点上限
        offset: 跳过

    Returns:
        {nodes, links, total_in_bbox, total_returned, ...}
    """
    try:
        from ..database import layout_service
        bbox_tuple = None
        if bbox:
            parts = [float(p) for p in bbox.split(",")]
            if len(parts) != 4:
                raise ValueError("bbox 必须是 4 个逗号分隔的 float: xmin,ymin,xmax,ymax")
            bbox_tuple = tuple(parts)
        result = layout_service.get_layout_subset(
            source=source,
            bbox=bbox_tuple,
            limit=limit,
            offset=offset,
        )
        return {"status": "success", **result}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kg/layout/metadata")
async def kg_layout_metadata(source: str = "jiapu"):
    """布局元信息（节点/边总数 + 坐标范围）。"""
    try:
        from ..database import layout_service
        meta = layout_service.get_layout_metadata(source=source)
        return {"status": "success", **meta}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting layout metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kg/entity/extract")
async def kg_extract_entities(request: KGEntityExtractRequest):
    """从文本中提取实体（不存储）—— 用于 OCR 联动预览"""
    try:
        from ..kg import KGPipeline
        pipeline = KGPipeline()
        result = pipeline.build_kg_from_text(
            text=request.text,
            source=request.source,
            title=request.title,
        )
        return {
            "status": "success",
            "entities": result.get("entities", []),
            "relations": result.get("relations", []),
            "stats": result.get("stats", {}),
        }
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kg/build")
async def kg_build_pipeline(request: KGPipelineRequest):
    """从文本构建知识图谱（可选择存储）"""
    try:
        from ..kg import KGPipeline
        pipeline = KGPipeline()
        result = pipeline.build_kg_from_text(
            text=request.text,
            source=request.source,
            title=request.title,
        )

        stored_count = 0
        relation_count = 0
        if request.store:
            service = get_kg_service()
            for entity in result["entities"]:
                if entity.get("type") != "PER":
                    continue
                name = entity.get("name", "")
                if not name:
                    continue
                try:
                    service.add_person({
                        "name": name,
                        "biography": entity.get("biography", ""),
                        "dynasty": entity.get("dynasty", ""),
                        "years": entity.get("years", ""),
                        "birthplace": entity.get("location", ""),
                        "person_type": entity.get("person_type", 2),
                        "source": entity.get("source", request.source),
                    })
                    stored_count += 1
                except Exception as e:
                    logger.warning(f"Failed to store person {name}: {e}")

            for rel in result["relations"]:
                from_name = rel.get("source", "")
                to_name = rel.get("target", "")
                if not from_name or not to_name:
                    continue
                try:
                    service.add_relation(
                        from_name=from_name,
                        to_name=to_name,
                        relation_type=rel.get("relation", "RELATED"),
                        confidence=rel.get("confidence", 0.5),
                    )
                    relation_count += 1
                except Exception as e:
                    logger.warning(f"Failed to store relation {from_name}->{to_name}: {e}")

            result["stats"]["stored_entities"] = stored_count
            result["stats"]["stored_relations"] = relation_count

        return {
            "status": "success",
            "entities": result["entities"],
            "relations": result["relations"],
            "stats": result["stats"],
        }
    except Exception as e:
        logger.error(f"Error building KG: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kg/entity")
async def kg_add_entity(request: KGEntityStoreRequest):
    """添加单个实体到知识图谱"""
    try:
        service = get_kg_service()
        if not request.name:
            raise HTTPException(status_code=400, detail="name is required")
        person = service.add_person({
            "name": request.name,
            "biography": request.biography or "",
            "dynasty": request.dynasty or "",
            "years": request.years or "",
            "birthplace": request.birthplace or "",
            "title": request.title or "",
            "person_type": request.person_type or 2,
            "source": request.source or "",
        })
        return {"status": "success", "person": person}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/kg/relate")
async def kg_add_relation(request: KGRelationRequest):
    """添加关系到知识图谱"""
    try:
        service = get_kg_service()
        if not request.from_name or not request.to_name:
            raise HTTPException(status_code=400, detail="from_name and to_name are required")
        relation = service.add_relation(
            from_name=request.from_name,
            to_name=request.to_name,
            relation_type=request.relation_type,
            confidence=(request.properties or {}).get("confidence", 0.5),
        )
        return {"status": "success", "relation": relation}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding relation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# KG 初始化（背景 + 同步）
# ============================================================

def _run_kg_init_background(clear: bool, corpus_path: str):
    """后台线程：运行 KG 初始化"""
    global _kg_init_state
    _kg_init_state = {
        "running": True, "completed": False, "error": None, "result": None,
    }
    try:
        from ..kg import KGPipeline
        from ..database.kg_service import identify_dynasty, post_process_relations

        project_root = Path(__file__).resolve().parents[2]
        person_file = project_root / corpus_path
        if not person_file.exists():
            raise FileNotFoundError(f"人物志文件不存在: {person_file}")

        service = get_kg_service()
        if clear:
            service.clear()

        text = person_file.read_text(encoding="utf-8")
        logger.info(f"KG background init: reading {len(text):,} chars from {person_file.name}")

        pipeline = KGPipeline()
        result = pipeline.build_kg_from_text(
            text=text,
            source=str(person_file),
            title=person_file.stem,
        )

        stored_names = set()
        for entity in result["entities"]:
            if entity.get("type") != "PER":
                continue
            name = entity.get("name", "")
            if not name or name in stored_names:
                continue
            if service.has_person(name):
                stored_names.add(name)
                continue
            bio = (entity.get("biography") or "")[:500]
            service.add_person({
                "name": name,
                "biography": bio,
                "dynasty": identify_dynasty(bio),
                "years": entity.get("years", ""),
                "birthplace": entity.get("location", ""),
                "person_type": entity.get("person_type", 2),
                "source": str(person_file),
            })
            stored_names.add(name)

        relations_stored = post_process_relations(service, text, stored_names, result["relations"])

        stats = service.get_stats()
        samples = [p["name"] for p in service.get_all_persons(limit=5)]
        _kg_init_state["result"] = KGInitResponse(
            status="success",
            persons_stored=len(stored_names),
            relations_stored=relations_stored,
            total_persons=stats["person_count"],
            total_relations=stats["relation_count"],
            sample_persons=samples,
        )
        _kg_init_state["completed"] = True
        logger.info(f"KG background init complete: {len(stored_names)} persons, {relations_stored} relations")
    except Exception as e:
        logger.error(f"KG background init error: {e}")
        _kg_init_state["error"] = str(e)
        _kg_init_state["completed"] = True
    finally:
        _kg_init_state["running"] = False


@router.get("/kg/init/status", response_model=KGInitStatusResponse)
async def kg_init_status():
    return KGInitStatusResponse(
        running=_kg_init_state["running"],
        completed=_kg_init_state["completed"],
        error=_kg_init_state["error"],
        result=_kg_init_state["result"],
    )


@router.post("/kg/init", response_model=KGInitResponse)
async def kg_init(
    corpus_path: str = "data/raw/1998/第二十一编人物.txt",
    clear: bool = False,
    background: bool = False,
):
    """
    从人物志文本初始化知识图谱。
    corpus_path 默认为 1998 版固安县志人物志，可指定其他路径。
    """
    if _kg_init_state["running"]:
        raise HTTPException(status_code=409, detail="KG 初始化已在运行中")
    if _kg_init_state["completed"] and _kg_init_state["result"] and not clear:
        return _kg_init_state["result"]

    if background:
        import threading
        thread = threading.Thread(target=_run_kg_init_background, args=(clear, corpus_path))
        thread.daemon = True
        thread.start()
        return KGInitResponse(
            status="started",
            persons_stored=0, relations_stored=0,
            total_persons=0, total_relations=0,
            sample_persons=[],
        )

    # 同步执行
    try:
        from ..kg import KGPipeline
        from ..database.kg_service import identify_dynasty, post_process_relations

        project_root = Path(__file__).resolve().parents[2]
        person_file = project_root / corpus_path
        if not person_file.exists():
            raise HTTPException(status_code=404, detail=f"人物志文件不存在: {person_file}")

        service = get_kg_service()
        if clear:
            service.clear()

        text = person_file.read_text(encoding="utf-8")
        logger.info(f"KG init: reading {len(text):,} chars from {person_file.name}")

        pipeline = KGPipeline()
        result = pipeline.build_kg_from_text(
            text=text,
            source=str(person_file),
            title=person_file.stem,
        )

        stored_names = set()
        for entity in result["entities"]:
            if entity.get("type") != "PER":
                continue
            name = entity.get("name", "")
            if not name or name in stored_names:
                continue
            if service.has_person(name):
                stored_names.add(name)
                continue
            bio = (entity.get("biography") or "")[:500]
            service.add_person({
                "name": name,
                "biography": bio,
                "dynasty": identify_dynasty(bio),
                "years": entity.get("years", ""),
                "birthplace": entity.get("location", ""),
                "source": str(person_file),
            })
            stored_names.add(name)

        relations_stored = post_process_relations(service, text, stored_names, result["relations"])

        stats = service.get_stats()
        samples = [p["name"] for p in service.get_all_persons(limit=5)]
        logger.info(
            f"KG init complete: {len(stored_names)} persons, {relations_stored} relations. "
            f"Total: {stats['person_count']} persons, {stats['relation_count']} relations"
        )
        return KGInitResponse(
            status="success",
            persons_stored=len(stored_names),
            relations_stored=relations_stored,
            total_persons=stats["person_count"],
            total_relations=stats["relation_count"],
            sample_persons=samples,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in KG init: {e}")
        raise HTTPException(status_code=500, detail=str(e))
