"""
Memory Palace — Shared Test Fixtures

IMMUTABLE CONTRACT: These fixtures define the test infrastructure.
Mock objects here represent the LLM boundary — they are deterministic
substitutes for non-deterministic external services.

Ref: SPEC v2.0 §7.2, CONVENTIONS.md Rule 2.5
"""

import json
from dataclasses import dataclass, field

import pytest

# ============================================================
# LLM Mock — Protocol-compatible deterministic substitute
# ============================================================


@dataclass
class MockLLM:
    """Deterministic LLM Mock. Returns preset responses in order.

    Implements LLMProvider Protocol:
        async def complete(self, prompt: str,
                           response_format: type | None = None) -> str
    """

    responses: list[str]
    _call_count: int = field(default=0, init=False)
    _prompts_received: list[str] = field(default_factory=list, init=False)

    async def complete(self, prompt: str, response_format: type | None = None) -> str:
        self._prompts_received.append(prompt)
        response = self.responses[self._call_count % len(self.responses)]
        self._call_count += 1
        return response


# ============================================================
# Fixtures: LLM Mocks (pre-configured for common scenarios)
# ============================================================


@pytest.fixture
def mock_llm_extract():
    """Mock LLM that returns 2 atomic facts (FactExtractor scenario)."""
    return MockLLM(
        responses=[
            '[{"content": "用户喜欢深色模式", "importance": 0.8, "tags": ["preferences"]},'
            '{"content": "用户正在开发DreamEngine项目", "importance": 0.6, "tags": ["projects"]}]'
        ]
    )


@pytest.fixture
def mock_llm_extract_single():
    """Mock LLM that returns 1 atomic fact."""
    return MockLLM(
        responses=[
            '[{"content": "用户偏好Python语言", "importance": 0.7, "tags": ["preferences"]}]'
        ]
    )


@pytest.fixture
def mock_llm_extract_empty():
    """Mock LLM that returns empty fact list."""
    return MockLLM(responses=["[]"])


@pytest.fixture
def mock_llm_reconcile_add():
    """Mock LLM that always returns ADD decision."""
    return MockLLM(
        responses=['{"action": "ADD", "target_id": null, "reason": "genuinely new information"}']
    )


@pytest.fixture
def mock_llm_reconcile_update():
    """Mock LLM that always returns UPDATE decision."""
    return MockLLM(
        responses=[
            '{"action": "UPDATE", "target_id": "TARGET_ID", "reason": "updated preference"}'
        ]
    )


@pytest.fixture
def mock_llm_reconcile_delete():
    """Mock LLM that always returns DELETE decision."""
    return MockLLM(
        responses=[
            '{"action": "DELETE", "target_id": "TARGET_ID", "reason": "contradicted by new info"}'
        ]
    )


@pytest.fixture
def mock_llm_reconcile_noop():
    """Mock LLM that always returns NOOP decision."""
    return MockLLM(
        responses=['{"action": "NOOP", "target_id": null, "reason": "already captured"}']
    )


@pytest.fixture
def mock_llm_malformed():
    """Mock LLM that returns malformed JSON."""
    return MockLLM(responses=["this is not valid json {{{"])


# ============================================================
# Fixtures: ReflectionEngine Mocks
# ============================================================


@pytest.fixture
def mock_llm_reflect():
    """Mock LLM returning a valid single-insight reflection response."""
    response = json.dumps([
        {
            "content": "用户正在从Python学习者转变为ML实践者",
            "source_ids": ["id1", "id2"],
        }
    ])
    return MockLLM(responses=[response])


@pytest.fixture
def mock_llm_reflect_many():
    """Mock LLM returning 5 insights (for testing max_insights cap)."""
    response = json.dumps([
        {"content": f"Insight {i}", "source_ids": []} for i in range(5)
    ])
    return MockLLM(responses=[response])


@pytest.fixture
def mock_llm_reflect_with_sources():
    """Mock LLM returning insights with source_ids populated."""
    response = json.dumps([
        {
            "content": "用户同时对Python和ML感兴趣，可能在做ML项目",
            "source_ids": ["src_a", "src_b"],
        }
    ])
    return MockLLM(responses=[response])


# ============================================================
# Fixtures: File System
# ============================================================


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create complete temporary data directory structure.

    Returns tmp_path with:
      tmp_path/core/
      tmp_path/archival/
    """
    (tmp_path / "core").mkdir()
    (tmp_path / "archival").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def _clean_llm_env(monkeypatch):
    """Remove MP_LLM__* and provider API key env vars to prevent leaking
    host config into tests. Real-LLM tests set them explicitly."""
    import os

    for key in list(os.environ):
        if key.startswith("MP_LLM__"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)


# ============================================================
# Embedding Mock — Protocol-compatible deterministic substitute
# ============================================================


@dataclass
class MockEmbedding:
    """Hash-based deterministic embedding mock.

    Implements EmbeddingProvider Protocol:
        async def embed(self, texts: list[str]) -> list[list[float]]
        @property dimension -> int

    Same text always produces the same unit vector — makes tests
    reproducible without any external API calls.
    """

    _dimension: int = 8

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_to_vector(t) for t in texts]

    @property
    def dimension(self) -> int:
        return self._dimension

    def _hash_to_vector(self, text: str) -> list[float]:
        """Deterministic: same text → same unit vector."""
        import hashlib

        h = hashlib.sha256(text.encode()).digest()
        raw = [b / 255.0 for b in h[: self._dimension]]
        # Normalize to unit vector
        norm = sum(x * x for x in raw) ** 0.5
        if norm == 0:
            return [0.0] * self._dimension
        return [x / norm for x in raw]


@pytest.fixture
def mock_embedding():
    """Deterministic hash-based embedding mock (dim=8)."""
    return MockEmbedding()
