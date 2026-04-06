"""
Round 3: Store — RecallStore Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §4.1 S-9

RecallStore uses SQLite + FTS5 for full-text search.
Stores MemoryItems with all fields in a relational table,
with a shadow FTS5 virtual table for keyword search.
"""

import pytest


class TestRecallStoreInsert:
    """RecallStore insert operations."""

    def test_insert_creates_record(self, tmp_data_dir):
        """insert(MemoryItem) should persist to SQLite."""
        pytest.skip("RED: RecallStore not implemented")

    def test_insert_stores_all_fields(self, tmp_data_dir):
        """All MemoryItem fields must be retrievable after insert."""
        pytest.skip("RED: RecallStore not implemented")

    def test_insert_duplicate_id_raises(self, tmp_data_dir):
        """Inserting same ID twice should raise or handle gracefully."""
        pytest.skip("RED: RecallStore not implemented")


class TestRecallStoreSearch:
    """RecallStore FTS5 search operations."""

    def test_search_by_keyword_returns_matches(self, tmp_data_dir):
        """search('深色模式') returns items containing that text."""
        pytest.skip("RED: RecallStore not implemented")

    def test_search_by_keyword_returns_empty_on_no_match(self, tmp_data_dir):
        """search('不存在的内容') returns empty list."""
        pytest.skip("RED: RecallStore not implemented")

    def test_search_returns_fts5_bm25_rank(self, tmp_data_dir):
        """Results must include raw BM25 rank score for ScoringEngine."""
        pytest.skip("RED: RecallStore not implemented")

    def test_search_by_room_filter(self, tmp_data_dir):
        """search(query, room='preferences') filters by room."""
        pytest.skip("RED: RecallStore not implemented")


class TestRecallStoreRetrieval:
    """RecallStore direct retrieval operations."""

    def test_get_by_id_returns_correct_item(self, tmp_data_dir):
        """get(id) returns the exact MemoryItem."""
        pytest.skip("RED: RecallStore not implemented")

    def test_get_by_id_returns_none_for_missing(self, tmp_data_dir):
        """get(nonexistent_id) returns None."""
        pytest.skip("RED: RecallStore not implemented")

    def test_get_recent_returns_n_most_recent(self, tmp_data_dir):
        """get_recent(n=3) returns 3 most recently created items."""
        pytest.skip("RED: RecallStore not implemented")

    def test_count_returns_correct_total(self, tmp_data_dir):
        """count() returns total number of active records."""
        pytest.skip("RED: RecallStore not implemented")


class TestRecallStoreUpdate:
    """RecallStore update operations."""

    def test_update_status_marks_superseded(self, tmp_data_dir):
        """update_status(id, SUPERSEDED) changes the status field."""
        pytest.skip("RED: RecallStore not implemented")

    def test_update_access_count_increments(self, tmp_data_dir):
        """touch(id) increments access_count and updates accessed_at."""
        pytest.skip("RED: RecallStore not implemented")
