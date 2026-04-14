"""
Round 21: Service — BatchImporter / BatchExporter Tests

Ref: TASK_R21

Tests use tmp_data_dir — no real I/O beyond temp files.
"""

import json

import pytest

from memory_palace.service.batch_io import (
    BatchExporter,
    BatchImporter,
    ExportReport,
    ImportReport,
)
from memory_palace.service.memory_service import MemoryService

# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def svc(tmp_data_dir):
    """MemoryService with tmp data dir."""
    return MemoryService(tmp_data_dir)


@pytest.fixture
def importer(svc):
    return BatchImporter(svc)


@pytest.fixture
def exporter(svc):
    return BatchExporter(svc)


# ── Import Markdown ───────────────────────────────────────────


class TestImportMarkdown:
    @pytest.mark.asyncio
    async def test_import_markdown_basic(self, importer, tmp_path):
        """3 个 heading → 3 条记忆."""
        md = tmp_path / "notes.md"
        md.write_text(
            "# Title\n\n"
            "## Note 1\nFirst memory content\n\n"
            "## Note 2\nSecond memory content\n\n"
            "## Note 3\nThird memory content\n",
            encoding="utf-8",
        )
        report = await importer.import_markdown(md)

        assert report.total_found == 3
        assert report.imported == 3
        assert report.skipped == 0

    @pytest.mark.asyncio
    async def test_import_markdown_with_frontmatter(self, importer, svc, tmp_path):
        """YAML importance/room 解析."""
        md = tmp_path / "notes.md"
        md.write_text(
            "---\n"
            "importance: 0.9\n"
            "room: projects\n"
            "tags: [python, ml]\n"
            "---\n\n"
            "## Insight\nThis is important\n",
            encoding="utf-8",
        )
        report = await importer.import_markdown(md)

        assert report.imported == 1
        # importance=0.9 → CoreStore, verify via core_store
        from memory_palace.store.core_store import CoreStore

        core = CoreStore(svc._data_dir)
        items = core.load("projects")
        assert len(items) == 1
        item = items[0]
        assert item.importance == 0.9
        assert item.room == "projects"
        assert "python" in item.tags

    @pytest.mark.asyncio
    async def test_import_markdown_empty(self, importer, tmp_path):
        """空文件 → 0 条."""
        md = tmp_path / "empty.md"
        md.write_text("", encoding="utf-8")
        report = await importer.import_markdown(md)

        assert report.total_found == 0
        assert report.imported == 0


# ── Import JSONL ──────────────────────────────────────────────


class TestImportJsonl:
    @pytest.mark.asyncio
    async def test_import_jsonl_basic(self, importer, tmp_path):
        """3 行 → 3 条."""
        jl = tmp_path / "data.jsonl"
        lines = [
            json.dumps({"content": f"Memory {i}", "importance": 0.5})
            for i in range(3)
        ]
        jl.write_text("\n".join(lines), encoding="utf-8")

        report = await importer.import_jsonl(jl)

        assert report.total_found == 3
        assert report.imported == 3
        assert report.skipped == 0

    @pytest.mark.asyncio
    async def test_import_jsonl_invalid_line(self, importer, tmp_path):
        """跳过坏行, errors 记录."""
        jl = tmp_path / "data.jsonl"
        jl.write_text(
            '{"content": "good line"}\n'
            "this is not json\n"
            '{"content": "another good"}\n',
            encoding="utf-8",
        )
        report = await importer.import_jsonl(jl)

        assert report.imported == 2
        assert len(report.errors) == 1
        assert "Line 2" in report.errors[0]

    @pytest.mark.asyncio
    async def test_import_jsonl_duplicate(self, importer, svc, tmp_path):
        """重复 content 跳过."""
        # Pre-save a memory
        svc.save(content="Already exists", importance=0.5)

        jl = tmp_path / "data.jsonl"
        jl.write_text(
            '{"content": "Already exists"}\n'
            '{"content": "Brand new"}\n',
            encoding="utf-8",
        )
        report = await importer.import_jsonl(jl)

        assert report.imported == 1
        assert report.skipped == 1


# ── Export Markdown ───────────────────────────────────────────


class TestExportMarkdown:
    def test_export_markdown(self, svc, exporter, tmp_path):
        """导出后文件存在, 内容正确."""
        svc.save("Hello world", importance=0.5, room="general")

        out_dir = tmp_path / "export_md"
        report = exporter.export_markdown(out_dir)

        assert report.total_exported == 1
        assert (out_dir / "general.md").exists()
        content = (out_dir / "general.md").read_text(encoding="utf-8")
        assert "Hello world" in content

    def test_export_markdown_per_room(self, svc, exporter, tmp_path):
        """每个房间一个文件."""
        svc.save("Mem A", importance=0.5, room="general")
        svc.save("Mem B", importance=0.5, room="projects")

        out_dir = tmp_path / "export_md"
        report = exporter.export_markdown(out_dir)

        assert report.total_exported == 2
        assert (out_dir / "general.md").exists()
        assert (out_dir / "projects.md").exists()


# ── Export JSONL ──────────────────────────────────────────────


class TestExportJsonl:
    def test_export_jsonl(self, svc, exporter, tmp_path):
        """导出后每行可解析为 dict."""
        svc.save("Line 1", importance=0.5)
        svc.save("Line 2", importance=0.3)

        out_file = tmp_path / "export.jsonl"
        report = exporter.export_jsonl(out_file)

        assert report.total_exported == 2
        lines = out_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        for line in lines:
            data = json.loads(line)
            assert "content" in data
            assert "importance" in data

    @pytest.mark.asyncio
    async def test_export_jsonl_roundtrip(self, svc, tmp_path):
        """导出 → 导入 → 记忆数量一致."""
        svc.save("RT Memory 1", importance=0.5, room="general")
        svc.save("RT Memory 2", importance=0.6, room="projects")

        exporter = BatchExporter(svc)
        out_file = tmp_path / "roundtrip.jsonl"
        export_report = exporter.export_jsonl(out_file)
        assert export_report.total_exported == 2

        # Create a fresh service for import
        fresh_dir = tmp_path / "fresh"
        fresh_dir.mkdir()
        (fresh_dir / "core").mkdir()
        fresh_svc = MemoryService(fresh_dir)
        importer = BatchImporter(fresh_svc)

        import_report = await importer.import_jsonl(out_file)
        assert import_report.imported == 2


# ── Error Handling ────────────────────────────────────────────


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_import_nonexistent_file(self, importer, tmp_path):
        """FileNotFoundError 处理."""
        with pytest.raises(FileNotFoundError):
            await importer.import_markdown(tmp_path / "nope.md")

        with pytest.raises(FileNotFoundError):
            await importer.import_jsonl(tmp_path / "nope.jsonl")


# ── Report Fields ─────────────────────────────────────────────


class TestReportFields:
    @pytest.mark.asyncio
    async def test_import_report_fields(self, importer, tmp_path):
        """report 字段完整."""
        jl = tmp_path / "data.jsonl"
        jl.write_text('{"content": "test"}\n', encoding="utf-8")
        report = await importer.import_jsonl(jl)

        assert isinstance(report, ImportReport)
        assert isinstance(report.total_found, int)
        assert isinstance(report.imported, int)
        assert isinstance(report.skipped, int)
        assert isinstance(report.errors, list)
        assert isinstance(report.duration_seconds, float)

    def test_export_report_fields(self, svc, exporter, tmp_path):
        """report 字段完整."""
        svc.save("X", importance=0.5)
        out = tmp_path / "out.jsonl"
        report = exporter.export_jsonl(out)

        assert isinstance(report, ExportReport)
        assert isinstance(report.total_exported, int)
        assert isinstance(report.output_path, str)
        assert isinstance(report.duration_seconds, float)
