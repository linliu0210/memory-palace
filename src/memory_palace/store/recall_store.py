"""RecallStore — SQLite + FTS5 full-text search storage.

Stores MemoryItems with all fields in a relational table,
with a shadow FTS5 virtual table for keyword search.

Ref: SPEC v2.0 §4.1 S-9
"""

import json
import re
import sqlite3
from pathlib import Path

from memory_palace.models.memory import MemoryItem, MemoryStatus

# CJK Unicode ranges for pre-tokenization
_CJK_RE = re.compile(r"([\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff])")


def _tokenize_cjk(text: str) -> str:
    """Pre-process text for FTS5 by spacing CJK characters.

    unicode61 groups contiguous CJK into one token; spacing ensures
    per-character tokens so substring search works.
    """
    return _CJK_RE.sub(r" \1 ", text)


def _row_to_memory_item(row: sqlite3.Row) -> MemoryItem:
    """Convert a database row to a MemoryItem."""
    return MemoryItem(
        id=row["id"],
        content=row["content"],
        memory_type=row["memory_type"],
        tier=row["tier"],
        importance=row["importance"],
        tags=json.loads(row["tags"]) if row["tags"] else [],
        room=row["room"],
        user_pinned=bool(row["user_pinned"]),
        created_at=row["created_at"],
        accessed_at=row["accessed_at"],
        updated_at=row["updated_at"],
        access_count=row["access_count"],
        status=row["status"],
        version=row["version"],
        parent_id=row["parent_id"],
        merged_from=json.loads(row["merged_from"]) if row["merged_from"] else [],
        superseded_by=row["superseded_by"],
        change_reason=row["change_reason"],
        embedding=json.loads(row["embedding"]) if row["embedding"] else None,
        source_hash=row["source_hash"],
    )


class RecallStore:
    """Recall Memory store: on-demand searchable memory.

    SQLite backend with FTS5 full-text search.
    BM25 ranking for search results.

    CJK characters are pre-tokenized (spaced) to enable per-character
    matching since standard FTS5 has no CJK word segmenter.
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialize RecallStore.

        Args:
            data_dir: Root data directory. Database stored at {data_dir}/recall.db.
        """
        self._db_path = data_dir / "recall.db"
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        # R19: WAL mode for concurrent read support
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        cursor = self._conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                tier TEXT NOT NULL,
                importance REAL NOT NULL,
                tags TEXT,
                room TEXT NOT NULL DEFAULT 'general',
                user_pinned INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                accessed_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                access_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'active',
                version INTEGER NOT NULL DEFAULT 1,
                parent_id TEXT,
                merged_from TEXT,
                superseded_by TEXT,
                change_reason TEXT,
                embedding TEXT,
                source_hash TEXT
            )
        """)
        # Reason: Standalone FTS5 table (no content sync) so we can
        # pre-process CJK text before indexing. unicode61 is standard built-in.
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content,
                tags,
                room,
                tokenize='unicode61'
            )
        """)
        self._conn.commit()

    def insert(self, item: MemoryItem) -> None:
        """Insert a MemoryItem into the store.

        Args:
            item: The MemoryItem to insert.

        Raises:
            sqlite3.IntegrityError: If an item with the same ID already exists.
        """
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT INTO memories (
                id, content, memory_type, tier, importance, tags, room,
                user_pinned, created_at, accessed_at, updated_at,
                access_count, status, version, parent_id, merged_from,
                superseded_by, change_reason, embedding, source_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.id,
                item.content,
                item.memory_type,
                item.tier,
                item.importance,
                json.dumps(item.tags),
                item.room,
                int(item.user_pinned),
                item.created_at.isoformat(),
                item.accessed_at.isoformat(),
                item.updated_at.isoformat(),
                item.access_count,
                item.status,
                item.version,
                item.parent_id,
                json.dumps(item.merged_from),
                item.superseded_by,
                item.change_reason,
                json.dumps(item.embedding) if item.embedding is not None else None,
                item.source_hash,
            ),
        )
        # Reason: Same rowid in FTS table as main table for JOIN
        rowid = cursor.lastrowid
        fts_content = _tokenize_cjk(item.content)
        fts_tags = _tokenize_cjk(item.room if not item.tags else " ".join(item.tags))
        cursor.execute(
            "INSERT INTO memories_fts(rowid, content, tags, room) VALUES (?, ?, ?, ?)",
            (rowid, fts_content, fts_tags, item.room),
        )
        self._conn.commit()

    def search(self, query: str, room: str | None = None, limit: int = 10) -> list[dict]:
        """Search memories using FTS5 full-text search.

        Args:
            query: Search query string.
            room: Optional room filter.
            limit: Maximum number of results.

        Returns:
            List of dicts with 'item' (MemoryItem) and 'rank' (float, raw BM25).
        """
        fts_query = _tokenize_cjk(query)
        if room is not None:
            sql = """
                SELECT m.*, f.rank
                FROM memories_fts f
                JOIN memories m ON m.rowid = f.rowid
                WHERE memories_fts MATCH ? AND m.room = ? AND m.status = 'active'
                ORDER BY f.rank
                LIMIT ?
            """
            rows = self._conn.execute(sql, (fts_query, room, limit)).fetchall()
        else:
            sql = """
                SELECT m.*, f.rank
                FROM memories_fts f
                JOIN memories m ON m.rowid = f.rowid
                WHERE memories_fts MATCH ? AND m.status = 'active'
                ORDER BY f.rank
                LIMIT ?
            """
            rows = self._conn.execute(sql, (fts_query, limit)).fetchall()

        results = []
        for row in rows:
            item = _row_to_memory_item(row)
            # Reason: FTS5 rank is negative (lower = more relevant), keep raw value
            results.append({"item": item, "rank": row["rank"]})
        return results

    def get(self, memory_id: str) -> MemoryItem | None:
        """Get a single MemoryItem by ID.

        Args:
            memory_id: The memory ID to look up.

        Returns:
            MemoryItem if found, None otherwise.
        """
        row = self._conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
        if row is None:
            return None
        return _row_to_memory_item(row)

    def get_recent(self, n: int = 10) -> list[MemoryItem]:
        """Get the N most recently created items.

        Args:
            n: Number of items to return.

        Returns:
            List of MemoryItems ordered by created_at descending.
        """
        rows = self._conn.execute(
            "SELECT * FROM memories WHERE status = 'active' ORDER BY created_at DESC LIMIT ?",
            (n,),
        ).fetchall()
        return [_row_to_memory_item(row) for row in rows]

    def count(self) -> int:
        """Return total number of records.

        Returns:
            Count of all stored memories.
        """
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM memories WHERE status = 'active'"
        ).fetchone()
        return row["cnt"]

    def update_status(self, memory_id: str, status: MemoryStatus) -> None:
        """Update the status of a memory item.

        Args:
            memory_id: The memory ID to update.
            status: New status value.
        """
        self._conn.execute(
            "UPDATE memories SET status = ? WHERE id = ?",
            (status, memory_id),
        )
        self._conn.commit()

    def touch(self, memory_id: str) -> None:
        """Increment access count and update accessed_at timestamp.

        Args:
            memory_id: The memory ID to touch.
        """
        from datetime import datetime

        now = datetime.now().isoformat()
        self._conn.execute(
            """
            UPDATE memories
            SET access_count = access_count + 1, accessed_at = ?
            WHERE id = ?
            """,
            (now, memory_id),
        )
        self._conn.commit()

    # Valid columns for update_field (safety whitelist)
    _UPDATABLE_FIELDS: frozenset[str] = frozenset(
        {
            "content",
            "memory_type",
            "tier",
            "importance",
            "tags",
            "room",
            "user_pinned",
            "accessed_at",
            "updated_at",
            "access_count",
            "status",
            "version",
            "parent_id",
            "merged_from",
            "superseded_by",
            "change_reason",
            "embedding",
            "source_hash",
        }
    )

    def update_field(self, memory_id: str, field: str, value: object) -> None:
        """Update a single field on a memory record.

        Eliminates the need for callers to access the database directly.
        Only columns listed in ``_UPDATABLE_FIELDS`` are accepted.

        Args:
            memory_id: The memory ID to update.
            field: Column name to update.
            value: New value for the field.

        Raises:
            ValueError: If ``field`` is not in the updatable whitelist.

        Ref: TD-1 — encapsulate field-level mutations inside RecallStore.
        """
        if field not in self._UPDATABLE_FIELDS:
            raise ValueError(
                f"Field '{field}' is not updatable. Allowed: {sorted(self._UPDATABLE_FIELDS)}"
            )

        # Serialize list/dict values to JSON for storage
        if isinstance(value, (list, dict)):
            value = json.dumps(value)
        elif isinstance(value, bool):
            value = int(value)

        self._conn.execute(
            f"UPDATE memories SET {field} = ? WHERE id = ?",  # noqa: S608
            (value, memory_id),
        )
        self._conn.commit()
