"""FactExtractor — LLM-based atomic fact extraction.

Uses an LLM to extract self-contained, atomic facts from natural text,
returning a list of ``MemoryItem`` objects.

Ref: SPEC v2.0 §4.1 S-10, §4.5
"""

from __future__ import annotations

import json

import structlog

from memory_palace.foundation.llm import LLMProvider
from memory_palace.models.memory import MemoryItem, MemoryTier, MemoryType

logger = structlog.get_logger(__name__)

# ── Prompt Template (SPEC §4.5) ──────────────────────────────────────

FACT_EXTRACT_PROMPT = """Extract atomic facts from the following conversation.
Each fact should be:
- Self-contained (understandable without context)
- Atomic (one fact per item, not compound)
- Factual (not opinions unless user preference)

Rate importance 0.0-1.0:
- 0.0-0.3: Trivial (greetings, filler)
- 0.4-0.6: Useful context (project details, dates)
- 0.7-0.9: Important (preferences, decisions, key facts)
- 1.0: Critical (identity, safety-relevant)

Return JSON: [{{"content": "...", "importance": 0.X, "tags": [...]}}]

Conversation:
{text}"""


class FactExtractor:
    """Extract atomic facts from text using an LLM.

    Args:
        llm: Any object satisfying the ``LLMProvider`` protocol.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def extract(self, text: str) -> list[MemoryItem]:
        """Extract atomic facts from *text*.

        Workflow:
        1. Build prompt from SPEC §4.5 template.
        2. Call ``llm.complete(prompt)``.
        3. Parse JSON array response.
        4. Convert each fact dict to a ``MemoryItem`` (type=OBSERVATION).
        5. Return empty list for empty input or malformed JSON.

        Args:
            text: Conversation text to extract facts from.

        Returns:
            List of ``MemoryItem`` objects, one per atomic fact.
        """
        if not text or not text.strip():
            return []

        prompt = FACT_EXTRACT_PROMPT.format(text=text)
        raw = await self._llm.complete(prompt)

        try:
            facts = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Malformed LLM response in FactExtractor", raw=raw[:200])
            return []

        if not isinstance(facts, list):
            logger.warning("LLM response is not a JSON array", type=type(facts).__name__)
            return []

        items: list[MemoryItem] = []
        for fact in facts:
            if not isinstance(fact, dict) or "content" not in fact:
                continue
            try:
                item = MemoryItem(
                    content=fact["content"],
                    memory_type=MemoryType.OBSERVATION,
                    tier=MemoryTier.RECALL,
                    importance=float(fact.get("importance", 0.5)),
                    tags=fact.get("tags", []),
                )
                items.append(item)
            except (ValueError, TypeError) as exc:
                logger.warning("Skipping malformed fact", fact=fact, error=str(exc))

        return items
