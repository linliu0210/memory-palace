"""Tests for LocalEmbedding provider.

Validates:
- Friendly ImportError when sentence-transformers is missing
- Correct behavior with mocked sentence-transformers
- Protocol compliance

Ref: SPEC_V02 §2.1 (F-3c)
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from memory_palace.foundation.embedding import EmbeddingConfig, EmbeddingProvider


class TestLocalEmbeddingImportError:
    """Verify friendly error when sentence-transformers is missing."""

    def test_import_error_message(self):
        """Missing sentence-transformers raises ImportError with install hint."""
        # Temporarily hide the module
        with patch.dict(sys.modules, {"sentence_transformers": None}):
            # Remove cached local_embedding module to trigger fresh import
            sys.modules.pop("memory_palace.foundation.local_embedding", None)

            with pytest.raises(ImportError, match="pip install memory-palace\\[local\\]"):
                from memory_palace.foundation.local_embedding import LocalEmbedding  # noqa: F811

                LocalEmbedding()


class TestLocalEmbeddingMocked:
    """Verify LocalEmbedding behavior with mocked sentence-transformers."""

    def _make_provider(self):
        """Create LocalEmbedding with mocked sentence-transformers."""
        mock_st = MagicMock()
        mock_model = MagicMock()

        # Create a mock array-like object that behaves like numpy output
        class FakeArray:
            """Minimal ndarray-like for testing .tolist()."""

            def __init__(self, data):
                self._data = data

            def tolist(self):
                return self._data

        mock_model.encode.return_value = [
            FakeArray([0.1, 0.2, 0.3, 0.4]),
            FakeArray([0.5, 0.6, 0.7, 0.8]),
        ]
        mock_st.SentenceTransformer.return_value = mock_model

        with patch.dict(sys.modules, {"sentence_transformers": mock_st}):
            # Remove cached module to force re-import with mock
            sys.modules.pop("memory_palace.foundation.local_embedding", None)
            from memory_palace.foundation.local_embedding import LocalEmbedding

            cfg = EmbeddingConfig(
                provider="local",
                model_id="all-MiniLM-L6-v2",
                dimension=4,
                batch_size=32,
            )
            provider = LocalEmbedding(config=cfg)

        return provider, mock_model

    def test_satisfies_protocol(self):
        """LocalEmbedding must satisfy EmbeddingProvider at runtime."""
        provider, _ = self._make_provider()
        assert isinstance(provider, EmbeddingProvider)

    def test_dimension(self):
        """Dimension matches config."""
        provider, _ = self._make_provider()
        assert provider.dimension == 4

    @pytest.mark.asyncio
    async def test_embed_calls_encode(self):
        """embed() delegates to SentenceTransformer.encode()."""
        provider, mock_model = self._make_provider()

        result = await provider.embed(["text A", "text B"])

        mock_model.encode.assert_called_once_with(["text A", "text B"], batch_size=32)
        assert len(result) == 2
        assert result[0] == pytest.approx([0.1, 0.2, 0.3, 0.4])

    @pytest.mark.asyncio
    async def test_embed_empty(self):
        """Empty input returns empty without calling encode."""
        provider, mock_model = self._make_provider()

        result = await provider.embed([])

        assert result == []
        mock_model.encode.assert_not_called()

    @pytest.mark.asyncio
    async def test_embed_returns_plain_lists(self):
        """Output should be plain Python lists, not numpy arrays."""
        provider, _ = self._make_provider()

        result = await provider.embed(["test"])

        # Ensure we got plain lists, not numpy types
        assert isinstance(result[0], list)
        assert isinstance(result[0][0], float)
