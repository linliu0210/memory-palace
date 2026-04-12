"""MemoryHealthScore — 5-dimension health assessment.

Pure-function computation of system health across:
freshness, efficiency, coverage, diversity, coherence.

Ref: SPEC_V02 §2.3 (F-15)
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from pydantic import BaseModel

from memory_palace.config import RoomConfig
from memory_palace.models.memory import MemoryItem, MemoryStatus


class MemoryHealthScore(BaseModel):
    """Five-dimension health assessment. Ref: SPEC §2.3."""

    freshness: float = 0.0  # [0,1] — fraction of memories accessed in last 30 days
    efficiency: float = 0.0  # [0,1] — Core active/total ratio
    coverage: float = 0.0  # [0,1] — fraction of configured rooms with items
    diversity: float = 0.0  # [0,1] — MemoryType distribution evenness (Shannon)
    coherence: float = 0.0  # [0,1] — currently 1.0 placeholder (needs dedup engine)

    @property
    def overall(self) -> float:
        """Weighted average of all dimensions.

        Weights: freshness=0.25, efficiency=0.25, coverage=0.15,
                 diversity=0.15, coherence=0.20.
        """
        return (
            self.freshness * 0.25
            + self.efficiency * 0.25
            + self.coverage * 0.15
            + self.diversity * 0.15
            + self.coherence * 0.20
        )


def compute_health(
    core_items: list[MemoryItem],
    recall_items: list[MemoryItem],
    rooms_config: list[RoomConfig],
) -> MemoryHealthScore:
    """Compute 5-dimension health score from memory collections.

    This is a pure function — no side effects or I/O.

    Args:
        core_items: Items in the Core tier.
        recall_items: Items in the Recall tier.
        rooms_config: Configured room definitions.

    Returns:
        MemoryHealthScore with all five dimensions computed.
    """
    all_items = core_items + recall_items

    return MemoryHealthScore(
        freshness=_compute_freshness(all_items),
        efficiency=_compute_efficiency(core_items),
        coverage=_compute_coverage(all_items, rooms_config),
        diversity=_compute_diversity(all_items),
        coherence=_compute_coherence(all_items),
    )


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
    """Coherence score — placeholder for future dedup/contradiction detection.

    Currently returns 1.0 (fully coherent) when items exist, 0.0 when empty.
    Will be enhanced in v0.3 with semantic deduplication.
    """
    if not items:
        return 0.0
    return 1.0  # TODO: implement semantic dedup/contradiction detection
