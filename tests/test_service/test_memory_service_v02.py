"""
Round 12: Service — MemoryService v0.2 Upgrade Tests

Tests for the v0.2 additions:
- get_by_id(): three-tier lookup (TD-4)
- get_core_context(): active-only filter (TD-2)
- save(): Core budget check + auto-demote (TD-7)
- update(): uses update_field (TD-1 final fix)
"""

import pytest

from memory_palace.models.memory import MemoryItem, MemoryStatus, MemoryTier, MemoryType
from memory_palace.service.memory_service import CORE_MAX_ITEMS_PER_BLOCK, MemoryService
from memory_palace.store.core_store import CoreStore
from memory_palace.store.recall_store import RecallStore


class TestGetById:
    """MemoryService.get_by_id() — three-tier lookup (TD-4)."""

    def test_get_by_id_from_core(self, tmp_data_dir):
        """get_by_id() finds items stored in Core tier."""
        ms = MemoryService(tmp_data_dir)
        item = ms.save("核心记忆", importance=0.9, room="preferences")

        result = ms.get_by_id(item.id)
        assert result is not None
        assert result.content == "核心记忆"

    def test_get_by_id_from_recall(self, tmp_data_dir):
        """get_by_id() finds items stored in Recall tier."""
        ms = MemoryService(tmp_data_dir)
        item = ms.save("召回记忆", importance=0.4, room="general")

        result = ms.get_by_id(item.id)
        assert result is not None
        assert result.content == "召回记忆"

    def test_get_by_id_not_found(self, tmp_data_dir):
        """get_by_id() returns None for non-existent ID."""
        ms = MemoryService(tmp_data_dir)
        result = ms.get_by_id("does-not-exist")
        assert result is None


class TestGetCoreContextActiveOnly:
    """MemoryService.get_core_context() — active-only filter (TD-2)."""

    def test_core_context_active_only(self, tmp_data_dir):
        """get_core_context() excludes SUPERSEDED items."""
        ms = MemoryService(tmp_data_dir)
        item1 = ms.save("旧偏好: 浅色模式", importance=0.8, room="preferences")
        ms.save("保持活跃", importance=0.9, room="preferences")

        # Supersede item1
        ms.update(item1.id, "新偏好: 深色模式", "preference changed")

        context = ms.get_core_context()

        assert "保持活跃" in context
        # The superseded content should NOT appear
        assert "旧偏好: 浅色模式" not in context

    def test_core_context_excludes_pruned(self, tmp_data_dir):
        """get_core_context() excludes PRUNED items."""
        ms = MemoryService(tmp_data_dir)
        item = ms.save("要被删除的", importance=0.8, room="test")
        ms.save("保留的", importance=0.9, room="test")

        ms.forget(item.id, "no longer relevant")

        context = ms.get_core_context()
        assert "保留的" in context
        assert "要被删除的" not in context


class TestCoreAutoDemote:
    """MemoryService.save() — Core budget check + auto-demote (TD-7)."""

    def test_auto_demote_when_core_full(self, tmp_data_dir):
        """save() auto-demotes oldest Core item when block is full."""
        ms = MemoryService(tmp_data_dir)

        # Fill Core block to max capacity
        saved_ids = []
        for i in range(CORE_MAX_ITEMS_PER_BLOCK):
            item = ms.save(
                f"核心记忆 {i}",
                importance=0.9,
                room="test_block",
            )
            saved_ids.append(item.id)

        # Save one more — should trigger auto-demote
        new_item = ms.save("触发降级的记忆", importance=0.95, room="test_block")

        # The new item should be in Core
        core = CoreStore(tmp_data_dir)
        core_items = core.load("test_block")
        core_ids = {i.id for i in core_items}
        assert new_item.id in core_ids

        # The oldest should have been demoted to Recall
        recall = RecallStore(tmp_data_dir)
        demoted = recall.get(saved_ids[0])
        assert demoted is not None
        assert demoted.tier == MemoryTier.RECALL

    def test_no_demote_when_under_budget(self, tmp_data_dir):
        """save() does not demote when Core block is under budget."""
        ms = MemoryService(tmp_data_dir)
        ms.save("记忆A", importance=0.9, room="small_block")
        ms.save("记忆B", importance=0.8, room="small_block")

        core = CoreStore(tmp_data_dir)
        assert len(core.load("small_block")) == 2


class TestUpdateWithUpdateField:
    """MemoryService.update() — uses update_field (TD-1 final fix)."""

    def test_update_sets_superseded_by(self, tmp_data_dir):
        """update() correctly sets superseded_by on the old item via update_field."""
        ms = MemoryService(tmp_data_dir)
        old = ms.save("旧版本", importance=0.4, room="general")

        new = ms.update(old.id, "新版本", "content updated")

        # Old item should have superseded_by set
        recall = RecallStore(tmp_data_dir)
        old_item = recall.get(old.id)
        assert old_item is not None
        assert old_item.status == MemoryStatus.SUPERSEDED
        assert old_item.superseded_by == new.id

    def test_update_core_item(self, tmp_data_dir):
        """update() works for Core tier items."""
        ms = MemoryService(tmp_data_dir)
        old = ms.save("核心旧版本", importance=0.9, room="test")

        new = ms.update(old.id, "核心新版本", "core update")

        assert new.version == old.version + 1
        assert new.parent_id == old.id

    def test_update_nonexistent_raises(self, tmp_data_dir):
        """update() raises ValueError for non-existent ID."""
        ms = MemoryService(tmp_data_dir)

        with pytest.raises(ValueError, match="not found"):
            ms.update("nonexistent-id", "content", "reason")
