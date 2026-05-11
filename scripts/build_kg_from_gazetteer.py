"""
从固安县志文本批量构建知识图谱

功能：
- 读取1998年版人物志文本
- 调用KGPipeline进行实体识别和关系抽取
- 存储结果到 in-memory KG（Neo4j不可用时）
- 支持增量添加

Usage:
    python scripts/build_kg_from_gazetteer.py [--source 1998|all] [--clear]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.kg.pipeline import KGPipeline
from app.database.in_memory_kg import get_in_memory_kg
from app.database.kg_service import KnowledgeGraphService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("kg_build.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

#  Dynasty markers for section identification
DYNASTY_MARKERS = [
    "西汉", "东汉", "三国", "晋", "南北朝", "南朝", "北朝",
    "隋", "唐", "五代", "宋", "辽", "金", "元", "明", "清"
]

# Text files to process and their sources
GAZETTEER_FILES = {
    "第二十一编人物.txt": "1998年版固安县志·人物志",
    "概述.txt": "1998年版固安县志·概述",
}


def identify_dynasty(text: str, position: int) -> str:
    """Identify dynasty from nearby text"""
    context = text[max(0, position - 200):position]
    for marker in DYNASTY_MARKERS:
        if marker in context:
            return marker
    return ""


def extract_biography(text: str, start: int, end: int, window: int = 150) -> str:
    """Extract biography context around entity mention"""
    bio_start = max(0, start - window)
    bio_end = min(len(text), end + window)
    bio = text[bio_start:bio_end]
    # Clean whitespace
    bio = " ".join(bio.split())
    return bio


def store_entities_relations(entities, relations, source: str, kg=None):
    """Store entities and relations to in-memory KG"""
    if kg is None:
        kg = get_in_memory_kg()

    stored_persons = 0
    stored_relations = 0

    # Group entities by dynasty
    dynasty_groups = {}
    for entity in entities:
        if entity.get("type") != "PER":
            continue
        name = entity.get("name", "")
        if not name:
            continue

        # Get dynasty from context
        dynasty = entity.get("dynasty", "")
        if not dynasty:
            dynasty = identify_dynasty(
                entity.get("context", ""), entity.get("start", 0)
            )

        biography = entity.get("biography", "")
        if not biography and entity.get("context"):
            biography = entity.get("context", "")[:200]

        person_type = entity.get("person_type", 2)
        years = entity.get("years", "")
        birthplace = entity.get("location", "")

        try:
            existing = kg.get_node(name)
            if existing is None:
                kg.add_node(
                    "Person",
                    name,
                    dynasty=dynasty,
                    years=years,
                    birthplace=birthplace,
                    person_type=person_type,
                    biography=biography[:500] if biography else "",
                    source=source,
                )
                stored_persons += 1
            else:
                # Update dynasty if not set
                if not existing.get("dynasty") and dynasty:
                    existing["dynasty"] = dynasty
        except Exception as e:
            logger.warning(f"Failed to store person {name}: {e}")

    # Store relations
    for rel in relations:
        from_name = rel.get("source", "")
        to_name = rel.get("target", "")
        rel_type = rel.get("relation", "RELATED")
        confidence = rel.get("confidence", 0.5)

        if not from_name or not to_name:
            continue

        try:
            # Check both nodes exist
            from_node = kg.get_node(from_name)
            to_node = kg.get_node(to_name)
            if from_node and to_node:
                kg.add_relationship(
                    from_name, to_name, rel_type, confidence=confidence
                )
                stored_relations += 1
            else:
                if not from_node:
                    logger.debug(f"Source node not found: {from_name}")
                if not to_node:
                    logger.debug(f"Target node not found: {to_name}")
        except Exception as e:
            logger.warning(f"Failed to store relation {from_name}->{to_name}: {e}")

    return stored_persons, stored_relations


def process_text_file(filepath: Path, source_name: str, pipeline: KGPipeline, kg):
    """Process a single text file and store results"""
    logger.info(f"Processing: {filepath.name}")

    try:
        with open(filepath, encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        logger.error(f"Failed to read {filepath}: {e}")
        return 0, 0

    if len(text) < 50:
        logger.warning(f"Text too short: {filepath.name}")
        return 0, 0

    logger.info(f"  Text length: {len(text):,} chars")

    # Build KG from text
    result = pipeline.build_kg_from_text(
        text=text,
        source=source_name,
        title=filepath.stem
    )

    stats = result["stats"]
    logger.info(
        f"  Extracted: {stats['person_entities']} persons, "
        f"{stats['total_relations']} relations, "
        f"{stats['resolved_entities']} resolved"
    )

    # Store to in-memory KG
    persons_stored, rels_stored = store_entities_relations(
        result["entities"],
        result["relations"],
        source=source_name,
        kg=kg
    )

    logger.info(f"  Stored: {persons_stored} persons, {rels_stored} relations")
    return persons_stored, rels_stored


def main():
    parser = argparse.ArgumentParser(description="从县志文本构建知识图谱")
    parser.add_argument(
        "--source",
        choices=["1998", "kangxi", "all"],
        default="1998",
        help="数据来源"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="清空现有KG数据"
    )
    parser.add_argument(
        "--data-dir",
        default="data/raw/1998",
        help="数据目录"
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    data_dir = project_root / args.data_dir

    if not data_dir.exists():
        logger.error(f"数据目录不存在: {data_dir}")
        sys.exit(1)

    # Initialize KG and pipeline
    kg_service = KnowledgeGraphService()
    kg_service._ensure_backend()
    kg = kg_service.in_memory_kg

    if args.clear:
        kg.clear()
        logger.info("KG data cleared")

    pipeline = KGPipeline()

    total_persons = 0
    total_relations = 0

    if args.source in ["1998", "all"]:
        # Process 人物志 first (most important for KG)
        person_file = data_dir / "第二十一编人物.txt"
        if person_file.exists():
            p, r = process_text_file(person_file, "1998年版固安县志·人物志", pipeline, kg)
            total_persons += p
            total_relations += r

        # Process other text files
        for fname, source_name in GAZETTEER_FILES.items():
            if fname == "第二十一编人物.txt":
                continue
            fpath = data_dir / fname
            if fpath.exists():
                p, r = process_text_file(fpath, source_name, pipeline, kg)
                total_persons += p
                total_relations += r

    # Report final stats
    final_stats = kg.get_stats()
    logger.info("=" * 50)
    logger.info("KG Build Complete")
    logger.info(f"  New persons added: {total_persons}")
    logger.info(f"  New relations added: {total_relations}")
    logger.info(f"  Total persons in KG: {final_stats['person_count']}")
    logger.info(f"  Total relations: {final_stats['relation_count']}")

    # Show sample nodes
    all_nodes = kg.get_all_nodes(label="Person", limit=10)
    if all_nodes:
        logger.info(f"  Sample persons: {[n['name'] for n in all_nodes[:5]]}")

    # Show graph data
    graph = kg.get_graph_data(limit=10)
    logger.info(f"  KG nodes in graph data: {len(graph['nodes'])}")
    logger.info(f"  KG links in graph data: {len(graph['links'])}")


if __name__ == "__main__":
    main()
