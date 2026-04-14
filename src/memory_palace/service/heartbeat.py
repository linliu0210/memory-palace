"""HeartbeatController — Curator runtime safety guard.

Pure in-memory controller with three-layer protection:
1. MAX_STEPS: state machine transition limit
2. MAX_LLM_CALLS: LLM invocation limit per run
3. MAX_DURATION: wall-clock timeout
Plus dedup guard to skip already-processed memory_ids.

No I/O, no LLM — counting and time checks only.
Uses time.monotonic() for stable elapsed measurement.

Ref: CONVENTIONS_V10 §7 (CuratorSafetyError → REPORT)
"""

from __future__ import annotations

import time

from memory_palace.models.errors import CuratorSafetyError


class HeartbeatController:
    """Curator runtime safety guard.

    Three-layer protection:
    1. MAX_STEPS: state machine max transitions (default 50)
    2. MAX_LLM_CALLS: single-run LLM call ceiling (default 30)
    3. MAX_DURATION: single-run wall-clock seconds (default 120)
    + Dedup guard: same memory_id not processed twice in one run.

    Args:
        max_steps: Maximum state machine transitions per run.
        max_llm_calls: Maximum LLM calls per run.
        max_duration_seconds: Maximum wall-clock seconds per run.
    """

    def __init__(
        self,
        max_steps: int = 50,
        max_llm_calls: int = 30,
        max_duration_seconds: int = 120,
    ) -> None:
        self._max_steps = max_steps
        self._max_llm_calls = max_llm_calls
        self._max_duration_seconds = max_duration_seconds

        # Mutable counters — reset() before each run
        self._steps: int = 0
        self._llm_calls: int = 0
        self._start_time: float = time.monotonic()
        self._seen_ids: set[str] = set()
        self._dedup_skipped: int = 0

    # ── Public API ─────────────────────────────────────────

    def tick(self) -> None:
        """Record one state transition. Raises on step or duration breach."""
        self._steps += 1
        if self._steps > self._max_steps:
            raise CuratorSafetyError("max_steps_exceeded", self.stats)
        self._check_duration()

    def record_llm_call(self) -> None:
        """Record one LLM invocation. Raises on LLM-call or duration breach."""
        self._llm_calls += 1
        if self._llm_calls > self._max_llm_calls:
            raise CuratorSafetyError("max_llm_calls_exceeded", self.stats)
        self._check_duration()

    def check_dedup(self, memory_id: str) -> bool:
        """Check whether *memory_id* was already processed in this run.

        Returns:
            True if already seen (caller should skip), False if first time.
        """
        if memory_id in self._seen_ids:
            self._dedup_skipped += 1
            return True
        self._seen_ids.add(memory_id)
        return False

    def reset(self) -> None:
        """Reset all counters for a fresh Curator run."""
        self._steps = 0
        self._llm_calls = 0
        self._start_time = time.monotonic()
        self._seen_ids.clear()
        self._dedup_skipped = 0

    @property
    def stats(self) -> dict:
        """Current counter snapshot.

        Returns:
            Dict with keys: steps, llm_calls, elapsed_seconds, dedup_skipped.
        """
        return {
            "steps": self._steps,
            "llm_calls": self._llm_calls,
            "elapsed_seconds": round(time.monotonic() - self._start_time, 3),
            "dedup_skipped": self._dedup_skipped,
        }

    # ── Internal ───────────────────────────────────────────

    def _check_duration(self) -> None:
        """Raise if elapsed time exceeds max_duration_seconds."""
        elapsed = time.monotonic() - self._start_time
        if elapsed > self._max_duration_seconds:
            raise CuratorSafetyError("max_duration_exceeded", self.stats)
