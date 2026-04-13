"""
Round 16: Service — HeartbeatController Tests

Tests the three-layer safety guard for CuratorGraph:
1. Step limit enforcement
2. LLM call limit enforcement
3. Duration limit enforcement
4. Dedup guard (memory_id de-duplication)
5. Integration with CuratorGraph (injection + graceful safety stop)

Ref: CONVENTIONS_V10 §7, §1 (TDD)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from memory_palace.models.errors import CuratorSafetyError
from memory_palace.models.memory import MemoryItem, MemoryTier, MemoryType
from memory_palace.service.heartbeat import HeartbeatController
from memory_palace.store.recall_store import RecallStore
from tests.conftest import MockLLM

# ============================================================
# Unit tests: HeartbeatController in isolation
# ============================================================


class TestHeartbeatTick:
    """tick() step counting and step-limit enforcement."""

    def test_tick_within_limit(self):
        """Normal ticks within max_steps do not raise."""
        hb = HeartbeatController(max_steps=5)
        for _ in range(5):
            hb.tick()  # exactly at limit, should not raise

    def test_max_steps_exceeded(self):
        """Exceeding max_steps raises CuratorSafetyError."""
        hb = HeartbeatController(max_steps=3)
        hb.tick()
        hb.tick()
        hb.tick()
        with pytest.raises(CuratorSafetyError) as exc_info:
            hb.tick()  # 4th tick → exceeds limit of 3
        assert exc_info.value.reason == "max_steps_exceeded"
        assert exc_info.value.stats["steps"] == 4


class TestHeartbeatLLMCalls:
    """record_llm_call() counting and LLM-call limit enforcement."""

    def test_llm_calls_within_limit(self):
        """LLM calls within max_llm_calls do not raise."""
        hb = HeartbeatController(max_llm_calls=3)
        for _ in range(3):
            hb.record_llm_call()

    def test_max_llm_calls_exceeded(self):
        """Exceeding max_llm_calls raises CuratorSafetyError."""
        hb = HeartbeatController(max_llm_calls=2)
        hb.record_llm_call()
        hb.record_llm_call()
        with pytest.raises(CuratorSafetyError) as exc_info:
            hb.record_llm_call()  # 3rd call → exceeds limit of 2
        assert exc_info.value.reason == "max_llm_calls_exceeded"
        assert exc_info.value.stats["llm_calls"] == 3


class TestHeartbeatDuration:
    """Duration (wall-clock) limit enforcement via time.monotonic()."""

    def test_max_duration_exceeded_on_tick(self):
        """tick() raises when duration exceeded (mocked monotonic)."""
        hb = HeartbeatController(max_duration_seconds=10)

        # Simulate time passing beyond the limit
        with patch("memory_palace.service.heartbeat.time") as mock_time:
            # First .monotonic() call in __init__ already happened, set start manually
            hb._start_time = 1000.0
            mock_time.monotonic.return_value = 1011.0  # 11 seconds → over 10s limit
            with pytest.raises(CuratorSafetyError) as exc_info:
                hb.tick()
            assert exc_info.value.reason == "max_duration_exceeded"

    def test_max_duration_exceeded_on_llm_call(self):
        """record_llm_call() also checks duration."""
        hb = HeartbeatController(max_duration_seconds=5)
        with patch("memory_palace.service.heartbeat.time") as mock_time:
            hb._start_time = 1000.0
            mock_time.monotonic.return_value = 1006.0  # 6 seconds → over 5s limit
            with pytest.raises(CuratorSafetyError) as exc_info:
                hb.record_llm_call()
            assert exc_info.value.reason == "max_duration_exceeded"


class TestHeartbeatDedup:
    """check_dedup() memory_id de-duplication."""

    def test_first_time_returns_false(self):
        """First encounter of a memory_id returns False (proceed)."""
        hb = HeartbeatController()
        assert hb.check_dedup("mem-001") is False

    def test_second_time_returns_true(self):
        """Second encounter of same memory_id returns True (skip)."""
        hb = HeartbeatController()
        hb.check_dedup("mem-001")
        assert hb.check_dedup("mem-001") is True

    def test_dedup_skipped_counter(self):
        """dedup_skipped stat increments on duplicate encounters."""
        hb = HeartbeatController()
        hb.check_dedup("mem-001")
        hb.check_dedup("mem-001")  # duplicate → skip
        hb.check_dedup("mem-002")  # new → not a skip
        hb.check_dedup("mem-001")  # duplicate again → skip
        assert hb.stats["dedup_skipped"] == 2


class TestHeartbeatReset:
    """reset() clears all counters and state."""

    def test_reset_clears_all(self):
        """After reset(), all counters are zeroed and seen_ids is empty."""
        hb = HeartbeatController(max_steps=100, max_llm_calls=100)
        hb.tick()
        hb.tick()
        hb.record_llm_call()
        hb.check_dedup("mem-001")
        hb.check_dedup("mem-001")  # +1 dedup_skipped

        hb.reset()

        stats = hb.stats
        assert stats["steps"] == 0
        assert stats["llm_calls"] == 0
        assert stats["dedup_skipped"] == 0
        # After reset, the same ID is "new" again
        assert hb.check_dedup("mem-001") is False


class TestHeartbeatStats:
    """stats property reflects real counters accurately."""

    def test_stats_accuracy(self):
        """stats dict mirrors actual tick/llm_call/dedup counts."""
        hb = HeartbeatController(max_steps=100, max_llm_calls=100)
        hb.tick()
        hb.tick()
        hb.tick()
        hb.record_llm_call()
        hb.record_llm_call()
        hb.check_dedup("a")
        hb.check_dedup("b")
        hb.check_dedup("a")  # dup

        stats = hb.stats
        assert stats["steps"] == 3
        assert stats["llm_calls"] == 2
        assert stats["dedup_skipped"] == 1
        assert isinstance(stats["elapsed_seconds"], float)
        assert stats["elapsed_seconds"] >= 0


# ============================================================
# Integration tests: HeartbeatController ↔ CuratorGraph
# ============================================================


def _seed_recall(tmp_data_dir, n=3, importance=0.5):
    """Seed RecallStore with n items."""
    recall = RecallStore(tmp_data_dir)
    items = []
    for i in range(n):
        item = MemoryItem(
            content=f"种子记忆 {i}",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.RECALL,
            importance=importance,
        )
        recall.insert(item)
        items.append(item)
    return items


def _make_graph_with_heartbeat(tmp_data_dir, llm, heartbeat=None):
    """Create CuratorGraph with optional HeartbeatController."""
    from memory_palace.engine.fact_extractor import FactExtractor
    from memory_palace.engine.reconcile import ReconcileEngine
    from memory_palace.service.curator_graph import CuratorGraph
    from memory_palace.service.memory_service import MemoryService

    ms = MemoryService(tmp_data_dir, llm=llm)
    return CuratorGraph(
        memory_service=ms,
        recall_store=ms._recall_store,
        core_store=ms._core_store,
        fact_extractor=FactExtractor(llm),
        reconcile_engine=ReconcileEngine(llm),
        llm=llm,
        heartbeat=heartbeat,
    )


class TestCuratorGraphHeartbeatIntegration:
    """CuratorGraph with HeartbeatController injection."""

    @pytest.mark.asyncio
    async def test_curator_graph_with_heartbeat_normal(self, tmp_data_dir):
        """CuratorGraph completes normally with generous heartbeat limits."""
        _seed_recall(tmp_data_dir)

        llm = MockLLM(
            responses=[
                '[{"content": "新事实", "importance": 0.5, "tags": []}]',
                '{"action": "ADD", "target_id": null, "reason": "new"}',
            ]
        )
        hb = HeartbeatController(max_steps=100, max_llm_calls=100)
        graph = _make_graph_with_heartbeat(tmp_data_dir, llm, heartbeat=hb)
        report = await graph.run()

        assert report.facts_extracted >= 1
        assert hb.stats["steps"] > 0
        assert hb.stats["llm_calls"] > 0

    @pytest.mark.asyncio
    async def test_curator_graph_safety_stop(self, tmp_data_dir):
        """CuratorGraph gracefully reports when heartbeat trips safety."""
        _seed_recall(tmp_data_dir)

        llm = MockLLM(
            responses=[
                '[{"content": "fact", "importance": 0.5, "tags": []}]',
                '{"action": "ADD", "target_id": null, "reason": "new"}',
            ]
        )
        # max_steps=1 → will trip on 2nd phase transition
        hb = HeartbeatController(max_steps=1, max_llm_calls=100)
        graph = _make_graph_with_heartbeat(tmp_data_dir, llm, heartbeat=hb)
        report = await graph.run()

        # Should produce a report (not crash) with safety error logged
        assert report is not None
        assert any("max_steps_exceeded" in e for e in report.errors)

    @pytest.mark.asyncio
    async def test_curator_graph_without_heartbeat_backward_compat(self, tmp_data_dir):
        """CuratorGraph without heartbeat works identically to before (v0.2 compat)."""
        _seed_recall(tmp_data_dir)

        llm = MockLLM(
            responses=[
                '[{"content": "fact", "importance": 0.5, "tags": []}]',
                '{"action": "NOOP", "target_id": null, "reason": "known"}',
            ]
        )
        graph = _make_graph_with_heartbeat(tmp_data_dir, llm, heartbeat=None)
        report = await graph.run()

        assert report is not None
        assert report.health is not None
