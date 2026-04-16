"""OpenAI-compatible LLM provider.

Satisfies the ``LLMProvider`` Protocol via structural typing.
Supports any OpenAI-compatible API (OpenAI, DeepSeek, Ollama, vLLM, etc.)

Ref: SPEC v2.0 §7.2, §8.1
"""

from __future__ import annotations

import re

import litellm

from memory_palace.foundation.llm import ModelConfig, get_api_key

# Providers that do NOT support response_format: json_object
_NO_JSON_FORMAT_PROVIDERS = {"minimax"}


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
        kwargs: dict = {
            "model": f"{self._config.provider}/{self._config.model_id}",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self._config.max_tokens,
            "timeout": self._timeout,
        }
        if self._api_key:
            kwargs["api_key"] = self._api_key
        if self._config.base_url:
            kwargs["api_base"] = self._config.base_url
        if (
            response_format is not None
            and self._config.provider not in _NO_JSON_FORMAT_PROVIDERS
        ):
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await litellm.acompletion(**kwargs)
        except litellm.Timeout as exc:
            raise ConnectionError(
                f"LLM API request timed out after {self._timeout}s: {exc}"
            ) from exc
        except litellm.APIConnectionError as exc:
            raise ConnectionError(
                f"Failed to connect to LLM API at {self._config.base_url}: {exc}"
            ) from exc
        except litellm.APIError as exc:
            raise RuntimeError(f"LLM API error: {exc}") from exc

        content = response.choices[0].message.content
        # Strip <think>...</think> tags from reasoning models (MiniMax, DeepSeek, etc.)
        content = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL)
        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        fence_match = re.match(
            r"^\s*```(?:json|JSON)?\s*\n(.*?)\n\s*```\s*$", content, re.DOTALL
        )
        if fence_match:
            content = fence_match.group(1)
        return content
