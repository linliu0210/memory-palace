"""
Round 10: HybridRetriever — FTS5 + Vector hybrid search with RRF fusion.

SPEC Ref: SPEC_V02 §2.4 HybridRetriever, §RRF 算法
Tests hybrid combine, FTS5-only fallback, RRF merge, room/importance filters.
"""


from memory_palace.models.memory import MemoryItem, MemoryTier, MemoryType
from memory_palace.service.hybrid_retriever import HybridRetriever, reciprocal_rank_fusion
from memory_palace.store.recall_store import RecallStore

# pytest-asyncio auto-mode: all async tests run automatically


# ── Helpers ──────────────────────────────────────────────────


def _make_item(
    content: str = "test",
    importance: float = 0.5,
    room: str = "general",
    tier: MemoryTier = MemoryTier.RECALL,
) -> MemoryItem:
    """Create a minimal MemoryItem."""
    return MemoryItem(
        content=content,
        memory_type=MemoryType.OBSERVATION,
        tier=tier,
        importance=importance,
        room=room,
    )


def _insert_items(recall: RecallStore, items: list[MemoryItem]) -> None:
    """Insert multiple items into RecallStore."""
    for item in items:
        recall.insert(item)


# ============================================================
# reciprocal_rank_fusion (unit)
# ============================================================


class TestReciprocalRankFusion:
    """RRF merges multiple rankings into a single fused ranking."""

    def test_single_ranking(self):
        """Single ranking → preserves order."""
        rankings = [["a", "b", "c"]]
        result = reciprocal_rank_fusion(rankings)
        ids = [doc_id for doc_id, _ in result]
        assert ids == ["a", "b", "c"]

    def test_two_rankings_agree(self):
        """Two rankings with same order → same output order."""
        rankings = [["a", "b", "c"], ["a", "b", "c"]]
        result = reciprocal_rank_fusion(rankings)
        ids = [doc_id for doc_id, _ in result]
        assert ids[0] == "a"  # a is ranked first in both

    def test_two_rankings_disagree(self):
        """With conflicting rankings, item consistently ranked high wins."""
        rankings = [
            ["a", "b", "c", "d"],  # ranking 1: b=2nd
            ["d", "b", "c", "a"],  # ranking 2: b=2nd
        ]
        result = reciprocal_rank_fusion(rankings)
        ids = [doc_id for doc_id, _ in result]
        # b is 2nd in both → highest combined RRF score
        assert ids[0] == "b"

    def test_empty_rankings(self):
        """No rankings → empty result."""
        result = reciprocal_rank_fusion([])
        assert result == []

    def test_empty_individual_rankings(self):
        """Empty individual rankings → empty result."""
        result = reciprocal_rank_fusion([[], []])
        assert result == []

    def test_disjoint_rankings(self):
        """Items appearing in only one ranking still included."""
        rankings = [["a", "b"], ["c", "d"]]
        result = reciprocal_rank_fusion(rankings)
        ids = {doc_id for doc_id, _ in result}
        assert ids == {"a", "b", "c", "d"}

    def test_scores_are_positive(self):
        """All RRF scores are positive floats."""
        rankings = [["a", "b", "c"]]
        result = reciprocal_rank_fusion(rankings)
        for _, score in result:
            assert score > 0.0

    def test_custom_k_parameter(self):
        """Custom k changes scores but not relative order."""
        rankings = [["a", "b", "c"]]
        result_k60 = reciprocal_rank_fusion(rankings, k=60)
        result_k10 = reciprocal_rank_fusion(rankings, k=10)
        # Order should be same
        ids_k60 = [doc_id for doc_id, _ in result_k60]
        ids_k10 = [doc_id for doc_id, _ in result_k10]
        assert ids_k60 == ids_k10
        # But scores differ
        score_k60 = result_k60[0][1]
        score_k10 = result_k10[0][1]
        assert score_k60 != score_k10


# ============================================================
# HybridRetriever — FTS5-only fallback
# ============================================================


class TestHybridRetrieverFTSOnly:
    """When archival_store=None, HybridRetriever degrades to FTS5-only."""

    async def test_fts_only_fallback(self, tmp_data_dir):
        """FTS5-only mode returns matched results."""
        recall = RecallStore(tmp_data_dir)
        items = [
            _make_item(content="Python is great for ML"),
            _make_item(content="Java is great for enterprise"),
        ]
        _insert_items(recall, items)

        retriever = HybridRetriever(
            recall_store=recall,
            archival_store=None,
            embedding=None,
        )
        results = await retriever.search("Python")
        assert len(results) >= 1
        assert any("Python" in r.content for r in results)

    async def test_fts_only_empty_query_returns_recent(self, tmp_data_dir):
        """FTS5-only: empty query fallback returns recent items."""
        recall = RecallStore(tmp_data_dir)
        item = _make_item(content="recent memory item")
        recall.insert(item)

        retriever = HybridRetriever(
            recall_store=recall,
            archival_store=None,
            embedding=None,
        )
        results = await retriever.search("")
        assert len(results) >= 1

    async def test_fts_only_respects_top_k(self, tmp_data_dir):
        """top_k limits number of results."""
        recall = RecallStore(tmp_data_dir)
        for i in range(5):
            recall.insert(_make_item(content=f"data item {i}"))

        retriever = HybridRetriever(
            recall_store=recall,
            archival_store=None,
            embedding=None,
        )
        results = await retriever.search("data", top_k=2)
        assert len(results) <= 2

    async def test_fts_only_touches_returned_items(self, tmp_data_dir):
        """Returned items have access_count incremented."""
        recall = RecallStore(tmp_data_dir)
        item = _make_item(content="trackable access count item")
        recall.insert(item)

        retriever = HybridRetriever(
            recall_store=recall,
            archival_store=None,
            embedding=None,
        )
        await retriever.search("trackable")

        updated = recall.get(item.id)
        assert updated is not None
        assert updated.access_count >= 1


# ============================================================
# HybridRetriever — Hybrid mode (FTS5 + Vector)
# ============================================================


class TestHybridRetrieverHybrid:
    """Full hybrid mode with both FTS5 and Vector search."""

    async def test_hybrid_combines_fts_and_vector(self, tmp_data_dir, mock_embedding):
        """Hybrid search returns results from both FTS5 and Vector channels."""
        import chromadb

        recall = RecallStore(tmp_data_dir)
        client = chromadb.EphemeralClient()

        from memory_palace.store.archival_store import ArchivalStore

        archival = ArchivalStore(client=client, embedding=mock_embedding)

        # Insert items — some only match keyword, some only match semantically
        keyword_item = _make_item(content="Python programming language tutorial")
        semantic_item = _make_item(content="coding with serpent-based syntax")

        recall.insert(keyword_item)
        recall.insert(semantic_item)
        await archival.insert(keyword_item)
        await archival.insert(semantic_item)

        retriever = HybridRetriever(
            recall_store=recall,
            archival_store=archival,
            embedding=mock_embedding,
        )
        results = await retriever.search("Python")

        # Should return at least the keyword-matched item
        assert len(results) >= 1
        contents = [r.content for r in results]
        assert "Python programming language tutorial" in contents

    async def test_hybrid_room_filter(self, tmp_data_dir, mock_embedding):
        """Room filter limits results to specified room."""
        import chromadb

        recall = RecallStore(tmp_data_dir)
        client = chromadb.EphemeralClient()

        from memory_palace.store.archival_store import ArchivalStore

        archival = ArchivalStore(client=client, embedding=mock_embedding)

        projects_item = _make_item(content="project task deadline", room="projects")
        general_item = _make_item(content="general task note", room="general")

        recall.insert(projects_item)
        recall.insert(general_item)
        await archival.insert(projects_item)
        await archival.insert(general_item)

        retriever = HybridRetriever(
            recall_store=recall,
            archival_store=archival,
            embedding=mock_embedding,
        )
        results = await retriever.search("task", room="projects")

        # All results must be from "projects" room
        for item in results:
            assert item.room == "projects"

    async def test_hybrid_min_importance_filter(self, tmp_data_dir, mock_embedding):
        """min_importance filters out low-importance items."""
        import chromadb

        recall = RecallStore(tmp_data_dir)
        client = chromadb.EphemeralClient()

        from memory_palace.store.archival_store import ArchivalStore

        archival = ArchivalStore(client=client, embedding=mock_embedding)

        high = _make_item(content="important data analysis", importance=0.9)
        low = _make_item(content="minor data note", importance=0.1)

        recall.insert(high)
        recall.insert(low)
        await archival.insert(high)
        await archival.insert(low)

        retriever = HybridRetriever(
            recall_store=recall,
            archival_store=archival,
            embedding=mock_embedding,
        )
        results = await retriever.search("data", min_importance=0.5)

        for item in results:
            assert item.importance >= 0.5

    async def test_hybrid_empty_query_returns_recent(self, tmp_data_dir, mock_embedding):
        """Empty query in hybrid mode still returns recent items."""
        import chromadb

        recall = RecallStore(tmp_data_dir)
        client = chromadb.EphemeralClient()

        from memory_palace.store.archival_store import ArchivalStore

        archival = ArchivalStore(client=client, embedding=mock_embedding)

        item = _make_item(content="a recent memory for empty query")
        recall.insert(item)
        await archival.insert(item)

        retriever = HybridRetriever(
            recall_store=recall,
            archival_store=archival,
            embedding=mock_embedding,
        )
        results = await retriever.search("")
        assert len(results) >= 1

    async def test_hybrid_touches_returned_items(self, tmp_data_dir, mock_embedding):
        """Hybrid retriever touches (updates access_count) returned items."""
        import chromadb

        recall = RecallStore(tmp_data_dir)
        client = chromadb.EphemeralClient()

        from memory_palace.store.archival_store import ArchivalStore

        archival = ArchivalStore(client=client, embedding=mock_embedding)

        item = _make_item(content="touchable hybrid result")
        recall.insert(item)
        await archival.insert(item)

        retriever = HybridRetriever(
            recall_store=recall,
            archival_store=archival,
            embedding=mock_embedding,
        )
        await retriever.search("touchable")

        updated = recall.get(item.id)
        assert updated is not None
        assert updated.access_count >= 1
