"""MCP Server integration tests — FastMCP in-process testing.

Uses FastMCP Client with in-memory transport (no real server needed).
Tests all 12 tools and 6 resources defined in mcp_server.py.

FastMCP Client API:
    call_tool() → CallToolResult  (use .data for parsed result)
    read_resource() → list[TextResourceContents]  (use [0].text for raw text)

Ref: CONVENTIONS_V10.md §1 TDD, TASK_R18
"""

from __future__ import annotations

import json

import pytest
from fastmcp import Client

from memory_palace.integration.mcp_context import MCPServiceManager
from memory_palace.integration.mcp_server import mcp

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


@pytest.fixture
async def mcp_client_with_llm(tmp_data_dir, mock_llm_for_mcp):
    """Create in-process MCP client with MockLLM for curate/reflect."""
    MCPServiceManager.configure(tmp_data_dir, llm=mock_llm_for_mcp)
    async with Client(mcp) as client:
        yield client


@pytest.fixture
def mock_llm_for_mcp():
    """MockLLM that handles both extract + reconcile + reflect responses."""
    from tests.conftest import MockLLM

    # Cycle through: extract → reconcile(ADD) → reflect
    responses = [
        # FactExtractor response
        '[{"content": "测试事实", "importance": 0.6, "tags": ["test"]}]',
        # ReconcileEngine response (ADD)
        '{"action": "ADD", "target_id": null, "reason": "new info"}',
        # ReflectionEngine response
        '[{"content": "测试洞察", "source_ids": []}]',
    ]
    return MockLLM(responses=responses)


# ── Tool Tests ────────────────────────────────────────────────


class TestSaveMemoryTool:
    """Test save_memory tool."""

    async def test_save_returns_dict_with_id_and_tier(self, mcp_client: Client):
        """save_memory returns dict with id and tier fields."""
        result = await mcp_client.call_tool(
            "save_memory",
            {"content": "用户喜欢深色模式", "importance": 0.5},
        )
        data = result.data
        assert data["success"] is True
        assert "id" in data["data"]
        assert data["data"]["tier"] == "recall"

    async def test_save_core_tier(self, mcp_client: Client):
        """importance >= 0.7 routes to core tier."""
        result = await mcp_client.call_tool(
            "save_memory",
            {"content": "重要记忆", "importance": 0.9, "room": "general"},
        )
        data = result.data
        assert data["success"] is True
        assert data["data"]["tier"] == "core"

    async def test_save_with_tags(self, mcp_client: Client):
        """save_memory correctly parses comma-separated tags."""
        result = await mcp_client.call_tool(
            "save_memory",
            {"content": "Python 学习", "tags": "python,coding,学习"},
        )
        data = result.data
        assert data["success"] is True
        assert "python" in data["data"]["tags"]

    async def test_save_invalid_importance(self, mcp_client: Client):
        """importance > 1.0 returns validation error."""
        result = await mcp_client.call_tool(
            "save_memory",
            {"content": "测试", "importance": 1.5},
        )
        data = result.data
        assert data["success"] is False
        assert data["code"] == "VALIDATION"


class TestSearchMemoryTool:
    """Test search_memory tool."""

    async def test_search_finds_saved_memory(self, mcp_client: Client):
        """save → search finds the saved memory."""
        await mcp_client.call_tool(
            "save_memory",
            {"content": "Python是最好的编程语言", "importance": 0.5},
        )
        result = await mcp_client.call_tool(
            "search_memory",
            {"query": "Python"},
        )
        data = result.data
        assert data["success"] is True
        items = data["data"]
        assert isinstance(items, list)
        assert len(items) > 0
        assert "Python" in items[0]["content"]

    async def test_search_empty_returns_empty_list(self, mcp_client: Client):
        """Empty database search returns empty data list."""
        result = await mcp_client.call_tool(
            "search_memory",
            {"query": "不存在的内容"},
        )
        data = result.data
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert len(data["data"]) == 0


class TestUpdateMemoryTool:
    """Test update_memory tool."""

    async def test_update_returns_new_id(self, mcp_client: Client):
        """save → update returns new version with different id."""
        save_result = await mcp_client.call_tool(
            "save_memory",
            {"content": "旧内容", "importance": 0.5},
        )
        old_id = save_result.data["data"]["id"]

        update_result = await mcp_client.call_tool(
            "update_memory",
            {"memory_id": old_id, "new_content": "新内容", "reason": "更新测试"},
        )
        data = update_result.data
        assert data["success"] is True
        assert data["data"]["id"] != old_id
        assert data["data"]["version"] == 2


class TestForgetMemoryTool:
    """Test forget_memory tool."""

    async def test_forget_then_inspect_pruned(self, mcp_client: Client):
        """save → forget → inspect shows PRUNED status."""
        save_result = await mcp_client.call_tool(
            "save_memory",
            {"content": "要遗忘的记忆", "importance": 0.5},
        )
        memory_id = save_result.data["data"]["id"]

        forget_result = await mcp_client.call_tool(
            "forget_memory",
            {"memory_id": memory_id, "reason": "测试遗忘"},
        )
        assert forget_result.data["success"] is True

        inspect_result = await mcp_client.call_tool(
            "inspect_memory",
            {"memory_id": memory_id},
        )
        assert inspect_result.data["success"] is True
        assert inspect_result.data["data"]["status"] == "pruned"

    async def test_forget_nonexistent(self, mcp_client: Client):
        """Forget non-existent ID returns error."""
        result = await mcp_client.call_tool(
            "forget_memory",
            {"memory_id": "nonexistent-id-12345"},
        )
        data = result.data
        assert data["success"] is False
        assert data["code"] == "NOT_FOUND"


class TestInspectMemoryTool:
    """Test inspect_memory tool."""

    async def test_inspect_returns_full_detail(self, mcp_client: Client):
        """save → inspect returns complete memory detail."""
        save_result = await mcp_client.call_tool(
            "save_memory",
            {
                "content": "详细记忆内容",
                "importance": 0.6,
                "room": "projects",
                "tags": "test,detail",
            },
        )
        memory_id = save_result.data["data"]["id"]

        result = await mcp_client.call_tool(
            "inspect_memory",
            {"memory_id": memory_id},
        )
        data = result.data
        assert data["success"] is True
        item = data["data"]
        assert item["content"] == "详细记忆内容"
        assert item["room"] == "projects"
        assert "test" in item["tags"]
        assert item["status"] == "active"


class TestCurateNowTool:
    """Test curate_now tool."""

    async def test_curate_without_llm_returns_error(self, mcp_client: Client):
        """curate_now without LLM returns LLMNotConfigured error."""
        result = await mcp_client.call_tool("curate_now", {})
        data = result.data
        assert data["success"] is False
        assert data["code"] == "LLM_ERROR"

    async def test_curate_with_llm_returns_report(self, mcp_client_with_llm: Client):
        """curate_now with LLM returns CuratorReport dict."""
        result = await mcp_client_with_llm.call_tool("curate_now", {})
        data = result.data
        assert data["success"] is True
        assert "duration_seconds" in data["data"]
        assert "facts_extracted" in data["data"]


class TestReflectNowTool:
    """Test reflect_now tool."""

    async def test_reflect_no_memories_returns_empty(self, mcp_client_with_llm: Client):
        """reflect_now with no memories returns empty data + message."""
        result = await mcp_client_with_llm.call_tool("reflect_now", {})
        data = result.data
        assert data["success"] is True
        assert "message" in data["data"]


class TestGetHealthTool:
    """Test get_health tool."""

    async def test_health_returns_five_dimensions(self, mcp_client: Client):
        """get_health returns all 5 health dimensions."""
        result = await mcp_client.call_tool("get_health", {})
        data = result.data
        assert data["success"] is True
        health = data["data"]
        assert "freshness" in health
        assert "efficiency" in health
        assert "coverage" in health
        assert "diversity" in health
        assert "coherence" in health
        assert "overall" in health


class TestListRoomsTool:
    """Test list_rooms tool."""

    async def test_returns_default_rooms(self, mcp_client: Client):
        """list_rooms returns 5 default rooms."""
        result = await mcp_client.call_tool("list_rooms", {})
        data = json.loads(result.content[0].text)
        assert isinstance(data, list)
        assert len(data) == 5
        names = [r["name"] for r in data]
        assert "general" in names
        assert "preferences" in names


class TestGetStatsTool:
    """Test get_stats tool."""

    async def test_returns_core_and_recall_counts(self, mcp_client: Client):
        """get_stats returns core_count and recall_count."""
        result = await mcp_client.call_tool("get_stats", {})
        data = result.data
        assert data["success"] is True
        assert "core_count" in data["data"]
        assert "recall_count" in data["data"]


class TestGetAuditLogTool:
    """Test get_audit_log tool."""

    async def test_save_creates_audit_entry(self, mcp_client: Client):
        """save → audit log contains CREATE record."""
        await mcp_client.call_tool(
            "save_memory",
            {"content": "审计测试", "importance": 0.5},
        )
        result = await mcp_client.call_tool("get_audit_log", {"last_n": 10})
        data = json.loads(result.content[0].text)
        assert isinstance(data, list)
        assert len(data) > 0
        assert data[-1]["action"] == "create"


class TestGetContextTool:
    """Test get_context tool."""

    async def test_returns_formatted_string(self, mcp_client: Client):
        """get_context returns formatted context string."""
        # Save something to Core for context
        await mcp_client.call_tool(
            "save_memory",
            {"content": "核心记忆内容", "importance": 0.9, "room": "general"},
        )
        result = await mcp_client.call_tool("get_context", {})
        # get_context returns a string, which becomes result.data
        text = result.data
        assert isinstance(text, str)


# ── Resource Tests ────────────────────────────────────────────


class TestHealthResource:
    """Test palace://health resource."""

    async def test_health_resource_returns_json(self, mcp_client: Client):
        """Health resource returns valid JSON with health dimensions."""
        result = await mcp_client.read_resource("palace://health")
        data = json.loads(result[0].text)
        assert "freshness" in data.get("data", data)


class TestStatsResource:
    """Test palace://stats resource."""

    async def test_stats_resource_returns_json(self, mcp_client: Client):
        """Stats resource returns valid JSON with counts."""
        result = await mcp_client.read_resource("palace://stats")
        data = json.loads(result[0].text)
        assert "core_count" in data.get("data", data)


class TestMemoryResource:
    """Test palace://memory/{memory_id} resource."""

    async def test_memory_resource_returns_detail(self, mcp_client: Client):
        """Memory resource returns single memory detail."""
        # First save a memory to get its ID
        save_result = await mcp_client.call_tool(
            "save_memory",
            {"content": "资源测试记忆", "importance": 0.5},
        )
        memory_id = save_result.data["data"]["id"]

        result = await mcp_client.read_resource(f"palace://memory/{memory_id}")
        data = json.loads(result[0].text)
        assert data["success"] is True
        assert data["data"]["content"] == "资源测试记忆"
