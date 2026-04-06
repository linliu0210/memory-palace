# 🏛️ Memory Palace — SPEC v2.0

> **Version**: v2.0  
> **Date**: 2026-04-06  
> **Status**: Approved — Ready for Implementation  
> **前置文档**:  
> - [调研报告 v1.1](file:///Users/link/.gemini/antigravity/brain/363f3fd5-6335-403e-8eca-702c7398c766/memory_palace_agent_research.md)  
> - [CEO 架构指南](file:///Users/link/.gemini/antigravity/brain/363f3fd5-6335-403e-8eca-702c7398c766/ceo_architecture_guide.md)  
> - [理念更新 v1.1](file:///Users/link/.gemini/antigravity/brain/363f3fd5-6335-403e-8eca-702c7398c766/ideation_update_v1.1.md)

---

## 0. 项目理念

### 一句话

**给 AI 装一套「记忆操作系统」**——不只让它记得住，而是让它**自己整理、自己归纳、自己遗忘**，越用越聪明。

### 核心公式

```
知识价值 = f(摄取次数 × 查询次数 × 梦境次数)   ← 复合增长
        ≠ f(文档上传数)                        ← 线性堆积
```

### 设计理念（v1.1 — 融合 Karpathy LLM Wiki + Auto-Dream）

> - **宫殿 (Palace)** 不是静态仓库，而是**活的 Wiki**——知识编译一次，持续更新，查询本身也是增值事件
> - **搬运小人 (Curator)** 不只是整理工，更是**认知管家**——去重、解决冲突、发现模式、生成洞察、监控健康
> - **记忆 (Memory)** 不只是存取，而是**完整生命周期**——摄取→评分→调和→存储→整合→衰减→归档→审计
> - **遗忘 (Forgetting)** 不是缺陷，而是**智慧**——渐进衰减、优雅归档、永不物理删除
> - **维护成本趋近于零**——人负责输入和决策，搬运小人负责所有簿记

### 版本迭代哲学

> **Stability before Sophistication** — 先跑通再跑好。

| 版本 | 代号 | 分数 | 核心交付 | 隐喻完成度 |
|------|------|------|---------|-----------|
| **v0.1** | 🦴 Skeleton | **60** | Pipeline 跑通；全构件就位；两层存储 | 宫殿有骨架，搬运小人能走路 |
| **v0.2** | 🧱 Foundation | **80** | 三层存储完整；混合检索；搬运小人自动化+反思 | 宫殿有房间有路径，小人能搬运整理 |
| **v1.0** | 🏛️ Palace | **95** | Sleep-time 自动化；空间邻近性；监控仪表盘 | 记忆宫殿完全建成，小人高效自治 |

> [!IMPORTANT]
> **v0.1 是唯一硬性里程碑**。标准：给它一段对话，它能存、能检索、能整理、能遗忘，全链路 E2E 跑通。

---

## 1. 系统边界

**是**：
- Python library（`memory_palace`），可被任意 Agent 框架集成
- 三层存储引擎 (Core / Recall / Archival)
- 后台 Memory Curator Agent（搬运小人）
- 混合检索引擎 + CLI 调试工具

**不是**：
- ❌ 完整 Agent 框架（不含对话管理/任务规划）
- ❌ 多租户 SaaS 平台（v1.0 内仅单用户本地部署）
- ❌ UI 前端（CLI + API 交互）

---

## 2. 数据模型

### 2.1 MemoryItem — 原子记忆单元

> 💡 **灵感**：Mem0 的 Atomic Facts + MemGPT 的 tiered storage

```python
class MemoryStatus(str, Enum):
    ACTIVE = "active"           # 正常存活
    SUPERSEDED = "superseded"   # 被更新版本替代
    PRUNED = "pruned"           # 被淘汰（软删除）
    MERGED = "merged"           # 被合并到另一条记忆

class MemoryTier(str, Enum):
    CORE = "core"               # 随身口袋（始终加载）
    RECALL = "recall"           # 抽屉柜（按需检索）
    ARCHIVAL = "archival"       # 地下室（持久存储）[v0.2]

class MemoryType(str, Enum):
    OBSERVATION = "observation"     # 直接观察/事实
    REFLECTION = "reflection"      # 高阶洞察（搬运小人生成）
    PREFERENCE = "preference"      # 用户偏好
    PROCEDURE = "procedure"        # 操作知识/技能
    SYNTHESIS = "synthesis"        # 查询中诞生的知识 [v0.1+]
    DECISION = "decision"          # 决策记录 [v0.2]

class MemoryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str                                # 原子事实文本
    memory_type: MemoryType
    tier: MemoryTier
    importance: float = Field(ge=0.0, le=1.0)   # 重要性 [0,1]
    tags: list[str] = []
    room: str = "general"                       # 所属「房间」
    user_pinned: bool = False                   # 用户钉住 → 永不淘汰

    # 时间维度
    created_at: datetime = Field(default_factory=datetime.now)
    accessed_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    access_count: int = 0

    # 版本与审计
    status: MemoryStatus = MemoryStatus.ACTIVE
    version: int = 1
    parent_id: Optional[str] = None
    merged_from: list[str] = []
    superseded_by: Optional[str] = None
    change_reason: Optional[str] = None

    # v0.2+
    embedding: Optional[list[float]] = None
    source_hash: Optional[str] = None           # 命题级溯源
```

### 2.2 AuditEntry — 审计日志

> 💡 **灵感**：Karpathy 的 `log.md`（时间线）+ Git 版本历史

```python
class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    MERGE = "merge"
    PRUNE = "prune"
    PROMOTE = "promote"     # Recall → Core
    DEMOTE = "demote"       # Core → Archival
    ACCESS = "access"

class AuditEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    action: AuditAction
    memory_id: str
    actor: str              # "user" | "curator" | "system"
    details: dict = {}
```

### 2.3 CuratorReport — 搬运小人工作报告

> 💡 **灵感**：OpenClaw Auto-Dream 的健康评分 + Claude Auto-Dream 的梦境报告

```python
class CuratorReport(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    triggered_at: datetime
    trigger_reason: str                 # "session_count" | "timer" | "manual"

    facts_extracted: int = 0
    memories_created: int = 0
    memories_updated: int = 0
    memories_merged: int = 0
    memories_pruned: int = 0
    reflections_generated: int = 0      # [v0.2]

    duration_seconds: float = 0
    tokens_consumed: int = 0
    errors: list[str] = []

    # 健康评分 (v0.1 简化版: freshness + efficiency)
    health_freshness: float = 0.0       # [0,1] 近 30 天引用比例
    health_efficiency: float = 0.0      # [0,1] Core Memory 精简度
    # v0.2: 扩展为完整 MemoryHealthScore
    # v1.0: + 趋势追踪 + Dashboard 可视化
```

### 2.4 Room — 记忆宫殿的「房间」

```python
class Room(BaseModel):
    name: str                   # 唯一标识
    description: str
    parent: Optional[str]       # 父房间 (v0.2 层级)
    memory_count: int = 0
    last_accessed: Optional[datetime] = None
```

---

## 3. 五层架构

> 💡 **灵感**：MemGPT 的 OS 类比（RAM/Cache/Disk）

```
╔══════════════════════════════════════════════════════════╗
║  5F  Integration Layer   — CLI / Python API / MCP [v1.0]║
╠══════════════════════════════════════════════════════════╣
║  4F  Service Layer       — 三个管家                      ║
║      MemoryService │ Retriever │ CuratorService          ║
╠══════════════════════════════════════════════════════════╣
║  3F  Engine Layer        — 三台机器                      ║
║      FactExtractor │ ScoringEngine │ ReconcileEngine     ║
╠══════════════════════════════════════════════════════════╣
║  2F  Storage Layer       — 三个仓库                      ║
║      CoreStore(YAML) │ RecallStore(SQLite) │ Archival[v0.2]║
╠══════════════════════════════════════════════════════════╣
║  1F  Foundation          — 水电煤                        ║
║      Config │ AuditLog │ LLMProvider │ Embedding[v0.2]   ║
╚══════════════════════════════════════════════════════════╝
```

### 目录结构

```
memory-palace/
├── pyproject.toml
├── README.md
├── SPEC.md
├── CONVENTIONS.md
├── PROJECT_CONTEXT.md
│
├── src/memory_palace/
│   ├── __init__.py
│   ├── config.py                   # 配置管理
│   ├── models/                     # 2F 数据模型
│   │   ├── memory.py               # MemoryItem, Room
│   │   ├── audit.py                # AuditEntry
│   │   └── curator.py              # CuratorReport
│   ├── store/                      # 2F 存储层
│   │   ├── base.py                 # AbstractStore Protocol
│   │   ├── core_store.py           # Core (JSON flat file)
│   │   ├── recall_store.py         # Recall (SQLite+FTS5)
│   │   └── archival_store.py       # Archival [v0.2]
│   ├── engine/                     # 3F 引擎层
│   │   ├── fact_extractor.py       # LLM 原子事实提取
│   │   ├── scoring.py              # 检索评分（纯函数）
│   │   ├── reconcile.py            # LLM 冲突解决
│   │   └── reflection.py           # Reflection [v0.2]
│   ├── service/                    # 4F 服务层
│   │   ├── memory_service.py       # 记忆管家 (CRUD)
│   │   ├── retriever.py            # 搜索管家
│   │   └── curator.py              # 搬运小人
│   ├── integration/                # 5F 集成层
│   │   ├── tools.py                # LLM Tool 定义
│   │   └── cli.py                  # CLI
│   └── foundation/                 # 1F 基础设施
│       ├── audit_log.py            # Append-only JSONL
│       ├── embedding.py            # Embedding [v0.2]
│       └── llm.py                  # LLM Protocol + Provider
│
├── tests/                          # 镜像 src 结构
│   ├── conftest.py
│   ├── test_models/
│   ├── test_store/
│   ├── test_engine/
│   ├── test_service/
│   └── test_e2e/
│
├── data/                           # 运行时 (gitignored)
│   ├── core/
│   ├── recall.db
│   ├── archival/                   # [v0.2]
│   └── audit.jsonl
│
└── scripts/
    ├── curator_run.py
    └── memory_inspect.py
```

---

## 4. v0.1 — 🦴 Skeleton（60 分）

> **目标**：Pipeline 完整跑通。所有构件就位，各组件用最简实现。
> **验收**：`pytest tests/test_e2e/ -v` 全绿 + CLI demo 可演示完整生命周期。

### 4.1 组件清单

> 每个组件标注了「灵感来源」和「版本边界」。

#### 1F — Foundation（水电煤）

| # | 组件 | 文件 | 做什么 | 灵感 |
|---|------|------|--------|------|
| S-1 | **AuditLog** | `foundation/audit_log.py` | Append-only JSONL，每次写操作产生一条日志 | Karpathy `log.md` + Git 历史 |
| S-2 | **Config** | `config.py` | Pydantic Settings，`.env`/YAML 外部化 | pi-mono Provider 模式 |
| S-3 | **LLM 抽象** | `foundation/llm.py` | `LLMProvider` Protocol + env key 解析 | DreamEngine provider_factory |

#### 2F — Data Models（数据模型）

| # | 组件 | 文件 | 做什么 | 灵感 |
|---|------|------|--------|------|
| S-4 | **MemoryItem** | `models/memory.py` | Pydantic v2，含全部字段+校验 | Mem0 Atomic Facts |
| S-5 | **AuditEntry** | `models/audit.py` | 审计条目，JSONL 序列化 | — |
| S-6 | **CuratorReport** | `models/curator.py` | 搬运小人工作报告+简化版健康分 | OpenClaw health score |
| S-7 | **Room** | `models/memory.py` | 房间命名空间 | Method of Loci |

#### 2F — Storage（仓库）

| # | 组件 | 文件 | 做什么 | 灵感 |
|---|------|------|--------|------|
| S-8 | **CoreStore** | `store/core_store.py` | JSON 平文件，1 block = 1 文件，≤2KB 预算 | MemGPT Core Memory (RAM) |
| S-9 | **RecallStore** | `store/recall_store.py` | SQLite + FTS5 全文搜索 | MemGPT Recall (Cache) |

#### 3F — Engine（机器）

| # | 组件 | 文件 | 做什么 | 灵感 |
|---|------|------|--------|------|
| S-10 | **FactExtractor** | `engine/fact_extractor.py` | LLM 提取原子事实 → `list[MemoryItem]` | Mem0 fact extraction |
| S-11 | **ScoringEngine** | `engine/scoring.py` | 三因子评分（纯函数，零 LLM 依赖） | Generative Agents 三因子 |
| S-12 | **ReconcileEngine** | `engine/reconcile.py` | LLM 判断 ADD/UPDATE/DELETE/NOOP | Mem0 Reconcile |

#### 4F — Service（管家）

| # | 组件 | 文件 | 做什么 | 灵感 |
|---|------|------|--------|------|
| S-13 | **MemoryService** | `service/memory_service.py` | CRUD facade：save/search/update/forget | Mem0 + MemGPT |
| S-14 | **Retriever** | `service/retriever.py` | FTS5 + 三因子评分排序 | Generative Agents |
| S-15 | **CuratorService** | `service/curator.py` | 同步执行，手动触发，无 LangGraph | Claude Auto-Dream |

#### 5F — Integration（入口）

| # | 组件 | 文件 | 做什么 | 灵感 |
|---|------|------|--------|------|
| S-16 | **CLI** | `integration/cli.py` | Typer CLI：palace save/search/curate/inspect | Karpathy "Obsidian = IDE" |
| S-17 | **E2E Test** | `tests/test_e2e/` | 完整生命周期验证 | — |

### 4.2 v0.1 显式不做（推迟清单）

| 推迟项 | 理由 | 引入版本 |
|--------|------|---------|
| 向量存储 (Qdrant/Chroma) | 三因子中 Relevance 先用 FTS5 近似 | v0.2 |
| 图存储 (KuzuDB) | Proximity 需要图结构 | v0.2 |
| Embedding 计算 | 无向量存储不需要 | v0.2 |
| LangGraph 编排 | Curator MVP 用同步函数够 | v0.2 |
| Reflection (反思) | 高阶记忆需要足够积累 | v0.2 |
| Dream Insights (梦境洞察) | 依赖 Reflection | v0.2 |
| Query Write-back | 查询增值机制 | v0.2 |
| Multi-pass Ingest | 事实提取先用单 pass | v0.2 |
| Sleep-time 自动触发 | 手动触发足够 | v1.0 |
| Room 层级检索 | 扁平 tags 即可 | v0.2 |
| MCP Server | 集成层先做 CLI | v1.0 |

### 4.3 E2E 关键路径

```
[用户输入对话文本]
   │
   ▼
FactExtractor.extract(text)
   │  → list[MemoryItem] (importance 已评分)
   ▼
MemoryService.save(items)
   │  ├─ importance ≥ 0.7 → CoreStore
   │  └─ else → RecallStore
   │  └─ AuditLog.append(CREATE)
   ▼
MemoryService.search(query, top_k=5)
   │  → RecallStore.fts_search(query)
   │  → ScoringEngine.rank(results, query)
   │  → 返回 ranked list
   ▼
CuratorService.run()  # 手动触发
   │  ├─ scan RecallStore for recent items
   │  ├─ ReconcileEngine.reconcile(new, existing)
   │  │   → ADD / UPDATE / DELETE / NOOP
   │  ├─ 执行决策 → Store 写入
   │  ├─ 计算 health_freshness + health_efficiency
   │  ├─ AuditLog.append(MERGE/PRUNE/UPDATE)
   │  └─ 返回 CuratorReport
   ▼
[CLI: palace inspect] → 查看记忆状态
```

### 4.4 接口契约

```python
# === 4F: Memory Service (记忆管家) ===
class MemoryService:
    def save(self, content: str,
             importance: float | None = None,  # None = LLM 自动评分
             tags: list[str] = [],
             room: str = "general",
             memory_type: MemoryType = MemoryType.OBSERVATION
             ) -> MemoryItem:
        """保存新记忆。importance ≥ 0.7 → Core，否则 → Recall。"""

    def save_batch(self, texts: list[str]) -> list[MemoryItem]:
        """批量保存。内部调用 FactExtractor。"""

    def search(self, query: str, top_k: int = 5,
               room: str | None = None,
               min_importance: float = 0.0
               ) -> list[MemoryItem]:
        """检索记忆，按评分排序。"""

    def update(self, memory_id: str, new_content: str,
               reason: str) -> MemoryItem:
        """更新。旧版本标记 superseded，创建新版本。"""

    def forget(self, memory_id: str, reason: str) -> bool:
        """软删除。标记 pruned，不物理删除。"""

    def get_core_context(self) -> str:
        """返回全部 Core Memory 文本拼接。"""

    def stats(self) -> dict:
        """各层数量、总大小、最近访问时间。"""


# === 4F: Curator Service (搬运小人) ===
class CuratorService:
    def run(self, since: datetime | None = None) -> CuratorReport:
        """执行一轮整理。v0.1 同步执行。"""

    def should_trigger(self) -> tuple[bool, str]:
        """检查是否满足触发条件。"""


# === 5F: CLI ===
# palace save "用户喜欢深色模式" --importance 0.8 --room preferences
# palace save-batch --file conversation.txt
# palace search "用户偏好" --top-k 5
# palace update <id> "改为浅色" --reason "用户要求"
# palace forget <id> --reason "用户要求遗忘"
# palace curate                    # 手动触发搬运小人
# palace inspect                   # 记忆概览
# palace inspect <id>              # 单条 + 审计历史
# palace audit --last 20           # 最近 20 条审计
# palace rooms                    # 列出房间
```

### 4.5 v0.1 Prompt 模板

**Fact Extractor**：
```
Extract atomic facts from the following conversation.
Each fact should be:
- Self-contained (understandable without context)
- Atomic (one fact per item, not compound)
- Factual (not opinions unless user preference)

Rate importance 0.0-1.0:
- 0.0-0.3: Trivial (greetings, filler)
- 0.4-0.6: Useful context (project details, dates)
- 0.7-0.9: Important (preferences, decisions, key facts)
- 1.0: Critical (identity, safety-relevant)

Return JSON: [{"content": "...", "importance": 0.X, "tags": [...]}]

Conversation:
{text}
```

**Reconcile**：
```
You are a memory reconciliation engine.
Given a NEW fact and EXISTING memories:

NEW: {new_fact}
EXISTING:
{existing_memories}

Decide ONE action:
- ADD: genuinely new information
- UPDATE <id>: updates/corrects existing
- DELETE <id>: contradicts existing, making it obsolete
- NOOP: already captured

Return JSON: {"action": "ADD|UPDATE|DELETE|NOOP", "target_id": "...|null", "reason": "..."}
```

### 4.6 v0.1 评分公式

> 💡 **灵感**：Generative Agents 三因子（Recency×Importance×Relevance）

```python
# v0.1: 三因子（无 Proximity）
score = α·recency + β·importance + γ·relevance

recency   = exp(-λ · hours_since_last_access)   # λ=0.01, ~69h 半衰
importance = memory.importance                    # already [0,1]
relevance  = normalize_bm25(fts5_rank)           # FTS5 BM25 → [0,1]

# v0.1 权重: α=0.25, β=0.25, γ=0.50
```

**BM25 归一化**：
```python
def normalize_bm25(raw_rank: float, results: list[float]) -> float:
    """FTS5 rank (负数，越小越相关) → [0,1]"""
    if not results: return 0.0
    min_r, max_r = min(results), max(results)
    if min_r == max_r: return 1.0
    return (max_r - raw_rank) / (max_r - min_r)
```

> **v0.2 替换路径**：`normalize_bm25()` → `cosine_similarity(embed(query), memory.embedding)`，接口不变。

### 4.7 v0.1 遗忘公式

> 💡 **灵感**：OpenClaw Auto-Dream 渐进衰减

```python
# 渐进衰减（替代断崖式 TTL）
recency_factor = max(0.1, 1.0 - days_since_access / 180)  # 6个月渐衰
reference_boost = log2(access_count + 1)                    # 被引用越多越重要
effective_importance = (importance * recency_factor * reference_boost) / 8.0

# 淘汰条件
if days_since_access > 90 and effective_importance < 0.3:
    → 压缩为一行摘要 → status = PRUNED (保留 ID 和关系)

# 豁免
if user_pinned: → 永不淘汰
```

---

## 5. v0.2 — 🧱 Foundation（80 分）

> **前置**：v0.1 稳定运行，E2E 全绿  
> **目标**：三层存储完整；混合检索；搬运小人自动化+反思

### 5.1 新增组件

| # | 组件 | 做什么 | 灵感 |
|---|------|--------|------|
| F-1 | **ArchivalStore (向量)** | ChromaDB 嵌入式向量库 | MemGPT Archival (Disk) |
| F-2 | **ArchivalStore (图)** | KuzuDB 嵌入式图库，Room 成为真实图节点 | Mem0 Graph Store |
| F-3 | **EmbeddingProvider** | OpenAI / 本地 ONNX 嵌入计算 | — |
| F-4 | **四因子评分** | +Proximity 维度（图距离） | Generative Agents + Method of Loci |
| F-5 | **HybridRetriever** | 向量 + FTS5 + 图遍历混合检索 | Mem0 Hybrid Retrieval |
| F-6 | **ReflectionEngine** | LLM 生成高阶洞察 | Generative Agents Reflection |
| F-7 | **Curator LangGraph** | 状态机编排搬运小人 | LangGraph StateGraph |
| F-8 | **Room 管理** | 房间 CRUD + 层级关系 | — |
| F-9 | **ContextCompiler** | 上下文编译器：Core + Retrieved + Recent | MemGPT Context Compiler |
| F-10 | **MemoryTools** | OpenAI function schema Tool 定义 | MemGPT Tool Use |
| F-11 | **DreamInsight** | 搬运小人巡检洞察（1-3条/轮） | OpenClaw Dream Insights |
| F-12 | **Query Write-back** | 好的查询结果回写知识库 | Karpathy LLM Wiki |
| F-13 | **Multi-pass Ingest** | Pass 2+3+4（事实+去重+关系） | sage-wiki 5-pass |
| F-14 | **MemoryType.DECISION** | 决策记录作为一等公民 | @bendetro Decision Record |
| F-15 | **MemoryHealthScore** | 完整 5 维度健康评分 | OpenClaw health score |

### 5.2 四因子评分（升级）

```python
score = α·recency + β·importance + γ·relevance + δ·proximity

relevance  = cosine_similarity(embed(query), memory.embedding)  # 替代 BM25
proximity  = 1.0 / (1.0 + graph_distance(query_room, memory.room))

# v0.2 权重: α=0.2, β=0.2, γ=0.4, δ=0.2
```

### 5.3 Curator LangGraph 状态机

```
START → GATHER_SIGNAL → items>0? ─No→ END
                            │Yes
                    EXTRACT_FACTS
                            │
                      RECONCILE (per fact)
                            │
                      REFLECT (importance_sum > threshold → insights)
                            │
                        PRUNE (decay + auto)
                            │
                      HEALTH_CHECK (5-dimension score)
                            │
                       REPORT → END
```

### 5.4 Context Compiler

```python
class ContextCompiler:
    def compile(self, query: str | None = None,
                include_core: bool = True,
                max_tokens: int = 4000) -> str:
        """
        ===== CORE MEMORY =====
        [persona] [user] [preferences]

        ===== RELEVANT MEMORIES =====
        [top-k retrieved, if query provided]

        ===== RECENT CONTEXT =====
        [last N turns from Recall]
        """
```

---

## 6. v1.0 — 🏛️ Palace（95 分）

> **前置**：v0.2 使用 2 周+，搬运小人自动运行 10+ 次  
> **目标**：生产就绪。Sleep-time 自动化、完整审计、监控

### 6.1 新增组件

| # | 组件 | 做什么 | 灵感 |
|---|------|--------|------|
| P-1 | **Sleep-time Compute** | 定时器+事件驱动自动触发 Curator | Sleep-time Compute 论文 |
| P-2 | **Heartbeat Controller** | 循环防护：MAX_STEPS, token ceiling, dedup | MemGPT Heartbeat |
| P-3 | **Ebbinghaus 衰减** | 遗忘曲线驱动的自动 importance 衰减 | 认知科学 |
| P-4 | **Core 预算执行** | 硬性 token 上限 + 自动 demote | Claude MEMORY.md ≤200行 |
| P-5 | **监控指标** | p95 延迟, 增长率, 整理频率, token/轮 | 工程最佳实践 |
| P-6 | **MCP Server** | Memory Tools 暴露为 MCP 标准协议 | — |
| P-7 | **Batch Import** | 批量导入 Markdown/JSONL | Karpathy Ingest |
| P-8 | **Memory Export** | 全量导出为 Markdown 知识库 | — |
| P-9 | **Multi-persona** | 多 persona profile 切换 | MemGPT persona blocks |
| P-10 | **Full Ingest Pipeline** | 完整 5-pass（diff→extract→map→link→update） | sage-wiki |

### 6.2 Sleep-time Trigger

```python
# 满足任一即触发
triggers:
  - 距上次整理 ≥ 24h
  - 累计新增 ≥ 20 条记忆
  - 近期重要性累加 ≥ 5.0
  - 手动 CLI/API

# 冷却期: 两次整理间隔 ≥ 1h
```

### 6.3 Ebbinghaus 衰减

```python
retention = exp(-t / S)
S = base_stability * (1 + log(1 + access_count))  # 访问次数增加稳定性
base_stability = 168  # 1 week half-life (单次访问)
effective_importance = importance * retention
# prune when effective_importance < 0.05
```

---

## 7. TDD 策略

> **Iron Law**: NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.

### 7.1 测试架构

| 层级 | 目录 | LLM 依赖 | v0.1 覆盖率 |
|------|------|---------|------------|
| Unit | `test_models/` | ❌ | ≥95% |
| Unit | `test_store/` | ❌ | ≥90% |
| Unit | `test_engine/` | ⚡Mock | ≥85% |
| Unit | `test_foundation/` | ❌ | ≥90% |
| Integration | `test_service/` | ⚡Mock | 全 Service 方法 |
| E2E | `test_e2e/` | ⚡Mock | 2 核心场景 |

### 7.2 Mock 策略

> LLM 是系统边界。所有 LLM 依赖通过 Protocol 注入，测试时用确定性 Mock。

```python
# foundation/llm.py
class LLMProvider(Protocol):
    async def complete(self, prompt: str,
                       response_format: type | None = None) -> str: ...

# tests/conftest.py
@dataclass
class MockLLM:
    responses: list[str]
    _call_count: int = 0
    async def complete(self, prompt, response_format=None) -> str:
        response = self.responses[self._call_count % len(self.responses)]
        self._call_count += 1
        return response

@pytest.fixture
def tmp_data_dir(tmp_path):
    (tmp_path / "core").mkdir()
    (tmp_path / "archival").mkdir()
    return tmp_path
```

### 7.3 实现顺序（按依赖拓扑）

```
Round 1: Foundation (无外部依赖)
  → test_audit_log.py, test_config.py, test_llm.py

Round 2: Models (纯数据)
  → test_memory.py, test_audit.py, test_curator.py

Round 3: Store (I/O, tmp_path)
  → test_core_store.py, test_recall_store.py

Round 4: Engine (Mock LLM)
  → test_scoring.py, test_fact_extractor.py, test_reconcile.py

Round 5: Service (Integration)
  → test_memory_service.py, test_retriever.py, test_curator.py

Round 6: E2E Pipeline
  → test_full_lifecycle.py (save→search→update→curate→verify)
  → test_core_budget_enforcement.py
```

### 7.4 TDD 纪律

| 规则 | 执行 |
|------|------|
| 每个 test 先 RED | 必须看到 FAILED |
| 最小 GREEN | 写刚好够通过的代码 |
| 即时 REFACTOR | GREEN 后立刻清理 |
| LLM = Protocol | 所有 LLM 依赖注入 |
| 文件系统 = tmp_path | 所有 Store 测试 |
| 每个 Round 结束 | `pytest tests/ -v` 全绿才下一 Round |

---

## 8. 配置设计

> 💡 参照 pi-mono Provider 抽象：Provider + Model 分离，API key 从环境变量自动解析。

### 8.1 LLM Provider

```python
class ModelConfig(BaseModel):
    provider: str = "openai"
    model_id: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    max_tokens: int = 2000

ENV_KEY_MAP = {
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "local": "",
}
```

### 8.2 配置文件

```yaml
memory_palace:
  llm:
    provider: "openai"
    model_id: "gpt-4o-mini"
  storage:
    base_dir: "./data"
  core:
    max_bytes: 2048
    blocks: ["persona", "user", "preferences"]
  rooms:
    - {name: "general", description: "未分类通用记忆"}
    - {name: "preferences", description: "用户偏好"}
    - {name: "projects", description: "项目知识"}
    - {name: "people", description: "人物关系"}
    - {name: "skills", description: "技能记忆"}
  scoring:
    weights: {recency: 0.25, importance: 0.25, relevance: 0.50}
    decay_lambda: 0.01
  curator:
    trigger: {timer_hours: 24, session_count: 20, cooldown_hours: 1}
    prune_threshold: 0.05
```

---

## 9. 非功能性需求

| 需求 | v0.1 | v0.2 | v1.0 |
|------|------|------|------|
| 检索延迟 p95 | <500ms | <200ms | <100ms |
| Curator 单轮耗时 | <60s | <30s | <15s |
| 记忆容量 | ~100 条 | ~1000 条 | ~10000 条 |
| 测试覆盖率 | ≥80% | ≥85% | ≥90% |

---

## 10. 依赖清单

```toml
# v0.1
[project]
dependencies = [
    "pydantic>=2.0", "pydantic-settings>=2.0",
    "openai>=1.0", "typer>=0.9", "rich>=13.0", "pyyaml>=6.0",
]
[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=5.0", "pytest-asyncio>=0.23", "ruff>=0.4"]

# v0.2 新增
# "chromadb>=0.5", "kuzu>=0.4", "langgraph>=0.2", "sentence-transformers"
```

---

## 11. 版本升级检查清单

### v0.1 → v0.2

- [ ] E2E 测试全绿稳定 ≥1 周
- [ ] 积累 50+ 条记忆
- [ ] FTS5 检索质量不足（需向量）
- [ ] Room 分类体系验证合理

### v0.2 → v1.0

- [ ] 搬运小人自动运行 10+ 次
- [ ] 混合检索准确率满足需求
- [ ] Reflection 洞察被引用 ≥5 次
- [ ] 手动触发不够用（需 Sleep-time）

---

## Appendix: 隐喻映射速查

```
认知概念               v0.1                  v0.2                 v1.0
──────────           ──────────            ──────────           ──────────
记忆宫殿 (Palace)     JSON+SQLite           +Chroma+KuzuDB       +监控指标
房间 (Room)           tags: list            Room 图节点           Room 层级导航
位点 (Locus)          MemoryItem            +embedding 位置       +空间坐标
路径 (Path)           FTS5 关键词           图遍历                +遗忘曲线路径
搬运小人 (Curator)     同步函数              LangGraph 状态机      +Sleep-time auto
巡检 (Patrol)          手动 CLI              timer/count           +importance 累加
搬运 (Move)            Reconcile CRUD        +Promote/Demote      +自动预算管理
整理 (Organize)        去重/合并             +Reflection+Insight   +洞察递归
清扫 (Sweep)           手动 prune            decay+auto            +Ebbinghaus
记录 (Log)             JSONL audit           +变更链               +可视化审计图
```

---

## 已确认决策

| 决策 | 结论 |
|------|------|
| 项目位置 | 独立仓库 `/Users/link/Documents/Agent_Project/memory-palace/` |
| LLM Provider | 独立配置，pi-mono 风格，默认 `openai/gpt-4o-mini` |
| 首批 Room | general / preferences / projects / people / skills |
| v0.1 Relevance | SQLite FTS5 BM25 归一化 → v0.2 替换为余弦相似度 |
| 同步优先 | v0.1 全同步，v0.2 引入 LangGraph 编排 |
| 遗忘策略 | 渐进衰减（OpenClaw 公式），非断崖 TTL |

