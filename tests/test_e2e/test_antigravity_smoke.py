"""Antigravity Integration Smoke Test.

Simulates real Antigravity→Memory Palace usage via:
  1. CLI interface (save/search/inspect/curate/metrics/rooms/audit)
  2. MCP tool layer (_impl_* functions)
  3. Sleep-time scheduler (auto-trigger curate)
  4. Context compilation (full pipeline)

All MockLLM — no real API calls.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from typer.testing import CliRunner


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 1: CLI — Simulate Antigravity calling `palace` commands
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestCLISmoke:
    """Simulate Antigravity calling CLI commands."""

    def test_save_search_inspect(self, tmp_path):
        """palace save → search → inspect end-to-end."""
        from memory_palace.integration.cli import app

        runner = CliRunner()
        dd = str(tmp_path)
        (tmp_path / "core").mkdir()

        # Save
        r1 = runner.invoke(app, [
            "save", "Antigravity 是 Google DeepMind 的 IDE",
            "--importance", "0.8", "--room", "general",
            "--data-dir", dd,
        ])
        assert r1.exit_code == 0, f"save failed: {r1.output}"

        r2 = runner.invoke(app, [
            "save", "Memory Palace v1.0 已发布",
            "--importance", "0.9", "--room", "projects",
            "--data-dir", dd,
        ])
        assert r2.exit_code == 0

        # Search
        r_search = runner.invoke(app, [
            "search", "Memory Palace",
            "--top-k", "5", "--data-dir", dd,
        ])
        assert r_search.exit_code == 0
        assert "Memory Palace" in r_search.output

        # Rooms (static, no data-dir needed)
        r_rooms = runner.invoke(app, ["rooms"])
        assert r_rooms.exit_code == 0

        # Metrics
        r_metrics = runner.invoke(app, ["metrics", "--data-dir", dd])
        assert r_metrics.exit_code == 0

    def test_audit_and_rooms(self, tmp_path):
        """palace audit + rooms work after saves."""
        from memory_palace.integration.cli import app

        runner = CliRunner()
        dd = str(tmp_path)
        (tmp_path / "core").mkdir()

        # Save to generate audit entries
        runner.invoke(app, [
            "save", "审计测试记忆",
            "--importance", "0.5", "--data-dir", dd,
        ])

        # Audit (uses --last, not --last-n)
        r_audit = runner.invoke(app, ["audit", "--last", "10", "--data-dir", dd])
        assert r_audit.exit_code == 0

    def test_serve_help(self):
        """palace serve --help reachable."""
        from memory_palace.integration.cli import app

        runner = CliRunner()
        r = runner.invoke(app, ["serve", "--help"])
        assert r.exit_code == 0
        assert "stdio" in r.output.lower() or "transport" in r.output.lower()

    def test_persona_commands(self):
        """palace persona subcommands all reachable."""
        from memory_palace.integration.cli import app

        runner = CliRunner()
        for cmd in ["list", "create", "switch", "delete"]:
            r = runner.invoke(app, ["persona", cmd, "--help"])
            assert r.exit_code == 0, f"persona {cmd} --help failed"

    def test_schedule_commands(self):
        """palace schedule subcommands all reachable."""
        from memory_palace.integration.cli import app

        runner = CliRunner()
        for cmd in ["start", "status"]:
            r = runner.invoke(app, ["schedule", cmd, "--help"])
            assert r.exit_code == 0, f"schedule {cmd} --help failed"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 2: MCP Tool Layer — Simulate Antigravity MCP client calls
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestMCPToolSmoke:
    """Simulate MCP tool calls as Antigravity would make them."""

    @pytest.fixture(autouse=True)
    def _setup_mcp(self, tmp_path):
        """Configure MCPServiceManager per existing test pattern."""
        from memory_palace.integration.mcp_context import MCPServiceManager

        (tmp_path / "core").mkdir(exist_ok=True)
        MCPServiceManager.configure(tmp_path)
        yield
        MCPServiceManager._service = None
        MCPServiceManager._lock = None

    @pytest.mark.asyncio
    async def test_mcp_save_search_inspect(self):
        """MCP: save → search → inspect → stats."""
        from memory_palace.integration.mcp_server import (
            _impl_save_memory,
            _impl_search_memory,
            _impl_inspect_memory,
            _impl_get_stats,
        )

        # Save at LOW importance → goes to Recall tier where FTS5 can find it
        result = await _impl_save_memory(
            "Antigravity connects to Memory Palace via MCP",
            importance=0.3,
            room="general",
        )
        assert result["success"] is True
        memory_id = result["data"]["id"]

        # Search (FTS5-only Retriever searches Recall tier)
        search = await _impl_search_memory("Antigravity")
        assert search["success"] is True
        assert len(search["data"]) >= 1

        # Inspect
        inspect = await _impl_inspect_memory(memory_id)
        assert inspect["success"] is True
        assert "Antigravity" in inspect["data"]["content"]

        # Stats
        stats = await _impl_get_stats()
        assert stats["success"] is True
        assert stats["data"]["total"] >= 1

    @pytest.mark.asyncio
    async def test_mcp_error_codes(self):
        """MCP: verify uniform error codes."""
        from memory_palace.integration.mcp_server import (
            _impl_inspect_memory,
            _impl_forget_memory,
        )

        # NOT_FOUND
        r = await _impl_inspect_memory("nonexistent-id")
        assert r["success"] is False
        assert r["code"] == "NOT_FOUND"

        r2 = await _impl_forget_memory("nonexistent-id")
        assert r2["success"] is False

    @pytest.mark.asyncio
    async def test_mcp_health_and_metrics(self):
        """MCP: health + metrics after operations."""
        from memory_palace.integration.mcp_server import (
            _impl_save_memory,
            _impl_get_health,
            _impl_get_metrics,
        )

        for i in range(3):
            await _impl_save_memory(f"MCP metric test {i}", importance=0.5)

        # Health
        health = await _impl_get_health()
        assert health["success"] is True
        assert "overall" in health["data"]

        # Metrics
        metrics = await _impl_get_metrics()
        assert metrics["success"] is True
        assert metrics["data"]["total_saves"] >= 3

    @pytest.mark.asyncio
    async def test_mcp_context_compilation(self):
        """MCP: context compilation returns structured text."""
        from memory_palace.integration.mcp_server import (
            _impl_save_memory,
            _impl_get_context,
        )

        await _impl_save_memory("用户是 AI 工程师", importance=0.9)
        await _impl_save_memory("用户偏好 Python", importance=0.8)

        # _impl_get_context returns str directly (not dict)
        ctx = await _impl_get_context("AI 工程师")
        assert isinstance(ctx, str)
        assert len(ctx) > 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 3: Sleep-time Scheduler — Auto-trigger curate
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestSchedulerSmoke:
    """Test sleep-time compute auto-trigger."""

    @pytest.fixture
    def mock_llm(self):
        """Multi-response MockLLM for curator pipeline."""
        from tests.conftest import MockLLM

        return MockLLM(responses=[
            # Extract
            json.dumps([
                {"content": "Test fact", "importance": 0.5, "tags": []},
            ]),
            # Reconcile
            '{"action": "ADD", "target_id": null, "reason": "new"}',
            # Reflect
            json.dumps([{"content": "Insight", "source_ids": []}]),
        ])

    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self, tmp_path, mock_llm):
        """Scheduler starts → runs → stops cleanly."""
        from memory_palace.service.memory_service import MemoryService
        from memory_palace.service.curator import CuratorService
        from memory_palace.service.scheduler import SleepTimeScheduler

        (tmp_path / "core").mkdir(exist_ok=True)

        svc = MemoryService(data_dir=tmp_path, llm=mock_llm)
        for i in range(3):
            svc.save(f"Scheduler test {i}", importance=0.5)

        curator = CuratorService(data_dir=tmp_path, llm=mock_llm)

        scheduler = SleepTimeScheduler(
            curator_service=curator,
            check_interval=0.1,
            min_interval=0,
        )

        await scheduler.start()
        assert scheduler.is_running is True

        await asyncio.sleep(0.4)

        await scheduler.stop()
        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_scheduler_cooldown_works(self, tmp_path, mock_llm):
        """Scheduler with long cooldown runs at most once."""
        from memory_palace.service.memory_service import MemoryService
        from memory_palace.service.curator import CuratorService
        from memory_palace.service.scheduler import SleepTimeScheduler

        (tmp_path / "core").mkdir(exist_ok=True)

        svc = MemoryService(data_dir=tmp_path, llm=mock_llm)
        svc.save("Cooldown test", importance=0.5)

        curator = CuratorService(data_dir=tmp_path, llm=mock_llm)

        scheduler = SleepTimeScheduler(
            curator_service=curator,
            check_interval=0.05,
            min_interval=999,  # 999s cooldown
        )

        await scheduler.start()
        await asyncio.sleep(0.3)
        await scheduler.stop()

        assert scheduler.stats["trigger_count"] <= 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TEST 4: Context Compilation — Full pipeline
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class _MockRetriever:
    """Minimal HybridRetriever mock (mirrors test_context_compiler.py)."""

    def __init__(self, results=None):
        self._results = results or []

    async def search(self, query, top_k=5, **kw):
        return self._results[:top_k]


class TestContextCompilationSmoke:
    """Test context compiler produces Antigravity-ready output."""

    @pytest.mark.asyncio
    async def test_context_with_data(self, tmp_path):
        """Save data → compile context → verify output."""
        from memory_palace.service.memory_service import MemoryService
        from memory_palace.service.context_compiler import ContextCompiler

        (tmp_path / "core").mkdir(exist_ok=True)

        svc = MemoryService(data_dir=tmp_path)

        svc.save("用户是一名 AI 工程师", importance=0.9)
        svc.save("用户使用 Python 和 TypeScript", importance=0.85)
        svc.save("上次对话讨论了 LLM 架构", importance=0.3)

        # MockRetriever since no ArchivalStore/Embedding in test env
        compiler = ContextCompiler(
            memory_service=svc,
            retriever=_MockRetriever(),
        )

        context = await compiler.compile(query="AI 工程师")
        assert isinstance(context, str)
        assert len(context) > 0
        # Core items should appear in [CORE MEMORY] section
        assert "[CORE MEMORY]" in context

    @pytest.mark.asyncio
    async def test_context_empty_state(self, tmp_path):
        """Compile context with no data — should not crash."""
        from memory_palace.service.memory_service import MemoryService
        from memory_palace.service.context_compiler import ContextCompiler

        (tmp_path / "core").mkdir(exist_ok=True)

        svc = MemoryService(data_dir=tmp_path)

        compiler = ContextCompiler(
            memory_service=svc,
            retriever=_MockRetriever(),
        )

        context = await compiler.compile(query="anything")
        assert isinstance(context, str)

    @pytest.mark.asyncio
    async def test_context_via_mcp(self, tmp_path):
        """Context compilation through MCP layer."""
        from memory_palace.integration.mcp_context import MCPServiceManager
        from memory_palace.integration.mcp_server import (
            _impl_save_memory,
            _impl_get_context,
        )

        (tmp_path / "core").mkdir(exist_ok=True)
        MCPServiceManager.configure(tmp_path)

        try:
            await _impl_save_memory("MCP context item", importance=0.9)

            # _impl_get_context returns str directly
            ctx = await _impl_get_context("context item")
            assert isinstance(ctx, str)
            assert len(ctx) > 0
        finally:
            MCPServiceManager._service = None
            MCPServiceManager._lock = None
