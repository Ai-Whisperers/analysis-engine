"""
Embedding generation and vector search with FAISS (CPU-only).

Model: all-MiniLM-L6-v2 (384 dimensions, 23MB)
- Fast on CPU (40ms per embedding)
- Good quality (semantic search)
- Free tier friendly
"""

import pickle
from pathlib import Path
from typing import List, Optional, Tuple

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from shared.security import CircuitBreaker, CircuitBreakerOpen
from shared.telemetry import MetricsCollector, StructuredLogger

logger = StructuredLogger(__name__)


class EmbeddingGenerator:
    """
    Generate embeddings with sentence-transformers.

    Features:
    - CPU-optimized model (free tier)
    - Batch processing
    - Circuit breaker (fault tolerance)
    - Caching
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: str = "cpu",
    ):
        """
        Initialize embedding generator.

        Args:
            model_name: SentenceTransformers model name
            device: Device to use (cpu, cuda)
        """
        self.model_name = model_name
        self.device = device

        logger.info(
            "Loading embedding model",
            model_name=model_name,
            device=device,
        )

        # Circuit breaker for model loading
        breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=60,
            name="embedding_model_loader",
        )

        try:
            self.model = breaker.call(
                SentenceTransformer, model_name, device=device
            )
            logger.info("Embedding model loaded successfully")
        except CircuitBreakerOpen as e:
            logger.error(
                "Failed to load embedding model - circuit breaker open",
                error=str(e),
            )
            raise
        except Exception as e:
            logger.error(
                "Failed to load embedding model",
                error=str(e),
            )
            raise

    def generate_embeddings(
        self, texts: List[str], batch_size: int = 32
    ) -> np.ndarray:
        """
        Generate embeddings for texts.

        Args:
            texts: List of texts
            batch_size: Batch size for processing

        Returns:
            Numpy array of embeddings (shape: [num_texts, embedding_dim])
        """
        import time

        start_time = time.time()

        # Generate embeddings
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
        )

        duration = time.time() - start_time

        logger.log_performance(
            operation="generate_embeddings",
            duration_ms=duration * 1000,
            records_processed=len(texts),
        )

        MetricsCollector.record_processing(
            layer="rag-layer",
            operation="embeddings",
            records=len(texts),
            duration_seconds=duration,
        )

        return embeddings

    def serialize_embedding(self, embedding: np.ndarray) -> bytes:
        """
        Serialize embedding for database storage.

        Args:
            embedding: Numpy array

        Returns:
            Serialized bytes
        """
        return pickle.dumps(embedding)

    def deserialize_embedding(self, data: bytes) -> np.ndarray:
        """
        Deserialize embedding from database.

        Args:
            data: Serialized bytes

        Returns:
            Numpy array
        """
        return pickle.loads(data)


class VectorSearch:
    """
    FAISS vector search (CPU-only, free tier).

    Features:
    - Fast approximate search (HNSW index)
    - CPU-optimized (no GPU needed)
    - Persistent index
    - Semantic similarity search
    """

    def __init__(
        self,
        embedding_dim: int = 384,
        index_type: str = "HNSW",
    ):
        """
        Initialize vector search index.

        Args:
            embedding_dim: Dimension of embeddings (384 for all-MiniLM-L6-v2)
            index_type: FAISS index type (HNSW for CPU)
        """
        self.embedding_dim = embedding_dim
        self.index_type = index_type

        # Create FAISS index
        if index_type == "HNSW":
            # HNSW (Hierarchical Navigable Small World) - best for CPU
            self.index = faiss.IndexHNSWFlat(embedding_dim, 32)  # 32 = M parameter
        else:
            # Fallback to flat index (exact search)
            self.index = faiss.IndexFlatL2(embedding_dim)

        self.id_map: List[int] = []  # Map FAISS index to record IDs

        logger.info(
            "Vector search index initialized",
            index_type=index_type,
            embedding_dim=embedding_dim,
        )

    def add_embeddings(
        self, embeddings: np.ndarray, record_ids: List[int]
    ) -> None:
        """
        Add embeddings to index.

        Args:
            embeddings: Numpy array of embeddings (shape: [num_records, embedding_dim])
            record_ids: List of record IDs
        """
        # Ensure float32
        embeddings = embeddings.astype(np.float32)

        # Normalize embeddings (for cosine similarity)
        faiss.normalize_L2(embeddings)

        # Add to index
        self.index.add(embeddings)

        # Update ID map
        self.id_map.extend(record_ids)

        logger.info(
            "Embeddings added to index",
            count=len(record_ids),
            total_size=self.index.ntotal,
        )

    def search(
        self, query_embedding: np.ndarray, k: int = 10
    ) -> Tuple[List[int], List[float]]:
        """
        Search for similar vectors.

        Args:
            query_embedding: Query embedding (shape: [embedding_dim])
            k: Number of results to return

        Returns:
            Tuple of (record_ids, distances)
        """
        import time

        start_time = time.time()

        # Ensure 2D array
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)

        # Ensure float32
        query_embedding = query_embedding.astype(np.float32)

        # Normalize
        faiss.normalize_L2(query_embedding)

        # Search
        distances, indices = self.index.search(query_embedding, k)

        # Map indices to record IDs
        record_ids = [self.id_map[idx] for idx in indices[0] if idx < len(self.id_map)]
        distances_list = distances[0].tolist()

        duration = time.time() - start_time

        logger.log_performance(
            operation="vector_search",
            duration_ms=duration * 1000,
            records_processed=k,
        )

        return record_ids, distances_list

    def save(self, path: str) -> None:
        """
        Save index to disk.

        Args:
            path: Path to save index
        """
        path_obj = Path(path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        faiss.write_index(self.index, str(path_obj))

        # Save ID map
        id_map_path = path_obj.with_suffix(".idmap")
        with open(id_map_path, "wb") as f:
            pickle.dump(self.id_map, f)

        logger.info(
            "Vector index saved",
            path=path,
            size=self.index.ntotal,
        )

    def load(self, path: str) -> None:
        """
        Load index from disk.

        Args:
            path: Path to load index from
        """
        path_obj = Path(path)

        # Load FAISS index
        self.index = faiss.read_index(str(path_obj))

        # Load ID map
        id_map_path = path_obj.with_suffix(".idmap")
        with open(id_map_path, "rb") as f:
            self.id_map = pickle.load(f)

        logger.info(
            "Vector index loaded",
            path=path,
            size=self.index.ntotal,
        )
