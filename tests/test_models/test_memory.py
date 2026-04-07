"""
Round 2: Models — MemoryItem & Room Tests

IMMUTABLE SPEC: These tests define the MemoryItem data contract.
Ref: SPEC v2.0 §2.1 MemoryItem, §2.4 Room

MemoryItem is the atomic unit of memory. All fields, defaults,
validation rules, and serialization are specified here.
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from memory_palace.models.memory import (
    MemoryItem,
    MemoryStatus,
    MemoryTier,
    MemoryType,
    Room,
)


def _make_item(**overrides):
    """Helper to create a MemoryItem with required fields."""
    defaults = {
        "content": "test memory content",
        "memory_type": MemoryType.OBSERVATION,
        "tier": MemoryTier.RECALL,
        "importance": 0.5,
    }
    defaults.update(overrides)
    return MemoryItem(**defaults)


class TestMemoryItemDefaults:
    """MemoryItem default values and auto-generated fields."""

    def test_id_auto_generated(self):
        """id should auto-generate a UUID string if not provided."""
        item = _make_item()
        assert isinstance(item.id, str)
        assert len(item.id) > 0
        # Two items should have different IDs
        item2 = _make_item()
        assert item.id != item2.id

    def test_default_status_is_active(self):
        """status should default to MemoryStatus.ACTIVE."""
        item = _make_item()
        assert item.status == MemoryStatus.ACTIVE

    def test_default_tier_required(self):
        """tier is required, no default — must be explicitly set."""
        with pytest.raises(ValidationError):
            MemoryItem(
                content="test",
                memory_type=MemoryType.OBSERVATION,
                importance=0.5,
            )

    def test_default_room_is_general(self):
        """room should default to 'general'."""
        item = _make_item()
        assert item.room == "general"

    def test_default_version_is_one(self):
        """version should default to 1."""
        item = _make_item()
        assert item.version == 1

    def test_default_access_count_is_zero(self):
        """access_count should default to 0."""
        item = _make_item()
        assert item.access_count == 0

    def test_default_user_pinned_is_false(self):
        """user_pinned should default to False."""
        item = _make_item()
        assert item.user_pinned is False

    def test_timestamps_auto_set(self):
        """created_at, accessed_at, updated_at should auto-populate."""
        item = _make_item()
        assert isinstance(item.created_at, datetime)
        assert isinstance(item.accessed_at, datetime)
        assert isinstance(item.updated_at, datetime)


class TestMemoryItemValidation:
    """MemoryItem field validation rules."""

    def test_importance_must_be_between_0_and_1(self):
        """importance < 0 or > 1 should raise ValidationError."""
        with pytest.raises(ValidationError):
            _make_item(importance=-0.1)
        with pytest.raises(ValidationError):
            _make_item(importance=1.1)

    def test_importance_at_boundaries(self):
        """importance=0.0 and importance=1.0 should be valid."""
        item_low = _make_item(importance=0.0)
        assert item_low.importance == 0.0
        item_high = _make_item(importance=1.0)
        assert item_high.importance == 1.0

    def test_content_cannot_be_empty(self):
        """Empty content string should raise ValidationError."""
        with pytest.raises(ValidationError):
            _make_item(content="")
        with pytest.raises(ValidationError):
            _make_item(content="   ")


class TestMemoryItemSerialization:
    """MemoryItem JSON round-trip."""

    def test_json_roundtrip(self):
        """model_dump_json() → model_validate_json() preserves all fields."""
        item = _make_item(tags=["important", "test"])
        json_str = item.model_dump_json()
        restored = MemoryItem.model_validate_json(json_str)
        assert restored.id == item.id
        assert restored.content == item.content
        assert restored.memory_type == item.memory_type
        assert restored.tier == item.tier
        assert restored.importance == item.importance
        assert restored.tags == item.tags
        assert restored.status == item.status

    def test_dict_roundtrip(self):
        """model_dump() → model_validate() preserves all fields."""
        item = _make_item(tags=["tag1"])
        data = item.model_dump()
        restored = MemoryItem.model_validate(data)
        assert restored.id == item.id
        assert restored.content == item.content
        assert restored.importance == item.importance


class TestMemoryEnums:
    """Enum values are correct and complete."""

    def test_memory_status_values(self):
        """MemoryStatus: active, superseded, pruned, merged."""
        values = {s.value for s in MemoryStatus}
        assert values == {"active", "superseded", "pruned", "merged"}

    def test_memory_tier_values(self):
        """MemoryTier: core, recall, archival."""
        values = {t.value for t in MemoryTier}
        assert values == {"core", "recall", "archival"}

    def test_memory_type_values(self):
        """MemoryType: observation, reflection, preference, procedure, synthesis, decision."""
        values = {t.value for t in MemoryType}
        assert values == {
            "observation",
            "reflection",
            "preference",
            "procedure",
            "synthesis",
            "decision",
        }


class TestRoom:
    """Room model."""

    def test_room_defaults(self):
        """Room(name=X, description=Y) defaults: parent=None, memory_count=0."""
        room = Room(name="study", description="A quiet room")
        assert room.parent is None
        assert room.memory_count == 0
        assert room.last_accessed is None

    def test_room_name_required(self):
        """Room must have a name."""
        with pytest.raises(ValidationError):
            Room(description="no name")
