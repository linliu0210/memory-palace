"""MemoryService — CRUD facade for the Memory Palace.

Coordinates Store (CoreStore + RecallStore + ArchivalStore), Engine
(FactExtractor), AuditLog, and Retriever to provide a unified memory API.

v0.2 upgrades:
- get_by_id(): three-tier lookup (TD-4)
- get_core_context(): active-only filter (TD-2)
- save(): all items indexed in ArchivalStore + Core budget check (TD-7)
- update(): uses update_field() (TD-1 final fix)

Ref: SPEC v2.0 §4.1 S-13, §4.4, SPEC_V02 §6.2
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from memory_palace.engine.fact_extractor import FactExtractor
from memory_palace.engine.metrics import OperationTimer, get_metrics
from memory_palace.foundation.audit_log import AuditAction, AuditEntry, AuditLog
from memory_palace.foundation.llm import LLMProvider
from memory_palace.models.memory import (
    MemoryItem,
    MemoryStatus,
    MemoryTier,
    MemoryType,
)
from memory_palace.service.retriever import Retriever
from memory_palace.store.core_store import CoreStore
from memory_palace.store.recall_store import RecallStore

if TYPE_CHECKING:
    from memory_palace.foundation.embedding import EmbeddingProvider
    from memory_palace.service.curator import CuratorService
    from memory_palace.service.scheduler import SleepTimeScheduler
    from memory_palace.store.archival_store import ArchivalStore
    from memory_palace.store.graph_store import GraphStore

logger = structlog.get_logger(__name__)

# Core budget: max items per block before auto-demote (SPEC §4.1 S-8)
CORE_MAX_ITEMS_PER_BLOCK = 10


class MemoryService:
    """CRUD facade for memory operations.

    Routes high-importance items to CoreStore, others to RecallStore.
    All items are indexed in ArchivalStore (when available) for semantic search.
    All mutations are audited through AuditLog.

    Args:
        data_dir: Root data directory for stores and audit log.
        llm: Optional LLM provider (needed for save_batch via FactExtractor).
        archival_store: Optional ArchivalStore for vector indexing.
        embedding: Optional EmbeddingProvider for computing embeddings.
        graph_store: Optional GraphStore for KuzuDB graph proximity scoring.
    """

    def __init__(
        self,
        data_dir: Path,
        llm: LLMProvider | None = None,
        archival_store: ArchivalStore | None = None,
        embedding: EmbeddingProvider | None = None,
        graph_store: GraphStore | None = None,
    ) -> None:
        self._data_dir = data_dir
        self._core_store = CoreStore(data_dir)
        self._recall_store = RecallStore(data_dir)
        self._audit_log = AuditLog(data_dir)
        self._retriever = Retriever(self._recall_store)
        self._llm = llm
        self._archival_store = archival_store
        self._embedding = embedding
        self._graph_store = graph_store
        if llm is not None:
            self._fact_extractor = FactExtractor(llm)
        else:
            self._fact_extractor = None

        # R19: asyncio write lock for concurrency safety
        self._write_lock = asyncio.Lock()

        # R23: operational metrics collection
        self._metrics = get_metrics()

        # Optional scheduler and curator integration (R14)
        self._scheduler: SleepTimeScheduler | None = None
        self._curator: CuratorService | None = None

    def set_scheduler(self, scheduler: SleepTimeScheduler) -> None:
        """Inject optional SleepTimeScheduler for background curation.

        Args:
            scheduler: The scheduler instance to notify on save operations.
        """
        self._scheduler = scheduler

    def save(
        self,
        content: str,
        importance: float | None = None,
        tags: list[str] | None = None,
        room: str = "general",
        memory_type: MemoryType = MemoryType.OBSERVATION,
    ) -> MemoryItem:
        """Save a new memory. Routes to Core or Recall by importance.

        v0.2 changes:
        - Core budget check: auto-demote oldest if block exceeds limit (TD-7).
        - ArchivalStore indexing: all items indexed for semantic search.

        importance >= 0.7 → CoreStore (block = room)
        importance < 0.7 → RecallStore

        Args:
            content: Memory text content.
            importance: Importance score [0, 1]. None defaults to 0.5.
            tags: Optional tags list.
            room: Room name (namespace).
            memory_type: Type classification.

        Returns:
            The created MemoryItem.
        """
        if tags is None:
            tags = []
        if importance is None:
            importance = 0.5

        timer = OperationTimer("save")
        with timer:
            # Determine tier based on importance
            tier = MemoryTier.CORE if importance >= 0.7 else MemoryTier.RECALL

            item = MemoryItem(
                content=content,
                memory_type=memory_type,
                tier=tier,
                importance=importance,
                tags=tags,
                room=room,
            )

            # Route to appropriate store
            if tier == MemoryTier.CORE:
                existing = self._core_store.load(room)

                # TD-7: Core budget check — auto-demote oldest if over limit
                while len(existing) >= CORE_MAX_ITEMS_PER_BLOCK:
                    oldest = min(
                        (i for i in existing if i.status == MemoryStatus.ACTIVE),
                        key=lambda x: x.created_at,
                        default=None,
                    )
                    if oldest is None:
                        break  # all items are already non-active
                    # Demote to Recall
                    existing = [i for i in existing if i.id != oldest.id]
                    demoted = oldest.model_copy(update={"tier": MemoryTier.RECALL})
                    self._recall_store.insert(demoted)
                    logger.info(
                        "Core auto-demote",
                        memory_id=oldest.id,
                        room=room,
                    )

                existing.append(item)
                self._core_store.save(room, existing)
            else:
                self._recall_store.insert(item)

            # Audit
            self._audit_log.append(
                AuditEntry(
                    action=AuditAction.CREATE,
                    memory_id=item.id,
                    actor="user",
                    details={"content": content, "tier": tier, "room": room},
                )
            )

            logger.info("Memory saved", memory_id=item.id, tier=tier, room=room)

            # v0.2: Index ALL items in ArchivalStore for semantic search
            if self._archival_store is not None:
                try:
                    self._index_in_archival_sync(item)
                except Exception:
                    logger.warning("archival_index_failed", memory_id=item.id, exc_info=True)

            # R24: Sync to GraphStore (incremental, skip on error)
            if self._graph_store is not None:
                try:
                    self._graph_store.add_memory_node(item)
                except Exception:
                    logger.warning("graph_sync_failed", memory_id=item.id, exc_info=True)

            # R14: Notify scheduler and update curator tracking
            if self._curator is not None:
                self._curator.increment_session()
                self._curator.record_importance(importance)
            if self._scheduler is not None:
                self._scheduler.notify("save")

        self._metrics.record_save(timer.duration_ms)
        return item

    async def save_batch(self, texts: list[str]) -> list[MemoryItem]:
        """Batch save: extract facts from texts, then save each.

        Uses FactExtractor to parse texts into atomic facts,
        then saves each fact individually.

        Args:
            texts: List of text strings to extract facts from.

        Returns:
            List of saved MemoryItems.

        Raises:
            RuntimeError: If no LLM provider was configured.
        """
        if self._fact_extractor is None:
            raise RuntimeError("save_batch requires an LLM provider")

        saved: list[MemoryItem] = []
        for text in texts:
            facts = await self._fact_extractor.extract(text)
            for fact in facts:
                item = self.save(
                    content=fact.content,
                    importance=fact.importance,
                    tags=fact.tags,
                    room=fact.room,
                    memory_type=fact.memory_type,
                )
                saved.append(item)

        return saved

    async def search(
        self,
        query: str,
        top_k: int = 5,
        room: str | None = None,
        min_importance: float = 0.0,
    ) -> list[MemoryItem]:
        """Search memories, ranked by combined score.

        Uses HybridRetriever (FTS5 + Vector) when archival is configured,
        otherwise falls back to FTS5-only Retriever.

        Args:
            query: Search query string.
            top_k: Maximum results to return.
            room: Optional room filter.
            min_importance: Minimum importance threshold.

        Returns:
            Ranked list of MemoryItems, highest score first.
        """
        timer = OperationTimer("search")
        with timer:
            hybrid = self.get_hybrid_retriever()
            if hybrid is not None:
                results = await hybrid.search(
                    query=query,
                    top_k=top_k,
                    room=room,
                    min_importance=min_importance,
                )
            else:
                results = self._retriever.search(
                    query=query,
                    top_k=top_k,
                    room=room,
                    min_importance=min_importance,
                )
        self._metrics.record_search(timer.duration_ms)
        return results

    def get_by_id(self, memory_id: str) -> MemoryItem | None:
        """Get memory by ID from any tier (Core → Recall → Archival).

        Searches tiers in order: Core (all blocks), Recall (SQLite),
        then Archival (ChromaDB metadata only).

        Args:
            memory_id: The memory ID to look up.

        Returns:
            MemoryItem if found in Core or Recall, None otherwise.
            (Archival lookup returns metadata only — not a full MemoryItem.)

        Ref: TD-4 — route through MemoryService instead of direct store access.
        """
        # Tier 1: Core
        core_item = self._find_in_core(memory_id)
        if core_item is not None:
            return core_item

        # Tier 2: Recall
        recall_item = self._recall_store.get(memory_id)
        if recall_item is not None:
            return recall_item

        # Tier 3: Archival — metadata only (no full MemoryItem reconstruction)
        # Return None since Archival doesn't store full MemoryItem
        return None

    def _find_in_core(self, memory_id: str) -> MemoryItem | None:
        """Search all Core blocks for a memory by ID."""
        for block in self._core_store.list_blocks():
            for item in self._core_store.load(block):
                if item.id == memory_id:
                    return item
        return None

    def update(self, memory_id: str, new_content: str, reason: str) -> MemoryItem:
        """Update a memory: supersede old, create new version.

        Searches both Recall and Core tiers for the old item.

        v0.2: Uses RecallStore.update_field() instead of direct SQL (TD-1 final fix).

        Args:
            memory_id: ID of the memory to update.
            new_content: New content for the memory.
            reason: Reason for the update.

        Returns:
            The new MemoryItem version.

        Raises:
            ValueError: If the memory_id is not found in either tier.
        """
        # Find the old item — search Recall first, fallback to Core
        old_item = self._recall_store.get(memory_id)
        old_tier = MemoryTier.RECALL
        if old_item is None:
            old_item = self._find_in_core(memory_id)
            old_tier = MemoryTier.CORE
        if old_item is None:
            raise ValueError(f"Memory {memory_id} not found")

        # Create new version
        new_item = MemoryItem(
            content=new_content,
            memory_type=old_item.memory_type,
            tier=old_item.tier,
            importance=old_item.importance,
            tags=old_item.tags,
            room=old_item.room,
            version=old_item.version + 1,
            parent_id=old_item.id,
            change_reason=reason,
        )

        # Mark old as superseded
        if old_tier == MemoryTier.RECALL:
            self._recall_store.update_status(memory_id, MemoryStatus.SUPERSEDED)
            # TD-1 final fix: use update_field() instead of direct SQL
            self._recall_store.update_field(memory_id, "superseded_by", new_item.id)
        elif old_tier == MemoryTier.CORE:
            # Mark old item as SUPERSEDED in-place (soft — preserve in block per SPEC §4.4)
            block = old_item.room
            items = self._core_store.load(block)
            for i, item in enumerate(items):
                if item.id == memory_id:
                    items[i] = item.model_copy(
                        update={
                            "status": MemoryStatus.SUPERSEDED,
                            "superseded_by": new_item.id,
                        }
                    )
                    break
            self._core_store.save(block, items)

        # Save new item
        if new_item.tier == MemoryTier.CORE:
            existing = self._core_store.load(new_item.room)
            existing.append(new_item)
            self._core_store.save(new_item.room, existing)
        else:
            self._recall_store.insert(new_item)

        # Audit both operations
        self._audit_log.append(
            AuditEntry(
                action=AuditAction.UPDATE,
                memory_id=memory_id,
                actor="user",
                details={"action": "superseded", "superseded_by": new_item.id},
            )
        )
        self._audit_log.append(
            AuditEntry(
                action=AuditAction.CREATE,
                memory_id=new_item.id,
                actor="user",
                details={
                    "action": "new_version",
                    "parent_id": memory_id,
                    "reason": reason,
                },
            )
        )

        logger.info(
            "Memory updated",
            old_id=memory_id,
            new_id=new_item.id,
            reason=reason,
        )

        # v0.2: Sync ArchivalStore on update (delete old, index new)
        if self._archival_store is not None:
            try:
                self._archival_store.delete(memory_id)
                self._index_in_archival_sync(new_item)
            except Exception:
                logger.warning(
                    "archival_sync_update_failed",
                    old_id=memory_id,
                    new_id=new_item.id,
                    exc_info=True,
                )

        # R24: Sync GraphStore on update (remove old node, add new)
        if self._graph_store is not None:
            try:
                self._graph_store.remove_memory_node(memory_id)
                self._graph_store.add_memory_node(new_item)
            except Exception:
                logger.warning(
                    "graph_sync_update_failed",
                    old_id=memory_id,
                    new_id=new_item.id,
                    exc_info=True,
                )

        return new_item

    def forget(self, memory_id: str, reason: str) -> bool:
        """Soft delete: mark memory as pruned.

        Searches both Recall and Core tiers. For Recall items, sets
        status to PRUNED. For Core items, marks as PRUNED in-place
        (item preserved in block per SPEC §4.4).

        Args:
            memory_id: ID of the memory to forget.
            reason: Reason for forgetting.

        Returns:
            True if the memory was found and pruned.
        """
        item = self._recall_store.get(memory_id)
        if item is not None:
            self._recall_store.update_status(memory_id, MemoryStatus.PRUNED)
        else:
            # Try Core
            core_item = self._find_in_core(memory_id)
            if core_item is None:
                return False
            # Mark as PRUNED in-place (soft delete — preserve in block per SPEC §4.4)
            block = core_item.room
            items = self._core_store.load(block)
            for i, it in enumerate(items):
                if it.id == memory_id:
                    items[i] = it.model_copy(update={"status": MemoryStatus.PRUNED})
                    break
            self._core_store.save(block, items)

        self._audit_log.append(
            AuditEntry(
                action=AuditAction.PRUNE,
                memory_id=memory_id,
                actor="user",
                details={"reason": reason},
            )
        )

        logger.info("Memory forgotten", memory_id=memory_id, reason=reason)

        # v0.2: Sync ArchivalStore on forget (delete entry)
        if self._archival_store is not None:
            try:
                self._archival_store.delete(memory_id)
            except Exception:
                logger.warning("archival_sync_forget_failed", memory_id=memory_id, exc_info=True)

        # R24: Sync GraphStore on forget (remove node)
        if self._graph_store is not None:
            try:
                self._graph_store.remove_memory_node(memory_id)
            except Exception:
                logger.warning("graph_sync_forget_failed", memory_id=memory_id, exc_info=True)

        return True

    def search_sync(
        self,
        query: str,
        top_k: int = 5,
        room: str | None = None,
        min_importance: float = 0.0,
    ) -> list[MemoryItem]:
        """Synchronous search across both Core and Recall tiers.

        Merges FTS5 results from Recall with keyword-matched Core items,
        then returns up to *top_k* results sorted by importance descending.
        """
        timer = OperationTimer("search")
        with timer:
            # Recall tier: FTS5 search
            recall_results = self._retriever.search(
                query=query,
                top_k=top_k,
                room=room,
                min_importance=min_importance,
            )

            # Core tier: keyword match across all blocks
            core_results: list[MemoryItem] = []
            query_lower = query.lower() if query else ""
            if query_lower:
                blocks = self._core_store.list_blocks()
                if room is not None:
                    blocks = [b for b in blocks if b == room]
                for block in blocks:
                    for item in self._core_store.load(block):
                        if item.status != MemoryStatus.ACTIVE:
                            continue
                        if item.importance < min_importance:
                            continue
                        if query_lower in item.content.lower():
                            core_results.append(item)

            # Merge and deduplicate (Core items may also be in Recall)
            seen_ids = {r.id for r in recall_results}
            merged = list(recall_results)
            for item in core_results:
                if item.id not in seen_ids:
                    merged.append(item)
                    seen_ids.add(item.id)

            # Sort by importance descending, truncate to top_k
            merged.sort(key=lambda x: x.importance, reverse=True)
            results = merged[:top_k]

        self._metrics.record_search(timer.duration_ms)
        return results

    def get_recent(self, n: int = 10) -> list[MemoryItem]:
        """Get the N most recently created Recall items.

        Args:
            n: Number of items to return.

        Returns:
            List of MemoryItems ordered by created_at descending.
        """
        return self._recall_store.get_recent(n)

    def get_hybrid_retriever(self):
        """Return a HybridRetriever if archival+embedding are configured, else None."""
        if self._archival_store is not None and self._embedding is not None:
            from memory_palace.service.hybrid_retriever import HybridRetriever

            return HybridRetriever(
                recall_store=self._recall_store,
                archival_store=self._archival_store,
                embedding=self._embedding,
                graph_store=self._graph_store,
            )
        return None

    def get_all_items(self) -> tuple[list[MemoryItem], list[MemoryItem]]:
        """Return (core_items, recall_items) for health computation.

        Returns:
            Tuple of (core items list, recall items list).
        """
        core_items: list[MemoryItem] = []
        for block in self._core_store.list_blocks():
            core_items.extend(self._core_store.load(block))
        recall_items = self._recall_store.get_recent(1000)
        return core_items, recall_items

    def _index_in_archival_sync(self, item: MemoryItem) -> None:
        """Index item in ArchivalStore synchronously.

        Computes embedding if an EmbeddingProvider is available,
        running the async embed() in a new event loop if necessary.
        """
        import asyncio

        embedding = None
        if self._embedding is not None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is None:
                vectors = asyncio.run(self._embedding.embed([item.content]))
                embedding = vectors[0]
            else:
                # Inside an existing event loop — use nest workaround
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    vectors = pool.submit(
                        asyncio.run, self._embedding.embed([item.content])
                    ).result()
                    embedding = vectors[0]

        if embedding is not None:
            metadata = self._archival_store._build_metadata(item)
            self._archival_store._collection.upsert(
                ids=[item.id],
                documents=[item.content],
                embeddings=[embedding],
                metadatas=[metadata],
            )

    def get_core_context(self) -> str:
        """Return ACTIVE-only Core Memory text concatenated.

        v0.2: Filters out SUPERSEDED and PRUNED items (TD-2).

        Returns:
            Single string with active core memory contents joined by newlines.
        """
        texts: list[str] = []
        for block_name in self._core_store.list_blocks():
            items = self._core_store.load(block_name)
            for item in items:
                if item.status == MemoryStatus.ACTIVE:
                    texts.append(item.content)
        return "\n".join(texts)

    def stats(self) -> dict:
        """Return statistics about memory stores.

        Returns:
            Dict with core_count, recall_count, core_blocks, archival_count.
        """
        core_blocks = self._core_store.list_blocks()
        core_count = 0
        for block in core_blocks:
            items = self._core_store.load(block)
            core_count += len(items)

        recall_count = self._recall_store.count()

        result = {
            "core_count": core_count,
            "recall_count": recall_count,
            "core_blocks": core_blocks,
            "total": core_count + recall_count,
        }

        if self._archival_store is not None:
            result["archival_count"] = self._archival_store.count()
            result["total"] += result["archival_count"]

        return result

    def get_metrics(self) -> dict:
        """Return operational metrics summary.

        Returns:
            Dict with search_p95_ms, save_p95_ms, curator_avg_duration_s,
            growth_rate_per_day, total_searches, total_saves, total_curations.
        """
        return self._metrics.summary

    # ── R19: Async lock-wrapped methods for MCP concurrency safety ──

    async def async_save(
        self,
        content: str,
        importance: float | None = None,
        tags: list[str] | None = None,
        room: str = "general",
        memory_type: MemoryType = MemoryType.OBSERVATION,
    ) -> MemoryItem:
        """Concurrency-safe save. Acquires write lock before delegating to save()."""
        async with self._write_lock:
            return self.save(content, importance, tags, room, memory_type)

    async def async_update(
        self,
        memory_id: str,
        new_content: str,
        reason: str,
    ) -> MemoryItem:
        """Concurrency-safe update. Acquires write lock before delegating to update()."""
        async with self._write_lock:
            return self.update(memory_id, new_content, reason)

    async def async_forget(self, memory_id: str, reason: str) -> bool:
        """Concurrency-safe forget. Acquires write lock before delegating to forget()."""
        async with self._write_lock:
            return self.forget(memory_id, reason)
