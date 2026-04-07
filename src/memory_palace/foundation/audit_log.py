"""Append-only JSONL audit log.

Every write operation in the system produces exactly one AuditEntry line.
The log is the single source of truth for "what happened and when".

Ref: SPEC v2.0 §4.1 S-1, §2.2 AuditEntry
"""

from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class AuditAction(str, Enum):
    """Possible audit actions across the Memory Palace lifecycle."""

    CREATE = "create"
    UPDATE = "update"
    MERGE = "merge"
    PRUNE = "prune"
    PROMOTE = "promote"
    DEMOTE = "demote"
    ACCESS = "access"


class AuditEntry(BaseModel):
    """A single audit record captured for every write operation."""

    timestamp: datetime = Field(default_factory=datetime.now)
    action: AuditAction
    memory_id: str
    actor: str  # "user" | "curator" | "system"
    details: dict = {}


class AuditLog:
    """Append-only JSONL audit log backed by a single file.

    Args:
        data_dir: Directory where ``audit.jsonl`` is stored.
    """

    _FILENAME = "audit.jsonl"

    def __init__(self, data_dir: Path) -> None:
        self._path = data_dir / self._FILENAME

    def append(self, entry: AuditEntry) -> None:
        """Append one audit record.  Creates the file on first call."""
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(entry.model_dump_json() + "\n")

    def read(self, memory_id: str | None = None) -> list[AuditEntry]:
        """Read audit records, optionally filtered by *memory_id*.

        Returns entries in chronological (timestamp-ascending) order.
        If the backing file does not exist yet, returns ``[]``.
        """
        if not self._path.exists():
            return []

        entries: list[AuditEntry] = []
        with open(self._path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                entry = AuditEntry.model_validate_json(line)
                entries.append(entry)

        if memory_id is not None:
            entries = [e for e in entries if e.memory_id == memory_id]

        entries.sort(key=lambda e: e.timestamp)
        return entries
