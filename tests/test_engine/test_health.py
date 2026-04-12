"""
Round 11: MemoryHealthScore — 5-dimension health assessment.

SPEC Ref: SPEC_V02 §2.3 (F-15), MemoryHealthScore
Tests: comprehensive, skewed, empty, overall weighted average.
"""

from datetime import datetime, timedelta

import pytest

from memory_palace.config import RoomConfig
from memory_palace.engine.health import MemoryHealthScore, compute_health
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
# MemoryHealthScore dataclass
# ============================================================


class TestMemoryHealthScore:
    """MemoryHealthScore holds five dimensions + overall property."""

    def test_all_dimensions_default_zero(self):
        """All dimensions default to 0.0."""
        score = MemoryHealthScore()
        assert score.freshness == 0.0
        assert score.efficiency == 0.0
        assert score.coverage == 0.0
        assert score.diversity == 0.0
        assert score.coherence == 0.0

    def test_overall_weighted_average(self):
        """overall = 0.25·freshness + 0.25·efficiency + 0.15·coverage + 0.15·diversity + 0.20·coherence."""
        score = MemoryHealthScore(
            freshness=1.0,
            efficiency=0.8,
            coverage=0.6,
            diversity=0.4,
            coherence=0.5,
        )
        expected = 1.0 * 0.25 + 0.8 * 0.25 + 0.6 * 0.15 + 0.4 * 0.15 + 0.5 * 0.20
        assert score.overall == pytest.approx(expected)

    def test_perfect_score_is_one(self):
        """All dimensions = 1.0 → overall = 1.0."""
        score = MemoryHealthScore(
            freshness=1.0,
            efficiency=1.0,
            coverage=1.0,
            diversity=1.0,
            coherence=1.0,
        )
        assert score.overall == pytest.approx(1.0)

    def test_zero_score_is_zero(self):
        """All dimensions = 0.0 → overall = 0.0."""
        score = MemoryHealthScore()
        assert score.overall == pytest.approx(0.0)


# ============================================================
# compute_health()
# ============================================================


class TestComputeHealth:
    """compute_health() computes 5-dimension scores from memory collections."""

    def test_comprehensive_healthy_system(self):
        """A well-maintained system scores high across all dimensions."""
        now = datetime.now()
        core_items = [
            _make_item(room="general", status=MemoryStatus.ACTIVE, tier=MemoryTier.CORE, accessed_at=now - timedelta(days=1)),
            _make_item(room="preferences", status=MemoryStatus.ACTIVE, tier=MemoryTier.CORE, accessed_at=now - timedelta(days=5)),
        ]
        recall_items = [
            _make_item(room="projects", memory_type=MemoryType.PREFERENCE, accessed_at=now - timedelta(days=2)),
            _make_item(room="people", memory_type=MemoryType.PROCEDURE, accessed_at=now - timedelta(days=10)),
            _make_item(room="skills", memory_type=MemoryType.DECISION, accessed_at=now - timedelta(days=15)),
        ]

        result = compute_health(core_items, recall_items, DEFAULT_ROOMS)

        assert isinstance(result, MemoryHealthScore)
        # Freshness: all accessed within 30 days → ≈ 1.0
        assert result.freshness >= 0.8
        # Efficiency: all core items are active → 1.0
        assert result.efficiency == pytest.approx(1.0)
        # Coverage: 5 rooms covered → 1.0
        assert result.coverage == pytest.approx(1.0)
        # Diversity: multiple types → > 0.5
        assert result.diversity > 0.5
        # Overall should be reasonably high
        assert result.overall > 0.5

    def test_skewed_system_low_diversity(self):
        """All items same type → low diversity."""
        now = datetime.now()
        items = [
            _make_item(room="general", memory_type=MemoryType.OBSERVATION, accessed_at=now),
            _make_item(room="preferences", memory_type=MemoryType.OBSERVATION, accessed_at=now),
            _make_item(room="projects", memory_type=MemoryType.OBSERVATION, accessed_at=now),
        ]

        result = compute_health([], items, DEFAULT_ROOMS)

        # Diversity: all same type → low
        assert result.diversity < 0.5

    def test_empty_system_scores_zero(self):
        """No items → health is minimal."""
        result = compute_health([], [], DEFAULT_ROOMS)

        assert result.freshness == 0.0
        assert result.efficiency == 0.0
        assert result.coverage == 0.0
        assert result.diversity == 0.0

    def test_stale_system_low_freshness(self):
        """All items accessed > 30 days ago → low freshness."""
        old = datetime.now() - timedelta(days=60)
        items = [
            _make_item(accessed_at=old),
            _make_item(accessed_at=old),
        ]

        result = compute_health([], items, DEFAULT_ROOMS)

        assert result.freshness == pytest.approx(0.0)

    def test_inefficient_core_with_pruned(self):
        """Core with many non-active items → low efficiency."""
        core_items = [
            _make_item(status=MemoryStatus.ACTIVE, tier=MemoryTier.CORE),
            _make_item(status=MemoryStatus.SUPERSEDED, tier=MemoryTier.CORE),
            _make_item(status=MemoryStatus.PRUNED, tier=MemoryTier.CORE),
            _make_item(status=MemoryStatus.PRUNED, tier=MemoryTier.CORE),
        ]

        result = compute_health(core_items, [], DEFAULT_ROOMS)

        # 1 active / 4 total = 0.25
        assert result.efficiency == pytest.approx(0.25)
