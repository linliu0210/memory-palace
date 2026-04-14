"""Layer 2 MCP E2E Tests — v1.0 MCP tool implementations.

Tests MCP _impl_* functions end-to-end: save/search/inspect, error handling,
health/stats/audit/metrics, context compilation, persona and batch tools.

Ref: TASK_R25
"""

from __future__ import annotations

import pytest

from memory_palace.integration.mcp_context import MCPServiceManager
from memory_palace.integration.mcp_server import (
    _impl_forget_memory,
    _impl_get_audit_log,
    _impl_get_context,
    _impl_get_health,
    _impl_get_metrics,
    _impl_get_stats,
    _impl_import_memories,
    _impl_inspect_memory,
    _impl_list_personas,
    _impl_save_memory,
    _impl_search_memory,
)


@pytest.fixture(autouse=True)
def _setup_mcp(tmp_path):
    """Configure MCPServiceManager with temp directory for each test."""
    (tmp_path / "core").mkdir(exist_ok=True)
    MCPServiceManager.configure(tmp_path)
    yield
    MCPServiceManager._service = None
    MCPServiceManager._lock = None


# ── T2.9 — MCP Save → Search → Inspect ───────────────────────


class TestMCPSaveSearchInspect:
    """Save a memory, search for it, then inspect by id."""

    @pytest.mark.asyncio
    async def test_save_returns_success_with_id(self):
        result = await _impl_save_memory("MCP test", importance=0.6)
        assert result["success"] is True
        assert "id" in result["data"]

    @pytest.mark.asyncio
    async def test_search_finds_saved_memory(self):
        result = await _impl_save_memory("MCP test", importance=0.6)
        assert result["success"] is True

        search = await _impl_search_memory("MCP test")
        assert search["success"] is True
        assert isinstance(search["data"], list)
        assert len(search["data"]) >= 1

    @pytest.mark.asyncio
    async def test_inspect_returns_correct_content(self):
        result = await _impl_save_memory("MCP test", importance=0.6)
        memory_id = result["data"]["id"]

        inspect = await _impl_inspect_memory(memory_id)
        assert inspect["success"] is True
        assert inspect["data"]["content"] == "MCP test"

    @pytest.mark.asyncio
    async def test_save_search_inspect_full_flow(self):
        """Full flow: save → search → inspect."""
        # Save
        save_result = await _impl_save_memory("MCP test", importance=0.6)
        assert save_result["success"] is True
        memory_id = save_result["data"]["id"]

        # Search
        search_result = await _impl_search_memory("MCP test")
        assert search_result["success"] is True
        assert len(search_result["data"]) >= 1

        # Inspect
        inspect_result = await _impl_inspect_memory(memory_id)
        assert inspect_result["success"] is True
        assert inspect_result["data"]["content"] == "MCP test"


# ── T2.10 — MCP Error Handling Uniformity ─────────────────────


class TestMCPErrorHandlingUniformity:
    """All errors follow {success: False, error: str, code: str}."""

    @pytest.mark.asyncio
    async def test_save_importance_too_high(self):
        result = await _impl_save_memory("x", importance=1.5)
        assert result["success"] is False
        assert result["code"] == "VALIDATION"
        assert isinstance(result["error"], str)

    @pytest.mark.asyncio
    async def test_save_importance_too_low(self):
        result = await _impl_save_memory("x", importance=-0.1)
        assert result["success"] is False
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_inspect_empty_id(self):
        result = await _impl_inspect_memory("")
        assert result["success"] is False
        assert result["code"] == "VALIDATION"
        assert isinstance(result["error"], str)

    @pytest.mark.asyncio
    async def test_forget_nonexistent_id(self):
        result = await _impl_forget_memory("nonexistent-id")
        assert result["success"] is False
        assert result["code"] == "NOT_FOUND"
        assert isinstance(result["error"], str)

    @pytest.mark.asyncio
    async def test_search_top_k_too_high(self):
        result = await _impl_search_memory("test", top_k=999)
        assert result["success"] is False
        assert result["code"] == "VALIDATION"
        assert isinstance(result["error"], str)

    @pytest.mark.asyncio
    async def test_search_top_k_too_low(self):
        result = await _impl_search_memory("test", top_k=0)
        assert result["success"] is False
        assert result["code"] == "VALIDATION"
        assert isinstance(result["error"], str)

    @pytest.mark.asyncio
    async def test_all_errors_have_uniform_format(self):
        """Verify all error responses share the same three keys."""
        errors = [
            await _impl_save_memory("x", importance=1.5),
            await _impl_inspect_memory(""),
            await _impl_forget_memory("nonexistent-id"),
            await _impl_search_memory("test", top_k=999),
            await _impl_search_memory("test", top_k=0),
        ]
        for err in errors:
            assert err["success"] is False
            assert "error" in err and isinstance(err["error"], str)
            assert "code" in err and isinstance(err["code"], str)


# ── T2.11 — MCP Tools: Health + Stats + Audit + Metrics ──────


class TestMCPHealthStatsAuditMetrics:
    """Health, stats, audit log, and metrics after saving items."""

    @pytest.mark.asyncio
    async def test_health_has_all_dimensions(self):
        for i in range(3):
            await _impl_save_memory(f"health item {i}", importance=0.5)

        result = await _impl_get_health()
        assert result["success"] is True
        data = result["data"]
        dims = ("freshness", "efficiency", "coverage",
                "diversity", "coherence", "operations", "overall")
        for key in dims:
            assert key in data, f"Missing health dimension: {key}"

    @pytest.mark.asyncio
    async def test_stats_total_gte_saved(self):
        for i in range(3):
            await _impl_save_memory(f"stats item {i}", importance=0.5)

        result = await _impl_get_stats()
        assert result["success"] is True
        assert result["data"]["total"] >= 3

    @pytest.mark.asyncio
    async def test_audit_log_returns_list(self):
        for i in range(3):
            await _impl_save_memory(f"audit item {i}", importance=0.5)

        entries = await _impl_get_audit_log()
        assert isinstance(entries, list)
        assert len(entries) >= 3

    @pytest.mark.asyncio
    async def test_metrics_total_saves(self):
        for i in range(3):
            await _impl_save_memory(f"metrics item {i}", importance=0.5)

        result = await _impl_get_metrics()
        assert result["success"] is True
        assert isinstance(result["data"], dict)
        assert result["data"].get("total_saves", 0) >= 3


# ── T2.12 — MCP Context Compilation ──────────────────────────


class TestMCPContextCompilation:
    """Save items then compile context and verify format."""

    @pytest.mark.asyncio
    async def test_context_returns_str_with_content(self):
        await _impl_save_memory("context alpha", importance=0.8, room="general")
        await _impl_save_memory("context beta", importance=0.6, room="preferences")
        await _impl_save_memory("context gamma", importance=0.4, room="skills")

        context = await _impl_get_context(query="test")
        assert isinstance(context, str)
        assert len(context) > 0

    @pytest.mark.asyncio
    async def test_context_has_section_markers(self):
        await _impl_save_memory("section marker test", importance=0.8)
        await _impl_save_memory("another section item", importance=0.6)
        await _impl_save_memory("third section item", importance=0.4)

        context = await _impl_get_context(query="test")
        assert isinstance(context, str)
        # Context compiler emits section markers like [CORE MEMORY], [RECENT ACTIVITY]
        assert "[" in context and "]" in context


# ── T2.13 — MCP Persona + Batch Tools ────────────────────────


class TestMCPPersonaBatchTools:
    """List personas and test batch import via exported JSONL."""

    @pytest.mark.asyncio
    async def test_list_personas_returns_list(self):
        result = await _impl_list_personas()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_import_memories_from_exported_jsonl(self, tmp_path):
        """Save items, export via BatchExporter, then import via _impl_import_memories."""
        # Save some items first
        for i in range(3):
            await _impl_save_memory(f"batch item {i}", importance=0.5)

        # Export via BatchExporter directly
        from memory_palace.service.batch_io import BatchExporter

        svc = await MCPServiceManager.get_service()
        exporter = BatchExporter(svc)
        export_path = tmp_path / "export.jsonl"
        report = exporter.export_jsonl(export_path)
        assert report.total_exported >= 3

        # Reset service to a fresh data dir for import
        fresh_dir = tmp_path / "fresh"
        fresh_dir.mkdir()
        (fresh_dir / "core").mkdir()
        MCPServiceManager._service = None
        MCPServiceManager._lock = None
        MCPServiceManager.configure(fresh_dir)

        # Import the exported file
        result = await _impl_import_memories(str(export_path))
        assert isinstance(result, dict)
        assert result.get("imported", 0) >= 3
