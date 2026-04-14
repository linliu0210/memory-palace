"""SleepTimeScheduler — asyncio background scheduler for Curator.

Runs CuratorService in the background using asyncio.Event + wait(timeout)
to support both periodic and event-driven triggering. Zero new dependencies.

Ref: SPEC_V10 R14, CONVENTIONS_V10 §6
"""

from __future__ import annotations

import asyncio
import time as _time
from datetime import datetime
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from memory_palace.models.curator import CuratorReport
    from memory_palace.service.curator import CuratorService

logger = structlog.get_logger(__name__)


class SleepTimeScheduler:
    """Asyncio-based background scheduler for CuratorService.

    Uses asyncio.Event + wait(timeout=check_interval) to unify
    periodic checks and event-driven wakeups in a single loop.

    Args:
        curator_service: The CuratorService instance to trigger.
        check_interval: Seconds between periodic checks (default 300 = 5 min).
        min_interval: Minimum seconds between curator runs (cooldown).
            Prevents event-driven notify() from triggering too-frequent
            curations. Default 0 = no cooldown.
    """

    def __init__(
        self,
        curator_service: CuratorService,
        check_interval: int | float = 300,
        min_interval: int | float = 0,
    ) -> None:
        self._curator = curator_service
        self._check_interval = check_interval
        self._min_interval = min_interval

        self._running = False
        self._task: asyncio.Task | None = None
        self._event = asyncio.Event()
        self._curator_active = False  # Guard: prevent concurrent runs

        # Stats
        self._trigger_count: int = 0
        self._last_trigger_reason: str = ""
        self._last_run_report: CuratorReport | None = None
        self._started_at: datetime | None = None
        self._last_run_at: float = 0.0  # monotonic timestamp

    async def start(self) -> None:
        """Start the background scheduler task.

        Idempotent: calling start() when already running is a no-op.
        """
        if self._running:
            logger.debug("Scheduler already running, ignoring start()")
            return

        self._running = True
        self._started_at = datetime.now()
        self._event.clear()
        self._task = asyncio.create_task(self._loop())
        logger.info("Scheduler started", check_interval=self._check_interval)

    async def stop(self) -> None:
        """Gracefully stop the scheduler.

        Sets _running=False, wakes the event loop, and awaits task completion.
        Idempotent: calling stop() when not running is a no-op.
        """
        if not self._running:
            return

        self._running = False
        self._event.set()  # Wake up the wait() so the loop can exit

        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=30.0)
            except TimeoutError:
                logger.warning("Scheduler task did not complete in 30s, cancelling")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            self._task = None

        logger.info("Scheduler stopped", trigger_count=self._trigger_count)

    def notify(self, event: str) -> None:
        """External notification (e.g., after save()).

        Wakes the scheduler loop for an immediate should_trigger() check.

        Args:
            event: Description of the triggering event (for logging).
        """
        logger.debug("Scheduler notified", event_name=event)
        self._event.set()

    @property
    def is_running(self) -> bool:
        """Whether the scheduler loop is active."""
        return self._running

    @property
    def last_run_report(self) -> CuratorReport | None:
        """The CuratorReport from the most recent run, or None."""
        return self._last_run_report

    @property
    def stats(self) -> dict:
        """Runtime statistics.

        Returns:
            Dict with trigger_count, last_trigger_reason, is_running,
            curator_active, started_at.
        """
        return {
            "trigger_count": self._trigger_count,
            "last_trigger_reason": self._last_trigger_reason,
            "is_running": self._running,
            "curator_active": self._curator_active,
            "started_at": self._started_at.isoformat() if self._started_at else None,
        }

    async def _loop(self) -> None:
        """Main scheduler loop.

        Each iteration:
        1. Wait for check_interval OR an event notification (whichever first).
        2. Check should_trigger().
        3. If triggered and curator is not already running, execute run().
        """
        while self._running:
            # Wait for timeout or event notification
            try:
                await asyncio.wait_for(
                    self._event.wait(),
                    timeout=self._check_interval,
                )
            except TimeoutError:
                pass  # Timer expired — proceed to check

            # Clear event for next iteration
            self._event.clear()

            # Exit check: stop() may have set _running=False
            if not self._running:
                break

            # Guard: skip if curator is currently running
            if self._curator_active:
                logger.debug("Curator still active, skipping check")
                continue

            # Check trigger conditions
            should, reason = self._curator.should_trigger()
            if not should or not self._cooldown_elapsed():
                continue

            # Run curator
            self._curator_active = True
            try:
                logger.info("Scheduler triggering curator", reason=reason)
                report = await self._curator.run()
                self._last_run_report = report
                self._trigger_count += 1
                self._last_trigger_reason = reason
                self._last_run_at = _time.monotonic()
                logger.info(
                    "Scheduler curator run complete",
                    trigger_count=self._trigger_count,
                    facts=report.facts_extracted,
                )
            except Exception:
                logger.exception("Curator run failed in scheduler")
            finally:
                self._curator_active = False

    def _cooldown_elapsed(self) -> bool:
        """Check if enough time has passed since the last curator run."""
        if self._min_interval <= 0:
            return True
        return (_time.monotonic() - self._last_run_at) >= self._min_interval
