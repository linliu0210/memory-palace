"""Custom exception types — Models layer.

Ref: CONVENTIONS_V10 §7
"""

from __future__ import annotations


class CuratorSafetyError(Exception):
    """Raised when HeartbeatController detects a safety limit breach.

    Attributes:
        reason: One of "max_steps_exceeded", "max_llm_calls_exceeded",
                "max_duration_exceeded".
        stats: Snapshot of HeartbeatController counters at time of breach.
    """

    def __init__(self, reason: str, stats: dict) -> None:
        self.reason = reason
        self.stats = stats
        super().__init__(f"Curator safety limit: {reason} (stats={stats})")
