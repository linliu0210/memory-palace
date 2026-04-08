"""ReconcileEngine — LLM-based memory conflict resolution.

Given a new fact and existing memories, asks the LLM to decide one of:
ADD / UPDATE / DELETE / NOOP.

Ref: SPEC v2.0 §4.1 S-12, §4.5
"""

from __future__ import annotations

import json

import structlog

from memory_palace.foundation.llm import LLMProvider
from memory_palace.models.memory import MemoryItem

logger = structlog.get_logger(__name__)

# ── Prompt Template (SPEC §4.5) ──────────────────────────────────────

RECONCILE_PROMPT = """You are a memory reconciliation engine.
Given a NEW fact and EXISTING memories:

NEW: {new_fact}
EXISTING:
{existing_memories}

Decide ONE action:
- ADD: genuinely new information
- UPDATE <id>: updates/corrects existing
- DELETE <id>: contradicts existing, making it obsolete
- NOOP: already captured

Return JSON: {{"action": "ADD|UPDATE|DELETE|NOOP", "target_id": "...|null", "reason": "..."}}"""

VALID_ACTIONS = {"ADD", "UPDATE", "DELETE", "NOOP"}


class ReconcileEngine:
    """Reconcile a new fact against existing memories using an LLM.

    Args:
        llm: Any object satisfying the ``LLMProvider`` protocol.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def reconcile(
        self,
        new_fact: str,
        existing: list[MemoryItem],
    ) -> dict:
        """Decide how a new fact relates to existing memories.

        Args:
            new_fact: The newly extracted fact text.
            existing: List of existing ``MemoryItem`` objects to compare against.

        Returns:
            Dict with keys ``action``, ``target_id``, and ``reason``.

        Raises:
            ValueError: If the LLM returns unparseable JSON.
        """
        # Format existing memories for the prompt
        if existing:
            existing_text = "\n".join(f"- [{m.id}] {m.content}" for m in existing)
        else:
            existing_text = "(none)"

        prompt = RECONCILE_PROMPT.format(
            new_fact=new_fact,
            existing_memories=existing_text,
        )

        raw = await self._llm.complete(prompt)

        try:
            result = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Malformed LLM response in ReconcileEngine", raw=raw[:200])
            raise ValueError(f"Failed to parse reconcile response: {exc}") from exc

        # ── Post-parse schema validation ──────────────────────────
        if not isinstance(result, dict):
            raise ValueError(
                f"Expected dict from LLM, got {type(result).__name__}"
            )

        action = result.get("action")
        if action not in VALID_ACTIONS:
            raise ValueError(
                f"Invalid action '{action}', expected one of {VALID_ACTIONS}"
            )

        reason = result.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Missing or empty 'reason' in reconcile response")

        # Normalize target_id: JSON null / string "null" → Python None
        target_id = result.get("target_id")
        if target_id == "null":
            target_id = None

        # target_id must be str or None (reject int, list, etc.)
        if target_id is not None and not isinstance(target_id, str):
            raise ValueError(
                f"target_id must be str or None, got {type(target_id).__name__}"
            )

        # UPDATE/DELETE must have a concrete target_id
        if action in ("UPDATE", "DELETE") and not target_id:
            raise ValueError(
                f"Action '{action}' requires a non-null target_id"
            )

        return {
            "action": action,
            "target_id": target_id,
            "reason": reason,
        }
