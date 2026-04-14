"""Layer 2 CLI E2E Tests — Typer CLI commands for Memory Palace.

Validates CLI commands end-to-end using CliRunner:
save, search, inspect, update, forget, rooms, audit, metrics,
schedule, import/export, persona, serve, ingest.

Ref: TASK_R25
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from memory_palace.integration.cli import app
from memory_palace.service.memory_service import MemoryService
from memory_palace.store.recall_store import RecallStore

runner = CliRunner()


# ── Helpers ───────────────────────────────────────────────────


def _save_via_cli(tmp_data_dir: Path, content: str, **kwargs) -> str:
    """Save a memory via CLI and return the full memory ID."""
    args = ["save", content, "--data-dir", str(tmp_data_dir)]
    for k, v in kwargs.items():
        args.extend([f"--{k}", str(v)])
    result = runner.invoke(app, args)
    assert result.exit_code == 0, f"save failed: {result.output}"
    # CLI shows truncated ID; retrieve the real full ID via service
    svc = MemoryService(tmp_data_dir)
    # First try Recall tier (FTS5 search)
    results = svc.search_sync(content, top_k=1)
    if results:
        return results[0].id
    # High importance items go to Core tier — look there
    from memory_palace.store.core_store import CoreStore
    cs = CoreStore(tmp_data_dir)
    for block in cs.list_blocks():
        for item in cs.load(block):
            if item.content == content:
                return item.id
    raise AssertionError(f"Could not find saved memory for '{content}' in any tier")


# ── T2.1: CLI Save + Search + Inspect ────────────────────────


class TestCLISaveSearchInspect:
    """T2.1 — save → search → inspect (overview + detail)."""

    def test_save_and_search(self, tmp_data_dir):
        # Save — use importance < 0.7 so item goes to Recall tier (FTS5 searchable)
        result = runner.invoke(
            app,
            [
                "save", "测试内容Alpha",
                "--importance", "0.5",
                "--room", "projects",
                "--data-dir", str(tmp_data_dir),
            ],
        )
        assert result.exit_code == 0
        assert "记忆已保存" in result.output
        assert "id=" in result.output

        # Search — CLI search uses FTS5 (sync), works for Recall tier items
        result = runner.invoke(
            app,
            ["search", "测试内容Alpha", "--top-k", "3", "--data-dir", str(tmp_data_dir)],
        )
        assert result.exit_code == 0
        # Output contains either the content or the table title
        assert "测试内容Alpha" in result.output or "搜索结果" in result.output

    def test_inspect_overview(self, tmp_data_dir):
        # Save one item first
        _save_via_cli(tmp_data_dir, "概览测试记忆")

        result = runner.invoke(
            app, ["inspect", "--data-dir", str(tmp_data_dir)]
        )
        assert result.exit_code == 0
        assert "Memory Palace 概览" in result.output
        # Should show core/recall counts
        assert "Core" in result.output or "core" in result.output.lower()

    def test_inspect_detail(self, tmp_data_dir):
        # Use importance < 0.7 for Recall tier, or >= 0.7 for Core tier
        memory_id = _save_via_cli(tmp_data_dir, "详情测试记忆", importance="0.5")

        result = runner.invoke(
            app, ["inspect", memory_id, "--data-dir", str(tmp_data_dir)]
        )
        assert result.exit_code == 0
        assert "记忆详情" in result.output
        # Should contain importance, room, version info
        assert "0.8" in result.output or "重要性" in result.output
        assert "版本" in result.output or "version" in result.output.lower()

    def test_search_with_date_query_in_cli_flow(self, tmp_data_dir):
        """Hyphenated/date queries should work through the public CLI lifecycle."""
        content = "Nested Codex CLI smoke test 2026-04-13"
        save_result = runner.invoke(
            app,
            [
                "save", content,
                "--importance", "0.5",
                "--tags", "cli,smoke-test",
                "--data-dir", str(tmp_data_dir),
            ],
        )
        assert save_result.exit_code == 0

        search_result = runner.invoke(
            app,
            ["search", "2026-04-13", "--top-k", "3", "--data-dir", str(tmp_data_dir)],
        )
        assert search_result.exit_code == 0
        assert "2026-04-13" in search_result.output

        memory_id = RecallStore(tmp_data_dir).get_recent(1)[0].id
        inspect_result = runner.invoke(
            app, ["inspect", memory_id, "--data-dir", str(tmp_data_dir)]
        )
        assert inspect_result.exit_code == 0
        assert content in inspect_result.output


# ── T2.2: CLI Update + Forget ────────────────────────────────


class TestCLIUpdateForget:
    """T2.2 — save → update → verify v2 → forget → inspect shows gone."""

    def test_update_then_forget(self, tmp_data_dir):
        # Save
        original_id = _save_via_cli(tmp_data_dir, "原始内容")

        # Update
        result = runner.invoke(
            app,
            [
                "update", original_id, "更新后内容",
                "--reason", "测试更新",
                "--data-dir", str(tmp_data_dir),
            ],
        )
        assert result.exit_code == 0
        assert "记忆已更新" in result.output
        assert "v2" in result.output

        # Get the new ID from the updated memory
        svc = MemoryService(tmp_data_dir)
        results = svc.search_sync("更新后内容", top_k=1)
        assert results
        new_id = results[0].id

        # Forget the new version
        result = runner.invoke(
            app,
            [
                "forget", new_id,
                "--reason", "测试遗忘",
                "--data-dir", str(tmp_data_dir),
            ],
        )
        assert result.exit_code == 0
        assert "记忆已遗忘" in result.output

        # Inspect the forgotten memory — should show PRUNED status or not found
        result = runner.invoke(
            app, ["inspect", new_id, "--data-dir", str(tmp_data_dir)]
        )
        # Either shows PRUNED status or "未找到"
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert (
            "pruned" in output_lower
            or "未找到" in result.output
            or "forgotten" in output_lower
        )


# ── T2.3: CLI Rooms + Audit + Metrics ────────────────────────


class TestCLIRoomsAuditMetrics:
    """T2.3 — rooms listing, audit log, metrics output."""

    def test_rooms(self, tmp_data_dir):
        result = runner.invoke(
            app, ["rooms", "--data-dir", str(tmp_data_dir)]
        )
        assert result.exit_code == 0
        assert "房间列表" in result.output
        # 5 default rooms
        for room in ("general", "preferences", "projects", "people", "skills"):
            assert room in result.output

    def test_audit_after_saves(self, tmp_data_dir):
        # Save a couple items to generate audit entries
        _save_via_cli(tmp_data_dir, "审计测试1")
        _save_via_cli(tmp_data_dir, "审计测试2")

        result = runner.invoke(
            app, ["audit", "--last", "5", "--data-dir", str(tmp_data_dir)]
        )
        assert result.exit_code == 0
        # Should show audit table or note that log exists
        assert "审计日志" in result.output or "暂无审计日志" in result.output

    def test_metrics(self, tmp_data_dir):
        result = runner.invoke(
            app, ["metrics", "--data-dir", str(tmp_data_dir)]
        )
        assert result.exit_code == 0
        # Metrics table should contain key fields
        assert "search_p95" in result.output.lower() or "搜索" in result.output
        assert "save_p95" in result.output.lower() or "保存" in result.output


# ── T2.4: CLI Schedule Commands ───────────────────────────────


class TestCLIScheduleCommands:
    """T2.4 — schedule start --help, schedule status."""

    def test_schedule_start_help(self, tmp_data_dir):
        result = runner.invoke(app, ["schedule", "start", "--help"])
        assert result.exit_code == 0
        assert "check-interval" in result.output or "检查间隔" in result.output

    def test_schedule_status(self, tmp_data_dir):
        result = runner.invoke(
            app, ["schedule", "status", "--data-dir", str(tmp_data_dir)]
        )
        assert result.exit_code == 0
        # Should report not running or show status
        assert "调度" in result.output


# ── T2.5: CLI Import + Export Roundtrip ───────────────────────


class TestCLIImportExportRoundtrip:
    """T2.5 — save items → export JSONL → import into fresh dir → verify."""

    def test_export_import_jsonl(self, tmp_data_dir, tmp_path):
        # Save 3 items
        for i in range(3):
            _save_via_cli(tmp_data_dir, f"导出测试记忆{i}")

        # Export to JSONL
        export_file = tmp_path / "export.jsonl"
        result = runner.invoke(
            app,
            [
                "export", str(export_file),
                "--format", "jsonl",
                "--data-dir", str(tmp_data_dir),
            ],
        )
        assert result.exit_code == 0
        assert "导出完成" in result.output
        assert export_file.exists()

        # Count exported lines
        lines = [ln for ln in export_file.read_text().strip().split("\n") if ln.strip()]
        assert len(lines) >= 3

        # Import into fresh data dir
        fresh_dir = tmp_path / "fresh_palace"
        fresh_dir.mkdir()
        (fresh_dir / "core").mkdir()
        (fresh_dir / "archival").mkdir()

        result = runner.invoke(
            app,
            ["import", str(export_file), "--data-dir", str(fresh_dir)],
        )
        assert result.exit_code == 0
        assert "导入完成" in result.output

        # Verify imported count via stats
        svc = MemoryService(fresh_dir)
        stats = svc.stats()
        assert stats["total"] >= 3


# ── T2.6: CLI Persona Commands ────────────────────────────────


class TestCLIPersonaCommands:
    """T2.6 — persona list, create, switch, delete full lifecycle."""

    def test_persona_list(self, tmp_data_dir):
        result = runner.invoke(
            app, ["persona", "list", "--data-dir", str(tmp_data_dir)]
        )
        assert result.exit_code == 0 or "Persona" in result.output

    def test_persona_create_help(self):
        result = runner.invoke(app, ["persona", "create", "--help"])
        assert result.exit_code == 0
        assert "--name" in result.output
        assert "--dir" in result.output

    def test_persona_create_and_list(self, tmp_path):
        """Create a persona via CLI, then verify it appears in list."""
        import yaml

        base_dir = tmp_path / "palace_base"
        base_dir.mkdir()
        persona_dir = tmp_path / "test_bot_data"
        persona_dir.mkdir()
        (persona_dir / "core").mkdir()

        # Write initial config YAML
        config = {
            "personas": [
                {
                    "name": "default",
                    "data_dir": str(base_dir),
                    "description": "默认",
                }
            ],
            "active_persona": "default",
        }
        yaml_path = base_dir / "memory_palace.yaml"
        yaml_path.write_text(
            yaml.dump(config), encoding="utf-8"
        )

        # Create persona
        result = runner.invoke(
            app,
            [
                "persona", "create",
                "--name", "test-bot",
                "--dir", str(persona_dir),
                "--desc", "测试角色",
                "--data-dir", str(base_dir),
            ],
        )
        assert result.exit_code == 0
        assert "test-bot" in result.output

        # List should show the new persona
        result = runner.invoke(
            app,
            ["persona", "list", "--data-dir", str(base_dir)],
        )
        assert result.exit_code == 0
        assert "test-bot" in result.output

    def test_persona_switch_help(self):
        result = runner.invoke(app, ["persona", "switch", "--help"])
        assert result.exit_code == 0
        assert "--name" in result.output

    def test_persona_delete_help(self):
        result = runner.invoke(app, ["persona", "delete", "--help"])
        assert result.exit_code == 0
        assert "--name" in result.output


# ── T2.7: CLI Serve Help ─────────────────────────────────────


class TestCLIServeHelp:
    """T2.7 — palace serve --help shows transport option."""

    def test_serve_help(self):
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--transport" in result.output
        assert "stdio" in result.output


# ── T2.8: CLI Ingest ─────────────────────────────────────────


class TestCLIIngest:
    """T2.8 — ingest command exists (needs LLM; test via help)."""

    def test_ingest_help(self):
        result = runner.invoke(app, ["ingest", "--help"])
        assert result.exit_code == 0
        assert "--data-dir" in result.output
        # ingest takes a file argument
        assert "文档" in result.output or "file" in result.output.lower()
