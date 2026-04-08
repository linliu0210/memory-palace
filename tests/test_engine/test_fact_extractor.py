"""
Round 4: Engine — FactExtractor Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §4.1 S-10, §4.5

FactExtractor uses LLM to extract atomic facts from text.
All tests use MockLLM — no real LLM calls.
"""

import pytest

from memory_palace.engine.fact_extractor import FactExtractor
from memory_palace.models.memory import MemoryItem, MemoryType


class TestFactExtractorHappyPath:
    """FactExtractor normal operation with MockLLM."""

    @pytest.mark.asyncio
    async def test_extract_returns_memory_items(self, mock_llm_extract):
        """extract(text) returns list[MemoryItem]."""
        extractor = FactExtractor(llm=mock_llm_extract)
        result = await extractor.extract("用户说喜欢深色模式，正在做DreamEngine项目")
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(item, MemoryItem) for item in result)

    @pytest.mark.asyncio
    async def test_extract_parses_json_array(self, mock_llm_extract):
        """LLM response JSON array is correctly parsed."""
        extractor = FactExtractor(llm=mock_llm_extract)
        result = await extractor.extract("some conversation text")
        assert len(result) == 2
        assert result[0].content == "用户喜欢深色模式"
        assert result[1].content == "用户正在开发DreamEngine项目"

    @pytest.mark.asyncio
    async def test_extract_assigns_importance_from_llm(self, mock_llm_extract):
        """Each item's importance comes from the LLM response."""
        extractor = FactExtractor(llm=mock_llm_extract)
        result = await extractor.extract("some conversation text")
        assert result[0].importance == pytest.approx(0.8)
        assert result[1].importance == pytest.approx(0.6)

    @pytest.mark.asyncio
    async def test_extract_sets_memory_type_to_observation(self, mock_llm_extract):
        """Extracted facts default to MemoryType.OBSERVATION."""
        extractor = FactExtractor(llm=mock_llm_extract)
        result = await extractor.extract("some conversation text")
        assert all(item.memory_type == MemoryType.OBSERVATION for item in result)

    @pytest.mark.asyncio
    async def test_extract_assigns_tags(self, mock_llm_extract):
        """Tags from LLM response are preserved on MemoryItem."""
        extractor = FactExtractor(llm=mock_llm_extract)
        result = await extractor.extract("some conversation text")
        assert result[0].tags == ["preferences"]
        assert result[1].tags == ["projects"]


class TestFactExtractorEdgeCases:
    """FactExtractor error handling."""

    @pytest.mark.asyncio
    async def test_extract_handles_empty_input(self, mock_llm_extract_empty):
        """extract('') should return empty list."""
        extractor = FactExtractor(llm=mock_llm_extract_empty)
        result = await extractor.extract("")
        assert result == []

    @pytest.mark.asyncio
    async def test_extract_handles_malformed_llm_response(self, mock_llm_malformed):
        """Malformed LLM JSON → graceful error, not crash."""
        extractor = FactExtractor(llm=mock_llm_malformed)
        result = await extractor.extract("some text")
        assert result == []
