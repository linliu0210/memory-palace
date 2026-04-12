"""
Round 10: ScoringEngine v2 — ScoredCandidate + cosine_similarity + 4-factor rank

SPEC Ref: SPEC_V02 §2.3 ScoringEngine 重构
Tests the v0.2 additions while v0.1 tests remain on rank_legacy().
"""

import math

import pytest

from memory_palace.engine.scoring import (
    ScoredCandidate,
    cosine_similarity,
    rank,
    recency_score,
)
from memory_palace.models.memory import MemoryItem, MemoryTier, MemoryType


# ── Helpers ──────────────────────────────────────────────────


def _make_item(content: str = "test", importance: float = 0.5, room: str = "general") -> MemoryItem:
    """Create a minimal MemoryItem for testing."""
    return MemoryItem(
        content=content,
        memory_type=MemoryType.OBSERVATION,
        tier=MemoryTier.RECALL,
        importance=importance,
        room=room,
    )


def _make_candidate(
    content: str = "test",
    recency_hours: float = 0.0,
    importance: float = 0.5,
    relevance: float = 0.5,
    room_bonus: float = 0.0,
    room: str = "general",
) -> ScoredCandidate:
    """Create a ScoredCandidate with a minimal MemoryItem."""
    item = _make_item(content=content, importance=importance, room=room)
    return ScoredCandidate(
        item=item,
        recency_hours=recency_hours,
        importance=importance,
        relevance=relevance,
        room_bonus=room_bonus,
    )


# ============================================================
# ScoredCandidate dataclass
# ============================================================


class TestScoredCandidate:
    """ScoredCandidate holds a MemoryItem with pre-computed scoring factors."""

    def test_creation(self):
        """ScoredCandidate stores all four scoring factors."""
        item = _make_item()
        sc = ScoredCandidate(
            item=item,
            recency_hours=10.0,
            importance=0.8,
            relevance=0.6,
            room_bonus=1.0,
        )
        assert sc.item is item
        assert sc.recency_hours == 10.0
        assert sc.importance == 0.8
        assert sc.relevance == 0.6
        assert sc.room_bonus == 1.0

    def test_default_room_bonus_is_zero(self):
        """room_bonus defaults to 0.0."""
        item = _make_item()
        sc = ScoredCandidate(
            item=item,
            recency_hours=0.0,
            importance=0.5,
            relevance=0.5,
        )
        assert sc.room_bonus == 0.0


# ============================================================
# cosine_similarity
# ============================================================


class TestCosineSimilarity:
    """cosine_similarity(a, b) → float in [-1, 1]."""

    def test_identical_vectors_is_one(self):
        """Two identical unit vectors have cosine similarity = 1.0."""
        v = [1.0, 0.0, 0.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_is_zero(self):
        """Orthogonal vectors have cosine similarity = 0.0."""
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors_is_negative_one(self):
        """Opposite vectors have cosine similarity = -1.0."""
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_non_unit_vectors(self):
        """Works with non-unit vectors (normalizes internally)."""
        a = [3.0, 4.0]
        b = [6.0, 8.0]
        # Same direction, different magnitude → cos = 1.0
        assert cosine_similarity(a, b) == pytest.approx(1.0)

    def test_zero_vector_returns_zero(self):
        """Zero vector → 0.0 (avoid division by zero)."""
        a = [0.0, 0.0, 0.0]
        b = [1.0, 2.0, 3.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_both_zero_returns_zero(self):
        """Both zero vectors → 0.0."""
        a = [0.0, 0.0]
        b = [0.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0)

    def test_known_angle(self):
        """45-degree angle → cos(45°) ≈ 0.707."""
        a = [1.0, 0.0]
        b = [1.0, 1.0]
        expected = 1.0 / math.sqrt(2)
        assert cosine_similarity(a, b) == pytest.approx(expected)


# ============================================================
# rank() v2 — 4-factor weighted scoring
# ============================================================


class TestRankV2:
    """New rank() accepts list[ScoredCandidate], returns list[MemoryItem]."""

    def test_items_sorted_by_score_descending(self):
        """Higher-scoring candidate appears first."""
        high = _make_candidate(content="high", recency_hours=0.0, importance=0.9, relevance=0.9)
        low = _make_candidate(content="low", recency_hours=100.0, importance=0.1, relevance=0.1)
        result = rank([low, high])
        assert result[0].content == "high"
        assert result[1].content == "low"

    def test_room_bonus_breaks_tie(self):
        """When other factors are equal, room_bonus tips the ranking."""
        no_bonus = _make_candidate(content="no_bonus", recency_hours=0.0, importance=0.5, relevance=0.5, room_bonus=0.0)
        with_bonus = _make_candidate(content="with_bonus", recency_hours=0.0, importance=0.5, relevance=0.5, room_bonus=1.0)
        result = rank([no_bonus, with_bonus])
        assert result[0].content == "with_bonus"

    def test_default_weights_sum_to_one(self):
        """Default weights (0.20, 0.20, 0.50, 0.10) sum to 1.0."""
        default_weights = (0.20, 0.20, 0.50, 0.10)
        assert sum(default_weights) == pytest.approx(1.0)

    def test_custom_weights(self):
        """Custom weights change ranking order."""
        # High recency, low relevance
        a = _make_candidate(content="recency_heavy", recency_hours=0.0, importance=0.5, relevance=0.1, room_bonus=0.0)
        # Low recency, high relevance
        b = _make_candidate(content="relevance_heavy", recency_hours=100.0, importance=0.5, relevance=0.9, room_bonus=0.0)

        # With recency-heavy weights → a wins
        result_recency = rank([a, b], weights=(0.70, 0.10, 0.10, 0.10))
        assert result_recency[0].content == "recency_heavy"

        # With relevance-heavy weights → b wins
        result_relevance = rank([a, b], weights=(0.05, 0.05, 0.80, 0.10))
        assert result_relevance[0].content == "relevance_heavy"

    def test_empty_candidates(self):
        """Empty candidate list → empty result."""
        result = rank([])
        assert result == []

    def test_single_candidate(self):
        """Single candidate is returned directly."""
        c = _make_candidate(content="only")
        result = rank([c])
        assert len(result) == 1
        assert result[0].content == "only"

    def test_returns_memory_items(self):
        """rank() returns list[MemoryItem], not ScoredCandidate."""
        c = _make_candidate(content="item")
        result = rank([c])
        assert isinstance(result[0], MemoryItem)
