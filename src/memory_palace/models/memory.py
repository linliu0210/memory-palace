"""Memory data models.

Ref: SPEC v2.0 §2.1 MemoryItem, §2.4 Room
"""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class MemoryStatus(StrEnum):
    """Status of a memory item in the system."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    PRUNED = "pruned"
    MERGED = "merged"


class MemoryTier(StrEnum):
    """Storage tier for a memory item."""

    CORE = "core"
    RECALL = "recall"
    ARCHIVAL = "archival"


class MemoryType(StrEnum):
    """Type classification for a memory item."""

    OBSERVATION = "observation"
    REFLECTION = "reflection"
    PREFERENCE = "preference"
    PROCEDURE = "procedure"
    SYNTHESIS = "synthesis"
    DECISION = "decision"


class MemoryItem(BaseModel):
    """The atomic unit of memory in the Memory Palace.

    Ref: SPEC v2.0 §2.1
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    memory_type: MemoryType
    tier: MemoryTier
    importance: float = Field(ge=0.0, le=1.0)
    tags: list[str] = []
    room: str = "general"
    user_pinned: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    accessed_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    access_count: int = 0
    status: MemoryStatus = MemoryStatus.ACTIVE
    version: int = 1
    parent_id: str | None = None
    merged_from: list[str] = []
    superseded_by: str | None = None
    change_reason: str | None = None
    embedding: list[float] | None = None
    source_hash: str | None = None

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        """Content must not be empty."""
        if not v.strip():
            raise ValueError("content must not be empty")
        return v


class Room(BaseModel):
    """A spatial grouping for memories.

    Ref: SPEC v2.0 §2.4
    """

    name: str
    description: str
    parent: str | None = None
    memory_count: int = 0
    last_accessed: datetime | None = None
