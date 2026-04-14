"""IngestPipeline — 5-pass document ingestion pipeline.

Transforms raw text into structured memories with relations.

Pass 1 — DIFF:    content hash → skip if already processed
Pass 2 — EXTRACT: FactExtractor → atomic facts
Pass 3 — MAP:     LLM assigns room + importance per fact
Pass 4 — LINK:    LLM discovers relations (requires GraphStore)
Pass 5 — UPDATE:  ReconcileEngine → ADD/UPDATE/NOOP/DELETE → write

Ref: TASK_R25
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from memory_palace.foundation.audit_log import AuditAction, AuditEntry
from memory_palace.models.ingest import IngestReport

if TYPE_CHECKING:
    from memory_palace.engine.fact_extractor import FactExtractor
    from memory_palace.engine.reconcile import ReconcileEngine
    from memory_palace.foundation.llm import LLMProvider
    from memory_palace.service.memory_service import MemoryService
    from memory_palace.store.graph_store import GraphStore

logger = structlog.get_logger(__name__)

# ── Prompt Templates ──────────────────────────────────────────

MAP_PROMPT = """You are a memory classification engine.
Given atomic facts, assign each fact to exactly ONE room and adjust importance.

Available rooms:
- general: Uncategorized general knowledge
- preferences: User preferences and settings
- projects: Project-related knowledge
- people: People and relationships
- skills: Skills and abilities

Facts:
{facts}

Return JSON array: [{{"index": 0, "room": "general", "importance": 0.5}}, ...]
Every fact must have an entry. Keep importance between 0.0 and 1.0."""

LINK_PROMPT = """You are a knowledge graph engine.
Given these facts, identify meaningful relations between them.

Facts:
{facts}

Return JSON array of relations (empty array [] if no relations found):
[{{"from": 0, "to": 1, "type": "semantic", "weight": 0.8}}, ...]

"from" and "to" are fact indices (0-based).
"type" is one of: semantic, temporal, causal, hierarchical.
"weight" is relation strength 0.0-1.0."""


def _content_hash(text: str) -> str:
    """SHA-256 hash of stripped text for dedup."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


class IngestPipeline:
    """5-pass document ingestion pipeline.

    Pass 1 — DIFF: Check if document was already processed (content hash)
    Pass 2 — EXTRACT: FactExtractor extracts atomic facts
    Pass 3 — MAP: Assign room + importance to each fact via LLM
    Pass 4 — LINK: Discover relations between facts (requires GraphStore)
    Pass 5 — UPDATE: ReconcileEngine compares with existing, then writes

    Args:
        memory_service: MemoryService for CRUD operations.
        fact_extractor: FactExtractor for atomic fact extraction.
        reconcile_engine: ReconcileEngine for conflict resolution.
        llm: LLMProvider for MAP and LINK passes.
        graph_store: Optional GraphStore for relation edges.
    """

    def __init__(
        self,
        memory_service: MemoryService,
        fact_extractor: FactExtractor,
        reconcile_engine: ReconcileEngine,
        llm: LLMProvider,
        graph_store: GraphStore | None = None,
    ) -> None:
        self._svc = memory_service
        self._extractor = fact_extractor
        self._reconcile = reconcile_engine
        self._llm = llm
        self._graph_store = graph_store

    # ── Public API ────────────────────────────────────────────

    async def ingest(self, text: str, source_id: str = "") -> IngestReport:
        """Run the full 5-pass pipeline on raw text.

        Args:
            text: Raw document text.
            source_id: Optional identifier for the source document.

        Returns:
            IngestReport with statistics from each pass.
        """
        start = time.monotonic()
        report = IngestReport(total_input_chars=len(text))
        errors: list[str] = []

        # Pass 1 — DIFF
        skipped = self._pass_diff(text, source_id, report)
        if skipped:
            report.duration_seconds = round(time.monotonic() - start, 3)
            report.errors = errors
            return report

        # Pass 2 — EXTRACT
        facts = await self._pass_extract(text, report, errors)
        if not facts:
            # Record ingest even with 0 facts (empty document)
            self._record_ingest(text, source_id)
            report.duration_seconds = round(time.monotonic() - start, 3)
            report.errors = errors
            return report

        # Pass 3 — MAP
        facts = await self._pass_map(facts, report, errors)

        # Pass 4 — LINK
        pending_relations = await self._pass_link(facts, report, errors)

        # Pass 5 — UPDATE
        saved_ids = await self._pass_update(facts, report, errors)

        # Write pending relations to GraphStore
        relations_created = 0
        if pending_relations and self._graph_store is not None:
            for rel in pending_relations:
                from_idx = rel["from"]
                to_idx = rel["to"]
                if from_idx < len(saved_ids) and to_idx < len(saved_ids):
                    from_id = saved_ids[from_idx]
                    to_id = saved_ids[to_idx]
                    if from_id and to_id:
                        try:
                            self._graph_store.add_relation(
                                from_id,
                                to_id,
                                rel.get("type", "semantic"),
                                rel.get("weight", 1.0),
                            )
                            relations_created += 1
                        except Exception as exc:
                            errors.append(f"add_relation failed: {exc}")

        report.relations_created = relations_created

        # Record successful ingest in AuditLog
        self._record_ingest(text, source_id)

        report.duration_seconds = round(time.monotonic() - start, 3)
        report.errors = errors
        return report

    async def ingest_file(self, path: Path) -> IngestReport:
        """Ingest a single file.

        Args:
            path: Path to the document file.

        Returns:
            IngestReport for this file.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        text = path.read_text(encoding="utf-8")
        return await self.ingest(text, source_id=path.name)

    async def ingest_batch(self, paths: list[Path]) -> IngestReport:
        """Ingest multiple files, merging results into a single report.

        Args:
            paths: List of file paths to ingest.

        Returns:
            Merged IngestReport across all files.
        """
        merged = IngestReport()
        start = time.monotonic()

        for path in paths:
            try:
                r = await self.ingest_file(path)
                merged.total_input_chars += r.total_input_chars
                merged.memories_created += r.memories_created
                merged.relations_created += r.relations_created
                merged.errors.extend(r.errors)
                # Merge pass_results (keep per-file stats under file key)
                merged.pass_results[str(path.name)] = r.pass_results
            except Exception as exc:
                merged.errors.append(f"{path.name}: {exc}")

        merged.duration_seconds = round(time.monotonic() - start, 3)
        return merged

    # ── Pass Implementations ──────────────────────────────────

    def _pass_diff(
        self, text: str, source_id: str, report: IngestReport,
    ) -> bool:
        """Pass 1 — DIFF: Check if document was already processed.

        Returns True if the document should be skipped.
        """
        h = _content_hash(text)
        audit_log = self._svc._audit_log

        # Scan audit log for previous INGEST with same hash
        entries = audit_log.read()
        for entry in entries:
            if (
                entry.action == AuditAction.INGEST
                and entry.details.get("source_hash") == h
            ):
                report.pass_results["diff"] = {"skipped": True, "hash": h}
                logger.info("ingest_diff_skip", source_id=source_id, hash=h[:12])
                return True

        report.pass_results["diff"] = {"skipped": False, "hash": h}
        return False

    async def _pass_extract(
        self,
        text: str,
        report: IngestReport,
        errors: list[str],
    ) -> list:
        """Pass 2 — EXTRACT: Extract atomic facts from text."""
        try:
            facts = await self._extractor.extract(text)
        except Exception as exc:
            errors.append(f"extract failed: {exc}")
            facts = []

        report.pass_results["extract"] = {"facts_count": len(facts)}
        return facts

    async def _pass_map(
        self,
        facts: list,
        report: IngestReport,
        errors: list[str],
    ) -> list:
        """Pass 3 — MAP: Assign room and importance to each fact via LLM."""
        facts_text = "\n".join(
            f"[{i}] {f.content}" for i, f in enumerate(facts)
        )
        prompt = MAP_PROMPT.format(facts=facts_text)

        try:
            raw = await self._llm.complete(prompt)
            mappings = json.loads(raw)
            if not isinstance(mappings, list):
                raise ValueError("MAP response is not a list")

            mapped_count = 0
            for m in mappings:
                idx = m.get("index")
                if idx is not None and 0 <= idx < len(facts):
                    update = {}
                    if "room" in m:
                        update["room"] = m["room"]
                    if "importance" in m:
                        imp = float(m["importance"])
                        if 0.0 <= imp <= 1.0:
                            update["importance"] = imp
                            # Re-tier based on updated importance
                            from memory_palace.models.memory import MemoryTier
                            update["tier"] = (
                                MemoryTier.CORE if imp >= 0.7 else MemoryTier.RECALL
                            )
                    if update:
                        facts[idx] = facts[idx].model_copy(update=update)
                        mapped_count += 1

            report.pass_results["map"] = {
                "mapped": mapped_count,
                "total": len(facts),
            }
        except Exception as exc:
            errors.append(f"map failed: {exc}")
            report.pass_results["map"] = {
                "mapped": 0,
                "total": len(facts),
                "error": str(exc),
            }

        return facts

    async def _pass_link(
        self,
        facts: list,
        report: IngestReport,
        errors: list[str],
    ) -> list[dict]:
        """Pass 4 — LINK: Discover relations between facts.

        Returns list of pending relation dicts (from/to are indices).
        """
        if self._graph_store is None:
            report.pass_results["link"] = {"skipped": True}
            return []

        facts_text = "\n".join(
            f"[{i}] {f.content}" for i, f in enumerate(facts)
        )
        prompt = LINK_PROMPT.format(facts=facts_text)

        try:
            raw = await self._llm.complete(prompt)
            relations = json.loads(raw)
            if not isinstance(relations, list):
                raise ValueError("LINK response is not a list")

            # Validate indices
            valid = []
            for rel in relations:
                f_idx = rel.get("from")
                t_idx = rel.get("to")
                if (
                    isinstance(f_idx, int)
                    and isinstance(t_idx, int)
                    and 0 <= f_idx < len(facts)
                    and 0 <= t_idx < len(facts)
                    and f_idx != t_idx
                ):
                    valid.append(rel)

            report.pass_results["link"] = {
                "skipped": False,
                "relations_found": len(valid),
            }
            return valid
        except Exception as exc:
            errors.append(f"link failed: {exc}")
            report.pass_results["link"] = {
                "skipped": False,
                "relations_found": 0,
                "error": str(exc),
            }
            return []

    async def _pass_update(
        self,
        facts: list,
        report: IngestReport,
        errors: list[str],
    ) -> list[str | None]:
        """Pass 5 — UPDATE: Reconcile each fact and write to storage.

        Returns list of saved memory IDs (None for skipped/failed facts).
        """
        created = 0
        updated = 0
        noop = 0
        deleted = 0
        saved_ids: list[str | None] = []

        for fact in facts:
            try:
                # Find existing memories to compare against
                existing = self._svc.search_sync(fact.content, top_k=5)

                # Reconcile
                try:
                    decision = await self._reconcile.reconcile(
                        fact.content, existing,
                    )
                except ValueError as exc:
                    # Fallback to ADD on reconcile failure
                    errors.append(f"reconcile fallback to ADD: {exc}")
                    decision = {
                        "action": "ADD",
                        "target_id": None,
                        "reason": "reconcile_fallback",
                    }

                action = decision["action"]

                if action == "ADD":
                    item = self._svc.save(
                        content=fact.content,
                        importance=fact.importance,
                        tags=fact.tags,
                        room=fact.room,
                        memory_type=fact.memory_type,
                    )
                    saved_ids.append(item.id)
                    created += 1

                elif action == "UPDATE":
                    target_id = decision["target_id"]
                    try:
                        new_item = self._svc.update(
                            target_id,
                            fact.content,
                            decision.get("reason", "ingest_update"),
                        )
                        saved_ids.append(new_item.id)
                        updated += 1
                    except ValueError as exc:
                        # Target not found — fallback to ADD
                        errors.append(f"update target not found, adding: {exc}")
                        item = self._svc.save(
                            content=fact.content,
                            importance=fact.importance,
                            tags=fact.tags,
                            room=fact.room,
                            memory_type=fact.memory_type,
                        )
                        saved_ids.append(item.id)
                        created += 1

                elif action == "DELETE":
                    target_id = decision["target_id"]
                    self._svc.forget(target_id, decision.get("reason", "ingest_delete"))
                    saved_ids.append(None)
                    deleted += 1

                elif action == "NOOP":
                    saved_ids.append(None)
                    noop += 1

                else:
                    errors.append(f"unknown action: {action}")
                    saved_ids.append(None)

            except Exception as exc:
                errors.append(f"update pass error: {exc}")
                saved_ids.append(None)

        report.memories_created = created
        report.pass_results["update"] = {
            "created": created,
            "updated": updated,
            "noop": noop,
            "deleted": deleted,
        }

        return saved_ids

    # ── Helpers ────────────────────────────────────────────────

    def _record_ingest(self, text: str, source_id: str) -> None:
        """Record a successful ingest in the AuditLog."""
        h = _content_hash(text)
        self._svc._audit_log.append(
            AuditEntry(
                action=AuditAction.INGEST,
                memory_id=source_id or h[:16],
                actor="system",
                details={"source_hash": h, "source_id": source_id},
            )
        )
