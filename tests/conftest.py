"""
Memory Palace — Shared Test Fixtures

IMMUTABLE CONTRACT: These fixtures define the test infrastructure.
Mock objects here represent the LLM boundary — they are deterministic
substitutes for non-deterministic external services.

Ref: SPEC v2.0 §7.2, CONVENTIONS.md Rule 2.5
"""

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
