import logging
import re
from typing import List, Dict, Optional, Callable
from collections import defaultdict
import math

from app.database.chroma_client import ChromaVectorClient

logger = logging.getLogger(__name__)

# Pre-compiled tokenization pattern for BM25
_BM25_TOKENIZE_PATTERN = re.compile(r'\w+')


class BM25:
    """Simple BM25 implementation for keyword search fallback."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.avg_doc_len = 0
        self.doc_freqs = {}
        self.idf = {}
        self.num_docs = 0
        self.doc_len = []
        self.corpus = []

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization by splitting on non-alphanumeric characters."""
        return _BM25_TOKENIZE_PATTERN.findall(text.lower())

    def fit(self, documents: List[str]):
        """Build the BM25 index from documents."""
        self.corpus = documents
        self.num_docs = len(documents)
        self.doc_freqs = defaultdict(int)
        self.doc_len = []
        total_len = 0

        for doc in documents:
            tokens = self._tokenize(doc)
            self.doc_len.append(len(tokens))
            total_len += len(tokens)

            seen = set()
            for token in tokens:
                if token not in seen:
                    self.doc_freqs[token] += 1
                    seen.add(token)

        self.avg_doc_len = total_len / self.num_docs if self.num_docs > 0 else 0

        # Calculate IDF for each term
        for token, freq in self.doc_freqs.items():
            self.idf[token] = math.log((self.num_docs - freq + 0.5) / (freq + 0.5) + 1)

        logger.info(f"BM25 index built with {self.num_docs} documents")

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search the index and return top-k results with scores."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = []
        for i, doc in enumerate(self.corpus):
            doc_tokens = self._tokenize(doc)
            doc_len = self.doc_len[i]

            score = 0.0
            for token in query_tokens:
                if token in self.idf:
                    tf = doc_tokens.count(token)
                    if tf > 0:
                        idf = self.idf[token]
                        # BM25 scoring formula
                        numerator = tf * (self.k1 + 1)
                        denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_len)
                        score += idf * (numerator / denominator)

            if score > 0:
                scores.append({
                    "index": i,
                    "text": doc,
                    "score": score
                })

        # Sort by score descending
        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_k]


class Retriever:
    """Hybrid retriever combining vector search with BM25 keyword search."""

    def __init__(
        self,
        milvus_client: Optional[ChromaVectorClient] = None,
        embedder: Optional[Callable[[str], List[float]]] = None,
        milvus_uri: str = "./chroma_zhijian"
    ):
        """
        Initialize the Retriever.

        Args:
            milvus_client: Optional ChromaVectorClient instance. If not provided,
                           a new one will be created using milvus_uri.
            embedder: Optional callable that takes a string query and returns
                     a list of floats (embedding vector). If not provided,
                     BM25-only search will be used.
            milvus_uri: Path for ChromaDB database (used if milvus_client not provided).
        """
        self.milvus_client = milvus_client or ChromaVectorClient(persist_directory=milvus_uri)
        self.embedder = embedder
        # Per-collection BM25 data storage using defaultdict
        self._bm25_data = defaultdict(lambda: {
            "texts": [],
            "metadata": [],
            "index": None
        })
        logger.info("Retriever initialized")

    def _ensure_bm25_built(self, collection: str):
        """Build BM25 index if not already built for the collection."""
        if self._bm25_data[collection]["index"] is not None:
            return

        try:
            # Query all texts from Milvus to build BM25 index
            # Note: This requires the collection to have data
            # In production, you might want to maintain a separate text store
            logger.info(f"Building BM25 index for collection: {collection}")

            # For now, we'll build a placeholder that can be populated
            bm25 = BM25()
            self._bm25_data[collection]["index"] = bm25
        except Exception as e:
            logger.warning(f"Failed to build BM25 index: {e}")

    def index_collection_for_bm25(
        self,
        collection: str,
        texts: List[str],
        metadata: List[Dict] = None
    ):
        """
        Index a collection of texts for BM25 search.

        Args:
            collection: Collection name for caching purposes.
            texts: List of text documents to index.
            metadata: Optional list of metadata dicts corresponding to texts.
        """
        bm25 = BM25()
        bm25.fit(texts)

        self._bm25_data[collection]["texts"] = texts
        self._bm25_data[collection]["metadata"] = metadata or [{} for _ in texts]
        self._bm25_data[collection]["index"] = bm25
        logger.info(f"BM25 index built for collection '{collection}' with {len(texts)} documents")

    def retrieve(
        self,
        query: str,
        query_vector: Optional[List[float]] = None,
        top_k: int = 5,
        collection: str = "gazetteer_chunks",
        alpha: float = 0.5
    ) -> List[Dict]:
        """
        Retrieve relevant documents using hybrid search (vector + BM25).

        Args:
            query: The search query string.
            query_vector: Optional pre-computed query embedding. If not provided,
                         will be computed using self.embedder if available.
            top_k: Number of results to return.
            collection: Milvus collection name for vector search.
            alpha: Weight for vector search scores (0.0 = BM25 only, 1.0 = vector only).
                   Default is 0.5 (balanced hybrid).

        Returns:
            List of dicts with keys: text, chapter_title, distance, source.
            Results are sorted by combined score (descending).
        """
        results = []
        vector_results = []
        bm25_results = []

        # Rebuild BM25 index from ChromaDB if empty but collection has data
        bm25_index = self._bm25_data[collection]["index"]
        if bm25_index is None or not self._bm25_data[collection]["texts"]:
            try:
                if self.milvus_client.has_collection(collection):
                    col = self.milvus_client.get_collection(collection)
                    count = col.count()
                    if count > 0:
                        logger.info(f"Rebuilding BM25 index from ChromaDB for collection '{collection}' ({count} items)")
                        all_data = col.get(limit=count)
                        texts = all_data.get("documents", [])
                        metadatas = all_data.get("metadatas", [])
                        if texts:
                            self.index_collection_for_bm25(collection, texts, metadatas)
            except Exception as e:
                logger.warning(f"Failed to rebuild BM25 index: {e}")

        # 1. Vector similarity search
        if query_vector is not None:
            # Use pre-computed query vector
            try:
                vector_results = self.milvus_client.search(
                    collection_name=collection,
                    query_vector=query_vector,
                    top_k=top_k * 2  # Get more for better fusion
                )
                logger.debug(f"Vector search returned {len(vector_results)} results")
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
        elif self.embedder:
            # Compute query vector using embedder
            try:
                query_vector = self.embedder(query)
                vector_results = self.milvus_client.search(
                    collection_name=collection,
                    query_vector=query_vector,
                    top_k=top_k * 2  # Get more for better fusion
                )
                logger.debug(f"Vector search returned {len(vector_results)} results")
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")

        # 2. BM25 keyword search fallback
        bm25_index = self._bm25_data[collection]["index"]

        bm25_texts = self._bm25_data[collection]["texts"]
        bm25_metadata = self._bm25_data[collection]["metadata"]

        if bm25_index and bm25_index.corpus:
            try:
                bm25_results = bm25_index.search(query, top_k=top_k * 2)
                logger.debug(f"BM25 search returned {len(bm25_results)} results")
            except Exception as e:
                logger.warning(f"BM25 search failed: {e}")

        # 3. Hybrid fusion using Reciprocal Rank Fusion (RRF)
        if vector_results and bm25_results:
            scores = self._reciprocal_rank_fusion(vector_results, bm25_results, top_k, alpha, collection)
            for idx, score in scores:
                # Determine source
                source = "hybrid"
                chapter_title = ""
                doc_title = ""

                # Check if from vector results
                for vr in vector_results:
                    if vr.get("text") == bm25_texts[idx] if bm25_texts else False:
                        meta = vr.get("metadata", {})
                        chapter_title = meta.get("chapter_title", "")
                        doc_title = meta.get("title", "")
                        source = "vector"
                        break

                # Check if from BM25 results
                if not chapter_title:
                    for br in bm25_results:
                        if br.get("text") == bm25_texts[idx] if bm25_texts else False:
                            if bm25_metadata and idx < len(bm25_metadata):
                                chapter_title = bm25_metadata[idx].get("chapter_title", "")
                                doc_title = bm25_metadata[idx].get("title", "")
                            source = "bm25"
                            break

                # Use doc_title as chapter_title if chapter_title is empty or "Unknown"
                if not chapter_title or chapter_title == "Unknown":
                    chapter_title = doc_title

                results.append({
                    "text": bm25_texts[idx] if bm25_texts else "",
                    "chapter_title": chapter_title,
                    "distance": score,
                    "source": source
                })
        elif vector_results:
            # Vector-only results
            for vr in vector_results:
                metadata = vr.get("metadata", {})
                chapter_title = metadata.get("chapter_title", "")
                # Fall back to title if chapter_title is empty or "Unknown"
                if not chapter_title or chapter_title == "Unknown":
                    chapter_title = metadata.get("title", "") or ""
                results.append({
                    "text": vr.get("text", ""),
                    "chapter_title": chapter_title,
                    "distance": vr.get("distance", 0.0),
                    "source": "vector"
                })
        elif bm25_results:
            # BM25-only results
            for br in bm25_results:
                idx = br["index"]
                metadata = bm25_metadata[idx] if bm25_metadata and idx < len(bm25_metadata) else {}
                results.append({
                    "text": br["text"],
                    "chapter_title": metadata.get("chapter_title", ""),
                    "distance": br["score"],
                    "source": "bm25"
                })
        else:
            logger.warning(f"No results found for query: {query}")

        # Sort by distance/score descending and limit to top_k
        results.sort(key=lambda x: x["distance"], reverse=True)
        return results[:top_k]

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Dict],
        bm25_results: List[Dict],
        top_k: int,
        alpha: float,
        collection: str = "gazetteer_chunks"
    ) -> List[tuple]:
        """
        Fuse vector and BM25 results using a simple weighted combination.
        For pure RRF, use alpha=0.5 with k=60 in the formula: 1/(k+rank)

        Args:
            vector_results: Results from vector search.
            bm25_results: Results from BM25 search.
            top_k: Number of results to return.
            alpha: Weight for vector scores (0.5 = balanced).
            collection: Collection name for per-collection BM25 data.

        Returns:
            List of (index, combined_score) tuples.
        """
        # Normalize vector distances to 0-1 range
        max_vec_dist = max(vr.get("distance", 0) for vr in vector_results) if vector_results else 1
        min_vec_dist = min(vr.get("distance", 0) for vr in vector_results) if vector_results else 0
        vec_range = max_vec_dist - min_vec_dist if max_vec_dist != min_vec_dist else 1

        # Normalize BM25 scores
        max_bm25_score = max(br.get("score", 0) for br in bm25_results) if bm25_results else 1
        min_bm25_score = min(br.get("score", 0) for br in bm25_results) if bm25_results else 0
        bm25_range = max_bm25_score - min_bm25_score if max_bm25_score != min_bm25_score else 1

        # Create text-to-index mapping for BM25 results
        bm25_text_to_idx = {}
        for i, br in enumerate(bm25_results):
            bm25_text_to_idx[br["text"]] = i

        # Create text-to-index mapping for vector results
        vec_text_to_idx = {}
        for i, vr in enumerate(vector_results):
            vec_text_to_idx[vr.get("text", "")] = i

        # Find common texts and calculate combined scores
        all_texts = set(bm25_text_to_idx.keys()) | set(vec_text_to_idx.keys())
        combined_scores = []

        bm25_texts = self._bm25_data[collection]["texts"]

        for text in all_texts:
            bm25_idx = bm25_text_to_idx.get(text)
            vec_idx = vec_text_to_idx.get(text)

            # Normalized BM25 rank score (higher is better)
            bm25_score = 0.0
            if bm25_idx is not None:
                bm25_score = (bm25_results[bm25_idx]["score"] - min_bm25_score) / bm25_range

            # Normalized vector distance score (higher is better)
            vec_score = 0.0
            if vec_idx is not None:
                raw_dist = vector_results[vec_idx].get("distance", 0)
                vec_score = (raw_dist - min_vec_dist) / vec_range

            # Weighted combination
            combined = alpha * vec_score + (1 - alpha) * bm25_score

            # Find the index in bm25_texts
            text_idx = 0
            if bm25_texts:
                try:
                    text_idx = bm25_texts.index(text)
                except ValueError:
                    text_idx = 0

            combined_scores.append((text_idx, combined))

        # Sort by combined score descending
        combined_scores.sort(key=lambda x: x[1], reverse=True)
        return combined_scores[:top_k]

    def vector_search_only(
        self,
        query: str,
        top_k: int = 5,
        collection: str = "gazetteer_chunks"
    ) -> List[Dict]:
        """
        Perform vector-only search (no BM25 fallback).

        Args:
            query: The search query string.
            top_k: Number of results to return.
            collection: Milvus collection name.

        Returns:
            List of dicts with keys: text, chapter_title, distance, source.
        """
        if not self.embedder:
            raise ValueError("Embedder not provided for vector search")

        query_vector = self.embedder(query)
        results = self.milvus_client.search(
            collection_name=collection,
            query_vector=query_vector,
            top_k=top_k
        )

        formatted_results = []
        for vr in results:
            metadata = vr.get("metadata", {})
            formatted_results.append({
                "text": vr.get("text", ""),
                "chapter_title": metadata.get("chapter_title", ""),
                "distance": vr.get("distance", 0.0),
                "source": "vector"
            })

        return formatted_results

    def keyword_search_only(
        self,
        query: str,
        top_k: int = 5,
        collection: str = "gazetteer_chunks"
    ) -> List[Dict]:
        """
        Perform BM25 keyword-only search.

        Args:
            query: The search query string.
            top_k: Number of results to return.
            collection: Collection name (used for caching).

        Returns:
            List of dicts with keys: text, chapter_title, distance, source.
        """
        bm25_index = self._bm25_data[collection]["index"]
        bm25_metadata = self._bm25_data[collection]["metadata"]

        if not bm25_index or not bm25_index.corpus:
            logger.warning(f"BM25 index not built for collection '{collection}'")
            return []

        results = bm25_index.search(query, top_k=top_k)
        formatted_results = []

        for br in results:
            idx = br["index"]
            metadata = bm25_metadata[idx] if bm25_metadata and idx < len(bm25_metadata) else {}
            formatted_results.append({
                "text": br["text"],
                "chapter_title": metadata.get("chapter_title", ""),
                "distance": br["score"],
                "source": "bm25"
            })

        return formatted_results
