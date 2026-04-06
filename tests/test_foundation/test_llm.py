"""
Round 1: Foundation — LLM Provider Tests

IMMUTABLE SPEC: These tests define the LLMProvider Protocol contract.
Ref: SPEC v2.0 §4.1 S-3, §7.2

LLMProvider is a Protocol (structural typing). Any object with
`async def complete(prompt, response_format) -> str` satisfies it.
"""

import pytest


class TestLLMProviderProtocol:
    """LLMProvider Protocol contract verification."""

    def test_protocol_has_complete_method(self):
        """LLMProvider must define async complete(prompt, response_format) -> str."""
        pytest.skip("RED: LLMProvider not implemented")

    def test_mock_llm_satisfies_protocol(self):
        """MockLLM from conftest must satisfy LLMProvider Protocol."""
        pytest.skip("RED: LLMProvider not implemented")


class TestMockLLM:
    """MockLLM deterministic behavior (from conftest)."""

    @pytest.mark.asyncio
    async def test_returns_preset_responses_in_order(self):
        """MockLLM(['a','b']) → first call 'a', second call 'b'."""
        pytest.skip("RED: test infrastructure validation")

    @pytest.mark.asyncio
    async def test_cycles_when_exhausted(self):
        """MockLLM(['a']) → call 1 'a', call 2 'a' (wraps around)."""
        pytest.skip("RED: test infrastructure validation")

    @pytest.mark.asyncio
    async def test_records_prompts_received(self):
        """MockLLM._prompts_received should capture each prompt."""
        pytest.skip("RED: test infrastructure validation")


class TestModelConfig:
    """ModelConfig Pydantic model."""

    def test_default_values(self):
        """ModelConfig() defaults: provider=openai, model_id=gpt-4o-mini."""
        pytest.skip("RED: ModelConfig not implemented")

    def test_custom_values(self):
        """ModelConfig(provider='deepseek', ...) overrides."""
        pytest.skip("RED: ModelConfig not implemented")


class TestGetApiKey:
    """get_api_key() env resolution."""

    def test_returns_key_when_set(self, monkeypatch):
        """get_api_key('openai') reads OPENAI_API_KEY from env."""
        pytest.skip("RED: get_api_key not implemented")

    def test_returns_none_when_missing(self, monkeypatch):
        """get_api_key('openai') returns None if not set."""
        pytest.skip("RED: get_api_key not implemented")

    def test_local_returns_none(self):
        """get_api_key('local') always returns None."""
        pytest.skip("RED: get_api_key not implemented")
