"""OpenAI-compatible embedding provider.

Satisfies the ``EmbeddingProvider`` Protocol via structural typing.
Uses httpx for HTTP calls — consistent with ``OpenAIProvider`` in the
same layer.

Ref: SPEC_V02 §2.1 (F-3b)
"""

from __future__ import annotations

import httpx

from memory_palace.foundation.embedding import EmbeddingConfig
from memory_palace.foundation.llm import get_api_key


class OpenAIEmbedding:
    """OpenAI-compatible embedding provider.

    Satisfies the EmbeddingProvider protocol via structural typing.
    Supports any OpenAI-compatible embedding API.

    Args:
        config: Embedding configuration. Falls back to defaults.
        base_url: API base URL. Defaults to OpenAI.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        config: EmbeddingConfig | None = None,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
    ) -> None:
        self._config = config or EmbeddingConfig()
        self._base_url = base_url
        self._api_key = get_api_key("openai")
        self._timeout = timeout

    @property
    def dimension(self) -> int:
        """Dimensionality of the embedding vectors."""
        return self._config.dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Encode texts into dense vectors via OpenAI Embeddings API.

        Handles batching internally when ``len(texts)`` exceeds
        ``config.batch_size``.

        Args:
            texts: List of text strings to embed. May be empty.

        Returns:
            List of embedding vectors, one per input text.

        Raises:
            ConnectionError: If the API endpoint is unreachable.
            RuntimeError: If the API returns a non-200 status code.
        """
        if not texts:
            return []

        all_vectors: list[list[float]] = []
        batch_size = self._config.batch_size

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            vectors = await self._embed_batch(batch)
            all_vectors.extend(vectors)

        return all_vectors

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Send a single batch to the embeddings API."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        body = {
            "model": self._config.model_id,
            "input": texts,
        }

        url = f"{self._base_url}/embeddings"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=body, headers=headers)
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Failed to connect to Embedding API at {self._base_url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise ConnectionError(
                f"Embedding API request timed out after {self._timeout}s: {exc}"
            ) from exc

        if resp.status_code != 200:
            raise RuntimeError(f"Embedding API error {resp.status_code}: {resp.text}")

        data = resp.json()["data"]
        # API returns objects sorted by index; sort explicitly to be safe
        sorted_data = sorted(data, key=lambda d: d["index"])
        return [d["embedding"] for d in sorted_data]
