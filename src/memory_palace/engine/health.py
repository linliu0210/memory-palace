"""MemoryHealthScore — 6-dimension health assessment.

Pure-function computation of system health across:
freshness, efficiency, coverage, diversity, coherence, operations.

Ref: SPEC_V02 §2.3 (F-15), TASK_R23
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from pydantic import BaseModel

from memory_palace.config import RoomConfig
from memory_palace.models.memory import MemoryItem, MemoryStatus


class MemoryHealthScore(BaseModel):
    """Six-dimension health assessment. Ref: SPEC §2.3, R23."""

    freshness: float = 0.0  # [0,1] — fraction of memories accessed in last 30 days
    efficiency: float = 0.0  # [0,1] — Core active/total ratio
    coverage: float = 0.0  # [0,1] — fraction of configured rooms with items
    diversity: float = 0.0  # [0,1] — MemoryType distribution evenness (Shannon)
    coherence: float = 0.0  # [0,1] — currently 1.0 placeholder (needs dedup engine)
    operations: float = 0.0  # [0,1] — operational metrics health (R23)

    @property
    def overall(self) -> float:
        """Weighted average of all six dimensions.

        Weights: freshness=0.20, efficiency=0.20, coverage=0.15,
                 diversity=0.10, coherence=0.15, operations=0.20.
        """
        return (
            self.freshness * 0.20
            + self.efficiency * 0.20
            + self.coverage * 0.15
            + self.diversity * 0.10
            + self.coherence * 0.15
            + self.operations * 0.20
        )


def compute_health(
    core_items: list[MemoryItem],
    recall_items: list[MemoryItem],
    rooms_config: list[RoomConfig],
    metrics_summary: dict | None = None,
) -> MemoryHealthScore:
    """Compute 6-dimension health score from memory collections.

    This is a pure function — no side effects or I/O.

    Args:
        core_items: Items in the Core tier.
        recall_items: Items in the Recall tier.
        rooms_config: Configured room definitions.
        metrics_summary: Optional metrics summary dict from MemoryMetrics.
            When provided, the ``operations`` dimension is computed.

    Returns:
        MemoryHealthScore with all six dimensions computed.
    """
    all_items = core_items + recall_items

    ops_score = compute_operations_score(metrics_summary) if metrics_summary else 0.0

    return MemoryHealthScore(
        freshness=_compute_freshness(all_items),
        efficiency=_compute_efficiency(core_items),
        coverage=_compute_coverage(all_items, rooms_config),
        diversity=_compute_diversity(all_items),
        coherence=_compute_coherence(all_items),
        operations=ops_score,
    )


def compute_operations_score(metrics_summary: dict) -> float:
    """Compute operations health from metrics summary.

    Scoring based on search P95 latency:
    - < 100ms → 1.0 (excellent)
    - < 200ms → 0.7 (acceptable)
    - >= 200ms → 0.3 (degraded)

    Returns 1.0 if no search data recorded (benefit of the doubt).
    """
    p95 = metrics_summary.get("search_p95_ms", 0.0)
    if p95 == 0.0:
        return 1.0  # no data yet — assume healthy
    if p95 < 100.0:
        return 1.0
    if p95 < 200.0:
        return 0.7
    return 0.3


# ── Dimension Computations ──────────────────────────────────


def _compute_freshness(items: list[MemoryItem], window_days: int = 30) -> float:
    """Fraction of items accessed within the last `window_days`.

    Returns 0.0 if no items exist.
    """
    if not items:
        return 0.0

    cutoff = datetime.now() - timedelta(days=window_days)
    fresh_count = sum(1 for item in items if item.accessed_at >= cutoff)
    return fresh_count / len(items)


def _compute_efficiency(core_items: list[MemoryItem]) -> float:
    """Ratio of ACTIVE items in Core tier.

    A high ratio means Core is well-curated (no stale/pruned clutter).
    Returns 0.0 if no core items exist.
    """
    if not core_items:
        return 0.0

    active_count = sum(1 for item in core_items if item.status == MemoryStatus.ACTIVE)
    return active_count / len(core_items)


def _compute_coverage(
    items: list[MemoryItem],
    rooms_config: list[RoomConfig],
) -> float:
    """Fraction of configured rooms that have at least one item.

    Returns 0.0 if no rooms are configured.
    """
    if not rooms_config:
        return 0.0
    if not items:
        return 0.0

    configured_rooms = {r.name for r in rooms_config}
    occupied_rooms = {item.room for item in items} & configured_rooms
    return len(occupied_rooms) / len(configured_rooms)


def _compute_diversity(items: list[MemoryItem]) -> float:
    """Normalized Shannon entropy of MemoryType distribution.

    Returns a value in [0, 1] where:
    - 1.0 = perfectly uniform distribution across all observed types
    - 0.0 = all items are the same type (or no items)

    Uses normalized entropy: H / log(n_types) where n_types is the
    number of distinct types observed.
    """
    if not items:
        return 0.0

    # Count occurrences of each type
    type_counts: dict[str, int] = {}
    for item in items:
        t = item.memory_type.value
        type_counts[t] = type_counts.get(t, 0) + 1

    n_types = len(type_counts)
    if n_types <= 1:
        return 0.0  # single type = no diversity

    total = len(items)
    # Shannon entropy
    entropy = -sum(
        (count / total) * math.log(count / total) for count in type_counts.values()
    )
    max_entropy = math.log(n_types)

    return entropy / max_entropy if max_entropy > 0 else 0.0


def _compute_coherence(items: list[MemoryItem]) -> float:
    """Coherence score based on content uniqueness.

    Detects near-duplicate memories by comparing normalized content.
    Returns 1.0 (fully coherent / no duplicates) when all items are unique,
    lower values when duplicates or near-duplicates are present.

    Score = 1.0 - (duplicate_count / total_count)
    """
    if not items:
        return 0.0
    if len(items) == 1:
        return 1.0

    # Normalize content for comparison: lowercase, strip whitespace
    seen: set[str] = set()
    duplicate_count = 0
    for item in items:
        normalized = item.content.strip().lower()
        # Use first 200 chars as fingerprint (handles near-dupes with minor edits)
        fingerprint = normalized[:200]
        if fingerprint in seen:
            duplicate_count += 1
        else:
            seen.add(fingerprint)

    return 1.0 - (duplicate_count / len(items))
