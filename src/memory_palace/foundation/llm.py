"""LLM Provider abstraction layer.

Defines the ``LLMProvider`` Protocol for structural subtyping,
``ModelConfig`` for LLM connection parameters, and ``get_api_key()``
for environment-variable-based API key resolution.

Ref: SPEC v2.0 §7.2, §8.1
"""

import os
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


@runtime_checkable
class LLMProvider(Protocol):
    """Structural-typing protocol for LLM backends.

    Any object with a matching ``complete`` signature satisfies this
    protocol — no inheritance required.
    """

    async def complete(
        self, prompt: str, response_format: type | None = None
    ) -> str: ...


class ModelConfig(BaseModel):
    """LLM connection parameters."""

    provider: str = "openai"
    model_id: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    max_tokens: int = 2000


# ── API key resolution ───────────────────────────────────────────────

ENV_KEY_MAP: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "local": "",
}


def get_api_key(provider: str) -> str | None:
    """Resolve the API key for *provider* from environment variables.

    Resolution rules:
    - Known providers (openai/deepseek/anthropic): look up ``ENV_KEY_MAP``.
    - ``local``: always returns ``None`` (no key needed).
    - Unknown providers: convention ``{PROVIDER}_API_KEY`` (uppercased).

    Returns ``None`` when the env var is absent or the provider is ``local``.
    """
    if provider == "local":
        return None

    env_var = ENV_KEY_MAP.get(provider)
    if env_var is None:
        # Unknown provider → convention: FOO_API_KEY
        env_var = f"{provider.upper()}_API_KEY"

    if not env_var:
        return None

    return os.environ.get(env_var) or None
