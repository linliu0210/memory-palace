"""
Round 4: Engine — ReconcileEngine Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §4.1 S-12, §4.5

ReconcileEngine uses LLM to decide: ADD / UPDATE / DELETE / NOOP.
All tests use MockLLM — no real LLM calls.
"""

import pytest

from memory_palace.engine.reconcile import ReconcileEngine
from memory_palace.models.memory import MemoryItem, MemoryTier, MemoryType


def _make_memory(content: str = "existing fact", memory_id: str = "TARGET_ID") -> MemoryItem:
    """Helper: create a MemoryItem for testing."""
    return MemoryItem(
        id=memory_id,
        content=content,
        memory_type=MemoryType.OBSERVATION,
        tier=MemoryTier.RECALL,
        importance=0.5,
    )


class TestReconcileDecisions:
    """ReconcileEngine decision routing."""

    @pytest.mark.asyncio
    async def test_returns_add_for_new_fact(self, mock_llm_reconcile_add):
        """New fact with no similar existing → ADD."""
        engine = ReconcileEngine(llm=mock_llm_reconcile_add)
        result = await engine.reconcile("brand new fact", [])
        assert result["action"] == "ADD"

    @pytest.mark.asyncio
    async def test_returns_update_for_similar_fact(self, mock_llm_reconcile_update):
        """Updated preference → UPDATE with target_id."""
        engine = ReconcileEngine(llm=mock_llm_reconcile_update)
        existing = [_make_memory("user likes dark mode")]
        result = await engine.reconcile("user now prefers light mode", existing)
        assert result["action"] == "UPDATE"
        assert result["target_id"] == "TARGET_ID"

    @pytest.mark.asyncio
    async def test_returns_delete_for_contradiction(self, mock_llm_reconcile_delete):
        """Contradicting fact → DELETE with target_id."""
        engine = ReconcileEngine(llm=mock_llm_reconcile_delete)
        existing = [_make_memory("user likes cats")]
        result = await engine.reconcile("user is allergic to cats", existing)
        assert result["action"] == "DELETE"
        assert result["target_id"] == "TARGET_ID"

    @pytest.mark.asyncio
    async def test_returns_noop_for_duplicate(self, mock_llm_reconcile_noop):
        """Already captured → NOOP."""
        engine = ReconcileEngine(llm=mock_llm_reconcile_noop)
        existing = [_make_memory("user likes dark mode")]
        result = await engine.reconcile("user likes dark mode", existing)
        assert result["action"] == "NOOP"


class TestReconcileOutput:
    """ReconcileEngine output format."""

    @pytest.mark.asyncio
    async def test_includes_reason(self, mock_llm_reconcile_add):
        """Result must include a 'reason' string."""
        engine = ReconcileEngine(llm=mock_llm_reconcile_add)
        result = await engine.reconcile("new fact", [])
        assert "reason" in result
        assert isinstance(result["reason"], str)
        assert len(result["reason"]) > 0

    @pytest.mark.asyncio
    async def test_includes_target_id_when_applicable(self, mock_llm_reconcile_update):
        """UPDATE/DELETE must include target_id."""
        engine = ReconcileEngine(llm=mock_llm_reconcile_update)
        existing = [_make_memory("old fact")]
        result = await engine.reconcile("updated fact", existing)
        assert result["target_id"] is not None

    @pytest.mark.asyncio
    async def test_handles_malformed_response(self, mock_llm_malformed):
        """Malformed LLM JSON → graceful error, not crash."""
        engine = ReconcileEngine(llm=mock_llm_malformed)
        with pytest.raises(ValueError):
            await engine.reconcile("some fact", [])
