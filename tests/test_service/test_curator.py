"""
Round 5: Service — CuratorService Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §4.1 S-15, §4.3

CuratorService (搬运小人) orchestrates:
  Gather → Extract → Reconcile → Execute → Report
v0.1: synchronous, manually triggered.
"""

import pytest


class TestCuratorRun:
    """CuratorService.run() full cycle."""

    @pytest.mark.asyncio
    async def test_run_extracts_facts_from_recent(self, tmp_data_dir, mock_llm_extract):
        """run() scans recent items and extracts facts."""
        pytest.skip("RED: CuratorService not implemented")

    @pytest.mark.asyncio
    async def test_run_reconciles_each_fact(
        self, tmp_data_dir, mock_llm_extract, mock_llm_reconcile_add
    ):
        """Each extracted fact is passed through ReconcileEngine."""
        pytest.skip("RED: CuratorService not implemented")

    @pytest.mark.asyncio
    async def test_run_applies_add_action(
        self, tmp_data_dir, mock_llm_extract, mock_llm_reconcile_add
    ):
        """ADD decision → new MemoryItem saved."""
        pytest.skip("RED: CuratorService not implemented")

    @pytest.mark.asyncio
    async def test_run_applies_update_action(
        self, tmp_data_dir, mock_llm_extract, mock_llm_reconcile_update
    ):
        """UPDATE decision → old superseded, new created."""
        pytest.skip("RED: CuratorService not implemented")

    @pytest.mark.asyncio
    async def test_run_applies_delete_action(
        self, tmp_data_dir, mock_llm_extract, mock_llm_reconcile_delete
    ):
        """DELETE decision → target marked PRUNED."""
        pytest.skip("RED: CuratorService not implemented")

    @pytest.mark.asyncio
    async def test_run_skips_noop(self, tmp_data_dir, mock_llm_extract, mock_llm_reconcile_noop):
        """NOOP decision → no store mutation."""
        pytest.skip("RED: CuratorService not implemented")

    @pytest.mark.asyncio
    async def test_run_returns_complete_report(
        self, tmp_data_dir, mock_llm_extract, mock_llm_reconcile_add
    ):
        """run() returns CuratorReport with all metrics populated."""
        pytest.skip("RED: CuratorService not implemented")

    @pytest.mark.asyncio
    async def test_run_creates_audit_entries(
        self, tmp_data_dir, mock_llm_extract, mock_llm_reconcile_add
    ):
        """Each action produces an AuditEntry."""
        pytest.skip("RED: CuratorService not implemented")


class TestCuratorTrigger:
    """CuratorService.should_trigger() logic."""

    def test_trigger_by_session_count(self, tmp_data_dir):
        """Triggers when session_count >= threshold (default 20)."""
        pytest.skip("RED: CuratorService not implemented")

    def test_trigger_by_timer(self, tmp_data_dir):
        """Triggers when hours since last run >= timer_hours (default 24)."""
        pytest.skip("RED: CuratorService not implemented")

    def test_should_not_trigger_in_cooldown(self, tmp_data_dir):
        """Does NOT trigger if last run was < cooldown_hours ago."""
        pytest.skip("RED: CuratorService not implemented")
