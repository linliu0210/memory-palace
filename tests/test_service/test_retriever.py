"""
Round 5: Service — Retriever Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §4.1 S-14

Retriever combines FTS5 search with ScoringEngine ranking.
"""

import pytest


class TestRetriever:
    """Retriever search + scoring integration."""

    def test_search_uses_fts5_and_scoring(self, tmp_data_dir):
        """Results are FTS5-matched then scored by ScoringEngine."""
        pytest.skip("RED: Retriever not implemented")

    def test_search_respects_top_k(self, tmp_data_dir):
        """search(query, top_k=3) returns at most 3 results."""
        pytest.skip("RED: Retriever not implemented")

    def test_search_empty_query_returns_recent(self, tmp_data_dir):
        """Empty query fallback: return most recent items."""
        pytest.skip("RED: Retriever not implemented")

    def test_search_updates_access_count(self, tmp_data_dir):
        """Returned items have their access_count incremented."""
        pytest.skip("RED: Retriever not implemented")
