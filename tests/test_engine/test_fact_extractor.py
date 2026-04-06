"""
Round 4: Engine — FactExtractor Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §4.1 S-10, §4.5

FactExtractor uses LLM to extract atomic facts from text.
All tests use MockLLM — no real LLM calls.
"""

import pytest


class TestFactExtractorHappyPath:
    """FactExtractor normal operation with MockLLM."""

    @pytest.mark.asyncio
    async def test_extract_returns_memory_items(self, mock_llm_extract):
        """extract(text) returns list[MemoryItem]."""
        pytest.skip("RED: FactExtractor not implemented")

    @pytest.mark.asyncio
    async def test_extract_parses_json_array(self, mock_llm_extract):
        """LLM response JSON array is correctly parsed."""
        pytest.skip("RED: FactExtractor not implemented")

    @pytest.mark.asyncio
    async def test_extract_assigns_importance_from_llm(self, mock_llm_extract):
        """Each item's importance comes from the LLM response."""
        pytest.skip("RED: FactExtractor not implemented")

    @pytest.mark.asyncio
    async def test_extract_sets_memory_type_to_observation(self, mock_llm_extract):
        """Extracted facts default to MemoryType.OBSERVATION."""
        pytest.skip("RED: FactExtractor not implemented")

    @pytest.mark.asyncio
    async def test_extract_assigns_tags(self, mock_llm_extract):
        """Tags from LLM response are preserved on MemoryItem."""
        pytest.skip("RED: FactExtractor not implemented")


class TestFactExtractorEdgeCases:
    """FactExtractor error handling."""

    @pytest.mark.asyncio
    async def test_extract_handles_empty_input(self, mock_llm_extract_empty):
        """extract('') should return empty list."""
        pytest.skip("RED: FactExtractor not implemented")

    @pytest.mark.asyncio
    async def test_extract_handles_malformed_llm_response(self, mock_llm_malformed):
        """Malformed LLM JSON → graceful error, not crash."""
        pytest.skip("RED: FactExtractor not implemented")
