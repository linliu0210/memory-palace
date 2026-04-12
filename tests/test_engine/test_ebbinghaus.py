"""Tests for the Ebbinghaus forgetting curve engine.

Covers:
- retention() decay function
- stability() logarithmic growth
- effective_importance() combined scoring
- should_prune() threshold decision
- Edge cases: negative hours, infinite hours, negative access_count
- Integration with scoring.py ebbinghaus_recency()

Ref: TASK_R15 §5
"""

from __future__ import annotations

import math

import pytest

from memory_palace.engine.ebbinghaus import (
    effective_importance,
    retention,
    should_prune,
    stability,
)

# ── retention() ────────────────────────────────────────────


class TestRetention:
    """R(t) = exp(-t / S) behavior."""

    def test_retention_at_zero(self) -> None:
        """R(0) = 1.0 — freshly accessed memory is fully retained."""
        assert retention(0.0, stability=168.0) == 1.0

    def test_retention_decays_over_time(self) -> None:
        """R(168h) ≈ 1/e ≈ 0.368 when stability = 168."""
        r = retention(168.0, stability=168.0)
        assert r == pytest.approx(1 / math.e, rel=1e-6)

    def test_retention_approaches_zero(self) -> None:
        """R(very large t) → 0."""
        r = retention(10000.0, stability=168.0)
        assert r < 0.001

    def test_retention_bounded_zero_one(self) -> None:
        """Retention is always in [0, 1]."""
        for hours in [0, 1, 10, 100, 1000]:
            r = retention(float(hours), stability=168.0)
            assert 0.0 <= r <= 1.0


# ── stability() ────────────────────────────────────────────


class TestStability:
    """S = S₀ × (1 + ln(1 + n)) behavior."""

    def test_stability_base_case(self) -> None:
        """S(n=0) = S₀ = 168 (1 week)."""
        s = stability(base_stability=168.0, access_count=0)
        assert s == pytest.approx(168.0)

    def test_stability_increases_with_access(self) -> None:
        """S(n=5) > S(n=0) — more access = more stable."""
        s0 = stability(base_stability=168.0, access_count=0)
        s5 = stability(base_stability=168.0, access_count=5)
        assert s5 > s0

    def test_stability_log_growth(self) -> None:
        """Growth rate decreases: S(10)-S(5) < S(5)-S(0)."""
        s0 = stability(base_stability=168.0, access_count=0)
        s5 = stability(base_stability=168.0, access_count=5)
        s10 = stability(base_stability=168.0, access_count=10)
        assert (s10 - s5) < (s5 - s0)

    def test_stability_exact_value(self) -> None:
        """S(n=0) = 168 * (1 + ln(1)) = 168 * 1 = 168."""
        s = stability(base_stability=168.0, access_count=0)
        # ln(1+0) = ln(1) = 0, so S = 168 * (1 + 0) = 168
        assert s == pytest.approx(168.0)

    def test_stability_n1(self) -> None:
        """S(n=1) = 168 * (1 + ln(2)) ≈ 168 * 1.693."""
        s = stability(base_stability=168.0, access_count=1)
        expected = 168.0 * (1 + math.log(2))
        assert s == pytest.approx(expected)


# ── effective_importance() ─────────────────────────────────


class TestEffectiveImportance:
    """effective = importance × R(t)."""

    def test_effective_importance_fresh(self) -> None:
        """Just accessed → effective = importance."""
        ei = effective_importance(importance=0.8, hours_since_access=0.0)
        assert ei == pytest.approx(0.8)

    def test_effective_importance_decayed(self) -> None:
        """After one base_stability period, decayed to importance / e."""
        ei = effective_importance(
            importance=0.8,
            hours_since_access=168.0,
            access_count=0,
            base_stability=168.0,
        )
        assert ei == pytest.approx(0.8 / math.e, rel=1e-6)

    def test_effective_importance_high_access_protects(self) -> None:
        """High access_count increases stability, slowing decay."""
        ei_low = effective_importance(
            importance=0.5, hours_since_access=336.0, access_count=0
        )
        ei_high = effective_importance(
            importance=0.5, hours_since_access=336.0, access_count=10
        )
        assert ei_high > ei_low


# ── should_prune() ─────────────────────────────────────────


class TestShouldPrune:
    """Prune when effective_importance < threshold."""

    def test_should_prune_below_threshold(self) -> None:
        """Very old, low-importance → prune."""
        assert should_prune(importance=0.1, hours_since_access=2000.0) is True

    def test_should_prune_fresh_memory(self) -> None:
        """Just accessed → never prune."""
        assert should_prune(importance=0.5, hours_since_access=0.0) is False

    def test_should_not_prune_frequently_accessed(self) -> None:
        """High access_count protects from pruning even after long time."""
        result = should_prune(
            importance=0.5,
            hours_since_access=500.0,
            access_count=20,
            threshold=0.05,
        )
        assert result is False

    def test_should_prune_threshold_boundary(self) -> None:
        """At exactly the threshold boundary, favor pruning (strict <)."""
        # Find time where effective_importance ≈ threshold for importance=1.0
        # R(t) = exp(-t / 168) = 0.05 → t = -168 * ln(0.05) ≈ 503.6
        # At t slightly above, effective < 0.05
        result_above = should_prune(importance=1.0, hours_since_access=510.0)
        assert result_above is True

        result_below = should_prune(importance=1.0, hours_since_access=490.0)
        assert result_below is False


# ── Edge cases ─────────────────────────────────────────────


class TestEdgeCases:
    """Boundary and degenerate inputs."""

    def test_edge_negative_hours(self) -> None:
        """Negative hours clamped to 0 → R = 1.0."""
        r = retention(-10.0, stability=168.0)
        assert r == 1.0

    def test_edge_infinite_hours(self) -> None:
        """inf hours → retention = 0.0."""
        r = retention(float("inf"), stability=168.0)
        assert r == 0.0

    def test_edge_negative_access_count(self) -> None:
        """Negative access_count clamped to 0."""
        s = stability(base_stability=168.0, access_count=-5)
        s_zero = stability(base_stability=168.0, access_count=0)
        assert s == s_zero

    def test_effective_importance_negative_hours(self) -> None:
        """Negative hours → treated as 0 → full importance."""
        ei = effective_importance(importance=0.7, hours_since_access=-100.0)
        assert ei == pytest.approx(0.7)

    def test_should_prune_negative_access(self) -> None:
        """Negative access_count doesn't crash."""
        # Should work same as access_count=0
        result = should_prune(
            importance=0.1, hours_since_access=2000.0, access_count=-3
        )
        assert result is True


# ── Integration with scoring.py ────────────────────────────


class TestScoringIntegration:
    """Test ebbinghaus_recency() in scoring.py."""

    def test_ebbinghaus_recency_in_scoring(self) -> None:
        """ebbinghaus_recency returns same value as manual calculation."""
        from memory_palace.engine.scoring import ebbinghaus_recency

        result = ebbinghaus_recency(
            hours_since_access=168.0, access_count=0, base_stability=168.0
        )
        expected = retention(168.0, stability=stability(168.0, 0))
        assert result == pytest.approx(expected)

    def test_ebbinghaus_recency_fresh(self) -> None:
        """Fresh memory → recency = 1.0."""
        from memory_palace.engine.scoring import ebbinghaus_recency

        assert ebbinghaus_recency(0.0) == pytest.approx(1.0)

    def test_rank_with_ebbinghaus_mode(self) -> None:
        """rank() with decay_mode='ebbinghaus' uses Ebbinghaus curve."""
        from memory_palace.engine.scoring import ScoredCandidate, rank
        from memory_palace.models.memory import MemoryItem, MemoryTier, MemoryType

        items = [
            MemoryItem(
                content="old memory",
                memory_type=MemoryType.OBSERVATION,
                tier=MemoryTier.RECALL,
                importance=0.5,
            ),
            MemoryItem(
                content="frequently accessed",
                memory_type=MemoryType.OBSERVATION,
                tier=MemoryTier.RECALL,
                importance=0.5,
                access_count=10,
            ),
        ]

        candidates = [
            ScoredCandidate(
                item=items[0],
                recency_hours=500.0,
                importance=0.5,
                relevance=0.5,
                access_count=0,
            ),
            ScoredCandidate(
                item=items[1],
                recency_hours=500.0,
                importance=0.5,
                relevance=0.5,
                access_count=10,
            ),
        ]

        result = rank(candidates, decay_mode="ebbinghaus")
        # Frequently accessed should rank higher due to higher stability
        assert result[0].content == "frequently accessed"

    def test_rank_default_mode_unchanged(self) -> None:
        """rank() default mode is still 'exponential' — backward compatible."""
        from memory_palace.engine.scoring import ScoredCandidate, rank
        from memory_palace.models.memory import MemoryItem, MemoryTier, MemoryType

        item = MemoryItem(
            content="test",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.RECALL,
            importance=0.5,
        )

        candidates = [
            ScoredCandidate(
                item=item,
                recency_hours=10.0,
                importance=0.5,
                relevance=0.5,
            ),
        ]

        # Should work without specifying decay_mode (defaults to exponential)
        result = rank(candidates)
        assert len(result) == 1
        assert result[0].content == "test"
