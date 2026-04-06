"""
Round 4: Engine — ReconcileEngine Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §4.1 S-12, §4.5

ReconcileEngine uses LLM to decide: ADD / UPDATE / DELETE / NOOP.
All tests use MockLLM — no real LLM calls.
"""

import pytest


class TestReconcileDecisions:
    """ReconcileEngine decision routing."""

    @pytest.mark.asyncio
    async def test_returns_add_for_new_fact(self, mock_llm_reconcile_add):
        """New fact with no similar existing → ADD."""
        pytest.skip("RED: ReconcileEngine not implemented")

    @pytest.mark.asyncio
    async def test_returns_update_for_similar_fact(self, mock_llm_reconcile_update):
        """Updated preference → UPDATE with target_id."""
        pytest.skip("RED: ReconcileEngine not implemented")

    @pytest.mark.asyncio
    async def test_returns_delete_for_contradiction(self, mock_llm_reconcile_delete):
        """Contradicting fact → DELETE with target_id."""
        pytest.skip("RED: ReconcileEngine not implemented")

    @pytest.mark.asyncio
    async def test_returns_noop_for_duplicate(self, mock_llm_reconcile_noop):
        """Already captured → NOOP."""
        pytest.skip("RED: ReconcileEngine not implemented")


class TestReconcileOutput:
    """ReconcileEngine output format."""

    @pytest.mark.asyncio
    async def test_includes_reason(self, mock_llm_reconcile_add):
        """Result must include a 'reason' string."""
        pytest.skip("RED: ReconcileEngine not implemented")

    @pytest.mark.asyncio
    async def test_includes_target_id_when_applicable(self, mock_llm_reconcile_update):
        """UPDATE/DELETE must include target_id."""
        pytest.skip("RED: ReconcileEngine not implemented")

    @pytest.mark.asyncio
    async def test_handles_malformed_response(self, mock_llm_malformed):
        """Malformed LLM JSON → graceful error, not crash."""
        pytest.skip("RED: ReconcileEngine not implemented")
