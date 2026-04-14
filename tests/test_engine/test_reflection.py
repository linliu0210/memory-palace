"""
Round 11: ReflectionEngine — LLM-based higher-order insight generation.

SPEC Ref: SPEC_V02 §2.3 (F-6), ReflectionEngine Prompt
Tests: reflect normal flow, output type=REFLECTION, importance propagation,
       source_ids tracking, max_insights cap, malformed JSON, threshold, empty.
"""



from memory_palace.engine.reflection import ReflectionEngine, should_reflect
from memory_palace.models.memory import MemoryItem, MemoryTier, MemoryType

# ── Helpers ──────────────────────────────────────────────────


def _make_item(
    content: str = "test memory",
    importance: float = 0.5,
    room: str = "general",
    memory_type: MemoryType = MemoryType.OBSERVATION,
) -> MemoryItem:
    """Create a minimal MemoryItem for testing."""
    return MemoryItem(
        content=content,
        memory_type=memory_type,
        tier=MemoryTier.RECALL,
        importance=importance,
        room=room,
    )


# ============================================================
# ReflectionEngine.reflect()
# ============================================================


class TestReflect:
    """ReflectionEngine.reflect() generates higher-order insights."""

    async def test_reflect_returns_insights(self, mock_llm_reflect):
        """Normal flow: LLM returns valid insights → list[MemoryItem]."""
        engine = ReflectionEngine(mock_llm_reflect)
        memories = [
            _make_item(content="用户喜欢Python"),
            _make_item(content="用户正在学机器学习"),
        ]
        results = await engine.reflect(memories)

        assert len(results) >= 1
        assert all(isinstance(r, MemoryItem) for r in results)

    async def test_reflect_output_type_is_reflection(self, mock_llm_reflect):
        """All generated insights have memory_type=REFLECTION."""
        engine = ReflectionEngine(mock_llm_reflect)
        memories = [_make_item(), _make_item()]
        results = await engine.reflect(memories)

        for item in results:
            assert item.memory_type == MemoryType.REFLECTION

    async def test_reflect_output_tier_is_recall(self, mock_llm_reflect):
        """Generated reflections default to RECALL tier."""
        engine = ReflectionEngine(mock_llm_reflect)
        memories = [_make_item(), _make_item()]
        results = await engine.reflect(memories)

        for item in results:
            assert item.tier == MemoryTier.RECALL

    async def test_reflect_importance_is_high(self, mock_llm_reflect):
        """Reflections should have importance ≥ 0.7 (higher-order insights)."""
        engine = ReflectionEngine(mock_llm_reflect)
        memories = [_make_item(), _make_item()]
        results = await engine.reflect(memories)

        for item in results:
            assert item.importance >= 0.7

    async def test_reflect_max_insights_cap(self, mock_llm_reflect_many):
        """max_insights limits the number of returned insights."""
        engine = ReflectionEngine(mock_llm_reflect_many)
        memories = [_make_item() for _ in range(5)]
        results = await engine.reflect(memories, max_insights=2)

        assert len(results) <= 2

    async def test_reflect_malformed_json_returns_empty(self, mock_llm_malformed):
        """Malformed JSON from LLM → empty list, no crash."""
        engine = ReflectionEngine(mock_llm_malformed)
        memories = [_make_item(), _make_item()]
        results = await engine.reflect(memories)

        assert results == []

    async def test_reflect_empty_memories_returns_empty(self, mock_llm_reflect):
        """No memories → no reflection, returns empty."""
        engine = ReflectionEngine(mock_llm_reflect)
        results = await engine.reflect([])

        assert results == []

    async def test_reflect_includes_source_ids_in_tags(self, mock_llm_reflect_with_sources):
        """source_ids from LLM response are tracked in the item."""
        memories = [
            _make_item(content="fact A"),
            _make_item(content="fact B"),
        ]
        engine = ReflectionEngine(mock_llm_reflect_with_sources)
        results = await engine.reflect(memories)

        assert len(results) >= 1
        # source_ids should be stored (as parent_id or merged_from)
        first = results[0]
        assert first.merged_from  # non-empty source tracking


# ============================================================
# should_reflect()
# ============================================================


class TestShouldReflect:
    """should_reflect() checks if reflection is warranted based on importance sum."""

    def test_high_importance_above_threshold(self):
        """Sum of importance > threshold → should reflect."""
        memories = [
            _make_item(importance=0.8),
            _make_item(importance=0.9),
            _make_item(importance=0.7),
        ]
        # sum = 2.4, threshold = 2.0
        assert should_reflect(memories, threshold=2.0) is True

    def test_low_importance_below_threshold(self):
        """Sum of importance < threshold → should not reflect."""
        memories = [
            _make_item(importance=0.2),
            _make_item(importance=0.3),
        ]
        # sum = 0.5, threshold = 2.0
        assert should_reflect(memories, threshold=2.0) is False

    def test_empty_memories_is_false(self):
        """No memories → should not reflect."""
        assert should_reflect([], threshold=1.0) is False

    def test_exact_threshold_is_false(self):
        """importance sum == threshold → should NOT reflect (strict >)."""
        memories = [_make_item(importance=0.5), _make_item(importance=0.5)]
        assert should_reflect(memories, threshold=1.0) is False
