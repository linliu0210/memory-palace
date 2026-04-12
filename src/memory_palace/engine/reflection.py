"""ReflectionEngine — LLM-based higher-order insight generation.

Uses an LLM to synthesize patterns and insights from recent memories,
producing new MemoryItems of type REFLECTION.

Ref: SPEC_V02 §2.3 (F-6), ReflectionEngine Prompt
"""

from __future__ import annotations

import json

import structlog

from memory_palace.foundation.llm import LLMProvider
from memory_palace.models.memory import MemoryItem, MemoryTier, MemoryType

logger = structlog.get_logger(__name__)

# ── Prompt Template (SPEC §2.3) ──────────────────────────────

REFLECTION_PROMPT = """You are a reflection engine for a Memory Palace system.
Given recent memories, generate 1-3 higher-order insights.

Each insight should:
- Synthesize across multiple memories (not just rephrase)
- Reveal patterns the user might not notice
- Be actionable or diagnostic

MEMORIES:
{formatted_memories}

Return JSON array:
[{{
  "content": "insight text",
  "source_ids": ["id1", "id2", ...]
}}]"""


class ReflectionEngine:
    """Generate higher-order insights from recent memories using an LLM.

    Args:
        llm: Any object satisfying the ``LLMProvider`` protocol.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def reflect(
        self,
        memories: list[MemoryItem],
        max_insights: int = 3,
    ) -> list[MemoryItem]:
        """Reflect on a batch of recent memories and produce insights.

        Workflow:
        1. Guard: return [] if memories is empty.
        2. Format memories into prompt context.
        3. Call LLM to generate insights.
        4. Parse JSON response → list of MemoryItem (type=REFLECTION).
        5. Cap output to max_insights.

        Args:
            memories: Recent memories to reflect on.
            max_insights: Maximum number of insights to generate.

        Returns:
            List of REFLECTION MemoryItems. Empty on error or no input.
        """
        if not memories:
            return []

        formatted = self._format_memories(memories)
        prompt = REFLECTION_PROMPT.format(formatted_memories=formatted)

        raw = await self._llm.complete(prompt)

        try:
            insights_data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Malformed LLM response in ReflectionEngine", raw=raw[:200])
            return []

        if not isinstance(insights_data, list):
            logger.warning(
                "LLM response is not a JSON array",
                type=type(insights_data).__name__,
            )
            return []

        items: list[MemoryItem] = []
        for insight in insights_data[:max_insights]:
            if not isinstance(insight, dict) or "content" not in insight:
                continue

            source_ids = insight.get("source_ids", [])
            if not isinstance(source_ids, list):
                source_ids = []

            try:
                item = MemoryItem(
                    content=insight["content"],
                    memory_type=MemoryType.REFLECTION,
                    tier=MemoryTier.RECALL,
                    importance=0.8,  # reflections are inherently high-importance
                    merged_from=source_ids,  # track which memories were synthesized
                )
                items.append(item)
            except (ValueError, TypeError) as exc:
                logger.warning("Skipping malformed insight", insight=insight, error=str(exc))

        return items

    @staticmethod
    def _format_memories(memories: list[MemoryItem]) -> str:
        """Format memories for the prompt context."""
        lines: list[str] = []
        for i, m in enumerate(memories, 1):
            lines.append(f"{i}. [{m.id}] {m.content} (importance={m.importance:.1f})")
        return "\n".join(lines)


def should_reflect(memories: list[MemoryItem], threshold: float = 2.0) -> bool:
    """Check if a batch of memories warrants reflection.

    Returns True when the sum of importance scores strictly exceeds
    the threshold, indicating enough significant material has accumulated.

    Args:
        memories: Recent memories to evaluate.
        threshold: Minimum importance sum to trigger reflection.

    Returns:
        True if sum(importance) > threshold.
    """
    if not memories:
        return False
    return sum(m.importance for m in memories) > threshold
