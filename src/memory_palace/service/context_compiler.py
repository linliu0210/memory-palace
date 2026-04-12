"""ContextCompiler — compile structured context for Agent consumption.

Assembles Core Memory (always-on), retrieved results (query-dependent),
and recent activity into a single structured text block.

Ref: SPEC_V02 §2.4 (F-9)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from memory_palace.service.hybrid_retriever import HybridRetriever
    from memory_palace.service.memory_service import MemoryService

logger = structlog.get_logger(__name__)


class ContextCompiler:
    """Compile structured context for an Agent from Memory Palace stores.

    Output format:
    ```
    [CORE MEMORY]
    <all active core memories>

    [RETRIEVED]
    <top_k results for the query>

    [RECENT ACTIVITY]
    <latest N recalled memories>
    ```

    Args:
        memory_service: MemoryService for Core access and stats.
        retriever: HybridRetriever for search (FTS5 + Vector).
    """

    def __init__(
        self,
        memory_service: MemoryService,
        retriever: HybridRetriever,
    ) -> None:
        self._memory_service = memory_service
        self._retriever = retriever

    async def compile(
        self,
        query: str | None = None,
        include_core: bool = True,
        top_k: int = 5,
        recent_n: int = 3,
        max_chars: int = 4000,
    ) -> str:
        """Compile context string for Agent consumption.

        Args:
            query: Optional search query for retrieval section.
            include_core: Whether to include Core Memory section.
            top_k: Max items in the RETRIEVED section.
            recent_n: Max items in the RECENT ACTIVITY section.
            max_chars: Soft character limit for the entire context.

        Returns:
            Formatted context string with sections.
        """
        sections: list[str] = []

        # Section 1: Core Memory (always-on)
        if include_core:
            core_text = self._memory_service.get_core_context()
            if core_text.strip():
                sections.append(f"[CORE MEMORY]\n{core_text}")

        # Section 2: Retrieved (query-dependent)
        if query and query.strip():
            results = await self._retriever.search(query=query, top_k=top_k)
            if results:
                lines = []
                for i, item in enumerate(results, 1):
                    lines.append(
                        f"{i}. [{item.room}] {item.content} "
                        f"(importance={item.importance:.1f})"
                    )
                sections.append("[RETRIEVED]\n" + "\n".join(lines))

        # Section 3: Recent Activity
        recent_items = self._memory_service._recall_store.get_recent(recent_n)
        if recent_items:
            lines = []
            for item in recent_items:
                lines.append(f"- {item.content} ({item.room})")
            sections.append("[RECENT ACTIVITY]\n" + "\n".join(lines))

        full_text = "\n\n".join(sections)

        # Soft truncation to max_chars
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars] + "\n[...truncated]"

        return full_text
