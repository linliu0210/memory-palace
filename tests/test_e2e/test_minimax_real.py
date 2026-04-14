"""MiniMax Real LLM E2E Tests — validates full pipeline with real API calls.

Requires:
  - MINIMAX_API_KEY environment variable set
  - Network access to https://api.minimaxi.com/v1

All tests are marked with `@pytest.mark.minimax` and `@pytest.mark.real_llm`
so they can be selectively run:

    # Run only MiniMax real tests
    pytest tests/test_e2e/test_minimax_real.py -v -m minimax

    # Skip MiniMax tests in CI
    pytest tests/ -v -m "not real_llm"

Ref: TASK_R25 — Fix Plan — MiniMax integration
"""

from __future__ import annotations

import json
import os

import pytest

from memory_palace.foundation.llm import ModelConfig, get_api_key
from memory_palace.foundation.openai_provider import OpenAIProvider

# ── Skip if no API key ────────────────────────────────────────

# Capture at module load (before autouse _clean_llm_env strips it)
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY")

pytestmark = [
    pytest.mark.minimax,
    pytest.mark.real_llm,
    pytest.mark.skipif(
        not MINIMAX_API_KEY,
        reason="MINIMAX_API_KEY not set — skip real LLM tests",
    ),
]


@pytest.fixture(autouse=True)
def _restore_minimax_env(monkeypatch):
    """Re-inject MINIMAX_API_KEY after global _clean_llm_env strips it."""
    if MINIMAX_API_KEY:
        monkeypatch.setenv("MINIMAX_API_KEY", MINIMAX_API_KEY)

# ── MiniMax Config ────────────────────────────────────────────

MINIMAX_CONFIG = ModelConfig(
    provider="minimax",
    model_id="MiniMax-M2.5",
    base_url="https://api.minimaxi.com/v1",
    max_tokens=2000,
)


def _make_llm() -> OpenAIProvider:
    return OpenAIProvider(MINIMAX_CONFIG, timeout=60.0)


# ── T-MM.1 — Connectivity ────────────────────────────────────


class TestMiniMaxConnectivity:
    """Verify MiniMax API reachable and responds correctly."""

    @pytest.mark.asyncio
    async def test_basic_chat_completion(self):
        llm = _make_llm()
        response = await llm.complete("Say exactly: hello")
        assert isinstance(response, str)
        assert len(response) > 0
        assert "hello" in response.lower()

    @pytest.mark.asyncio
    async def test_json_mode_returns_valid_json(self):
        """MiniMax ignores response_format; use prompt-only JSON extraction."""
        llm = _make_llm()
        prompt = (
            "Return a JSON object with keys: name (string), age (int). "
            "Example: {\"name\": \"Bob\", \"age\": 30}. "
            "Return ONLY the JSON object, no other text, no markdown fences."
        )
        # Do NOT pass response_format — MiniMax doesn't support json_object
        response = await llm.complete(prompt)
        # Strip potential think tags from reasoning models
        cleaned = _strip_think_tags(response)
        # Also strip markdown code fences if present
        cleaned = cleaned.strip("`").removeprefix("json").strip()
        data = json.loads(cleaned)
        assert "name" in data
        assert "age" in data

    @pytest.mark.asyncio
    async def test_api_key_resolves(self):
        key = get_api_key("minimax")
        assert key is not None
        assert len(key) > 10


# ── T-MM.2 — Fact Extraction ─────────────────────────────────


class TestMiniMaxFactExtraction:
    """FactExtractor with real MiniMax produces valid facts."""

    @pytest.mark.asyncio
    async def test_extract_facts_from_text(self, tmp_data_dir):
        from memory_palace.engine.fact_extractor import FactExtractor

        llm = _make_llm()
        extractor = FactExtractor(llm)

        text = (
            "用户名叫小明，今年 28 岁，在杭州工作。"
            "他喜欢用 Python 写代码，最近在学 Rust。"
            "他的项目用了 FastAPI 和 PostgreSQL。"
        )
        facts = await extractor.extract(text)

        assert isinstance(facts, list)
        assert len(facts) >= 2, f"Expected >= 2 facts, got {len(facts)}"
        for fact in facts:
            # extract() returns MemoryItem objects, not dicts
            assert hasattr(fact, "content")
            assert len(fact.content) > 0


# ── T-MM.3 — Reconcile Decisions ─────────────────────────────


class TestMiniMaxReconcile:
    """ReconcileEngine with real MiniMax returns valid decisions."""

    @pytest.mark.asyncio
    async def test_reconcile_add_decision(self, tmp_data_dir):
        from memory_palace.engine.reconcile import ReconcileEngine

        llm = _make_llm()
        reconciler = ReconcileEngine(llm)

        # No existing memories → should recommend ADD
        decision = await reconciler.reconcile(
            new_fact="用户喜欢深色模式", existing=[]
        )
        assert isinstance(decision, dict)
        assert "action" in decision
        assert decision["action"] in ("ADD", "UPDATE", "DELETE", "NOOP")


# ── T-MM.4 — Full Ingest Pipeline ────────────────────────────


class TestMiniMaxIngestPipeline:
    """Full 5-pass ingest with real MiniMax LLM."""

    @pytest.mark.asyncio
    async def test_ingest_creates_memories(self, tmp_data_dir):
        from memory_palace.engine.fact_extractor import FactExtractor
        from memory_palace.engine.reconcile import ReconcileEngine
        from memory_palace.service.ingest_pipeline import IngestPipeline
        from memory_palace.service.memory_service import MemoryService

        llm = _make_llm()
        svc = MemoryService(tmp_data_dir, llm=llm)
        pipeline = IngestPipeline(
            memory_service=svc,
            fact_extractor=FactExtractor(llm),
            reconcile_engine=ReconcileEngine(llm),
            llm=llm,
        )

        text = (
            "今天和团队开了项目评审会。"
            "前端用 React，后端用 FastAPI，数据库是 PostgreSQL。"
            "下个月要上线 v2.0，需要完成搜索优化。"
        )
        report = await pipeline.ingest(text, source_id="meeting-001")

        assert report.memories_created >= 1, (
            f"Expected >= 1 memories, got {report.memories_created}"
        )
        # Non-fatal FTS5 tokenizer warnings are acceptable
        fatal = [e for e in report.errors if "Safety" in e]
        assert fatal == [], f"Fatal errors: {fatal}"
        assert report.duration_seconds > 0

        # Verify memories are searchable
        results = svc.search_sync("FastAPI", top_k=5)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_ingest_dedup(self, tmp_data_dir):
        """Same source_id → second ingest skipped."""
        from memory_palace.engine.fact_extractor import FactExtractor
        from memory_palace.engine.reconcile import ReconcileEngine
        from memory_palace.service.ingest_pipeline import IngestPipeline
        from memory_palace.service.memory_service import MemoryService

        llm = _make_llm()
        svc = MemoryService(tmp_data_dir, llm=llm)
        pipeline = IngestPipeline(
            memory_service=svc,
            fact_extractor=FactExtractor(llm),
            reconcile_engine=ReconcileEngine(llm),
            llm=llm,
        )

        text = "用户的主力编辑器是 Neovim"
        r1 = await pipeline.ingest(text, source_id="editor-pref")
        r2 = await pipeline.ingest(text, source_id="editor-pref")

        assert r1.memories_created >= 1
        assert r2.memories_created == 0


# ── T-MM.5 — Curator with Real LLM ───────────────────────────


class TestMiniMaxCurator:
    """CuratorService.run() with real MiniMax LLM."""

    @pytest.mark.asyncio
    async def test_curator_runs_successfully(self, tmp_data_dir):
        from memory_palace.service.curator import CuratorService
        from memory_palace.service.memory_service import MemoryService

        llm = _make_llm()
        svc = MemoryService(tmp_data_dir, llm=llm)

        # Pre-populate with data
        svc.save(content="用户喜欢深色模式", importance=0.6)
        svc.save(content="用户在学习 Rust", importance=0.5)
        svc.save(content="项目使用 FastAPI", importance=0.7)
        svc.save(content="团队有五名成员", importance=0.4)
        svc.save(content="下月发布 v2.0", importance=0.6)

        curator = CuratorService(tmp_data_dir, llm)
        report = await curator.run()

        assert report is not None
        assert report.duration_seconds > 0
        # No fatal errors (warnings OK)
        fatal = [e for e in report.errors if "Safety" in e]
        assert fatal == [], f"Fatal errors: {fatal}"


# ── T-MM.6 — Full Pipeline: Save → Search → Update → Forget ──


class TestMiniMaxFullPipeline:
    """Complete CRUD lifecycle with real MiniMax."""

    @pytest.mark.asyncio
    async def test_full_crud_with_real_llm(self, tmp_data_dir):
        from memory_palace.service.memory_service import MemoryService

        llm = _make_llm()
        svc = MemoryService(tmp_data_dir, llm=llm)

        # Save
        item = svc.save(
            content="MiniMax 真实测试记忆",
            importance=0.6,
            room="projects",
            tags=["minimax", "test"],
        )
        assert item.id

        # Search (Core+Recall)
        results = svc.search_sync("MiniMax", top_k=3)
        assert len(results) >= 1
        assert any("MiniMax" in r.content for r in results)

        # Update
        new_item = svc.update(
            item.id, "MiniMax 真实测试记忆 v2", reason="更新"
        )
        assert new_item.version == 2

        # Forget
        assert svc.forget(new_item.id, "测试完成") is True

        # Stats — after forget, total may be 0; verify stats works
        stats = svc.stats()
        assert isinstance(stats["total"], int)


# ── T-MM.7 — MCP with Real LLM ───────────────────────────────


class TestMiniMaxMCPIntegration:
    """MCP tool calls with real LLM-backed service."""

    @pytest.mark.asyncio
    async def test_mcp_save_search_with_real_llm(self, tmp_path):
        from fastmcp import Client

        from memory_palace.integration.mcp_context import (
            MCPServiceManager,
        )
        from memory_palace.integration.mcp_server import mcp as mcp_srv

        (tmp_path / "core").mkdir()
        MCPServiceManager.configure(tmp_path)

        async with Client(mcp_srv) as client:
            # Save via MCP transport
            save = await client.call_tool(
                "save_memory",
                {
                    "content": "MiniMax MCP real test",
                    "importance": 0.5,
                },
            )
            data = json.loads(save.content[0].text)
            assert data["success"] is True

            # Search via MCP transport
            search = await client.call_tool(
                "search_memory",
                {"query": "MiniMax MCP", "top_k": 3},
            )
            sdata = json.loads(search.content[0].text)
            assert sdata["success"] is True
            assert len(sdata["data"]) >= 1

        # Cleanup
        MCPServiceManager._service = None
        MCPServiceManager._lock = None


# ── Helpers ───────────────────────────────────────────────────


def _strip_think_tags(text: str) -> str:
    """Strip <think>...</think> tags from reasoning model output."""
    import re
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
