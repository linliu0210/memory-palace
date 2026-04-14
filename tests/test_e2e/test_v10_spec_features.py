"""Layer 3 SPEC Feature Verification Tests — v1.0 declared components P-1..P-10.

Validates SPEC §6.1 declared components:
  T3.1  Sleep-time Compute Auto-Trigger
  T3.2  Heartbeat Safety Guard
  T3.3  Ebbinghaus Complete Formula Verification
  T3.4  Core Budget Auto-Demote
  T3.5  Monitoring Metrics 7 Fields
  T3.6  MCP Server Tool Registration
  T3.7  Markdown Import with Frontmatter
  T3.8  Export Format Verification
  T3.9  Multi-Persona Data Isolation
  T3.10 Ingest Pipeline Full 5-Pass

Ref: SPEC §6.1, TASK_R25
"""

from __future__ import annotations

import asyncio
import json
import math

import pytest

from memory_palace.engine.ebbinghaus import (
    effective_importance,
    retention,
    should_prune,
    stability,
)
from memory_palace.engine.fact_extractor import FactExtractor
from memory_palace.engine.reconcile import ReconcileEngine
from memory_palace.models.memory import MemoryStatus
from memory_palace.service.batch_io import BatchExporter, BatchImporter
from memory_palace.service.curator import CuratorService
from memory_palace.service.curator_graph import CuratorGraph
from memory_palace.service.heartbeat import HeartbeatController
from memory_palace.service.ingest_pipeline import IngestPipeline
from memory_palace.service.memory_service import MemoryService
from memory_palace.service.scheduler import SleepTimeScheduler
from tests.conftest import MockLLM

# ── T3.1 — Sleep-time Compute Auto-Trigger ────────────────────


class TestSleepTimeComputeAutoTrigger:
    """SleepTimeScheduler triggers CuratorService at least once."""

    @pytest.mark.asyncio
    async def test_scheduler_auto_trigger(self, tmp_data_dir):
        llm = MockLLM(
            responses=[
                # EXTRACT
                json.dumps([{"content": "测试事实", "importance": 0.5, "tags": ["test"]}]),
                # RECONCILE
                json.dumps({"action": "NOOP", "target_id": None, "reason": "known"}),
                # REFLECT
                json.dumps([]),
            ]
        )
        curator = CuratorService(tmp_data_dir, llm)
        scheduler = SleepTimeScheduler(curator, check_interval=0.1)
        await scheduler.start()
        await asyncio.sleep(0.3)
        await scheduler.stop()
        assert scheduler.stats["trigger_count"] >= 1
        assert scheduler.last_run_report is not None
        assert scheduler.is_running is False


# ── T3.2 — Heartbeat Safety Guard ─────────────────────────────


class TestHeartbeatSafetyGuard:
    """HeartbeatController stops CuratorGraph early on max_steps breach."""

    @pytest.mark.asyncio
    async def test_heartbeat_stops_curator_early(self, tmp_data_dir):
        # Save several items so CuratorGraph has work to do
        svc = MemoryService(tmp_data_dir)
        for i in range(5):
            svc.save(content=f"heartbeat test item {i}", importance=0.4)

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

        heartbeat = HeartbeatController(max_steps=3, max_llm_calls=30, max_duration_seconds=120)
        graph = CuratorGraph(
            memory_service=svc,
            recall_store=svc._recall_store,
            core_store=svc._core_store,
            fact_extractor=FactExtractor(llm),
            reconcile_engine=ReconcileEngine(llm),
            llm=llm,
            heartbeat=heartbeat,
        )

        report = await graph.run()
        # With max_steps=3, the graph should hit the safety limit
        has_safety_error = any("Safety" in e or "max_steps" in e for e in report.errors)
        assert has_safety_error, f"Expected safety error, got: {report.errors}"


# ── T3.3 — Ebbinghaus Complete Formula Verification ───────────


class TestEbbinghausFormula:
    """Pure function tests for the Ebbinghaus forgetting curve engine."""

    def test_retention_at_zero(self):
        assert retention(0, 168) == pytest.approx(1.0)

    def test_retention_at_one_week(self):
        # R(168, 168) = exp(-1) ≈ 0.368
        assert retention(168, 168) == pytest.approx(math.exp(-1), rel=1e-3)

    def test_retention_at_one_month(self):
        # R(720, 168) = exp(-720/168) ≈ 0.014
        assert retention(720, 168) == pytest.approx(math.exp(-720 / 168), rel=1e-3)

    def test_stability_increases_with_access(self):
        s0 = stability(168, 0)   # = 168
        s5 = stability(168, 5)   # = 168 × (1 + ln(6))
        assert s5 > s0 * 2

    def test_effective_importance_decays(self):
        ei = effective_importance(0.5, hours_since_access=168, access_count=0)
        assert ei < 0.5

    def test_access_slows_decay(self):
        ei = effective_importance(0.5, hours_since_access=168, access_count=0)
        ei_accessed = effective_importance(0.5, hours_since_access=168, access_count=10)
        assert ei_accessed > ei

    def test_should_prune_old_low_importance(self):
        assert should_prune(0.2, hours_since_access=720, access_count=0)

    def test_should_not_prune_high_importance_accessed(self):
        assert not should_prune(0.9, hours_since_access=720, access_count=5)


# ── T3.4 — Core Budget Auto-Demote ────────────────────────────


class TestCoreBudgetAutoDemote:
    """Core store auto-demotes oldest items when block exceeds budget (10)."""

    def test_core_budget_auto_demote(self, tmp_data_dir):
        svc = MemoryService(tmp_data_dir)
        # Save 15 items with importance >= 0.7 → all route to Core "general" block
        for i in range(15):
            svc.save(content=f"core budget item {i}", importance=0.9, room="general")

        # Core block should be capped at CORE_MAX_ITEMS_PER_BLOCK (10)
        core_items = svc._core_store.load("general")
        active_core = [it for it in core_items if it.status == MemoryStatus.ACTIVE]
        assert len(active_core) <= 10

        # Demoted items should be in recall
        recall_items = svc._recall_store.get_recent(100)
        assert len(recall_items) >= 5  # at least 5 demoted


# ── T3.5 — Monitoring Metrics 7 Fields ────────────────────────


class TestMonitoringMetrics:
    """MemoryService.get_metrics() returns all 7 required metric fields."""

    def test_metrics_fields(self, tmp_data_dir):
        svc = MemoryService(tmp_data_dir)
        m_before = svc.get_metrics()
        saves_before = m_before["total_saves"]
        searches_before = m_before["total_searches"]

        for i in range(10):
            svc.save(content=f"metrics item {i}", importance=0.5)
        for _ in range(5):
            svc.search_sync("metrics item", top_k=1)

        m = svc.get_metrics()
        assert m["total_saves"] - saves_before == 10
        assert m["total_searches"] - searches_before == 5
        assert m["save_p95_ms"] >= 0
        assert m["search_p95_ms"] >= 0
        assert "growth_rate_per_day" in m
        assert "total_curations" in m
        assert "curator_avg_duration_s" in m


# ── T3.6 — MCP Server Tool Registration ───────────────────────


class TestMCPServerToolRegistration:
    """FastMCP instance has >= 18 registered tools with expected names."""

    def test_mcp_tools_registered(self):
        from memory_palace.integration.mcp_server import mcp

        expected = {
            "save_memory",
            "search_memory",
            "update_memory",
            "forget_memory",
            "inspect_memory",
            "curate_now",
            "reflect_now",
            "get_health",
            "list_rooms",
            "get_stats",
            "get_audit_log",
            "get_context",
            "ingest_document",
            "import_memories",
            "export_memories",
            "list_personas",
            "switch_persona",
            "get_metrics",
        }

        # FastMCP stores tools in _tool_manager._tools dict
        tool_names: set[str] = set()
        if hasattr(mcp, "_tool_manager") and hasattr(mcp._tool_manager, "_tools"):
            tool_names = set(mcp._tool_manager._tools.keys())
        elif hasattr(mcp, "_tools"):
            tool_names = set(mcp._tools.keys())
        else:
            # Fallback: inspect via list_tools (sync or async)
            import inspect

            if hasattr(mcp, "list_tools"):
                result = mcp.list_tools()
                if inspect.isawaitable(result):
                    pytest.skip("Cannot call async list_tools in sync test")
                tool_names = {t.name if hasattr(t, "name") else str(t) for t in result}

        assert len(tool_names) >= 18, f"Expected >= 18 tools, got {len(tool_names)}: {tool_names}"
        missing = expected - tool_names
        assert not missing, f"Missing MCP tools: {missing}"


# ── T3.7 — Markdown Import with Frontmatter ───────────────────


class TestMarkdownImportFrontmatter:
    """BatchImporter parses YAML frontmatter (importance, room, tags)."""

    @pytest.mark.asyncio
    async def test_import_markdown_with_frontmatter(self, tmp_data_dir):
        md_content = """\
---
importance: 0.8
room: projects
tags: [python, ml]
---
## 记忆标题一
第一条记忆内容

## 记忆标题二
第二条记忆内容
"""
        md_file = tmp_data_dir / "import_test.md"
        md_file.write_text(md_content, encoding="utf-8")

        svc = MemoryService(tmp_data_dir)
        importer = BatchImporter(svc)
        report = await importer.import_markdown(md_file)

        assert report.total_found == 2
        assert report.imported == 2
        assert report.errors == []

        # Verify imported items have correct frontmatter values
        # importance=0.8 → Core tier (>= 0.7)
        core_items = svc._core_store.load("projects")
        assert len(core_items) >= 2, (
            f"Expected 2 items in 'projects' core block, got {len(core_items)}"
        )
        for item in core_items:
            assert item.importance == pytest.approx(0.8)
            assert item.room == "projects"
            assert "python" in item.tags
            assert "ml" in item.tags


# ── T3.8 — Export Format Verification ──────────────────────────


class TestExportFormatVerification:
    """BatchExporter produces correct markdown and JSONL output."""

    def test_export_markdown_creates_room_files(self, tmp_data_dir):
        svc = MemoryService(tmp_data_dir)
        svc.save(content="export md general", importance=0.5, room="general")
        svc.save(content="export md projects", importance=0.5, room="projects")

        exporter = BatchExporter(svc)
        output_dir = tmp_data_dir / "export_md"
        report = exporter.export_markdown(output_dir)

        assert report.total_exported == 2
        assert (output_dir / "general.md").exists()
        assert (output_dir / "projects.md").exists()

    def test_export_jsonl_valid_json_lines(self, tmp_data_dir):
        svc = MemoryService(tmp_data_dir)
        for i in range(3):
            svc.save(content=f"jsonl item {i}", importance=0.5)

        exporter = BatchExporter(svc)
        output_path = tmp_data_dir / "export.jsonl"
        report = exporter.export_jsonl(output_path)

        assert report.total_exported == 3
        assert output_path.exists()

        lines = output_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3
        for line in lines:
            data = json.loads(line)
            assert "content" in data
            assert "importance" in data
            assert "id" in data


# ── T3.9 — Multi-Persona Data Isolation ───────────────────────


class TestMultiPersonaDataIsolation:
    """Separate data_dir instances are fully isolated."""

    def test_persona_isolation(self, tmp_path):
        dir_a = tmp_path / "persona_a"
        dir_b = tmp_path / "persona_b"
        for d in (dir_a, dir_b):
            (d / "core").mkdir(parents=True)
            (d / "archival").mkdir(parents=True)

        svc_a = MemoryService(dir_a)
        svc_b = MemoryService(dir_b)

        svc_a.save(content="Persona A secret", importance=0.5)

        results_b = svc_b.search_sync("secret")
        assert len(results_b) == 0

        results_a = svc_a.search_sync("secret")
        assert len(results_a) >= 1


# ── T3.10 — Ingest Pipeline Full 5-Pass ───────────────────────


class TestIngestPipelineFullFivePass:
    """IngestPipeline processes a document through all 5 passes."""

    @pytest.mark.asyncio
    async def test_ingest_creates_memories(self, tmp_data_dir):
        llm = MockLLM(
            responses=[
                # EXTRACT: 3 facts
                json.dumps([
                    {"content": "事实一", "importance": 0.5, "tags": ["test"]},
                    {"content": "事实二", "importance": 0.6, "tags": ["test"]},
                    {"content": "事实三", "importance": 0.4, "tags": ["test"]},
                ]),
                # MAP
                json.dumps([
                    {"index": 0, "room": "general", "importance": 0.5},
                    {"index": 1, "room": "projects", "importance": 0.6},
                    {"index": 2, "room": "skills", "importance": 0.4},
                ]),
                # RECONCILE × 3
                '{"action": "ADD", "target_id": null, "reason": "new"}',
                '{"action": "ADD", "target_id": null, "reason": "new"}',
                '{"action": "ADD", "target_id": null, "reason": "new"}',
            ]
        )

        svc = MemoryService(tmp_data_dir, llm=llm)
        pipeline = IngestPipeline(
            memory_service=svc,
            fact_extractor=FactExtractor(llm),
            reconcile_engine=ReconcileEngine(llm),
            llm=llm,
        )

        report = await pipeline.ingest("含 3 个事实的文档", source_id="doc-001")

        assert report.memories_created == 3
        assert report.errors == []
        assert "EXTRACT" in report.pass_results or len(report.pass_results) > 0

    @pytest.mark.asyncio
    async def test_ingest_dedup_skips_second_run(self, tmp_data_dir):
        """Same source_id ingested twice → second run creates 0 memories."""
        llm = MockLLM(
            responses=[
                # EXTRACT: 3 facts
                json.dumps([
                    {"content": "事实一", "importance": 0.5, "tags": ["test"]},
                    {"content": "事实二", "importance": 0.6, "tags": ["test"]},
                    {"content": "事实三", "importance": 0.4, "tags": ["test"]},
                ]),
                # MAP
                json.dumps([
                    {"index": 0, "room": "general", "importance": 0.5},
                    {"index": 1, "room": "projects", "importance": 0.6},
                    {"index": 2, "room": "skills", "importance": 0.4},
                ]),
                # RECONCILE × 3
                '{"action": "ADD", "target_id": null, "reason": "new"}',
                '{"action": "ADD", "target_id": null, "reason": "new"}',
                '{"action": "ADD", "target_id": null, "reason": "new"}',
            ]
        )

        svc = MemoryService(tmp_data_dir, llm=llm)
        pipeline = IngestPipeline(
            memory_service=svc,
            fact_extractor=FactExtractor(llm),
            reconcile_engine=ReconcileEngine(llm),
            llm=llm,
        )

        # First ingest
        report1 = await pipeline.ingest("含 3 个事实的文档", source_id="doc-dedup")
        assert report1.memories_created == 3

        # Second ingest with same source_id → DIFF pass should skip
        report2 = await pipeline.ingest("含 3 个事实的文档", source_id="doc-dedup")
        assert report2.memories_created == 0
