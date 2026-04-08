"""CuratorService — 搬运小人 (Memory Curator Agent).

Orchestrates: Gather → Extract → Reconcile → Execute → Report.
v0.1: synchronous trigger, manually invoked.

Ref: SPEC v2.0 §4.1 S-15, §4.3, §4.4
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import structlog

from memory_palace.engine.fact_extractor import FactExtractor
from memory_palace.engine.reconcile import ReconcileEngine
from memory_palace.foundation.audit_log import AuditAction, AuditEntry, AuditLog
from memory_palace.foundation.llm import LLMProvider
from memory_palace.models.curator import CuratorReport
from memory_palace.store.recall_store import RecallStore

logger = structlog.get_logger(__name__)

# Default trigger thresholds (SPEC §6.2 / §8.2)
DEFAULT_SESSION_THRESHOLD = 20
DEFAULT_TIMER_HOURS = 24
DEFAULT_COOLDOWN_HOURS = 1


class CuratorService:
    """Memory Curator: automated memory maintenance agent.

    Gathers recent items, extracts facts, reconciles with existing
    memories, executes decisions (ADD/UPDATE/DELETE/NOOP), and
    generates a CuratorReport.

    Args:
        data_dir: Root data directory.
        llm: LLM provider for fact extraction and reconciliation.
    """

    def __init__(self, data_dir: Path, llm: LLMProvider) -> None:
        self._data_dir = data_dir
        self._recall_store = RecallStore(data_dir)
        self._audit_log = AuditLog(data_dir)
        self._fact_extractor = FactExtractor(llm)
        self._reconcile_engine = ReconcileEngine(llm)
        self._llm = llm

        # Track run history for trigger logic
        self._last_run_at: datetime | None = None
        self._session_count: int = 0

        # Lazy import to avoid circular dependency
        self._memory_service: object | None = None

    def _get_memory_service(self) -> object:
        """Lazy-init MemoryService to avoid circular import."""
        if self._memory_service is None:
            from memory_palace.service.memory_service import MemoryService

            self._memory_service = MemoryService(self._data_dir, self._llm)
        return self._memory_service

    async def run(self, since: datetime | None = None) -> CuratorReport:
        """Execute one curation cycle.

        Workflow:
        1. Gather: get recent items from RecallStore.
        2. Extract: run FactExtractor on recent item contents.
        3. Reconcile: for each new fact, run ReconcileEngine.
        4. Execute: apply decisions (ADD/UPDATE/DELETE/NOOP).
        5. Report: return CuratorReport with metrics.

        Args:
            since: Optional cutoff datetime. If None, uses last 20 items.

        Returns:
            CuratorReport with all metrics populated.
        """
        start_time = time.time()
        ms = self._get_memory_service()

        report = CuratorReport(
            triggered_at=datetime.now(),
            trigger_reason="manual",
        )

        errors: list[str] = []

        # 1. Gather — get recent items
        recent_items = self._recall_store.get_recent(20)
        if not recent_items:
            report.duration_seconds = time.time() - start_time
            self._last_run_at = datetime.now()
            return report

        # 2. Extract — combine content and extract facts
        combined_text = "\n".join(item.content for item in recent_items)
        try:
            new_facts = await self._fact_extractor.extract(combined_text)
        except Exception as exc:
            errors.append(f"FactExtractor error: {exc}")
            report.errors = errors
            report.duration_seconds = time.time() - start_time
            self._last_run_at = datetime.now()
            return report

        report.facts_extracted = len(new_facts)

        # Get existing items for reconciliation
        existing_items = self._recall_store.get_recent(50)

        # 3. Reconcile + 4. Execute — process each fact
        for fact in new_facts:
            try:
                decision = await self._reconcile_engine.reconcile(fact.content, existing_items)
            except (ValueError, Exception) as exc:
                errors.append(f"Reconcile error for '{fact.content[:50]}': {exc}")
                continue

            action = decision["action"]
            target_id = decision.get("target_id")
            reason = decision.get("reason", "curator decision")

            if action == "ADD":
                ms.save(
                    content=fact.content,
                    importance=fact.importance,
                    tags=fact.tags,
                )
                report.memories_created += 1

                self._audit_log.append(
                    AuditEntry(
                        action=AuditAction.CREATE,
                        memory_id=fact.id,
                        actor="curator",
                        details={"reason": reason, "source": "curator_run"},
                    )
                )

            elif action == "UPDATE" and target_id:
                ms.update(target_id, fact.content, reason)
                report.memories_updated += 1

            elif action == "DELETE" and target_id:
                ms.forget(target_id, reason)
                report.memories_pruned += 1

            # NOOP — do nothing

        report.errors = errors
        report.duration_seconds = time.time() - start_time
        self._last_run_at = datetime.now()
        self._session_count = 0  # Reset after run

        logger.info(
            "Curator run complete",
            facts_extracted=report.facts_extracted,
            created=report.memories_created,
            updated=report.memories_updated,
            pruned=report.memories_pruned,
            duration_s=report.duration_seconds,
        )

        return report

    def should_trigger(self) -> tuple[bool, str]:
        """Check whether curation should be triggered.

        Conditions (any one triggers):
        - session_count >= threshold (default 20)
        - hours since last run >= timer_hours (default 24)

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

        # Timer trigger
        if self._last_run_at is not None:
            hours_since_last = (now - self._last_run_at).total_seconds() / 3600
            if hours_since_last >= DEFAULT_TIMER_HOURS:
                return (True, "timer")
        else:
            # Never run before — timer trigger (more than 24h since start)
            return (True, "timer")

        return (False, "")
