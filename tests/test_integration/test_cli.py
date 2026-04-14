"""Tests for the palace CLI.

Uses Typer's CliRunner for isolated testing.
All file-backed commands use tmp_path for data isolation.
"""

from typer.testing import CliRunner

from memory_palace.integration.cli import app

runner = CliRunner()


class TestSaveCommand:
    """palace save — single memory persistence."""

    def test_save_basic(self, tmp_path):
        """Save a memory with default options."""
        data_dir = str(tmp_path)
        result = runner.invoke(app, ["save", "测试记忆", "--data-dir", data_dir])
        assert result.exit_code == 0
        assert "记忆已保存" in result.stdout

    def test_save_with_options(self, tmp_path):
        """Save a memory with explicit importance, room, and tags."""
        data_dir = str(tmp_path)
        result = runner.invoke(
            app,
            [
                "save",
                "用户喜欢深色模式",
                "--importance",
                "0.8",
                "--room",
                "preferences",
                "--tags",
                "ui,theme",
                "--data-dir",
                data_dir,
            ],
        )
        assert result.exit_code == 0
        assert "记忆已保存" in result.stdout
        assert "core" in result.stdout  # importance 0.8 → core tier


class TestSearchCommand:
    """palace search — FTS5 keyword search."""

    def test_search_finds_saved(self, tmp_path):
        """Search finds a previously saved memory."""
        data_dir = str(tmp_path)
        runner.invoke(app, ["save", "用户喜欢Python语言", "--data-dir", data_dir])
        result = runner.invoke(app, ["search", "Python", "--data-dir", data_dir])
        assert result.exit_code == 0
        assert "Python" in result.stdout

    def test_search_empty_results(self, tmp_path):
        """Search with no matches shows a helpful message."""
        data_dir = str(tmp_path)
        result = runner.invoke(app, ["search", "不存在的查询", "--data-dir", data_dir])
        assert result.exit_code == 0
        assert "未找到" in result.stdout


class TestInspectCommand:
    """palace inspect — overview or single-item detail."""

    def test_inspect_overview(self, tmp_path):
        """Inspect without ID shows stats overview."""
        data_dir = str(tmp_path)
        result = runner.invoke(app, ["inspect", "--data-dir", data_dir])
        assert result.exit_code == 0
        assert "概览" in result.stdout

    def test_inspect_overview_after_save(self, tmp_path):
        """Inspect shows correct counts after saving."""
        data_dir = str(tmp_path)
        runner.invoke(app, ["save", "记忆一", "--data-dir", data_dir])
        runner.invoke(app, ["save", "记忆二", "--data-dir", data_dir])
        result = runner.invoke(app, ["inspect", "--data-dir", data_dir])
        assert result.exit_code == 0
        assert "2" in result.stdout  # total count

    def test_inspect_nonexistent_id(self, tmp_path):
        """Inspect with invalid ID shows not-found message."""
        data_dir = str(tmp_path)
        result = runner.invoke(app, ["inspect", "nonexistent-id", "--data-dir", data_dir])
        assert result.exit_code == 0
        assert "未找到" in result.stdout


class TestRoomsCommand:
    """palace rooms — list default rooms."""

    def test_rooms_lists_defaults(self):
        """Rooms command lists all default rooms."""
        result = runner.invoke(app, ["rooms"])
        assert result.exit_code == 0
        assert "general" in result.stdout
        assert "preferences" in result.stdout
        assert "projects" in result.stdout
        assert "people" in result.stdout
        assert "skills" in result.stdout


class TestAuditCommand:
    """palace audit — view audit log."""

    def test_audit_empty(self, tmp_path):
        """Audit on empty data shows helpful message."""
        data_dir = str(tmp_path)
        result = runner.invoke(app, ["audit", "--data-dir", data_dir])
        assert result.exit_code == 0
        assert "暂无" in result.stdout

    def test_audit_after_save(self, tmp_path):
        """Audit shows entries after save operations."""
        data_dir = str(tmp_path)
        runner.invoke(app, ["save", "审计测试", "--data-dir", data_dir])
        result = runner.invoke(app, ["audit", "--data-dir", data_dir])
        assert result.exit_code == 0
        assert "create" in result.stdout


class TestUpdateCommand:
    """palace update — version update."""

    def test_update_nonexistent(self, tmp_path):
        """Update with invalid ID exits with error."""
        data_dir = str(tmp_path)
        result = runner.invoke(app, ["update", "bad-id", "new content", "--data-dir", data_dir])
        assert result.exit_code == 1

    def test_update_success(self, tmp_path):
        """Update a previously saved memory succeeds."""
        data_dir = str(tmp_path)
        # Save first
        save_result = runner.invoke(app, ["save", "旧内容", "--data-dir", data_dir])
        assert save_result.exit_code == 0
        # Extract ID from output (id=XXXXXXXX…)
        import re

        match = re.search(r"id=([a-f0-9]{8})", save_result.stdout)
        assert match, f"Could not find ID in output: {save_result.stdout}"
        match.group(1)

        # Get the full ID from recall store
        from pathlib import Path

        from memory_palace.store.recall_store import RecallStore

        store = RecallStore(Path(data_dir))
        items = store.get_recent(1)
        assert len(items) == 1
        full_id = items[0].id

        # Update
        result = runner.invoke(
            app,
            [
                "update",
                full_id,
                "新内容",
                "--reason",
                "测试更新",
                "--data-dir",
                data_dir,
            ],
        )
        assert result.exit_code == 0
        assert "记忆已更新" in result.stdout


class TestForgetCommand:
    """palace forget — soft delete."""

    def test_forget_nonexistent(self, tmp_path):
        """Forget with invalid ID shows not-found."""
        data_dir = str(tmp_path)
        result = runner.invoke(app, ["forget", "bad-id", "--data-dir", data_dir])
        assert result.exit_code == 0
        assert "未找到" in result.stdout


# ── [v1.0] Schedule command tests ─────────────────────────────


class TestScheduleCommand:
    """palace schedule — scheduler management CLI."""

    def test_schedule_status_shows_not_running(self):
        """schedule status → shows not-running message."""
        result = runner.invoke(app, ["schedule", "status"])
        assert result.exit_code == 0
        assert "未运行" in result.stdout

    def test_schedule_help(self):
        """schedule --help → shows subcommands."""
        result = runner.invoke(app, ["schedule", "--help"])
        assert result.exit_code == 0
        assert "start" in result.stdout
        assert "status" in result.stdout


# ── [R20] Serve command tests ─────────────────────────────────


class TestServeCommand:
    """palace serve — MCP server launch CLI."""

    def test_serve_help(self):
        """serve --help → shows transport/host/port options."""
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "transport" in result.stdout
        assert "host" in result.stdout
        assert "port" in result.stdout
