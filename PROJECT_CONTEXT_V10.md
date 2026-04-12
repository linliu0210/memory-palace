# Memory Palace v1.0 — Project Context (for Subagents)

> **读者**: 执行 v1.0 开发的 AI Subagent  
> **目的**: 提供必要的项目上下文，使你能独立编码  
> **规则**: 本文件是压缩后的事实，不含观点。编码规范见 CONVENTIONS_V10.md

---

## 1. 项目定位

给 AI Agent 装一套「记忆操作系统」。三个核心隐喻：
- **宫殿 (Palace)** = 分层存储系统
- **房间 (Room)** = 记忆分类空间
- **搬运小人 (Curator)** = 自动整理代理

## 2. 技术栈

```
Python 3.11+ | Pydantic 2.x | SQLite (FTS5) | ChromaDB 1.x
async: httpx + asyncio | CLI: Typer + Rich | Log: structlog
Test: pytest + pytest-asyncio | Lint: ruff
```

依赖来源: `pyproject.toml` (项目根目录)

## 3. 五层架构 (严格单向依赖)

```
5F Integration  →  CLI (cli.py), MCP Server (tools.py placeholder)  
4F Service      →  MemoryService, HybridRetriever, ContextCompiler, CuratorService+Graph
3F Engine       →  ScoringEngine, FactExtractor, ReconcileEngine, ReflectionEngine, Health
2F Storage      →  CoreStore (JSON), RecallStore (SQLite+FTS5), ArchivalStore (ChromaDB)
1F Foundation   →  Config, AuditLog, LLMProvider(Protocol), EmbeddingProvider(Protocol)
   Models       →  MemoryItem, AuditEntry, CuratorReport (Pydantic BaseModel)
```

**依赖方向**: 上层可以 import 下层，反过来禁止。同层之间避免循环。

## 4. 关键文件速查

### 4.1 Models (`src/memory_palace/models/`)

| 文件 | 核心类 | 你需要知道的 |
|------|--------|------------|
| `memory.py` | `MemoryItem`, `MemoryStatus`, `MemoryTier`, `MemoryType`, `Room` | MemoryItem 是系统的原子单位。tier: CORE/RECALL。status: ACTIVE/SUPERSEDED/PRUNED |
| `audit.py` | `AuditEntry`, `AuditAction` | AuditAction 枚举: CREATE/UPDATE/DELETE/PROMOTE/DEMOTE |
| `curator.py` | `CuratorReport` | run() 的返回值。含 facts_extracted, memories_created/updated/pruned, health, duration_seconds, errors |

### 4.2 Foundation (`src/memory_palace/foundation/`)

| 文件 | 接口 | 你需要知道的 |
|------|------|------------|
| `llm.py` | `LLMProvider(Protocol)` | 方法: `async complete(prompt, response_format?) -> str`。所有 LLM 操作通过此 Protocol |
| `embedding.py` | `EmbeddingProvider(Protocol)` | 方法: `async embed(texts: list[str]) -> list[list[float]]`。`EmbeddingConfig` 含 provider/model_id/dimension |
| `audit_log.py` | `AuditLog` | append-only JSONL。方法: `append(entry)`, `read(memory_id?)` |
| `openai_provider.py` | `OpenAIProvider` | httpx async POST to OpenAI-compatible API |

### 4.3 Storage (`src/memory_palace/store/`)

| 文件 | 存储介质 | 关键方法 |
|------|---------|---------|
| `core_store.py` | JSON 平文件 `core/{room}.json` | `save(room, item)`, `load_all()`, `delete(room, id)` — ≤2KB 预算 |
| `recall_store.py` | SQLite + FTS5 | `insert(item)`, `fts_search(query, top_k)`, `get_recent(n)`, `get_by_id(id)`, `update_field(id, field, value)` |
| `archival_store.py` | ChromaDB 向量 | `insert(item, embedding)`, `search(query_embedding, top_k)`, `delete(id)` — 全量语义索引 |

### 4.4 Engine (`src/memory_palace/engine/`)

| 文件 | LLM? | 核心函数/类 |
|------|------|-----------|
| `scoring.py` | ❌ | `rank(candidates, weights, decay_rate) -> list[MemoryItem]`, `ScoredCandidate`, `cosine_similarity()`, `recency_score()` |
| `fact_extractor.py` | ✅ | `FactExtractor(llm).extract(texts) -> list[Fact]` |
| `reconcile.py` | ✅ | `ReconcileEngine(llm).reconcile(fact, existing) -> Action(ADD/UPDATE/DELETE/NOOP)` |
| `reflection.py` | ✅ | `ReflectionEngine(llm).reflect(items) -> list[MemoryItem]` (type=REFLECTION, importance=0.8) |
| `health.py` | ❌ | `compute_health(core, recall, rooms) -> MemoryHealthScore` — 5维: freshness, efficiency, coverage, diversity, coherence |

### 4.5 Service (`src/memory_palace/service/`)

| 文件 | 你需要知道的 |
|------|------------|
| `memory_service.py` | **CRUD facade**。save() 路由: importance≥0.7→Core, <0.7→Recall, ALL→Archival。update() 创建新版本。forget() 软删除。search() 委托 HybridRetriever |
| `hybrid_retriever.py` | FTS5 + Vector → Reciprocal Rank Fusion (k=60)。archival_store=None 时降级为 FTS5-only |
| `context_compiler.py` | 编译 [CORE] + [RETRIEVED] + [RECENT] 文本给 Agent system prompt |
| `curator.py` | CuratorService: should_trigger() 检查触发条件, run() 委托 CuratorGraph |
| `curator_graph.py` | **7阶段状态机**: GATHER→EXTRACT→RECONCILE→REFLECT→PRUNE→HEALTH_CHECK→REPORT。纯 Python enum 驱动 |
| `retriever.py` | v0.1 legacy FTS5-only retriever，保留向后兼容 |

### 4.6 Config (`src/memory_palace/config.py`)

```python
class Config(BaseSettings):
    llm: LLMConfig
    embedding: EmbeddingConfig
    storage: StorageConfig
    core: CoreConfig          # max_bytes=2048
    rooms: list[RoomConfig]   # 5 default rooms
    scoring: ScoringConfig    # recency=0.20, importance=0.20, relevance=0.50, room_bonus=0.10
    curator: CuratorConfig    # trigger: timer_hours=24, session_count=20, cooldown_hours=1

# 加载优先级: env vars (MP_ prefix) > YAML > defaults
Config.from_yaml(path) -> Config
```

## 5. 数据流 (四条核心路径)

### Save
```
MemoryService.save(content, importance, room)
  ├─ importance ≥ 0.7 → CoreStore.save()
  ├─ importance < 0.7 → RecallStore.insert()
  ├─ ALL → ArchivalStore.insert() (全量向量索引)
  ├─ Core 超预算? → auto-demote 最低 importance 到 Recall
  └─ AuditLog.append(CREATE)
```

### Search
```
HybridRetriever.search(query, top_k)
  ├─ 并行: RecallStore.fts_search() + ArchivalStore.search()
  ├─ Reciprocal Rank Fusion (k=60) → 合并去重
  ├─ ScoredCandidate 重打分 (4因子加权)
  └─ 返回 top_k MemoryItem[]
```

### Curate
```
CuratorGraph.run()
  GATHER → EXTRACT → RECONCILE → REFLECT → PRUNE → HEALTH_CHECK → REPORT
```

### Context
```
ContextCompiler.compile(query)
  [CORE MEMORY] + [RETRIEVED] + [RECENT ACTIVITY] → 结构化文本
```

## 6. 数据目录

```
~/.memory_palace/            # 默认 data_dir
├── core/                    # CoreStore JSON
├── recall.db                # RecallStore SQLite + FTS5
├── archival/                # ArchivalStore ChromaDB  
├── audit.jsonl              # AuditLog
└── memory_palace.yaml       # Config
```

## 7. 测试基础设施

```python
# tests/conftest.py 提供:
@pytest.fixture
def tmp_data_dir(tmp_path) -> Path:  # 含 core/ 子目录
    
class MockLLM:                       # 确定性 LLM mock
    responses: list[str]
    async def complete(prompt, response_format=None) -> str

class MockEmbedding:                 # 确定性 embedding mock
    async def embed(texts) -> list[list[float]]
```

## 8. CLI 命令 (Typer app)

```
palace save, save-batch, search, update, forget, curate, inspect, audit, context, reflect, health, rooms
```

入口: `pyproject.toml` → `palace = "memory_palace.integration.cli:app"`

## 9. 当前分支状态

```
main @ v0.2.0 — 284 tests, 0 failures
```
