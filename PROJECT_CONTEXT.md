# Memory Palace — Project Context

> **⚡ SEMI-FIXED**: 本文档随项目里程碑更新，不随每次任务变化。
> Orchestrator 在合并重大分支后**必须**更新本文档。
>
> **最后更新**: 2026-04-06 | **更新原因**: SPEC v2.0 重构 — 基于 CEO 架构指南全面重写

---

## 定位

**Memory Palace** 是一个以「记忆宫殿」为空间化存储隐喻、以「搬运小人 (Memory Curator)」为后台自主整理机制的 **Agent Memory System**。

给它一段对话，它能提取原子事实、评估重要性、按空间隐喻分类存储、多因子检索、自动整理冲突和冗余——为任意 LLM Agent 提供可插拔的持久化记忆层。

**核心差异化** vs mem0 / MemGPT:
- mem0 = 向量堆 + 简单 CRUD（无自主整理）
- MemGPT = 操作系统隐喻 + 虚拟分页（复杂但不直觉）
- Memory Palace = **空间化分类 (Room → Locus)** + **后台 Curator Agent 自动整理** + **四因子检索**

---

## 架构

<!-- SEMI-FIXED: 新增/删除 pipeline 节点时更新 -->

```
用户输入: 对话文本 / 原子事实
    │
    ▼
┌──────────── INGEST ────────────────────────────┐
│  FactExtractor (LLM) → list[MemoryItem]        │
│  importance 评分 + 自动分 Room                   │
└────────────────────────────────────────────────┘
    │ MemoryItem[]
    ▼
┌──────────── STORE ─────────────────────────────┐
│  importance ≥ 0.7 → CoreStore (JSON)           │
│  else             → RecallStore (SQLite+FTS5)  │
│  AuditLog.append(CREATE)                       │
└────────────────────────────────────────────────┘
    │
    ▼
┌──────────── RETRIEVE ──────────────────────────┐
│  RecallStore.fts_search(query)                 │
│  ScoringEngine.rank(三因子: R×I×Rel)            │
│  返回 top_k ranked results                     │
└────────────────────────────────────────────────┘
    │
    ▼
┌──────────── CURATE (搬运小人) ─────────────────┐
│  Gather recent → Extract facts                 │
│  Reconcile(new, existing) → ADD/UPDATE/DEL     │
│  AuditLog.append(MERGE/PRUNE/UPDATE)           │
│  → CuratorReport                               │
└────────────────────────────────────────────────┘
```

---

## 模块拓扑

<!-- SEMI-FIXED: 新增/删除/重命名模块时更新 -->

```
src/memory_palace/
├── 🔴 models/              数据模型
│   ├── memory.py                MemoryItem, MemoryStatus, MemoryTier, MemoryType, Room
│   ├── audit.py                 AuditEntry, AuditAction
│   └── curator.py               CuratorReport
│
├── 🔴 store/               存储层
│   ├── base.py                  AbstractStore 接口
│   ├── core_store.py            Core Memory (JSON 文件)
│   └── recall_store.py          Recall Memory (SQLite + FTS5)
│
├── 🔴 engine/              引擎层
│   ├── fact_extractor.py        LLM-based 原子事实提取
│   ├── scoring.py               三因子评分 (Recency × Importance × Relevance)
│   └── reconcile.py             LLM-based 冲突解决 (ADD/UPDATE/DELETE/NOOP)
│
├── 🔴 service/             服务层
│   ├── memory_service.py        对外 CRUD 主接口 (save, search, update, forget)
│   ├── retriever.py             检索引擎 (FTS5 + Scoring)
│   └── curator.py               Memory Curator Agent (搬运小人, 同步 MVP)
│
├── 🔴 integration/         集成层
│   ├── tools.py                 LLM Tool 定义 (MemoryTools)
│   └── cli.py                   CLI 调试工具 (palace save/search/curate/inspect)
│
├── 🔴 foundation/          基础设施
│   ├── audit_log.py             Append-only JSONL 审计日志
│   ├── llm.py                   LLMProvider Protocol + get_api_key() + ModelConfig
│   └── embedding.py             Embedding 提供者抽象 [v0.2]
│
└── config.py                配置管理 (Pydantic Settings)
```

### 状态图例

| 图标 | 含义 |
|------|------|
| 🔴 | **未实现** — 待 v0.1 实现 |
| 🟡 | **部分实现** — 核心功能就位，待完善 |
| 🟢 | **已完成** — 测试通过，可用 |

### 外部依赖

| 组件 | 依赖 | v0.1 需要 |
|------|------|-----------|
| LLM | OpenAI-compatible API (`OPENAI_API_KEY`) | ✅ 是 |
| SQLite | Python 内置 (`sqlite3`) | ✅ 是 |
| ChromaDB | `chromadb` | ❌ v0.2 |
| KuzuDB | `kuzu` | ❌ v0.2 |
| LangGraph | `langgraph` | ❌ v0.2 |

---

## 代码规模

<!-- SEMI-FIXED: 大规模增删文件后更新 -->

| 维度 | 数据 |
|------|------|
| 源代码 | 0 个 .py（未开始） |
| 测试 | 0 个测试文件, 0 passed |
| Prompt 模板 | 2 个 (FactExtractor + Reconcile) |
| 依赖 | pydantic, openai, typer, rich, pyyaml, structlog |

---

## 当前状态

<!-- SEMI-FIXED: 每完成/启动一个任务时更新 -->

| 任务 | 状态 | 分支 |
|------|------|------|
| Spec 设计 (v2.0 重构) | ✅ 完成 | — |
| 三层 Prompt 体系 | ✅ 完成 | — |
| CEO 架构指南 | ✅ 完成 | — |
| **v0.1 Round 1: Foundation** | 🔴 待开始 | — |
| v0.1 Round 2: Models | 🔴 待开始 | — |
| v0.1 Round 3: Store | 🔴 待开始 | — |
| v0.1 Round 4: Engine | 🔴 待开始 | — |
| v0.1 Round 5: Service | 🔴 待开始 | — |
| v0.1 Round 6: E2E | 🔴 待开始 | — |

## 测试 Baseline

<!-- SEMI-FIXED: 每次 merge 后更新此数字 -->

```
当前 baseline: 0 passed, 135 skipped (全 RED — TDD specs 已冻结)
冻结 tag: tdd-spec-v0.1 @ dc8f30e
运行命令: uv run pytest tests/ -q
```

---

## 版本规划

| 版本 | 代号 | 分数 | 核心交付 | 隐喻完成度 |
|------|------|------|---------|-----------|
| **v0.1** | 🦴 Skeleton | **60** | Pipeline 跑通；全构件就位；两层存储 | 宫殿有骨架，搬运小人能走路 |
| v0.2 | 🧱 Foundation | 80 | 三层存储完整；混合检索；搬运小人自动化+反思 | 有房间有路径，小人能搬运整理 |
| v1.0 | 🏛️ Palace | 95 | Sleep-time 自动化；空间邻近性；监控仪表盘 | 记忆宫殿完全建成，小人高效自治 |

**详细 Spec**: [SPEC v2.0](file:///Users/link/.gemini/antigravity/brain/363f3fd5-6335-403e-8eca-702c7398c766/spec.md)  
**CEO 架构指南**: [ceo_architecture_guide.md](file:///Users/link/.gemini/antigravity/brain/363f3fd5-6335-403e-8eca-702c7398c766/ceo_architecture_guide.md)

---

## 更新触发条件

Orchestrator 在以下事件后必须更新本文档：

- [ ] 完成一个 TDD Round（更新模块状态图标 🔴→🟢）
- [ ] 合并一个 feature 分支到主线
- [ ] 新增或删除 `src/memory_palace/` 下的模块
- [ ] 测试 baseline 数字变化 ≥5
- [ ] 任务状态发生变化（启动/完成/阻塞）
