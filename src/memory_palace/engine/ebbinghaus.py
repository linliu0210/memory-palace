"""Ebbinghaus forgetting curve engine — pure functions, zero I/O.

Mathematical model for memory retention and decay:

    R(t) = exp(-t / S)                    — retention rate
    S = S₀ × (1 + ln(1 + n))             — stability (n = access count)
    effective_importance = importance × R  — weighted importance
    prune when effective_importance < θ   — eviction decision

All functions are pure: no side-effects, no I/O, no LLM.

Ref: TASK_R15 §1
"""

from __future__ import annotations

import math


def retention(hours_since_access: float, stability: float) -> float:
    """Compute retention rate via Ebbinghaus forgetting curve.

    R(t) = exp(-t / S). Returns value in [0, 1].

    Args:
        hours_since_access: Hours since last access (clamped to ≥ 0).
        stability: Memory stability S in hours (higher = slower decay).

    Returns:
        Retention rate in [0, 1], where 1.0 = fully retained.
    """
    # Edge: non-finite → 0.0 (infinitely old = forgotten)
    if not math.isfinite(hours_since_access):
        return 0.0
    # Clamp negative hours to 0
    if hours_since_access < 0:
        hours_since_access = 0.0
    return math.exp(-hours_since_access / stability)


def stability(base_stability: float = 168.0, access_count: int = 0) -> float:
    """Compute memory stability with logarithmic access reinforcement.

    S = S₀ × (1 + ln(1 + n)). More accesses = slower forgetting.

    Args:
        base_stability: Base stability S₀ in hours. Default 168h (1 week).
        access_count: Number of times memory has been accessed (clamped to ≥ 0).

    Returns:
        Stability value in hours.
    """
    # Clamp negative access_count to 0
    if access_count < 0:
        access_count = 0
    return base_stability * (1 + math.log(1 + access_count))


def effective_importance(
    importance: float,
    hours_since_access: float,
    access_count: int = 0,
    base_stability: float = 168.0,
) -> float:
    """Compute decay-adjusted importance.

    effective = importance × R(t), where R uses stability(S₀, n).

    Args:
        importance: Raw importance score [0, 1].
        hours_since_access: Hours since last access.
        access_count: Number of accesses (reinforcement).
        base_stability: Base stability S₀ in hours.

    Returns:
        Effective importance after decay.
    """
    s = stability(base_stability, access_count)
    r = retention(hours_since_access, s)
    return importance * r


def should_prune(
    importance: float,
    hours_since_access: float,
    access_count: int = 0,
    threshold: float = 0.05,
    base_stability: float = 168.0,
) -> bool:
    """Decide whether a memory should be pruned.

    Prunes when effective_importance < threshold.

    Args:
        importance: Raw importance score [0, 1].
        hours_since_access: Hours since last access.
        access_count: Number of accesses (reinforcement).
        threshold: Pruning threshold (default 0.05).
        base_stability: Base stability S₀ in hours.

    Returns:
        True if the memory should be pruned.
    """
    ei = effective_importance(importance, hours_since_access, access_count, base_stability)
    return ei < threshold
