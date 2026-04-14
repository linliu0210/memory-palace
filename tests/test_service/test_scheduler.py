"""SleepTimeScheduler — asyncio background scheduler tests.

Tests the sleep-time compute scheduler that runs Curator in the background,
triggered by timer, session count, importance accumulation, or external events.

Ref: SPEC_V10 R14
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from memory_palace.models.curator import CuratorReport
from memory_palace.service.curator import CuratorService
from memory_palace.service.scheduler import SleepTimeScheduler

# ─── Helpers ─────────────────────────────────────────────────────


def _make_curator_mock(
    should_trigger_returns: tuple[bool, str] = (False, ""),
    run_delay: float = 0,
) -> MagicMock:
    """Create a mock CuratorService with controllable trigger and run."""
    mock = MagicMock(spec=CuratorService)
    mock.should_trigger.return_value = should_trigger_returns

    report = CuratorReport(
        triggered_at=datetime.now(),
        trigger_reason="timer",
        facts_extracted=1,
        memories_created=1,
        memories_updated=0,
        memories_pruned=0,
        reflections_generated=0,
        duration_seconds=0.01,
        errors=[],
    )

    async def _fake_run(since=None):
        if run_delay > 0:
            await asyncio.sleep(run_delay)
        return report

    mock.run = AsyncMock(side_effect=_fake_run)
    return mock


# ─── Tests ───────────────────────────────────────────────────────


class TestSchedulerLifecycle:
    """test_scheduler_starts_and_stops — basic start/stop lifecycle."""

    async def test_scheduler_starts_and_stops(self):
        curator = _make_curator_mock()
        scheduler = SleepTimeScheduler(curator, check_interval=300)

        assert scheduler.is_running is False

        await scheduler.start()
        assert scheduler.is_running is True

        await scheduler.stop()
        assert scheduler.is_running is False

    async def test_double_start_is_safe(self):
        """Starting twice should not create duplicate tasks."""
        curator = _make_curator_mock()
        scheduler = SleepTimeScheduler(curator, check_interval=300)

        await scheduler.start()
        await scheduler.start()  # Should be a no-op
        assert scheduler.is_running is True

        await scheduler.stop()

    async def test_double_stop_is_safe(self):
        """Stopping twice should not raise."""
        curator = _make_curator_mock()
        scheduler = SleepTimeScheduler(curator, check_interval=300)

        await scheduler.start()
        await scheduler.stop()
        await scheduler.stop()  # Should be a no-op
        assert scheduler.is_running is False


class TestSchedulerTriggerOnTimer:
    """test_scheduler_triggers_on_timer — auto-trigger via short check_interval."""

    async def test_scheduler_triggers_on_timer(self):
        """With short interval and should_trigger=True, curator.run() is called."""
        curator = _make_curator_mock(should_trigger_returns=(True, "timer"))
        scheduler = SleepTimeScheduler(curator, check_interval=0.05)

        await scheduler.start()
        # Wait for at least one cycle
        await asyncio.sleep(0.2)
        await scheduler.stop()

        assert curator.run.call_count >= 1
        assert scheduler.last_run_report is not None


class TestSchedulerTriggerOnNotify:
    """test_scheduler_triggers_on_notify — notify() wakes up the loop early."""

    async def test_scheduler_triggers_on_notify(self):
        """notify() wakes the loop from a long sleep to check immediately."""
        curator = _make_curator_mock(should_trigger_returns=(True, "importance_sum"))
        scheduler = SleepTimeScheduler(curator, check_interval=60)  # Very long interval

        await scheduler.start()
        # First check happens immediately on loop start, which triggers run()
        await asyncio.sleep(0.15)  # Let the first run() complete

        # At this point, first run is done. Loop is sleeping for 60s.
        # Reset the mock to track the next call
        curator.run.reset_mock()

        # notify should wake up the loop from 60s sleep
        scheduler.notify("save")
        await asyncio.sleep(0.3)  # Give time for wakeup + check + run
        await scheduler.stop()

        # run() was called again after notify (wouldn't happen within 60s otherwise)
        assert curator.run.call_count >= 1


class TestSchedulerCooldown:
    """test_scheduler_respects_cooldown — consecutive triggers respect cooldown."""

    async def test_scheduler_respects_cooldown(self):
        """After a successful run, cooldown prevents immediate re-trigger."""
        run_count = 0

        def trigger_with_cooldown():
            nonlocal run_count
            if run_count == 0:
                return (True, "session_count")
            # After first run, curator's own cooldown logic returns False
            return (False, "")

        curator = _make_curator_mock()
        curator.should_trigger.side_effect = lambda: trigger_with_cooldown()

        async def counting_run(since=None):
            nonlocal run_count
            run_count += 1
            return CuratorReport(
                triggered_at=datetime.now(), trigger_reason="session_count",
                facts_extracted=0, memories_created=0, memories_updated=0,
                memories_pruned=0, reflections_generated=0,
                duration_seconds=0.01, errors=[],
            )

        curator.run = AsyncMock(side_effect=counting_run)

        scheduler = SleepTimeScheduler(curator, check_interval=0.05)
        await scheduler.start()
        await asyncio.sleep(0.3)
        await scheduler.stop()

        # Should have run exactly once because cooldown blocks subsequent triggers
        assert run_count == 1


class TestSchedulerNoConcurrentRuns:
    """test_scheduler_no_concurrent_runs — curator running blocks new triggers."""

    async def test_scheduler_no_concurrent_runs(self):
        """While curator.run() is in progress, new triggers are skipped."""
        curator = _make_curator_mock(
            should_trigger_returns=(True, "timer"),
            run_delay=0.3,  # Slow run
        )

        scheduler = SleepTimeScheduler(curator, check_interval=0.05)
        await scheduler.start()
        await asyncio.sleep(0.5)  # Multiple check intervals during slow run
        await scheduler.stop()

        # Even though many checks happened, run should only start once or twice
        # (not for every check interval during the slow run)
        assert curator.run.call_count <= 2


class TestSchedulerGracefulStop:
    """test_scheduler_graceful_stop — stop waits for current cycle to complete."""

    async def test_scheduler_graceful_stop(self):
        """stop() awaits the background task completion gracefully."""
        curator = _make_curator_mock(
            should_trigger_returns=(True, "timer"),
            run_delay=0.1,
        )

        scheduler = SleepTimeScheduler(curator, check_interval=0.02)
        await scheduler.start()
        await asyncio.sleep(0.05)  # Let it enter run()

        # stop() should wait for current run to finish
        await asyncio.wait_for(scheduler.stop(), timeout=2.0)

        assert scheduler.is_running is False
        # The run should have completed (not been cancelled mid-execution)
        if curator.run.call_count > 0:
            assert scheduler.last_run_report is not None


class TestSchedulerStats:
    """test_scheduler_stats — verify trigger_count and last_trigger_reason."""

    async def test_scheduler_stats(self):
        run_count = 0

        def trigger_once():
            nonlocal run_count
            if run_count == 0:
                return (True, "session_count")
            return (False, "")

        curator = _make_curator_mock()
        curator.should_trigger.side_effect = lambda: trigger_once()

        async def counting_run(since=None):
            nonlocal run_count
            run_count += 1
            return CuratorReport(
                triggered_at=datetime.now(), trigger_reason="session_count",
                facts_extracted=2, memories_created=1, memories_updated=0,
                memories_pruned=0, reflections_generated=0,
                duration_seconds=0.05, errors=[],
            )

        curator.run = AsyncMock(side_effect=counting_run)

        scheduler = SleepTimeScheduler(curator, check_interval=0.05)

        # Before start, stats should be empty
        stats = scheduler.stats
        assert stats["trigger_count"] == 0
        assert stats["last_trigger_reason"] == ""

        await scheduler.start()
        await asyncio.sleep(0.2)
        await scheduler.stop()

        stats = scheduler.stats
        assert stats["trigger_count"] >= 1
        assert stats["last_trigger_reason"] == "session_count"


class TestSaveTriggersNotify:
    """test_save_triggers_notify — MemoryService.save() calls scheduler.notify."""

    def test_save_triggers_notify(self, tmp_data_dir):
        from memory_palace.service.memory_service import MemoryService

        svc = MemoryService(tmp_data_dir)

        # Create a mock scheduler
        mock_scheduler = MagicMock(spec=SleepTimeScheduler)
        svc.set_scheduler(mock_scheduler)

        # Create a mock curator for increment_session / record_importance
        mock_curator = MagicMock(spec=CuratorService)
        svc._curator = mock_curator

        svc.save("test content", importance=0.8, room="general")

        mock_scheduler.notify.assert_called_once_with("save")
        mock_curator.increment_session.assert_called_once()
        mock_curator.record_importance.assert_called_once_with(0.8)

    async def test_save_batch_triggers_notify(self, tmp_data_dir):
        from memory_palace.service.memory_service import MemoryService
        from tests.conftest import MockLLM

        llm = MockLLM(responses=[
            '[{"content": "fact1", "importance": 0.6, "tags": []}]'
        ])
        svc = MemoryService(tmp_data_dir, llm=llm)

        mock_scheduler = MagicMock(spec=SleepTimeScheduler)
        svc.set_scheduler(mock_scheduler)

        mock_curator = MagicMock(spec=CuratorService)
        svc._curator = mock_curator

        await svc.save_batch(["some text"])

        # notify called for each saved item
        assert mock_scheduler.notify.call_count >= 1


class TestImportanceSumTrigger:
    """test_importance_sum_trigger — importance accumulation triggers curator."""

    def test_importance_accumulates_and_resets(self, tmp_data_dir):
        """CuratorService.record_importance() accumulates, run() resets."""
        from tests.conftest import MockLLM

        llm = MockLLM(responses=['[]'])
        curator = CuratorService(tmp_data_dir, llm)

        # Accumulate importance
        curator.record_importance(2.0)
        curator.record_importance(1.5)
        assert curator._importance_sum == 3.5

        # Not yet at threshold (default 5.0)
        # Set last_run far enough past cooldown (1h) but not reaching timer (24h)
        curator._last_run_at = datetime.now() - timedelta(hours=2)
        should, reason = curator.should_trigger()
        assert should is False

        # Push over threshold
        curator.record_importance(2.0)  # Total: 5.5
        should, reason = curator.should_trigger()
        assert should is True
        assert reason == "importance_sum"

    def test_increment_session(self, tmp_data_dir):
        """CuratorService.increment_session() increments session count."""
        from tests.conftest import MockLLM

        llm = MockLLM(responses=['[]'])
        curator = CuratorService(tmp_data_dir, llm)
        curator._last_run_at = datetime.now()  # Avoid first-use trigger

        assert curator._session_count == 0
        curator.increment_session()
        assert curator._session_count == 1
        curator.increment_session()
        assert curator._session_count == 2

    async def test_run_resets_importance_sum(self, tmp_data_dir):
        """CuratorService.run() resets _importance_sum to 0."""
        from tests.conftest import MockLLM

        llm = MockLLM(responses=[
            '[]',  # fact extractor: no facts
        ])
        curator = CuratorService(tmp_data_dir, llm)
        curator.record_importance(3.0)
        assert curator._importance_sum == 3.0

        await curator.run()
        assert curator._importance_sum == 0.0


class TestSchedulerWithoutScheduler:
    """test_scheduler_without_scheduler — MemoryService works without scheduler."""

    def test_save_works_without_scheduler(self, tmp_data_dir):
        from memory_palace.service.memory_service import MemoryService

        svc = MemoryService(tmp_data_dir)
        # No scheduler set — should not raise
        item = svc.save("test", importance=0.5, room="general")
        assert item is not None
        assert item.content == "test"

    async def test_save_batch_works_without_scheduler(self, tmp_data_dir):
        from memory_palace.service.memory_service import MemoryService
        from tests.conftest import MockLLM

        llm = MockLLM(responses=[
            '[{"content": "fact1", "importance": 0.6, "tags": []}]'
        ])
        svc = MemoryService(tmp_data_dir, llm=llm)
        items = await svc.save_batch(["text"])
        assert len(items) == 1
