"""
ChromaDB vector database client for RAG system.

Provides a compatible interface with MilvusVectorClient for local embedding storage.
"""

import logging
from typing import List, Dict, Optional

import chromadb

logger = logging.getLogger(__name__)


class ChromaVectorClient:
    """
    ChromaDB-based vector client providing similar interface to MilvusVectorClient.

    ChromaDB is a lightweight vector database that works locally without Docker.
    """

    def __init__(self, persist_directory: str = None):
        from .. import config as app_config
        if persist_directory is None:
            persist_directory = str(app_config.CHROMA_PERSIST_DIR)
        self.persist_directory = persist_directory
        self.client = chromadb.PersistentClient(path=persist_directory)
        self._collections = {}
        logger.info(f"Connected to ChromaDB at {persist_directory}")

    def create_collection(self, collection_name: str, dimension: int = 768):
        """Create a new collection with specified dimension."""
        if self.has_collection(collection_name):
            self.drop_collection(collection_name)
            logger.info(f"Dropped existing collection: {collection_name}")

        collection = self.client.create_collection(
            name=collection_name,
            metadata={"dimension": dimension}
        )
        self._collections[collection_name] = collection
        logger.info(f"Created collection: {collection_name} with dimension {dimension}")

    def insert_vectors(self, collection_name: str, vectors: list, texts: list, metadata: list = None):
        """Insert vectors and their associated texts into a collection."""
        collection = self.client.get_collection(collection_name)

        # Prepare IDs
        ids = [f"vec_{i}" for i in range(len(vectors))]

        # Prepare metadata - ChromaDB only supports str/int/float/bool values
        metas = metadata if metadata is not None else [{} for _ in vectors]
        for i, meta in enumerate(metas):
            if not isinstance(meta, dict):
                metas[i] = {}
            metas[i]["text"] = texts[i] if i < len(texts) else ""
            # Filter out None and non-serializable values for ChromaDB
            cleaned = {}
            for k, v in metas[i].items():
                if v is None:
                    cleaned[k] = ""
                elif isinstance(v, (str, int, float, bool)):
                    cleaned[k] = v
                else:
                    cleaned[k] = str(v)
            metas[i] = cleaned

        collection.add(
            embeddings=vectors,
            documents=texts,
            metadatas=metas,
            ids=ids
        )
        logger.info(f"Inserted {len(vectors)} vectors into {collection_name}")

    def search(self, collection_name: str, query_vector: list, top_k: int = 5) -> list:
        """Search for similar vectors in a collection."""
        collection = self.client.get_collection(collection_name)

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        formatted_results = []
        if results["ids"] and len(results["ids"]) > 0:
            for i, hit_id in enumerate(results["ids"][0]):
                idx = results["ids"][0].index(hit_id)
                formatted_results.append({
                    "id": hit_id,
                    "distance": results["distances"][0][idx] if results["distances"] else 0,
                    "text": results["documents"][0][idx] if results["documents"] else "",
                    "metadata": results["metadatas"][0][idx] if results["metadatas"] else {}
                })

        return formatted_results

    def drop_collection(self, collection_name: str):
        """Delete a collection and its data."""
        try:
            self.client.delete_collection(collection_name)
            if collection_name in self._collections:
                del self._collections[collection_name]
            logger.info(f"Dropped collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to drop collection {collection_name}: {e}")

    def has_collection(self, collection_name: str) -> bool:
        """Check if a collection exists."""
        try:
            self.client.get_collection(collection_name)
            return True
        except Exception:
            return False

    def get_collection(self, collection_name: str):
        """Get a collection by name."""
        return self.client.get_collection(collection_name)
