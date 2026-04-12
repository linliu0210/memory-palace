"""CuratorService — 搬运小人 (Memory Curator Agent).

v0.2: Delegates run() to CuratorGraph (pure Python state machine).
Preserves should_trigger() interface from v0.1.

Ref: SPEC v2.0 §4.1 S-15, §4.3, §4.4, SPEC_V02 §2.4
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from memory_palace.engine.fact_extractor import FactExtractor
from memory_palace.engine.reconcile import ReconcileEngine
from memory_palace.foundation.llm import LLMProvider
from memory_palace.models.curator import CuratorReport
from memory_palace.service.curator_graph import CuratorGraph
from memory_palace.store.core_store import CoreStore
from memory_palace.store.recall_store import RecallStore

if TYPE_CHECKING:
    from memory_palace.config import RoomConfig

logger = structlog.get_logger(__name__)

# Default trigger thresholds (SPEC §6.2 / §8.2)
DEFAULT_SESSION_THRESHOLD = 20
DEFAULT_TIMER_HOURS = 24
DEFAULT_COOLDOWN_HOURS = 1
DEFAULT_IMPORTANCE_SUM = 5.0


class CuratorService:
    """Memory Curator: automated memory maintenance agent.

    v0.2: run() delegates to CuratorGraph (pure Python state machine)
    for the full pipeline: Gather → Extract → Reconcile → Reflect →
    Prune → HealthCheck → Report.

    Args:
        data_dir: Root data directory.
        llm: LLM provider for fact extraction and reconciliation.
        rooms_config: Room definitions for health coverage calculation.
    """

    def __init__(
        self,
        data_dir: Path,
        llm: LLMProvider,
        rooms_config: list[RoomConfig] | None = None,
    ) -> None:
        self._data_dir = data_dir
        self._llm = llm
        self._rooms_config = rooms_config or []

        # Stores
        self._recall_store = RecallStore(data_dir)
        self._core_store = CoreStore(data_dir)

        # Engines
        self._fact_extractor = FactExtractor(llm)
        self._reconcile_engine = ReconcileEngine(llm)

        # Track run history for trigger logic
        self._last_run_at: datetime | None = None
        self._session_count: int = 0
        self._importance_sum: float = 0.0

        # Lazy init for MemoryService (circular dep avoidance)
        self._memory_service: object | None = None

    def _get_memory_service(self) -> object:
        """Lazy-init MemoryService to avoid circular import."""
        if self._memory_service is None:
            from memory_palace.service.memory_service import MemoryService

            self._memory_service = MemoryService(self._data_dir, self._llm)
        return self._memory_service

    async def run(self, since: datetime | None = None) -> CuratorReport:
        """Execute one curation cycle via CuratorGraph.

        v0.2: Delegates to CuratorGraph (pure Python state machine).

        Args:
            since: Optional cutoff datetime. If None, uses last 20 items.

        Returns:
            CuratorReport with all metrics populated.
        """
        ms = self._get_memory_service()

        graph = CuratorGraph(
            memory_service=ms,
            recall_store=self._recall_store,
            core_store=self._core_store,
            fact_extractor=self._fact_extractor,
            reconcile_engine=self._reconcile_engine,
            llm=self._llm,
            rooms_config=self._rooms_config,
        )

        report = await graph.run(since=since)

        self._last_run_at = datetime.now()
        self._session_count = 0  # Reset after run
        self._importance_sum = 0.0  # Reset importance accumulator

        logger.info(
            "Curator run complete",
            facts_extracted=report.facts_extracted,
            created=report.memories_created,
            updated=report.memories_updated,
            pruned=report.memories_pruned,
            reflections=report.reflections_generated,
            duration_s=report.duration_seconds,
        )

        return report

    def increment_session(self) -> None:
        """Increment session count for trigger tracking.

        Called by MemoryService after each save operation.
        """
        self._session_count += 1

    def record_importance(self, value: float) -> None:
        """Accumulate importance value for trigger tracking.

        Called by MemoryService after each save operation.

        Args:
            value: The importance score of the saved memory.
        """
        self._importance_sum += value

    def should_trigger(self) -> tuple[bool, str]:
        """Check whether curation should be triggered.

        Conditions (any one triggers):
        - session_count >= threshold (default 20)
        - hours since last run >= timer_hours (default 24)
        - importance_sum >= threshold (default 5.0)

        Cooldown: will NOT trigger if last run was < cooldown_hours ago.

        Returns:
            Tuple of (should_trigger: bool, reason: str).
        """
        now = datetime.now()

        # Cooldown check
        if self._last_run_at is not None:
            hours_since_last = (now - self._last_run_at).total_seconds() / 3600
            if hours_since_last < DEFAULT_COOLDOWN_HOURS:
                return (False, "")

        # Session count trigger
        if self._session_count >= DEFAULT_SESSION_THRESHOLD:
            return (True, "session_count")

        # Importance sum trigger
        if self._importance_sum >= DEFAULT_IMPORTANCE_SUM:
            return (True, "importance_sum")

        # Timer trigger
        if self._last_run_at is not None:
            hours_since_last = (now - self._last_run_at).total_seconds() / 3600
            if hours_since_last >= DEFAULT_TIMER_HOURS:
                return (True, "timer")
        else:
            # Never run before — trigger on first use to perform initial curation.
            # This is intentional: a fresh system should curate on first opportunity.
            return (True, "timer")

        return (False, "")
