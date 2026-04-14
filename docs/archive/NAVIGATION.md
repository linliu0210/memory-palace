# 🏛️ Memory Palace — 项目导航

> **用途**: 任何 Agent 或开发者首次接触本项目时的 **唯一入口**。  
> **更新时间**: 2026-04-07  
> **项目状态**: 全 RED — TDD specs 已冻结，等待 Round 1 实施

---

## 一、推荐阅读顺序

新 Agent 首次接触项目，按以下顺序阅读：

```
1. 本文件（导航全貌）
2. SPEC.md §0-§1（理念 + 系统边界 — 5 min）
3. CONVENTIONS.md §1-§3（TDD 纪律 + 分层规则 — 5 min）
4. PROJECT_CONTEXT.md（当前状态 + 测试 baseline — 3 min）
5. CONVENTIONS.md §8（Known Gotchas — 2 min）
6. 对应 Round 的灵感源文档（examples/ — 按需）
```

---

## 二、仓库全局结构

```
memory-palace/
│
├── 📋 治理文档（Governance）
│   ├── SPEC.md                    ← 技术规格书 v2.0（835 行）
│   ├── CONVENTIONS.md             ← 代码约定 + TDD 纪律 + Gotchas
│   ├── PROJECT_CONTEXT.md         ← 项目全貌 + 模块状态 + baseline
│   ├── PROMPT_TEMPLATE.md         ← Subagent 任务 prompt 模板
│   ├── DISPATCH_LOG.md            ← 多 Agent 任务日志（只追加）
│   └── README.md                  ← 开发者级项目简介
│
├── 💡 灵感来源（Examples）
│   └── examples/                  ← 8 个灵感源文档（→ 详见第四节）
│
├── 📦 源码骨架（Source）
│   └── src/memory_palace/         ← 五层架构 placeholder（→ 详见第五节）
│
├── 🧪 测试规约（Tests）
│   └── tests/                     ← 135 tests × 6 Rounds（→ 详见第六节）
│
├── 🔧 脚本（Scripts）
│   └── scripts/                   ← curator_run.py, memory_inspect.py
│
└── ⚙️ 基建（Infrastructure）
    ├── pyproject.toml             ← 依赖声明 + pytest 配置
    ├── .env.example               ← 环境变量模板
    └── .gitignore                 ← Python 标准排除
```

---

## 三、治理文档详解

### 3.1 [SPEC.md](SPEC.md) — 技术规格书（835 行）

> **角色**: 接口的**唯一真相来源**。所有数据模型、API 签名、Prompt 模板以此为准。

| 章节 | 内容 | 关键信息 |
|------|------|---------|
| §0 | 项目理念 | 核心公式 + 设计哲学 + 版本迭代策略 |
| §1 | 系统边界 | 是什么 / 不是什么 |
| §2 | 数据模型 | MemoryItem, AuditEntry, CuratorReport, Room |
| §3 | 五层架构 | 分层图 + 目录结构 |
| §4 | 核心逻辑域 | 衰减公式、四因子权重、推迟清单（11 项） |
| §5 | 接口契约 | 每层的 Protocol / API 签名 |
| §6 | Prompt 模板 | FactExtractor / Reconcile 的 LLM prompt |
| §7 | TDD 路线图 | 6 Round 实施计划 + MockLLM 策略 |
| §8 | 配置管理 | pi-mono 模式 + .env 映射 |

---

### 3.2 [CONVENTIONS.md](CONVENTIONS.md) — 代码约定（317 行）

> **角色**: Agent 的 **行为准则**。实施代码时的红线和纪律。

| 章节 | 内容 | 关键规则 |
|------|------|---------|
| §1 | Tech Stack | Python 3.11+, Pydantic v2, structlog, SQLite |
| §2 | 分层依赖 | 单向依赖：低层 → 高层不可逆引用 |
| §2.5 | **TDD 不可变规则** | 测试 = 可执行规约，断言语义在 GREEN 阶段不可修改 |
| §3 | 文件组织 | 单类/单文件、Google Docstring |
| §4 | 错误处理 | Validation → Graceful → Fatal 三层模式 |
| §5 | Git 规范 | Conventional Commits + Scope 枚举 |
| §6 | 验证命令 | `pytest + ruff` 双重验证 |
| §7 | Dispatch 协议 | 多 Agent 任务日志格式 |
| **§8** | **Known Gotchas** | SQLite FTS5、Pydantic v2、structlog 等陷阱 |

---

### 3.3 [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) — 项目全貌（181 行）

> **角色**: 项目的 **实时仪表盘**。每完成一个 Round 必须更新。

| 区域 | 内容 | 更新频率 |
|------|------|---------|
| 项目定位 | 一句话定位 + 边界 | STATIC |
| Spec 链接 | 指向 SPEC v2.0 | STATIC |
| 版本规划 | v0.1 → v0.2 → v1.0 | STATIC |
| 模块拓扑 | 按层列出所有模块 + 🔴🟡🟢状态 | **SEMI-FIXED** |
| 测试 Baseline | 当前 0 passed, 135 skipped | **SEMI-FIXED** |
| 代码规模 | 总行数、覆盖率 | **SEMI-FIXED** |
| 任务状态 | 当前 Round 进展 | **SEMI-FIXED** |

---

### 3.4 [PROMPT_TEMPLATE.md](PROMPT_TEMPLATE.md) — Subagent Prompt 模板

> **角色**: Orchestrator 发任务给 Subagent 的**标准格式**。

包含: 变量清单、Round→Prompt 映射速查表、Agent 分配规则、Orchestrator 自检清单。

---

### 3.5 [DISPATCH_LOG.md](DISPATCH_LOG.md) — 任务日志

> **角色**: 历史执行记录。**只追加不修改**。

---

### 3.6 [.env.example](.env.example) — 环境变量模板

> **角色**: 告诉 Agent 需要配置什么。对应 SPEC §8。

包含: LLM Provider / Storage / Curator / Embedding / Debug 五组配置。

---

## 四、灵感来源详解（examples/）

> 每个文件格式: **是什么 → 启发了什么 → 我们的差异 → 关键参考链接**

| 文件 | 灵感源 | 启发的组件 | 关键 URL |
|------|--------|-----------|---------|
| [memgpt.md](examples/memgpt.md) | MemGPT / Letta | 五层架构 + 三层存储 | [letta-ai/letta](https://github.com/letta-ai/letta) |
| [mem0.md](examples/mem0.md) | Mem0 (YC) | FactExtractor + Reconcile + CRUD | [mem0ai/mem0](https://github.com/mem0ai/mem0) |
| [generative_agents.md](examples/generative_agents.md) | Stanford Generative Agents | ScoringEngine 三因子 | [arXiv:2304.03442](https://arxiv.org/abs/2304.03442) |
| [karpathy_llm_wiki.md](examples/karpathy_llm_wiki.md) | Karpathy LLM Wiki | Core 活 Wiki + Lint 操作 | [YouTube](https://www.youtube.com/watch?v=FJkLJvRGNyg) |
| [auto_dream.md](examples/auto_dream.md) | Claude Code Auto-Dream | Curator "梦境"机制 | [Anthropic Docs](https://docs.anthropic.com/en/docs/claude-code/memory) |
| [openclaw.md](examples/openclaw.md) | OpenClaw | Reflection + Health Score | [AiAutoTool/OpenClaw](https://github.com/AiAutoTool/OpenClaw) |
| [dreamengine.md](examples/dreamengine.md) | DreamEngine (姊妹项目) | LLMProvider Protocol | [本地: ../dream-engine/](../dream-engine/) |
| [method_of_loci.md](examples/method_of_loci.md) | 位点记忆法 (认知科学) | 第四因子 Proximity + Room | [Wikipedia](https://en.wikipedia.org/wiki/Method_of_loci) |

---

## 五、源码骨架详解（src/memory_palace/）

> 当前状态: 全部 placeholder，等待 Round 1 开始填充。

```
src/memory_palace/
├── __init__.py              ← 根包 (version=0.1.0)
├── config.py                ← 配置管理 [Round 1]
│
├── 🔧 foundation/           ← 1F 水电煤 [Round 1]
│   ├── audit_log.py         ← Append-only JSONL 审计
│   ├── llm.py               ← LLMProvider Protocol
│   └── embedding.py         ← Embedding [v0.2]
│
├── 📐 models/               ← 2F 数据模型 [Round 2]
│   ├── memory.py            ← MemoryItem, MemoryStatus, MemoryTier, Room
│   ├── audit.py             ← AuditEntry
│   └── curator.py           ← CuratorReport
│
├── 🗄️ store/                ← 2F 存储层 [Round 3]
│   ├── base.py              ← AbstractStore Protocol
│   ├── core_store.py        ← Core: JSON flat file (≤200 条)
│   ├── recall_store.py      ← Recall: SQLite + FTS5
│   └── archival_store.py    ← Archival [v0.2]
│
├── ⚙️ engine/               ← 3F 引擎层 [Round 4]
│   ├── fact_extractor.py    ← LLM 原子事实提取
│   ├── scoring.py           ← 三/四因子评分 (纯函数)
│   ├── reconcile.py         ← LLM 冲突调和
│   └── reflection.py        ← Reflection [v0.2]
│
├── 🧑‍💼 service/             ← 4F 管家层 [Round 5]
│   ├── memory_service.py    ← 记忆管家 (save/search/update/forget)
│   ├── retriever.py         ← 搜索管家 (多源检索+评分)
│   └── curator.py           ← 搬运小人 (7 步巡检)
│
└── 🏢 integration/          ← 5F 接待层 [Round 6]
    ├── tools.py             ← LLM Tool 定义
    └── cli.py               ← CLI 命令行
```

### 依赖方向（严格单向 ↓）

```
Integration ──→ Service ──→ Engine ──→ Store ──→ Foundation
     5F            4F          3F        2F         1F
                                         ↑
                                       Models
```

---

## 六、测试规约详解（tests/）

> **冻结标签**: `tdd-spec-v0.1 @ dc8f30e`  
> **不可变性检查**: `git diff tdd-spec-v0.1 -- tests/`

| Round | 目录 | 测试文件 | Tests | 对应 src |
|-------|------|---------|-------|---------|
| 1 | `test_foundation/` | test_audit_log, test_config, test_llm | 21 | foundation/ + config.py |
| 2 | `test_models/` | test_memory, test_audit, test_curator | 21 | models/ |
| 3 | `test_store/` | test_core_store, test_recall_store | 23 | store/ |
| 4 | `test_engine/` | test_scoring, test_fact_extractor, test_reconcile | 24 | engine/ |
| 5 | `test_service/` | test_memory_service, test_retriever, test_curator | 27 | service/ |
| 6 | `test_e2e/` | test_full_lifecycle | 2 | integration/ |
| | | **Total** | **135** | |

### 共享 Fixtures（conftest.py）

| Fixture | 用途 |
|---------|------|
| `MockLLM` | 确定性 LLM 替身（Protocol 兼容） |
| `mock_llm_extract_*` | FactExtractor 场景预配置（3 个） |
| `mock_llm_reconcile_*` | ReconcileEngine 场景预配置（3 个） |
| `mock_llm_malformed` | Malformed JSON 返回测试 |
| `tmp_data_dir` | 临时文件系统 fixture |

---

## 七、Conversation Artifacts（参考文档）

> 以下文档在 Antigravity brain 目录，不在 repo 内。供回溯设计决策时参考。

| Artifact | 内容 | 路径 |
|----------|------|------|
| CEO 架构指南 | 面向决策者的非技术解读 | [ceo_architecture_guide.md](file:///Users/link/.gemini/antigravity/brain/363f3fd5-6335-403e-8eca-702c7398c766/ceo_architecture_guide.md) |
| CTO 直白版 | 技术总监级务实评审 | [cto_plain_talk.md](file:///Users/link/.gemini/antigravity/brain/363f3fd5-6335-403e-8eca-702c7398c766/cto_plain_talk.md) |
| CTO 就绪评审 | 技术准备度打分 | [cto_readiness_review.md](file:///Users/link/.gemini/antigravity/brain/363f3fd5-6335-403e-8eca-702c7398c766/cto_readiness_review.md) |
| 理念更新 v1.1 | Karpathy+AutoDream 融合 | [ideation_update_v1.1.md](file:///Users/link/.gemini/antigravity/brain/363f3fd5-6335-403e-8eca-702c7398c766/ideation_update_v1.1.md) |
| 调研报告 | 全领域调研 (Mem0/MemGPT/...) | [memory_palace_agent_research.md](file:///Users/link/.gemini/antigravity/brain/363f3fd5-6335-403e-8eca-702c7398c766/memory_palace_agent_research.md) |
| Gap Analysis | PRP 对标审计 | [gap_analysis.md](file:///Users/link/.gemini/antigravity/brain/363f3fd5-6335-403e-8eca-702c7398c766/gap_analysis.md) |
| SPEC v1 归档 | 旧版 spec（已替换） | [spec_v1_archived.md](file:///Users/link/.gemini/antigravity/brain/363f3fd5-6335-403e-8eca-702c7398c766/spec_v1_archived.md) |

---

## 八、快速命令参考

```bash
# 运行全部测试
uv run pytest tests/ -q

# 运行单个 Round 的测试
uv run pytest tests/test_foundation/ -v     # Round 1
uv run pytest tests/test_models/ -v         # Round 2
uv run pytest tests/test_store/ -v          # Round 3
uv run pytest tests/test_engine/ -v         # Round 4
uv run pytest tests/test_service/ -v        # Round 5
uv run pytest tests/test_e2e/ -v            # Round 6

# Lint 检查
uv run ruff check src/ tests/

# 验证包可导入
uv run python -c "import memory_palace; print(memory_palace.__version__)"

# 检测测试规约是否被篡改
git diff tdd-spec-v0.1 -- tests/

# 查看 git 历史
git log --oneline
```

---

## 九、下一步: Round 1 实施清单

```bash
# 1. 创建实施分支
git checkout -b feat/foundation-round1

# 2. 解锁 Round 1 测试 (移除 pytest.skip)
# 文件: tests/test_foundation/test_audit_log.py
#       tests/test_foundation/test_config.py
#       tests/test_foundation/test_llm.py

# 3. 实现目标
# src/memory_palace/foundation/audit_log.py
# src/memory_palace/config.py
# src/memory_palace/foundation/llm.py

# 4. 验证
uv run pytest tests/test_foundation/ -v   # 目标: 21 passed
uv run ruff check src/memory_palace/foundation/ src/memory_palace/config.py
```
