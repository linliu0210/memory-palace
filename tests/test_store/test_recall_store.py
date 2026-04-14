"""
Round 3: Store — RecallStore Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §4.1 S-9

RecallStore uses SQLite + FTS5 for full-text search.
Stores MemoryItems with all fields in a relational table,
with a shadow FTS5 virtual table for keyword search.
"""

from datetime import datetime, timedelta

import pytest

from memory_palace.models.memory import (
    MemoryItem,
    MemoryStatus,
    MemoryTier,
    MemoryType,
)
from memory_palace.store.recall_store import RecallStore


def _make_item(
    content: str = "test content",
    memory_type: MemoryType = MemoryType.OBSERVATION,
    importance: float = 0.5,
    room: str = "general",
    item_id: str | None = None,
    created_at: datetime | None = None,
) -> MemoryItem:
    """Helper to create a MemoryItem for testing."""
    return MemoryItem(
        id=item_id or "test-id-001",
        content=content,
        memory_type=memory_type,
        tier=MemoryTier.RECALL,
        importance=importance,
        room=room,
        tags=["test"],
        created_at=created_at or datetime.now(),
        accessed_at=created_at or datetime.now(),
        updated_at=created_at or datetime.now(),
    )


class TestRecallStoreInsert:
    """RecallStore insert operations."""

    def test_insert_creates_record(self, tmp_data_dir):
        """insert(MemoryItem) should persist to SQLite."""
        store = RecallStore(tmp_data_dir)
        item = _make_item()
        store.insert(item)
        assert store.count() == 1

    def test_insert_stores_all_fields(self, tmp_data_dir):
        """All MemoryItem fields must be retrievable after insert."""
        store = RecallStore(tmp_data_dir)
        item = _make_item(
            content="用户喜欢深色模式",
            memory_type=MemoryType.PREFERENCE,
            importance=0.8,
            room="preferences",
            item_id="field-test-001",
        )
        store.insert(item)
        retrieved = store.get("field-test-001")
        assert retrieved is not None
        assert retrieved.content == "用户喜欢深色模式"
        assert retrieved.memory_type == MemoryType.PREFERENCE
        assert retrieved.tier == MemoryTier.RECALL
        assert retrieved.importance == 0.8
        assert retrieved.room == "preferences"
        assert retrieved.tags == ["test"]
        assert retrieved.status == MemoryStatus.ACTIVE
        assert retrieved.version == 1
        assert retrieved.access_count == 0

    def test_insert_duplicate_id_raises(self, tmp_data_dir):
        """Inserting same ID twice should raise or handle gracefully."""
        store = RecallStore(tmp_data_dir)
        item = _make_item(item_id="dup-id")
        store.insert(item)
        with pytest.raises(Exception):
            store.insert(_make_item(item_id="dup-id"))


class TestRecallStoreSearch:
    """RecallStore FTS5 search operations."""

    def test_search_by_keyword_returns_matches(self, tmp_data_dir):
        """search('深色模式') returns items containing that text."""
        store = RecallStore(tmp_data_dir)
        store.insert(_make_item(content="用户喜欢深色模式", item_id="s1", room="preferences"))
        store.insert(_make_item(content="项目使用Python开发", item_id="s2", room="projects"))
        results = store.search("深色模式")
        assert len(results) >= 1
        assert any(r["item"].content == "用户喜欢深色模式" for r in results)

    def test_search_by_keyword_returns_empty_on_no_match(self, tmp_data_dir):
        """search('不存在的内容') returns empty list."""
        store = RecallStore(tmp_data_dir)
        store.insert(_make_item(content="用户喜欢深色模式", item_id="s1"))
        results = store.search("不存在的内容")
        assert results == []

    def test_search_returns_fts5_bm25_rank(self, tmp_data_dir):
        """Results must include raw BM25 rank score for ScoringEngine."""
        store = RecallStore(tmp_data_dir)
        store.insert(_make_item(content="深色模式偏好设置", item_id="r1"))
        results = store.search("深色模式")
        assert len(results) >= 1
        # Reason: FTS5 BM25 rank is negative (lower = more relevant)
        assert "rank" in results[0]
        assert isinstance(results[0]["rank"], float)

    def test_search_by_room_filter(self, tmp_data_dir):
        """search(query, room='preferences') filters by room."""
        store = RecallStore(tmp_data_dir)
        store.insert(_make_item(content="深色模式偏好", item_id="rf1", room="preferences"))
        store.insert(_make_item(content="深色模式项目", item_id="rf2", room="projects"))
        results = store.search("深色模式", room="preferences")
        assert len(results) >= 1
        assert all(r["item"].room == "preferences" for r in results)

    def test_search_with_date_token_returns_matches(self, tmp_data_dir):
        """Date-like tokens should be treated as plain full-text input, not FTS syntax."""
        store = RecallStore(tmp_data_dir)
        store.insert(_make_item(content="发布日期是 2026-04-13", item_id="date-1"))

        results = store.search("2026-04-13")

        assert len(results) >= 1
        assert any(r["item"].id == "date-1" for r in results)

    def test_search_with_hyphenated_token_returns_matches(self, tmp_data_dir):
        """Hyphenated tokens should be searchable without MATCH parse failures."""
        store = RecallStore(tmp_data_dir)
        store.insert(_make_item(content="标签包含 foo-bar", item_id="hyphen-1"))

        results = store.search("foo-bar")

        assert len(results) >= 1
        assert any(r["item"].id == "hyphen-1" for r in results)

    def test_search_with_multiple_plain_tokens_keeps_and_semantics(self, tmp_data_dir):
        """Multiple words should still behave like a normal full-text AND query."""
        store = RecallStore(tmp_data_dir)
        store.insert(_make_item(content="Nested Codex MCP smoke test", item_id="multi-1"))
        store.insert(_make_item(content="Nested Codex only", item_id="multi-2"))

        results = store.search("Nested Codex smoke")

        ids = {r["item"].id for r in results}
        assert "multi-1" in ids
        assert "multi-2" not in ids


class TestRecallStoreRetrieval:
    """RecallStore direct retrieval operations."""

    def test_get_by_id_returns_correct_item(self, tmp_data_dir):
        """get(id) returns the exact MemoryItem."""
        store = RecallStore(tmp_data_dir)
        item = _make_item(content="Exact match test", item_id="get-exact")
        store.insert(item)
        retrieved = store.get("get-exact")
        assert retrieved is not None
        assert retrieved.id == "get-exact"
        assert retrieved.content == "Exact match test"

    def test_get_by_id_returns_none_for_missing(self, tmp_data_dir):
        """get(nonexistent_id) returns None."""
        store = RecallStore(tmp_data_dir)
        result = store.get("does-not-exist")
        assert result is None

    def test_get_recent_returns_n_most_recent(self, tmp_data_dir):
        """get_recent(n=3) returns 3 most recently created items."""
        store = RecallStore(tmp_data_dir)
        base_time = datetime(2026, 1, 1, 12, 0, 0)
        for i in range(5):
            store.insert(
                _make_item(
                    content=f"Item {i}",
                    item_id=f"recent-{i}",
                    created_at=base_time + timedelta(hours=i),
                )
            )
        recent = store.get_recent(n=3)
        assert len(recent) == 3
        # Reason: most recent first (created_at DESC)
        assert recent[0].content == "Item 4"

    def test_count_returns_correct_total(self, tmp_data_dir):
        """count() returns total number of active records."""
        store = RecallStore(tmp_data_dir)
        assert store.count() == 0
        store.insert(_make_item(item_id="cnt-1"))
        store.insert(_make_item(item_id="cnt-2"))
        assert store.count() == 2


class TestRecallStoreUpdate:
    """RecallStore update operations."""

    def test_update_status_marks_superseded(self, tmp_data_dir):
        """update_status(id, SUPERSEDED) changes the status field."""
        store = RecallStore(tmp_data_dir)
        store.insert(_make_item(item_id="status-1"))
        store.update_status("status-1", MemoryStatus.SUPERSEDED)
        item = store.get("status-1")
        assert item is not None
        assert item.status == MemoryStatus.SUPERSEDED

    def test_update_access_count_increments(self, tmp_data_dir):
        """touch(id) increments access_count and updates accessed_at."""
        store = RecallStore(tmp_data_dir)
        store.insert(_make_item(item_id="touch-1"))
        item_before = store.get("touch-1")
        assert item_before is not None
        assert item_before.access_count == 0

        store.touch("touch-1")
        item_after = store.get("touch-1")
        assert item_after is not None
        assert item_after.access_count == 1
        # Reason: accessed_at should be updated to a newer timestamp
        assert item_after.accessed_at >= item_before.accessed_at


class TestRecallStoreUpdateField:
    """RecallStore.update_field — TD-1 resolution."""

    def test_update_field_changes_value(self, tmp_data_dir):
        """update_field(id, 'importance', 0.9) updates the field."""
        store = RecallStore(tmp_data_dir)
        store.insert(_make_item(item_id="uf-1", importance=0.5))
        store.update_field("uf-1", "importance", 0.9)
        item = store.get("uf-1")
        assert item is not None
        assert item.importance == 0.9

    def test_update_field_rejects_invalid_field(self, tmp_data_dir):
        """update_field(id, 'id', ...) should raise ValueError."""
        store = RecallStore(tmp_data_dir)
        store.insert(_make_item(item_id="uf-2"))
        with pytest.raises(ValueError, match="not updatable"):
            store.update_field("uf-2", "id", "new-id")

    def test_update_field_serializes_list(self, tmp_data_dir):
        """update_field with list value should JSON-serialize it."""
        store = RecallStore(tmp_data_dir)
        store.insert(_make_item(item_id="uf-3"))
        store.update_field("uf-3", "tags", ["updated", "tags"])
        item = store.get("uf-3")
        assert item is not None
        assert item.tags == ["updated", "tags"]
