import logging
from .neo4j_client import Neo4jClient
from .in_memory_kg import InMemoryKG, get_in_memory_kg

logger = logging.getLogger(__name__)


class KnowledgeGraphService:
    """
    Service that combines Neo4j + Milvus for the knowledge graph.

    When Neo4j is unavailable, falls back to in-memory implementation.
    """

    def __init__(self):
        self._neo4j_client = None
        self._milvus_client = None
        self._in_memory_kg = None
        self._use_in_memory = False
        logger.info("KnowledgeGraphService initialized")

    @property
    def neo4j_client(self) -> Neo4jClient:
        """Lazy initialization of Neo4j client"""
        if self._neo4j_client is None:
            self._neo4j_client = Neo4jClient()
        return self._neo4j_client

    @property
    def in_memory_kg(self) -> InMemoryKG:
        """Lazy initialization of in-memory KG fallback"""
        if self._in_memory_kg is None:
            self._in_memory_kg = get_in_memory_kg()
        return self._in_memory_kg

    @property
    def milvus_client(self):
        """Lazy initialization of Milvus client"""
        if self._milvus_client is None:
            from .milvus_client import MilvusVectorClient
            self._milvus_client = MilvusVectorClient()
        return self._milvus_client

    def is_neo4j_available(self) -> bool:
        """Check if Neo4j is connected"""
        try:
            return self.neo4j_client.ensure_connection()
        except Exception:
            return False

    def _ensure_backend(self):
        """Ensure we have a working backend (Neo4j or in-memory)"""
        if self._use_in_memory:
            return
        if not self.is_neo4j_available():
            logger.warning("Neo4j unavailable, switching to in-memory KG fallback")
            self._use_in_memory = True

    def add_person_with_embedding(self, name: str, biography_text: str, embedding: list, **properties):
        """Add a person with embedding to the knowledge graph"""
        self._ensure_backend()

        if self._use_in_memory:
            self.in_memory_kg.add_node("Person", name, biography=biography_text, **properties)
        else:
            self.neo4j_client.create_person(name, biography=biography_text, **properties)

        try:
            self.milvus_client.insert_vectors(
                collection_name="persons",
                vectors=[embedding],
                texts=[biography_text],
                metadata=[{"name": name}]
            )
        except Exception as e:
            logger.warning(f"Failed to store embedding in Milvus: {e}")

        logger.info(f"Added person with embedding: {name}")

    def add_gazetteer_content(self, gazetteer_title: str, content_chunks: list, embeddings: list):
        """Add gazetteer content to the knowledge graph"""
        self._ensure_backend()

        if self._use_in_memory:
            self.in_memory_kg.add_node("Gazetteer", gazetteer_title, content_count=len(content_chunks))
        else:
            self.neo4j_client.create_gazetteer_node(gazetteer_title, content_count=len(content_chunks))

        try:
            self.milvus_client.insert_vectors(
                collection_name="gazetteers",
                vectors=embeddings,
                texts=content_chunks,
                metadata=[{"title": gazetteer_title}]
            )
        except Exception as e:
            logger.warning(f"Failed to store embeddings in Milvus: {e}")

        logger.info(f"Added gazetteer content: {gazetteer_title} with {len(content_chunks)} chunks")

    def create_person_relation(self, from_name: str, to_name: str, relation_type: str, **properties):
        """Create a relationship between two persons"""
        self._ensure_backend()

        if self._use_in_memory:
            self.in_memory_kg.add_relationship(from_name, to_name, relation_type, **properties)
        else:
            self.neo4j_client.create_relation(from_name, to_name, relation_type, **properties)

        logger.info(f"Created relation: {from_name} -[{relation_type}]-> {to_name}")

    def query_person_info(self, name: str) -> dict:
        """Query person information"""
        self._ensure_backend()

        if self._use_in_memory:
            return self.in_memory_kg.get_node(name) or {}
        return self.neo4j_client.find_person(name)

    def query_related_persons(self, name: str, depth: int = 2) -> list:
        """Query persons related to a given person"""
        self._ensure_backend()

        if self._use_in_memory:
            paths = self.in_memory_kg.get_person_network(name, depth)
            return [{"paths": paths}]
        return self.neo4j_client.query_person_network(name, depth)

    def semantic_search(self, query_embedding: list, top_k: int = 5, person_filter: str = None) -> list:
        """Semantic search for persons"""
        try:
            results = self.milvus_client.search(
                collection_name="persons",
                query_vector=query_embedding,
                top_k=top_k
            )

            if person_filter:
                results = [
                    r for r in results
                    if r.get("metadata") and r["metadata"].get("name") == person_filter
                ]
            return results
        except Exception as e:
            logger.warning(f"Semantic search failed: {e}")
            return []

    def store_collation_result(
        self,
        source_a: str,
        source_b: str,
        diffs: list,
        alignment_score: float = 0.0,
        metadata: dict = None
    ) -> dict:
        """
        Store collation comparison results as graph relationships.
        """
        self._ensure_backend()

        metadata = metadata or {}

        if self._use_in_memory:
            # Use in-memory KG
            self.in_memory_kg.add_node("Version", source_a)
            self.in_memory_kg.add_node("Version", source_b)
            self.in_memory_kg.add_relationship(source_a, source_b, "COMPARED_WITH",
                                               alignment_score=alignment_score)

            variation_count = 0
            for diff in diffs:
                diff_type = diff.get("type", "unknown")
                text_a = diff.get("text_a", "")
                text_b = diff.get("text_b", "")

                if diff_type in ("substitution", "insertion", "deletion") and (text_a or text_b):
                    self.in_memory_kg.add_node("Variation", f"var_{variation_count}",
                                              type=diff_type, text_a=text_a, text_b=text_b,
                                              source_a=source_a, source_b=source_b)
                    self.in_memory_kg.add_relationship(source_a, f"var_{variation_count}", "HAS_VARIATION")
                    self.in_memory_kg.add_relationship(f"var_{variation_count}", source_b, "VARIATION_OF")
                    variation_count += 1

            return {
                "status": "success_in_memory",
                "source_a": source_a,
                "source_b": source_b,
                "alignment_score": alignment_score,
                "variation_count": variation_count
            }

        # Neo4j implementation
        try:
            self.neo4j_client.execute_cypher(
                f"MERGE (a:Version {{title: $source_a}})",
                source_a=source_a
            )
            self.neo4j_client.execute_cypher(
                f"MERGE (b:Version {{title: $source_b}})",
                source_b=source_b
            )
        except Exception as e:
            logger.warning(f"Failed to create version nodes: {e}")

        try:
            self.neo4j_client.execute_cypher(
                f"""
                MATCH (a:Version {{title: $source_a}}), (b:Version {{title: $source_b}})
                MERGE (a)-[r:COMPARED_WITH]->(b)
                SET r.alignment_score = $alignment_score
                """,
                source_a=source_a,
                source_b=source_b,
                alignment_score=alignment_score
            )
        except Exception as e:
            logger.warning(f"Failed to create comparison relationship: {e}")

        variation_count = 0
        for diff in diffs:
            diff_type = diff.get("type", "unknown")
            text_a = diff.get("text_a", "")
            text_b = diff.get("text_b", "")

            if diff_type in ("substitution", "insertion", "deletion") and (text_a or text_b):
                try:
                    self.neo4j_client.execute_cypher(
                        f"""
                        MERGE (v:Variation {{id: randomUUID()}})
                        SET v.type = $diff_type,
                            v.text_a = $text_a,
                            v.text_b = $text_b,
                            v.source_a = $source_a,
                            v.source_b = $source_b
                        """,
                        diff_type=diff_type,
                        text_a=text_a,
                        text_b=text_b,
                        source_a=source_a,
                        source_b=source_b
                    )

                    self.neo4j_client.execute_cypher(
                        f"""
                        MATCH (v:Variation {{text_a: $text_a, text_b: $text_b}})
                        MATCH (a:Version {{title: $source_a}}), (b:Version {{title: $source_b}})
                        MERGE (a)-[:HAS_VARIATION]->(v)
                        MERGE (v)-[:VARIATION_OF]->(b)
                        """,
                        text_a=text_a,
                        text_b=text_b,
                        source_a=source_a,
                        source_b=source_b
                    )
                    variation_count += 1
                except Exception as e:
                    logger.warning(f"Failed to create variation node: {e}")

        logger.info(f"Stored collation result: {source_a} vs {source_b}, {variation_count} variations")
        return {
            "status": "success",
            "source_a": source_a,
            "source_b": source_b,
            "alignment_score": alignment_score,
            "variation_count": variation_count
        }

    def get_kg_status(self) -> dict:
        """Get knowledge graph system status"""
        self._ensure_backend()

        if self._use_in_memory:
            stats = self.in_memory_kg.get_stats()
            return {
                "status": "in_memory_fallback",
                "mode": "in_memory",
                "message": "Using in-memory graph (Neo4j unavailable)",
                "person_count": stats["person_count"],
                "version_count": stats["version_count"],
                "relation_count": stats["relation_count"]
            }

        # Neo4j implementation
        try:
            result = self.neo4j_client.execute_cypher("MATCH (p:Person) RETURN count(p) AS count")
            person_count = result[0]["count"] if result else 0
        except Exception as e:
            person_count = f"error: {e}"

        try:
            result = self.neo4j_client.execute_cypher("MATCH (v:Version) RETURN count(v) AS count")
            version_count = result[0]["count"] if result else 0
        except Exception as e:
            version_count = f"error: {e}"

        try:
            result = self.neo4j_client.execute_cypher("MATCH (a)-[r]->(b) WHERE a:Person AND b:Person RETURN count(r) AS count")
            relation_count = result[0]["count"] if result else 0
        except Exception as e:
            relation_count = f"error: {e}"

        return {
            "status": "operational",
            "person_count": person_count,
            "version_count": version_count,
            "relation_count": relation_count
        }

    def get_all_persons(self) -> list:
        """Get all person nodes"""
        self._ensure_backend()

        if self._use_in_memory:
            return self.in_memory_kg.get_all_nodes(label="Person")

        try:
            result = self.neo4j_client.execute_cypher(
                "MATCH (p:Person) RETURN p ORDER BY p.name LIMIT 200"
            )
            return [record["p"] for record in result]
        except Exception as e:
            logger.warning(f"Failed to get all persons: {e}")
            return []

    def get_person_with_relations(self, name: str, depth: int = 1) -> dict:
        """Get a person with their relations"""
        self._ensure_backend()

        if self._use_in_memory:
            person = self.in_memory_kg.get_node(name)
            if not person:
                return {}

            # Get relations
            rels = self.in_memory_kg.get_relationships(from_name=name)
            relations = []
            for rel in rels:
                relations.append({
                    "type": rel["type"],
                    "name": rel["to"],
                    "direction": "outgoing"
                })

            person["relations"] = relations
            return person

        try:
            result = self.neo4j_client.execute_cypher(
                """
                MATCH (p:Person {name: $name})
                OPTIONAL MATCH (p)-[r]-(other)
                WHERE other IS NOT NULL
                RETURN p, collect({other_name: other.name, rel_type: r.type, other: other}) AS relations
                """,
                name=name
            )
            if not result:
                return {}
            record = result[0]
            person = record["p"]
            rels = record.get("relations") or []

            relations = []
            for rel in rels:
                rel_type = rel.get("rel_type", "RELATED")
                other = rel.get("other", {})
                other_name = other.get("name", "") if isinstance(other, dict) else ""
                if other_name:
                    relations.append({
                        "type": rel_type,
                        "name": other_name,
                        "direction": "outgoing"
                    })

            person["relations"] = relations
            return person
        except Exception as e:
            logger.warning(f"Failed to get person with relations: {e}")
            return {}

    def get_graph_data(self, limit: int = 200) -> dict:
        """Get graph data for visualization (ECharts)"""
        self._ensure_backend()

        if self._use_in_memory:
            return self.in_memory_kg.get_graph_data(limit=limit)

        try:
            # Get all person nodes
            persons = self.neo4j_client.execute_cypher(
                "MATCH (p:Person) RETURN p LIMIT $limit",
                limit=limit
            )
            nodes = []
            for record in persons:
                p = record["p"]
                nodes.append({
                    "name": p.get("name", ""),
                    "category": p.get("person_type", 2),
                    "dynasty": p.get("dynasty", ""),
                    "title": p.get("title", ""),
                    "years": p.get("years", ""),
                    "birthplace": p.get("birthplace", ""),
                    "biography": p.get("biography", ""),
                    "source": p.get("source", ""),
                })

            # Get person relationships
            rels = self.neo4j_client.execute_cypher(
                """
                MATCH (a:Person)-[r]->(b:Person)
                RETURN a.name AS source, b.name AS target, r.type AS relation
                LIMIT $limit
                """,
                limit=limit
            )
            links = []
            seen = set()
            for record in rels:
                key = (record["source"], record["target"], record["relation"])
                if key not in seen:
                    seen.add(key)
                    links.append({
                        "source": record["source"],
                        "target": record["target"],
                        "name": record["relation"],
                        "relation": record["relation"]
                    })

            return {
                "nodes": nodes,
                "links": links,
                "total_persons": len(nodes),
                "total_links": len(links),
                "status": "success"
            }
        except Exception as e:
            logger.warning(f"Failed to get graph data: {e}")
            return {
                "nodes": [],
                "links": [],
                "total_persons": 0,
                "total_links": 0,
                "status": "error",
                "error": str(e)
            }
