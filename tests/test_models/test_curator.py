"""
Round 2: Models — CuratorReport Tests

IMMUTABLE SPEC: Ref: SPEC v2.0 §2.3 CuratorReport
"""

from datetime import datetime

from memory_palace.models.curator import CuratorReport


class TestCuratorReport:
    """CuratorReport data model."""

    def test_defaults(self):
        """CuratorReport auto-generates run_id. All counters default to 0."""
        report = CuratorReport(
            triggered_at=datetime.now(),
            trigger_reason="manual",
        )
        assert isinstance(report.run_id, str)
        assert len(report.run_id) > 0
        assert report.facts_extracted == 0
        assert report.memories_created == 0
        assert report.duration_seconds == 0
        assert report.tokens_consumed == 0

    def test_tracks_all_metrics(self):
        """Must have: facts_extracted, memories_created, memories_updated,
        memories_merged, memories_pruned, reflections_generated."""
        report = CuratorReport(
            triggered_at=datetime.now(),
            trigger_reason="session_count",
            facts_extracted=5,
            memories_created=3,
            memories_updated=2,
            memories_merged=1,
            memories_pruned=0,
            reflections_generated=1,
        )
        assert report.facts_extracted == 5
        assert report.memories_created == 3
        assert report.memories_updated == 2
        assert report.memories_merged == 1
        assert report.memories_pruned == 0
        assert report.reflections_generated == 1

    def test_health_scores_default_to_zero(self):
        """health_freshness and health_efficiency default to 0.0."""
        report = CuratorReport(
            triggered_at=datetime.now(),
            trigger_reason="timer",
        )
        assert report.health_freshness == 0.0
        assert report.health_efficiency == 0.0

    def test_errors_defaults_to_empty_list(self):
        """errors should default to []."""
        report = CuratorReport(
            triggered_at=datetime.now(),
            trigger_reason="manual",
        )
        assert report.errors == []

    def test_json_roundtrip(self):
        """model_dump_json() → model_validate_json() preserves all fields."""
        report = CuratorReport(
            triggered_at=datetime.now(),
            trigger_reason="session_count",
            facts_extracted=10,
            errors=["timeout on item-3"],
            health_freshness=0.85,
        )
        json_str = report.model_dump_json()
        restored = CuratorReport.model_validate_json(json_str)
        assert restored.run_id == report.run_id
        assert restored.trigger_reason == report.trigger_reason
        assert restored.facts_extracted == 10
        assert restored.errors == ["timeout on item-3"]
        assert restored.health_freshness == 0.85
