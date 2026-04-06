"""
Round 3: Store — CoreStore Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §4.1 S-8

CoreStore manages Core Memory (JSON flat files).
One block = one JSON file. Max 2KB per block.
Blocks: persona, user, preferences.
"""

import pytest


class TestCoreStoreCRUD:
    """CoreStore basic CRUD operations."""

    def test_save_creates_json_file(self, tmp_data_dir):
        """Saving to block 'persona' creates core/persona.json."""
        pytest.skip("RED: CoreStore not implemented")

    def test_save_overwrites_existing(self, tmp_data_dir):
        """Saving again to same block replaces content."""
        pytest.skip("RED: CoreStore not implemented")

    def test_load_returns_saved_items(self, tmp_data_dir):
        """load('persona') returns previously saved MemoryItems."""
        pytest.skip("RED: CoreStore not implemented")

    def test_load_returns_empty_for_missing_block(self, tmp_data_dir):
        """load('nonexistent') returns empty list, not error."""
        pytest.skip("RED: CoreStore not implemented")

    def test_delete_removes_item(self, tmp_data_dir):
        """delete(memory_id) removes item from block file."""
        pytest.skip("RED: CoreStore not implemented")

    def test_list_blocks_returns_all_block_names(self, tmp_data_dir):
        """list_blocks() returns ['persona', 'user'] after writing both."""
        pytest.skip("RED: CoreStore not implemented")


class TestCoreStoreBudget:
    """CoreStore 2KB budget enforcement."""

    def test_budget_check_returns_current_size(self, tmp_data_dir):
        """budget_check('persona') returns current byte size."""
        pytest.skip("RED: CoreStore not implemented")

    def test_budget_check_warns_when_near_limit(self, tmp_data_dir):
        """Should return warning when block exceeds 80% of 2048 bytes."""
        pytest.skip("RED: CoreStore not implemented")

    def test_get_all_core_text(self, tmp_data_dir):
        """get_all_text() concatenates all blocks into a single string."""
        pytest.skip("RED: CoreStore not implemented")
