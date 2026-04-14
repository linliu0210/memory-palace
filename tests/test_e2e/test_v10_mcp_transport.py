"""MCP JSON-RPC Transport E2E Tests — validates full serialization chain.

Tests actual FastMCP Client ↔ Server communication via in-process
transport, verifying that @mcp.tool() decorated functions correctly
serialize/deserialize through JSON-RPC.

This is *not* testing _impl_* directly — it tests the full MCP stack.

Ref: TASK_R25 observation report — Fix 4
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastmcp import Client

from memory_palace.integration.mcp_context import MCPServiceManager
from memory_palace.integration.mcp_server import mcp


@pytest.fixture(autouse=True)
def _setup_mcp(tmp_path):
    """Configure MCPServiceManager with temp dir for each test."""
    (tmp_path / "core").mkdir(exist_ok=True)
    MCPServiceManager.configure(tmp_path)
    yield
    MCPServiceManager._service = None
    MCPServiceManager._lock = None


def _extract(result) -> dict | list | str:
    """Extract structured data from CallToolResult."""
    if hasattr(result, "structured_content") and result.structured_content:
        return result.structured_content
    # Fallback: parse first text content
    for c in result.content:
        if hasattr(c, "text"):
            return json.loads(c.text)
    return {}


class TestMCPTransportToolDiscovery:
    """Verify tool listing through transport returns all 18 tools."""

    @pytest.mark.asyncio
    async def test_list_tools_returns_18(self):
        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert len(names) >= 18
            expected = {
                "save_memory", "search_memory",
                "update_memory", "forget_memory",
                "inspect_memory", "get_health",
                "get_stats", "get_audit_log",
                "get_context", "get_metrics",
                "list_rooms", "list_personas",
                "switch_persona", "curate_now",
                "reflect_now", "ingest_document",
                "import_memories", "export_memories",
            }
            missing = expected - names
            assert not missing, f"Missing: {missing}"


class TestMCPTransportSaveSearchInspect:
    """Full JSON-RPC roundtrip: save → search → inspect."""

    @pytest.mark.asyncio
    async def test_save_returns_json_with_id(self):
        async with Client(mcp) as client:
            result = _extract(
                await client.call_tool(
                    "save_memory",
                    {"content": "transport test", "importance": 0.6},
                )
            )
            assert result["success"] is True
            assert "id" in result["data"]
            assert result["data"]["content"] == "transport test"

    @pytest.mark.asyncio
    async def test_search_returns_list(self):
        async with Client(mcp) as client:
            await client.call_tool(
                "save_memory",
                {"content": "findable item", "importance": 0.5},
            )
            result = _extract(
                await client.call_tool(
                    "search_memory",
                    {"query": "findable", "top_k": 3},
                )
            )
            assert result["success"] is True
            assert isinstance(result["data"], list)
            assert len(result["data"]) >= 1

    @pytest.mark.asyncio
    async def test_full_roundtrip(self):
        async with Client(mcp) as client:
            # Save
            save = _extract(
                await client.call_tool(
                    "save_memory",
                    {
                        "content": "roundtrip via JSON-RPC",
                        "importance": 0.5,
                        "room": "projects",
                    },
                )
            )
            mid = save["data"]["id"]

            # Inspect
            inspect = _extract(
                await client.call_tool(
                    "inspect_memory", {"memory_id": mid},
                )
            )
            assert inspect["success"] is True
            assert inspect["data"]["content"] == "roundtrip via JSON-RPC"
            assert inspect["data"]["room"] == "projects"

            # Update
            update = _extract(
                await client.call_tool(
                    "update_memory",
                    {
                        "memory_id": mid,
                        "new_content": "updated via JSON-RPC",
                    },
                )
            )
            assert update["success"] is True
            assert update["data"]["version"] == 2

            # Forget the new version
            new_id = update["data"]["id"]
            forget = _extract(
                await client.call_tool(
                    "forget_memory", {"memory_id": new_id},
                )
            )
            assert forget["success"] is True


class TestMCPTransportErrorSerialization:
    """Errors serialize correctly through JSON-RPC."""

    @pytest.mark.asyncio
    async def test_validation_error_serialized(self):
        async with Client(mcp) as client:
            result = _extract(
                await client.call_tool(
                    "save_memory",
                    {"content": "x", "importance": 1.5},
                )
            )
            assert result["success"] is False
            assert result["code"] == "VALIDATION"
            assert isinstance(result["error"], str)

    @pytest.mark.asyncio
    async def test_not_found_error_serialized(self):
        async with Client(mcp) as client:
            result = _extract(
                await client.call_tool(
                    "forget_memory",
                    {"memory_id": "nonexistent-id-xyz"},
                )
            )
            assert result["success"] is False
            assert result["code"] == "NOT_FOUND"


class TestMCPTransportHealthStatsMetrics:
    """Health, stats, metrics through full transport."""

    @pytest.mark.asyncio
    async def test_health_through_transport(self):
        async with Client(mcp) as client:
            for i in range(3):
                await client.call_tool(
                    "save_memory",
                    {"content": f"health {i}", "importance": 0.5},
                )
            result = _extract(
                await client.call_tool("get_health", {})
            )
            assert result["success"] is True
            assert "overall" in result["data"]

    @pytest.mark.asyncio
    async def test_stats_through_transport(self):
        async with Client(mcp) as client:
            await client.call_tool(
                "save_memory",
                {"content": "stats test", "importance": 0.5},
            )
            result = _extract(
                await client.call_tool("get_stats", {})
            )
            assert result["success"] is True
            assert result["data"]["total"] >= 1

    @pytest.mark.asyncio
    async def test_metrics_through_transport(self):
        async with Client(mcp) as client:
            await client.call_tool(
                "save_memory",
                {"content": "metrics test", "importance": 0.5},
            )
            result = _extract(
                await client.call_tool("get_metrics", {})
            )
            assert result["success"] is True
            assert "total_saves" in result["data"]

    @pytest.mark.asyncio
    async def test_context_through_transport(self):
        async with Client(mcp) as client:
            await client.call_tool(
                "save_memory",
                {"content": "context core", "importance": 0.9},
            )
            await client.call_tool(
                "save_memory",
                {"content": "context recall", "importance": 0.4},
            )
            result = await client.call_tool(
                "get_context", {"query": "context"}
            )
            # get_context returns str, not dict
            text = result.content[0].text if result.content else ""
            assert isinstance(text, str)
            assert len(text) > 0


class TestMCPTransportListRoomsPersonas:
    """list_rooms and list_personas through transport."""

    @pytest.mark.asyncio
    async def test_list_rooms(self):
        async with Client(mcp) as client:
            result = await client.call_tool("list_rooms", {})
            data = json.loads(result.content[0].text)
            assert isinstance(data, list)
            names = {r["name"] for r in data}
            assert "general" in names

    @pytest.mark.asyncio
    async def test_list_personas(self):
        async with Client(mcp) as client:
            result = await client.call_tool("list_personas", {})
            data = json.loads(result.content[0].text)
            assert isinstance(data, list)


class TestMCPSubprocessStdioSmoke:
    """Smoke-test the real stdio server entrypoint, not the in-process transport."""

    @pytest.mark.asyncio
    async def test_cli_serve_stdio_roundtrip(self, tmp_path):
        repo_root = Path(__file__).resolve().parents[2]
        uv_bin = shutil.which("uv")
        assert uv_bin, "uv must be available to launch the stdio MCP server"

        (tmp_path / "core").mkdir(exist_ok=True)

        config = {
            "mcpServers": {
                "memory_palace": {
                    "command": uv_bin,
                    "args": [
                        "run",
                        "--directory",
                        str(repo_root),
                        "palace",
                        "serve",
                        "--data-dir",
                        str(tmp_path),
                    ],
                }
            }
        }

        async with Client(config, init_timeout=10, timeout=20) as client:
            save = _extract(
                await client.call_tool(
                    "save_memory",
                    {
                        "content": "subprocess smoke-test 2026-04-13",
                        "importance": 0.5,
                    },
                )
            )
            assert save["success"] is True

            search = _extract(
                await client.call_tool(
                    "search_memory",
                    {"query": "2026-04-13", "top_k": 3},
                )
            )
            assert search["success"] is True
            assert any(
                item["content"] == "subprocess smoke-test 2026-04-13"
                for item in search["data"]
            )

            inspect = _extract(
                await client.call_tool(
                    "inspect_memory",
                    {"memory_id": save["data"]["id"]},
                )
            )
            assert inspect["success"] is True
            assert inspect["data"]["content"] == "subprocess smoke-test 2026-04-13"
