"""
Round 5: Service — MemoryService Tests (Integration)

IMMUTABLE SPEC: Ref: SPEC v2.0 §4.4

MemoryService is the CRUD facade. It coordinates Store + Engine layers.
Tests use tmp_data_dir + MockLLM — no real I/O beyond temp files.
"""

import pytest


class TestMemoryServiceSave:
    """MemoryService.save() routing and audit."""

    def test_save_stores_to_core_when_high_importance(self, tmp_data_dir):
        """importance >= 0.7 → CoreStore."""
        pytest.skip("RED: MemoryService not implemented")

    def test_save_stores_to_recall_when_low_importance(self, tmp_data_dir):
        """importance < 0.7 → RecallStore."""
        pytest.skip("RED: MemoryService not implemented")

    def test_save_creates_audit_entry(self, tmp_data_dir):
        """Every save produces an AuditEntry(action=CREATE)."""
        pytest.skip("RED: MemoryService not implemented")

    @pytest.mark.asyncio
    async def test_save_batch_extracts_facts_and_saves(
        self, tmp_data_dir, mock_llm_extract
    ):
        """save_batch() calls FactExtractor then saves each fact."""
        pytest.skip("RED: MemoryService not implemented")


class TestMemoryServiceSearch:
    """MemoryService.search() with scoring."""

    def test_search_returns_ranked_results(self, tmp_data_dir):
        """Results are sorted by combined score descending."""
        pytest.skip("RED: MemoryService not implemented")

    def test_search_filters_by_room(self, tmp_data_dir):
        """search(query, room='preferences') excludes other rooms."""
        pytest.skip("RED: MemoryService not implemented")

    def test_search_filters_by_min_importance(self, tmp_data_dir):
        """search(query, min_importance=0.5) excludes low-importance items."""
        pytest.skip("RED: MemoryService not implemented")


class TestMemoryServiceUpdate:
    """MemoryService.update() versioning."""

    def test_update_creates_new_version(self, tmp_data_dir):
        """update(id, new_content) creates a new MemoryItem."""
        pytest.skip("RED: MemoryService not implemented")

    def test_update_marks_old_as_superseded(self, tmp_data_dir):
        """Old item status = SUPERSEDED, superseded_by = new_id."""
        pytest.skip("RED: MemoryService not implemented")

    def test_update_preserves_audit_chain(self, tmp_data_dir):
        """AuditLog records both the original and the update."""
        pytest.skip("RED: MemoryService not implemented")


class TestMemoryServiceForget:
    """MemoryService.forget() soft delete."""

    def test_forget_marks_as_pruned(self, tmp_data_dir):
        """forget(id) sets status = PRUNED."""
        pytest.skip("RED: MemoryService not implemented")

    def test_forget_does_not_physically_delete(self, tmp_data_dir):
        """Item is still in storage, just marked PRUNED."""
        pytest.skip("RED: MemoryService not implemented")


class TestMemoryServiceContext:
    """MemoryService utility methods."""

    def test_get_core_context_returns_all_core_text(self, tmp_data_dir):
        """get_core_context() returns concatenated Core Memory text."""
        pytest.skip("RED: MemoryService not implemented")

    def test_stats_returns_correct_counts(self, tmp_data_dir):
        """stats() reports correct counts per tier."""
        pytest.skip("RED: MemoryService not implemented")
