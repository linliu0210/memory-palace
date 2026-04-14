"""Phase A E2E tests — Scheduler + Ebbinghaus + Heartbeat integration.

Validates that R14-R16 components work together end-to-end:
- SleepTimeScheduler triggers CuratorService automatically
- Ebbinghaus decay drives pruning decisions
- HeartbeatController prevents runaway execution
- Backward compatibility with v0.2 behavior

All tests use MockLLM + tmp_path, no real LLM calls.

Ref: TASK_R17
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta

import pytest

from memory_palace.config import EbbinghausConfig
from memory_palace.engine.ebbinghaus import effective_importance, should_prune
from memory_palace.models.memory import MemoryStatus
from memory_palace.service.curator import CuratorService
from memory_palace.service.curator_graph import CuratorGraph
from memory_palace.service.heartbeat import HeartbeatController
from memory_palace.service.memory_service import MemoryService
from memory_palace.service.scheduler import SleepTimeScheduler
from memory_palace.store.recall_store import RecallStore

# ── Helpers ───────────────────────────────────────────────────


def _make_mock_llm_responses() -> list[str]:
    """Standard mock responses for a full curator cycle.

    Returns extract (1 fact) + reconcile (NOOP) + reflect (empty).
    """
    return [
        # FactExtractor response
        json.dumps([{
            "content": "测试事实",
            "importance": 0.5,
            "tags": ["test"],
        }]),
        # ReconcileEngine response
        json.dumps({"action": "NOOP", "target_id": None, "reason": "already known"}),
        # ReflectionEngine response (empty)
        json.dumps([]),
    ]


# ── Test: importance_sum accumulation + trigger ───────────────


class TestSaveAccumulatesImportanceSum:
    """save() accumulates importance_sum → triggers scheduler."""

    async def test_importance_sum_triggers(self, tmp_data_dir):
        """Save N memories → importance_sum >= 5.0 → should_trigger = True."""
        from tests.conftest import MockLLM

        llm = MockLLM(responses=_make_mock_llm_responses())
        ms = MemoryService(tmp_data_dir, llm)
        curator = CuratorService(tmp_data_dir, llm)
        # Wire up
        ms._curator = curator
        # Set last_run_at so cooldown doesn't interfere
        curator._last_run_at = datetime.now() - timedelta(hours=2)

        # Each save with importance 0.6 → need at least 9 saves to reach 5.0
        for i in range(8):
            ms.save(content=f"记忆 {i}", importance=0.6)

        # importance_sum = 8 × 0.6 = 4.8 → not triggered
        triggered, reason = curator.should_trigger()
        assert not triggered

        # One more save → 5.4 → triggered
        ms.save(content="最后一条", importance=0.6)
        triggered, reason = curator.should_trigger()
        assert triggered
        assert reason == "importance_sum"


# ── Test: Ebbinghaus decay lifecycle ─────────────────────────


class TestEbbinghausDecayLifecycle:
    """Save → time passes → effective_importance decays → prune."""

    async def test_decay_and_prune(self, tmp_data_dir):
        """Old memory with low importance gets pruned by Ebbinghaus."""
        from tests.conftest import MockLLM

        llm = MockLLM(responses=_make_mock_llm_responses())

        # 1. Save a memory with moderate importance
        ms = MemoryService(tmp_data_dir, llm)
        item = ms.save(content="临时信息", importance=0.3, room="general")

        # 2. Simulate time → set accessed_at to 30 days ago
        recall_store = RecallStore(tmp_data_dir)
        old_time = (datetime.now() - timedelta(days=30)).isoformat()
        recall_store.update_field(item.id, "accessed_at", old_time)

        # 3. Verify Ebbinghaus says prune
        hours_since = 30 * 24  # 720 hours
        assert should_prune(
            importance=0.3,
            hours_since_access=hours_since,
            access_count=0,
            threshold=0.05,
        )

        # 4. Run curator with Ebbinghaus enabled
        eb_cfg = EbbinghausConfig(enabled=True, base_stability_hours=168.0)
        curator = CuratorService(tmp_data_dir, llm)
        curator._heartbeat = HeartbeatController(
            max_steps=100, max_llm_calls=50, max_duration_seconds=30,
        )

        graph = CuratorGraph(
            memory_service=ms,
            recall_store=recall_store,
            core_store=ms._core_store,
            fact_extractor=curator._fact_extractor,
            reconcile_engine=curator._reconcile_engine,
            llm=llm,
            ebbinghaus_config=eb_cfg,
            heartbeat=curator._heartbeat,
        )
        report = await graph.run()

        # 5. Verify the memory was pruned by Ebbinghaus
        assert report.ebbinghaus_pruned >= 1
        assert report.memories_pruned >= 1

        # 6. Verify the item is actually PRUNED in the store
        pruned_item = recall_store.get(item.id)
        assert pruned_item is not None
        assert pruned_item.status == MemoryStatus.PRUNED

    def test_effective_importance_decays_with_time(self):
        """Pure function: effective_importance decreases over time."""
        ei_fresh = effective_importance(0.5, hours_since_access=0)
        ei_1week = effective_importance(0.5, hours_since_access=168)
        ei_1month = effective_importance(0.5, hours_since_access=720)

        assert ei_fresh == pytest.approx(0.5)
        assert ei_1week < ei_fresh
        assert ei_1month < ei_1week
        assert ei_1month < 0.1  # Should be quite low after a month

    def test_access_count_slows_decay(self):
        """More accesses → higher stability → slower decay."""
        ei_no_access = effective_importance(0.5, hours_since_access=336, access_count=0)
        ei_many_access = effective_importance(0.5, hours_since_access=336, access_count=10)

        assert ei_many_access > ei_no_access


# ── Test: Heartbeat prevents runaway ─────────────────────────


class TestHeartbeatPreventsRunaway:
    """HeartbeatController stops CuratorGraph when limits are breached."""

    async def test_max_steps_stops_graph(self, tmp_data_dir):
        """max_steps=3 → curator stops early, report.errors has safety info."""
        from tests.conftest import MockLLM

        # Many responses to keep the graph busy
        llm = MockLLM(responses=_make_mock_llm_responses())

        ms = MemoryService(tmp_data_dir, llm)
        # Save some items so the graph has work to do
        for i in range(5):
            ms.save(content=f"记忆 {i}", importance=0.4)

        recall_store = RecallStore(tmp_data_dir)
        from memory_palace.engine.fact_extractor import FactExtractor
        from memory_palace.engine.reconcile import ReconcileEngine

        heartbeat = HeartbeatController(
            max_steps=3,
            max_llm_calls=50,
            max_duration_seconds=120,
        )

        graph = CuratorGraph(
            memory_service=ms,
            recall_store=recall_store,
            core_store=ms._core_store,
            fact_extractor=FactExtractor(llm),
            reconcile_engine=ReconcileEngine(llm),
            llm=llm,
            heartbeat=heartbeat,
        )

        report = await graph.run()

        # Should have safety error in report
        assert any("Safety" in e for e in report.errors)
        assert any("max_steps_exceeded" in e for e in report.errors)


# ── Test: Scheduler integration ──────────────────────────────


class TestSchedulerIntegration:
    """SleepTimeScheduler triggers CuratorService automatically."""

    async def test_scheduler_auto_trigger(self, tmp_data_dir):
        """Start scheduler → save memories → auto-trigger → verify curate ran."""
        from tests.conftest import MockLLM

        llm = MockLLM(responses=_make_mock_llm_responses())
        ms = MemoryService(tmp_data_dir, llm)
        curator = CuratorService(tmp_data_dir, llm)
        ms._curator = curator

        # Very short interval for fast test
        scheduler = SleepTimeScheduler(curator, check_interval=0.1)
        ms.set_scheduler(scheduler)

        # Start scheduler
        await scheduler.start()
        assert scheduler.is_running

        try:
            # Since curator._last_run_at is None, should_trigger returns True
            # on initial timer trigger. Wait for one cycle.
            await asyncio.sleep(0.3)

            # Check that scheduler ran at least once
            assert scheduler.stats["trigger_count"] >= 1
            assert scheduler.last_run_report is not None
        finally:
            await scheduler.stop()

        assert not scheduler.is_running

    async def test_scheduler_stop_idempotent(self, tmp_data_dir):
        """Calling stop() multiple times is safe."""
        from tests.conftest import MockLLM

        llm = MockLLM(responses=_make_mock_llm_responses())
        curator = CuratorService(tmp_data_dir, llm)
        scheduler = SleepTimeScheduler(curator, check_interval=0.1)

        await scheduler.start()
        await scheduler.stop()
        await scheduler.stop()  # Should not raise
        assert not scheduler.is_running


# ── Test: Full Phase A lifecycle ─────────────────────────────


class TestFullPhaseALifecycle:
    """Comprehensive: save → decay → auto-trigger → curate with heartbeat."""

    async def test_full_lifecycle(self, tmp_data_dir):
        """End-to-end: save → Ebbinghaus decay → heartbeat safety → report."""
        from tests.conftest import MockLLM

        llm = MockLLM(responses=_make_mock_llm_responses())
        ms = MemoryService(tmp_data_dir, llm)

        # 1. Save some memories
        _high_item = ms.save(content="重要的持久记忆", importance=0.9, room="general")
        low_item = ms.save(content="低重要性暂时信息", importance=0.2, room="general")

        # 2. Simulate aging the low-importance memory
        recall_store = RecallStore(tmp_data_dir)
        old_time = (datetime.now() - timedelta(days=60)).isoformat()
        recall_store.update_field(low_item.id, "accessed_at", old_time)

        # 3. Build curator with Ebbinghaus + Heartbeat
        eb_cfg = EbbinghausConfig(enabled=True)
        heartbeat = HeartbeatController(
            max_steps=50, max_llm_calls=30, max_duration_seconds=30,
        )

        graph = CuratorGraph(
            memory_service=ms,
            recall_store=recall_store,
            core_store=ms._core_store,
            fact_extractor=ms._fact_extractor,
            reconcile_engine=ms._fact_extractor,  # Won't be called — NOOP
            llm=llm,
            ebbinghaus_config=eb_cfg,
            heartbeat=heartbeat,
        )

        # Need proper reconcile engine
        from memory_palace.engine.reconcile import ReconcileEngine

        graph._reconcile_engine = ReconcileEngine(llm)

        report = await graph.run()

        # 4. Verify: low-importance old memory should be pruned
        assert report.memories_pruned >= 1
        pruned = recall_store.get(low_item.id)
        assert pruned is not None
        assert pruned.status == MemoryStatus.PRUNED

        # 5. Heartbeat did NOT trigger (normal operation)
        assert not any("max_steps_exceeded" in e for e in report.errors)

        # 6. Duration should be recorded
        assert report.duration_seconds > 0


# ── Test: Backward compatibility ─────────────────────────────


class TestBackwardCompatibility:
    """v0.2 behavior preserved when no scheduler/ebbinghaus configured."""

    async def test_v02_behavior_unchanged(self, tmp_data_dir):
        """No scheduler, no ebbinghaus → v0.2 curate path still works."""
        from tests.conftest import MockLLM

        llm = MockLLM(responses=_make_mock_llm_responses())
        ms = MemoryService(tmp_data_dir, llm)

        # Save some memories
        ms.save(content="记忆一", importance=0.5)
        ms.save(content="记忆二", importance=0.3)

        # Run curator without Ebbinghaus (default: ebbinghaus_config=None)
        curator = CuratorService(tmp_data_dir, llm)
        report = await curator.run()

        # Basic curator logic should work
        assert report is not None
        assert report.duration_seconds >= 0
        assert report.ebbinghaus_pruned == 0  # No Ebbinghaus without config

    async def test_no_scheduler_no_side_effects(self, tmp_data_dir):
        """MemoryService without scheduler → save works normally."""
        ms = MemoryService(tmp_data_dir)
        item = ms.save(content="测试", importance=0.5)
        assert item.id is not None
        assert ms._scheduler is None
        assert ms._curator is None
