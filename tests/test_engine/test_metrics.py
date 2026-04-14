"""
Round 23: MemoryMetrics — Operational metrics collection + OperationTimer.

SPEC Ref: TASK_R23
Tests: record_search, record_save, record_curate, growth_rate, summary_format,
       p95_calculation, empty_metrics, operation_timer, health_operations_dimension,
       metrics_rolling_window.
"""

from datetime import datetime

import pytest

from memory_palace.config import RoomConfig
from memory_palace.engine.health import (
    MemoryHealthScore,
    compute_health,
    compute_operations_score,
)
from memory_palace.engine.metrics import (
    MemoryMetrics,
    OperationTimer,
    _percentile,
)
from memory_palace.models.memory import MemoryItem, MemoryStatus, MemoryTier, MemoryType

# ── Helpers ──────────────────────────────────────────────────


def _make_item(
    content: str = "test",
    importance: float = 0.5,
    room: str = "general",
    memory_type: MemoryType = MemoryType.OBSERVATION,
    status: MemoryStatus = MemoryStatus.ACTIVE,
    tier: MemoryTier = MemoryTier.RECALL,
    accessed_at: datetime | None = None,
) -> MemoryItem:
    """Create a minimal MemoryItem for testing."""
    return MemoryItem(
        content=content,
        memory_type=memory_type,
        tier=tier,
        importance=importance,
        room=room,
        status=status,
        accessed_at=accessed_at or datetime.now(),
    )


DEFAULT_ROOMS = [
    RoomConfig(name="general"),
    RoomConfig(name="preferences"),
    RoomConfig(name="projects"),
    RoomConfig(name="people"),
    RoomConfig(name="skills"),
]


# ============================================================
# OperationTimer
# ============================================================


class TestOperationTimer:
    def test_operation_timer(self):
        """OperationTimer records duration > 0 for a timed block."""
        timer = OperationTimer("test_op")
        with timer:
            # Small busy wait to ensure measurable duration
            total = sum(range(1000))
            _ = total  # prevent unused warning
        assert timer.duration_ms > 0.0
        assert timer.operation == "test_op"

    def test_operation_timer_minimal(self):
        """OperationTimer records extremely small durations."""
        timer = OperationTimer("noop")
        with timer:
            pass
        assert timer.duration_ms >= 0.0


# ============================================================
# MemoryMetrics
# ============================================================


class TestRecordSearch:
    def test_record_search(self):
        """Record search latencies and verify p95 in summary."""
        m = MemoryMetrics()
        for i in range(20):
            m.record_search(float(i * 5))

        s = m.summary
        assert s["total_searches"] == 20
        assert s["search_p95_ms"] > 0.0

    def test_record_search_single(self):
        """Single search record reflects in p95."""
        m = MemoryMetrics()
        m.record_search(42.0)
        assert m.summary["search_p95_ms"] == 42.0
        assert m.summary["total_searches"] == 1


class TestRecordSave:
    def test_record_save(self):
        """Record save latencies and verify p95 in summary."""
        m = MemoryMetrics()
        for i in range(10):
            m.record_save(float(i * 10))

        s = m.summary
        assert s["total_saves"] == 10
        assert s["save_p95_ms"] > 0.0


class TestRecordCurate:
    def test_record_curate(self):
        """Record curate durations and verify avg in summary."""
        m = MemoryMetrics()
        m.record_curate(2.0)
        m.record_curate(4.0)
        m.record_curate(6.0)

        s = m.summary
        assert s["total_curations"] == 3
        assert s["curator_avg_duration_s"] == pytest.approx(4.0)


class TestGrowthRate:
    def test_growth_rate(self):
        """Two count records compute daily growth rate."""
        m = MemoryMetrics()

        # Manually inject count history with known timestamps
        t1 = datetime(2026, 1, 1, 0, 0, 0)
        t2 = datetime(2026, 1, 3, 0, 0, 0)  # 2 days later
        m.memory_count_history.append((t1, 100))
        m.memory_count_history.append((t2, 120))

        rate = m._compute_growth_rate()
        assert rate == pytest.approx(10.0)  # 20 items / 2 days

    def test_growth_rate_insufficient_data(self):
        """Single data point returns 0.0 growth rate."""
        m = MemoryMetrics()
        m.record_count(50)
        assert m.summary["growth_rate_per_day"] == 0.0


class TestSummaryFormat:
    def test_summary_format(self):
        """Summary contains all 7 required fields."""
        m = MemoryMetrics()
        s = m.summary
        required = {
            "search_p95_ms",
            "save_p95_ms",
            "curator_avg_duration_s",
            "growth_rate_per_day",
            "total_searches",
            "total_saves",
            "total_curations",
        }
        assert set(s.keys()) == required


class TestP95Calculation:
    def test_p95_calculation(self):
        """Verify percentile calculation with 100 evenly spaced values."""
        data = list(range(100))  # 0..99
        p95 = _percentile(data, 0.95)
        # idx = int(100 * 0.95) = 95; sorted_data[95] = 95
        assert p95 == 95.0

    def test_p95_small_dataset(self):
        """Percentile with a small dataset clamps correctly."""
        data = [10.0, 20.0, 30.0]
        p95 = _percentile(data, 0.95)
        # idx = int(3 * 0.95) = 2; sorted_data[2] = 30.0
        assert p95 == 30.0

    def test_percentile_empty(self):
        """Percentile of empty data returns 0.0."""
        assert _percentile([], 0.95) == 0.0


class TestEmptyMetrics:
    def test_empty_metrics(self):
        """Fresh MemoryMetrics returns all zeros in summary."""
        m = MemoryMetrics()
        s = m.summary
        assert s["search_p95_ms"] == 0.0
        assert s["save_p95_ms"] == 0.0
        assert s["curator_avg_duration_s"] == 0.0
        assert s["growth_rate_per_day"] == 0.0
        assert s["total_searches"] == 0
        assert s["total_saves"] == 0
        assert s["total_curations"] == 0


class TestHealthOperationsDimension:
    def test_health_operations_dimension(self):
        """MemoryHealthScore includes operations in overall."""
        score = MemoryHealthScore(
            freshness=1.0,
            efficiency=1.0,
            coverage=1.0,
            diversity=1.0,
            coherence=1.0,
            operations=1.0,
        )
        # All 1.0 → overall = 1.0
        assert score.overall == pytest.approx(1.0)

    def test_health_operations_affects_overall(self):
        """Operations dimension changes the overall score."""
        with_ops = MemoryHealthScore(operations=1.0)
        without_ops = MemoryHealthScore(operations=0.0)
        # operations weight is 0.20
        assert with_ops.overall - without_ops.overall == pytest.approx(0.20)

    def test_compute_operations_score_fast(self):
        """Search p95 < 100ms → score 1.0."""
        assert compute_operations_score({"search_p95_ms": 50.0}) == 1.0

    def test_compute_operations_score_medium(self):
        """Search p95 < 200ms → score 0.7."""
        assert compute_operations_score({"search_p95_ms": 150.0}) == 0.7

    def test_compute_operations_score_slow(self):
        """Search p95 >= 200ms → score 0.3."""
        assert compute_operations_score({"search_p95_ms": 300.0}) == 0.3

    def test_compute_operations_score_no_data(self):
        """No search data (p95=0) → score 1.0 (benefit of doubt)."""
        assert compute_operations_score({"search_p95_ms": 0.0}) == 1.0

    def test_compute_health_with_metrics(self):
        """compute_health with metrics_summary includes operations dimension."""
        items = [_make_item()]
        metrics = {"search_p95_ms": 50.0}
        health = compute_health(items, [], DEFAULT_ROOMS, metrics_summary=metrics)
        assert health.operations == 1.0

    def test_compute_health_without_metrics(self):
        """compute_health without metrics_summary defaults operations to 0.0."""
        items = [_make_item()]
        health = compute_health(items, [], DEFAULT_ROOMS)
        assert health.operations == 0.0


class TestMetricsRollingWindow:
    def test_metrics_rolling_window(self):
        """Deque drops oldest entries beyond 100."""
        m = MemoryMetrics()
        for i in range(150):
            m.record_search(float(i))

        assert len(m.search_latencies) == 100
        # Oldest kept should be 50 (0..49 dropped)
        assert m.search_latencies[0] == 50.0
        # But total counter tracks all 150
        assert m.summary["total_searches"] == 150

    def test_save_rolling_window(self):
        """Save latencies also respect maxlen=100."""
        m = MemoryMetrics()
        for i in range(120):
            m.record_save(float(i))

        assert len(m.save_latencies) == 100
        assert m.summary["total_saves"] == 120

    def test_curate_rolling_window(self):
        """Curator durations also respect maxlen=100."""
        m = MemoryMetrics()
        for i in range(110):
            m.record_curate(float(i))

        assert len(m.curator_durations) == 100
        assert m.summary["total_curations"] == 110
