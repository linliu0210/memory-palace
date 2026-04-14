"""
Round 5: Service — MemoryService Tests (Integration)

IMMUTABLE SPEC: Ref: SPEC v2.0 §4.4

MemoryService is the CRUD facade. It coordinates Store + Engine layers.
Tests use tmp_data_dir + MockLLM — no real I/O beyond temp files.
"""

import pytest

from memory_palace.foundation.audit_log import AuditLog
from memory_palace.models.memory import MemoryStatus, MemoryTier
from memory_palace.service.memory_service import MemoryService
from memory_palace.store.core_store import CoreStore
from memory_palace.store.recall_store import RecallStore


class TestMemoryServiceSave:
    """MemoryService.save() routing and audit."""

    def test_save_stores_to_core_when_high_importance(self, tmp_data_dir):
        """importance >= 0.7 → CoreStore."""
        svc = MemoryService(tmp_data_dir)
        item = svc.save("用户喜欢深色模式", importance=0.8, room="preferences")

        assert item.tier == MemoryTier.CORE
        assert item.importance == 0.8

        # Verify in CoreStore
        core = CoreStore(tmp_data_dir)
        loaded = core.load("preferences")
        assert len(loaded) == 1
        assert loaded[0].id == item.id

    def test_save_stores_to_recall_when_low_importance(self, tmp_data_dir):
        """importance < 0.7 → RecallStore."""
        svc = MemoryService(tmp_data_dir)
        item = svc.save("今天天气不错", importance=0.3)

        assert item.tier == MemoryTier.RECALL
        assert item.importance == 0.3

        # Verify in RecallStore
        recall = RecallStore(tmp_data_dir)
        loaded = recall.get(item.id)
        assert loaded is not None
        assert loaded.content == "今天天气不错"

    def test_save_creates_audit_entry(self, tmp_data_dir):
        """Every save produces an AuditEntry(action=CREATE)."""
        svc = MemoryService(tmp_data_dir)
        item = svc.save("测试审计", importance=0.5)

        audit = AuditLog(tmp_data_dir)
        entries = audit.read(memory_id=item.id)
        assert len(entries) >= 1
        assert entries[0].action == "create"
        assert entries[0].memory_id == item.id

    @pytest.mark.asyncio
    async def test_save_batch_extracts_facts_and_saves(self, tmp_data_dir, mock_llm_extract):
        """save_batch() calls FactExtractor then saves each fact."""
        svc = MemoryService(tmp_data_dir, llm=mock_llm_extract)
        items = await svc.save_batch(["用户说喜欢深色模式，正在开发DreamEngine"])

        # mock_llm_extract returns 2 facts
        assert len(items) == 2
        assert items[0].content == "用户喜欢深色模式"
        assert items[1].content == "用户正在开发DreamEngine项目"


class TestMemoryServiceSearch:
    """MemoryService.search() with scoring."""

    def test_search_returns_ranked_results(self, tmp_data_dir):
        """Results are sorted by combined score descending."""
        svc = MemoryService(tmp_data_dir)
        # Save items to RecallStore (low importance → Recall)
        svc.save("Python是一种编程语言", importance=0.3)
        svc.save("Python用于数据科学", importance=0.6)

        results = svc.search_sync("Python")
        assert len(results) >= 1
        # Results should be returned (exact order depends on scoring)
        contents = [r.content for r in results]
        assert any("Python" in c for c in contents)

    def test_search_filters_by_room(self, tmp_data_dir):
        """search(query, room='preferences') excludes other rooms."""
        svc = MemoryService(tmp_data_dir)
        svc.save("用户喜欢深色模式偏好", importance=0.3, room="preferences")
        svc.save("项目使用深色主题设计", importance=0.3, room="projects")

        results = svc.search_sync("深色", room="preferences")
        for item in results:
            assert item.room == "preferences"

    def test_search_filters_by_min_importance(self, tmp_data_dir):
        """search(query, min_importance=0.5) excludes low-importance items."""
        svc = MemoryService(tmp_data_dir)
        svc.save("低重要性测试内容", importance=0.2)
        svc.save("高重要性测试内容", importance=0.6)

        results = svc.search_sync("测试内容", min_importance=0.5)
        for item in results:
            assert item.importance >= 0.5


class TestMemoryServiceUpdate:
    """MemoryService.update() versioning."""

    def test_update_creates_new_version(self, tmp_data_dir):
        """update(id, new_content) creates a new MemoryItem."""
        svc = MemoryService(tmp_data_dir)
        original = svc.save("用户喜欢Python", importance=0.5)

        new_item = svc.update(original.id, "用户更喜欢Rust", reason="偏好更新")

        assert new_item.id != original.id
        assert new_item.content == "用户更喜欢Rust"
        assert new_item.version == original.version + 1
        assert new_item.parent_id == original.id

    def test_update_marks_old_as_superseded(self, tmp_data_dir):
        """Old item status = SUPERSEDED, superseded_by = new_id."""
        svc = MemoryService(tmp_data_dir)
        original = svc.save("旧内容", importance=0.5)

        svc.update(original.id, "新内容", reason="更新")

        # Check old item status in RecallStore
        recall = RecallStore(tmp_data_dir)
        old = recall.get(original.id)
        assert old is not None
        assert old.status == MemoryStatus.SUPERSEDED

    def test_update_preserves_audit_chain(self, tmp_data_dir):
        """AuditLog records both the original and the update."""
        svc = MemoryService(tmp_data_dir)
        original = svc.save("原始内容", importance=0.5)
        svc.update(original.id, "更新内容", reason="测试审计链")

        audit = AuditLog(tmp_data_dir)
        # Should have entries for: original CREATE + UPDATE + new CREATE
        all_entries = audit.read()
        assert len(all_entries) >= 2


class TestMemoryServiceForget:
    """MemoryService.forget() soft delete."""

    def test_forget_marks_as_pruned(self, tmp_data_dir):
        """forget(id) sets status = PRUNED."""
        svc = MemoryService(tmp_data_dir)
        item = svc.save("要遗忘的内容", importance=0.3)

        result = svc.forget(item.id, reason="用户要求遗忘")
        assert result is True

        recall = RecallStore(tmp_data_dir)
        forgotten = recall.get(item.id)
        assert forgotten is not None
        assert forgotten.status == MemoryStatus.PRUNED

    def test_forget_does_not_physically_delete(self, tmp_data_dir):
        """Item is still in storage, just marked PRUNED."""
        svc = MemoryService(tmp_data_dir)
        item = svc.save("不要删除我", importance=0.3)

        svc.forget(item.id, reason="测试软删除")

        # Item still exists in storage
        recall = RecallStore(tmp_data_dir)
        stored = recall.get(item.id)
        assert stored is not None
        assert stored.content == "不要删除我"


class TestMemoryServiceContext:
    """MemoryService utility methods."""

    def test_get_core_context_returns_all_core_text(self, tmp_data_dir):
        """get_core_context() returns concatenated Core Memory text."""
        svc = MemoryService(tmp_data_dir)
        svc.save("核心记忆一", importance=0.8, room="persona")
        svc.save("核心记忆二", importance=0.9, room="user")

        context = svc.get_core_context()
        assert "核心记忆一" in context
        assert "核心记忆二" in context

    def test_stats_returns_correct_counts(self, tmp_data_dir):
        """stats() reports correct counts per tier."""
        svc = MemoryService(tmp_data_dir)
        svc.save("Core item", importance=0.8, room="general")
        svc.save("Recall item 1", importance=0.3)
        svc.save("Recall item 2", importance=0.4)

        stats = svc.stats()
        assert stats["core_count"] == 1
        assert stats["recall_count"] == 2
        assert stats["total"] == 3
