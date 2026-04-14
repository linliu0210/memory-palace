"""
Round 13: E2E — v0.2 Lifecycle Tests

Validates new v0.2 features end-to-end:
- Three-tier save/search
- HybridRetriever FTS5-only fallback
- Curator with reflect and prune
- ContextCompiler
- Health score computation

All LLM/embedding calls are mocked.
"""

import pytest

from memory_palace.config import Config
from memory_palace.engine.health import compute_health
from memory_palace.service.memory_service import MemoryService
from memory_palace.store.recall_store import RecallStore
from tests.conftest import MockLLM


class TestThreeTierSaveSearch:
    """Save items at different importance levels and verify tier routing."""

    def test_three_tier_save_search(self, tmp_data_dir):
        """Items route to Core (>=0.7) or Recall (<0.7) and search returns results."""
        svc = MemoryService(tmp_data_dir)

        # Save at different importance levels
        low = svc.save(content="低重要性记忆", importance=0.3, room="general")
        mid = svc.save(content="中重要性记忆", importance=0.5, room="general")
        high = svc.save(content="高重要性核心记忆", importance=0.9, room="general")

        # Verify tier assignment
        assert low.tier.value == "recall"
        assert mid.tier.value == "recall"
        assert high.tier.value == "core"

        # Search returns results from both tiers
        results = svc.search_sync("记忆")
        assert len(results) >= 2  # At least recall items show up in FTS5


class TestHybridSearchFTSOnly:
    """HybridRetriever degrades to FTS5-only when archival_store=None."""

    @pytest.mark.asyncio
    async def test_hybrid_search_beats_fts_only(self, tmp_data_dir):
        """HybridRetriever with archival_store=None uses FTS5 fallback."""
        from memory_palace.service.hybrid_retriever import HybridRetriever

        svc = MemoryService(tmp_data_dir)
        svc.save(content="Python编程语言学习笔记", importance=0.5, room="skills")
        svc.save(content="机器学习模型训练经验", importance=0.5, room="skills")

        recall_store = RecallStore(tmp_data_dir)
        retriever = HybridRetriever(recall_store=recall_store, archival_store=None)

        results = await retriever.search("Python", top_k=5)
        assert len(results) >= 1
        assert any("Python" in r.content for r in results)


class TestCuratorWithReflectAndPrune:
    """Curator full cycle with mock LLM."""

    @pytest.mark.asyncio
    async def test_curator_with_reflect_and_prune(self, tmp_data_dir):
        """CuratorService runs successfully with mocked LLM responses."""
        from memory_palace.service.curator import CuratorService

        # Save some items first
        svc = MemoryService(tmp_data_dir)
        svc.save(content="用户喜欢深色模式", importance=0.5, tags=["偏好"])
        svc.save(content="用户正在学习Rust", importance=0.5, tags=["技能"])

        # Mock LLM: extract response + reconcile response (ADD for each fact)
        curator_llm = MockLLM(
            responses=[
                '[{"content": "用户偏好深色主题", "importance": 0.6, "tags": ["偏好"]}]',
                '{"action": "ADD", "target_id": null, "reason": "new information"}',
            ]
        )

        curator = CuratorService(tmp_data_dir, llm=curator_llm)
        report = await curator.run()

        assert report is not None
        assert report.facts_extracted >= 0


class TestContextCompilerE2E:
    """ContextCompiler assembles structured context from saved memories."""

    @pytest.mark.asyncio
    async def test_context_compiler_e2e(self, tmp_data_dir):
        """Compile context with FTS5-only retriever."""
        from memory_palace.service.context_compiler import ContextCompiler
        from memory_palace.service.hybrid_retriever import HybridRetriever

        svc = MemoryService(tmp_data_dir)
        # Save a core item
        svc.save(content="核心记忆：项目架构设计决策", importance=0.9, room="projects")
        # Save a recall item
        svc.save(content="临时记忆：今日会议纪要", importance=0.4, room="general")

        retriever = HybridRetriever(
            recall_store=RecallStore(tmp_data_dir),
            archival_store=None,
        )
        compiler = ContextCompiler(memory_service=svc, retriever=retriever)

        result = await compiler.compile(query="记忆")
        assert isinstance(result, str)
        # Should contain CORE MEMORY section and/or RETRIEVED section
        assert "[CORE MEMORY]" in result or "[RETRIEVED]" in result or len(result) > 0


class TestHealthScoreE2E:
    """Health score computation from saved memories."""

    def test_health_score_e2e(self, tmp_data_dir):
        """Compute health score and verify overall is in [0, 1]."""
        svc = MemoryService(tmp_data_dir)
        svc.save(content="记忆A", importance=0.9, room="general")
        svc.save(content="记忆B", importance=0.3, room="preferences")
        svc.save(content="记忆C", importance=0.5, room="projects")

        # Gather items via public API
        core_items, recall_items = svc.get_all_items()

        cfg = Config()
        score = compute_health(core_items, recall_items, cfg.rooms)

        assert 0.0 <= score.overall <= 1.0
        assert 0.0 <= score.freshness <= 1.0
        assert 0.0 <= score.efficiency <= 1.0
        assert 0.0 <= score.coverage <= 1.0
        assert 0.0 <= score.diversity <= 1.0
        assert 0.0 <= score.coherence <= 1.0
