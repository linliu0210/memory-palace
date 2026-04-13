"""MCP E2E Tests — End-to-end testing of MCP Server tools.

Tests the full MCP tool chain: save → search → update → forget → curate.
All tests use MCPServiceManager with tmp_path isolation and MockLLM.

Ref: TASK_R20, CONVENTIONS_V10.md §7
"""

from __future__ import annotations

import pytest

from memory_palace.integration.mcp_context import MCPServiceManager
from memory_palace.integration.mcp_server import (
    _impl_forget_memory,
    _impl_get_audit_log,
    _impl_get_context,
    _impl_get_health,
    _impl_get_stats,
    _impl_save_memory,
    _impl_search_memory,
    _impl_update_memory,
)


@pytest.fixture(autouse=True)
def _setup_mcp(tmp_path):
    """Configure MCPServiceManager with temp directory for each test."""
    (tmp_path / "core").mkdir(exist_ok=True)
    MCPServiceManager.configure(tmp_path)
    yield
    # Reset singleton
    MCPServiceManager._service = None
    MCPServiceManager._lock = None


class TestFullMCPLifecycle:
    """MCP Client: save → search → update → forget → curate → verify."""

    @pytest.mark.asyncio
    async def test_full_mcp_lifecycle(self):
        """Complete lifecycle through MCP tool implementations."""
        # 1. Save (importance 0.5 → recall tier, searchable via FTS5)
        result = await _impl_save_memory(
            content="用户喜欢Python编程",
            importance=0.5,
            room="preferences",
            tags="python,coding",
        )
        assert result["success"] is True
        saved = result["data"]
        memory_id = saved["id"]

        # 2. Search
        result = await _impl_search_memory(query="Python", top_k=5)
        assert result["success"] is True
        assert len(result["data"]) >= 1
        assert any("Python" in item["content"] for item in result["data"])

        # 3. Update
        result = await _impl_update_memory(
            memory_id=memory_id,
            new_content="用户精通Python编程",
            reason="upgrade",
        )
        assert result["success"] is True
        new_id = result["data"]["id"]
        assert new_id != memory_id
        assert result["data"]["version"] > 1

        # 4. Forget
        result = await _impl_forget_memory(memory_id=new_id, reason="test cleanup")
        assert result["success"] is True

        # 5. Verify forget succeeded by inspecting
        from memory_palace.integration.mcp_server import _impl_inspect_memory

        result = await _impl_inspect_memory(new_id)
        # Forgotten items should not be found or have pruned status
        if result["success"]:
            assert result["data"]["status"] == "pruned"


class TestMCPContextCompilation:
    """save → get_context → verify format."""

    @pytest.mark.asyncio
    async def test_mcp_context_compilation(self):
        """Save items then compile context with expected sections."""
        await _impl_save_memory(content="核心偏好：深色模式", importance=0.9, room="preferences")
        await _impl_save_memory(content="最近在学Rust", importance=0.5, room="skills")

        context = await _impl_get_context(query="偏好", top_k=5)
        # Context should be a formatted string with section markers
        assert isinstance(context, str)
        assert len(context) > 0
        # Should contain at least one of the saved items' content
        assert "深色模式" in context or "Rust" in context


class TestMCPHealthAndStats:
    """save → get_health → verify 5 dimensions → get_stats → verify counts."""

    @pytest.mark.asyncio
    async def test_mcp_health_and_stats(self):
        """Health and stats endpoints return correct structure."""
        # Save a few items
        await _impl_save_memory(content="记忆一", importance=0.5)
        await _impl_save_memory(content="记忆二", importance=0.6)
        await _impl_save_memory(content="记忆三", importance=0.7)

        # Health check — 5 dimensions
        health = await _impl_get_health()
        assert health["success"] is True
        data = health["data"]
        for dim in ("freshness", "efficiency", "coverage", "diversity", "coherence"):
            assert dim in data, f"Missing health dimension: {dim}"
        assert "overall" in data

        # Stats check
        stats = await _impl_get_stats()
        assert stats["success"] is True
        assert stats["data"]["total"] >= 3


class TestMCPAuditTrail:
    """save → update → forget → get_audit_log → verify operation chain."""

    @pytest.mark.asyncio
    async def test_mcp_audit_trail(self):
        """Audit log captures the full save→update→forget chain."""
        # Save
        result = await _impl_save_memory(content="审计测试记忆", importance=0.5)
        memory_id = result["data"]["id"]

        # Update
        result = await _impl_update_memory(
            memory_id=memory_id,
            new_content="更新后的审计测试",
            reason="audit test",
        )
        new_id = result["data"]["id"]

        # Forget
        await _impl_forget_memory(memory_id=new_id, reason="audit test cleanup")

        # Check audit log
        entries = await _impl_get_audit_log(last_n=50)
        assert isinstance(entries, list)
        assert len(entries) >= 3

        # Verify the operation chain
        actions = [e["action"] for e in entries]
        assert "create" in actions
        assert "update" in actions
        # forget is logged as "prune" in the audit system
        assert "prune" in actions


class TestMCPErrorHandling:
    """Error handling for edge cases."""

    @pytest.mark.asyncio
    async def test_forget_nonexistent_id(self):
        """Forget a non-existent ID returns NOT_FOUND with correct format."""
        result = await _impl_forget_memory(
            memory_id="nonexistent-id-12345", reason="test"
        )
        assert result["success"] is False
        assert result["code"] == "NOT_FOUND"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_inspect_nonexistent_id(self):
        """Inspect a non-existent ID returns NOT_FOUND."""
        from memory_palace.integration.mcp_server import _impl_inspect_memory

        result = await _impl_inspect_memory(memory_id="nonexistent-id-12345")
        assert result["success"] is False
        assert result["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_save_invalid_importance(self):
        """Save with out-of-range importance returns VALIDATION error."""
        result = await _impl_save_memory(content="test", importance=2.0)
        assert result["success"] is False
        assert result["code"] == "VALIDATION"

    @pytest.mark.asyncio
    async def test_search_invalid_top_k(self):
        """Search with out-of-range top_k returns VALIDATION error."""
        result = await _impl_search_memory(query="test", top_k=0)
        assert result["success"] is False
        assert result["code"] == "VALIDATION"
