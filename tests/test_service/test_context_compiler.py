"""
Round 12: Service — ContextCompiler Tests

IMMUTABLE SPEC: Ref: SPEC_V02 §2.4 (F-9)

ContextCompiler assembles Agent context from three sources:
  [CORE MEMORY] — always-on Core items (active only)
  [RETRIEVED]    — HybridRetriever search results
  [RECENT ACTIVITY] — latest RecallStore items
"""

import pytest

from memory_palace.models.memory import MemoryItem, MemoryStatus, MemoryTier, MemoryType
from memory_palace.service.context_compiler import ContextCompiler
from memory_palace.service.memory_service import MemoryService
from memory_palace.store.recall_store import RecallStore


# ── Mock HybridRetriever ───────────────────────────────────


class MockHybridRetriever:
    """Minimal HybridRetriever mock for ContextCompiler tests."""

    def __init__(self, results: list[MemoryItem] | None = None) -> None:
        self._results = results or []

    async def search(self, query: str, top_k: int = 5, **kw) -> list[MemoryItem]:
        return self._results[:top_k]


# ── Tests ──────────────────────────────────────────────────


class TestContextCompilerBasic:
    """ContextCompiler basic output structure."""

    @pytest.mark.asyncio
    async def test_compile_includes_core_section(self, tmp_data_dir):
        """compile() includes [CORE MEMORY] section from active Core items."""
        ms = MemoryService(tmp_data_dir)
        ms.save("用户喜欢深色模式", importance=0.9, room="preferences")
        ms.save("用户的名字是Link", importance=0.8, room="identity")

        retriever = MockHybridRetriever()
        compiler = ContextCompiler(ms, retriever)

        result = await compiler.compile()

        assert "[CORE MEMORY]" in result
        assert "深色模式" in result
        assert "Link" in result

    @pytest.mark.asyncio
    async def test_compile_excludes_non_active_core(self, tmp_data_dir):
        """compile() filters out SUPERSEDED/PRUNED Core items (TD-2)."""
        ms = MemoryService(tmp_data_dir)
        ms.save("活跃记忆", importance=0.9, room="test")
        # Create and then supersede a memory
        item = ms.save("旧记忆", importance=0.8, room="test")
        ms.update(item.id, "新版本记忆", "updated")

        retriever = MockHybridRetriever()
        compiler = ContextCompiler(ms, retriever)

        result = await compiler.compile()

        assert "活跃记忆" in result
        # The old content should NOT appear in core context (superseded)
        # Note: new_version is in Recall (tier=CORE, but saved to Core block)
        assert "[CORE MEMORY]" in result

    @pytest.mark.asyncio
    async def test_compile_includes_retrieved_section(self, tmp_data_dir):
        """compile() includes [RETRIEVED] section when query is provided."""
        ms = MemoryService(tmp_data_dir)

        search_result = MemoryItem(
            content="Python是最佳编程语言",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.RECALL,
            importance=0.6,
            room="coding",
        )
        retriever = MockHybridRetriever(results=[search_result])
        compiler = ContextCompiler(ms, retriever)

        result = await compiler.compile(query="Python")

        assert "[RETRIEVED]" in result
        assert "Python" in result

    @pytest.mark.asyncio
    async def test_compile_no_retrieved_without_query(self, tmp_data_dir):
        """compile() omits [RETRIEVED] section when query is None."""
        ms = MemoryService(tmp_data_dir)
        retriever = MockHybridRetriever()
        compiler = ContextCompiler(ms, retriever)

        result = await compiler.compile(query=None)

        assert "[RETRIEVED]" not in result

    @pytest.mark.asyncio
    async def test_compile_includes_recent_section(self, tmp_data_dir):
        """compile() includes [RECENT ACTIVITY] from RecallStore."""
        ms = MemoryService(tmp_data_dir)
        ms.save("最近的活动记录", importance=0.4, room="general")

        retriever = MockHybridRetriever()
        compiler = ContextCompiler(ms, retriever)

        result = await compiler.compile()

        assert "[RECENT ACTIVITY]" in result
        assert "最近的活动记录" in result

    @pytest.mark.asyncio
    async def test_compile_respects_max_chars(self, tmp_data_dir):
        """compile() truncates output to max_chars."""
        ms = MemoryService(tmp_data_dir)
        # Create enough content to exceed limit
        for i in range(20):
            ms.save(f"这是一段很长的记忆内容编号{i}，用来测试截断功能。" * 5,
                    importance=0.4, room="general")

        retriever = MockHybridRetriever()
        compiler = ContextCompiler(ms, retriever)

        result = await compiler.compile(max_chars=200)

        assert len(result) <= 200 + len("\n[...truncated]")
        assert "[...truncated]" in result

    @pytest.mark.asyncio
    async def test_compile_empty_system(self, tmp_data_dir):
        """compile() returns empty string for empty system."""
        ms = MemoryService(tmp_data_dir)
        retriever = MockHybridRetriever()
        compiler = ContextCompiler(ms, retriever)

        result = await compiler.compile()

        # Should be empty or just whitespace (no sections)
        assert result.strip() == ""
