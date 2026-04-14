"""IngestReport — Result of a 5-pass ingest pipeline run.

Ref: TASK_R25
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class IngestReport:
    """Report produced by IngestPipeline after processing a document."""

    total_input_chars: int = 0
    pass_results: dict[str, dict] = field(default_factory=dict)
    memories_created: int = 0
    relations_created: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
