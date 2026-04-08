"""
Round 4: Engine — ScoringEngine Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §4.6

ScoringEngine is a pure-function module (ZERO LLM dependency).
v0.1 uses 3 factors: Recency × Importance × Relevance.
"""

import pytest

from memory_palace.engine.scoring import (
    combined_score,
    importance_score,
    normalize_bm25,
    rank,
    recency_score,
)


class TestRecencyScore:
    """recency = exp(-λ · hours_since_last_access), λ=0.01."""

    def test_just_accessed_is_near_one(self):
        """Memory accessed 0 hours ago → recency ≈ 1.0."""
        result = recency_score(0.0)
        assert result == pytest.approx(1.0)

    def test_decays_exponentially(self):
        """Memory accessed 100 hours ago → recency < memory at 10 hours."""
        score_10h = recency_score(10.0)
        score_100h = recency_score(100.0)
        assert score_100h < score_10h

    def test_very_old_approaches_zero(self):
        """Memory accessed 1000 hours ago → recency near 0."""
        result = recency_score(1000.0)
        assert result < 0.01


class TestImportanceScore:
    """importance = memory.importance (passthrough [0,1])."""

    def test_passthrough(self):
        """importance(0.8) → 0.8."""
        assert importance_score(0.8) == 0.8


class TestRelevanceScore:
    """relevance = normalize_bm25(fts5_rank)."""

    def test_normalized_range(self):
        """Result must be in [0, 1]."""
        ranks = [-10.0, -5.0, -1.0]
        for r in ranks:
            result = normalize_bm25(r, ranks)
            assert 0.0 <= result <= 1.0

    def test_most_relevant_is_one(self):
        """The best-matching result gets relevance = 1.0."""
        ranks = [-10.0, -5.0, -1.0]
        # Most negative = most relevant in FTS5
        result = normalize_bm25(-10.0, ranks)
        assert result == pytest.approx(1.0)

    def test_single_result_is_one(self):
        """Only one result → relevance = 1.0."""
        result = normalize_bm25(-5.0, [-5.0])
        assert result == pytest.approx(1.0)

    def test_empty_results_is_zero(self):
        """No results → relevance = 0.0."""
        result = normalize_bm25(-5.0, [])
        assert result == pytest.approx(0.0)


class TestCombinedScore:
    """Combined score = α·R + β·I + γ·Rel."""

    def test_weights_sum_to_one(self):
        """Default weights α+β+γ = 1.0."""
        default_weights = (0.25, 0.25, 0.50)
        assert sum(default_weights) == pytest.approx(1.0)

    def test_respects_weight_config(self):
        """Custom weights should change the ranking."""
        # Same factors, different weights → different scores
        factors = (0.8, 0.3, 0.6)
        score_a = combined_score(*factors, weights=(0.7, 0.1, 0.2))
        score_b = combined_score(*factors, weights=(0.2, 0.1, 0.7))
        # recency=0.8 is high, so recency-heavy weights should yield higher score
        assert score_a > score_b

    def test_items_ranked_by_score_descending(self):
        """rank() returns items sorted highest-score first."""
        items = ["low", "high", "mid"]
        recency_hours = [100.0, 0.0, 50.0]
        importances = [0.1, 0.9, 0.5]
        relevances = [0.1, 0.9, 0.5]
        result = rank(items, recency_hours, importances, relevances)
        assert result[0] == "high"
        assert result[-1] == "low"
