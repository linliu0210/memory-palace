# Round 24 — KuzuDB 图存储

> **Round**: 24 / Phase D  
> **分支**: `feat/v1.0-phase-d`  
> **前置**: Phase C 完成 (R21-R23)  
> **交付**: GraphStore (KuzuDB) + 真实 Proximity 评分 + Room 图节点

---

## 目标

用 KuzuDB 嵌入式图数据库替代 Room bonus 的简单 0/1 匹配，实现真实的图距离 Proximity 评分。

Room 成为图节点，记忆之间可以有关联边。

---

## 必读文档

1. `PROJECT_CONTEXT_V10.md` + `CONVENTIONS_V10.md`
2. `src/memory_palace/engine/scoring.py` — 现有 room_bonus 逻辑
3. `src/memory_palace/models/memory.py` — MemoryItem.room 字段
4. `src/memory_palace/config.py` — RoomConfig
5. KuzuDB Python API: `pip install kuzu` 后参考 https://docs.kuzudb.com

---

## 交付件

### 1. [MODIFY] `pyproject.toml`

```diff
 dependencies = [
     ...
+    "kuzu>=0.4",
 ]
```

### 2. [NEW] `src/memory_palace/store/graph_store.py`

```python
class GraphStore:
    """KuzuDB-based graph storage for Room topology and memory relations.
    
    Schema:
    - Node: Room (name, description, parent?)
    - Node: Memory (id, content_preview, room, importance)
    - Edge: BELONGS_TO (Memory → Room)
    - Edge: RELATED_TO (Memory → Memory, weight, relation_type)
    - Edge: PARENT_OF (Room → Room, 层级关系)
    """
    
    def __init__(self, data_dir: Path): ...
    
    # Room 操作
    def add_room(self, room: RoomConfig) -> None: ...
    def get_room_distance(self, room_a: str, room_b: str) -> int: ...
    
    # 记忆关联
    def add_memory_node(self, item: MemoryItem) -> None: ...
    def add_relation(self, from_id: str, to_id: str, relation_type: str, weight: float = 1.0) -> None: ...
    def get_related(self, memory_id: str, max_hops: int = 2) -> list[str]: ...
    
    # Proximity
    def proximity_score(self, query_room: str, memory_room: str) -> float:
        """1.0 / (1.0 + graph_distance). 替代简单 room_bonus."""
    
    def close(self) -> None: ...
```

### 3. [MODIFY] `src/memory_palace/engine/scoring.py`

- `ScoredCandidate` 的 `room_bonus` 改为 `proximity: float = 0.0`
- `rank()` 使用 proximity 替代 room_bonus
- 向后兼容: `room_bonus` 参数仍接受但映射到 proximity

### 4. [MODIFY] `src/memory_palace/service/memory_service.py`

- `save()` 时同步写入 GraphStore (如果注入了)
- `search()` 时从 GraphStore 获取 proximity 而非硬编码 room_bonus

### 5. [MODIFY] `src/memory_palace/config.py`

```python
class GraphConfig(BaseModel):
    enabled: bool = False  # 默认关闭，需显式启用
    include_relations: bool = True

class RoomConfig(BaseModel):
    name: str
    description: str = ""
    parent: str | None = None  # 层级关系
```

### 6. [NEW] `tests/test_store/test_graph_store.py`

```
test_add_room — 添加房间节点
test_room_distance_same — 同房间距离 = 0
test_room_distance_sibling — 兄弟房间距离 = 2
test_room_distance_parent_child — 父子距离 = 1
test_add_memory_node — 添加记忆节点
test_add_relation — 添加关联边
test_get_related — 获取关联记忆
test_proximity_same_room — proximity = 1.0
test_proximity_distant_room — proximity < 0.5
test_proximity_unknown_room — fallback = 0.0
test_scoring_with_proximity — ScoredCandidate 使用 proximity
test_close_cleanup — 关闭后资源释放
```

预计 ~12 tests。

---

## 约束

1. GraphStore 默认 disabled — `graph.enabled = False` 时完全跳过
2. 不强制所有记忆建图 — 增量同步，skip on error
3. KuzuDB 文件存储在 `data_dir/graph/`
4. 向后兼容: room_bonus 参数仍可用

---

## 验证

```bash
pip install "kuzu>=0.4"
pytest tests/ -q
pytest tests/test_store/test_graph_store.py -v
ruff check
git commit -m "feat(R24): KuzuDB graph storage with real proximity scoring"
```
