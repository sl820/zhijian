import logging
from typing import Optional
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class Neo4jClient:
    def __init__(self, uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = "password"):
        self.uri = uri
        self.user = user
        self.password = password
        self._driver = None
        self._connected = False

    @property
    def driver(self):
        """Lazy initialization of Neo4j driver"""
        if self._driver is None:
            try:
                self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
                self._connected = True
                logger.info(f"Connected to Neo4j at {self.uri}")
            except Exception as e:
                logger.warning(f"Failed to connect to Neo4j at {self.uri}: {e}")
                self._connected = False
                raise
        return self._driver

    @property
    def is_connected(self) -> bool:
        """Check if Neo4j is connected"""
        return self._connected

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None
            self._connected = False
            logger.info("Neo4j connection closed")

    def ensure_connection(self) -> bool:
        """Verify connection is available by running a simple query"""
        try:
            _ = self.driver
            # Actually try to verify the connection works
            with self.driver.session() as session:
                result = session.run("RETURN 1")
                result.single()
            self._connected = True
            return True
        except Exception as e:
            logger.warning(f"Neo4j connection verification failed: {e}")
            self._connected = False
            return False

    def create_person(self, name: str, **properties) -> dict:
        if not self.ensure_connection():
            raise ConnectionError("Neo4j not connected")
        props_str = ", ".join([f"{k}: ${k}" for k in properties.keys()])
        if props_str:
            props_str = ", " + props_str
        query = f"CREATE (p:Person {{name: $name{props_str}}}) RETURN p"
        with self.driver.session() as session:
            result = session.run(query, name=name, **properties)
            record = result.single()
            return dict(record["p"]) if record else {}

    def create_relation(self, from_name: str, to_name: str, relation_type: str, **properties) -> dict:
        if not self.ensure_connection():
            raise ConnectionError("Neo4j not connected")
        props_str = ", ".join([f"r.{k} = ${k}" for k in properties.keys()])
        if props_str:
            props_str = " SET " + props_str
        query = f"""
        MATCH (a), (b)
        WHERE a.name = $from_name AND b.name = $to_name
        CREATE (a)-[r:{relation_type} {{}}]->(b)
        RETURN r
        """
        with self.driver.session() as session:
            result = session.run(query, from_name=from_name, to_name=to_name, **properties)
            record = result.single()
            return dict(record["r"]) if record else {}

    def query_person_network(self, name: str, depth: int = 2) -> dict:
        if not self.ensure_connection():
            raise ConnectionError("Neo4j not connected")
        query = f"""
        MATCH path = (center)-[r*1..{depth}]-(other)
        WHERE center.name = $name
        RETURN path
        """
        with self.driver.session() as session:
            result = session.run(query, name=name)
            paths = [dict(p) for p in result]
            return {"paths": paths}

    def execute_cypher(self, query: str, **params) -> list:
        if not self.ensure_connection():
            raise ConnectionError("Neo4j not connected")
        try:
            with self.driver.session() as session:
                result = session.run(query, **params)
                return [dict(record) for record in result]
        except Exception as e:
            logger.warning(f"Neo4j query failed: {e}")
            raise

    def create_gazetteer_node(self, title: str, **properties) -> dict:
        if not self.ensure_connection():
            raise ConnectionError("Neo4j not connected")
        props_str = ", ".join([f"{k}: ${k}" for k in properties.keys()])
        if props_str:
            props_str = ", " + props_str
        query = f"CREATE (g:Gazetteer {{title: $title{props_str}}}) RETURN g"
        with self.driver.session() as session:
            result = session.run(query, title=title, **properties)
            record = result.single()
            return dict(record["g"]) if record else {}

    def create_relationship_between_nodes(
        self, from_label: str, from_name: str, to_label: str, to_name: str, rel_type: str
    ) -> dict:
        if not self.ensure_connection():
            raise ConnectionError("Neo4j not connected")
        query = f"""
        MATCH (a:{from_label}), (b:{to_label})
        WHERE a.name = $from_name AND b.name = $to_name
        CREATE (a)-[r:{rel_type}]->(b)
        RETURN r
        """
        with self.driver.session() as session:
            result = session.run(query, from_name=from_name, to_name=to_name)
            record = result.single()
            return dict(record["r"]) if record else {}

    def get_all_persons(self) -> list:
        if not self.ensure_connection():
            raise ConnectionError("Neo4j not connected")
        query = "MATCH (p:Person) RETURN p"
        with self.driver.session() as session:
            result = session.run(query)
            return [dict(record["p"]) for record in result]

    def find_person(self, name: str) -> dict:
        if not self.ensure_connection():
            raise ConnectionError("Neo4j not connected")
        query = "MATCH (p:Person {name: $name}) RETURN p"
        with self.driver.session() as session:
            result = session.run(query, name=name)
            record = result.single()
            return dict(record["p"]) if record else {}
