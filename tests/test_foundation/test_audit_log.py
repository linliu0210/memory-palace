"""
Round 1: Foundation — AuditLog Tests

IMMUTABLE SPEC: These tests define the AuditLog contract.
Ref: SPEC v2.0 §4.1 S-1, §2.2 AuditEntry

AuditLog is an append-only JSONL file. Each write operation in the
system produces exactly one AuditEntry line. The log is the single
source of truth for "what happened and when".
"""

import json
from datetime import datetime

from memory_palace.foundation.audit_log import AuditAction, AuditEntry, AuditLog


class TestAuditLogAppend:
    """AuditLog.append() creates and writes to JSONL file."""

    def test_append_creates_file_if_not_exists(self, tmp_data_dir):
        """First append should create the audit.jsonl file."""
        log = AuditLog(tmp_data_dir)
        entry = AuditEntry(
            action=AuditAction.CREATE,
            memory_id="mem-001",
            actor="user",
        )
        log.append(entry)
        assert (tmp_data_dir / "audit.jsonl").exists()

    def test_append_writes_valid_jsonl(self, tmp_data_dir):
        """Each appended entry should be a valid JSON line."""
        log = AuditLog(tmp_data_dir)
        entry = AuditEntry(
            action=AuditAction.CREATE,
            memory_id="mem-001",
            actor="user",
        )
        log.append(entry)

        lines = (tmp_data_dir / "audit.jsonl").read_text().strip().split("\n")
        for line in lines:
            parsed = json.loads(line)  # should not raise
            assert isinstance(parsed, dict)

    def test_append_preserves_all_fields(self, tmp_data_dir):
        """Entry fields (timestamp, action, memory_id, actor, details)
        must all be present in the written line."""
        log = AuditLog(tmp_data_dir)
        entry = AuditEntry(
            action=AuditAction.UPDATE,
            memory_id="mem-002",
            actor="curator",
            details={"reason": "merged duplicate"},
        )
        log.append(entry)

        line = (tmp_data_dir / "audit.jsonl").read_text().strip()
        parsed = json.loads(line)
        assert "timestamp" in parsed
        assert parsed["action"] == "update"
        assert parsed["memory_id"] == "mem-002"
        assert parsed["actor"] == "curator"
        assert parsed["details"] == {"reason": "merged duplicate"}

    def test_file_is_append_only_after_restart(self, tmp_data_dir):
        """Re-opening the log and appending must not overwrite existing entries."""
        log1 = AuditLog(tmp_data_dir)
        log1.append(AuditEntry(action=AuditAction.CREATE, memory_id="mem-001", actor="user"))

        # "restart" → new AuditLog instance
        log2 = AuditLog(tmp_data_dir)
        log2.append(AuditEntry(action=AuditAction.ACCESS, memory_id="mem-002", actor="system"))

        lines = (tmp_data_dir / "audit.jsonl").read_text().strip().split("\n")
        assert len(lines) == 2


class TestAuditLogRead:
    """AuditLog.read() retrieves entries from the JSONL file."""

    def test_read_returns_all_entries(self, tmp_data_dir):
        """read() with no filter should return all appended entries."""
        log = AuditLog(tmp_data_dir)
        log.append(AuditEntry(action=AuditAction.CREATE, memory_id="mem-001", actor="user"))
        log.append(AuditEntry(action=AuditAction.UPDATE, memory_id="mem-002", actor="curator"))

        entries = log.read()
        assert len(entries) == 2

    def test_read_filters_by_memory_id(self, tmp_data_dir):
        """read(memory_id=X) should return only entries for memory X."""
        log = AuditLog(tmp_data_dir)
        log.append(AuditEntry(action=AuditAction.CREATE, memory_id="mem-001", actor="user"))
        log.append(AuditEntry(action=AuditAction.UPDATE, memory_id="mem-002", actor="curator"))
        log.append(AuditEntry(action=AuditAction.ACCESS, memory_id="mem-001", actor="system"))

        entries = log.read(memory_id="mem-001")
        assert len(entries) == 2
        assert all(e.memory_id == "mem-001" for e in entries)

    def test_read_returns_empty_for_nonexistent_file(self, tmp_data_dir):
        """read() before any append should return empty list, not error."""
        log = AuditLog(tmp_data_dir)
        entries = log.read()
        assert entries == []

    def test_read_returns_entries_in_chronological_order(self, tmp_data_dir):
        """Entries should be returned oldest-first."""
        log = AuditLog(tmp_data_dir)

        t1 = datetime(2024, 1, 1, 10, 0, 0)
        t2 = datetime(2024, 1, 1, 12, 0, 0)
        t3 = datetime(2024, 1, 1, 11, 0, 0)

        log.append(
            AuditEntry(timestamp=t1, action=AuditAction.CREATE, memory_id="mem-001", actor="user")
        )
        log.append(
            AuditEntry(
                timestamp=t2, action=AuditAction.UPDATE, memory_id="mem-001", actor="curator"
            )
        )
        log.append(
            AuditEntry(
                timestamp=t3, action=AuditAction.ACCESS, memory_id="mem-001", actor="system"
            )
        )

        entries = log.read()
        assert entries[0].timestamp == t1
        assert entries[1].timestamp == t3
        assert entries[2].timestamp == t2
