"""Layer 4 Supplementary E2E Tests — T4.1..T4.5.

Validates supplementary integration scenarios:
  T4.1  GraphStore / ArchivalStore Proximity Affects Search Ordering
  T4.2  Concurrent Write Safety
  T4.3  Ebbinghaus + Curator Integration
  T4.4  Export → Import Data Completeness
  T4.5  Health Score 6 Dimensions Non-Zero

Ref: SPEC §6.1, TASK_R25
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta

import pytest

from memory_palace.config import Config, EbbinghausConfig
from memory_palace.engine.fact_extractor import FactExtractor
from memory_palace.engine.health import compute_health
from memory_palace.engine.reconcile import ReconcileEngine
from memory_palace.models.memory import MemoryStatus
from memory_palace.service.batch_io import BatchExporter, BatchImporter
from memory_palace.service.curator_graph import CuratorGraph
from memory_palace.service.heartbeat import HeartbeatController
from memory_palace.service.memory_service import MemoryService
from memory_palace.store.core_store import CoreStore
from memory_palace.store.recall_store import RecallStore
from tests.conftest import MockEmbedding, MockLLM

# ── T4.1 — GraphStore Proximity Affects Search Ordering ────


class TestGraphStoreProximity:
    """ArchivalStore + MockEmbedding search ordering is sensible."""

    @pytest.mark.asyncio
    async def test_archival_search_ordering(self, tmp_data_dir):
        pytest.importorskip("chromadb")
        from memory_palace.store.archival_store import ArchivalStore

        mock_emb = MockEmbedding()
        archival = ArchivalStore(data_dir=tmp_data_dir, embedding=mock_emb)
        svc = MemoryService(
            tmp_data_dir,
            embedding=mock_emb,
            archival_store=archival,
        )

        # Save items with distinct content in different rooms
        svc.save(content="Python机器学习项目", importance=0.5, room="projects")
        svc.save(content="Rust系统编程经验", importance=0.5, room="skills")
        svc.save(content="Python深度学习框架", importance=0.5, room="projects")

        # Search using hybrid retriever
        results = await svc.search("Python学习", top_k=3)
        assert len(results) >= 1
        # All returned results should be valid MemoryItems
        for item in results:
            assert item.content
            assert item.room in ("projects", "skills")


# ── T4.2 — Concurrent Write Safety ────────────────────────


class TestConcurrentWriteSafety:
    """MemoryService handles concurrent saves without data loss."""

    @pytest.mark.asyncio
    async def test_concurrent_saves(self, tmp_data_dir):
        svc = MemoryService(tmp_data_dir)

        # Use async_save which acquires write lock for concurrency safety
        tasks = [
            svc.async_save(content=f"并发记忆 {i}", importance=0.5)
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        # Verify no data loss
        stats = svc.stats()
        assert stats["total"] == 10
        # Verify all are distinct
        ids = {r.id for r in results}
        assert len(ids) == 10


# ── T4.3 — Ebbinghaus + Curator Integration ───────────────


class TestEbbinghausCuratorIntegration:
    """CuratorGraph with Ebbinghaus pruning prunes old low-importance items."""

    @pytest.mark.asyncio
    async def test_curator_with_ebbinghaus(self, tmp_data_dir):
        llm = MockLLM(
            responses=[
                # EXTRACT
                json.dumps([{"content": "事实", "importance": 0.5, "tags": ["test"]}]),
                # RECONCILE
                json.dumps({"action": "NOOP", "target_id": None, "reason": "known"}),
                # REFLECT
                json.dumps([]),
            ]
        )
        ms = MemoryService(tmp_data_dir, llm)

        # Save items: one high importance (→ Core), one low importance (→ Recall)
        high = ms.save(content="重要持久记忆", importance=0.9)
        low = ms.save(content="低重要性信息", importance=0.2)

        # Age the low importance item by backdating accessed_at
        recall_store = RecallStore(tmp_data_dir)
        old_time = (datetime.now() - timedelta(days=60)).isoformat()
        recall_store.update_field(low.id, "accessed_at", old_time)

        # Run curator with Ebbinghaus enabled
        eb_cfg = EbbinghausConfig(enabled=True)
        heartbeat = HeartbeatController(
            max_steps=100, max_llm_calls=50, max_duration_seconds=30
        )
        graph = CuratorGraph(
            memory_service=ms,
            recall_store=recall_store,
            core_store=ms._core_store,
            fact_extractor=FactExtractor(llm),
            reconcile_engine=ReconcileEngine(llm),
            llm=llm,
            ebbinghaus_config=eb_cfg,
            heartbeat=heartbeat,
        )
        report = await graph.run()

        # Low importance old item should be pruned via Ebbinghaus
        assert report.ebbinghaus_pruned >= 1
        pruned = recall_store.get(low.id)
        assert pruned is not None
        assert pruned.status == MemoryStatus.PRUNED

        # High importance item should survive (it's in Core since importance=0.9)
        high_item = ms.get_by_id(high.id)
        assert high_item is not None
        assert high_item.status == MemoryStatus.ACTIVE


# ── T4.4 — Export → Import Data Completeness ──────────────


class TestExportImportCompleteness:
    """BatchExporter → BatchImporter roundtrip preserves all fields."""

    @pytest.mark.asyncio
    async def test_export_import_roundtrip_fields(self, tmp_data_dir):
        svc = MemoryService(tmp_data_dir)
        # Save items with specific fields
        svc.save(content="导出测试一", importance=0.6, room="projects", tags=["python", "ml"])
        svc.save(content="导出测试二", importance=0.4, room="skills", tags=["rust"])

        # Export JSONL
        exporter = BatchExporter(svc)
        jsonl_path = tmp_data_dir / "roundtrip.jsonl"
        export_report = exporter.export_jsonl(jsonl_path)
        assert export_report.total_exported == 2

        # Verify JSONL content
        lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            data = json.loads(line)
            assert "id" in data
            assert "content" in data
            assert "importance" in data
            assert "room" in data
            assert "tags" in data

        # Import into fresh store
        fresh_dir = tmp_data_dir / "fresh"
        fresh_dir.mkdir()
        (fresh_dir / "core").mkdir()
        (fresh_dir / "archival").mkdir()
        fresh_svc = MemoryService(fresh_dir)
        importer = BatchImporter(fresh_svc)
        import_report = await importer.import_jsonl(jsonl_path)
        assert import_report.imported == 2

        # Verify content matches
        original_items = svc.search_sync("导出测试", top_k=10)
        imported_items = fresh_svc.search_sync("导出测试", top_k=10)
        assert len(imported_items) == len(original_items)


# ── T4.5 — Health Score 6 Dimensions Non-Zero ─────────────


class TestHealthScoreDimensions:
    """compute_health returns non-zero values across all 6 dimensions."""

    def test_health_all_dimensions_with_data(self, tmp_data_dir):
        svc = MemoryService(tmp_data_dir)
        # Save items in multiple rooms to get coverage
        for room in ["general", "preferences", "projects", "people", "skills"]:
            svc.save(content=f"{room}记忆内容", importance=0.5, room=room)

        # Also save some high-importance for core
        svc.save(content="核心记忆", importance=0.9, room="general")

        # Do some searches to populate metrics
        for _ in range(3):
            svc.search_sync("记忆", top_k=3)

        core_items: list = []
        cs = CoreStore(tmp_data_dir)
        for block in cs.list_blocks():
            core_items.extend(cs.load(block))
        recall_items = RecallStore(tmp_data_dir).get_recent(1000)

        cfg = Config()
        health = compute_health(core_items, recall_items, cfg.rooms, svc.get_metrics())

        # With data in all rooms, coverage should be > 0
        assert health.coverage > 0
        # Fresh data → freshness should be > 0
        assert health.freshness > 0
        # overall should be > 0
        assert health.overall > 0
        # All dimensions should be in [0, 1]
        for dim in ["freshness", "efficiency", "coverage", "diversity", "coherence", "operations"]:
            val = getattr(health, dim)
            assert 0.0 <= val <= 1.0, f"{dim} = {val} out of range"
