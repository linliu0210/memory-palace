"""MemoryMetrics — Operational metrics collection for Memory Palace.

Collects search/save latencies, curator durations, and memory growth rate.
Uses a module-level singleton for shared access across service and integration layers.

Ref: TASK_R23
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime
from typing import Any


class OperationTimer:
    """Context manager that records operation latency in milliseconds.

    Usage::

        timer = OperationTimer("save")
        with timer:
            do_something()
        print(timer.duration_ms)
    """

    def __init__(self, operation: str) -> None:
        self.operation = operation
        self.duration_ms: float = 0.0
        self._start: float = 0.0

    def __enter__(self) -> OperationTimer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args: Any) -> None:
        elapsed = time.perf_counter() - self._start
        self.duration_ms = elapsed * 1000.0


class MemoryMetrics:
    """Operational metrics collection.

    Collects rolling-window latencies (last 100 entries) and cumulative counters.

    Attributes:
        search_latencies: Recent search operation durations (ms).
        save_latencies: Recent save operation durations (ms).
        curator_durations: Recent curator cycle durations (seconds).
        memory_count_history: Recent (timestamp, count) snapshots.
    """

    def __init__(self) -> None:
        self.search_latencies: deque[float] = deque(maxlen=100)
        self.save_latencies: deque[float] = deque(maxlen=100)
        self.curator_durations: deque[float] = deque(maxlen=100)
        self.memory_count_history: deque[tuple[datetime, int]] = deque(maxlen=100)

        # Cumulative counters (not affected by rolling window)
        self._total_searches: int = 0
        self._total_saves: int = 0
        self._total_curations: int = 0

    def record_search(self, duration_ms: float) -> None:
        """Record a search operation latency."""
        self.search_latencies.append(duration_ms)
        self._total_searches += 1

    def record_save(self, duration_ms: float) -> None:
        """Record a save operation latency."""
        self.save_latencies.append(duration_ms)
        self._total_saves += 1

    def record_curate(self, duration_s: float) -> None:
        """Record a curator cycle duration."""
        self.curator_durations.append(duration_s)
        self._total_curations += 1

    def record_count(self, count: int) -> None:
        """Record a memory count snapshot for growth rate calculation."""
        self.memory_count_history.append((datetime.now(), count))

    @property
    def summary(self) -> dict:
        """Return metrics summary dict.

        Keys:
            search_p95_ms: 95th percentile of search latencies.
            save_p95_ms: 95th percentile of save latencies.
            curator_avg_duration_s: Average curator cycle duration.
            growth_rate_per_day: Estimated daily memory growth rate.
            total_searches: Cumulative search count.
            total_saves: Cumulative save count.
            total_curations: Cumulative curation count.
        """
        return {
            "search_p95_ms": _percentile(list(self.search_latencies), 0.95),
            "save_p95_ms": _percentile(list(self.save_latencies), 0.95),
            "curator_avg_duration_s": _mean(list(self.curator_durations)),
            "growth_rate_per_day": self._compute_growth_rate(),
            "total_searches": self._total_searches,
            "total_saves": self._total_saves,
            "total_curations": self._total_curations,
        }

    def _compute_growth_rate(self) -> float:
        """Compute daily growth rate from count history.

        Uses first and last entries in count history.
        Returns 0.0 if fewer than 2 data points.
        """
        if len(self.memory_count_history) < 2:
            return 0.0

        first_time, first_count = self.memory_count_history[0]
        last_time, last_count = self.memory_count_history[-1]

        elapsed_days = (last_time - first_time).total_seconds() / 86400.0
        if elapsed_days <= 0:
            return 0.0

        return (last_count - first_count) / elapsed_days


def _percentile(data: list[float], pct: float) -> float:
    """Compute the given percentile of a sorted dataset.

    Returns 0.0 for empty data.
    """
    if not data:
        return 0.0

    sorted_data = sorted(data)
    idx = int(len(sorted_data) * pct)
    # Clamp to valid range
    idx = min(idx, len(sorted_data) - 1)
    return sorted_data[idx]


def _mean(data: list[float]) -> float:
    """Compute mean of a dataset. Returns 0.0 for empty data."""
    if not data:
        return 0.0
    return sum(data) / len(data)


# ── Module-level singleton ──────────────────────────────────

_global_metrics: MemoryMetrics | None = None


def get_metrics() -> MemoryMetrics:
    """Get the shared MemoryMetrics singleton."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MemoryMetrics()
    return _global_metrics
