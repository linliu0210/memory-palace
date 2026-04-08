"""
Round 5: Service — CuratorService Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §4.1 S-15, §4.3

CuratorService (搬运小人) orchestrates:
  Gather → Extract → Reconcile → Execute → Report
v0.1: synchronous, manually triggered.
"""

import json
from datetime import datetime, timedelta

import pytest

from tests.conftest import MockLLM

from memory_palace.foundation.audit_log import AuditLog
from memory_palace.models.memory import MemoryItem, MemoryStatus, MemoryTier, MemoryType
from memory_palace.service.curator import CuratorService
from memory_palace.store.recall_store import RecallStore


def _seed_recall(tmp_data_dir, n=3):
    """Helper: seed RecallStore with n items for curation."""
    recall = RecallStore(tmp_data_dir)
    items = []
    for i in range(n):
        item = MemoryItem(
            content=f"种子记忆内容 {i}",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.RECALL,
            importance=0.5,
        )
        recall.insert(item)
        items.append(item)
    return items


class TestCuratorRun:
    """CuratorService.run() full cycle."""

    @pytest.mark.asyncio
    async def test_run_extracts_facts_from_recent(self, tmp_data_dir, mock_llm_extract):
        """run() scans recent items and extracts facts."""
        _seed_recall(tmp_data_dir)

        curator = CuratorService(tmp_data_dir, llm=mock_llm_extract)
        report = await curator.run()

        assert report.facts_extracted >= 1

    @pytest.mark.asyncio
    async def test_run_reconciles_each_fact(
        self, tmp_data_dir, mock_llm_extract, mock_llm_reconcile_add
    ):
        """Each extracted fact is passed through ReconcileEngine."""
        _seed_recall(tmp_data_dir)

        # Combine extract + reconcile responses:
        # First call = extract (returns 2 facts), subsequent calls = reconcile (ADD)
        combined = MockLLM(
            responses=[
                '[{"content": "事实一", "importance": 0.5, "tags": []}, '
                '{"content": "事实二", "importance": 0.6, "tags": []}]',
                '{"action": "ADD", "target_id": null, "reason": "new info"}',
                '{"action": "ADD", "target_id": null, "reason": "new info"}',
            ]
        )
        curator = CuratorService(tmp_data_dir, llm=combined)
        report = await curator.run()

        assert report.facts_extracted == 2

    @pytest.mark.asyncio
    async def test_run_applies_add_action(
        self, tmp_data_dir, mock_llm_extract, mock_llm_reconcile_add
    ):
        """ADD decision → new MemoryItem saved."""
        _seed_recall(tmp_data_dir)

        combined = MockLLM(
            responses=[
                '[{"content": "新发现的事实", "importance": 0.5, "tags": []}]',
                '{"action": "ADD", "target_id": null, "reason": "genuinely new"}',
            ]
        )
        curator = CuratorService(tmp_data_dir, llm=combined)
        report = await curator.run()

        assert report.memories_created >= 1

    @pytest.mark.asyncio
    async def test_run_applies_update_action(
        self, tmp_data_dir, mock_llm_extract, mock_llm_reconcile_update
    ):
        """UPDATE decision → old superseded, new created."""
        seeds = _seed_recall(tmp_data_dir)
        target_id = seeds[0].id

        combined = MockLLM(
            responses=[
                '[{"content": "更新的事实", "importance": 0.5, "tags": []}]',
                json.dumps(
                    {"action": "UPDATE", "target_id": target_id, "reason": "updated info"}
                ),
            ]
        )
        curator = CuratorService(tmp_data_dir, llm=combined)
        report = await curator.run()

        assert report.memories_updated >= 1

        # Old item should be superseded
        recall = RecallStore(tmp_data_dir)
        old = recall.get(target_id)
        assert old is not None
        assert old.status == MemoryStatus.SUPERSEDED

    @pytest.mark.asyncio
    async def test_run_applies_delete_action(
        self, tmp_data_dir, mock_llm_extract, mock_llm_reconcile_delete
    ):
        """DELETE decision → target marked PRUNED."""
        seeds = _seed_recall(tmp_data_dir)
        target_id = seeds[0].id

        combined = MockLLM(
            responses=[
                '[{"content": "矛盾事实", "importance": 0.5, "tags": []}]',
                json.dumps(
                    {"action": "DELETE", "target_id": target_id, "reason": "contradicted"}
                ),
            ]
        )
        curator = CuratorService(tmp_data_dir, llm=combined)
        report = await curator.run()

        assert report.memories_pruned >= 1

        recall = RecallStore(tmp_data_dir)
        old = recall.get(target_id)
        assert old is not None
        assert old.status == MemoryStatus.PRUNED

    @pytest.mark.asyncio
    async def test_run_skips_noop(self, tmp_data_dir, mock_llm_extract, mock_llm_reconcile_noop):
        """NOOP decision → no store mutation."""
        seeds = _seed_recall(tmp_data_dir)

        combined = MockLLM(
            responses=[
                '[{"content": "已知事实", "importance": 0.5, "tags": []}]',
                '{"action": "NOOP", "target_id": null, "reason": "already captured"}',
            ]
        )
        curator = CuratorService(tmp_data_dir, llm=combined)

        recall = RecallStore(tmp_data_dir)
        count_before = recall.count()

        report = await curator.run()

        count_after = recall.count()
        assert count_after == count_before
        assert report.memories_created == 0
        assert report.memories_updated == 0
        assert report.memories_pruned == 0

    @pytest.mark.asyncio
    async def test_run_returns_complete_report(
        self, tmp_data_dir, mock_llm_extract, mock_llm_reconcile_add
    ):
        """run() returns CuratorReport with all metrics populated."""
        _seed_recall(tmp_data_dir)

        combined = MockLLM(
            responses=[
                '[{"content": "报告事实", "importance": 0.5, "tags": []}]',
                '{"action": "ADD", "target_id": null, "reason": "new info"}',
            ]
        )
        curator = CuratorService(tmp_data_dir, llm=combined)
        report = await curator.run()

        assert report.run_id is not None
        assert report.triggered_at is not None
        assert report.trigger_reason == "manual"
        assert report.facts_extracted >= 0
        assert report.duration_seconds >= 0

    @pytest.mark.asyncio
    async def test_run_creates_audit_entries(
        self, tmp_data_dir, mock_llm_extract, mock_llm_reconcile_add
    ):
        """Each action produces an AuditEntry."""
        _seed_recall(tmp_data_dir)

        combined = MockLLM(
            responses=[
                '[{"content": "审计事实", "importance": 0.5, "tags": []}]',
                '{"action": "ADD", "target_id": null, "reason": "new fact"}',
            ]
        )
        curator = CuratorService(tmp_data_dir, llm=combined)
        await curator.run()

        audit = AuditLog(tmp_data_dir)
        entries = audit.read()
        # At least one audit entry for the ADD action
        assert len(entries) >= 1


class TestCuratorTrigger:
    """CuratorService.should_trigger() logic."""

    def test_trigger_by_session_count(self, tmp_data_dir):
        """Triggers when session_count >= threshold (default 20)."""
        llm = MockLLM(responses=["[]"])
        curator = CuratorService(tmp_data_dir, llm=llm)
        curator._session_count = 25
        curator._last_run_at = datetime.now() - timedelta(hours=2)

        should, reason = curator.should_trigger()
        assert should is True
        assert reason == "session_count"

    def test_trigger_by_timer(self, tmp_data_dir):
        """Triggers when hours since last run >= timer_hours (default 24)."""
        llm = MockLLM(responses=["[]"])
        curator = CuratorService(tmp_data_dir, llm=llm)
        curator._last_run_at = datetime.now() - timedelta(hours=30)

        should, reason = curator.should_trigger()
        assert should is True
        assert reason == "timer"

    def test_should_not_trigger_in_cooldown(self, tmp_data_dir):
        """Does NOT trigger if last run was < cooldown_hours ago."""
        llm = MockLLM(responses=["[]"])
        curator = CuratorService(tmp_data_dir, llm=llm)
        curator._last_run_at = datetime.now() - timedelta(minutes=30)
        curator._session_count = 25  # Would trigger but for cooldown

        should, reason = curator.should_trigger()
        assert should is False
