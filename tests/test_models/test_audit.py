"""
Round 2: Models — AuditEntry Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §2.2 AuditEntry
"""

import pytest


class TestAuditEntry:
    """AuditEntry data model."""

    def test_defaults(self):
        """AuditEntry auto-generates timestamp."""
        pytest.skip("RED: AuditEntry not implemented")

    def test_json_roundtrip(self):
        """model_dump_json() → model_validate_json() preserves all fields."""
        pytest.skip("RED: AuditEntry not implemented")

    def test_action_enum_values(self):
        """AuditAction: create, update, merge, prune, promote, demote, access."""
        pytest.skip("RED: AuditAction not implemented")

    def test_actor_field_accepts_string(self):
        """actor accepts 'user', 'curator', 'system'."""
        pytest.skip("RED: AuditEntry not implemented")

    def test_details_defaults_to_empty_dict(self):
        """details should default to {}."""
        pytest.skip("RED: AuditEntry not implemented")
