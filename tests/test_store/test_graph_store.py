"""
Round 24: GraphStore — KuzuDB graph storage tests

Tests Room topology, Memory nodes, RELATED_TO edges, proximity scoring,
and integration with ScoredCandidate.

Ref: R24 KuzuDB Graph Storage
"""

import pytest

from memory_palace.config import RoomConfig
from memory_palace.engine.scoring import ScoredCandidate, rank
from memory_palace.models.memory import MemoryItem, MemoryTier, MemoryType
from memory_palace.store.graph_store import GraphStore


@pytest.fixture
def graph_store(tmp_data_dir):
    """Create a GraphStore backed by a temporary directory."""
    store = GraphStore(tmp_data_dir)
    yield store
    store.close()


def _make_item(
    content: str = "test",
    importance: float = 0.5,
    room: str = "general",
    item_id: str | None = None,
) -> MemoryItem:
    """Create a minimal MemoryItem for testing."""
    return MemoryItem(
        id=item_id or "test-id-001",
        content=content,
        memory_type=MemoryType.OBSERVATION,
        tier=MemoryTier.RECALL,
        importance=importance,
        room=room,
    )


def _setup_room_hierarchy(store: GraphStore) -> None:
    """Set up a room tree: work -> [projects, general], projects -> [frontend]."""
    store.add_room(RoomConfig(name="work", description="工作相关"))
    store.add_room(RoomConfig(name="projects", description="项目", parent="work"))
    store.add_room(RoomConfig(name="general", description="通用", parent="work"))
    store.add_room(RoomConfig(name="frontend", description="前端", parent="projects"))


# ============================================================
# Room operations
# ============================================================


class TestAddRoom:
    """GraphStore.add_room() creates Room nodes and PARENT_OF edges."""

    def test_add_room(self, graph_store):
        """Adding a room node succeeds without error."""
        graph_store.add_room(RoomConfig(name="general", description="通用记忆"))
        # Verify by checking distance to itself
        assert graph_store.get_room_distance("general", "general") == 0

    def test_room_distance_same(self, graph_store):
        """Same room → distance 0."""
        graph_store.add_room(RoomConfig(name="projects", description="项目"))
        assert graph_store.get_room_distance("projects", "projects") == 0

    def test_room_distance_parent_child(self, graph_store):
        """Parent-child → distance 1."""
        _setup_room_hierarchy(graph_store)
        assert graph_store.get_room_distance("work", "projects") == 1

    def test_room_distance_sibling(self, graph_store):
        """Siblings (shared parent) → distance 2."""
        _setup_room_hierarchy(graph_store)
        # projects <-- work --> general => distance 2
        assert graph_store.get_room_distance("projects", "general") == 2

    def test_room_distance_grandparent(self, graph_store):
        """Grandparent relationship → distance 2."""
        _setup_room_hierarchy(graph_store)
        assert graph_store.get_room_distance("work", "frontend") == 2

    def test_room_distance_unknown_room(self, graph_store):
        """Unknown room → -1."""
        graph_store.add_room(RoomConfig(name="general", description="test"))
        assert graph_store.get_room_distance("general", "nonexistent") == -1


# ============================================================
# Memory operations
# ============================================================


class TestMemoryNode:
    """GraphStore memory node and relation operations."""

    def test_add_memory_node(self, graph_store):
        """Adding a memory node creates both Memory node and BELONGS_TO edge."""
        graph_store.add_room(RoomConfig(name="general", description="test"))
        item = _make_item(content="用户喜欢深色模式", room="general", item_id="m1")
        graph_store.add_memory_node(item)
        # Verify: node should exist (can add another and relate to it)
        item2 = _make_item(content="另一条记忆", room="general", item_id="m2")
        graph_store.add_memory_node(item2)
        graph_store.add_relation("m1", "m2", "test")
        related = graph_store.get_related("m1")
        assert "m2" in related

    def test_add_relation(self, graph_store):
        """add_relation() creates RELATED_TO edge between two memories."""
        graph_store.add_room(RoomConfig(name="general", description="test"))
        graph_store.add_memory_node(_make_item(item_id="a", room="general"))
        graph_store.add_memory_node(_make_item(item_id="b", room="general"))
        graph_store.add_relation("a", "b", "semantic", weight=0.9)
        related = graph_store.get_related("a")
        assert "b" in related

    def test_get_related(self, graph_store):
        """get_related() returns memories within max_hops via RELATED_TO."""
        graph_store.add_room(RoomConfig(name="general", description="test"))
        graph_store.add_memory_node(_make_item(item_id="x", room="general"))
        graph_store.add_memory_node(_make_item(item_id="y", room="general"))
        graph_store.add_memory_node(_make_item(item_id="z", room="general"))
        # x -> y -> z (chain)
        graph_store.add_relation("x", "y", "chain")
        graph_store.add_relation("y", "z", "chain")
        # max_hops=2 should find both y and z from x
        related = graph_store.get_related("x", max_hops=2)
        assert "y" in related
        assert "z" in related

    def test_get_related_respects_max_hops(self, graph_store):
        """get_related(max_hops=1) should not return 2-hop neighbors."""
        graph_store.add_room(RoomConfig(name="general", description="test"))
        graph_store.add_memory_node(_make_item(item_id="x", room="general"))
        graph_store.add_memory_node(_make_item(item_id="y", room="general"))
        graph_store.add_memory_node(_make_item(item_id="z", room="general"))
        graph_store.add_relation("x", "y", "chain")
        graph_store.add_relation("y", "z", "chain")
        related = graph_store.get_related("x", max_hops=1)
        assert "y" in related
        assert "z" not in related


# ============================================================
# Proximity scoring
# ============================================================


class TestProximity:
    """GraphStore.proximity_score() returns 1/(1+distance)."""

    def test_proximity_same_room(self, graph_store):
        """Same room → proximity = 1.0."""
        graph_store.add_room(RoomConfig(name="general", description="test"))
        assert graph_store.proximity_score("general", "general") == 1.0

    def test_proximity_parent_child(self, graph_store):
        """Parent-child (dist=1) → proximity = 0.5."""
        _setup_room_hierarchy(graph_store)
        assert graph_store.proximity_score("work", "projects") == pytest.approx(0.5)

    def test_proximity_distant_room(self, graph_store):
        """Sibling rooms (dist=2) → proximity ≈ 0.333 < 0.5."""
        _setup_room_hierarchy(graph_store)
        prox = graph_store.proximity_score("projects", "general")
        assert prox < 0.5
        assert prox == pytest.approx(1.0 / 3.0)

    def test_proximity_unknown_room(self, graph_store):
        """Unknown room → fallback 0.0."""
        graph_store.add_room(RoomConfig(name="general", description="test"))
        assert graph_store.proximity_score("general", "nonexistent") == 0.0

    def test_proximity_both_unknown(self, graph_store):
        """Both rooms unknown → 0.0."""
        assert graph_store.proximity_score("nope", "also_nope") == 0.0


# ============================================================
# Integration with scoring
# ============================================================


class TestScoringWithProximity:
    """ScoredCandidate uses proximity field for scoring."""

    def test_scoring_with_proximity(self):
        """proximity field affects rank() output correctly."""
        item_near = _make_item(content="near", importance=0.5, room="projects")
        item_far = _make_item(content="far", importance=0.5, room="general")

        near = ScoredCandidate(
            item=item_near,
            recency_hours=0.0,
            importance=0.5,
            relevance=0.5,
            proximity=1.0,  # same room
        )
        far = ScoredCandidate(
            item=item_far,
            recency_hours=0.0,
            importance=0.5,
            relevance=0.5,
            proximity=0.0,  # unknown room
        )
        result = rank([far, near])
        assert result[0].content == "near"
        assert result[1].content == "far"


# ============================================================
# Lifecycle
# ============================================================


class TestCloseCleanup:
    """GraphStore.close() releases resources."""

    def test_close_cleanup(self, tmp_data_dir):
        """After close(), internal references are None."""
        store = GraphStore(tmp_data_dir)
        store.add_room(RoomConfig(name="test", description="test"))
        store.close()
        assert store._conn is None
        assert store._db is None
