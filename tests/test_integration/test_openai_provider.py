"""Tests for the OpenAIProvider.

Verifies protocol compliance and error handling.
No real API key required — tests use invalid endpoints.
"""

import pytest

from memory_palace.foundation.llm import LLMProvider, ModelConfig
from memory_palace.foundation.openai_provider import OpenAIProvider


class TestOpenAIProviderProtocol:
    """OpenAIProvider satisfies the LLMProvider protocol."""

    def test_satisfies_protocol(self):
        """OpenAIProvider is recognized as a LLMProvider."""
        provider = OpenAIProvider()
        assert isinstance(provider, LLMProvider)

    def test_default_model_config(self):
        """When no config given, uses ModelConfig defaults."""
        provider = OpenAIProvider()
        assert provider._config.provider == "openai"
        assert provider._config.model_id == "gpt-4o-mini"

    def test_custom_model_config(self):
        """Custom ModelConfig is stored correctly."""
        cfg = ModelConfig(provider="deepseek", model_id="deepseek-chat", base_url="https://api.deepseek.com/v1")
        provider = OpenAIProvider(model_config=cfg)
        assert provider._config.provider == "deepseek"
        assert provider._config.model_id == "deepseek-chat"


class TestOpenAIProviderErrors:
    """Error handling for unreachable or invalid endpoints."""

    @pytest.mark.asyncio
    async def test_connection_error_on_invalid_url(self):
        """Connection to an invalid URL raises ConnectionError."""
        provider = OpenAIProvider(
            ModelConfig(base_url="http://localhost:1"),
            timeout=1.0,
        )
        with pytest.raises((ConnectionError, RuntimeError)):
            await provider.complete("test")

    @pytest.mark.asyncio
    async def test_timeout_raises_connection_error(self):
        """Timeout on slow endpoint raises ConnectionError."""
        provider = OpenAIProvider(
            ModelConfig(base_url="http://10.255.255.1"),  # non-routable
            timeout=0.5,
        )
        with pytest.raises((ConnectionError, RuntimeError)):
            await provider.complete("test")
