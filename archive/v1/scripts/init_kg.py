"""
知识图谱批量初始化脚本

从多个数据源批量构建知识图谱。

Usage:
    # 从1998年版人物志初始化
    python scripts/init_kg.py --source data/raw/1998/第二十一编人物.txt --clear

    # 从多个文本文件初始化
    python scripts/init_kg.py --dir data/raw/1998 --clear

    # 提取但不存储（预览模式）
    python scripts/init_kg.py --source data/raw/1998/第二十一编人物.txt --preview
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.kg.pipeline import KGPipeline
from app.database.kg_service import KnowledgeGraphService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("kg_init.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def init_from_file(
    file_path: str,
    source_name: str = None,
    store: bool = True,
    clear: bool = False,
    use_llm: bool = True
) -> dict:
    """从单个文本文件初始化知识图谱

    Args:
        file_path: 文本文件路径
        source_name: 来源名称
        store: 是否存储到数据库
        clear: 是否清除已有数据
        use_llm: 是否使用LLM辅助抽取

    Returns:
        dict: 初始化结果
    """
    file_path = Path(file_path)
    if not file_path.exists():
        logger.error(f"文件不存在: {file_path}")
        return {"status": "error", "error": "file_not_found"}

    source_name = source_name or file_path.stem

    # 读取文本
    with open(file_path, encoding="utf-8") as f:
        text = f.read()

    logger.info(f"读取文件: {file_path}, 字符数: {len(text):,}")

    # 初始化KG服务
    kg_service = KnowledgeGraphService()
    kg_service._ensure_backend()

    if clear:
        if kg_service._use_in_memory:
            kg_service.in_memory_kg.clear()
            logger.info("已清除in-memory KG数据")
        else:
            try:
                kg_service.neo4j_client.execute_cypher("MATCH (n) DETACH DELETE n")
                logger.info("已清除Neo4j数据")
            except Exception as e:
                logger.warning(f"清除Neo4j失败: {e}")

    # 运行KG pipeline
    pipeline = KGPipeline()
    start_time = time.time()

    result = pipeline.build_kg_from_text(
        text=text,
        source=source_name,
        title=file_path.stem,
        use_llm=use_llm
    )

    elapsed = time.time() - start_time

    stats = result["stats"]
    logger.info(
        f"KG Pipeline 完成: "
        f"{stats['person_entities']} 人物, "
        f"{stats['total_relations']} 关系, "
        f"耗时 {elapsed:.1f}秒"
    )

    # 存储到数据库
    stored_persons = 0
    stored_relations = 0

    if store:
        for entity in result["entities"]:
            if entity.get("type") != "PER":
                continue
            name = entity.get("name", "")
            if not name:
                continue

            props = {
                "biography": entity.get("biography", "")[:500],
                "dynasty": entity.get("dynasty", ""),
                "years": entity.get("years", ""),
                "birthplace": entity.get("location", ""),
                "person_type": entity.get("person_type", 2),
                "source": source_name
            }

            try:
                if kg_service._use_in_memory:
                    if not kg_service.in_memory_kg.get_node(name):
                        kg_service.in_memory_kg.add_node("Person", name, **props)
                        stored_persons += 1
                else:
                    kg_service.neo4j_client.create_person(name=name, **props)
                    stored_persons += 1
            except Exception as e:
                logger.debug(f"存储人物失败 {name}: {e}")

        for rel in result["relations"]:
            from_name = rel.get("source", "")
            to_name = rel.get("target", "")
            if not from_name or not to_name:
                continue

            try:
                if kg_service._use_in_memory:
                    kg_service.in_memory_kg.add_relationship(
                        from_name, to_name,
                        rel.get("relation", "RELATED"),
                        confidence=rel.get("confidence", 0.5)
                    )
                    stored_relations += 1
                else:
                    kg_service.neo4j_client.create_relation(
                        from_name, to_name,
                        rel.get("relation", "RELATED"),
                        confidence=rel.get("confidence", 0.5)
                    )
                    stored_relations += 1
            except Exception as e:
                logger.debug(f"存储关系失败 {from_name}->{to_name}: {e}")

        logger.info(f"已存储: {stored_persons} 人物, {stored_relations} 关系")

    # 获取最终统计
    if kg_service._use_in_memory:
        final_stats = kg_service.in_memory_kg.get_stats()
    else:
        try:
            person_count = kg_service.neo4j_client.execute_cypher(
                "MATCH (p:Person) RETURN count(p) AS count"
            )[0]["count"]
            final_stats = {
                "person_count": person_count,
                "relation_count": 0
            }
        except:
            final_stats = {"person_count": 0, "relation_count": 0}

    return {
        "status": "success",
        "source": source_name,
        "file": str(file_path),
        "chars": len(text),
        "pipeline_stats": stats,
        "stored_persons": stored_persons,
        "stored_relations": stored_relations,
        "total_persons": final_stats["person_count"],
        "total_relations": final_stats["relation_count"],
        "elapsed": elapsed
    }


def init_from_directory(
    dir_path: str,
    store: bool = True,
    clear: bool = False,
    use_llm: bool = True,
    file_pattern: str = "*.txt"
) -> dict:
    """从目录批量初始化知识图谱

    Args:
        dir_path: 目录路径
        store: 是否存储
        clear: 是否清除
        use_llm: 是否使用LLM
        file_pattern: 文件匹配模式

    Returns:
        dict: 批量处理结果
    """
    dir_path = Path(dir_path)
    if not dir_path.exists():
        logger.error(f"目录不存在: {dir_path}")
        return {"status": "error", "error": "dir_not_found"}

    # 查找文本文件
    txt_files = list(dir_path.glob(file_pattern))
    logger.info(f"在 {dir_path} 中找到 {len(txt_files)} 个文本文件")

    # 排除特定文件
    skip_files = {"图片.txt", "封面.txt", "目录 (2).txt"}
    txt_files = [f for f in txt_files if f.name not in skip_files]

    if not txt_files:
        logger.warning("没有找到需要处理的文件")
        return {"status": "no_files", "total": 0}

    stats = {
        "total": len(txt_files),
        "success": 0,
        "failed": 0,
        "total_persons": 0,
        "total_relations": 0,
        "total_chars": 0
    }

    results = []

    for txt_file in tqdm(txt_files, desc="处理文件"):
        try:
            result = init_from_file(
                str(txt_file),
                source_name=txt_file.stem,
                store=store,
                clear=False,  # 只在第一个文件时清除
                use_llm=use_llm
            )

            if result["status"] == "success":
                stats["success"] += 1
                stats["total_chars"] += result["chars"]
            else:
                stats["failed"] += 1

            results.append(result)

            # 只在第一个文件时清除
            clear = False

        except Exception as e:
            logger.error(f"处理文件失败 {txt_file.name}: {e}")
            stats["failed"] += 1
            results.append({
                "file": str(txt_file),
                "status": "error",
                "error": str(e)
            })

    # 获取最终统计
    kg_service = KnowledgeGraphService()
    kg_service._ensure_backend()

    if kg_service._use_in_memory:
        final_stats = kg_service.in_memory_kg.get_stats()
        stats["total_persons"] = final_stats["person_count"]
        stats["total_relations"] = final_stats["relation_count"]

    logger.info(
        f"批量初始化完成: "
        f"成功 {stats['success']}, 失败 {stats['failed']}, "
        f"共 {stats['total_persons']} 人物, {stats['total_relations']} 关系"
    )

    return {
        "status": "completed",
        "stats": stats,
        "results": results
    }


def main():
    parser = argparse.ArgumentParser(
        description="知识图谱批量初始化脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # 输入选项（互斥）
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--source", "-s", help="单个源文件路径")
    input_group.add_argument("--dir", "-d", help="源目录路径")

    # 选项
    parser.add_argument("--output", "-o", help="输出文件路径（用于预览模式）")
    parser.add_argument("--no-store", action="store_true", help="不存储到数据库（预览模式）")
    parser.add_argument("--clear", action="store_true", help="清除已有数据")
    parser.add_argument("--no-llm", action="store_true", help="不使用LLM辅助抽取")
    parser.add_argument("--pattern", default="*.txt", help="文件匹配模式（用于目录模式）")

    args = parser.parse_args()

    store = not args.no_store
    use_llm = not args.no_llm

    logger.info(f"=" * 60)
    logger.info(f"知识图谱初始化")
    logger.info(f"=" * 60)
    logger.info(f"存储模式: {'启用' if store else '预览模式'}")
    logger.info(f"LLM辅助: {'启用' if use_llm else '禁用'}")
    logger.info(f"清除已有数据: {args.clear}")
    logger.info(f"=" * 60)

    start_time = time.time()

    if args.source:
        result = init_from_file(
            args.source,
            store=store,
            clear=args.clear,
            use_llm=use_llm
        )
    else:
        result = init_from_directory(
            args.dir,
            store=store,
            clear=args.clear,
            use_llm=use_llm,
            file_pattern=args.pattern
        )

    elapsed = time.time() - start_time
    logger.info(f"总耗时: {elapsed:.1f}秒")

    # 保存结果
    if args.output:
        output_file = Path(args.output)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"结果已保存到: {output_file}")

    return 0 if result.get("status") in ["success", "completed"] else 1


if __name__ == "__main__":
    sys.exit(main())
