"""Retriever — FTS5 + three-factor scoring search.

Combines RecallStore.search() (FTS5 BM25) with ScoringEngine
ranking (recency × importance × relevance) to return ranked results.

Ref: SPEC v2.0 §4.1 S-14, §4.6
"""

from __future__ import annotations

from datetime import datetime

import structlog

from memory_palace.engine.scoring import normalize_bm25, rank
from memory_palace.models.memory import MemoryItem
from memory_palace.store.recall_store import RecallStore

logger = structlog.get_logger(__name__)


class Retriever:
    """Search recall memory with FTS5 + three-factor scoring.

    Wraps RecallStore.search() results with ScoringEngine ranking,
    then touches accessed items to update their access_count.

    Args:
        recall_store: RecallStore instance to search against.
    """

    def __init__(self, recall_store: RecallStore) -> None:
        self._recall_store = recall_store

    def search(
        self,
        query: str,
        top_k: int = 5,
        room: str | None = None,
        min_importance: float = 0.0,
    ) -> list[MemoryItem]:
        """Search recall memory, rank by combined score, return top_k.

        Workflow:
        1. Empty query → fallback to get_recent(top_k).
        2. FTS5 search → get raw BM25 ranks.
        3. Compute parallel arrays for scoring.rank().
        4. Truncate to top_k.
        5. Touch returned items (increment access_count).

        Args:
            query: Search query string.
            top_k: Maximum results to return.
            room: Optional room filter.
            min_importance: Minimum importance threshold.

        Returns:
            Ranked list of MemoryItems, highest score first.
        """
        # Empty query fallback — still apply room/min_importance filters
        if not query or not query.strip():
            items = self._recall_store.get_recent(top_k * 3)  # over-fetch for filtering
            if room is not None:
                items = [i for i in items if i.room == room]
            if min_importance > 0.0:
                items = [i for i in items if i.importance >= min_importance]
            items = items[:top_k]
            for item in items:
                self._recall_store.touch(item.id)
            return items

        # FTS5 search → list[dict] with "item" and "rank" keys
        results = self._recall_store.search(query, room=room, limit=top_k * 3)

        if not results:
            return []

        # Filter by min_importance
        if min_importance > 0.0:
            results = [r for r in results if r["item"].importance >= min_importance]

        if not results:
            return []

        # Extract parallel arrays for scoring.rank()
        items = [r["item"] for r in results]
        now = datetime.now()

        recency_hours = []
        for item in items:
            delta = (now - item.accessed_at).total_seconds() / 3600
            recency_hours.append(max(0.0, delta))

        importances = [item.importance for item in items]

        # Normalize BM25 ranks
        all_ranks = [r["rank"] for r in results]
        relevances = [normalize_bm25(r["rank"], all_ranks) for r in results]

        # Rank using scoring engine
        ranked = rank(items, recency_hours, importances, relevances)

        # Truncate to top_k
        ranked = ranked[:top_k]

        # Touch returned items
        for item in ranked:
            self._recall_store.touch(item.id)

        return ranked
