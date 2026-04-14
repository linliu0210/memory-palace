"""MCPServiceManager — Request-level context for MCP Server.

Singleton MemoryService manager for MCP server lifecycle.
Ensures all MCP tools and resources share the same MemoryService instance.

Reuses cli.py patterns for building MemoryService and LLM providers.
Uses asyncio.Lock for thread-safe lazy initialization.

Ref: CONVENTIONS_V10.md §7, TASK_R18
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from memory_palace.foundation.llm import LLMProvider
    from memory_palace.service.memory_service import MemoryService

logger = structlog.get_logger(__name__)


class MCPServiceManager:
    """Singleton MemoryService for MCP server lifecycle.

    Lazy-initializes a MemoryService on first access.
    All MCP tools/resources call ``get_service()`` to obtain the shared instance.

    Usage::

        MCPServiceManager.configure(data_dir)  # before server starts
        svc = await MCPServiceManager.get_service()
        svc.save(...)
    """

    _service: MemoryService | None = None
    _llm: LLMProvider | None = None
    _lock: asyncio.Lock | None = None
    _data_dir: Path = Path("~/.memory_palace").expanduser()

    @classmethod
    def _ensure_lock(cls) -> asyncio.Lock:
        """Create lock lazily to avoid event-loop issues at import time."""
        if cls._lock is None:
            cls._lock = asyncio.Lock()
        return cls._lock

    @classmethod
    def configure(cls, data_dir: Path, llm: LLMProvider | None = None) -> None:
        """Configure data directory and optional LLM before server starts.

        Args:
            data_dir: Root data directory for stores and audit log.
            llm: Optional LLM provider for curate/reflect operations.
        """
        cls._data_dir = data_dir
        cls._llm = llm
        # Reset service so next get_service() re-initializes
        cls._service = None
        cls._lock = None

    @classmethod
    async def get_service(cls) -> MemoryService:
        """Get or lazily create the shared MemoryService instance.

        Returns:
            The singleton MemoryService.
        """
        lock = cls._ensure_lock()
        async with lock:
            if cls._service is None:
                cls._service = cls._build_service()
                logger.info(
                    "MCP MemoryService initialized",
                    data_dir=str(cls._data_dir),
                    has_llm=cls._service._llm is not None,
                )
            return cls._service

    @classmethod
    def _build_service(cls) -> MemoryService:
        """Build MemoryService with full v1.0 stack.

        Wires embedding → archival → graph based on config.
        Gracefully degrades: no API key → FTS-only, no kuzu → no graph.
        """
        from memory_palace.service.memory_service import MemoryService

        # Ensure data directory exists
        cls._data_dir.mkdir(parents=True, exist_ok=True)
        (cls._data_dir / "core").mkdir(exist_ok=True)

        # Embedding + Archival
        embedding = cls._try_build_embedding()
        archival_store = None
        if embedding is not None:
            from memory_palace.store.archival_store import ArchivalStore

            archival_store = ArchivalStore(
                data_dir=cls._data_dir, embedding=embedding,
            )

        # Graph (optional — only when config.graph.enabled)
        graph_store = None
        try:
            from memory_palace.config import Config

            yaml_path = cls._data_dir / "memory_palace.yaml"
            cfg = Config.from_yaml(yaml_path) if yaml_path.exists() else Config()
            if cfg.graph.enabled:
                from memory_palace.store.graph_store import GraphStore

                graph_store = GraphStore(cls._data_dir)
        except ImportError:
            pass  # kuzu not installed — degrade gracefully

        # Auto-build LLM from config/env if not explicitly provided
        llm = cls._llm
        if llm is None:
            llm = cls._try_build_llm()

        return MemoryService(
            cls._data_dir,
            llm=llm,
            archival_store=archival_store,
            embedding=embedding,
            graph_store=graph_store,
        )

    @classmethod
    def _try_build_llm(cls) -> LLMProvider | None:
        """Attempt to build LLM from config (YAML, env vars, or defaults)."""
        try:
            from memory_palace.config import Config
            from memory_palace.foundation.llm import ModelConfig
            from memory_palace.foundation.openai_provider import OpenAIProvider

            yaml_path = cls._data_dir / "memory_palace.yaml"
            cfg = Config.from_yaml(yaml_path) if yaml_path.exists() else Config()
            model_config = ModelConfig(
                provider=cfg.llm.provider,
                model_id=cfg.llm.model_id,
                base_url=cfg.llm.base_url,
                max_tokens=cfg.llm.max_tokens,
            )
            # Only build if we have an API key (or local provider)
            from memory_palace.foundation.llm import get_api_key

            if model_config.provider != "local" and not get_api_key(model_config.provider):
                return None
            return OpenAIProvider(model_config)
        except Exception:
            logger.warning("Failed to build LLM from config", exc_info=True)
            return None

    @classmethod
    def _try_build_embedding(cls):
        """Attempt to build EmbeddingProvider from config, return None on failure."""
        import os

        try:
            from memory_palace.config import Config
            from memory_palace.foundation.embedding import EmbeddingConfig

            yaml_path = cls._data_dir / "memory_palace.yaml"
            if yaml_path.exists():
                cfg = Config.from_yaml(yaml_path)
                emb_cfg = cfg.embedding
            else:
                emb_cfg = EmbeddingConfig()

            if emb_cfg.provider == "local":
                from memory_palace.foundation.local_embedding import LocalEmbedding

                return LocalEmbedding(emb_cfg)
            else:
                if not os.environ.get("OPENAI_API_KEY"):
                    return None
                from memory_palace.foundation.openai_embedding import OpenAIEmbedding

                return OpenAIEmbedding(config=emb_cfg)
        except Exception:
            logger.warning("Failed to build embedding provider", exc_info=True)
            return None

    @classmethod
    async def shutdown(cls) -> None:
        """Clean up service references."""
        cls._service = None
        cls._llm = None
        cls._lock = None
        logger.info("MCP MemoryService shut down")
