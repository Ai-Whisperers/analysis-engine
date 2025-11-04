"""
RAG layer - Sharded SQLite + vector embeddings for semantic search.

Responsibilities:
- Store processed data in sharded SQLite (100x write throughput)
- Generate embeddings with sentence-transformers
- FAISS vector search (CPU-only, free tier)
- Semantic search and retrieval
"""

from .database import ShardedDatabase, DatabaseShard
from .embeddings import EmbeddingGenerator, VectorSearch

__all__ = ["ShardedDatabase", "DatabaseShard", "EmbeddingGenerator", "VectorSearch"]
