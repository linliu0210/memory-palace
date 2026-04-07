"""
Round 1: Foundation — LLM Provider Tests

IMMUTABLE SPEC: These tests define the LLMProvider Protocol contract.
Ref: SPEC v2.0 §4.1 S-3, §7.2

LLMProvider is a Protocol (structural typing). Any object with
`async def complete(prompt, response_format) -> str` satisfies it.
"""

import pytest

from dataclasses import dataclass, field

from memory_palace.foundation.llm import LLMProvider, ModelConfig, get_api_key


@dataclass
class _MockLLM:
    """Local copy matching conftest.MockLLM for direct instantiation in tests."""

    responses: list[str]
    _call_count: int = field(default=0, init=False)
    _prompts_received: list[str] = field(default_factory=list, init=False)

    async def complete(
        self, prompt: str, response_format: type | None = None
    ) -> str:
        self._prompts_received.append(prompt)
        response = self.responses[self._call_count % len(self.responses)]
        self._call_count += 1
        return response


class TestLLMProviderProtocol:
    """LLMProvider Protocol contract verification."""

    def test_protocol_has_complete_method(self):
        """LLMProvider must define async complete(prompt, response_format) -> str."""
        assert hasattr(LLMProvider, "complete")

    def test_mock_llm_satisfies_protocol(self):
        """MockLLM from conftest must satisfy LLMProvider Protocol."""
        mock = _MockLLM(responses=["hello"])
        assert isinstance(mock, LLMProvider)


class TestMockLLM:
    """MockLLM deterministic behavior (from conftest)."""

    @pytest.mark.asyncio
    async def test_returns_preset_responses_in_order(self):
        """MockLLM(['a','b']) → first call 'a', second call 'b'."""
        mock = _MockLLM(responses=["a", "b"])
        assert await mock.complete("p1") == "a"
        assert await mock.complete("p2") == "b"

    @pytest.mark.asyncio
    async def test_cycles_when_exhausted(self):
        """MockLLM(['a']) → call 1 'a', call 2 'a' (wraps around)."""
        mock = _MockLLM(responses=["a"])
        assert await mock.complete("p1") == "a"
        assert await mock.complete("p2") == "a"

    @pytest.mark.asyncio
    async def test_records_prompts_received(self):
        """MockLLM._prompts_received should capture each prompt."""
        mock = _MockLLM(responses=["r"])
        await mock.complete("first")
        await mock.complete("second")
        assert mock._prompts_received == ["first", "second"]


class TestModelConfig:
    """ModelConfig Pydantic model."""

    def test_default_values(self):
        """ModelConfig() defaults: provider=openai, model_id=gpt-4o-mini."""
        cfg = ModelConfig()
        assert cfg.provider == "openai"
        assert cfg.model_id == "gpt-4o-mini"
        assert cfg.base_url == "https://api.openai.com/v1"
        assert cfg.max_tokens == 2000

    def test_custom_values(self):
        """ModelConfig(provider='deepseek', ...) overrides."""
        cfg = ModelConfig(
            provider="deepseek",
            model_id="deepseek-chat",
            base_url="https://api.deepseek.com/v1",
            max_tokens=4000,
        )
        assert cfg.provider == "deepseek"
        assert cfg.model_id == "deepseek-chat"
        assert cfg.base_url == "https://api.deepseek.com/v1"
        assert cfg.max_tokens == 4000


class TestGetApiKey:
    """get_api_key() env resolution."""

    def test_returns_key_when_set(self, monkeypatch):
        """get_api_key('openai') reads OPENAI_API_KEY from env."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
        assert get_api_key("openai") == "sk-test-123"

    def test_returns_none_when_missing(self, monkeypatch):
        """get_api_key('openai') returns None if not set."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        assert get_api_key("openai") is None

    def test_local_returns_none(self):
        """get_api_key('local') always returns None."""
        assert get_api_key("local") is None
