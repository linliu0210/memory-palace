"""Local embedding provider using sentence-transformers.

Satisfies the ``EmbeddingProvider`` Protocol via structural typing.
Requires ``sentence-transformers`` (optional dependency: ``pip install memory-palace[local]``).

Ref: SPEC_V02 §2.1 (F-3c), §1.5
"""

from __future__ import annotations

from memory_palace.foundation.embedding import EmbeddingConfig


class LocalEmbedding:
    """Local embedding provider using sentence-transformers.

    Satisfies the EmbeddingProvider protocol via structural typing.
    Runs inference locally — zero API cost, works offline.

    Args:
        config: Embedding configuration. Defaults to ``all-MiniLM-L6-v2``.

    Raises:
        ImportError: If sentence-transformers is not installed.
    """

    def __init__(self, config: EmbeddingConfig | None = None) -> None:
        self._config = config or EmbeddingConfig(
            provider="local",
            model_id="all-MiniLM-L6-v2",
            dimension=384,
        )

        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for local embeddings. "
                "Install it with: pip install memory-palace[local]"
            ) from None

        self._model = SentenceTransformer(self._config.model_id)

    @property
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors."""
        return self._config.dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Encode texts into dense vectors using local model.

        Args:
            texts: List of text strings to embed. May be empty.

        Returns:
            List of embedding vectors, one per input text.
        """
        if not texts:
            return []

        # sentence-transformers.encode() is synchronous but fast for local models
        embeddings = self._model.encode(texts, batch_size=self._config.batch_size)
        # Convert numpy arrays to plain Python lists
        return [vec.tolist() for vec in embeddings]
