"""Embedding provider abstraction layer.

Defines the ``EmbeddingProvider`` Protocol for structural subtyping
and ``EmbeddingConfig`` for embedding backend selection.

Ref: SPEC_V02 §2.1 (F-3a), §1.5
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Structural-typing protocol for embedding backends.

    Any object with matching ``embed`` and ``dimension`` satisfies this
    protocol — no inheritance required.
    """

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Encode texts into dense vectors.

        Args:
            texts: List of text strings to embed. May be empty.

        Returns:
            List of embedding vectors, one per input text.
            Each vector has exactly ``self.dimension`` floats.
        """
        ...

    @property
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors."""
        ...


class EmbeddingConfig(BaseModel):
    """Embedding backend configuration.

    Attributes:
        provider: Backend selector — ``"openai"`` or ``"local"``.
        model_id: Model identifier for the selected provider.
        dimension: Embedding vector dimensionality.
        batch_size: Maximum texts per API call.
    """

    provider: str = "openai"
    model_id: str = "text-embedding-3-small"
    dimension: int = 1536
    batch_size: int = 64
