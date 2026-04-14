"""GraphStore — KuzuDB-based graph storage for Room topology and memory relations.

Schema:
- Node: Room (name, description) — PRIMARY KEY(name)
- Node: Memory (id, content_preview, room, importance) — PRIMARY KEY(id)
- Edge: BELONGS_TO (Memory → Room)
- Edge: RELATED_TO (Memory → Memory, weight, relation_type)
- Edge: PARENT_OF (Room → Room, 层级关系)

Ref: R24 KuzuDB Graph Storage
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from memory_palace.config import RoomConfig
    from memory_palace.models.memory import MemoryItem

logger = structlog.get_logger(__name__)

# Maximum content preview length stored in the graph
_PREVIEW_LEN = 80


class GraphStore:
    """KuzuDB-based graph storage for Room topology and memory relations.

    Stores rooms as graph nodes with parent-child edges, enabling real
    graph-distance proximity scoring instead of simple 0/1 room matching.

    All mutating operations are wrapped in try/except to ensure failures
    do not block the main memory pipeline (incremental sync, skip on error).

    Args:
        data_dir: Root data directory. Graph DB is stored at ``data_dir/graph/``.
    """

    def __init__(self, data_dir: Path) -> None:
        try:
            import kuzu
        except ImportError:
            raise ImportError(
                "kuzu is required for GraphStore. "
                "Install with: pip install memory-palace[graph]"
            ) from None

        self._db_path = data_dir / "graph"
        self._db = kuzu.Database(str(self._db_path))
        self._conn = kuzu.Connection(self._db)
        self._init_schema()

    def _init_schema(self) -> None:
        """Create node/edge tables if they don't already exist."""
        stmts = [
            (
                "CREATE NODE TABLE IF NOT EXISTS Room"
                "(name STRING, description STRING, PRIMARY KEY(name))"
            ),
            (
                "CREATE NODE TABLE IF NOT EXISTS Memory"
                "(id STRING, content_preview STRING, room STRING,"
                " importance DOUBLE, PRIMARY KEY(id))"
            ),
            "CREATE REL TABLE IF NOT EXISTS PARENT_OF(FROM Room TO Room)",
            "CREATE REL TABLE IF NOT EXISTS BELONGS_TO(FROM Memory TO Room)",
            (
                "CREATE REL TABLE IF NOT EXISTS RELATED_TO"
                "(FROM Memory TO Memory, weight DOUBLE, relation_type STRING)"
            ),
        ]
        for stmt in stmts:
            self._conn.execute(stmt)

    # ── Room operations ─────────────────────────────────────

    def add_room(self, room: RoomConfig) -> None:
        """Insert or update a Room node. Creates PARENT_OF edge if parent is set.

        Args:
            room: RoomConfig with name, description, and optional parent.
        """
        try:
            self._conn.execute(
                "MERGE (r:Room {name: $name}) SET r.description = $description",
                {"name": room.name, "description": room.description},
            )
            if room.parent:
                # Ensure parent exists as a node first
                self._conn.execute(
                    "MERGE (r:Room {name: $name})",
                    {"name": room.parent},
                )
                # Delete existing PARENT_OF edge to this room, then recreate
                self._conn.execute(
                    "MATCH (p:Room)-[e:PARENT_OF]->(c:Room {name: $child}) DELETE e",
                    {"child": room.name},
                )
                self._conn.execute(
                    "MATCH (p:Room {name: $parent}), (c:Room {name: $child})"
                    " CREATE (p)-[:PARENT_OF]->(c)",
                    {"parent": room.parent, "child": room.name},
                )
        except Exception:
            logger.warning("graph_add_room_failed", room=room.name, exc_info=True)

    def get_room_distance(self, room_a: str, room_b: str) -> int:
        """Compute shortest graph distance between two rooms via PARENT_OF edges.

        Args:
            room_a: Source room name.
            room_b: Target room name.

        Returns:
            Shortest path length (number of edges). Returns -1 if no path exists
            or either room is unknown.
        """
        if room_a == room_b:
            # Verify the room exists
            result = self._conn.execute(
                "MATCH (r:Room {name: $name}) RETURN r.name",
                {"name": room_a},
            )
            if result.has_next():
                return 0
            return -1

        try:
            result = self._conn.execute(
                "MATCH p = (a:Room {name: $ra})-[:PARENT_OF*1..10]-(b:Room {name: $rb})"
                " RETURN min(size(nodes(p))) - 1 AS dist",
                {"ra": room_a, "rb": room_b},
            )
            if result.has_next():
                row = result.get_next()
                dist_val = row[0]
                if dist_val is None:
                    return -1
                return int(dist_val)
            return -1
        except Exception:
            logger.warning(
                "graph_room_distance_failed",
                room_a=room_a,
                room_b=room_b,
                exc_info=True,
            )
            return -1

    # ── Memory operations ───────────────────────────────────

    def add_memory_node(self, item: MemoryItem) -> None:
        """Insert a Memory node and BELONGS_TO edge to its room.

        Args:
            item: The MemoryItem to add to the graph.
        """
        try:
            preview = item.content[:_PREVIEW_LEN]
            self._conn.execute(
                "MERGE (m:Memory {id: $id})"
                " SET m.content_preview = $preview,"
                " m.room = $room, m.importance = $imp",
                {
                    "id": item.id,
                    "preview": preview,
                    "room": item.room,
                    "imp": float(item.importance),
                },
            )
            # Ensure room node exists
            self._conn.execute(
                "MERGE (r:Room {name: $name})",
                {"name": item.room},
            )
            # Recreate BELONGS_TO edge (delete old first to avoid duplicates)
            self._conn.execute(
                "MATCH (m:Memory {id: $id})-[e:BELONGS_TO]->(:Room) DELETE e",
                {"id": item.id},
            )
            self._conn.execute(
                "MATCH (m:Memory {id: $id}), (r:Room {name: $room})"
                " CREATE (m)-[:BELONGS_TO]->(r)",
                {"id": item.id, "room": item.room},
            )
        except Exception:
            logger.warning("graph_add_memory_failed", memory_id=item.id, exc_info=True)

    def remove_memory_node(self, memory_id: str) -> None:
        """Remove a Memory node and its edges from the graph.

        Args:
            memory_id: The memory ID to remove.
        """
        try:
            # Delete edges first (BELONGS_TO and RELATED_TO)
            self._conn.execute(
                "MATCH (m:Memory {id: $id})-[e:BELONGS_TO]->(:Room) DELETE e",
                {"id": memory_id},
            )
            self._conn.execute(
                "MATCH (m:Memory {id: $id})-[e:RELATED_TO]-(:Memory) DELETE e",
                {"id": memory_id},
            )
            self._conn.execute(
                "MATCH (m:Memory {id: $id}) DELETE m",
                {"id": memory_id},
            )
        except Exception:
            logger.warning("graph_remove_memory_failed", memory_id=memory_id, exc_info=True)

    def add_relation(
        self,
        from_id: str,
        to_id: str,
        relation_type: str,
        weight: float = 1.0,
    ) -> None:
        """Add a RELATED_TO edge between two Memory nodes.

        Args:
            from_id: Source memory ID.
            to_id: Target memory ID.
            relation_type: Type of relation (e.g. "semantic", "temporal").
            weight: Edge weight [0, 1].
        """
        try:
            self._conn.execute(
                "MATCH (a:Memory {id: $fid}), (b:Memory {id: $tid})"
                " CREATE (a)-[:RELATED_TO {weight: $w, relation_type: $rt}]->(b)",
                {"fid": from_id, "tid": to_id, "w": float(weight), "rt": relation_type},
            )
        except Exception:
            logger.warning(
                "graph_add_relation_failed",
                from_id=from_id,
                to_id=to_id,
                exc_info=True,
            )

    def get_related(self, memory_id: str, max_hops: int = 2) -> list[str]:
        """Get IDs of memories related within max_hops via RELATED_TO edges.

        Args:
            memory_id: The source memory ID.
            max_hops: Maximum traversal depth.

        Returns:
            List of related memory IDs (excluding source).
        """
        try:
            result = self._conn.execute(
                f"MATCH (a:Memory {{id: $id}})-[:RELATED_TO*1..{max_hops}]-(b:Memory)"
                " WHERE b.id <> $id RETURN DISTINCT b.id",
                {"id": memory_id},
            )
            ids: list[str] = []
            while result.has_next():
                ids.append(result.get_next()[0])
            return ids
        except Exception:
            logger.warning(
                "graph_get_related_failed", memory_id=memory_id, exc_info=True
            )
            return []

    # ── Proximity ───────────────────────────────────────────

    def proximity_score(self, query_room: str, memory_room: str) -> float:
        """Compute proximity score based on graph distance between rooms.

        ``proximity = 1.0 / (1.0 + distance)``

        Replaces the simple 0/1 room_bonus with a continuous score.

        Args:
            query_room: The query context room.
            memory_room: The memory item's room.

        Returns:
            Proximity in (0, 1.0]. Returns 0.0 if either room is unknown
            or no path exists.
        """
        dist = self.get_room_distance(query_room, memory_room)
        if dist < 0:
            return 0.0
        return 1.0 / (1.0 + dist)

    # ── Lifecycle ───────────────────────────────────────────

    def close(self) -> None:
        """Release database resources."""
        try:
            self._conn.close()
        except Exception:
            pass
        self._conn = None  # type: ignore[assignment]
        self._db = None  # type: ignore[assignment]
