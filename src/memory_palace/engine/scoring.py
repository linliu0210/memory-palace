"""ScoringEngine — Three-factor pure-function scoring module.

Zero LLM dependency. Implements recency × importance × relevance scoring
from Generative Agents (Park et al., 2023).

Ref: SPEC v2.0 §4.1 S-11, §4.6
"""

import math
from typing import Any


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


def combined_score(
    recency: float,
    importance: float,
    relevance: float,
    weights: tuple[float, float, float] = (0.25, 0.25, 0.50),
) -> float:
    """Weighted sum: α·recency + β·importance + γ·relevance.

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


def rank(
    items: list[Any],
    recency_hours: list[float],
    importances: list[float],
    relevances: list[float],
    weights: tuple[float, float, float] = (0.25, 0.25, 0.50),
    decay_rate: float = 0.01,
) -> list[Any]:
    """Sort items by combined score, descending (highest first).

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
