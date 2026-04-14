"""v1.0 Final E2E Tests — Full lifecycle, persona isolation, batch roundtrip.

Validates all v1.0 components work together end-to-end.
All LLM/embedding calls are mocked.

Ref: TASK_R25 §5
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from memory_palace.config import Config
from memory_palace.engine.ebbinghaus import effective_importance, should_prune
from memory_palace.engine.fact_extractor import FactExtractor
from memory_palace.engine.health import compute_health
from memory_palace.engine.reconcile import ReconcileEngine
from memory_palace.service.batch_io import BatchExporter, BatchImporter
from memory_palace.service.ingest_pipeline import IngestPipeline
from memory_palace.service.memory_service import MemoryService
from tests.conftest import MockLLM

# ── Helpers ───────────────────────────────────────────────────


def _build_ingest_pipeline(
    data_dir: Path,
    llm: MockLLM,
) -> tuple[IngestPipeline, MemoryService]:
    """Build pipeline + service with shared MockLLM."""
    svc = MemoryService(data_dir, llm=llm)
    extractor = FactExtractor(llm)
    reconciler = ReconcileEngine(llm)
    pipeline = IngestPipeline(
        memory_service=svc,
        fact_extractor=extractor,
        reconcile_engine=reconciler,
        llm=llm,
    )
    return pipeline, svc


# ── Test 1: Full v1.0 Lifecycle ──────────────────────────────


class TestV10FullLifecycle:
    """End-to-end: ingest → search → curate → ebbinghaus → health + metrics."""

    @pytest.mark.asyncio
    async def test_v10_full_lifecycle(self, tmp_data_dir):
        """
        1. ingest document → memories created
        2. search → memories retrievable
        3. curate → curator runs successfully
        4. ebbinghaus decay → pure function verification
        5. health + metrics → scores computed
        """
        # === Step 1: Ingest a document ===
        ingest_llm = MockLLM(responses=[
            # EXTRACT: 2 facts
            json.dumps([
                {"content": "Memory Palace使用三层存储架构", "importance": 0.6, "tags": ["arch"]},
                {"content": "用户偏好Python开发", "importance": 0.7, "tags": ["preferences"]},
            ]),
            # MAP
            json.dumps([
                {"index": 0, "room": "projects", "importance": 0.6},
                {"index": 1, "room": "preferences", "importance": 0.7},
            ]),
            # RECONCILE fact 0 → ADD
            '{"action": "ADD", "target_id": null, "reason": "new info"}',
            # RECONCILE fact 1 → ADD
            '{"action": "ADD", "target_id": null, "reason": "new info"}',
            # CuratorService: EXTRACT (for curator cycle)
            json.dumps([{"content": "系统架构知识", "importance": 0.5, "tags": []}]),
            # CuratorService: RECONCILE
            '{"action": "NOOP", "target_id": null, "reason": "already captured"}',
        ])

        pipeline, svc = _build_ingest_pipeline(tmp_data_dir, ingest_llm)

        report = await pipeline.ingest("Memory Palace系统使用三层存储。用户偏好Python。")
        assert report.memories_created == 2
        assert report.errors == []

        # === Step 2: Search → memories retrievable ===
        results = svc.search_sync("存储架构", top_k=5)
        assert len(results) >= 1
        assert any("存储" in r.content for r in results)

        # === Step 3: Curate ===
        from memory_palace.service.curator import CuratorService

        curator = CuratorService(tmp_data_dir, ingest_llm)
        curator_report = await curator.run()
        assert curator_report is not None
        assert curator_report.duration_seconds >= 0

        # === Step 4: Ebbinghaus decay (pure function) ===
        # Fresh memory → high retention
        eff = effective_importance(
            importance=0.6,
            hours_since_access=1.0,
            access_count=0,
        )
        assert eff > 0.5

        # Very old memory → decayed
        eff_old = effective_importance(
            importance=0.3,
            hours_since_access=10000.0,
            access_count=0,
        )
        assert eff_old < 0.1
        assert should_prune(
            importance=0.3,
            hours_since_access=10000.0,
            access_count=0,
        )

        # === Step 5: Health + Metrics ===
        from memory_palace.store.core_store import CoreStore
        from memory_palace.store.recall_store import RecallStore

        core_items = []
        cs = CoreStore(tmp_data_dir)
        for block in cs.list_blocks():
            core_items.extend(cs.load(block))

        recall_items = RecallStore(tmp_data_dir).get_recent(1000)
        cfg = Config()

        health = compute_health(core_items, recall_items, cfg.rooms)
        assert health.overall >= 0.0
        assert health.overall <= 1.0

        # Verify metrics exist
        m = svc.get_metrics()
        assert isinstance(m, dict)
        assert "total_saves" in m


# ── Test 2: Multi-Persona Isolation ──────────────────────────


class TestV10MultiPersonaIsolation:
    """persona A ingest → persona B search → not found → data isolation."""

    @pytest.mark.asyncio
    async def test_v10_multi_persona_isolation(self, tmp_path):
        """Memories ingested under persona A are invisible to persona B."""
        # Create separate data dirs for two personas
        dir_a = tmp_path / "persona_a"
        dir_a.mkdir()
        (dir_a / "core").mkdir()

        dir_b = tmp_path / "persona_b"
        dir_b.mkdir()
        (dir_b / "core").mkdir()

        # Ingest into persona A
        llm_a = MockLLM(responses=[
            json.dumps([
                {"content": "PersonaA的秘密记忆", "importance": 0.6, "tags": []},
            ]),
            json.dumps([{"index": 0, "room": "general", "importance": 0.6}]),
            '{"action": "ADD", "target_id": null, "reason": "new"}',
        ])
        pipeline_a, svc_a = _build_ingest_pipeline(dir_a, llm_a)

        report_a = await pipeline_a.ingest("PersonaA的秘密")
        assert report_a.memories_created == 1

        # Search from persona B → should find nothing
        svc_b = MemoryService(dir_b)
        results_b = svc_b.search_sync("PersonaA", top_k=5)
        assert len(results_b) == 0

        # Confirm persona A can find it
        results_a = svc_a.search_sync("秘密", top_k=5)
        assert len(results_a) >= 1


# ── Test 3: Batch Roundtrip ─────────────────────────────────


class TestV10BatchRoundtrip:
    """ingest → export JSONL → import JSONL → count matches."""

    @pytest.mark.asyncio
    async def test_v10_batch_roundtrip(self, tmp_data_dir):
        """Ingest documents, export to JSONL, import into fresh store, verify count."""
        # Step 1: Ingest some memories
        llm = MockLLM(responses=[
            json.dumps([
                {"content": "记忆一号", "importance": 0.5, "tags": ["test"]},
                {"content": "记忆二号", "importance": 0.6, "tags": ["test"]},
                {"content": "记忆三号", "importance": 0.4, "tags": ["test"]},
            ]),
            json.dumps([
                {"index": 0, "room": "general", "importance": 0.5},
                {"index": 1, "room": "projects", "importance": 0.6},
                {"index": 2, "room": "skills", "importance": 0.4},
            ]),
            '{"action": "ADD", "target_id": null, "reason": "new"}',
            '{"action": "ADD", "target_id": null, "reason": "new"}',
            '{"action": "ADD", "target_id": null, "reason": "new"}',
        ])
        pipeline, svc = _build_ingest_pipeline(tmp_data_dir, llm)

        report = await pipeline.ingest("三条记忆内容")
        assert report.memories_created == 3

        # Step 2: Export to JSONL
        exporter = BatchExporter(svc)
        jsonl_path = tmp_data_dir / "export.jsonl"
        export_report = exporter.export_jsonl(jsonl_path)
        assert export_report.total_exported == 3

        # Step 3: Import into fresh store
        fresh_dir = tmp_data_dir / "fresh"
        fresh_dir.mkdir()
        (fresh_dir / "core").mkdir()
        fresh_svc = MemoryService(fresh_dir)
        importer = BatchImporter(fresh_svc)

        import_report = await importer.import_jsonl(jsonl_path)
        assert import_report.imported == 3
        assert import_report.skipped == 0

        # Step 4: Verify counts match
        fresh_stats = fresh_svc.stats()
        assert fresh_stats["total"] == 3
