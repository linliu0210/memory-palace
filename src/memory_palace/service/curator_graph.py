"""CuratorGraph — Pure Python State Machine for Curator orchestration.

Implements the SPEC_V02 §2.4 CuratorGraph flow as a lightweight
state machine (no LangGraph — rejected due to 13 transitive dependencies).

Flow:
  START → gather_signal → has_items? ─No→ health_check → report → END
                              │Yes
                        extract_facts
                              │
                        reconcile (per fact)
                              │
                        reflect (importance_sum > threshold)
                              │
                        prune (decay check)
                              │
                        health_check (5-dimension)
                              │
                        report → END

Ref: SPEC_V02 §2.4, §9.1 (langgraph mitigation)
"""

from __future__ import annotations

import time
from datetime import datetime
from enum import StrEnum, auto
from typing import TYPE_CHECKING

import structlog

from memory_palace.engine.health import MemoryHealthScore, compute_health
from memory_palace.engine.reflection import ReflectionEngine, should_reflect
from memory_palace.models.curator import CuratorReport
from memory_palace.models.memory import MemoryItem, MemoryStatus

if TYPE_CHECKING:
    from memory_palace.config import RoomConfig
    from memory_palace.engine.fact_extractor import FactExtractor
    from memory_palace.engine.reconcile import ReconcileEngine
    from memory_palace.foundation.llm import LLMProvider
    from memory_palace.service.memory_service import MemoryService
    from memory_palace.store.core_store import CoreStore
    from memory_palace.store.recall_store import RecallStore

logger = structlog.get_logger(__name__)


# ── State machine phases ───────────────────────────────────


class CuratorPhase(StrEnum):
    """Phases of the Curator state machine."""

    GATHER = auto()
    EXTRACT = auto()
    RECONCILE = auto()
    REFLECT = auto()
    PRUNE = auto()
    HEALTH_CHECK = auto()
    REPORT = auto()
    DONE = auto()


# ── Curator State (mutable dict-like) ──────────────────────


class CuratorState:
    """Mutable state container for the Curator pipeline.

    Corresponds to SPEC_V02 §2.4 CuratorState TypedDict,
    implemented as a plain class for pure-Python operation.
    """

    def __init__(self) -> None:
        self.items: list[MemoryItem] = []
        self.facts: list[MemoryItem] = []
        self.decisions: list[dict] = []
        self.reflections: list[MemoryItem] = []
        self.pruned_ids: list[str] = []
        self.health: MemoryHealthScore | None = None
        self.errors: list[str] = []
        self.report: CuratorReport | None = None

        # Metrics
        self.facts_extracted: int = 0
        self.memories_created: int = 0
        self.memories_updated: int = 0
        self.memories_pruned: int = 0
        self.reflections_generated: int = 0


# ── CuratorGraph (State Machine) ───────────────────────────


class CuratorGraph:
    """Pure Python state machine implementing the Curator pipeline.

    Each step is an async method that mutates ``CuratorState``
    and returns the next phase. No external dependencies beyond
    the Memory Palace engine/store layer.

    Args:
        memory_service: MemoryService for CRUD operations.
        recall_store: RecallStore for gathering recent items.
        core_store: CoreStore for Core tier access.
        fact_extractor: FactExtractor for LLM fact parsing.
        reconcile_engine: ReconcileEngine for dedup/merge decisions.
        llm: LLM provider for ReflectionEngine.
        rooms_config: Room definitions for health coverage calculation.
    """

    def __init__(
        self,
        memory_service: MemoryService,
        recall_store: RecallStore,
        core_store: CoreStore,
        fact_extractor: FactExtractor,
        reconcile_engine: ReconcileEngine,
        llm: LLMProvider,
        rooms_config: list[RoomConfig] | None = None,
    ) -> None:
        self._ms = memory_service
        self._recall_store = recall_store
        self._core_store = core_store
        self._fact_extractor = fact_extractor
        self._reconcile_engine = reconcile_engine
        self._reflection_engine = ReflectionEngine(llm)
        self._rooms_config = rooms_config or []

    async def run(self, since: datetime | None = None) -> CuratorReport:
        """Execute the full Curator pipeline.

        Args:
            since: Optional cutoff datetime. If None, uses last 20 items.

        Returns:
            CuratorReport with all metrics populated.
        """
        start_time = time.time()
        state = CuratorState()
        phase = CuratorPhase.GATHER

        while phase != CuratorPhase.DONE:
            try:
                if phase == CuratorPhase.GATHER:
                    phase = await self._gather(state)
                elif phase == CuratorPhase.EXTRACT:
                    phase = await self._extract(state)
                elif phase == CuratorPhase.RECONCILE:
                    phase = await self._reconcile(state)
                elif phase == CuratorPhase.REFLECT:
                    phase = await self._reflect(state)
                elif phase == CuratorPhase.PRUNE:
                    phase = await self._prune(state)
                elif phase == CuratorPhase.HEALTH_CHECK:
                    phase = self._health_check(state)
                elif phase == CuratorPhase.REPORT:
                    phase = self._report(state, start_time)
            except Exception as exc:
                state.errors.append(f"{phase}: {exc}")
                logger.warning("curator_phase_error", phase=phase, error=str(exc))
                # Prevent infinite loop: if REPORT or HEALTH_CHECK fails,
                # build a fallback report and exit immediately.
                if phase in (CuratorPhase.REPORT, CuratorPhase.HEALTH_CHECK):
                    state.report = CuratorReport(
                        triggered_at=datetime.now(),
                        trigger_reason="manual",
                        facts_extracted=state.facts_extracted,
                        memories_created=state.memories_created,
                        memories_updated=state.memories_updated,
                        memories_pruned=state.memories_pruned,
                        reflections_generated=state.reflections_generated,
                        duration_seconds=time.time() - start_time,
                        errors=state.errors,
                    )
                    phase = CuratorPhase.DONE
                else:
                    # For earlier phases, skip forward to health_check
                    phase = CuratorPhase.HEALTH_CHECK

        assert state.report is not None
        return state.report

    # ── Phase implementations ──────────────────────────────

    async def _gather(self, state: CuratorState) -> CuratorPhase:
        """Gather recent items from RecallStore."""
        state.items = self._recall_store.get_recent(20)
        if not state.items:
            return CuratorPhase.HEALTH_CHECK  # skip to health if nothing to curate
        return CuratorPhase.EXTRACT

    async def _extract(self, state: CuratorState) -> CuratorPhase:
        """Extract atomic facts from gathered items."""
        combined_text = "\n".join(item.content for item in state.items)
        try:
            facts = await self._fact_extractor.extract(combined_text)
            state.facts = facts
            state.facts_extracted = len(facts)
        except Exception as exc:
            state.errors.append(f"FactExtractor error: {exc}")
        return CuratorPhase.RECONCILE

    async def _reconcile(self, state: CuratorState) -> CuratorPhase:
        """Reconcile each extracted fact with existing memories."""
        existing_items = self._recall_store.get_recent(50)

        for fact in state.facts:
            try:
                decision = await self._reconcile_engine.reconcile(
                    fact.content, existing_items
                )
            except (ValueError, Exception) as exc:
                state.errors.append(f"Reconcile error for '{fact.content[:50]}': {exc}")
                continue

            action = decision["action"]
            target_id = decision.get("target_id")
            reason = decision.get("reason", "curator decision")

            try:
                if action == "ADD":
                    self._ms.save(
                        content=fact.content,
                        importance=fact.importance,
                        tags=fact.tags,
                    )
                    state.memories_created += 1
                elif action == "UPDATE" and target_id:
                    self._ms.update(target_id, fact.content, reason)
                    state.memories_updated += 1
                elif action == "DELETE" and target_id:
                    self._ms.forget(target_id, reason)
                    state.memories_pruned += 1
                # NOOP — do nothing
            except Exception as exc:
                state.errors.append(f"Execute error ({action}): {exc}")
                logger.warning(
                    "Curator execute failed",
                    action=action,
                    target_id=target_id,
                    error=str(exc),
                )

        return CuratorPhase.REFLECT

    async def _reflect(self, state: CuratorState) -> CuratorPhase:
        """Generate reflections if importance threshold met."""
        if should_reflect(state.items):
            try:
                reflections = await self._reflection_engine.reflect(state.items)
                for r in reflections:
                    self._ms.save(
                        content=r.content,
                        importance=r.importance,
                        memory_type=r.memory_type,
                    )
                state.reflections = reflections
                state.reflections_generated = len(reflections)
            except Exception as exc:
                state.errors.append(f"Reflection error: {exc}")
        return CuratorPhase.PRUNE

    async def _prune(self, state: CuratorState) -> CuratorPhase:
        """Prune low-importance decayed memories.

        Items with importance < 0.05 and status ACTIVE are candidates.
        """
        candidates = self._recall_store.get_recent(100)
        for item in candidates:
            if item.importance < 0.05 and item.status == MemoryStatus.ACTIVE:
                self._recall_store.update_status(item.id, MemoryStatus.PRUNED)
                state.pruned_ids.append(item.id)
                state.memories_pruned += 1
        return CuratorPhase.HEALTH_CHECK

    def _health_check(self, state: CuratorState) -> CuratorPhase:
        """Compute 5-dimension health score."""
        # Gather all core items
        core_items: list[MemoryItem] = []
        for block in self._core_store.list_blocks():
            core_items.extend(self._core_store.load(block))

        recall_items = self._recall_store.get_recent(200)

        state.health = compute_health(core_items, recall_items, self._rooms_config)
        return CuratorPhase.REPORT

    def _report(self, state: CuratorState, start_time: float) -> CuratorPhase:
        """Build the final CuratorReport."""
        state.report = CuratorReport(
            triggered_at=datetime.now(),
            trigger_reason="manual",
            facts_extracted=state.facts_extracted,
            memories_created=state.memories_created,
            memories_updated=state.memories_updated,
            memories_pruned=state.memories_pruned,
            reflections_generated=state.reflections_generated,
            duration_seconds=time.time() - start_time,
            errors=state.errors,
            health=state.health,
            health_freshness=state.health.freshness if state.health else 0.0,
            health_efficiency=state.health.efficiency if state.health else 0.0,
        )
        return CuratorPhase.DONE
