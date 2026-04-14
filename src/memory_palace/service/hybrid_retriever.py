"""HybridRetriever — FTS5 + Vector hybrid search with Reciprocal Rank Fusion.

Combines RecallStore.search() (FTS5 BM25) with ArchivalStore.search()
(vector cosine similarity) via RRF, then re-scores with the enhanced
four-factor ScoringEngine.

Falls back to FTS5-only when archival_store is None (backward compatible).

Ref: SPEC_V02 §2.4 HybridRetriever, §RRF 算法
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING

import structlog

from memory_palace.engine.scoring import ScoredCandidate, normalize_bm25, rank
from memory_palace.models.memory import MemoryItem

if TYPE_CHECKING:
    from memory_palace.foundation.embedding import EmbeddingProvider
    from memory_palace.store.archival_store import ArchivalStore
    from memory_palace.store.graph_store import GraphStore
    from memory_palace.store.recall_store import RecallStore

logger = structlog.get_logger(__name__)


# ── RRF Algorithm ───────────────────────────────────────────


def reciprocal_rank_fusion(
    rankings: list[list[str]],
    k: int = 60,
) -> list[tuple[str, float]]:
    """Merge multiple rankings via Reciprocal Rank Fusion.

    rrf_score(d) = Σ 1 / (k + rank_i(d))

    Args:
        rankings: List of ranked document ID lists.
        k: RRF constant (default 60, standard value from Cormack et al.).

    Returns:
        Sorted list of (doc_id, rrf_score), highest score first.
    """
    if not rankings:
        return []

    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for position, doc_id in enumerate(ranking):
            # position is 0-indexed; rank_i(d) = position + 1 in the formula
            scores[doc_id] += 1.0 / (k + position + 1)

    # Sort by RRF score descending
    sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return sorted_results


# ── HybridRetriever ─────────────────────────────────────────


class HybridRetriever:
    """FTS5 (keyword) + Vector (semantic) hybrid retrieval.

    Workflow:
    1. Parallel: FTS5 search → keyword candidates
                 Vector search → semantic candidates
    2. Reciprocal Rank Fusion (RRF) to de-dup & merge
    3. Re-score with enhanced four-factor + room bonus
    4. Return top_k

    When archival_store is None, automatically degrades to FTS5-only
    (equivalent to v0.1 Retriever behavior).

    Args:
        recall_store: RecallStore instance for FTS5 keyword search.
        archival_store: ArchivalStore for vector semantic search (None = FTS5-only).
        embedding: EmbeddingProvider for computing query vectors (None = FTS5-only).
        graph_store: GraphStore for real proximity scoring (None = binary 0/1 fallback).
    """

    def __init__(
        self,
        recall_store: RecallStore,
        archival_store: ArchivalStore | None = None,
        embedding: EmbeddingProvider | None = None,
        graph_store: GraphStore | None = None,
    ) -> None:
        self._recall_store = recall_store
        self._archival_store = archival_store
        self._embedding = embedding
        self._graph_store = graph_store

        self._hybrid_enabled = archival_store is not None and embedding is not None

    async def search(
        self,
        query: str,
        top_k: int = 5,
        room: str | None = None,
        min_importance: float = 0.0,
    ) -> list[MemoryItem]:
        """Search across FTS5 + Vector channels, fuse, re-score, return top_k.

        Args:
            query: Search query string.
            top_k: Maximum results to return.
            room: Optional room filter.
            min_importance: Minimum importance threshold.

        Returns:
            Ranked list of MemoryItems, highest score first.
        """
        # Empty query fallback
        if not query or not query.strip():
            return self._empty_query_fallback(top_k, room, min_importance)

        if self._hybrid_enabled:
            return await self._hybrid_search(query, top_k, room, min_importance)
        else:
            return self._fts_only_search(query, top_k, room, min_importance)

    # ── Private: FTS5-only (v0.1 equivalent) ────────────────

    def _fts_only_search(
        self,
        query: str,
        top_k: int,
        room: str | None,
        min_importance: float,
    ) -> list[MemoryItem]:
        """FTS5-only search with three-factor scoring (v0.1 path)."""
        results = self._recall_store.search(query, room=room, limit=top_k * 3)

        if not results:
            return []

        # Filter by min_importance
        if min_importance > 0.0:
            results = [r for r in results if r["item"].importance >= min_importance]

        if not results:
            return []

        # Build ScoredCandidate list
        now = datetime.now()
        all_ranks = [r["rank"] for r in results]
        candidates = []

        for r in results:
            item = r["item"]
            delta = (now - item.accessed_at).total_seconds() / 3600
            proximity = self._compute_proximity(room, item.room)
            candidates.append(
                ScoredCandidate(
                    item=item,
                    recency_hours=max(0.0, delta),
                    importance=item.importance,
                    relevance=normalize_bm25(r["rank"], all_ranks),
                    proximity=proximity,
                )
            )

        ranked = rank(candidates)[:top_k]

        # Touch returned items
        for item in ranked:
            self._recall_store.touch(item.id)

        return ranked

    # ── Private: Hybrid (FTS5 + Vector) ─────────────────────

    async def _hybrid_search(
        self,
        query: str,
        top_k: int,
        room: str | None,
        min_importance: float,
    ) -> list[MemoryItem]:
        """Full hybrid: parallel FTS5 + Vector → RRF → re-score."""
        fetch_limit = top_k * 3

        # Channel 1: FTS5 keyword search
        fts_results = self._recall_store.search(query, room=room, limit=fetch_limit)
        fts_id_to_item: dict[str, MemoryItem] = {}
        fts_ranking: list[str] = []
        for r in fts_results:
            item = r["item"]
            if min_importance > 0.0 and item.importance < min_importance:
                continue
            fts_id_to_item[item.id] = item
            fts_ranking.append(item.id)

        # Channel 2: Vector semantic search
        assert self._archival_store is not None  # guarded by _hybrid_enabled
        vector_results = await self._archival_store.search(
            query, top_k=fetch_limit, room=room, min_importance=min_importance
        )
        vector_ranking: list[str] = [r["id"] for r in vector_results]
        vector_distances: dict[str, float] = {
            r["id"]: r.get("distance", 0.0) for r in vector_results
        }

        # RRF fusion
        rankings = [fts_ranking, vector_ranking]
        fused = reciprocal_rank_fusion(rankings)

        if not fused:
            return []

        # Resolve MemoryItems: prefer FTS5 (has full MemoryItem), else fetch from recall
        now = datetime.now()
        all_fts_ranks = [r["rank"] for r in fts_results] if fts_results else []
        fts_rank_map = {r["item"].id: r["rank"] for r in fts_results}

        candidates: list[ScoredCandidate] = []
        for doc_id, rrf_score in fused:
            # Get the MemoryItem
            item = fts_id_to_item.get(doc_id)
            if item is None:
                # Item came from vector-only; fetch from RecallStore
                item = self._recall_store.get(doc_id)
            if item is None:
                logger.debug("hybrid_skip_missing_item", id=doc_id)
                continue

            # Apply min_importance filter (for vector-only items)
            if min_importance > 0.0 and item.importance < min_importance:
                continue

            # Compute relevance: use BM25 if available, else convert vector distance
            if doc_id in fts_rank_map:
                relevance = normalize_bm25(fts_rank_map[doc_id], all_fts_ranks)
            elif doc_id in vector_distances:
                # ChromaDB cosine distance → similarity: sim = 1 - distance
                relevance = max(0.0, 1.0 - vector_distances[doc_id])
            else:
                relevance = 0.0

            delta = (now - item.accessed_at).total_seconds() / 3600
            proximity = self._compute_proximity(room, item.room)

            candidates.append(
                ScoredCandidate(
                    item=item,
                    recency_hours=max(0.0, delta),
                    importance=item.importance,
                    relevance=relevance,
                    proximity=proximity,
                )
            )

        ranked = rank(candidates)[:top_k]

        # Touch returned items
        for item in ranked:
            self._recall_store.touch(item.id)

        return ranked

    # ── Private: Proximity computation ─────────────────────

    def _compute_proximity(
        self, query_room: str | None, memory_room: str
    ) -> float:
        """Compute proximity score using GraphStore or binary fallback."""
        if not query_room:
            return 0.0
        if self._graph_store is not None:
            return self._graph_store.proximity_score(query_room, memory_room)
        # Fallback: binary match (v0.1 behaviour)
        return 1.0 if memory_room == query_room else 0.0

    # ── Private: Empty query fallback ───────────────────────

    def _empty_query_fallback(
        self,
        top_k: int,
        room: str | None,
        min_importance: float,
    ) -> list[MemoryItem]:
        """Return most recent items when query is empty."""
        items = self._recall_store.get_recent(top_k * 3)

        if room is not None:
            items = [i for i in items if i.room == room]
        if min_importance > 0.0:
            items = [i for i in items if i.importance >= min_importance]

        items = items[:top_k]

        for item in items:
            self._recall_store.touch(item.id)

        return items
