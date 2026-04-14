"""
v0.2 Integration Fix — E2E Tests

Validates the REAL v0.2 main path that was previously untested:
- save() → ArchivalStore indexing
- search() via HybridRetriever (with actual MockEmbedding)
- update_field() → FTS5 sync
- coherence health metric (non-placeholder)

All embedding calls use MockEmbedding (hash-based deterministic vectors).
"""

import uuid

import chromadb
import pytest

from memory_palace.config import Config
from memory_palace.engine.health import compute_health
from memory_palace.models.memory import MemoryItem, MemoryTier, MemoryType
from memory_palace.service.memory_service import MemoryService
from memory_palace.store.archival_store import ArchivalStore
from memory_palace.store.recall_store import RecallStore
from tests.conftest import MockEmbedding


@pytest.fixture
def mock_embedding():
    return MockEmbedding()


@pytest.fixture
def archival_store(tmp_data_dir, mock_embedding):
    """ArchivalStore backed by EphemeralClient with unique collection per test."""
    client = chromadb.EphemeralClient()
    return ArchivalStore(
        data_dir=tmp_data_dir,
        embedding=mock_embedding,
        client=client,
        collection_name=f"test_{uuid.uuid4().hex[:8]}",
    )


@pytest.fixture
def full_svc(tmp_data_dir, mock_embedding, archival_store):
    """MemoryService with full v0.2 stack (embedding + archival)."""
    return MemoryService(
        tmp_data_dir,
        archival_store=archival_store,
        embedding=mock_embedding,
    )


class TestSaveIndexesArchival:
    """save() should index ALL items into ArchivalStore."""

    def test_save_core_item_indexed_in_archival(self, full_svc, archival_store):
        """Core item (importance >= 0.7) is indexed in ArchivalStore."""
        full_svc.save("架构设计决策记录", importance=0.9, room="projects")
        assert archival_store.count() == 1

    def test_save_recall_item_indexed_in_archival(self, full_svc, archival_store):
        """Recall item (importance < 0.7) is also indexed in ArchivalStore."""
        full_svc.save("今日会议纪要", importance=0.3, room="general")
        assert archival_store.count() == 1

    def test_save_multiple_all_indexed(self, full_svc, archival_store):
        """Multiple saves all get indexed."""
        full_svc.save("记忆A", importance=0.9, room="general")
        full_svc.save("记忆B", importance=0.5, room="preferences")
        full_svc.save("记忆C", importance=0.2, room="skills")
        assert archival_store.count() == 3

    def test_stats_includes_archival_count(self, full_svc, archival_store):
        """stats() reflects archival count."""
        full_svc.save("test", importance=0.5)
        stats = full_svc.stats()
        assert stats.get("archival_count", 0) == 1


class TestSearchViaHybridRetriever:
    """search() should use HybridRetriever when archival is configured."""

    @pytest.mark.asyncio
    async def test_search_returns_recall_items(self, full_svc):
        """Hybrid search returns items from Recall tier."""
        full_svc.save("Python编程语言学习笔记", importance=0.3, room="skills")
        full_svc.save("机器学习模型训练经验", importance=0.4, room="skills")

        results = await full_svc.search("Python")
        assert len(results) >= 1
        assert any("Python" in r.content for r in results)

    @pytest.mark.asyncio
    async def test_search_sync_fallback(self, full_svc):
        """search_sync() works as convenience wrapper."""
        full_svc.save("Rust系统编程", importance=0.3, room="skills")
        results = full_svc.search_sync("Rust")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_without_archival_falls_back(self, tmp_data_dir):
        """Without archival/embedding, search still works via FTS5."""
        svc = MemoryService(tmp_data_dir)
        svc.save("FTS5测试记忆", importance=0.3)
        results = svc.search_sync("FTS5")
        assert len(results) >= 1


class TestUpdateFieldFTSSync:
    """update_field() must keep FTS5 index in sync."""

    def test_fts5_syncs_after_content_update(self, tmp_data_dir):
        """After updating content, FTS5 search finds the new content."""
        store = RecallStore(tmp_data_dir)

        item = MemoryItem(
            content="old original content",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.RECALL,
            importance=0.5,
            room="general",
        )
        store.insert(item)

        # Verify old content is searchable
        results = store.search("original")
        assert len(results) >= 1

        # Update content
        store.update_field(item.id, "content", "brand new updated text")

        # New content should be searchable
        results_new = store.search("updated")
        assert len(results_new) >= 1, "FTS5 should find updated content"

        # Old content should NOT be searchable
        results_old = store.search("original")
        assert len(results_old) == 0, "FTS5 should not find old content after update"

    def test_fts5_syncs_after_room_update(self, tmp_data_dir):
        """After updating room, FTS5 search finds the new room."""
        store = RecallStore(tmp_data_dir)

        item = MemoryItem(
            content="room test item",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.RECALL,
            importance=0.5,
            room="general",
        )
        store.insert(item)

        store.update_field(item.id, "room", "preferences")

        # Search with new room should work
        results = store.search("room test", room="preferences")
        assert len(results) >= 1

    def test_fts5_unchanged_for_non_searchable_fields(self, tmp_data_dir):
        """Updating importance (non-FTS field) doesn't break FTS5."""
        store = RecallStore(tmp_data_dir)

        item = MemoryItem(
            content="importance test",
            memory_type=MemoryType.OBSERVATION,
            tier=MemoryTier.RECALL,
            importance=0.3,
            room="general",
        )
        store.insert(item)

        store.update_field(item.id, "importance", 0.9)

        results = store.search("importance test")
        assert len(results) >= 1


class TestCoherenceMetric:
    """coherence should detect duplicates, not return hardcoded 1.0."""

    def test_coherence_all_unique(self, tmp_data_dir):
        """All unique items → coherence = 1.0."""

        items = [
            MemoryItem(
                content=f"unique content {i}",
                memory_type=MemoryType.OBSERVATION,
                tier=MemoryTier.RECALL,
                importance=0.5,
            )
            for i in range(5)
        ]
        cfg = Config()
        score = compute_health([], items, cfg.rooms)
        assert score.coherence == 1.0

    def test_coherence_with_duplicates(self):
        """Duplicate content → coherence < 1.0."""

        items = [
            MemoryItem(
                content="same content",
                memory_type=MemoryType.OBSERVATION,
                tier=MemoryTier.RECALL,
                importance=0.5,
            )
            for _ in range(5)
        ]
        cfg = Config()
        score = compute_health([], items, cfg.rooms)
        assert score.coherence < 1.0
        # 5 items, 4 are duplicates: coherence = 1 - 4/5 = 0.2
        assert abs(score.coherence - 0.2) < 0.01

    def test_coherence_empty(self):
        """Empty items → coherence = 0.0."""
        cfg = Config()
        score = compute_health([], [], cfg.rooms)
        assert score.coherence == 0.0


class TestPublicAPI:
    """MemoryService public API methods for encapsulation."""

    def test_get_recent(self, tmp_data_dir):
        """get_recent() returns recall items without private field access."""
        svc = MemoryService(tmp_data_dir)
        svc.save("recent item A", importance=0.3)
        svc.save("recent item B", importance=0.4)

        recent = svc.get_recent(5)
        assert len(recent) == 2

    def test_get_all_items(self, tmp_data_dir):
        """get_all_items() returns (core, recall) tuple."""
        svc = MemoryService(tmp_data_dir)
        svc.save("core item", importance=0.9, room="test")
        svc.save("recall item", importance=0.3, room="test")

        core, recall = svc.get_all_items()
        assert len(core) == 1
        assert len(recall) == 1

    def test_get_hybrid_retriever_none(self, tmp_data_dir):
        """Without archival, get_hybrid_retriever() returns None."""
        svc = MemoryService(tmp_data_dir)
        assert svc.get_hybrid_retriever() is None

    def test_get_hybrid_retriever_with_archival(self, full_svc):
        """With archival, get_hybrid_retriever() returns an instance."""
        assert full_svc.get_hybrid_retriever() is not None


# ── Round 2 fixes ────────────────────────────────────────────────────


class TestUpdateSyncsArchival:
    """update() must delete old entry and index new version in ArchivalStore."""

    def test_update_removes_old_from_archival(self, full_svc, archival_store):
        """After update, old memory ID is deleted from ArchivalStore."""
        item = full_svc.save("原始内容", importance=0.3, room="general")
        assert archival_store.count() == 1

        full_svc.update(item.id, "更新后的内容", reason="修正")

        # Old entry should be gone
        assert archival_store.get(item.id) is None

    def test_update_indexes_new_in_archival(self, full_svc, archival_store):
        """After update, new version is indexed in ArchivalStore."""
        item = full_svc.save("原始内容", importance=0.3, room="general")
        new_item = full_svc.update(item.id, "更新后的内容", reason="修正")

        # New entry should exist
        record = archival_store.get(new_item.id)
        assert record is not None
        assert record["content"] == "更新后的内容"

    def test_update_archival_count_unchanged(self, full_svc, archival_store):
        """After update, total archival count stays at 1 (delete old + add new)."""
        item = full_svc.save("原始内容", importance=0.3, room="general")
        full_svc.update(item.id, "更新后的内容", reason="修正")
        assert archival_store.count() == 1

    def test_update_core_item_syncs_archival(self, full_svc, archival_store):
        """Core item update also syncs ArchivalStore."""
        item = full_svc.save("核心知识", importance=0.9, room="projects")
        assert archival_store.count() == 1

        new_item = full_svc.update(item.id, "核心知识v2", reason="版本更新")
        assert archival_store.get(item.id) is None
        assert archival_store.get(new_item.id) is not None


class TestForgetSyncsArchival:
    """forget() must remove pruned entry from ArchivalStore."""

    def test_forget_removes_from_archival(self, full_svc, archival_store):
        """Forgotten memory is deleted from ArchivalStore."""
        item = full_svc.save("临时记忆", importance=0.3, room="general")
        assert archival_store.count() == 1

        full_svc.forget(item.id, reason="不再需要")
        assert archival_store.count() == 0
        assert archival_store.get(item.id) is None

    def test_forget_core_item_removes_from_archival(self, full_svc, archival_store):
        """Forgetting a core item also removes from ArchivalStore."""
        item = full_svc.save("重要但已过时", importance=0.9, room="projects")
        assert archival_store.count() == 1

        full_svc.forget(item.id, reason="信息过时")
        assert archival_store.count() == 0

    def test_forget_one_of_many_only_removes_target(self, full_svc, archival_store):
        """forget() only removes the targeted item, not others."""
        a = full_svc.save("记忆A", importance=0.3, room="general")
        b = full_svc.save("记忆B", importance=0.4, room="general")

        assert archival_store.count() == 2
        full_svc.forget(a.id, reason="删除A")
        assert archival_store.count() == 1
        assert archival_store.get(b.id) is not None


class TestSaveArchivalDeterministic:
    """save() archival indexing must complete before returning (not fire-and-forget)."""

    def test_save_immediately_searchable_in_archival(self, full_svc, archival_store):
        """Immediately after save(), item is present in archival (no race)."""
        item = full_svc.save("确定性测试", importance=0.3, room="general")
        # Must be present immediately — no async delay
        record = archival_store.get(item.id)
        assert record is not None
        assert record["content"] == "确定性测试"

    @pytest.mark.asyncio
    async def test_save_in_async_context_still_deterministic(self, full_svc, archival_store):
        """save() called from async context still indexes synchronously."""
        item = full_svc.save("异步上下文确定性测试", importance=0.3, room="general")
        record = archival_store.get(item.id)
        assert record is not None
        assert record["content"] == "异步上下文确定性测试"

    @pytest.mark.asyncio
    async def test_save_batch_indexes_all_deterministically(
        self,
        tmp_data_dir,
        mock_embedding,
        archival_store,
    ):
        """save_batch() through FactExtractor also indexes all results deterministically."""
        from tests.conftest import MockLLM

        mock_llm = MockLLM(
            responses=[
                '[{"content": "事实A", "importance": 0.5, "tags": ["test"]},'
                '{"content": "事实B", "importance": 0.6, "tags": ["test"]}]'
            ]
        )
        svc = MemoryService(
            tmp_data_dir,
            llm=mock_llm,
            archival_store=archival_store,
            embedding=mock_embedding,
        )
        items = await svc.save_batch(["some text"])
        assert archival_store.count() == len(items)


class TestCLIEmbeddingConfig:
    """CLI _build_embedding_provider passes correct config objects."""

    def test_build_with_yaml_config_local(self, tmp_data_dir):
        """_build_embedding_provider with local config passes EmbeddingConfig object."""
        from memory_palace.integration.cli import _build_embedding_provider

        # Write a YAML config with local embedding
        yaml_path = tmp_data_dir / "memory_palace.yaml"
        yaml_path.write_text(
            "embedding:\n  provider: local\n  model_id: all-MiniLM-L6-v2\n  dimension: 384\n"
        )

        # This should fail with ImportError (sentence-transformers not installed)
        # but NOT with TypeError (wrong constructor args).
        # If it returns None, it could be either — so we catch ImportError.
        try:
            result = _build_embedding_provider(tmp_data_dir)
            # If sentence-transformers IS installed, result should not be None
            if result is not None:
                assert result.dimension == 384
        except ImportError:
            # Expected: sentence-transformers not installed
            pass

    def test_build_without_config_no_api_key(self, tmp_data_dir, monkeypatch):
        """Without OPENAI_API_KEY, returns None gracefully (not TypeError)."""
        from memory_palace.integration.cli import _build_embedding_provider

        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = _build_embedding_provider(tmp_data_dir)
        assert result is None
