"""Tests for EmbeddingProvider Protocol and EmbeddingConfig.

Validates:
- MockEmbedding satisfies the EmbeddingProvider Protocol (structural typing)
- EmbeddingConfig defaults and custom values
- Protocol edge cases (empty input, batch)

Ref: SPEC_V02 §2.1, §7.1
"""

import pytest

from memory_palace.foundation.embedding import EmbeddingConfig, EmbeddingProvider

# ── Protocol compliance ──────────────────────────────────────────────


class TestEmbeddingProtocol:
    """Verify EmbeddingProvider Protocol contracts."""

    def test_mock_satisfies_protocol(self, mock_embedding):
        """MockEmbedding must satisfy EmbeddingProvider at runtime."""
        assert isinstance(mock_embedding, EmbeddingProvider)

    def test_dimension_property(self, mock_embedding):
        """Dimension must be a positive integer."""
        assert mock_embedding.dimension == 8
        assert isinstance(mock_embedding.dimension, int)

    @pytest.mark.asyncio
    async def test_embed_single_text(self, mock_embedding):
        """Single text → list of one vector with correct dimension."""
        result = await mock_embedding.embed(["hello world"])
        assert len(result) == 1
        assert len(result[0]) == mock_embedding.dimension

    @pytest.mark.asyncio
    async def test_embed_batch(self, mock_embedding):
        """Multiple texts → matching number of vectors."""
        texts = ["alpha", "beta", "gamma"]
        result = await mock_embedding.embed(texts)
        assert len(result) == 3
        for vec in result:
            assert len(vec) == mock_embedding.dimension

    @pytest.mark.asyncio
    async def test_embed_empty_list(self, mock_embedding):
        """Empty input → empty output, no crash."""
        result = await mock_embedding.embed([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_deterministic(self, mock_embedding):
        """Same text must produce identical vectors across calls."""
        v1 = await mock_embedding.embed(["test input"])
        v2 = await mock_embedding.embed(["test input"])
        assert v1 == v2

    @pytest.mark.asyncio
    async def test_embed_different_texts_differ(self, mock_embedding):
        """Different texts should produce different vectors."""
        result = await mock_embedding.embed(["text A", "text B"])
        assert result[0] != result[1]

    @pytest.mark.asyncio
    async def test_embed_unit_vector(self, mock_embedding):
        """MockEmbedding vectors should be approximately unit length."""
        result = await mock_embedding.embed(["normalize me"])
        vec = result[0]
        norm = sum(x * x for x in vec) ** 0.5
        assert abs(norm - 1.0) < 1e-6


# ── EmbeddingConfig ──────────────────────────────────────────────────


class TestEmbeddingConfig:
    """Verify EmbeddingConfig defaults and customization."""

    def test_config_defaults(self):
        """Default config: OpenAI, text-embedding-3-small, 1536 dim."""
        cfg = EmbeddingConfig()
        assert cfg.provider == "openai"
        assert cfg.model_id == "text-embedding-3-small"
        assert cfg.dimension == 1536
        assert cfg.batch_size == 64

    def test_config_custom(self):
        """Custom config for local provider."""
        cfg = EmbeddingConfig(
            provider="local",
            model_id="all-MiniLM-L6-v2",
            dimension=384,
            batch_size=32,
        )
        assert cfg.provider == "local"
        assert cfg.model_id == "all-MiniLM-L6-v2"
        assert cfg.dimension == 384
        assert cfg.batch_size == 32

    def test_config_serialization(self):
        """Config round-trips through dict."""
        cfg = EmbeddingConfig(provider="local", dimension=384)
        data = cfg.model_dump()
        restored = EmbeddingConfig(**data)
        assert restored == cfg
