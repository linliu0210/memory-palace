"""Layer 1 E2E Pipeline Tests — v1.0 CRUD, routing, search, curator, ebbinghaus, context, ingest.

Validates core Memory Palace pipelines end-to-end with mocked LLM/embedding.

Ref: TASK_R25
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from memory_palace.config import EbbinghausConfig
from memory_palace.engine.fact_extractor import FactExtractor
from memory_palace.engine.reconcile import ReconcileEngine
from memory_palace.foundation.audit_log import AuditLog
from memory_palace.models.memory import MemoryStatus, MemoryTier
from memory_palace.service.context_compiler import ContextCompiler
from memory_palace.service.curator import CuratorService
from memory_palace.service.curator_graph import CuratorGraph
from memory_palace.service.hybrid_retriever import HybridRetriever
from memory_palace.service.ingest_pipeline import IngestPipeline
from memory_palace.service.memory_service import MemoryService
from memory_palace.store.archival_store import ArchivalStore
from memory_palace.store.core_store import CoreStore
from memory_palace.store.recall_store import RecallStore
from tests.conftest import MockLLM

# ── Helpers ───────────────────────────────────────────────────


def _build_ingest_pipeline(
    data_dir,
    llm: MockLLM,
    graph_store=None,
) -> tuple[IngestPipeline, MemoryService]:
    """Build IngestPipeline + MemoryService sharing the same MockLLM."""
    svc = MemoryService(data_dir, llm=llm)
    extractor = FactExtractor(llm)
    reconciler = ReconcileEngine(llm)
    pipeline = IngestPipeline(
        memory_service=svc,
        fact_extractor=extractor,
        reconcile_engine=reconciler,
        llm=llm,
        graph_store=graph_store,
    )
    return pipeline, svc


# ── T1.1: Basic CRUD Lifecycle ────────────────────────────────


class TestBasicCRUDLifecycle:
    """T1.1 — save → search → update → forget → get_by_id → stats → audit."""

    @pytest.mark.asyncio
    async def test_crud_lifecycle(self, tmp_data_dir):
        svc = MemoryService(tmp_data_dir)

        # Save 3 items
        svc.save(
            content="用户喜欢深色模式",
            importance=0.8, tags=["偏好"], room="preferences",
        )
        m2 = svc.save(
            content="用户正在学习Rust语言",
            importance=0.5, tags=["技能"], room="skills",
        )
        m3 = svc.save(
            content="项目使用Python后端",
            importance=0.6, tags=["项目"], room="projects",
        )

        # Search (search_sync uses FTS5 on Recall tier)
        results = svc.search_sync("Rust", top_k=5)
        assert len(results) >= 1
        assert any("Rust" in r.content for r in results)

        # Update m2
        new_m2 = svc.update(m2.id, "用户正在精通Rust语言", reason="更新学习进度")
        assert new_m2.version == 2
        assert new_m2.parent_id == m2.id
        old_m2 = svc.get_by_id(m2.id)
        assert old_m2 is not None
        assert old_m2.status == MemoryStatus.SUPERSEDED

        # Forget m3
        result = svc.forget(m3.id, reason="不再相关")
        assert result is True
        forgotten = svc.get_by_id(m3.id)
        assert forgotten is not None
        assert forgotten.status == MemoryStatus.PRUNED

        # Stats
        stats = svc.stats()
        assert stats["total"] >= 2  # at least core + active recall items counted

        # Audit log
        audit = AuditLog(tmp_data_dir).read()
        actions = [e.action for e in audit]
        assert "create" in actions
        assert "update" in actions
        assert "prune" in actions


# ── T1.2: Three-Tier Routing ─────────────────────────────────


class TestThreeTierRouting:
    """T1.2 — importance >= 0.7 → Core, importance < 0.7 → Recall."""

    def test_tier_routing(self, tmp_data_dir):
        svc = MemoryService(tmp_data_dir)

        core_item = svc.save(content="高重要性核心记忆", importance=0.9, room="general")
        recall_item = svc.save(content="低重要性回忆记忆", importance=0.3, room="general")

        assert core_item.tier == MemoryTier.CORE
        assert recall_item.tier == MemoryTier.RECALL

        # Verify Core item in core_store
        cs = CoreStore(tmp_data_dir)
        core_items = cs.load("general")
        core_ids = {i.id for i in core_items}
        assert core_item.id in core_ids

        # Verify Recall item in recall_store
        rs = RecallStore(tmp_data_dir)
        recall_fetched = rs.get(recall_item.id)
        assert recall_fetched is not None
        assert recall_fetched.id == recall_item.id

        # Both findable by search_sync
        results = svc.search_sync("记忆", top_k=10)
        found_ids = {r.id for r in results}
        # At minimum recall items show in FTS5
        assert recall_item.id in found_ids


# ── T1.3: HybridRetriever Search Quality ─────────────────────


class TestHybridRetrieverSearchQuality:
    """T1.3 — HybridRetriever with MockEmbedding: relevance, room filter, top_k."""

    @pytest.mark.asyncio
    async def test_hybrid_search_quality(self, tmp_data_dir, mock_embedding):
        archival = ArchivalStore(data_dir=tmp_data_dir, embedding=mock_embedding)
        svc = MemoryService(tmp_data_dir, embedding=mock_embedding, archival_store=archival)

        # Save 5 items with different rooms/content
        svc.save(content="Python编程语言基础教程", importance=0.5, room="skills")
        svc.save(content="Rust语言内存管理详解", importance=0.5, room="skills")
        svc.save(content="今日晚餐吃了寿司", importance=0.3, room="general")
        svc.save(content="Python机器学习框架对比", importance=0.6, room="projects")
        svc.save(content="会议纪要：季度目标讨论", importance=0.4, room="general")

        retriever = HybridRetriever(
            recall_store=RecallStore(tmp_data_dir),
            archival_store=archival,
            embedding=mock_embedding,
        )

        # Search for Python-related content
        results = await retriever.search("Python", top_k=5)
        assert len(results) >= 1

        # top_k limits results
        results_limited = await retriever.search("Python", top_k=2)
        assert len(results_limited) <= 2

        # Room filter works
        results_skills = await retriever.search("Python", top_k=5, room="skills")
        for r in results_skills:
            assert r.room == "skills"


# ── T1.4: Curator Full Pipeline ──────────────────────────────


class TestCuratorFullPipeline:
    """T1.4 — save(10) → CuratorService.run() → CuratorReport."""

    @pytest.mark.asyncio
    async def test_curator_full_pipeline(self, tmp_data_dir):
        # Pre-populate 10 recall items
        svc = MemoryService(tmp_data_dir)
        for i in range(10):
            svc.save(content=f"记忆条目 {i}: 测试数据内容", importance=0.4, room="general")

        # MockLLM: extract → facts, reconcile → NOOP, reflect → empty
        curator_llm = MockLLM(responses=[
            # FactExtractor: extract returns 2 facts
            json.dumps([
                {"content": "用户有多条测试数据", "importance": 0.5, "tags": ["测试"]},
                {"content": "记忆条目重复较多", "importance": 0.4, "tags": ["分析"]},
            ]),
            # ReconcileEngine: NOOP for fact 1
            json.dumps({"action": "NOOP", "target_id": None, "reason": "already captured"}),
            # ReconcileEngine: NOOP for fact 2
            json.dumps({"action": "NOOP", "target_id": None, "reason": "already captured"}),
            # ReflectionEngine: empty reflections
            json.dumps([]),
        ])

        curator = CuratorService(tmp_data_dir, llm=curator_llm)
        report = await curator.run()

        assert report is not None
        assert report.duration_seconds > 0
        # No safety errors
        safety_errors = [e for e in report.errors if "Safety" in e]
        assert len(safety_errors) == 0


# ── T1.5: Ebbinghaus Decay → Prune ──────────────────────────


class TestEbbinghausDecayPrune:
    """T1.5 — age a low-importance item 60 days → CuratorGraph prunes it."""

    @pytest.mark.asyncio
    async def test_ebbinghaus_prune(self, tmp_data_dir):
        svc = MemoryService(tmp_data_dir)

        # Save a low-importance item and a high-importance item
        low = svc.save(content="临时笔记不重要", importance=0.2, room="general")
        high = svc.save(content="核心架构决策", importance=0.9, room="general")

        # Manually age the low-importance item's accessed_at to 60 days ago
        rs = RecallStore(tmp_data_dir)
        aged_time = (datetime.now() - timedelta(days=60)).isoformat()
        rs.update_field(low.id, "accessed_at", aged_time)

        # Build CuratorGraph with ebbinghaus enabled
        eb_cfg = EbbinghausConfig(enabled=True, base_stability_hours=168.0, prune_threshold=0.05)

        # MockLLM for extract/reconcile/reflect phases
        curator_llm = MockLLM(responses=[
            # FactExtractor: empty (nothing new)
            json.dumps([]),
            # ReflectionEngine: empty
            json.dumps([]),
        ])

        cs = CoreStore(tmp_data_dir)
        extractor = FactExtractor(curator_llm)
        reconciler = ReconcileEngine(curator_llm)

        graph = CuratorGraph(
            memory_service=svc,
            recall_store=rs,
            core_store=cs,
            fact_extractor=extractor,
            reconcile_engine=reconciler,
            llm=curator_llm,
            ebbinghaus_config=eb_cfg,
        )

        report = await graph.run()

        assert report.ebbinghaus_pruned >= 1

        # Verify the low-importance item is now PRUNED
        pruned_item = rs.get(low.id)
        assert pruned_item is not None
        assert pruned_item.status == MemoryStatus.PRUNED

        # High-importance item (in Core) should not be pruned
        high_item = svc.get_by_id(high.id)
        assert high_item is not None
        assert high_item.status == MemoryStatus.ACTIVE


# ── T1.6: Context Compiler Output ────────────────────────────


class TestContextCompilerOutput:
    """T1.6 — compile context with Core + Recall items → structured output."""

    @pytest.mark.asyncio
    async def test_context_compiler_output(self, tmp_data_dir):
        svc = MemoryService(tmp_data_dir)

        # 3 Core items (importance >= 0.7)
        for i in range(3):
            svc.save(content=f"核心记忆测试条目{i}", importance=0.9, room="general")

        # 5 Recall items (importance < 0.7)
        for i in range(5):
            svc.save(content=f"回忆测试条目{i}", importance=0.4, room="general")

        retriever = HybridRetriever(
            recall_store=RecallStore(tmp_data_dir),
            archival_store=None,
        )
        compiler = ContextCompiler(memory_service=svc, retriever=retriever)

        result = await compiler.compile(query="测试")

        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain structured sections
        assert "[CORE MEMORY]" in result or "[RETRIEVED]" in result
        # Core items should appear in the output
        assert any(f"核心记忆测试条目{i}" in result for i in range(3))


# ── T1.7: IngestPipeline 5-Pass ──────────────────────────────


class TestIngestPipelineFivePass:
    """T1.7 — IngestPipeline: DIFF → EXTRACT → MAP → LINK → UPDATE."""

    @pytest.mark.asyncio
    async def test_ingest_five_pass(self, tmp_data_dir):
        llm = MockLLM(responses=[
            # EXTRACT: 3 facts
            json.dumps([
                {"content": "用户偏好深色模式", "importance": 0.8, "tags": ["偏好"]},
                {"content": "项目使用FastAPI框架", "importance": 0.6, "tags": ["项目"]},
                {"content": "团队有五名成员", "importance": 0.5, "tags": ["团队"]},
            ]),
            # MAP: 3 mappings
            json.dumps([
                {"index": 0, "room": "preferences", "importance": 0.8},
                {"index": 1, "room": "projects", "importance": 0.6},
                {"index": 2, "room": "people", "importance": 0.5},
            ]),
            # RECONCILE fact 0 → ADD
            json.dumps({"action": "ADD", "target_id": None, "reason": "new preference"}),
            # RECONCILE fact 1 → ADD
            json.dumps({"action": "ADD", "target_id": None, "reason": "new project info"}),
            # RECONCILE fact 2 → ADD
            json.dumps({"action": "ADD", "target_id": None, "reason": "new team info"}),
        ])

        pipeline, svc = _build_ingest_pipeline(tmp_data_dir, llm)

        report = await pipeline.ingest("用户偏好深色模式。项目使用FastAPI。团队有五人。")

        assert report.memories_created == 3
        assert report.errors == []

        # Audit log should have ingest/create entries
        audit = AuditLog(tmp_data_dir).read()
        actions = [e.action for e in audit]
        assert "create" in actions or "ingest" in actions


# ── T1.8: IngestPipeline Dedup ────────────────────────────────


class TestIngestPipelineDedup:
    """T1.8 — ingest same text twice with same source_id → second time skipped."""

    @pytest.mark.asyncio
    async def test_ingest_dedup(self, tmp_data_dir):
        text = "用户喜欢使用Vim编辑器进行开发工作"
        source_id = "doc_vim_preference"

        llm = MockLLM(responses=[
            # First call — EXTRACT
            json.dumps([
                {"content": "用户喜欢Vim编辑器", "importance": 0.6, "tags": ["工具"]},
            ]),
            # First call — MAP
            json.dumps([
                {"index": 0, "room": "preferences", "importance": 0.6},
            ]),
            # First call — RECONCILE → ADD
            json.dumps({"action": "ADD", "target_id": None, "reason": "new tool preference"}),
        ])

        pipeline, svc = _build_ingest_pipeline(tmp_data_dir, llm)

        # First ingest
        report1 = await pipeline.ingest(text, source_id=source_id)
        assert report1.memories_created == 1

        # Second ingest — DIFF pass should detect hash match and skip
        report2 = await pipeline.ingest(text, source_id=source_id)
        assert report2.memories_created == 0
        assert report2.pass_results.get("diff", {}).get("skipped") is True
