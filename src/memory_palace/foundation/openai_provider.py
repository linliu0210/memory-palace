"""OpenAI-compatible LLM provider.

Satisfies the ``LLMProvider`` Protocol via structural typing.
Supports any OpenAI-compatible API (OpenAI, DeepSeek, Ollama, vLLM, etc.)

Ref: SPEC v2.0 §7.2, §8.1
"""

from __future__ import annotations

import httpx

from memory_palace.foundation.llm import ModelConfig, get_api_key


class OpenAIProvider:
    """OpenAI-compatible LLM provider.

    Satisfies the LLMProvider protocol via structural typing.
    Supports any OpenAI-compatible API (OpenAI, DeepSeek, Ollama, vLLM, etc.)

    Args:
        model_config: LLM connection parameters. Falls back to defaults from ModelConfig.
        timeout: HTTP request timeout in seconds (default: 30).
    """

    def __init__(
        self,
        model_config: ModelConfig | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._config = model_config or ModelConfig()
        self._api_key = get_api_key(self._config.provider)
        self._timeout = timeout

    async def complete(self, prompt: str, response_format: type | None = None) -> str:
        """Send prompt to LLM API and return response text.

        Args:
            prompt: The user prompt to send.
            response_format: When not None, requests ``json_object`` response format.

        Returns:
            The assistant's response text.

        Raises:
            ConnectionError: If the API endpoint is unreachable.
            RuntimeError: If the API returns a non-200 status code.
        """
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        body: dict = {
            "model": self._config.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self._config.max_tokens,
        }
        if response_format is not None:
            body["response_format"] = {"type": "json_object"}

        url = f"{self._config.base_url}/chat/completions"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, json=body, headers=headers)
        except httpx.ConnectError as exc:
            raise ConnectionError(
                f"Failed to connect to LLM API at {self._config.base_url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise ConnectionError(
                f"LLM API request timed out after {self._timeout}s: {exc}"
            ) from exc

        if resp.status_code != 200:
            raise RuntimeError(f"LLM API error {resp.status_code}: {resp.text}")

        return resp.json()["choices"][0]["message"]["content"]
