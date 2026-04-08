"""MemoryService — CRUD facade for the Memory Palace.

Coordinates Store (CoreStore + RecallStore), Engine (FactExtractor),
AuditLog, and Retriever to provide a unified memory API.

Ref: SPEC v2.0 §4.1 S-13, §4.4
"""

from __future__ import annotations

from pathlib import Path

import structlog

from memory_palace.engine.fact_extractor import FactExtractor
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

logger = structlog.get_logger(__name__)


class MemoryService:
    """CRUD facade for memory operations.

    Routes high-importance items to CoreStore, others to RecallStore.
    All mutations are audited through AuditLog.

    Args:
        data_dir: Root data directory for stores and audit log.
        llm: Optional LLM provider (needed for save_batch via FactExtractor).
    """

    def __init__(self, data_dir: Path, llm: LLMProvider | None = None) -> None:
        self._data_dir = data_dir
        self._core_store = CoreStore(data_dir)
        self._recall_store = RecallStore(data_dir)
        self._audit_log = AuditLog(data_dir)
        self._retriever = Retriever(self._recall_store)
        self._llm = llm
        if llm is not None:
            self._fact_extractor = FactExtractor(llm)
        else:
            self._fact_extractor = None

    def save(
        self,
        content: str,
        importance: float | None = None,
        tags: list[str] | None = None,
        room: str = "general",
        memory_type: MemoryType = MemoryType.OBSERVATION,
    ) -> MemoryItem:
        """Save a new memory. Routes to Core or Recall by importance.

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
            # CoreStore.save(block, items) — block is room name
            existing = self._core_store.load(room)
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

    def search(
        self,
        query: str,
        top_k: int = 5,
        room: str | None = None,
        min_importance: float = 0.0,
    ) -> list[MemoryItem]:
        """Search memories, ranked by combined score.

        Delegates to Retriever for FTS5 + scoring.

        Args:
            query: Search query string.
            top_k: Maximum results to return.
            room: Optional room filter.
            min_importance: Minimum importance threshold.

        Returns:
            Ranked list of MemoryItems, highest score first.
        """
        return self._retriever.search(
            query=query,
            top_k=top_k,
            room=room,
            min_importance=min_importance,
        )

    def update(self, memory_id: str, new_content: str, reason: str) -> MemoryItem:
        """Update a memory: supersede old, create new version.

        Args:
            memory_id: ID of the memory to update.
            new_content: New content for the memory.
            reason: Reason for the update.

        Returns:
            The new MemoryItem version.

        Raises:
            ValueError: If the memory_id is not found.
        """
        # Find the old item
        old_item = self._recall_store.get(memory_id)
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
        self._recall_store.update_status(memory_id, MemoryStatus.SUPERSEDED)

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
        return new_item

    def forget(self, memory_id: str, reason: str) -> bool:
        """Soft delete: mark memory as pruned.

        Does NOT physically delete — just sets status to PRUNED.

        Args:
            memory_id: ID of the memory to forget.
            reason: Reason for forgetting.

        Returns:
            True if the memory was found and pruned.
        """
        item = self._recall_store.get(memory_id)
        if item is None:
            return False

        self._recall_store.update_status(memory_id, MemoryStatus.PRUNED)

        self._audit_log.append(
            AuditEntry(
                action=AuditAction.PRUNE,
                memory_id=memory_id,
                actor="user",
                details={"reason": reason},
            )
        )

        logger.info("Memory forgotten", memory_id=memory_id, reason=reason)
        return True

    def get_core_context(self) -> str:
        """Return all Core Memory text concatenated.

        Returns:
            Single string with all core memory contents joined by newlines.
        """
        return self._core_store.get_all_text()

    def stats(self) -> dict:
        """Return statistics about memory stores.

        Returns:
            Dict with core_count, recall_count, core_blocks.
        """
        core_blocks = self._core_store.list_blocks()
        core_count = 0
        for block in core_blocks:
            items = self._core_store.load(block)
            core_count += len(items)

        recall_count = self._recall_store.count()

        return {
            "core_count": core_count,
            "recall_count": recall_count,
            "core_blocks": core_blocks,
            "total": core_count + recall_count,
        }
