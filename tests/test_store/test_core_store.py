"""
Round 3: Store — CoreStore Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §4.1 S-8

CoreStore manages Core Memory (JSON flat files).
One block = one JSON file. Max 2KB per block.
Blocks: persona, user, preferences.
"""

from memory_palace.models.memory import MemoryItem, MemoryTier, MemoryType
from memory_palace.store.core_store import CoreStore


class TestCoreStoreCRUD:
    """CoreStore basic CRUD operations."""

    def test_save_creates_json_file(self, tmp_data_dir):
        """Saving to block 'persona' creates core/persona.json."""
        store = CoreStore(tmp_data_dir)
        item = MemoryItem(
            content="I am a helpful assistant",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.CORE,
            importance=0.9,
        )
        store.save("persona", [item])
        assert (tmp_data_dir / "core" / "persona.json").exists()

    def test_save_overwrites_existing(self, tmp_data_dir):
        """Saving again to same block replaces content."""
        store = CoreStore(tmp_data_dir)
        item1 = MemoryItem(
            content="Old persona",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.CORE,
            importance=0.8,
        )
        item2 = MemoryItem(
            content="New persona",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.CORE,
            importance=0.9,
        )
        store.save("persona", [item1])
        store.save("persona", [item2])
        items = store.load("persona")
        assert len(items) == 1
        assert items[0].content == "New persona"

    def test_load_returns_saved_items(self, tmp_data_dir):
        """load('persona') returns previously saved MemoryItems."""
        store = CoreStore(tmp_data_dir)
        item = MemoryItem(
            content="User prefers dark mode",
            memory_type=MemoryType.PREFERENCE,
            tier=MemoryTier.CORE,
            importance=0.8,
        )
        store.save("persona", [item])
        items = store.load("persona")
        assert len(items) == 1
        assert items[0].content == "User prefers dark mode"
        assert items[0].importance == 0.8

    def test_load_returns_empty_for_missing_block(self, tmp_data_dir):
        """load('nonexistent') returns empty list, not error."""
        store = CoreStore(tmp_data_dir)
        items = store.load("nonexistent")
        assert items == []

    def test_delete_removes_item(self, tmp_data_dir):
        """delete(memory_id) removes item from block file."""
        store = CoreStore(tmp_data_dir)
        item1 = MemoryItem(
            content="Keep this",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.CORE,
            importance=0.7,
        )
        item2 = MemoryItem(
            content="Delete this",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.CORE,
            importance=0.3,
        )
        store.save("persona", [item1, item2])
        store.delete("persona", item2.id)
        items = store.load("persona")
        assert len(items) == 1
        assert items[0].content == "Keep this"

    def test_list_blocks_returns_all_block_names(self, tmp_data_dir):
        """list_blocks() returns ['persona', 'user'] after writing both."""
        store = CoreStore(tmp_data_dir)
        item = MemoryItem(
            content="test",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.CORE,
            importance=0.5,
        )
        store.save("persona", [item])
        store.save("user", [item])
        blocks = store.list_blocks()
        assert "persona" in blocks
        assert "user" in blocks


class TestCoreStoreBudget:
    """CoreStore 2KB budget enforcement."""

    def test_budget_check_returns_current_size(self, tmp_data_dir):
        """budget_check('persona') returns current byte size."""
        store = CoreStore(tmp_data_dir)
        item = MemoryItem(
            content="Small content",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.CORE,
            importance=0.5,
        )
        store.save("persona", [item])
        result = store.budget_check("persona")
        assert result["size"] > 0
        assert result["limit"] == 2048
        assert result["warning"] is False

    def test_budget_check_warns_when_near_limit(self, tmp_data_dir):
        """Should return warning when block exceeds 80% of 2048 bytes."""
        store = CoreStore(tmp_data_dir)
        # Create items that together exceed 80% of 2048 (1638 bytes)
        items = [
            MemoryItem(
                content=f"A fairly long piece of content number {i} to fill up space quickly"
                f" with extra text to push the total size beyond the warning threshold boundary",
                memory_type=MemoryType.OBSERVATION,
                tier=MemoryTier.CORE,
                importance=0.5,
            )
            for i in range(20)
        ]
        store.save("persona", items)
        result = store.budget_check("persona")
        assert result["warning"] is True

    def test_get_all_core_text(self, tmp_data_dir):
        """get_all_text() concatenates all blocks into a single string."""
        store = CoreStore(tmp_data_dir)
        item1 = MemoryItem(
            content="Hello from persona",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.CORE,
            importance=0.7,
        )
        item2 = MemoryItem(
            content="Hello from user",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.CORE,
            importance=0.6,
        )
        store.save("persona", [item1])
        store.save("user", [item2])
        text = store.get_all_text()
        assert "Hello from persona" in text
        assert "Hello from user" in text
