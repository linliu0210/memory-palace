"""Tests for OpenAIEmbedding provider.

Validates:
- Correct API call format (mock httpx)
- Batching behavior
- Error handling (connection error, timeout, non-200)

Ref: SPEC_V02 §2.1 (F-3b)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from memory_palace.foundation.embedding import EmbeddingConfig, EmbeddingProvider
from memory_palace.foundation.openai_embedding import OpenAIEmbedding


class TestOpenAIEmbeddingProtocol:
    """Verify OpenAIEmbedding satisfies the Protocol."""

    def test_satisfies_protocol(self):
        """OpenAIEmbedding must satisfy EmbeddingProvider at runtime."""
        provider = OpenAIEmbedding()
        assert isinstance(provider, EmbeddingProvider)

    def test_dimension(self):
        """Default dimension is 1536."""
        provider = OpenAIEmbedding()
        assert provider.dimension == 1536

    def test_custom_dimension(self):
        """Custom config changes dimension."""
        cfg = EmbeddingConfig(dimension=3072)
        provider = OpenAIEmbedding(config=cfg)
        assert provider.dimension == 3072


class TestOpenAIEmbedAPI:
    """Verify API call mechanics with mocked httpx."""

    @pytest.mark.asyncio
    async def test_embed_calls_api(self):
        """embed() should POST to /embeddings with correct body."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"index": 0, "embedding": [0.1, 0.2, 0.3]},
            ]
        }

        provider = OpenAIEmbedding(
            config=EmbeddingConfig(model_id="text-embedding-3-small", dimension=3),
            base_url="https://test.api.com/v1",
        )

        with patch("memory_palace.foundation.openai_embedding.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await provider.embed(["hello"])

        assert len(result) == 1
        assert result[0] == [0.1, 0.2, 0.3]

        # Verify the POST call
        call_args = mock_instance.post.call_args
        assert call_args[0][0] == "https://test.api.com/v1/embeddings"
        body = call_args[1]["json"]
        assert body["model"] == "text-embedding-3-small"
        assert body["input"] == ["hello"]

    @pytest.mark.asyncio
    async def test_embed_empty_returns_empty(self):
        """Empty input should return empty without API call."""
        provider = OpenAIEmbedding()
        result = await provider.embed([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_sorts_by_index(self):
        """API results should be sorted by index."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"index": 1, "embedding": [0.4, 0.5, 0.6]},
                {"index": 0, "embedding": [0.1, 0.2, 0.3]},
            ]
        }

        provider = OpenAIEmbedding(
            config=EmbeddingConfig(dimension=3),
        )

        with patch("memory_palace.foundation.openai_embedding.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            result = await provider.embed(["a", "b"])

        assert result[0] == [0.1, 0.2, 0.3]  # index 0 first
        assert result[1] == [0.4, 0.5, 0.6]  # index 1 second


class TestOpenAIEmbedErrors:
    """Verify error handling."""

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """ConnectError → ConnectionError."""
        provider = OpenAIEmbedding(base_url="https://unreachable.test")

        with patch("memory_palace.foundation.openai_embedding.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.ConnectError("connect failed")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            with pytest.raises(ConnectionError, match="Failed to connect"):
                await provider.embed(["test"])

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        """TimeoutException → ConnectionError."""
        provider = OpenAIEmbedding(timeout=0.001)

        with patch("memory_palace.foundation.openai_embedding.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.ReadTimeout("timeout")
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            with pytest.raises(ConnectionError, match="timed out"):
                await provider.embed(["test"])

    @pytest.mark.asyncio
    async def test_api_error_status(self):
        """Non-200 status → RuntimeError."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"

        provider = OpenAIEmbedding()

        with patch("memory_palace.foundation.openai_embedding.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = mock_instance

            with pytest.raises(RuntimeError, match="429"):
                await provider.embed(["test"])
