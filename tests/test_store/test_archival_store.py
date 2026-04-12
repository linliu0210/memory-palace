"""
Round 9: Store — ArchivalStore Tests

IMMUTABLE SPEC: Ref: SPEC_V02 §2.2 (F-1), §1.4

ArchivalStore uses ChromaDB for full-index vector embeddings.
Tests use EphemeralClient for isolation (no disk I/O in tests).
MockEmbedding from conftest provides deterministic, hash-based vectors.
"""

import chromadb
import pytest

from memory_palace.models.memory import (
    MemoryItem,
    MemoryStatus,
    MemoryTier,
    MemoryType,
)
from memory_palace.store.archival_store import ArchivalStore


def _make_item(
    content: str = "test content",
    memory_type: MemoryType = MemoryType.OBSERVATION,
    importance: float = 0.5,
    room: str = "general",
    item_id: str | None = None,
    status: MemoryStatus = MemoryStatus.ACTIVE,
) -> MemoryItem:
    """Helper to create a MemoryItem for testing."""
    return MemoryItem(
        id=item_id or "archival-test-001",
        content=content,
        memory_type=memory_type,
        tier=MemoryTier.RECALL,
        importance=importance,
        room=room,
        tags=["test"],
        status=status,
    )


@pytest.fixture
def archival_store(mock_embedding):
    """ArchivalStore backed by EphemeralClient + MockEmbedding.

    Each test gets a fresh EphemeralClient + unique collection for isolation.
    """
    import uuid

    client = chromadb.EphemeralClient()
    return ArchivalStore(
        client=client,
        embedding=mock_embedding,
        collection_name=f"test_{uuid.uuid4().hex[:12]}",
    )


class TestArchivalStoreInsert:
    """ArchivalStore insert operations."""

    async def test_insert_increments_count(self, archival_store):
        """insert(item) should persist to ChromaDB."""
        item = _make_item(item_id="ins-1")
        await archival_store.insert(item)
        assert archival_store.count() == 1

    async def test_insert_stores_content_and_metadata(self, archival_store):
        """Inserted item should be retrievable with correct content and metadata."""
        item = _make_item(
            content="用户喜欢深色模式",
            room="preferences",
            importance=0.8,
            item_id="ins-meta",
        )
        await archival_store.insert(item)
        record = archival_store.get("ins-meta")

        assert record is not None
        assert record["id"] == "ins-meta"
        assert record["content"] == "用户喜欢深色模式"
        assert record["metadata"]["room"] == "preferences"
        assert record["metadata"]["importance"] == 0.8

    async def test_insert_with_precomputed_embedding(self, archival_store):
        """insert(item, embedding=...) should use the provided vector."""
        item = _make_item(item_id="ins-emb")
        vec = [0.1] * 8  # Match MockEmbedding dimension
        await archival_store.insert(item, embedding=vec)
        assert archival_store.count() == 1

    async def test_insert_without_embedding_or_provider_raises(self):
        """insert() without embedding and without provider should raise ValueError."""
        store = ArchivalStore(client=chromadb.EphemeralClient(), embedding=None)
        item = _make_item(item_id="no-emb")
        with pytest.raises(ValueError, match="No embedding"):
            await store.insert(item)

    async def test_insert_upsert_idempotent(self, archival_store):
        """Inserting the same ID twice should overwrite (upsert), not duplicate."""
        item1 = _make_item(content="version 1", item_id="upsert-id")
        item2 = _make_item(content="version 2", item_id="upsert-id")
        await archival_store.insert(item1)
        await archival_store.insert(item2)
        assert archival_store.count() == 1
        record = archival_store.get("upsert-id")
        assert record["content"] == "version 2"


class TestArchivalStoreSearch:
    """ArchivalStore semantic search operations."""

    async def test_search_returns_results(self, archival_store):
        """search() should return semantically similar items."""
        await archival_store.insert(_make_item(content="Python programming", item_id="s1"))
        await archival_store.insert(_make_item(content="Java development", item_id="s2"))
        await archival_store.insert(_make_item(content="用户偏好设置", item_id="s3"))

        results = await archival_store.search("Python coding")
        assert len(results) >= 1
        assert all("distance" in r for r in results)
        assert all("id" in r for r in results)
        assert all("content" in r for r in results)

    async def test_search_has_distance_scores(self, archival_store):
        """Results must include distance scores for ranking."""
        await archival_store.insert(_make_item(content="deep learning models", item_id="d1"))
        results = await archival_store.search("deep learning")
        assert len(results) >= 1
        assert isinstance(results[0]["distance"], float)

    async def test_search_room_filter(self, archival_store):
        """search(query, room='preferences') should filter by room."""
        await archival_store.insert(
            _make_item(content="深色模式偏好", item_id="rf1", room="preferences")
        )
        await archival_store.insert(
            _make_item(content="深色模式项目", item_id="rf2", room="projects")
        )
        results = await archival_store.search("深色模式", room="preferences")
        assert all(r["metadata"]["room"] == "preferences" for r in results)

    async def test_search_empty_collection_returns_empty(self, archival_store):
        """search() on empty collection should return empty list."""
        results = await archival_store.search("anything")
        assert results == []

    async def test_search_without_provider_raises(self):
        """search() without EmbeddingProvider should raise ValueError."""
        store = ArchivalStore(client=chromadb.EphemeralClient(), embedding=None)
        with pytest.raises(ValueError, match="No EmbeddingProvider"):
            await store.search("test")


class TestArchivalStoreRetrieval:
    """ArchivalStore direct retrieval operations."""

    async def test_get_by_id_returns_record(self, archival_store):
        """get(id) returns the correct record."""
        item = _make_item(content="Exact match test", item_id="get-exact")
        await archival_store.insert(item)
        record = archival_store.get("get-exact")
        assert record is not None
        assert record["id"] == "get-exact"
        assert record["content"] == "Exact match test"

    def test_get_missing_returns_none(self, archival_store):
        """get(nonexistent_id) returns None."""
        result = archival_store.get("does-not-exist")
        assert result is None

    async def test_delete_removes_record(self, archival_store):
        """delete(id) should remove the record from the store."""
        item = _make_item(item_id="del-1")
        await archival_store.insert(item)
        assert archival_store.count() == 1
        archival_store.delete("del-1")
        assert archival_store.count() == 0
        assert archival_store.get("del-1") is None

    async def test_count_returns_correct_total(self, archival_store):
        """count() returns total number of indexed items."""
        assert archival_store.count() == 0
        await archival_store.insert(_make_item(item_id="cnt-1"))
        await archival_store.insert(_make_item(item_id="cnt-2"))
        assert archival_store.count() == 2


class TestArchivalStoreInit:
    """ArchivalStore initialization."""

    def test_init_with_data_dir(self, tmp_data_dir, mock_embedding):
        """ArchivalStore(data_dir=...) should create PersistentClient."""
        store = ArchivalStore(data_dir=tmp_data_dir, embedding=mock_embedding)
        assert store.count() == 0

    def test_init_without_data_dir_or_client_raises(self):
        """ArchivalStore() with neither data_dir nor client should raise."""
        with pytest.raises(ValueError, match="Either data_dir or client"):
            ArchivalStore()
