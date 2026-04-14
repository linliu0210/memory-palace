"""MCP Concurrent Safety tests — R19 concurrency + error handling.

Tests asyncio.Lock-based write concurrency, SQLite WAL mode,
input validation, and standardized error format.

Ref: CONVENTIONS_V10.md §1 TDD, TASK_R19
"""

from __future__ import annotations

import asyncio

import pytest
from fastmcp import Client

from memory_palace.integration.mcp_context import MCPServiceManager
from memory_palace.integration.mcp_server import mcp
from memory_palace.store.recall_store import RecallStore

# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture(autouse=True)
async def _reset_manager():
    """Reset MCPServiceManager state between tests."""
    yield
    await MCPServiceManager.shutdown()


@pytest.fixture
async def mcp_client(tmp_data_dir):
    """Create in-process MCP client with temp data dir."""
    MCPServiceManager.configure(tmp_data_dir)
    async with Client(mcp) as client:
        yield client


# ── Concurrency Tests ─────────────────────────────────────────


class TestConcurrentSaves:
    """Test concurrent save operations."""

    async def test_concurrent_saves(self, mcp_client: Client):
        """asyncio.gather parallel save 10 items — all succeed, count correct."""
        tasks = [
            mcp_client.call_tool(
                "save_memory",
                {"content": f"并发记忆 {i}", "importance": 0.5},
            )
            for i in range(10)
        ]
        results = await asyncio.gather(*tasks)

        for r in results:
            assert r.data["success"] is True

        # Verify total count
        stats = await mcp_client.call_tool("get_stats", {})
        assert stats.data["data"]["recall_count"] == 10


class TestConcurrentSearchDuringSave:
    """Test concurrent read/write doesn't crash."""

    async def test_concurrent_search_during_save(self, mcp_client: Client):
        """Save and search concurrently — no crash."""
        # Pre-populate one item so search has something to match
        await mcp_client.call_tool(
            "save_memory",
            {"content": "预存记忆数据", "importance": 0.5},
        )

        save_tasks = [
            mcp_client.call_tool(
                "save_memory",
                {"content": f"写入记忆 {i}", "importance": 0.4},
            )
            for i in range(5)
        ]
        search_tasks = [
            mcp_client.call_tool(
                "search_memory",
                {"query": "记忆"},
            )
            for _ in range(5)
        ]

        results = await asyncio.gather(*save_tasks, *search_tasks)

        # All should succeed — no crashes
        for r in results:
            data = r.data
            assert data["success"] is True


class TestConcurrentCurateDedup:
    """Test concurrent curate triggers."""

    async def test_concurrent_curate_dedup(self, mcp_client: Client):
        """Two concurrent curate calls — both return (no LLM so both error), no crash."""
        tasks = [
            mcp_client.call_tool("curate_now", {}),
            mcp_client.call_tool("curate_now", {}),
        ]
        results = await asyncio.gather(*tasks)

        # Both should return LLM_ERROR (no LLM configured) — not crash
        for r in results:
            data = r.data
            assert data["success"] is False
            assert data["code"] == "LLM_ERROR"


class TestConcurrentUpdateSameMemory:
    """Test concurrent updates to the same memory."""

    async def test_concurrent_update_same_memory(self, mcp_client: Client):
        """Concurrent updates to same memory — both complete without crash."""
        save_result = await mcp_client.call_tool(
            "save_memory",
            {"content": "原始内容", "importance": 0.5},
        )
        memory_id = save_result.data["data"]["id"]

        tasks = [
            mcp_client.call_tool(
                "update_memory",
                {
                    "memory_id": memory_id,
                    "new_content": f"并发更新 {i}",
                    "reason": f"test {i}",
                },
            )
            for i in range(2)
        ]
        results = await asyncio.gather(*tasks)

        # First update succeeds; second may fail (old ID superseded) — but no crash
        success_count = sum(1 for r in results if r.data["success"])
        assert success_count >= 1


# ── SQLite WAL Test ───────────────────────────────────────────


class TestSQLiteWAL:
    """Verify SQLite WAL mode is enabled."""

    def test_sqlite_wal_mode(self, tmp_data_dir):
        """RecallStore sets journal_mode=WAL on init."""
        store = RecallStore(tmp_data_dir)
        row = store._conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0] == "wal"


# ── Validation Tests ──────────────────────────────────────────


class TestValidationImportanceRange:
    """Test importance range validation."""

    async def test_importance_above_range(self, mcp_client: Client):
        """importance=1.5 returns VALIDATION error."""
        result = await mcp_client.call_tool(
            "save_memory",
            {"content": "测试", "importance": 1.5},
        )
        data = result.data
        assert data["success"] is False
        assert data["code"] == "VALIDATION"
        assert "importance" in data["error"]

    async def test_importance_below_range(self, mcp_client: Client):
        """importance=-0.1 returns VALIDATION error."""
        result = await mcp_client.call_tool(
            "save_memory",
            {"content": "测试", "importance": -0.1},
        )
        data = result.data
        assert data["success"] is False
        assert data["code"] == "VALIDATION"


class TestValidationRoom:
    """Test room validation."""

    async def test_invalid_room_falls_back_to_general(self, mcp_client: Client):
        """Unknown room falls back to 'general'."""
        result = await mcp_client.call_tool(
            "save_memory",
            {"content": "测试房间", "importance": 0.5, "room": "nonexistent_room"},
        )
        data = result.data
        assert data["success"] is True
        assert data["data"]["room"] == "general"


class TestErrorFormatConsistency:
    """Test all error responses contain success, error, code fields."""

    async def test_not_found_format(self, mcp_client: Client):
        """NOT_FOUND error has success, error, code."""
        result = await mcp_client.call_tool(
            "inspect_memory",
            {"memory_id": "nonexistent-id"},
        )
        data = result.data
        assert "success" in data
        assert "error" in data
        assert "code" in data
        assert data["success"] is False
        assert data["code"] == "NOT_FOUND"

    async def test_validation_error_format(self, mcp_client: Client):
        """VALIDATION error has success, error, code."""
        result = await mcp_client.call_tool(
            "save_memory",
            {"content": "x", "importance": 2.0},
        )
        data = result.data
        assert "success" in data
        assert "error" in data
        assert "code" in data
        assert data["success"] is False
        assert data["code"] == "VALIDATION"

    async def test_forget_not_found_format(self, mcp_client: Client):
        """forget NOT_FOUND has success, error, code."""
        result = await mcp_client.call_tool(
            "forget_memory",
            {"memory_id": "does-not-exist"},
        )
        data = result.data
        assert "success" in data
        assert "error" in data
        assert "code" in data
        assert data["success"] is False
        assert data["code"] == "NOT_FOUND"

    async def test_search_validation_format(self, mcp_client: Client):
        """top_k=0 returns VALIDATION with correct fields."""
        result = await mcp_client.call_tool(
            "search_memory",
            {"query": "test", "top_k": 0},
        )
        data = result.data
        assert "success" in data
        assert "error" in data
        assert "code" in data
        assert data["success"] is False
        assert data["code"] == "VALIDATION"
