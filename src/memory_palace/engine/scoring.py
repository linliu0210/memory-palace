"""ScoringEngine — Enhanced scoring with ScoredCandidate interface.

v0.2 enhancements:
- ScoredCandidate dataclass replaces parallel-array API (TD-3)
- cosine_similarity for vector relevance
- 4-factor weighted scoring: recency × importance × relevance × room_bonus
- rank_legacy() preserves v0.1 backward compatibility

Ref: SPEC_V02 §2.3, SPEC v2.0 §4.1 S-11, §4.6
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from memory_palace.engine.ebbinghaus import retention as _eb_retention
from memory_palace.engine.ebbinghaus import stability as _eb_stability

if TYPE_CHECKING:
    from memory_palace.models.memory import MemoryItem


# ── ScoredCandidate ─────────────────────────────────────────


@dataclass
class ScoredCandidate:
    """A memory item with pre-computed scoring factors.

    Replaces v0.1 parallel-array API for cleaner, less error-prone ranking.

    Attributes:
        item: The MemoryItem being scored.
        recency_hours: Hours since last access (≥ 0).
        importance: Importance factor [0, 1].
        relevance: Cosine similarity or normalized BM25 [0, 1].
        room_bonus: 1.0 if item's room matches query context, else 0.0.
    """

    item: MemoryItem
    recency_hours: float
    importance: float
    relevance: float
    room_bonus: float = 0.0
    access_count: int = 0


# ── Pure scoring functions ──────────────────────────────────


def recency_score(hours_since_access: float, decay_rate: float = 0.01) -> float:
    """Compute recency factor via exponential decay.

    ``recency = exp(-λ · Δt)`` where λ defaults to 0.01 (~69h half-life).

    Args:
        hours_since_access: Hours since last access (≥ 0).
        decay_rate: Decay constant λ in 1/hours.

    Returns:
        Score in (0, 1], where 1.0 = just accessed.
    """
    # Guard: reject non-finite values; clamp negative hours to zero
    if not math.isfinite(hours_since_access):
        return 0.0
    if hours_since_access < 0:
        hours_since_access = 0.0
    return math.exp(-decay_rate * hours_since_access)


def ebbinghaus_recency(
    hours_since_access: float,
    access_count: int = 0,
    base_stability: float = 168.0,
) -> float:
    """Compute recency factor via Ebbinghaus forgetting curve.

    Uses ``stability()`` and ``retention()`` from the Ebbinghaus engine.
    Drop-in alternative to ``recency_score()`` for more realistic decay.

    Args:
        hours_since_access: Hours since last access (≥ 0).
        access_count: Number of prior accesses (reinforcement).
        base_stability: Base stability S₀ in hours.

    Returns:
        Score in [0, 1], where 1.0 = just accessed.
    """
    s = _eb_stability(base_stability, access_count)
    return _eb_retention(hours_since_access, s)


def importance_score(importance: float) -> float:
    """Passthrough: importance already in [0, 1].

    Args:
        importance: Raw importance value.

    Returns:
        The same value, unchanged.
    """
    return importance


def normalize_bm25(raw_rank: float, all_ranks: list[float]) -> float:
    """Normalize FTS5 BM25 rank (negative, lower = more relevant) to [0, 1].

    Args:
        raw_rank: This result's BM25 rank.
        all_ranks: All BM25 ranks in the result set.

    Returns:
        Normalized relevance in [0, 1].
    """
    if not all_ranks:
        return 0.0
    min_r = min(all_ranks)
    max_r = max(all_ranks)
    if min_r == max_r:
        return 1.0
    return (max_r - raw_rank) / (max_r - min_r)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First vector.
        b: Second vector (same dimensionality as a).

    Returns:
        Cosine similarity in [-1, 1]. Returns 0.0 if either vector is zero.
    """
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def combined_score(
    recency: float,
    importance: float,
    relevance: float,
    weights: tuple[float, float, float] = (0.25, 0.25, 0.50),
) -> float:
    """Weighted sum: α·recency + β·importance + γ·relevance (v0.1 3-factor).

    Args:
        recency: Recency factor [0, 1].
        importance: Importance factor [0, 1].
        relevance: Relevance factor [0, 1].
        weights: (α, β, γ) — must sum to 1.0.

    Returns:
        Combined score.
    """
    alpha, beta, gamma = weights
    return alpha * recency + beta * importance + gamma * relevance


# ── v0.2 ranking (ScoredCandidate interface) ────────────────


def rank(
    candidates: list[ScoredCandidate],
    weights: tuple[float, float, float, float] = (0.20, 0.20, 0.50, 0.10),
    decay_rate: float = 0.01,
    decay_mode: Literal["exponential", "ebbinghaus"] = "exponential",
    base_stability: float = 168.0,
) -> list[MemoryItem]:
    """Sort candidates by 4-factor weighted score, descending.

    Score = α·recency + β·importance + γ·relevance + δ·room_bonus

    Args:
        candidates: ScoredCandidate instances to rank.
        weights: (α_recency, β_importance, γ_relevance, δ_room_bonus).
        decay_rate: Decay constant λ for recency (exponential mode).
        decay_mode: "exponential" (v0.2 default) or "ebbinghaus".
        base_stability: Base stability S₀ for Ebbinghaus mode.

    Returns:
        MemoryItems sorted by combined score, highest first.

    Ref: SPEC_V02 §2.3 ScoredCandidate 接口
    """
    if not candidates:
        return []

    alpha, beta, gamma, delta = weights
    scored = []
    for c in candidates:
        if decay_mode == "ebbinghaus":
            r = ebbinghaus_recency(c.recency_hours, c.access_count, base_stability)
        else:
            r = recency_score(c.recency_hours, decay_rate)
        score = alpha * r + beta * c.importance + gamma * c.relevance + delta * c.room_bonus
        scored.append((score, c.item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]


# ── v0.1 backward compatibility ─────────────────────────────


def rank_legacy(
    items: list[Any],
    recency_hours: list[float],
    importances: list[float],
    relevances: list[float],
    weights: tuple[float, float, float] = (0.25, 0.25, 0.50),
    decay_rate: float = 0.01,
) -> list[Any]:
    """Sort items by combined score, descending (highest first).

    v0.1 parallel-array API preserved for backward compatibility.

    Args:
        items: The items to rank.
        recency_hours: Hours since last access for each item.
        importances: Importance values for each item.
        relevances: Pre-normalized relevance values for each item.
        weights: Scoring weights (α, β, γ).
        decay_rate: Decay constant λ for recency.

    Returns:
        Items sorted by combined score, highest first.
    """
    scored = []
    for i, item in enumerate(items):
        r = recency_score(recency_hours[i], decay_rate)
        imp = importance_score(importances[i])
        rel = relevances[i]
        score = combined_score(r, imp, rel, weights)
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored]
