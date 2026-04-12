"""Tests for the OpenAIProvider.

Verifies protocol compliance and error handling.
No real API key required — tests use invalid endpoints.
"""

from unittest.mock import AsyncMock, patch

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
    """Error handling — strict mapping from httpx errors."""

    @pytest.mark.asyncio
    async def test_connect_error_maps_to_connection_error(self):
        """httpx.ConnectError → ConnectionError (strict)."""
        import httpx

        provider = OpenAIProvider(ModelConfig(), timeout=1.0)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("refused")
            with pytest.raises(ConnectionError, match="Failed to connect"):
                await provider.complete("test")

    @pytest.mark.asyncio
    async def test_timeout_maps_to_connection_error(self):
        """httpx.TimeoutException → ConnectionError (strict)."""
        import httpx

        provider = OpenAIProvider(ModelConfig(), timeout=0.5)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ReadTimeout("timed out")
            with pytest.raises(ConnectionError, match="timed out"):
                await provider.complete("test")

    @pytest.mark.asyncio
    async def test_non_200_maps_to_runtime_error(self):
        """Non-200 API response → RuntimeError (strict)."""

        provider = OpenAIProvider(ModelConfig(), timeout=1.0)

        mock_response = AsyncMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            with pytest.raises(RuntimeError, match="429"):
                await provider.complete("test")
