"""MCP Server — FastMCP v2 server exposing Memory Palace as MCP tools and resources.

12 Tools (side-effect operations) + 6 Resources (read-only data).
All return values are JSON-serializable dict/list, never Pydantic models.

Transport: stdio (default, for Claude Desktop integration).

Architecture:
    Tool logic lives in private _impl_* functions.
    @mcp.tool() and @mcp.resource() decorators wrap them for MCP clients.
    Resources call _impl_* directly (not the decorated FunctionTool objects).

Ref: CONVENTIONS_V10.md §7, TASK_R18
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastmcp import FastMCP

from memory_palace.integration.mcp_context import MCPServiceManager

mcp = FastMCP("MemoryPalace")


# ── Serialization Helpers ─────────────────────────────────────


def _serialize_datetime(dt: datetime) -> str:
    """Convert datetime to ISO 8601 string."""
    return dt.isoformat()


def _serialize_item(item: Any) -> dict:
    """Convert a MemoryItem to a JSON-serializable dict.

    Handles datetime fields and enum values via model_dump(mode='json').
    """
    return item.model_dump(mode="json")


def _serialize_audit_entry(entry: Any) -> dict:
    """Convert an AuditEntry to a JSON-serializable dict."""
    return entry.model_dump(mode="json")


def _serialize_report(report: Any) -> dict:
    """Convert a CuratorReport to a JSON-serializable dict."""
    return report.model_dump(mode="json")


# ── Default Rooms (matches cli.py) ───────────────────────────

DEFAULT_ROOMS = [
    {"name": "general", "description": "未分类通用记忆"},
    {"name": "preferences", "description": "用户偏好"},
    {"name": "projects", "description": "项目知识"},
    {"name": "people", "description": "人物关系"},
    {"name": "skills", "description": "技能记忆"},
]


# ── Implementation Functions ─────────────────────────────────
# These are the actual logic; tools and resources both call these.


async def _impl_save_memory(
    content: str,
    importance: float = 0.5,
    room: str = "general",
    tags: str | None = None,
) -> dict:
    """Save implementation."""
    if importance < 0.0 or importance > 1.0:
        return {
            "success": False,
            "error": "importance must be between 0.0 and 1.0",
            "code": "ValidationError",
        }

    svc = await MCPServiceManager.get_service()
    tag_list = (
        [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    )
    item = svc.save(
        content=content, importance=importance, room=room, tags=tag_list
    )
    return {"success": True, "data": _serialize_item(item)}


async def _impl_search_memory(
    query: str, top_k: int = 5, room: str | None = None,
) -> list[dict]:
    """Search implementation."""
    svc = await MCPServiceManager.get_service()
    results = svc.search(query=query, top_k=top_k, room=room)
    return [_serialize_item(item) for item in results]


async def _impl_update_memory(
    memory_id: str, new_content: str, reason: str = "update",
) -> dict:
    """Update implementation."""
    svc = await MCPServiceManager.get_service()
    new_item = svc.update(memory_id, new_content, reason)
    return {"success": True, "data": _serialize_item(new_item)}


async def _impl_forget_memory(memory_id: str, reason: str = "request") -> dict:
    """Forget implementation."""
    svc = await MCPServiceManager.get_service()
    success = svc.forget(memory_id, reason)
    if success:
        return {"success": True, "memory_id": memory_id}
    return {
        "success": False,
        "error": f"Memory {memory_id} not found",
        "code": "NotFoundError",
    }


async def _impl_inspect_memory(memory_id: str) -> dict:
    """Inspect implementation."""
    svc = await MCPServiceManager.get_service()
    item = svc.get_by_id(memory_id)
    if item is None:
        return {
            "success": False,
            "error": f"Memory {memory_id} not found",
            "code": "NotFoundError",
        }
    return {"success": True, "data": _serialize_item(item)}


async def _impl_curate_now() -> dict:
    """Curate implementation."""
    svc = await MCPServiceManager.get_service()
    if svc._llm is None:
        return {
            "success": False,
            "error": "LLM not configured. Set up memory_palace.yaml with LLM settings.",
            "code": "LLMNotConfigured",
        }

    from memory_palace.service.curator import CuratorService

    curator = CuratorService(svc._data_dir, svc._llm)
    report = await curator.run()
    return {"success": True, "data": _serialize_report(report)}


async def _impl_reflect_now() -> dict:
    """Reflect implementation."""
    svc = await MCPServiceManager.get_service()
    if svc._llm is None:
        return {
            "success": False,
            "error": "LLM not configured. Set up memory_palace.yaml with LLM settings.",
            "code": "LLMNotConfigured",
        }

    from memory_palace.engine.reflection import ReflectionEngine

    engine = ReflectionEngine(svc._llm)

    # Gather recent memories for reflection
    recent = svc._recall_store.get_recent(20)
    if not recent:
        return {
            "success": True,
            "data": [],
            "message": "No memories available for reflection.",
        }

    insights = await engine.reflect(recent)
    return {
        "success": True,
        "data": [_serialize_item(item) for item in insights],
    }


async def _impl_get_health() -> dict:
    """Health implementation."""
    svc = await MCPServiceManager.get_service()

    from memory_palace.config import Config
    from memory_palace.engine.health import compute_health

    # Gather items from both tiers
    core_items = []
    for block in svc._core_store.list_blocks():
        core_items.extend(svc._core_store.load(block))

    recall_items = svc._recall_store.get_recent(1000)

    # Load room config
    yaml_path = svc._data_dir / "memory_palace.yaml"
    if yaml_path.exists():
        cfg = Config.from_yaml(yaml_path)
        rooms_config = cfg.rooms
    else:
        cfg = Config()
        rooms_config = cfg.rooms

    health = compute_health(core_items, recall_items, rooms_config)
    result = health.model_dump()
    result["overall"] = health.overall
    return {"success": True, "data": result}


async def _impl_get_stats() -> dict:
    """Stats implementation."""
    svc = await MCPServiceManager.get_service()
    stats = svc.stats()
    return {"success": True, "data": stats}


async def _impl_get_audit_log(last_n: int = 20) -> list[dict]:
    """Audit log implementation."""
    from memory_palace.foundation.audit_log import AuditLog

    svc = await MCPServiceManager.get_service()
    audit_log = AuditLog(svc._data_dir)
    entries = audit_log.read()

    # Return last N entries
    entries = entries[-last_n:]
    return [_serialize_audit_entry(e) for e in entries]


async def _impl_get_context(
    query: str | None = None, top_k: int = 5,
) -> str:
    """Context compilation implementation."""
    svc = await MCPServiceManager.get_service()

    from memory_palace.service.context_compiler import ContextCompiler
    from memory_palace.service.hybrid_retriever import HybridRetriever

    retriever = HybridRetriever(svc._recall_store)
    compiler = ContextCompiler(svc, retriever)
    return await compiler.compile(query=query, top_k=top_k)


# ── 12 Tools ──────────────────────────────────────────────────


@mcp.tool()
async def save_memory(
    content: str,
    importance: float = 0.5,
    room: str = "general",
    tags: str | None = None,
) -> dict:
    """Save a new memory to the Memory Palace.

    Args:
        content: Memory text content.
        importance: Importance score [0.0, 1.0].
        room: Room name for categorization.
        tags: Comma-separated tag string (e.g. "python,coding").

    Returns:
        Dict with success status and saved memory data.
    """
    try:
        return await _impl_save_memory(content, importance, room, tags)
    except Exception as exc:
        return {"success": False, "error": str(exc), "code": type(exc).__name__}


@mcp.tool()
async def search_memory(
    query: str,
    top_k: int = 5,
    room: str | None = None,
) -> list[dict]:
    """Search memories using keyword matching.

    Args:
        query: Search query string.
        top_k: Maximum number of results.
        room: Optional room filter.

    Returns:
        List of matching memory dicts, ranked by relevance.
    """
    try:
        return await _impl_search_memory(query, top_k, room)
    except Exception as exc:
        return [{"success": False, "error": str(exc), "code": type(exc).__name__}]


@mcp.tool()
async def update_memory(
    memory_id: str,
    new_content: str,
    reason: str = "update",
) -> dict:
    """Update a memory with new content (creates a new version).

    Args:
        memory_id: ID of the memory to update.
        new_content: New content text.
        reason: Reason for the update.

    Returns:
        Dict with success status and new version data.
    """
    try:
        return await _impl_update_memory(memory_id, new_content, reason)
    except Exception as exc:
        return {"success": False, "error": str(exc), "code": type(exc).__name__}


@mcp.tool()
async def forget_memory(
    memory_id: str,
    reason: str = "request",
) -> dict:
    """Soft-delete a memory (mark as pruned).

    Args:
        memory_id: ID of the memory to forget.
        reason: Reason for forgetting.

    Returns:
        Dict with success status.
    """
    try:
        return await _impl_forget_memory(memory_id, reason)
    except Exception as exc:
        return {"success": False, "error": str(exc), "code": type(exc).__name__}


@mcp.tool()
async def inspect_memory(memory_id: str) -> dict:
    """Get detailed information about a single memory.

    Args:
        memory_id: ID of the memory to inspect.

    Returns:
        Dict with memory details or error.
    """
    try:
        return await _impl_inspect_memory(memory_id)
    except Exception as exc:
        return {"success": False, "error": str(exc), "code": type(exc).__name__}


@mcp.tool()
async def curate_now() -> dict:
    """Trigger a manual curation cycle (requires LLM).

    Runs the full Curator pipeline: Gather → Extract → Reconcile →
    Reflect → Prune → HealthCheck → Report.

    Returns:
        CuratorReport dict or error if LLM not configured.
    """
    try:
        return await _impl_curate_now()
    except Exception as exc:
        return {"success": False, "error": str(exc), "code": type(exc).__name__}


@mcp.tool()
async def reflect_now() -> dict:
    """Generate higher-order insights from recent memories (requires LLM).

    Returns:
        Dict with list of generated reflection items or error.
    """
    try:
        return await _impl_reflect_now()
    except Exception as exc:
        return {"success": False, "error": str(exc), "code": type(exc).__name__}


@mcp.tool()
async def get_health() -> dict:
    """Get 5-dimension health assessment of the Memory Palace.

    Dimensions: freshness, efficiency, coverage, diversity, coherence.

    Returns:
        Health score dict with all dimensions and overall score.
    """
    try:
        return await _impl_get_health()
    except Exception as exc:
        return {"success": False, "error": str(exc), "code": type(exc).__name__}


@mcp.tool()
async def list_rooms() -> list[dict]:
    """List all configured rooms in the Memory Palace.

    Returns:
        List of room dicts with name and description.
    """
    try:
        return DEFAULT_ROOMS
    except Exception as exc:
        return [{"success": False, "error": str(exc), "code": type(exc).__name__}]


@mcp.tool()
async def get_stats() -> dict:
    """Get statistics overview of the Memory Palace.

    Returns:
        Dict with core_count, recall_count, total, etc.
    """
    try:
        return await _impl_get_stats()
    except Exception as exc:
        return {"success": False, "error": str(exc), "code": type(exc).__name__}


@mcp.tool()
async def get_audit_log(last_n: int = 20) -> list[dict]:
    """Get recent audit log entries.

    Args:
        last_n: Number of most recent entries to return.

    Returns:
        List of audit entry dicts.
    """
    try:
        return await _impl_get_audit_log(last_n)
    except Exception as exc:
        return [{"success": False, "error": str(exc), "code": type(exc).__name__}]


@mcp.tool()
async def get_context(
    query: str | None = None,
    top_k: int = 5,
) -> str:
    """Compile structured context for Agent consumption.

    Assembles [CORE MEMORY] + [RETRIEVED] + [RECENT ACTIVITY] sections.

    Args:
        query: Optional search query for retrieval section.
        top_k: Max items in the RETRIEVED section.

    Returns:
        Formatted context string with sections.
    """
    try:
        return await _impl_get_context(query, top_k)
    except Exception as exc:
        return f"Error compiling context: {exc}"


# ── 6 Resources ──────────────────────────────────────────────
# Resources call _impl_* functions directly (not decorated FunctionTool objects).


@mcp.resource("palace://health")
async def health_resource() -> str:
    """Real-time 5-dimension health assessment."""
    result = await _impl_get_health()
    return json.dumps(result, ensure_ascii=False)


@mcp.resource("palace://stats")
async def stats_resource() -> str:
    """Statistical overview of the Memory Palace."""
    result = await _impl_get_stats()
    return json.dumps(result, ensure_ascii=False)


@mcp.resource("palace://rooms")
async def rooms_resource() -> str:
    """List of all configured rooms."""
    return json.dumps(DEFAULT_ROOMS, ensure_ascii=False)


@mcp.resource("palace://context/{query}")
async def context_resource(query: str) -> str:
    """Compiled agent context for a given query."""
    return await _impl_get_context(query=query)


@mcp.resource("palace://memory/{memory_id}")
async def memory_resource(memory_id: str) -> str:
    """Single memory detail by ID."""
    result = await _impl_inspect_memory(memory_id)
    return json.dumps(result, ensure_ascii=False)


@mcp.resource("palace://audit")
async def audit_resource() -> str:
    """Recent audit log entries."""
    result = await _impl_get_audit_log()
    return json.dumps(result, ensure_ascii=False, default=str)


# ── Entry Point ──────────────────────────────────────────────


def main():
    """Run the MCP server with stdio transport."""
    mcp.run()
