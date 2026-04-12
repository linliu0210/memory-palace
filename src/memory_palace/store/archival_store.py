"""ArchivalStore — ChromaDB vector storage (全量语义索引层).

Stores embeddings for ALL memories regardless of tier, enabling
semantic similarity search across the entire memory space.

Uses ChromaDB PersistentClient for durability. In tests, use
EphemeralClient via the ``client`` constructor parameter.

Ref: SPEC_V02 §2.2 (F-1), §1.4
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import chromadb

if TYPE_CHECKING:
    from memory_palace.foundation.embedding import EmbeddingProvider
    from memory_palace.models.memory import MemoryItem

import structlog

logger = structlog.get_logger()


class ArchivalStore:
    """ChromaDB-backed vector store for semantic search.

    All memories are indexed here with their embeddings, allowing
    full-corpus semantic retrieval regardless of importance tier.

    Args:
        data_dir: Root data directory. ChromaDB persisted at ``{data_dir}/archival/``.
        embedding: EmbeddingProvider for computing query vectors.
        client: Optional pre-configured ChromaDB client (for testing with EphemeralClient).
        collection_name: ChromaDB collection name (default: ``"memory_palace"``).
    """

    def __init__(
        self,
        data_dir: Path | None = None,
        embedding: EmbeddingProvider | None = None,
        client: chromadb.ClientAPI | None = None,
        collection_name: str = "memory_palace",
    ) -> None:
        self._embedding = embedding

        if client is not None:
            self._client = client
        elif data_dir is not None:
            archival_path = data_dir / "archival"
            archival_path.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(archival_path))
        else:
            raise ValueError("Either data_dir or client must be provided")

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    async def insert(self, item: MemoryItem, embedding: list[float] | None = None) -> None:
        """Insert a memory item into the vector store.

        If ``embedding`` is not provided and ``self._embedding`` is set,
        computes the embedding from ``item.content``.

        Args:
            item: The MemoryItem to index.
            embedding: Pre-computed embedding vector. If None, uses the provider.

        Raises:
            ValueError: If no embedding is provided and no provider is configured.
        """
        if embedding is None:
            if self._embedding is None:
                raise ValueError("No embedding provided and no EmbeddingProvider configured")
            vectors = await self._embedding.embed([item.content])
            embedding = vectors[0]

        metadata = self._build_metadata(item)

        # ChromaDB .add() silently ignores duplicates — use upsert for idempotency
        self._collection.upsert(
            ids=[item.id],
            documents=[item.content],
            embeddings=[embedding],
            metadatas=[metadata],
        )

    async def search(
        self,
        query: str,
        top_k: int = 5,
        room: str | None = None,
        min_importance: float = 0.0,
    ) -> list[dict]:
        """Search for similar memories by semantic similarity.

        Args:
            query: Search query text.
            top_k: Maximum number of results.
            room: Optional room filter.
            min_importance: Minimum importance threshold.

        Returns:
            List of dicts: ``{"id": str, "content": str, "distance": float, "metadata": dict}``.
            Sorted by distance ascending (most similar first).

        Raises:
            ValueError: If no EmbeddingProvider is configured.
        """
        if self._embedding is None:
            raise ValueError("No EmbeddingProvider configured for search")

        if self._collection.count() == 0:
            return []

        query_vectors = await self._embedding.embed([query])

        where_filter = self._build_where_filter(room, min_importance)

        try:
            results = self._collection.query(
                query_embeddings=query_vectors,
                n_results=min(top_k, self._collection.count()),
                where=where_filter if where_filter else None,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            logger.warning("archival_search_error", error=str(e))
            return []

        return self._unpack_query_results(results)

    def get(self, memory_id: str) -> dict | None:
        """Get a single record by ID.

        Args:
            memory_id: The memory ID to look up.

        Returns:
            Dict with ``id``, ``content``, ``metadata`` if found, else None.
        """
        result = self._collection.get(ids=[memory_id], include=["documents", "metadatas"])

        if not result["ids"]:
            return None

        return {
            "id": result["ids"][0],
            "content": result["documents"][0] if result["documents"] else None,
            "metadata": result["metadatas"][0] if result["metadatas"] else None,
        }

    def count(self) -> int:
        """Return total number of indexed items."""
        return self._collection.count()

    def delete(self, memory_id: str) -> None:
        """Delete a record by ID.

        Args:
            memory_id: The memory ID to delete.
        """
        self._collection.delete(ids=[memory_id])

    # ── Private helpers ──────────────────────────────────────────────

    @staticmethod
    def _build_metadata(item: MemoryItem) -> dict:
        """Extract metadata dict from a MemoryItem for ChromaDB storage.

        ChromaDB metadata values must be str, int, float, or bool.
        Lists are serialized to JSON strings.
        """
        return {
            "tier": str(item.tier),
            "room": item.room,
            "importance": float(item.importance),
            "status": str(item.status),
            "tags": json.dumps(item.tags) if item.tags else "[]",
            "memory_type": str(item.memory_type),
        }

    @staticmethod
    def _build_where_filter(
        room: str | None = None,
        min_importance: float = 0.0,
    ) -> dict | None:
        """Build a ChromaDB where filter from search parameters."""
        conditions = []

        # Always filter for active status
        conditions.append({"status": {"$eq": "active"}})

        if room is not None:
            conditions.append({"room": {"$eq": room}})

        if min_importance > 0.0:
            conditions.append({"importance": {"$gte": min_importance}})

        if len(conditions) == 1:
            return conditions[0]
        elif len(conditions) > 1:
            return {"$and": conditions}
        return None

    @staticmethod
    def _unpack_query_results(results: dict) -> list[dict]:
        """Unpack ChromaDB column-major query results into row dicts."""
        if not results["ids"] or not results["ids"][0]:
            return []

        unpacked = []
        ids = results["ids"][0]
        documents = results["documents"][0] if results["documents"] else [None] * len(ids)
        distances = results["distances"][0] if results["distances"] else [0.0] * len(ids)
        metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(ids)

        for i, doc_id in enumerate(ids):
            unpacked.append(
                {
                    "id": doc_id,
                    "content": documents[i],
                    "distance": distances[i],
                    "metadata": metadatas[i],
                }
            )

        return unpacked
