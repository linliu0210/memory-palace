"""AuditEntry and AuditAction data models.

Re-exported from foundation.audit_log where the canonical definitions live.
Ref: SPEC v2.0 §2.2

Round 2 Models layer provides a convenience import path:
    from memory_palace.models.audit import AuditEntry, AuditAction
"""

from memory_palace.foundation.audit_log import AuditAction, AuditEntry

__all__ = ["AuditAction", "AuditEntry"]
