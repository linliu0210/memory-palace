# 🧱 Memory Palace v0.2 — SPEC

> **Version**: v0.2.0  
> **Date**: 2026-04-12  
> **Status**: Draft — Pending Approval  
> **Parent SPEC**: [SPEC.md v2.0](file:///Users/link/Documents/Agent_Project/memory-palace/SPEC.md)  
> **Base Commit**: `main @ 45ff461` — v0.1 MVP (154 passed, 0 skipped)

---

## 0. 版本定位

```
v0.1 (60分): 骨架跑通          →  v0.2 (80分): 有房间有路径，小人能搬运整理
              FTS5-only 检索              + 向量混合检索
              三因子评分                   + 增强三因子 + Room bonus
              手动 Curator                 + LangGraph 自动化 + Reflection
              两层存储                     + 三层存储（Core/Recall/Archival）
```

### v0.2 交付目标

1. **三层存储完整** — Archival (ChromaDB 向量) 作为全量语义索引层
2. **混合检索** — FTS5 关键词 + Embedding 向量 → Reciprocal Rank Fusion
3. **Embedding 双模式** — OpenAI API + 本地 ONNX，Protocol-based 切换
4. **ReflectionEngine** — 从近期记忆生成高阶洞察
5. **Curator 自动化** — LangGraph StateGraph 编排（轻量）
6. **ContextCompiler** — 为 Agent 编译结构化上下文
7. **v0.1 技术债清零**

---

## 1. 与上游 SPEC 的差异决策

> 以下是 v0.2 实施中对 [SPEC.md v2.0](file:///Users/link/Documents/Agent_Project/memory-palace/SPEC.md) §5 的调整。原始 SPEC 不做修改，各差异在本文档中记录。

### 1.1 KuzuDB 图存储 → 延迟至 v1.0

| SPEC 原文 (§5.1 F-2) | v0.2 决策 | 理由 |
|---|---|---|
| `ArchivalStore (图)` — KuzuDB | **不引入** | v0.2 已引入 ChromaDB + Embedding 两个新存储介质，再加 KuzuDB 意味着三新依赖同时引入，风险失控 |
| 四因子 Proximity = `1/(1+graph_distance)` | **降级**为 Room match bonus (0/0.1) | 当前 5 个房间，图查询无明显优势；v1.0 1000+ 记忆后图距离才有价值 |
| F-4 四因子评分 | **增强三因子 + Room bonus** | 效果等价，复杂度大幅降低 |

**v1.0 恢复计划**：KuzuDB 在 v1.0 §P 系列引入，届时 Room 已有层级 (`parent` 字段已在模型中)，图距离查询收益明确。

### 1.2 评分公式调整

原 SPEC §5.2：
```python
# 四因子
score = α·recency + β·importance + γ·relevance + δ·proximity
# α=0.2, β=0.2, γ=0.4, δ=0.2
```

v0.2 实际：
```python
# 增强三因子 + Room bonus
score = α·recency + β·importance + γ·relevance + δ·room_bonus

recency   = exp(-λ · hours_since_access)                      # 沿用 v0.1
importance = memory.importance                                  # 沿用 v0.1
relevance  = cosine_similarity(embed(query), memory.embedding) # ← 升级
room_bonus = 1.0 if query_room == memory.room else 0.0         # ← 新增

# v0.2 权重: α=0.20, β=0.20, γ=0.50, δ=0.10
```

### 1.3 LangGraph 使用策略

原 SPEC §5.3 设想完整 LangGraph StateGraph。v0.2 遵循但限制范围：

- ✅ 使用 `langgraph` 的 `StateGraph` + `add_node()` + `add_conditional_edges()`
- ⛔ 不引入 `langchain-core`、`langchain-openai` 等重量级依赖
- ⛔ 不使用 LangGraph 的 memory/checkpointing/streaming 特性
- 📌 依赖范围: `langgraph>=0.3` 仅此一项

### 1.4 Archival 定位 — 全量向量索引层

原 SPEC §4.2 推迟清单暗示 Archival 是低重要性记忆的存放地。v0.2 重新定位：

> **Archival = 全量语义索引层**

- **所有记忆**（不论 tier）在保存时**同时**向 ArchivalStore 写入一份 embedding
- Core/Recall 仍管理物理存储和 CRUD 路由（importance 路由不变）
- HybridRetriever 查询时对**全量** embedding 做向量搜索，与 FTS5 结果融合
- 这使得即使 Core 中的高重要性记忆也能通过语义相似查到

```
Save Flow (v0.2):
  MemoryService.save(content, importance)
    ├─ importance >= 0.7 → CoreStore.save()
    ├─ importance < 0.7  → RecallStore.insert()
    └─ ALL items → ArchivalStore.insert()  ← 全量索引
```

### 1.5 Embedding — 双模式

原 SPEC §5.1 F-3: `OpenAI / 本地 ONNX`。v0.2 **两者都实现**：

| Provider | 模型 | 维度 | 适用场景 |
|---|---|---|---|
| `OpenAIEmbedding` | `text-embedding-3-small` | 1536 | 默认，高质量 |
| `LocalEmbedding` | `all-MiniLM-L6-v2` (ONNX) | 384 | 离线/零成本 |

通过 `EmbeddingProvider` Protocol 统一接口，`Config.embedding.provider` 选择。

### 1.6 延迟至 v1.0 的 F 系列组件

以下 SPEC §5.1 组件**不在 v0.2 范围**，显式保留至 v1.0：

| # | 组件 | 延迟理由 |
|---|------|---------|
| F-2 | ArchivalStore (图/KuzuDB) | §1.1 已说明 |
| F-10 | MemoryTools (OpenAI function schema) | v0.2 不做 Tool Use 集成 |
| F-12 | Query Write-back | 需先稳定检索再增值 |
| F-13 | Multi-pass Ingest | 单 pass 足够 v0.2 |

---

## 2. 新增组件清单

> 每个组件注明架构层级、文件路径、依赖关系。

### 2.1 — 1F Foundation

| # | 组件 | 文件 | 功能 | 依赖 |
|---|------|------|------|------|
| F-3a | **EmbeddingProvider** | `foundation/embedding.py` | `Protocol`: `embed(texts) → vectors`, `dimension` 属性 | — |
| F-3b | **OpenAIEmbedding** | `foundation/openai_embedding.py` | httpx 调用 OpenAI Embedding API | httpx, openai |
| F-3c | **LocalEmbedding** | `foundation/local_embedding.py` | sentence-transformers / ONNX 本地推理 | sentence-transformers |
| F-3d | **EmbeddingConfig** | `config.py` (扩展) | provider, model_id, dimension, batch_size | pydantic |

### 2.2 — 2F Storage

| # | 组件 | 文件 | 功能 | 依赖 |
|---|------|------|------|------|
| F-1 | **ArchivalStore** | `store/archival_store.py` | ChromaDB 向量存储：insert, search, get, delete | chromadb, EmbeddingProvider |

设计要点：
- ChromaDB 使用**持久化模式** (`PersistentClient`)，数据目录: `{data_dir}/archival/`
- 集合名: `"memory_palace"`
- 每条文档: `id=memory.id`, `document=memory.content`, `metadata={tier, room, importance, status, tags}`
- `search()` 返回 `list[dict]` 格式 `{"item": MemoryItem, "distance": float}` — 与 RecallStore 统一
- **不存储 MemoryItem 全量字段**（embedding + metadata 够用），完整 Item 从 Core/Recall 获取

### 2.3 — 3F Engine

| # | 组件 | 文件 | 功能 | 依赖 |
|---|------|------|------|------|
| F-6 | **ReflectionEngine** | `engine/reflection.py` | LLM 从近期记忆提取高阶洞察 (MemoryType.REFLECTION) | LLMProvider |
| — | **ScoringEngine** (重构) | `engine/scoring.py` | 增强三因子 + Room bonus + `ScoredCandidate` 接口 | — |
| F-15 | **MemoryHealthScore** | `engine/health.py` | 5 维度健康评分: freshness, efficiency, coverage, diversity, coherence | — |

#### ReflectionEngine Prompt

```
You are a reflection engine for a Memory Palace system.
Given recent memories, generate 1-3 higher-order insights.

Each insight should:
- Synthesize across multiple memories (not just rephrase)
- Reveal patterns the user might not notice
- Be actionable or diagnostic

MEMORIES:
{formatted_memories}

Return JSON array:
[{
  "content": "insight text",
  "source_ids": ["id1", "id2", ...]
}]
```

#### ScoringEngine 重构

```python
@dataclass
class ScoredCandidate:
    """A memory item with pre-computed scoring factors."""
    item: MemoryItem
    recency_hours: float
    importance: float
    relevance: float    # cosine similarity [0,1] or normalized BM25
    room_bonus: float   # 0.0 or 1.0

def rank(candidates: list[ScoredCandidate],
         weights: tuple[float, float, float, float] = (0.20, 0.20, 0.50, 0.10),
         decay_rate: float = 0.01) -> list[MemoryItem]:
    """Sort candidates by weighted score, descending."""

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""

# 保留旧 rank() 函数为 rank_legacy() 兼容 v0.1 测试
```

#### MemoryHealthScore

```python
class MemoryHealthScore(BaseModel):
    """Five-dimension health assessment. Ref: SPEC §2.3 注释."""
    freshness: float = 0.0        # [0,1] 近 30 天被引用的记忆比例
    efficiency: float = 0.0       # [0,1] Core 精简度 (active/total)
    coverage: float = 0.0         # [0,1] Room 覆盖率
    diversity: float = 0.0        # [0,1] MemoryType 分布均匀度
    coherence: float = 0.0        # [0,1] 重复/矛盾率 (低=好)

    @property
    def overall(self) -> float:
        """Weighted average of all dimensions."""
        return (self.freshness * 0.25 + self.efficiency * 0.25 +
                self.coverage * 0.15 + self.diversity * 0.15 +
                self.coherence * 0.20)
```

### 2.4 — 4F Service

| # | 组件 | 文件 | 功能 | 依赖 |
|---|------|------|------|------|
| F-5 | **HybridRetriever** | `service/hybrid_retriever.py` | FTS5 + Vector 混合检索, RRF 融合 | RecallStore, ArchivalStore, EmbeddingProvider |
| F-9 | **ContextCompiler** | `service/context_compiler.py` | 为 Agent 编译 Core + Retrieved + Recent 上下文 | MemoryService, HybridRetriever |
| F-7 | **CuratorGraph** | `service/curator_graph.py` | LangGraph StateGraph 编排 Curator 流程 | langgraph, ReflectionEngine |

#### HybridRetriever

```python
class HybridRetriever:
    """FTS5 (keyword) + Vector (semantic) hybrid retrieval.

    Workflow:
    1. Parallel: FTS5 search → keyword candidates
                 Vector search → semantic candidates
    2. Reciprocal Rank Fusion (RRF) to de-dup & merge
    3. Re-score with enhanced three-factor + room bonus
    4. Return top_k
    """
    def __init__(self, recall_store: RecallStore,
                 archival_store: ArchivalStore | None,
                 embedding: EmbeddingProvider | None) -> None:
        """archival_store/embedding=None → fallback to FTS5-only."""

    async def search(self, query: str, top_k: int = 5,
                     room: str | None = None,
                     min_importance: float = 0.0) -> list[MemoryItem]: ...
```

**RRF 算法**：
```python
def reciprocal_rank_fusion(rankings: list[list[str]],
                           k: int = 60) -> list[tuple[str, float]]:
    """Merge multiple rankings via RRF.

    rrf_score(d) = Σ 1 / (k + rank_i(d))

    Args:
        rankings: list of ranked document ID lists.
        k: RRF constant (default 60, standard value).

    Returns: Sorted list of (doc_id, rrf_score).
    """
```

**降级策略**：当 `archival_store=None`（未配置 embedding）时，自动降级为 FTS5-only（等价 v0.1 Retriever 行为），保证向后兼容。

#### CuratorGraph (LangGraph)

```python
# LangGraph 状态定义
class CuratorState(TypedDict):
    items: list[MemoryItem]
    facts: list[MemoryItem]
    decisions: list[dict]
    reflections: list[MemoryItem]
    pruned_ids: list[str]
    health: MemoryHealthScore
    errors: list[str]
    report: CuratorReport | None

# 状态机流程
START → gather_signal → has_items? ─No→ health_check → report → END
                            │Yes
                      extract_facts
                            │
                      reconcile (per fact)
                            │
                      reflect (importance_sum > threshold)
                            │
                      prune (decay check)
                            │
                      health_check (5-dimension)
                            │
                      report → END
```

**轻量化原则**：
- 每个节点是一个**普通 async 函数**，不使用 LangChain/LangGraph 的 Runnable 体系
- 不使用 checkpointing（v0.2 不需要跨 session 恢复）
- 不使用 streaming（CLI 输出 CuratorReport 就够）

### 2.5 — 5F Integration

| # | 组件 | 文件 | 功能 |
|---|------|------|------|
| — | CLI v0.2 | `integration/cli.py` (扩展) | 新增 `context`, `reflect`, `health` 命令 |

---

## 3. 改动影响（v0.1 → v0.2）

### 3.1 修改的 v0.1 文件

| 文件 | 改动类型 | 改动内容 |
|------|---------|---------|
| `config.py` | **扩展** | 新增 `EmbeddingConfig`, `LangGraphConfig` |
| `engine/scoring.py` | **重构** | 新增 `ScoredCandidate`, `cosine_similarity`, `room_bonus`；旧 `rank()` → `rank_legacy()` |
| `service/memory_service.py` | **重构** | 三层路由, `get_by_id()`, `get_core_context()` active-only 过滤, `update()` 消除直连 |
| `service/retriever.py` | **重构** | 使用 `ScoredCandidate` 接口；保持 FTS5-only 功能作为 fallback |
| `service/curator.py` | **重写** | 拆分为 `curator.py` (接口) + `curator_graph.py` (LangGraph 实现) |
| `store/recall_store.py` | **扩展** | 新增 `update_field()` |
| `integration/cli.py` | **扩展** | 新增命令, `rooms` 改读 Config, `inspect` 走 MemoryService |
| `pyproject.toml` | **扩展** | 版本 0.2.0, 新增 chromadb, langgraph, sentence-transformers(optional) |

### 3.2 v0.1 技术债清理

| # | 债务 | 修复 Round |
|---|------|-----------|
| TD-1 | `update()` 直接访问 `_recall_store._conn` | R9 — `update_field()` 封装 |
| TD-2 | `get_core_context()` 返回含 SUPERSEDED/PRUNED | R12 — active-only 过滤 |
| TD-3 | `rank()` 平行数组 API | R10 — `ScoredCandidate` 重构 |
| TD-4 | CLI `inspect <id>` 绕过 MemoryService | R12 — `get_by_id()` |
| TD-5 | CLI `rooms` 硬编码列表 | R13 — 改读 Config |
| TD-6 | 未使用 `import httpx` | R9 — 删除 |
| TD-7 | `save()` 不检查 Core 预算 | R12 — 自动 demote |

---

## 4. 新增依赖

```toml
[project.dependencies]
# v0.1 沿用
"pydantic>=2.5",
"pydantic-settings>=2.1",
"pyyaml>=6.0",
"structlog>=24.1",
"typer>=0.9",
"rich>=13.0",
"httpx>=0.27",

# v0.2 新增
"chromadb>=1.0",                # ArchivalStore 向量存储
"langgraph>=0.3",               # Curator 状态机编排

[project.optional-dependencies]
local = [
    "sentence-transformers>=3.0", # LocalEmbedding 本地推理
]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "ruff>=0.4",
]
```

> ⚠️ `langgraph>=0.3` 会带入部分 langchain 依赖。实施时需验证**最小依赖树**，如果太重则考虑平替方案。

---

## 5. 数据目录结构 (v0.2)

```
~/.memory_palace/                    # 默认 data_dir
├── core/                           # CoreStore JSON 文件
│   ├── general.json
│   └── preferences.json
├── recall.db                       # RecallStore SQLite + FTS5
├── archival/                       # ArchivalStore ChromaDB [v0.2 新增]
│   └── chroma.sqlite3              # ChromaDB 持久化
├── audit.jsonl                     # 审计日志
└── memory_palace.yaml              # 配置文件
```

---

## 6. 接口契约 (v0.2 新增/变更)

### 6.1 EmbeddingProvider Protocol

```python
@runtime_checkable
class EmbeddingProvider(Protocol):
    """Structural-typing protocol for embedding backends."""
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimension(self) -> int: ...
```

### 6.2 MemoryService 变更

```python
class MemoryService:
    # v0.1 保留：save(), save_batch(), search(), update(), forget(), 
    #           get_core_context(), stats()

    # v0.2 新增
    def get_by_id(self, memory_id: str) -> MemoryItem | None:
        """Get memory by ID from any tier (Core → Recall → Archival)."""

    # v0.2 变更
    def get_core_context(self) -> str:
        """Return ACTIVE-only Core Memory text (filtered)."""

    def save(self, ...) -> MemoryItem:
        """Routes by importance, ALL items also indexed in ArchivalStore."""

    async def search(self, ...) -> list[MemoryItem]:
        """Now async — uses HybridRetriever (FTS5 + Vector)."""
```

### 6.3 CuratorService 变更

```python
class CuratorService:
    async def run(self, since: datetime | None = None) -> CuratorReport:
        """LangGraph 编排: Gather → Extract → Reconcile → Reflect → Prune → Health → Report"""

    def should_trigger(self) -> tuple[bool, str]:
        """沿用 v0.1 逻辑（session_count / timer / cooldown）"""
```

### 6.4 CLI 变更

```bash
# v0.1 保留
palace save "..." --importance 0.8 --room preferences
palace search "..." --top-k 5
palace update <id> "..." --reason "..."
palace forget <id> --reason "..."
palace curate
palace inspect [<id>]
palace audit --last 20
palace rooms

# v0.2 新增
palace context [--query "..."] [--no-core]     # 编译上下文
palace reflect                                  # 手动触发 Reflection
palace health                                   # 显示 5 维度健康分
```

---

## 7. 测试策略 (v0.2)

### 7.1 Mock 矩阵

| 外部依赖 | Mock 方式 | 测试层 |
|---------|----------|--------|
| LLM (GPT) | `MockLLM` (response list) — 沿用 v0.1 | Engine, Service |
| Embedding (OpenAI) | `MockEmbedding` (hash → 固定向量) | Store, Service |
| Embedding (Local) | `MockEmbedding` (同上) | Foundation |
| ChromaDB | **内存模式** (`EphemeralClient`) — 无需 mock | Store |
| LangGraph | **直接测试** — 轻量无外部 IO | Service |

```python
# MockEmbedding — 确定性、可重复
class MockEmbedding:
    """Hash-based deterministic embeddings for testing."""
    def __init__(self, dimension: int = 8):
        self._dimension = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_to_vector(t) for t in texts]

    @property
    def dimension(self) -> int:
        return self._dimension

    def _hash_to_vector(self, text: str) -> list[float]:
        """Deterministic: same text → same vector."""
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        raw = [b / 255.0 for b in h[:self._dimension]]
        # Normalize to unit vector
        norm = sum(x*x for x in raw) ** 0.5
        return [x / norm for x in raw]
```

### 7.2 测试增量预估

| 层级 | v0.1 | v0.2 新增 | v0.2 总计 |
|------|------|----------|----------|
| Foundation | ~20 | +12 (embedding) | ~32 |
| Models | ~25 | +2 (health score) | ~27 |
| Store | ~25 | +12 (archival + recall.update_field) | ~37 |
| Engine | ~30 | +18 (scoring refactor + reflection + health) | ~48 |
| Service | ~35 | +25 (hybrid retriever + context + curator graph) | ~60 |
| E2E | ~10 | +5 (v0.2 lifecycle) | ~15 |
| Integration | ~9 | +5 (CLI v0.2) | ~14 |
| **总计** | **154** | **~78** | **~232** |

---

## 8. Non-Goals (v0.2 显式不做)

| 不做 | 理由 | 引入版本 |
|------|------|---------|
| KuzuDB 图存储 | §1.1 已说明 | v1.0 |
| MemoryTools (Function Calling) | 先稳定 Library API | v1.0 |
| Query Write-back | 先稳定检索 | v1.0 |
| Multi-pass Ingest | 单 pass 够用 | v1.0 |
| Sleep-time 自动触发 | LangGraph 编排先用手动触发验证 | v1.0 |
| MCP Server | CLI 够用 | v1.0 |

---

## 9. 开放问题 & 风险

### 9.1 langgraph 依赖树

`langgraph>=0.3` 可能带入 `langchain-core` 等重量级依赖。

**缓解**：R12 实施前先做 `pip install langgraph && pip list | grep lang` 检查依赖树大小。如果超过 5 个新包，则降级为**纯 Python 状态机**（CuratorStateMachine + enum 状态）。

### 9.2 ChromaDB v1.0 API 稳定性

ChromaDB 于 2025 年底发布 v1.0，API 有 breaking changes。

**缓解**：实施时参考最新文档，pin 版本到 `~=1.0`。

### 9.3 search() 同步→异步

v0.2 的 `HybridRetriever.search()` 是 async（需要 await embedding），这意味着 `MemoryService.search()` 也需要变成 async。

**影响**：CLI 调用处需要 `asyncio.run()` 包装。v0.1 的同步 `Retriever` 保留为 fallback，无 embedding 时不需要 async。

---

## 附录 A: 与 SPEC v2.0 §5 的映射

| SPEC §5.1 组件 | v0.2 状态 | 本文档位置 |
|---|---|---|
| F-1 ArchivalStore (向量) | ✅ 实施 | §2.2 |
| F-2 ArchivalStore (图) | ⏳ 延迟至 v1.0 | §1.1 |
| F-3 EmbeddingProvider | ✅ 双模式实施 | §2.1 |
| F-4 四因子评分 | ⚠️ 降级为增强三因子 | §1.2 |
| F-5 HybridRetriever | ✅ 实施 | §2.4 |
| F-6 ReflectionEngine | ✅ 实施 | §2.3 |
| F-7 Curator LangGraph | ✅ 轻量实施 | §2.4 |
| F-8 Room 管理 | ⚠️ 部分 (Config 驱动, 无 CRUD API) | §3.2 TD-5 |
| F-9 ContextCompiler | ✅ 实施 | §2.4 |
| F-10 MemoryTools | ⏳ 延迟至 v1.0 | §8 |
| F-11 DreamInsight | ⚠️ 合并入 ReflectionEngine | §2.3 |
| F-12 Query Write-back | ⏳ 延迟至 v1.0 | §8 |
| F-13 Multi-pass Ingest | ⏳ 延迟至 v1.0 | §8 |
| F-14 MemoryType.DECISION | ✅ 已在 v0.1 模型中预定义 | — |
| F-15 MemoryHealthScore | ✅ 实施 | §2.3 |
