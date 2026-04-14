"""MCP Server — FastMCP v2 server exposing Memory Palace as MCP tools and resources.

12 Tools (side-effect operations) + 6 Resources (read-only data).
All return values are JSON-serializable dict/list, never Pydantic models.

Transport: stdio (default, for Claude Desktop integration).

Architecture:
    Tool logic lives in private _impl_* functions.
    @mcp.tool() and @mcp.resource() decorators wrap them for MCP clients.
    Resources call _impl_* directly (not the decorated FunctionTool objects).

Ref: CONVENTIONS_V10.md §7, TASK_R18, TASK_R19
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any

import structlog
from fastmcp import FastMCP

from memory_palace.integration.mcp_context import MCPServiceManager

mcp = FastMCP("MemoryPalace")


# ── R19: Error Codes ──────────────────────────────────────────

NOT_FOUND = "NOT_FOUND"
VALIDATION = "VALIDATION"
INTERNAL = "INTERNAL"
LLM_ERROR = "LLM_ERROR"


def _error(message: str, code: str) -> dict:
    """Build a standardized error response dict."""
    return {"success": False, "error": message, "code": code}


def _ok(data: Any) -> dict:
    """Build a standardized success response dict."""
    return {"success": True, "data": data}


def _configure_stdio_logging() -> None:
    """Silence non-critical structlog output for stdio MCP transport.

    stdio MCP clients expect stdout to contain protocol frames only. We also
    suppress normal structlog chatter on stderr so clients like Codex do not
    treat log noise as transport failures.
    """
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def run_stdio_server() -> None:
    """Run a stdio-safe MCP server with no banner or normal log output."""
    _configure_stdio_logging()
    mcp.run(show_banner=False, log_level="ERROR")


# ── R19: Validation Helpers ───────────────────────────────────


def _get_valid_rooms() -> set[str]:
    """Load valid room names from Config (single source of truth)."""
    from memory_palace.config import Config
    try:
        cfg = Config()
        return {r.name for r in cfg.rooms}
    except Exception:
        return {"general", "preferences", "projects", "people", "skills"}


def _validate_importance(importance: float) -> dict | None:
    """Return error dict if importance is out of [0.0, 1.0], else None."""
    if importance < 0.0 or importance > 1.0:
        return _error("importance must be between 0.0 and 1.0", VALIDATION)
    return None


def _validate_room(room: str) -> str:
    """Return room name; warn and fallback to 'general' if unknown."""
    valid = _get_valid_rooms()
    if room in valid:
        return room
    import structlog
    structlog.get_logger().warning("unknown_room_fallback", room=room, fallback="general")
    return "general"


def _validate_memory_id(memory_id: str) -> dict | None:
    """Return error dict if memory_id is empty or blank, else None."""
    if not memory_id or not memory_id.strip():
        return _error("memory_id must be a non-empty string", VALIDATION)
    return None


def _validate_top_k(top_k: int) -> dict | None:
    """Return error dict if top_k is out of [1, 100], else None."""
    if top_k < 1 or top_k > 100:
        return _error("top_k must be between 1 and 100", VALIDATION)
    return None


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


# ── Default Rooms (loaded from Config) ────────────────────


def _get_default_rooms() -> list[dict]:
    """Load room definitions from Config."""
    from memory_palace.config import Config
    try:
        cfg = Config()
        return [{"name": r.name, "description": r.description} for r in cfg.rooms]
    except Exception:
        return [
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
    err = _validate_importance(importance)
    if err:
        return err

    room = _validate_room(room)

    svc = await MCPServiceManager.get_service()
    tag_list = (
        [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    )
    item = await svc.async_save(
        content=content, importance=importance, room=room, tags=tag_list
    )
    return _ok(_serialize_item(item))


async def _impl_search_memory(
    query: str, top_k: int = 5, room: str | None = None,
) -> dict:
    """Search implementation."""
    err = _validate_top_k(top_k)
    if err:
        return err

    svc = await MCPServiceManager.get_service()
    results = await svc.search(query=query, top_k=top_k, room=room)
    return _ok([_serialize_item(item) for item in results])


async def _impl_update_memory(
    memory_id: str, new_content: str, reason: str = "update",
) -> dict:
    """Update implementation."""
    err = _validate_memory_id(memory_id)
    if err:
        return err

    svc = await MCPServiceManager.get_service()
    new_item = await svc.async_update(memory_id, new_content, reason)
    return _ok(_serialize_item(new_item))


async def _impl_forget_memory(memory_id: str, reason: str = "request") -> dict:
    """Forget implementation."""
    err = _validate_memory_id(memory_id)
    if err:
        return err

    svc = await MCPServiceManager.get_service()
    success = await svc.async_forget(memory_id, reason)
    if success:
        return _ok({"memory_id": memory_id})
    return _error(f"Memory {memory_id} not found", NOT_FOUND)


async def _impl_inspect_memory(memory_id: str) -> dict:
    """Inspect implementation."""
    err = _validate_memory_id(memory_id)
    if err:
        return err

    svc = await MCPServiceManager.get_service()
    item = svc.get_by_id(memory_id)
    if item is None:
        return _error(f"Memory {memory_id} not found", NOT_FOUND)
    return _ok(_serialize_item(item))


async def _impl_curate_now() -> dict:
    """Curate implementation."""
    svc = await MCPServiceManager.get_service()
    if svc._llm is None:
        return _error(
            "LLM not configured. Set up memory_palace.yaml with LLM settings.",
            LLM_ERROR,
        )

    from memory_palace.service.curator import CuratorService

    curator = CuratorService(svc._data_dir, svc._llm)
    report = await curator.run()
    return _ok(_serialize_report(report))


async def _impl_reflect_now() -> dict:
    """Reflect implementation."""
    svc = await MCPServiceManager.get_service()
    if svc._llm is None:
        return _error(
            "LLM not configured. Set up memory_palace.yaml with LLM settings.",
            LLM_ERROR,
        )

    from memory_palace.engine.reflection import ReflectionEngine

    engine = ReflectionEngine(svc._llm)

    # Gather recent memories for reflection
    recent = svc._recall_store.get_recent(20)
    if not recent:
        return _ok({"items": [], "message": "No memories available for reflection."})

    insights = await engine.reflect(recent)
    return _ok([_serialize_item(item) for item in insights])


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

    # R23: include operational metrics in health computation
    metrics_summary = svc.get_metrics()

    health = compute_health(core_items, recall_items, rooms_config, metrics_summary)
    result = health.model_dump()
    result["overall"] = health.overall
    return _ok(result)


async def _impl_get_metrics() -> dict:
    """Metrics implementation."""
    svc = await MCPServiceManager.get_service()
    return _ok(svc.get_metrics())


async def _impl_get_stats() -> dict:
    """Stats implementation."""
    svc = await MCPServiceManager.get_service()
    stats = svc.stats()
    return _ok(stats)


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

    # Use fully-configured retriever when archival+embedding are available,
    # otherwise degrade to FTS-only retriever.
    retriever = svc.get_hybrid_retriever()
    if retriever is None:
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
        return _error(str(exc), INTERNAL)


@mcp.tool()
async def search_memory(
    query: str,
    top_k: int = 5,
    room: str | None = None,
) -> dict:
    """Search memories using keyword matching.

    Args:
        query: Search query string.
        top_k: Maximum number of results.
        room: Optional room filter.

    Returns:
        Dict with success status and list of matching memory dicts.
    """
    try:
        return await _impl_search_memory(query, top_k, room)
    except Exception as exc:
        return _error(str(exc), INTERNAL)


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
        return _error(str(exc), INTERNAL)


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
        return _error(str(exc), INTERNAL)


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
        return _error(str(exc), INTERNAL)


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
        return _error(str(exc), INTERNAL)


@mcp.tool()
async def reflect_now() -> dict:
    """Generate higher-order insights from recent memories (requires LLM).

    Returns:
        Dict with list of generated reflection items or error.
    """
    try:
        return await _impl_reflect_now()
    except Exception as exc:
        return _error(str(exc), INTERNAL)


@mcp.tool()
async def get_health() -> dict:
    """Get 6-dimension health assessment of the Memory Palace.

    Dimensions: freshness, efficiency, coverage, diversity, coherence, operations.

    Returns:
        Health score dict with all dimensions and overall score.
    """
    try:
        return await _impl_get_health()
    except Exception as exc:
        return _error(str(exc), INTERNAL)


@mcp.tool()
async def list_rooms() -> list[dict]:
    """List all configured rooms in the Memory Palace.

    Returns:
        List of room dicts with name and description.
    """
    try:
        return _get_default_rooms()
    except Exception as exc:
        return [_error(str(exc), INTERNAL)]


@mcp.tool()
async def get_stats() -> dict:
    """Get statistics overview of the Memory Palace.

    Returns:
        Dict with core_count, recall_count, total, etc.
    """
    try:
        return await _impl_get_stats()
    except Exception as exc:
        return _error(str(exc), INTERNAL)


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
        return [_error(str(exc), INTERNAL)]


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


# ── Ingest Tool (R25) ─────────────────────────────────────────


async def _impl_ingest_document(text: str, source_id: str = "") -> dict:
    """Ingest implementation — 5-pass pipeline."""
    svc = await MCPServiceManager.get_service()
    if svc._llm is None:
        return _error(
            "LLM not configured. Set up memory_palace.yaml with LLM settings.",
            LLM_ERROR,
        )

    from memory_palace.engine.fact_extractor import FactExtractor
    from memory_palace.engine.reconcile import ReconcileEngine
    from memory_palace.service.ingest_pipeline import IngestPipeline

    extractor = FactExtractor(svc._llm)
    reconciler = ReconcileEngine(svc._llm)
    pipeline = IngestPipeline(
        memory_service=svc,
        fact_extractor=extractor,
        reconcile_engine=reconciler,
        llm=svc._llm,
        graph_store=svc._graph_store,
    )

    report = await pipeline.ingest(text, source_id=source_id)
    return {
        "total_input_chars": report.total_input_chars,
        "pass_results": report.pass_results,
        "memories_created": report.memories_created,
        "relations_created": report.relations_created,
        "duration_seconds": report.duration_seconds,
        "errors": report.errors,
    }


@mcp.tool()
async def ingest_document(text: str, source_id: str = "") -> dict:
    """5-pass intelligent document ingestion.

    Pass 1 — DIFF: skip if already processed.
    Pass 2 — EXTRACT: extract atomic facts.
    Pass 3 — MAP: assign room + importance.
    Pass 4 — LINK: discover relations (if GraphStore available).
    Pass 5 — UPDATE: reconcile & write.

    Args:
        text: Raw document text to ingest.
        source_id: Optional source identifier for deduplication tracking.

    Returns:
        Dict with ingest report (memories_created, relations_created, etc.).
    """
    try:
        return _ok(await _impl_ingest_document(text, source_id))
    except Exception as exc:
        return _error(str(exc), INTERNAL)


# ── Batch Import / Export Tools (R21) ─────────────────────────


async def _impl_import_memories(file_path: str) -> dict:
    """Import implementation."""
    from pathlib import Path

    from memory_palace.service.batch_io import BatchImporter

    svc = await MCPServiceManager.get_service()
    importer = BatchImporter(svc)
    p = Path(file_path).expanduser()

    if p.suffix == ".jsonl":
        report = await importer.import_jsonl(p)
    else:
        report = await importer.import_markdown(p)

    return {
        "total_found": report.total_found,
        "imported": report.imported,
        "skipped": report.skipped,
        "errors": report.errors,
        "duration_seconds": report.duration_seconds,
    }


def _impl_export_memories(output_path: str, fmt: str = "jsonl") -> dict:
    """Export implementation (sync — no LLM needed)."""
    import asyncio
    from pathlib import Path

    from memory_palace.service.batch_io import BatchExporter

    loop = asyncio.get_event_loop()
    svc = loop.run_until_complete(MCPServiceManager.get_service())
    exporter = BatchExporter(svc)
    p = Path(output_path).expanduser()

    if fmt == "markdown":
        report = exporter.export_markdown(p)
    else:
        report = exporter.export_jsonl(p)

    return {
        "total_exported": report.total_exported,
        "output_path": report.output_path,
        "duration_seconds": report.duration_seconds,
    }


@mcp.tool()
async def import_memories(file_path: str) -> dict:
    """从文件批量导入记忆.

    Supports .md (Markdown) and .jsonl formats.

    Args:
        file_path: Path to the import file (.md or .jsonl).

    Returns:
        Dict with import report (total_found, imported, skipped, errors).
    """
    try:
        return _ok(await _impl_import_memories(file_path))
    except FileNotFoundError as exc:
        return _error(str(exc), NOT_FOUND)
    except Exception as exc:
        return _error(str(exc), INTERNAL)


@mcp.tool()
async def export_memories(
    output_path: str, format: str = "jsonl",
) -> dict:
    """批量导出记忆.

    Args:
        output_path: Output path (directory for markdown, file for jsonl).
        format: Export format — "markdown" or "jsonl".

    Returns:
        Dict with export report (total_exported, output_path).
    """
    try:
        from pathlib import Path

        from memory_palace.service.batch_io import BatchExporter

        svc = await MCPServiceManager.get_service()
        exporter = BatchExporter(svc)
        p = Path(output_path).expanduser()

        if format == "markdown":
            report = exporter.export_markdown(p)
        else:
            report = exporter.export_jsonl(p)

        return _ok({
            "total_exported": report.total_exported,
            "output_path": report.output_path,
            "duration_seconds": report.duration_seconds,
        })
    except Exception as exc:
        return _error(str(exc), INTERNAL)


# ── Persona Tools (R22) ────────────────────────────────────


async def _impl_list_personas() -> list[dict]:
    """List all configured personas."""
    from memory_palace.config import Config
    from memory_palace.service.persona_manager import PersonaManager

    svc = await MCPServiceManager.get_service()
    yaml_path = svc._data_dir / "memory_palace.yaml"
    if yaml_path.exists():
        cfg = Config.from_yaml(yaml_path)
    else:
        cfg = Config()
    mgr = PersonaManager(cfg)
    return [
        {
            "name": p.name,
            "data_dir": p.data_dir,
            "description": p.description,
            "active": p.name == cfg.active_persona,
        }
        for p in mgr.list_personas()
    ]


async def _impl_switch_persona(name: str) -> dict:
    """Switch active persona and reconfigure MCPServiceManager."""
    from memory_palace.config import Config
    from memory_palace.service.persona_manager import PersonaManager

    svc = await MCPServiceManager.get_service()
    yaml_path = svc._data_dir / "memory_palace.yaml"
    if yaml_path.exists():
        cfg = Config.from_yaml(yaml_path)
    else:
        cfg = Config()
    mgr = PersonaManager(cfg, config_path=yaml_path)
    persona = mgr.switch(name)

    # Reconfigure MCPServiceManager with the new persona's data_dir
    from pathlib import Path

    new_dir = Path(persona.data_dir).expanduser()
    new_dir.mkdir(parents=True, exist_ok=True)
    (new_dir / "core").mkdir(exist_ok=True)
    MCPServiceManager.configure(new_dir)

    return {"switched_to": persona.name, "data_dir": persona.data_dir}


@mcp.tool()
async def list_personas() -> list[dict]:
    """List all configured persona profiles.

    Returns:
        List of persona dicts with name, data_dir, description, active flag.
    """
    try:
        return await _impl_list_personas()
    except Exception as exc:
        return [_error(str(exc), INTERNAL)]


@mcp.tool()
async def switch_persona(name: str) -> dict:
    """Switch to a different persona (isolated memory space).

    Args:
        name: Name of the persona to switch to.

    Returns:
        Dict with switched persona info or error.
    """
    try:
        return _ok(await _impl_switch_persona(name))
    except ValueError as exc:
        return _error(str(exc), NOT_FOUND)
    except Exception as exc:
        return _error(str(exc), INTERNAL)

@mcp.tool()
async def get_metrics() -> dict:
    """Get operational metrics of the Memory Palace.

    Returns:
        Dict with search_p95_ms, save_p95_ms, curator_avg_duration_s,
        growth_rate_per_day, total_searches, total_saves, total_curations.
    """
    try:
        return await _impl_get_metrics()
    except Exception as exc:
        return _error(str(exc), INTERNAL)

# ── 7 Resources ──────────────────────────────────────────
# Resources call _impl_* functions directly (not decorated FunctionTool objects).


@mcp.resource("palace://health")
async def health_resource() -> str:
    """Real-time 6-dimension health assessment."""
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
    return json.dumps(_get_default_rooms(), ensure_ascii=False)


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


@mcp.resource("palace://personas")
async def personas_resource() -> str:
    """All configured persona profiles."""
    result = await _impl_list_personas()
    return json.dumps(result, ensure_ascii=False)


@mcp.resource("palace://metrics")
async def metrics_resource() -> str:
    """Operational metrics summary."""
    result = await _impl_get_metrics()
    return json.dumps(result, ensure_ascii=False)


# ── Entry Point ──────────────────────────────────────────────


def main():
    """Run the MCP server with stdio transport."""
    run_stdio_server()
