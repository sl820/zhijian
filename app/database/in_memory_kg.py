"""
In-memory knowledge graph fallback when Neo4j is unavailable.

Provides basic KG functionality using Python dictionaries and networkx.
"""

import logging
from typing import Dict, List, Optional, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class InMemoryKG:
    """
    In-memory knowledge graph implementation as a fallback for Neo4j.

    Provides basic graph operations:
    - Create nodes (Person, Version, Gazetteer)
    - Create relationships
    - Query nodes and relationships
    - Get graph data for visualization
    """

    def __init__(self):
        self.nodes = {}  # {name: {type, properties}}
        self.relationships = []  # [{from, to, type, properties}]
        self._node_counter = 0
        logger.info("InMemoryKG initialized (Neo4j fallback)")

    def add_node(self, label: str, name: str, **properties) -> Dict:
        """Add a node to the graph"""
        node_id = f"{label}_{self._node_counter}"
        self._node_counter += 1

        self.nodes[name] = {
            "id": node_id,
            "label": label,
            "name": name,
            **properties
        }
        logger.debug(f"Added node: {name} ({label})")
        return self.nodes[name]

    def add_relationship(self, from_name: str, to_name: str, rel_type: str, **properties) -> Dict:
        """Add a relationship between two nodes"""
        # Ensure nodes exist
        if from_name not in self.nodes:
            self.add_node("Entity", from_name)
        if to_name not in self.nodes:
            self.add_node("Entity", to_name)

        rel = {
            "from": from_name,
            "to": to_name,
            "type": rel_type,
            **properties
        }
        self.relationships.append(rel)
        logger.debug(f"Added relationship: {from_name} -[{rel_type}]-> {to_name}")
        return rel

    def get_node(self, name: str) -> Optional[Dict]:
        """Get a node by name"""
        return self.nodes.get(name)

    def get_all_nodes(self, label: str = None, limit: int = 200) -> List[Dict]:
        """Get all nodes, optionally filtered by label"""
        if label:
            return [n for n in self.nodes.values() if n.get("label") == label][:limit]
        return list(self.nodes.values())[:limit]

    def get_relationships(self, from_name: str = None, to_name: str = None,
                          rel_type: str = None) -> List[Dict]:
        """Get relationships, optionally filtered"""
        results = self.relationships

        if from_name:
            results = [r for r in results if r["from"] == from_name]
        if to_name:
            results = [r for r in results if r["to"] == to_name]
        if rel_type:
            results = [r for r in results if r["type"] == rel_type]

        return results

    def get_person_network(self, name: str, depth: int = 2) -> List[List[Dict]]:
        """Get ego network around a person (simplified BFS)"""
        if name not in self.nodes:
            return []

        visited = {name}
        frontier = {name}
        paths = []

        for _ in range(depth):
            next_frontier = set()
            for current in frontier:
                # Find all relationships involving current node
                for rel in self.relationships:
                    neighbor = None
                    if rel["from"] == current and rel["to"] not in visited:
                        neighbor = rel["to"]
                    elif rel["to"] == current and rel["from"] not in visited:
                        neighbor = rel["from"]

                    if neighbor:
                        path = [self.nodes[current], rel, self.nodes.get(neighbor, {"name": neighbor})]
                        paths.append(path)
                        next_frontier.add(neighbor)
                        visited.add(neighbor)
            frontier = next_frontier
            if not frontier:
                break

        return paths

    def get_graph_data(self, limit: int = 200) -> Dict:
        """Get graph data for visualization"""
        nodes = []
        for name, node in list(self.nodes.items())[:limit]:
            nodes.append({
                "name": name,
                "category": node.get("person_type", 2),
                "dynasty": node.get("dynasty", ""),
                "title": node.get("title", ""),
                "years": node.get("years", ""),
                "biography": node.get("biography", ""),
                "source": node.get("source", ""),
            })

        links = []
        seen = set()
        for rel in self.relationships:
            key = (rel["from"], rel["to"], rel["type"])
            if key not in seen:
                seen.add(key)
                links.append({
                    "source": rel["from"],
                    "target": rel["to"],
                    "name": rel["type"],
                    "relation": rel["type"]
                })

        return {
            "nodes": nodes,
            "links": links,
            "total_persons": len([n for n in self.nodes.values() if n.get("label") == "Person"]),
            "total_links": len(links),
            "status": "in_memory_fallback"
        }

    def get_stats(self) -> Dict:
        """Get graph statistics"""
        person_count = len([n for n in self.nodes.values() if n.get("label") == "Person"])
        version_count = len([n for n in self.nodes.values() if n.get("label") == "Version"])
        relation_count = len(self.relationships)
        return {
            "person_count": person_count,
            "version_count": version_count,
            "relation_count": relation_count
        }

    def clear(self):
        """Clear all data"""
        self.nodes.clear()
        self.relationships.clear()
        self._node_counter = 0
        logger.info("InMemoryKG cleared")


# Global in-memory KG instance
_in_memory_kg: Optional[InMemoryKG] = None


def get_in_memory_kg() -> InMemoryKG:
    """Get or create the global in-memory KG instance"""
    global _in_memory_kg
    if _in_memory_kg is None:
        _in_memory_kg = InMemoryKG()
    return _in_memory_kg
