"""Tests for the OpenAIProvider.

Verifies protocol compliance and error handling.
No real API key required — tests use invalid endpoints.
"""

from unittest.mock import AsyncMock, patch

import litellm
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
        cfg = ModelConfig(
            provider="deepseek",
            model_id="deepseek-chat",
            base_url="https://api.deepseek.com/v1",
        )
        provider = OpenAIProvider(model_config=cfg)
        assert provider._config.provider == "deepseek"
        assert provider._config.model_id == "deepseek-chat"
        assert provider._config.base_url == "https://api.deepseek.com/v1"


class TestOpenAIProviderErrors:
    """Error handling — strict mapping from litellm errors."""

    @pytest.mark.asyncio
    async def test_connect_error_maps_to_connection_error(self):
        """litellm.APIConnectionError → ConnectionError (strict)."""
        provider = OpenAIProvider(ModelConfig(), timeout=1.0)

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = litellm.APIConnectionError(
                message="refused",
                llm_provider="openai",
                model="gpt-4o-mini",
            )
            with pytest.raises(ConnectionError, match="Failed to connect"):
                await provider.complete("test")

    @pytest.mark.asyncio
    async def test_timeout_maps_to_connection_error(self):
        """litellm.Timeout → ConnectionError (strict)."""
        provider = OpenAIProvider(ModelConfig(), timeout=0.5)

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = litellm.Timeout(
                message="timed out",
                model="gpt-4o-mini",
                llm_provider="openai",
            )
            with pytest.raises(ConnectionError, match="timed out"):
                await provider.complete("test")

    @pytest.mark.asyncio
    async def test_api_error_maps_to_runtime_error(self):
        """litellm.APIError → RuntimeError (strict)."""
        provider = OpenAIProvider(ModelConfig(), timeout=1.0)

        with patch("litellm.acompletion", new_callable=AsyncMock) as mock_completion:
            mock_completion.side_effect = litellm.APIError(
                message="Rate limit exceeded",
                status_code=429,
                model="gpt-4o-mini",
                llm_provider="openai",
            )
            with pytest.raises(RuntimeError, match="Rate limit exceeded"):
                await provider.complete("test")
