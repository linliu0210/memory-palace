"""
Round 5: Service — Retriever Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §4.1 S-14

Retriever combines FTS5 search with ScoringEngine ranking.
"""

from memory_palace.models.memory import MemoryItem, MemoryTier, MemoryType
from memory_palace.service.retriever import Retriever
from memory_palace.store.recall_store import RecallStore


class TestRetriever:
    """Retriever search + scoring integration."""

    def test_search_uses_fts5_and_scoring(self, tmp_data_dir):
        """Results are FTS5-matched then scored by ScoringEngine."""
        recall = RecallStore(tmp_data_dir)
        # Insert items with different importance
        item1 = MemoryItem(
            content="Python用于机器学习",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.RECALL,
            importance=0.3,
        )
        item2 = MemoryItem(
            content="Python是最流行的编程语言",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.RECALL,
            importance=0.6,
        )
        recall.insert(item1)
        recall.insert(item2)

        retriever = Retriever(recall)
        results = retriever.search("Python")

        assert len(results) >= 1
        # All results should contain Python content
        for item in results:
            assert "Python" in item.content

    def test_search_respects_top_k(self, tmp_data_dir):
        """search(query, top_k=3) returns at most 3 results."""
        recall = RecallStore(tmp_data_dir)
        # Insert 5 items
        for i in range(5):
            item = MemoryItem(
                content=f"测试数据项目 {i}",
                memory_type=MemoryType.OBSERVATION,
                tier=MemoryTier.RECALL,
                importance=0.5,
            )
            recall.insert(item)

        retriever = Retriever(recall)
        results = retriever.search("测试数据", top_k=3)

        assert len(results) <= 3

    def test_search_empty_query_returns_recent(self, tmp_data_dir):
        """Empty query fallback: return most recent items."""
        recall = RecallStore(tmp_data_dir)
        item = MemoryItem(
            content="最近的记忆",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.RECALL,
            importance=0.5,
        )
        recall.insert(item)

        retriever = Retriever(recall)
        results = retriever.search("")

        assert len(results) >= 1
        assert results[0].content == "最近的记忆"

    def test_search_updates_access_count(self, tmp_data_dir):
        """Returned items have their access_count incremented."""
        recall = RecallStore(tmp_data_dir)
        item = MemoryItem(
            content="追踪访问次数的记忆",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.RECALL,
            importance=0.5,
        )
        recall.insert(item)

        retriever = Retriever(recall)
        retriever.search("访问次数")

        # Check access count was incremented
        updated = recall.get(item.id)
        assert updated is not None
        assert updated.access_count >= 1
