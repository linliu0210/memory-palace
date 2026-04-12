# 🏛️ Memory Palace v0.2 — 项目转交书

> **版本**: v0.2.0 Foundation Complete  
> **日期**: 2026-04-12  
> **交付方**: Antigravity (System Architect / Dispatcher)  
> **接收方**: 项目所有者  
> **项目路径**: `/Users/link/Documents/Agent_Project/memory-palace`  
> **当前分支**: `feat/integration-round13` @ `29ac9aa`  
> **测试状态**: 284 passed, 0 failed  

---

## 第一部分：项目全景

### 1.1 一句话定位

**给 AI Agent 装一套「记忆操作系统」**——不只让它记得住，而是让它自己整理、自己归纳、自己遗忘，越用越聪明。

### 1.2 核心差异化

| 竞品 | 隐喻 | 短板 |
|-------|------|------|
| **mem0** | 向量堆 + CRUD | 无自主整理，记忆只增不减 |
| **MemGPT** | OS 虚拟分页 | 概念复杂，不直觉 |
| **Memory Palace** | 🏛️ 空间化宫殿 + 🧹 搬运小人 | 空间分类 + 后台 Curator 自动整理 + 混合检索 + 自我反思 |

### 1.3 设计理念

```
知识价值 = f(摄取次数 × 查询次数 × 梦境次数)   ← 复合增长
        ≠ f(文档上传数)                        ← 线性堆积
```

- **宫殿** 是活的 Wiki，不是静态仓库
- **搬运小人** 是认知管家——去重、冲突解决、模式发现、**生成高阶洞察**
- **遗忘** 不是缺陷，是智慧——渐进衰减、优雅归档、永不物理删除
- **维护成本趋近于零**——人负责输入和决策，搬运小人负责所有簿记

### 1.4 版本迭代总览

> **Stability before Sophistication** — 先跑通再跑好。

| 版本 | 代号 | 分数 | 核心交付 | 隐喻完成度 | 状态 |
|------|------|------|---------|-----------| ----|
| **v0.1** 🦴 | Skeleton | **60** | Pipeline 跑通；两层存储；FTS5 检索 | 宫殿有骨架，搬运小人能走路 | ✅ Complete |
| **v0.2** 🧱 | Foundation | **80** | 三层存储；混合检索；Curator 自动化+反思 | 有房间有路径，小人能搬运整理 | ✅ Complete |
| v1.0 🏛️ | Palace | 95 | Sleep-time 自动化；遗忘曲线；MCP 暴露 | 宫殿完全建成，小人高效自治 | 📋 Planned |

---

## 第二部分：v0.2 升级了什么

### 2.1 升级总览

v0.2 在 v0.1 骨架之上实现了四个关键能力跃迁：

| 维度 | v0.1 (60分) | v0.2 (80分) | 价值 |
|------|------------|------------|------|
| **检索** | FTS5 关键词匹配 | FTS5 + Vector 混合 (RRF) | 搜「编程偏好」能找到「喜欢 Python」 |
| **评分** | 三因子（BM25 归一化） | 增强三因子 + Room bonus（余弦相似度） | 语义+空间双维度排序 |
| **自我认知** | 无 | ReflectionEngine 生成高阶洞察 | 系统能「举一反三」 |
| **健康监控** | 无 | 5 维度 MemoryHealthScore | 知道记忆系统是否「生病了」 |
| **Curator** | 手动函数调用 | 7 阶段状态机自动编排 | 搬运小人有了完整工作流 |
| **存储** | 两层 (Core + Recall) | 三层 (+Archival 全量向量) | 所有记忆都可语义检索 |
| **上下文** | 简单文本拼接 | ContextCompiler 结构化编译 | Agent 拿到的上下文更精准 |
| **技术债** | 7 项 | 0 项 (全部清零) | 代码质量显著提升 |

### 2.2 与 SPEC 的差异决策

v0.2 开发中对原始 SPEC v2.0 做了以下重要调整：

| 原始 SPEC 设想 | v0.2 实际决策 | 理由 |
|---|---|---|
| KuzuDB 图存储 + 四因子 Proximity | **延迟至 v1.0**，用 Room bonus 替代 | 引入 ChromaDB+Embedding 两新介质已够，三新依赖同时上风险失控 |
| LangGraph StateGraph 编排 Curator | **拒绝 LangGraph → 纯 Python 状态机** | 预检发现 LangGraph 拉入 13 个传递依赖，超过阈值 |
| Archival = 低重要性存放地 | **Archival = 全量语义索引层** | 所有记忆同时写入 Archival，高重要性记忆也能语义检索 |
| 四因子评分 (含 Proximity) | **增强三因子 + Room bonus** | 当前 5 房间，图查询无明显优势；v1.0 1000+ 记忆后再上 |

> 详见: [SPEC_V02.md §1](file:///Users/link/Documents/Agent_Project/memory-palace/SPEC_V02.md)

---

## 第三部分：系统架构 (v0.2 当前态)

### 3.1 五层架构

```
╔════════════════════════════════════════════════════════════════════╗
║  5F  Integration    CLI: save, search, update, forget, curate,    ║
║                     inspect, audit, rooms, context, reflect,      ║
║                     health (12 commands)                          ║
╠════════════════════════════════════════════════════════════════════╣
║  4F  Service        MemoryService (CRUD facade, 3-tier routing)   ║
║                     HybridRetriever (FTS5 + Vector → RRF)         ║
║                     ContextCompiler (Core+Retrieved+Recent)       ║
║                     CuratorService + CuratorGraph (7-phase SM)    ║
║                     Retriever (v0.1 legacy fallback)              ║
╠════════════════════════════════════════════════════════════════════╣
║  3F  Engine         FactExtractor (LLM → 原子事实)                ║
║                     ScoringEngine (cosine sim + ScoredCandidate)  ║
║                     ReconcileEngine (LLM → ADD/UPDATE/DELETE)     ║
║                     ReflectionEngine (LLM → 高阶洞察)             ║
║                     MemoryHealthScore (5 维度评分)                 ║
╠════════════════════════════════════════════════════════════════════╣
║  2F  Storage        CoreStore (JSON 平文件, ≤2KB 预算)            ║
║                     RecallStore (SQLite + FTS5 全文搜索)           ║
║                     ArchivalStore (ChromaDB 向量, 全量索引)        ║
╠════════════════════════════════════════════════════════════════════╣
║  1F  Foundation     Config (Pydantic Settings + YAML)             ║
║                     AuditLog (JSONL append-only)                  ║
║                     LLMProvider (Protocol + OpenAI httpx)         ║
║                     EmbeddingProvider (Protocol: OpenAI / Local)  ║
╚════════════════════════════════════════════════════════════════════╝

依赖方向: Integration → Service → Engine → Store → Foundation → Models (严格单向)
```

### 3.2 数据流 — 四条核心路径

#### 路径一：保存 (Save)

```
用户输入 "我喜欢深色模式"
    │
    ▼
MemoryService.save(content, importance=0.8, room="preferences")
    │
    ├─ importance ≥ 0.7 → CoreStore.save("preferences", item)
    │                        └─ 写入 core/preferences.json
    │
    ├─ importance < 0.7  → RecallStore.insert(item)
    │                        └─ 写入 recall.db + FTS5 索引
    │
    ├─ ALL items → ArchivalStore.insert(item)         ← v0.2 新增
    │                └─ embed(content) → ChromaDB.upsert()
    │
    ├─ Core 超预算? → 自动 demote 最低 importance 到 Recall   ← v0.2 新增
    │
    └─ AuditLog.append(CREATE)
```

#### 路径二：搜索 (Search)

```
用户查询 "编程语言偏好"
    │
    ▼
HybridRetriever.search(query, top_k=5)
    │
    ├─ 并行 ① RecallStore.fts_search("编程语言偏好")    → 关键词候选
    │       ② ArchivalStore.search(embed(query))        → 语义候选
    │
    ├─ Reciprocal Rank Fusion (k=60)  → 合并去重
    │   rrf_score(d) = Σ 1 / (60 + rank_i(d))
    │
    ├─ 用 ScoredCandidate 重打分 (增强三因子 + room_bonus)
    │   score = 0.20·recency + 0.20·importance + 0.50·relevance + 0.10·room_bonus
    │
    └─ 返回 top_k MemoryItem[]

    降级: archival_store=None 时自动回退到 FTS5-only (兼容 v0.1)
```

#### 路径三：整理 (Curate)

```
palace curate → CuratorService.run()
    │
    ▼
CuratorGraph (7 阶段状态机)
    │
    ├─ ① GATHER: RecallStore.get_recent(24h) → items
    │
    ├─ ② EXTRACT: FactExtractor → 原子事实
    │
    ├─ ③ RECONCILE: ReconcileEngine → ADD/UPDATE/DELETE/NOOP
    │
    ├─ ④ REFLECT: importance 总和 > 阈值?
    │       └─ Yes → ReflectionEngine → 高阶洞察 (MemoryType.REFLECTION)
    │
    ├─ ⑤ PRUNE: 衰减检查 → PRUNED (软删除)
    │
    ├─ ⑥ HEALTH_CHECK: compute_health() → 5 维度评分
    │
    └─ ⑦ REPORT: 汇总 CuratorReport
```

#### 路径四：上下文编译 (Context)

```
ContextCompiler.compile(query="项目进展")
    │
    ├─ [CORE MEMORY] — CoreStore ACTIVE-only 记忆
    │
    ├─ [RETRIEVED] — HybridRetriever.search(query) 结果
    │
    └─ [RECENT ACTIVITY] — RecallStore.get_recent(N)
    
    →  结构化文本输出，直接注入 Agent system prompt
```

---

## 第四部分：代码清单

### 4.1 源代码文件 (34 个 .py)

#### Foundation (1F) — 水电煤

| 文件 | 行数 | 职责 | v0.2 变动 |
|------|------|------|-----------|
| [config.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/config.py) | 162 | Pydantic Settings + YAML 加载 | +EmbeddingConfig |
| [audit_log.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/foundation/audit_log.py) | 77 | JSONL append-only 审计日志 | — |
| [llm.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/foundation/llm.py) | 67 | LLMProvider Protocol | — |
| [openai_provider.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/foundation/openai_provider.py) | 79 | httpx async LLM 客户端 | — |
| [embedding.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/foundation/embedding.py) | 57 | EmbeddingProvider Protocol + Config | **v0.2 新增** |
| [openai_embedding.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/foundation/openai_embedding.py) | 106 | OpenAI Embedding httpx 客户端 | **v0.2 新增** |
| [local_embedding.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/foundation/local_embedding.py) | 64 | sentence-transformers 本地推理 | **v0.2 新增** |

#### Models — 数据模型

| 文件 | 行数 | 核心类 | v0.2 变动 |
|------|------|--------|-----------|
| [memory.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/models/memory.py) | 87 | MemoryItem, MemoryStatus, MemoryTier, MemoryType, Room | — |
| [audit.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/models/audit.py) | 12 | AuditEntry, AuditAction | — |
| [curator.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/models/curator.py) | 34 | CuratorReport | +health 字段 |

#### Storage (2F) — 三个仓库

| 文件 | 行数 | 存储介质 | v0.2 变动 |
|------|------|----------|-----------|
| [core_store.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/store/core_store.py) | 141 | JSON 平文件 | — |
| [recall_store.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/store/recall_store.py) | 370 | SQLite + FTS5 | +update_field() |
| [archival_store.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/store/archival_store.py) | 236 | ChromaDB 向量 | **v0.2 新增** |
| [base.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/store/base.py) | ~20 | AbstractStore 接口 | — |

#### Engine (3F) — 五台机器

| 文件 | 行数 | LLM? | v0.2 变动 |
|------|------|------|-----------|
| [fact_extractor.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/engine/fact_extractor.py) | 98 | ✅ | — |
| [scoring.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/engine/scoring.py) | 211 | ❌ | +ScoredCandidate, +cosine_similarity, +room_bonus |
| [reconcile.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/engine/reconcile.py) | 123 | ✅ | — |
| [reflection.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/engine/reflection.py) | 141 | ✅ | **v0.2 新增** |
| [health.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/engine/health.py) | 161 | ❌ | **v0.2 新增** |

#### Service (4F) — 四个管家

| 文件 | 行数 | v0.2 变动 |
|------|------|-----------|
| [memory_service.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/service/memory_service.py) | 475 | +get_by_id(), +active-only core, +auto-demote, +3-tier routing |
| [hybrid_retriever.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/service/hybrid_retriever.py) | 282 | **v0.2 新增** |
| [context_compiler.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/service/context_compiler.py) | 104 | **v0.2 新增** |
| [curator.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/service/curator.py) | 207 | 重构 → 委托给 CuratorGraph |
| [curator_graph.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/service/curator_graph.py) | 307 | **v0.2 新增** — 纯 Python 7 阶段状态机 |
| [retriever.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/service/retriever.py) | 110 | 保留为 FTS5-only fallback |

#### Integration (5F) — 入口

| 文件 | 行数 | v0.2 变动 |
|------|------|-----------|
| [cli.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/integration/cli.py) | ~410 | +context, +reflect, +health 三个新命令 |
| [tools.py](file:///Users/link/Documents/Agent_Project/memory-palace/src/memory_palace/integration/tools.py) | ~30 | placeholder (v1.0 MCP) |

### 4.2 测试文件 (26 个 .py)

| 目录 | 测试文件数 | 用例数 | 覆盖 |
|------|-----------|--------|------|
| test_foundation/ | 6 | 46 | Config, AuditLog, LLM, Embedding (3 种) |
| test_models/ | 3 | 25 | MemoryItem, AuditEntry, CuratorReport |
| test_store/ | 3 | 44 | CoreStore, RecallStore, ArchivalStore |
| test_engine/ | 5 | 51 | Scoring(v1+v2), FactExtractor, Reconcile, Reflection, Health |
| test_service/ | 6 | 80 | MemoryService(v1+v2), Retriever, HybridRetriever, ContextCompiler, CuratorGraph |
| test_integration/ | 2 | 13 | CLI, OpenAI Provider |
| test_e2e/ | 3 | 25 | 完整生命周期 (v0.1 + v0.2) |
| **总计** | **28** | **284** | — |

### 4.3 代码规模

| 维度 | v0.1 | v0.2 | 增幅 |
|------|------|------|------|
| 源代码文件 | 28 | 34 | +6 |
| 源代码总行数 | ~2,566 | ~4,595 | +2,029 |
| 测试文件 | 19 | 28 | +9 |
| 测试用例 | 154 | 284 | +130 (84%) |
| 运行时依赖 | 6 | 7 (+chromadb) | — |
| 开发依赖 | 3 | 3 | — |

---

## 第五部分：关键设计决策

### 5.1 完整决策时间线

| Round | 决策 | 理由 | 影响 |
|-------|------|------|------|
| R1 (v0.1) | LLM 用 Protocol（结构化子类型）而非 ABC | 测试用 MockLLM 无需继承，更 Pythonic | 奠定整个项目的 DI 基调 |
| R3 (v0.1) | CoreStore 用 JSON 而非 SQLite | SPEC「随身口袋」语义，原子写入，人类可读 | 低容量高可读的设计取舍 |
| R3 (v0.1) | RecallStore FTS5 用 `simple` tokenizer | 中文兼容，避免 ICU 依赖 | 全文搜索跨语言支持 |
| R4 (v0.1) | ScoringEngine 纯函数，零 LLM | 评分必须确定性可测试 | 引擎层的 LLM/非 LLM 边界 |
| R5 (v0.1) | update/forget 软操作 | 「永不物理删除」，保留完整审计链 | 所有数据操作可追溯 |
| **R8 (v0.2)** | **Embedding 双模式 Day 1** | OpenAI API + 本地 ONNX 同时实现 | 用户可离线使用，零成本方案 |
| **R9 (v0.2)** | **ChromaDB upsert 而非 add** | 幂等性——重复写入不崩溃 | 数据安全 |
| **R9 (v0.2)** | **update_field() 冻结列白名单** | 防止 SQL 注入和任意列修改 | 安全边界 |
| **R10 (v0.2)** | **RRF k=60（原论文标准值）** | 经验证有效，不做过早优化 | 检索质量基线 |
| **R10 (v0.2)** | **保留 rank_legacy()** | v0.1 测试不动，向后兼容 | 渐进式重构 |
| **R11 (v0.2)** | **Reflection 输出为完整 MemoryItem** | 洞察是一等公民记忆，可被检索、可被引用 | 记忆可自我增殖 |
| **R11 (v0.2)** | **Health diversity 用 Shannon 熵** | 数学严谨，归一化到 [0,1] | 可量化的健康指标 |
| **R12 (v0.2)** | **🚨 拒绝 LangGraph → 纯 Python 状态机** | 13 个传递依赖超过 5-package 阈值 | 项目保持轻量 |
| **R12 (v0.2)** | **Core 自动 demote** | 超预算时自动降级最低 importance 到 Recall | Budget 自动执行 |
| **R13 (v0.2)** | **Archival = 全量索引层** | 高重要性记忆也需要语义检索 | 检索无死角 |

### 5.2 LangGraph 拒绝事件（详述）

这是 v0.2 最重要的架构决策，值得展开说明。

**背景**：SPEC v2.0 §5.3 设想使用 LangGraph 的 StateGraph 编排 Curator 7 阶段流程。SPEC_V02.md 也沿用了这一设想，但在 §9.1 留了后手："如果超过 5 个新包，则降级为纯 Python 状态机"。

**R12 预检结果**：实施前执行 `pip install langgraph && pip list | grep lang`，发现 `langgraph>=0.3` 引入：
1. langchain-core
2. langsmith
3. orjson
4. tenacity
5. packaging
6. ... 共 13 个传递依赖

**决策**：超过阈值，拒绝 LangGraph，改用自主实现的 CuratorGraph（enum 驱动的状态机，307 行纯 Python，零外部依赖）。

**结果**：`pyproject.toml` 中没有 `langgraph`。CuratorGraph 完美实现了相同的 7 阶段流程 + 错误恢复 + 无限循环防护。

---

## 第六部分：技术债务状态

### 6.1 v0.1 技术债（7 项，v0.2 全部清零）

| # | 债务 | 来源 | 修复 | 方式 |
|---|------|------|------|------|
| TD-1 | `update()` 直接访问 `_recall_store._conn` | R5 | **R9** ✅ | `RecallStore.update_field()` 封装 |
| TD-2 | `get_core_context()` 含 SUPERSEDED/PRUNED | R5 | **R12** ✅ | Active-only 过滤 |
| TD-3 | `rank()` 平行数组 API，易错位 | R4 | **R10** ✅ | `ScoredCandidate` 类型安全接口 |
| TD-4 | CLI `inspect` 绕过 MemoryService | R7 | **R13** ✅ | `MemoryService.get_by_id()` |
| TD-5 | CLI `rooms` 硬编码列表 | R7 | **R13** ✅ | 改读 `Config.rooms` |
| TD-6 | 未使用 `import httpx` | R7 | **R8** ✅ | 删除 |
| TD-7 | `save()` 不检查 Core 预算 | R6 | **R12** ✅ | 超限自动 demote |

### 6.2 v0.2 新增技术债

**无**。v0.2 开发过程中未识别到新的技术债。

---

## 第七部分：开发历程

### 7.1 全 13 轮 TDD 里程碑

```
v0.1 Skeleton (7 轮, 2026-04-06 ~ 04-09)
  R1  Foundation    — Config + AuditLog + LLMProvider      (+19 tests)
  R2  Models        — MemoryItem + AuditEntry + Room        (+17 tests)
  R3  Store         — CoreStore + RecallStore               (+38 tests)
  R4  Engine        — FactExtractor + Scoring + Reconcile   (+32 tests)
  R5  Service       — MemoryService + Retriever + Curator   (+29 tests) ← 2 Fix Rounds
  R6  E2E           — Full lifecycle + budget enforcement    (+2 tests)
  R7  Integration   — OpenAI Provider + CLI 9 commands       (+16 tests)
  ── main @ 45ff461: 154 passed ──

v0.2 Foundation (6 轮, 2026-04-12)
  R8  Embedding     — EmbeddingProvider + OpenAI + Local     (+26 tests)
  R9  ArchivalStore — ChromaDB + RecallStore.update_field    (+19 tests)
  R10 Scoring+Hybrid— ScoredCandidate + HybridRetriever RRF (+33 tests)
  R11 Reflection    — ReflectionEngine + MemoryHealthScore   (+21 tests)
  R12 Service v0.2  — ContextCompiler + CuratorGraph + MemSvc升级 (+22 tests)
  R13 Integration   — CLI v0.2 + E2E lifecycle               (+9 tests)
  ── feat/integration-round13 @ 29ac9aa: 284 passed ──
```

### 7.2 治理协作模型

```
            ┌─────────────────────────────┐
            │  Antigravity (Dispatcher)    │
            │  系统设计 + 任务调度 + Merge  │
            └──────┬──────────────┬────────┘
                   │              │
            Prompt 下发      Prompt 下发
                   │              │
           ┌───────▼──────┐ ┌─────▼────────┐
           │ Claude Code  │ │    Codex      │
           │ (Dev Agent)  │ │ (Reviewer)    │
           │ 实现代码     │ │ 独立验证      │
           └──────────────┘ └───────────────┘
```

v0.2 沿用了 v0.1 的 Multi-Agent TDD 模式，但由于 Dispatcher (Antigravity) 直接充当了 v0.2 设计者的角色，R8-R13 的具体实现由 subagents 在独立 conversation 中完成。

### 7.3 Git 分支状态

```
main                           ← v0.1 MVP (154 passed)
feat/foundation-round1         (merged to main)
feat/models-round2             (merged to main)
feat/store-round3              (merged to main)
feat/engine-round4             (merged to main)
feat/service-round5            (merged to main)
feat/e2e-round6                (merged to main)
feat/integration-round7        (merged to main)
feat/embedding-round8          (v0.2, pending merge)
feat/archival-round9           (v0.2, pending merge)
feat/scoring-hybrid-round10    (v0.2, pending merge)
feat/reflection-round11        (v0.2, pending merge)
feat/service-round12           (v0.2, pending merge)
* feat/integration-round13     ← HEAD (v0.2 complete, 284 passed)
feat/benchmark-framework       (实验性分支, v0.2 完成后再评估)
```

**待办**：将 `feat/integration-round13` 合并到 `main`，打 `v0.2` tag。

---

## 第八部分：配置与环境

### 8.1 运行环境

```bash
# 语言
Python 3.11+

# 虚拟环境
source /Users/link/Documents/Agent_Project/.venv/bin/activate

# 运行测试 (在虚拟环境中)
pytest tests/ -q

# Lint
ruff check && ruff format --check

# CLI
palace --help
```

### 8.2 配置文件

```yaml
# memory_palace.yaml
llm:
  provider: "openai"
  model_id: "gpt-4o-mini"
  base_url: "https://api.openai.com/v1"
  max_tokens: 2000

embedding:                    # v0.2 新增
  provider: "openai"          # "openai" | "local"
  model_id: "text-embedding-3-small"
  dimension: 1536

core:
  max_bytes: 2048

rooms:
  - {name: "general", description: "未分类通用记忆"}
  - {name: "preferences", description: "用户偏好"}
  - {name: "projects", description: "项目知识"}
  - {name: "people", description: "人物关系"}
  - {name: "skills", description: "技能记忆"}

scoring:
  weights: {recency: 0.20, importance: 0.20, relevance: 0.50, room_bonus: 0.10}
  decay_lambda: 0.01

curator:
  trigger: {timer_hours: 24, session_count: 20, cooldown_hours: 1}
  prune_threshold: 0.05
```

API Key 环境变量：

```bash
export OPENAI_API_KEY="sk-..."        # LLM + Embedding (default)
export DEEPSEEK_API_KEY="sk-..."      # DeepSeek
# 本地模型无需 key
```

### 8.3 数据目录

```
~/.memory_palace/                     # 默认 data_dir
├── core/                            # CoreStore JSON 文件
│   ├── general.json
│   └── preferences.json
├── recall.db                        # RecallStore SQLite + FTS5
├── archival/                        # ArchivalStore ChromaDB (v0.2)
│   └── chroma.sqlite3
├── audit.jsonl                      # 审计日志
└── memory_palace.yaml               # 配置文件
```

### 8.4 依赖清单

```toml
[project.dependencies]
"pydantic>=2.5"
"pydantic-settings>=2.1"
"pyyaml>=6.0"
"structlog>=24.1"
"typer>=0.9"
"rich>=13.0"
"httpx>=0.27"
"chromadb>=1.0"              # v0.2 新增 — ArchivalStore

[project.optional-dependencies]
local = ["sentence-transformers>=3.0"]   # 本地 Embedding
dev = ["pytest>=8.0", "pytest-asyncio>=0.24", "ruff>=0.4"]
```

---

## 第九部分：API 变更与向后兼容

### 9.1 Breaking Changes

| API | v0.1 | v0.2 | 兼容性 |
|-----|------|------|--------|
| `ScoringEngine.rank()` | 平行数组参数 | `ScoredCandidate` 对象 | ✅ 旧签名保留为 `rank_legacy()` |
| `MemoryService.search()` | 同步, FTS5-only | **异步**, FTS5+Vector | ✅ 同步 `Retriever` 仍可用 |
| `CuratorService.run()` | 直接执行 | 委托 CuratorGraph | ✅ 签名不变，内部重构 |
| `get_core_context()` | 返回 ALL items | 返回 ACTIVE-only | ⚠️ 行为修正，不算 API break |

### 9.2 新增 API

```python
# MemoryService 新增
def get_by_id(memory_id: str) -> MemoryItem | None    # 跨层查找

# CLI 新增
palace context [--query "..."] [--no-core]              # 编译上下文
palace reflect                                          # 手动触发反思
palace health                                           # 5 维度健康分
```

---

## 第十部分：关键文档索引

| 文档 | 路径 | 职责 | 状态 |
|------|------|------|------|
| **SPEC.md** | 项目根 | 系统规格书 v2.0 (全版本愿景) | ✅ 最新 |
| **SPEC_V02.md** | 项目根 | v0.2 专项规格 (差异决策+新组件) | ✅ 最新 |
| **TUTORIAL_V02.md** | 项目根 | v0.2 开发者教学指南 (1100行) | ✅ 最新 |
| **CONVENTIONS.md** | 项目根 | 代码约定 + TDD 纪律 | ✅ 最新 |
| **NAVIGATION.md** | 项目根 | 项目导航入口 | ⚠️ 停留在 v0.1 |
| **PROJECT_CONTEXT.md** | 项目根 | 项目状态仪表盘 | ⚠️ 严重过期 (R1) |
| **DISPATCH_LOG.md** | 项目根 | Multi-Agent 任务日志 (R1-R7) | ✅ v0.1 完整 |
| **README.md** | 项目根 | 开发者简介 | ⚠️ 需更新 |

> ⚠️ `PROJECT_CONTEXT.md` 和 `NAVIGATION.md` 停留在 v0.1 早期阶段，**建议 v1.0 开发前更新**。

---

## 第十一部分：已知风险与待观察事项

| 风险 | 严重性 | 状态 | 缓解措施 |
|------|--------|------|----------|
| ChromaDB v1.0 API 稳定性 | 🟡 中 | 观察中 | Pin 版本 `>=1.0`，抽象在 ArchivalStore 之后 |
| search() 同步→异步迁移 | 🟢 已解决 | 已处理 | 旧同步 Retriever 保留 |
| LangGraph 被拒绝 | 🟢 已解决 | 已替代 | 纯 Python 状态机，更少活动部件 |
| PROJECT_CONTEXT.md 过期 | 🟡 中 | 待处理 | v1.0 前需更新 |
| Embedding 维度不一致风险 | 🟢 低 | 已缓解 | Config 强制声明 dimension，ChromaDB 自动校验 |

---

## 第十二部分：v1.0 发展设想（仅供参考）

> ⚠️ **以下内容为架构师的参考性建议，非正式 SPEC。v1.0 正式开发前应撰写 SPEC_V10.md。**

### 12.1 v1.0 定位

```
v0.2 (80分): 搬运小人能搬运整理，但需要你喊它
v1.0 (95分): 搬运小人自主巡逻，你睡觉时它也在干活
```

核心跃迁：**从被动工具变为主动代理**。

### 12.2 建议 v1.0 功能清单

按优先级排序：

#### Tier 1 — 必须做（核心价值飞跃）

| # | 功能 | 预估 | 理由 | v0.2 基础 |
|---|------|------|------|-----------|
| P-1 | **Sleep-time Compute** | 2-3 天 | Curator 从手动→自动，核心体验质变 | CuratorGraph 状态机已就绪 |
| P-2 | **Ebbinghaus 衰减** | 1-2 天 | 记忆自然遗忘曲线，替代简单线性衰减 | HealthScore + importance 追踪已就位 |
| P-3 | **MCP Server** | 3-4 天 | 让任意 Agent 即插即用 Memory Palace | Protocol-based API 可直接暴露 |

**Sleep-time Compute 设计草案**：

```python
# 触发条件（满足任一）
triggers:
  - 距上次整理 ≥ 24h
  - 累计新增 ≥ 20 条记忆
  - 近期重要性累加 ≥ 5.0
  - 手动 CLI/API

# 冷却期: 两次整理间隔 ≥ 1h

# 实现: 
# 方案 A: APScheduler (轻量级)
# 方案 B: asyncio 后台任务 (零依赖)
# 建议: 方案 B，保持零新依赖原则
```

**Ebbinghaus 衰减草案**：

```python
retention = exp(-t / S)
S = base_stability * (1 + log(1 + access_count))
base_stability = 168  # 1 week half-life (单次访问)
effective_importance = importance * retention
# prune when effective_importance < 0.05
```

#### Tier 2 — 应该做（显著提升易用性）

| # | 功能 | 预估 | 理由 |
|---|------|------|------|
| P-4 | **Heartbeat Controller** | 1 天 | MAX_STEPS + token ceiling，防止 Curator 失控 |
| P-5 | **Core 预算自动化** | 1 天 | v0.2 已做 auto-demote，v1.0 加指标监控 |
| P-6 | **Batch Import/Export** | 1-2 天 | Markdown/JSONL 批量导入导出 |
| P-7 | **Multi-persona** | 2 天 | 多 persona profile 切换 |

#### Tier 3 — 可以做（长期技术投资）

| # | 功能 | 预估 | 理由 |
|---|------|------|------|
| P-8 | **KuzuDB 图存储** | 3-4 天 | Room 成为真图节点，Proximity 变成真实图距离 |
| P-9 | **Full Ingest Pipeline** | 2-3 天 | 5-pass: diff → extract → map → link → update |
| P-10 | **Query Write-back** | 1 天 | 好的检索结果回写知识库 |
| P-11 | **监控指标** | 1 天 | p95 延迟, 增长率, 整理频率 |

### 12.3 建议开发顺序

```
Phase A: 自动化 (P-1, P-2, P-4)
  Sleep-time Compute → Ebbinghaus 衰减 → Heartbeat 防护
  
Phase B: 集成 (P-3)
  MCP Server — 最大的接口工程

Phase C: 扩展 (P-6, P-7)
  Batch Import/Export → Multi-persona

Phase D: 深水区 (P-8, P-9) — 可选
  KuzuDB 图存储 → Full Ingest Pipeline
```

### 12.4 升级前置条件

根据 SPEC v2.0 §11：

- [ ] v0.2 搬运小人自动运行 **10+ 次**
- [ ] 混合检索准确率满足需求
- [ ] Reflection 洞察被引用 **≥5 次**
- [ ] 手动触发不够用（需 Sleep-time）
- [ ] 积累 **1000+ 条**记忆

### 12.5 v1.0 治理建议

1. **先撰写 SPEC_V10.md**（类似 SPEC_V02.md 的增量 spec），明确与上游 SPEC 的差异
2. **更新 PROJECT_CONTEXT.md**，将模块状态图标更新到 v0.2 完成态
3. **MCP Server 单独一个 Round**，它会改变系统边界（从 lib → server）
4. **KuzuDB 延迟判断**——v1.0 1000+ 记忆后再评估图查询收益是否值得引入依赖
5. **考虑 CI/CD**——v1.0 是生产版本，建议引入 GitHub Actions

---

## 第十三部分：学透标准

当你能回答以下问题时，v0.2 就算掌握了：

### Foundation 层
- [ ] EmbeddingProvider 是 Protocol 还是 ABC？为什么？
- [ ] OpenAI Embedding 和 Local Embedding 通过什么配置切换？

### Storage 层
- [ ] CoreStore、RecallStore、ArchivalStore 分别用什么存储介质？
- [ ] Archival 为什么是「全量索引层」而不是「低重要性存放地」？
- [ ] `update_field()` 的冻结列白名单有哪些列？

### Engine 层
- [ ] ScoredCandidate vs 旧的平行数组有什么优势？
- [ ] cosine_similarity 算出来的值域是什么？
- [ ] ReflectionEngine 生成的洞察是什么 MemoryType？为什么设 importance=0.8？
- [ ] HealthScore 的 5 个维度是什么？diversity 用的什么数学公式？

### Service 层
- [ ] HybridRetriever 的 RRF k=60 是什么意思？为什么选 60？
- [ ] archival_store=None 时 HybridRetriever 降级为什么？
- [ ] CuratorGraph 的 7 个阶段分别是什么？
- [ ] LangGraph 为什么被拒绝？替代方案是什么？
- [ ] Core 超预算时发生什么？

### 系统层
- [ ] 一条记忆 save 时写入了几个存储介质？
- [ ] search 时 FTS5 和 Vector 的结果如何合并？
- [ ] v0.2 总共清理了几项技术债？最重要的是哪一项？

---

> **最后**：本转交书旨在让接收方获得完整的项目上下文，以便独立推进 v1.0 开发。  
> 如有任何疑问，参考 [TUTORIAL_V02.md](file:///Users/link/Documents/Agent_Project/memory-palace/TUTORIAL_V02.md) 获取更深入的逐文件代码讲解，  
> 或参考 [SPEC_V02.md](file:///Users/link/Documents/Agent_Project/memory-palace/SPEC_V02.md) 获取接口契约细节。
