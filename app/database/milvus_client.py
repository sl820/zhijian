import logging
from pymilvus import MilvusClient

logger = logging.getLogger(__name__)


class MilvusVectorClient:
    def __init__(self, uri: str = "./milvus_zhijian.db"):
        self.uri = uri
        self.client = MilvusClient(uri=uri)
        logger.info(f"Connected to Milvus at {uri}")

    def create_collection(self, collection_name: str, dimension: int = 768):
        if self.has_collection(collection_name):
            self.drop_collection(collection_name)
            logger.info(f"Dropped existing collection: {collection_name}")

        self.client.create_collection(
            collection_name=collection_name,
            dimension=dimension,
            index_type="HNSW",
            metric_type="IP",
            primary_field_name="id"
        )
        logger.info(f"Created collection: {collection_name} with dimension {dimension}")

    def insert_vectors(self, collection_name: str, vectors: list, texts: list, metadata: list = None):
        data = []
        for i, (vector, text) in enumerate(zip(vectors, texts)):
            record = {
                "id": i,
                "vector": vector,
                "text": text
            }
            if metadata:
                record["metadata"] = metadata[i]
            data.append(record)

        self.client.insert(collection_name=collection_name, data=data)
        logger.info(f"Inserted {len(vectors)} vectors into {collection_name}")

    def search(self, collection_name: str, query_vector: list, top_k: int = 5) -> list:
        results = self.client.search(
            collection_name=collection_name,
            data=[query_vector],
            limit=top_k,
            output_fields=["text", "metadata"]
        )

        formatted_results = []
        for hits in results:
            for hit in hits:
                formatted_results.append({
                    "id": hit["id"],
                    "distance": hit["distance"],
                    "text": hit["entity"]["text"],
                    "metadata": hit["entity"].get("metadata")
                })
        return formatted_results

    def drop_collection(self, collection_name: str):
        try:
            self.client.drop_collection(collection_name=collection_name)
            logger.info(f"Dropped collection: {collection_name}")
        except Exception as e:
            logger.error(f"Failed to drop collection {collection_name}: {e}")

    def has_collection(self, collection_name: str) -> bool:
        return self.client.has_collection(collection_name=collection_name)
