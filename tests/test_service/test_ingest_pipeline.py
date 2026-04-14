"""IngestPipeline — Unit tests for 5-pass document ingestion.

Ref: TASK_R25 §4
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from memory_palace.engine.fact_extractor import FactExtractor
from memory_palace.engine.reconcile import ReconcileEngine
from memory_palace.models.ingest import IngestReport
from memory_palace.service.ingest_pipeline import IngestPipeline
from memory_palace.service.memory_service import MemoryService
from tests.conftest import MockLLM

# ── Helpers ──────────────────────────────────────────────────────


def _make_extract_response(facts: list[dict]) -> str:
    return json.dumps(facts)


def _make_map_response(mappings: list[dict]) -> str:
    return json.dumps(mappings)


def _make_link_response(relations: list[dict]) -> str:
    return json.dumps(relations)


def _make_reconcile_add() -> str:
    return '{"action": "ADD", "target_id": null, "reason": "new info"}'


def _make_reconcile_update(target_id: str) -> str:
    return json.dumps({
        "action": "UPDATE",
        "target_id": target_id,
        "reason": "updated info",
    })


def _make_reconcile_noop() -> str:
    return '{"action": "NOOP", "target_id": null, "reason": "already captured"}'


def _build_pipeline(
    tmp_data_dir: Path,
    responses: list[str],
    graph_store=None,
) -> tuple[IngestPipeline, MemoryService, MockLLM]:
    """Build an IngestPipeline with a MockLLM for all components."""
    llm = MockLLM(responses=responses)
    svc = MemoryService(tmp_data_dir, llm=llm)
    extractor = FactExtractor(llm)
    reconciler = ReconcileEngine(llm)
    pipeline = IngestPipeline(
        memory_service=svc,
        fact_extractor=extractor,
        reconcile_engine=reconciler,
        llm=llm,
        graph_store=graph_store,
    )
    return pipeline, svc, llm


# ── Tests ────────────────────────────────────────────────────


class TestIngestBasic:
    """test_ingest_basic — text → extract facts → write memories."""

    @pytest.mark.asyncio
    async def test_ingest_basic(self, tmp_data_dir):
        responses = [
            # Pass 2 EXTRACT: 2 facts
            _make_extract_response([
                {"content": "Python是动态类型语言", "importance": 0.6, "tags": ["tech"]},
                {"content": "用户喜欢VSCode", "importance": 0.5, "tags": ["tools"]},
            ]),
            # Pass 3 MAP: assign rooms
            _make_map_response([
                {"index": 0, "room": "skills", "importance": 0.6},
                {"index": 1, "room": "preferences", "importance": 0.5},
            ]),
            # Pass 5 UPDATE: reconcile fact 0 → ADD
            _make_reconcile_add(),
            # Pass 5 UPDATE: reconcile fact 1 → ADD
            _make_reconcile_add(),
        ]
        pipeline, svc, _ = _build_pipeline(tmp_data_dir, responses)
        report = await pipeline.ingest("Python是动态类型语言。用户喜欢VSCode。")

        assert report.memories_created == 2
        assert report.total_input_chars > 0
        assert report.duration_seconds >= 0
        assert "diff" in report.pass_results
        assert report.pass_results["diff"]["skipped"] is False
        assert report.pass_results["extract"]["facts_count"] == 2


class TestIngestDiffSkip:
    """test_ingest_diff_skip — same text second time is skipped."""

    @pytest.mark.asyncio
    async def test_ingest_diff_skip(self, tmp_data_dir):
        text = "这是一段测试文本用于去重"
        responses = [
            # First ingest: extract + map + reconcile
            _make_extract_response([
                {"content": "测试文本", "importance": 0.5, "tags": []},
            ]),
            _make_map_response([{"index": 0, "room": "general", "importance": 0.5}]),
            _make_reconcile_add(),
        ]
        pipeline, svc, _ = _build_pipeline(tmp_data_dir, responses)

        # First ingest — succeeds
        r1 = await pipeline.ingest(text, source_id="test1")
        assert r1.memories_created == 1
        assert r1.pass_results["diff"]["skipped"] is False

        # Second ingest — same text → DIFF skip
        r2 = await pipeline.ingest(text, source_id="test1")
        assert r2.memories_created == 0
        assert r2.pass_results["diff"]["skipped"] is True


class TestIngestRoomMapping:
    """test_ingest_room_mapping — facts assigned to correct room."""

    @pytest.mark.asyncio
    async def test_ingest_room_mapping(self, tmp_data_dir):
        responses = [
            # EXTRACT
            _make_extract_response([
                {"content": "用户偏好深色主题", "importance": 0.5, "tags": []},
            ]),
            # MAP → preferences room, importance < 0.7 → Recall (FTS5 searchable)
            _make_map_response([
                {"index": 0, "room": "preferences", "importance": 0.6},
            ]),
            # RECONCILE → ADD
            _make_reconcile_add(),
        ]
        pipeline, svc, _ = _build_pipeline(tmp_data_dir, responses)
        report = await pipeline.ingest("用户偏好深色主题")

        assert report.memories_created == 1
        assert report.pass_results["map"]["mapped"] == 1

        # Verify the saved memory has room=preferences
        results = svc.search_sync("深色主题", top_k=5)
        assert len(results) >= 1
        assert results[0].room == "preferences"


class TestIngestReconcileUpdate:
    """test_ingest_reconcile_update — conflicting fact triggers UPDATE."""

    @pytest.mark.asyncio
    async def test_ingest_reconcile_update(self, tmp_data_dir):
        # Pre-save an existing memory
        svc = MemoryService(tmp_data_dir)
        old = svc.save("用户偏好浅色主题", importance=0.5, room="preferences")

        # Now ingest with conflicting info
        responses = [
            # EXTRACT
            _make_extract_response([
                {"content": "用户改为深色主题", "importance": 0.6, "tags": []},
            ]),
            # MAP
            _make_map_response([
                {"index": 0, "room": "preferences", "importance": 0.6},
            ]),
            # RECONCILE → UPDATE the old memory
            _make_reconcile_update(old.id),
        ]

        llm = MockLLM(responses=responses)
        extractor = FactExtractor(llm)
        reconciler = ReconcileEngine(llm)
        pipeline = IngestPipeline(
            memory_service=svc,
            fact_extractor=extractor,
            reconcile_engine=reconciler,
            llm=llm,
        )
        report = await pipeline.ingest("用户改为深色主题")

        # UPDATE, not ADD — memories_created should be 0
        assert report.memories_created == 0
        assert report.pass_results["update"]["updated"] == 1


class TestIngestReconcileNoop:
    """test_ingest_reconcile_noop — existing same fact NOOPs."""

    @pytest.mark.asyncio
    async def test_ingest_reconcile_noop(self, tmp_data_dir):
        # Pre-save
        svc = MemoryService(tmp_data_dir)
        svc.save("Python是动态类型语言", importance=0.5)

        responses = [
            _make_extract_response([
                {"content": "Python是动态类型语言", "importance": 0.5, "tags": []},
            ]),
            _make_map_response([{"index": 0, "room": "general", "importance": 0.5}]),
            _make_reconcile_noop(),
        ]

        llm = MockLLM(responses=responses)
        pipeline = IngestPipeline(
            memory_service=svc,
            fact_extractor=FactExtractor(llm),
            reconcile_engine=ReconcileEngine(llm),
            llm=llm,
        )
        report = await pipeline.ingest("Python是动态类型语言")

        assert report.memories_created == 0
        assert report.pass_results["update"]["noop"] == 1


class TestIngestLinkWithGraph:
    """test_ingest_link_with_graph — relations created via GraphStore."""

    @pytest.mark.asyncio
    async def test_ingest_link_with_graph(self, tmp_data_dir):
        mock_graph = MagicMock()

        responses = [
            # EXTRACT: 2 facts
            _make_extract_response([
                {"content": "Python是编程语言", "importance": 0.5, "tags": []},
                {"content": "Django是Python框架", "importance": 0.5, "tags": []},
            ]),
            # MAP
            _make_map_response([
                {"index": 0, "room": "skills", "importance": 0.5},
                {"index": 1, "room": "skills", "importance": 0.5},
            ]),
            # LINK: 1 relation
            _make_link_response([
                {"from": 0, "to": 1, "type": "hierarchical", "weight": 0.9},
            ]),
            # RECONCILE fact 0 → ADD
            _make_reconcile_add(),
            # RECONCILE fact 1 → ADD
            _make_reconcile_add(),
        ]

        pipeline, svc, _ = _build_pipeline(
            tmp_data_dir, responses, graph_store=mock_graph,
        )
        report = await pipeline.ingest("Python是编程语言。Django是Python框架。")

        assert report.memories_created == 2
        assert report.relations_created == 1
        assert report.pass_results["link"]["skipped"] is False
        assert report.pass_results["link"]["relations_found"] == 1
        mock_graph.add_relation.assert_called_once()


class TestIngestLinkWithoutGraph:
    """test_ingest_link_without_graph — pass 4 skipped when no GraphStore."""

    @pytest.mark.asyncio
    async def test_ingest_link_without_graph(self, tmp_data_dir):
        responses = [
            _make_extract_response([
                {"content": "事实一", "importance": 0.5, "tags": []},
            ]),
            _make_map_response([{"index": 0, "room": "general", "importance": 0.5}]),
            _make_reconcile_add(),
        ]
        pipeline, svc, _ = _build_pipeline(tmp_data_dir, responses)
        report = await pipeline.ingest("事实一")

        assert report.pass_results["link"]["skipped"] is True
        assert report.relations_created == 0


class TestIngestFile:
    """test_ingest_file — file path input."""

    @pytest.mark.asyncio
    async def test_ingest_file(self, tmp_data_dir):
        # Create a temp file
        doc = tmp_data_dir / "test_doc.txt"
        doc.write_text("这是测试文档的内容", encoding="utf-8")

        responses = [
            _make_extract_response([
                {"content": "测试文档内容", "importance": 0.5, "tags": []},
            ]),
            _make_map_response([{"index": 0, "room": "general", "importance": 0.5}]),
            _make_reconcile_add(),
        ]
        pipeline, svc, _ = _build_pipeline(tmp_data_dir, responses)
        report = await pipeline.ingest_file(doc)

        assert report.memories_created == 1
        assert report.total_input_chars == len("这是测试文档的内容")


class TestIngestBatch:
    """test_ingest_batch — multiple files."""

    @pytest.mark.asyncio
    async def test_ingest_batch(self, tmp_data_dir):
        # Create 2 temp files
        doc1 = tmp_data_dir / "doc1.txt"
        doc1.write_text("文档一内容", encoding="utf-8")
        doc2 = tmp_data_dir / "doc2.txt"
        doc2.write_text("文档二内容", encoding="utf-8")

        responses = [
            # File 1: extract + map + reconcile
            _make_extract_response([
                {"content": "文档一", "importance": 0.5, "tags": []},
            ]),
            _make_map_response([{"index": 0, "room": "general", "importance": 0.5}]),
            _make_reconcile_add(),
            # File 2: extract + map + reconcile
            _make_extract_response([
                {"content": "文档二", "importance": 0.5, "tags": []},
            ]),
            _make_map_response([{"index": 0, "room": "general", "importance": 0.5}]),
            _make_reconcile_add(),
        ]
        pipeline, svc, _ = _build_pipeline(tmp_data_dir, responses)
        report = await pipeline.ingest_batch([doc1, doc2])

        assert report.memories_created == 2
        assert len(report.pass_results) == 2  # one per file


class TestIngestErrorHandling:
    """test_ingest_error_handling — LLM failure → partial results + errors."""

    @pytest.mark.asyncio
    async def test_ingest_error_handling(self, tmp_data_dir):
        responses = [
            # EXTRACT: 1 fact
            _make_extract_response([
                {"content": "事实", "importance": 0.5, "tags": []},
            ]),
            # MAP: malformed JSON → error, but pipeline continues
            "this is not valid json {{{",
            # RECONCILE → ADD (pipeline should still reach here)
            _make_reconcile_add(),
        ]
        pipeline, svc, _ = _build_pipeline(tmp_data_dir, responses)
        report = await pipeline.ingest("事实")

        # Despite MAP failure, fact should still be saved (with defaults)
        assert report.memories_created == 1
        assert len(report.errors) >= 1
        assert any("map failed" in e for e in report.errors)


class TestIngestReportFields:
    """test_ingest_report_fields — all report fields present and correct types."""

    @pytest.mark.asyncio
    async def test_ingest_report_fields(self, tmp_data_dir):
        responses = [
            _make_extract_response([
                {"content": "测试", "importance": 0.5, "tags": ["test"]},
            ]),
            _make_map_response([{"index": 0, "room": "general", "importance": 0.5}]),
            _make_reconcile_add(),
        ]
        pipeline, svc, _ = _build_pipeline(tmp_data_dir, responses)
        report = await pipeline.ingest("测试内容")

        # Type checks
        assert isinstance(report, IngestReport)
        assert isinstance(report.total_input_chars, int)
        assert isinstance(report.pass_results, dict)
        assert isinstance(report.memories_created, int)
        assert isinstance(report.relations_created, int)
        assert isinstance(report.duration_seconds, float)
        assert isinstance(report.errors, list)

        # Value checks
        assert report.total_input_chars == len("测试内容")
        assert "diff" in report.pass_results
        assert "extract" in report.pass_results
        assert "map" in report.pass_results
        assert "link" in report.pass_results
        assert "update" in report.pass_results
        assert report.duration_seconds >= 0


class TestIngestEmptyText:
    """test_ingest_empty_text — empty text → 0 memories."""

    @pytest.mark.asyncio
    async def test_ingest_empty_text(self, tmp_data_dir):
        responses = [
            # EXTRACT will return [] for empty text (FactExtractor behavior)
            "[]",
        ]
        pipeline, svc, _ = _build_pipeline(tmp_data_dir, responses)
        report = await pipeline.ingest("")

        assert report.memories_created == 0
        assert report.total_input_chars == 0
        assert len(report.errors) == 0
