"""
Round 2: Models — AuditEntry Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §2.2 AuditEntry
"""

from datetime import datetime

from memory_palace.models.audit import AuditAction, AuditEntry


class TestAuditEntry:
    """AuditEntry data model."""

    def test_defaults(self):
        """AuditEntry auto-generates timestamp."""
        entry = AuditEntry(
            action=AuditAction.CREATE,
            memory_id="mem-001",
            actor="user",
        )
        assert isinstance(entry.timestamp, datetime)

    def test_json_roundtrip(self):
        """model_dump_json() → model_validate_json() preserves all fields."""
        entry = AuditEntry(
            action=AuditAction.UPDATE,
            memory_id="mem-002",
            actor="curator",
            details={"field": "importance", "old": 0.3, "new": 0.8},
        )
        json_str = entry.model_dump_json()
        restored = AuditEntry.model_validate_json(json_str)
        assert restored.action == entry.action
        assert restored.memory_id == entry.memory_id
        assert restored.actor == entry.actor
        assert restored.details == entry.details

    def test_action_enum_values(self):
        """AuditAction: create, update, merge, prune, promote, demote, access."""
        values = {a.value for a in AuditAction}
        assert values == {
            "create",
            "update",
            "merge",
            "prune",
            "promote",
            "demote",
            "access",
        }

    def test_actor_field_accepts_string(self):
        """actor accepts 'user', 'curator', 'system'."""
        for actor in ("user", "curator", "system"):
            entry = AuditEntry(
                action=AuditAction.ACCESS,
                memory_id="mem-003",
                actor=actor,
            )
            assert entry.actor == actor

    def test_details_defaults_to_empty_dict(self):
        """details should default to {}."""
        entry = AuditEntry(
            action=AuditAction.CREATE,
            memory_id="mem-004",
            actor="system",
        )
        assert entry.details == {}
