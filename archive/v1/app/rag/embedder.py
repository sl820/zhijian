"""
Vector embedder for RAG (Retrieval-Augmented Generation) using Ollama or BGE model.
"""

import logging
import json
import urllib.request
import urllib.error
from typing import List, Optional

import torch

logger = logging.getLogger(__name__)

# Default BGE model for Chinese text
DEFAULT_MODEL_NAME = "BAAI/bge-base-chinese-v1.5"
EMBEDDING_DIM = 768

# Ollama embedding configuration
OLLAMA_EMBEDDING_URL = "http://localhost:11434/api/embeddings"
OLLAMA_EMBEDDING_MODEL = "nomic-embed-text"

# Fallback models in order of preference
FALLBACK_MODELS = [
    "BAAI/bge-base-chinese-v1.5",
    "shibing624/text2vec-base-chinese",
    "paraphrase-multilingual-MiniLM-L12-v2",
]


class Embedder:
    """
    Vector embedder using Ollama or BGE model for Chinese text.

    This class provides methods to encode texts and queries into dense vector
    embeddings suitable for similarity search and RAG pipelines.

    Attributes:
        model_name: Name or path of the BGE model to use.
        device: Device to run the model on (cuda or cpu).
        batch_size: Default batch size for encoding.
        max_length: Maximum sequence length for tokenization.
        use_ollama: Whether to use Ollama for embeddings (default: True).
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        device: str = None,
        batch_size: int = 32,
        max_length: int = 512,
        use_ollama: bool = True,
    ):
        """
        Initialize the embedder.

        Args:
            model_name: Name or path of the BGE model. Defaults to "BAAI/bge-base-chinese-v1.5".
            device: Device to run the model on. If None, uses CUDA if available, else CPU.
            batch_size: Default batch size for encoding multiple texts.
            max_length: Maximum sequence length for tokenization.
            use_ollama: Whether to use Ollama for embeddings (default: True).
        """
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.batch_size = batch_size
        self.max_length = max_length
        self.use_ollama = use_ollama
        self.model = None
        self.tokenizer = None
        self._loaded = False
        self._actual_dim = None
        self._ollama_available = None
        logger.info(
            f"Embedder initialized with model_name={self.model_name}, "
            f"device={self.device}, batch_size={self.batch_size}, max_length={self.max_length}, "
            f"use_ollama={self.use_ollama}"
        )

    def _check_ollama(self):
        """Check if Ollama embedding service is available."""
        if self._ollama_available is not None:
            return self._ollama_available

        try:
            req = urllib.request.Request(
                OLLAMA_EMBEDDING_URL,
                data=json.dumps({"model": OLLAMA_EMBEDDING_MODEL, "prompt": "test"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode("utf-8"))
                if "embedding" in result:
                    self._ollama_available = True
                    logger.info(f"Ollama embedding service available: {OLLAMA_EMBEDDING_MODEL}")
                    return True
        except Exception as e:
            logger.warning(f"Ollama embedding service not available: {e}")
        self._ollama_available = False
        return False

    def _load_model(self):
        """Lazy load the model and tokenizer with fallback support."""
        if self._loaded:
            return

        # First, try Ollama if enabled
        if self.use_ollama and self._check_ollama():
            logger.info(f"Using Ollama for embeddings: {OLLAMA_EMBEDDING_MODEL}")
            self.model = "ollama"  # Placeholder to indicate Ollama is being used
            self._loaded = True
            self._actual_dim = 768  # nomic-embed-text uses 768 dimensions
            return

        # Fall back to sentence-transformers models
        from sentence_transformers import SentenceTransformer

        # Try models in order of preference
        models_to_try = [self.model_name] + FALLBACK_MODELS
        tried_models = []

        for model_name in models_to_try:
            if model_name in tried_models:
                continue
            tried_models.append(model_name)

            try:
                logger.info(f"Trying to load embedder model: {model_name}...")
                self.model = SentenceTransformer(model_name, device=self.device, local_files_only=True)
                self.model_name = model_name
                self._loaded = True
                logger.info(f"Successfully loaded embedder model: {model_name}")
                return
            except Exception as e:
                logger.warning(f"Failed to load model {model_name}: {str(e)[:100]}")

        # If all models fail, create a simple TF-IDF based embedder
        logger.error("All embedding models failed to load, using TF-IDF fallback")
        self.model = None
        self._loaded = True

    def load_model(self):
        """
        Public method to explicitly load the embedder model.
        Alias for _load_model() for compatibility.
        """
        self._load_model()

    def _ensure_model_loaded(self):
        """Ensure the model is loaded before encoding."""
        if not self._loaded:
            self._load_model()

    def encode(self, texts: List[str], batch_size: int = None, show_progress: bool = False) -> List[List[float]]:
        """
        Encode a list of texts into dense vector embeddings.

        Args:
            texts: List of input text strings to encode.
            batch_size: Batch size for encoding. If None, uses the default from __init__.
            show_progress: Whether to show progress bar during encoding.

        Returns:
            List of embedding vectors, each as a list of floats (768 dimensions for bge-base-chinese-v1.5).

        Raises:
            ValueError: If texts is empty.
        """
        self._ensure_model_loaded()

        if not texts:
            return []

        batch_size = batch_size or self.batch_size

        logger.debug(f"Encoding {len(texts)} texts with batch_size={batch_size}")

        # Use Ollama if available
        if self.model == "ollama":
            return self._ollama_encode_batch(texts)

        # If model loading failed, use TF-IDF fallback
        if self.model is None:
            return self._tfidf_encode(texts, fit_on_corpus=True)

        try:
            from flagembedding import FlagModel
            # flagembedding handles batching internally and returns numpy arrays
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
            )
            # Convert to list of floats
            return [emb.tolist() if hasattr(emb, 'tolist') else list(emb) for emb in embeddings]
        except Exception:
            # Fallback to sentence-transformers
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
            )
            return embeddings.tolist()

    def _ollama_encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encode texts using Ollama's embedding API."""
        embeddings = []
        for text in texts:
            try:
                payload = json.dumps({
                    "model": OLLAMA_EMBEDDING_MODEL,
                    "prompt": text
                }).encode("utf-8")

                req = urllib.request.Request(
                    OLLAMA_EMBEDDING_URL,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )

                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    embeddings.append(result["embedding"])
            except Exception as e:
                logger.warning(f"Ollama encoding failed for text: {e}, using zero vector")
                embeddings.append([0.0] * 768)

        return embeddings

    def _tfidf_encode(self, texts: List[str], fit_on_corpus: bool = False) -> List[List[float]]:
        """
        Simple TF-IDF based encoding fallback when transformer models are unavailable.

        Args:
            texts: List of input text strings to encode.
            fit_on_corpus: If True, fit on these texts as corpus. If False, only transform
                          using existing fitted vocabulary (for queries after corpus encoding).
        """
        from sklearn.feature_extraction.text import TfidfVectorizer

        if not hasattr(self, '_tfidf_vectorizer'):
            self._tfidf_vectorizer = TfidfVectorizer(max_features=768)
            self._corpus_fitted = False
            self._actual_dim = None

        # For corpus encoding: always fit if not already corpus-fitted
        if fit_on_corpus and not self._corpus_fitted:
            self._tfidf_vectorizer.fit(texts)
            self._corpus_fitted = True
            self._actual_dim = len(self._tfidf_vectorizer.vocabulary_)
            logger.info(f"TF-IDF fitted on corpus ({len(texts)} texts): actual_dim={self._actual_dim}")

        vectors = []
        for text in texts:
            try:
                vec = self._tfidf_vectorizer.transform([text]).toarray()[0].tolist()
                vectors.append(vec)
            except ValueError:
                # Query vocabulary not in fitted corpus - use zero vector
                logger.debug("Query term not in fitted vocabulary, using zero vector")
                dim = self._actual_dim if self._actual_dim else EMBEDDING_DIM
                vectors.append([0.0] * dim)

        return vectors

    @property
    def embedding_dim(self) -> int:
        """
        Get the dimension of the embedding vectors.

        Returns:
            The embedding dimension (actual TF-IDF vocabulary size if corpus-fitted, else 768).
        """
        if self._actual_dim is not None:
            return self._actual_dim
        return EMBEDDING_DIM

    def encode_query(self, query: str) -> List[float]:
        """
        Encode a single query into a dense vector embedding.

        This method is optimized for query encoding and may apply different
        preprocessing compared to document encoding.

        Args:
            query: Input query string to encode.

        Returns:
            Query embedding vector as a list of floats (768 dimensions).

        Raises:
            ValueError: If query is empty.
        """
        self._ensure_model_loaded()

        if not query:
            raise ValueError("Query cannot be empty")

        logger.debug(f"Encoding query: {query[:50]}...")

        # Use Ollama if available
        if self.model == "ollama":
            try:
                payload = json.dumps({
                    "model": OLLAMA_EMBEDDING_MODEL,
                    "prompt": query
                }).encode("utf-8")

                req = urllib.request.Request(
                    OLLAMA_EMBEDDING_URL,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )

                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    return result["embedding"]
            except Exception as e:
                logger.warning(f"Ollama query encoding failed: {e}, using zero vector")
                return [0.0] * 768

        # If model loading failed, use TF-IDF fallback
        if self.model is None:
            # Use fit_on_corpus=False to avoid contaminating the vectorizer with query vocabulary
            vectors = self._tfidf_encode([query], fit_on_corpus=False)
            # _tfidf_encode returns zero vectors if not corpus-fitted yet
            return vectors[0] if vectors else [0.0] * EMBEDDING_DIM

        try:
            from flagembedding import FlagModel
            # FlagModel has a separate encode_query method optimized for queries
            if hasattr(self.model, 'encode_queries'):
                embedding = self.model.encode_queries([query])[0]
            else:
                embedding = self.model.encode([query])[0]
            return embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
        except ImportError:
            # Fallback to sentence-transformers
            embedding = self.model.encode(query, convert_to_numpy=True)
            return embedding.tolist()

    def encode_query_batch(self, queries: List[str], batch_size: int = None) -> List[List[float]]:
        """
        Encode a batch of queries into dense vector embeddings.

        This method is optimized for batch query encoding.

        Args:
            queries: List of input query strings to encode.
            batch_size: Batch size for encoding. If None, uses the default from __init__.

        Returns:
            List of query embedding vectors.
        """
        self._ensure_model_loaded()

        if not queries:
            return []

        batch_size = batch_size or self.batch_size

        logger.debug(f"Encoding {len(queries)} queries with batch_size={batch_size}")

        try:
            from flagembedding import FlagModel
            if hasattr(self.model, 'encode_queries'):
                embeddings = self.model.encode_queries(queries, batch_size=batch_size)
            else:
                embeddings = self.model.encode(queries, batch_size=batch_size)
            return [emb.tolist() if hasattr(emb, 'tolist') else list(emb) for emb in embeddings]
        except ImportError:
            embeddings = self.model.encode(queries, batch_size=batch_size, convert_to_numpy=True)
            return embeddings.tolist()

    def __repr__(self) -> str:
        return (
            f"Embedder(model_name={self.model_name}, device={self.device}, "
            f"batch_size={self.batch_size}, max_length={self.max_length}, loaded={self._loaded})"
        )
