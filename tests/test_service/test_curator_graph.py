"""
Round 12: Service — CuratorGraph Tests

IMMUTABLE SPEC: Ref: SPEC_V02 §2.4, §9.1

CuratorGraph — Pure Python State Machine:
  GATHER → EXTRACT → RECONCILE → REFLECT → PRUNE → HEALTH_CHECK → REPORT

Tests the state machine flow, error handling, and health score integration.
"""


import pytest

from memory_palace.models.memory import MemoryItem, MemoryTier, MemoryType
from memory_palace.service.curator_graph import CuratorGraph, CuratorState
from memory_palace.store.recall_store import RecallStore
from tests.conftest import MockLLM


def _seed_recall(tmp_data_dir, n=3, importance=0.5):
    """Helper: seed RecallStore with n items."""
    recall = RecallStore(tmp_data_dir)
    items = []
    for i in range(n):
        item = MemoryItem(
            content=f"种子记忆内容 {i}",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.RECALL,
            importance=importance,
        )
        recall.insert(item)
        items.append(item)
    return items


def _make_graph(tmp_data_dir, llm):
    """Helper: create CuratorGraph with shared stores."""
    from memory_palace.engine.fact_extractor import FactExtractor
    from memory_palace.engine.reconcile import ReconcileEngine
    from memory_palace.service.memory_service import MemoryService

    ms = MemoryService(tmp_data_dir, llm=llm)
    recall = ms._recall_store
    core = ms._core_store
    fe = FactExtractor(llm)
    re_engine = ReconcileEngine(llm)

    return CuratorGraph(
        memory_service=ms,
        recall_store=recall,
        core_store=core,
        fact_extractor=fe,
        reconcile_engine=re_engine,
        llm=llm,
    )


class TestCuratorGraphFlow:
    """CuratorGraph state machine full pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_add(self, tmp_data_dir):
        """Full pipeline: gather → extract → reconcile (ADD) → health → report."""
        _seed_recall(tmp_data_dir)

        llm = MockLLM(
            responses=[
                '[{"content": "新事实A", "importance": 0.5, "tags": []}]',
                '{"action": "ADD", "target_id": null, "reason": "new info"}',
            ]
        )
        graph = _make_graph(tmp_data_dir, llm)
        report = await graph.run()

        assert report.facts_extracted >= 1
        assert report.memories_created >= 1
        assert report.trigger_reason == "manual"
        assert report.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_empty_recall_skips_to_health(self, tmp_data_dir):
        """Empty RecallStore → GATHER skips to HEALTH_CHECK → REPORT."""
        llm = MockLLM(responses=["[]"])
        graph = _make_graph(tmp_data_dir, llm)

        report = await graph.run()

        assert report.facts_extracted == 0
        assert report.memories_created == 0
        assert report.health is not None

    @pytest.mark.asyncio
    async def test_health_score_populated(self, tmp_data_dir):
        """Report includes 5-dimension health score."""
        _seed_recall(tmp_data_dir)

        llm = MockLLM(
            responses=[
                '[{"content": "fact", "importance": 0.5, "tags": []}]',
                '{"action": "NOOP", "target_id": null, "reason": "already known"}',
            ]
        )
        graph = _make_graph(tmp_data_dir, llm)
        report = await graph.run()

        assert report.health is not None
        assert 0 <= report.health.freshness <= 1
        assert 0 <= report.health.efficiency <= 1
        assert 0 <= report.health.coherence <= 1

    @pytest.mark.asyncio
    async def test_error_in_extract_continues(self, tmp_data_dir):
        """Error in EXTRACT doesn't crash — pipeline continues to RECONCILE."""
        _seed_recall(tmp_data_dir)

        # Malformed JSON causes FactExtractor to return []
        llm = MockLLM(responses=["not json at all {{{{"])
        graph = _make_graph(tmp_data_dir, llm)

        report = await graph.run()

        # Should still complete with 0 facts
        assert report.facts_extracted == 0
        assert report.health is not None


class TestCuratorState:
    """CuratorState initialization."""

    def test_state_defaults(self):
        """CuratorState initializes with empty defaults."""
        state = CuratorState()
        assert state.items == []
        assert state.facts == []
        assert state.errors == []
        assert state.health is None
        assert state.report is None
        assert state.facts_extracted == 0
