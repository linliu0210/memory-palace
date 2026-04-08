# Memory Palace — Dispatch Log

> **⚡ LIVE**: 本文档是项目的**唯一状态真相源**。
> 每个任务一个 block，包含 Dev walkthrough + Reviewer findings。
> **最新 block = 当前项目状态**。读最后一个 block 即可了解全局。
>
> **规则**:
> - 只追加新 block，不修改已有 block（除非 Dispatcher 标注合并结果）
> - Dev 写入 `### 🔨 Dev` sub-block
> - Reviewer 写入 `### 🔍 Review` sub-block
> - Dispatcher 写入 `### 📋 Dispatch` sub-block
>
> **格式规范**: 见 `CONVENTIONS.md` 第七节

---

## TASK-001: 项目初始化 ✅

### 📋 Dispatch
- **Round**: N/A (基础设施)
- **Branch**: `main` (文档直接提交)
- **Priority**: P0
- **Dispatched**: 2026-04-04T23:25
- **Status**: ✅ DONE
- **Merged**: 直接提交 main

### 🔨 Dev
- **Agent**: Antigravity (Orchestrator)
- **Completed**: 2026-04-04T23:25
- **Walkthrough**:
  - **实现摘要**: 创建三层 prompt 体系（CONVENTIONS + PROJECT_CONTEXT + PROMPT_TEMPLATE + DISPATCH_LOG）
  - **文件清单**:
    - `NEW` CONVENTIONS.md — Tier 1 静态约束
    - `NEW` PROJECT_CONTEXT.md — Tier 2 项目上下文
    - `NEW` PROMPT_TEMPLATE.md — Tier 3 任务 prompt 模板
    - `NEW` DISPATCH_LOG.md — 本文件
  - **关键设计决策**:
    1. 三层 prompt 体系对标 dream-engine，适配 memory-palace 的 TDD Round 模式
    2. 新增 Round → Prompt 映射速查表简化 dispatch 流程
    3. Protocol-based DI 作为核心架构约束写入 CONVENTIONS
  - **Tests**: N/A (无代码)
  - **已知风险**: 无

### 🔍 Review
_N/A — 纯文档初始化，无需 review_

---

## TASK-002: TDD 规约 + 约束对齐 ✅

### 📋 Dispatch
- **Round**: N/A (测试规约)
- **Branch**: `main` (测试冻结直接提交)
- **Priority**: P0
- **Dispatched**: 2026-04-06T23:30
- **Status**: ✅ DONE
- **Base**: `1161300`
- **Merged**: 直接提交 main

### 🔨 Dev
- **Agent**: Antigravity (Orchestrator)
- **Completed**: 2026-04-06T23:30
- **Walkthrough**:
  - **实现摘要**: 135 个 TDD 测试规约冻结为可执行 spec，创建 MockLLM + 7 个 fixture，Git tag 保护
  - **文件清单**:
    - `MOD` CONVENTIONS.md — 新增 Rule 2.5（TDD 不可变规则）
    - `MOD` PROJECT_CONTEXT.md — 更新 test baseline 至 135 skipped
    - `NEW` tests/conftest.py — MockLLM + 7 个预配置 fixture
    - `NEW` tests/test_foundation/ — 21 tests (audit_log, config, llm)
    - `NEW` tests/test_models/ — 21 tests (memory, audit, curator)
    - `NEW` tests/test_store/ — 23 tests (core_store, recall_store)
    - `NEW` tests/test_engine/ — 24 tests (scoring, fact_extractor, reconcile)
    - `NEW` tests/test_service/ — 27 tests (memory_service, retriever, curator)
    - `NEW` tests/test_e2e/ — 2 tests (full_lifecycle)
    - `NEW` pyproject.toml — 依赖声明 + pytest 配置
    - `NEW` .gitignore
  - **关键设计决策**:
    1. 135 tests 全部 skipped（RED 状态），作为可执行规约冻结
    2. Git tag `tdd-spec-v0.1 @ dc8f30e` 保护测试不可变性
    3. MockLLM 用 Protocol 兼容而非继承（structural subtyping）
  - **Tests**: 0 passed, 135 skipped
  - **已知风险**: 无

### 🔍 Review
_N/A — 纯测试 + 文档，无需 review_

---

## TASK-003: 基础设施补齐 + 导航 ✅

### 📋 Dispatch
- **Round**: N/A (骨架 + 文档)
- **Branch**: `main` (骨架直接提交)
- **Priority**: P0
- **Dispatched**: 2026-04-07T00:35
- **Status**: ✅ DONE
- **Base**: `0d0eb5b`
- **Merged**: 直接提交 main

### 🔨 Dev
- **Agent**: Antigravity (Orchestrator)
- **Completed**: 2026-04-07T00:35
- **Walkthrough**:
  - **实现摘要**: 创建 6 层 × 21 个 placeholder 文件的包骨架，入库 SPEC v2.0，8 个灵感源文档，全局导航入口
  - **文件清单**:
    - `NEW` src/memory_palace/ — 6 层 × 21 个 placeholder 文件
    - `MOD` CONVENTIONS.md — 新增 §8 Known Gotchas（16 条 CRITICAL）
    - `NEW` .env.example — 5 组环境变量模板
    - `NEW` README.md — 架构图 + Quick Start + 文档链接
    - `NEW` examples/ — 8 个灵感源文档（含参考 URL）
    - `NEW` SPEC.md — 完整技术规格 v2.0（835 行）
    - `NEW` NAVIGATION.md — 项目全局导航入口（293 行）
    - `NEW` scripts/ — curator_run.py, memory_inspect.py
  - **关键设计决策**:
    1. SPEC 从 conversation artifact 复制入 repo，成为版本控制下的单一真相源
    2. examples/ 每个文件格式统一：是什么→启发了什么→差异→关键 URL
    3. NAVIGATION.md 包含 9 节完整导航，覆盖项目所有上下文
  - **Tests**: 0 passed, 135 skipped（无回归）
  - **已知风险**: 无

### 🔍 Review
_N/A — 纯文档 + 骨架，无需 review_

---

## TASK-004: Dispatch 体系重设计（Dev/Reviewer 分工 + Block 结构） ✅

### 📋 Dispatch
- **Round**: N/A (基础设施)
- **Branch**: `main` (纯文档直接提交)
- **Priority**: P0
- **Dispatched**: 2026-04-07T13:55
- **Status**: ✅ DONE
- **Base**: `095b5c1`
- **Merged**: 直接提交 main @ `2d2a2b0`

### 🔨 Dev
- **Agent**: Antigravity (Dispatcher)
- **Completed**: 2026-04-07T14:05
- **Walkthrough**:
  - **实现摘要**: 重设计整个 Dispatch 体系——DISPATCH_LOG 从扁平 entry 改为 task-block 结构（📋/🔨/🔍 三个 sub-block），PROMPT_TEMPLATE 拆分为 Dev (Claude Code) 和 Reviewer (Codex) 两套模板，CONVENTIONS 更新 §七 协议，DISPATCHER_PROMPT 升级 v1.1
  - **文件清单**:
    - `MOD` DISPATCH_LOG.md — 全量重写为 block 结构，迁移 3 条历史 entry
    - `MOD` PROMPT_TEMPLATE.md — 全量重写：§A Dev / §B Reviewer / §C Dispatcher / §D-H 辅助
    - `MOD` CONVENTIONS.md — §七 更新为 block 格式 + 读写规则 + walkthrough 强制
    - `MOD` DISPATCHER_PROMPT.md — v1.1: 添加 Codex 角色、9 步生命周期、prompt 引用
  - **关键设计决策**:
    1. 不引入 KANBAN.md — DISPATCH_LOG 最新 block = 当前项目状态，单一真相源
    2. 三角色分工：Dispatcher (Antigravity) / Dev (Claude Code) / Reviewer (Codex)
    3. Walkthrough 强制：Dev 5 项必填 + Reviewer findings 结构化记录
  - **Tests**: N/A (无代码)
  - **已知风险**: 并行 agent 同时写 DISPATCH_LOG 可能产生 git 冲突，需 Dispatcher 手动 resolve

### 🔍 Review
_N/A — 纯文档重设计，无需 review_

---

## TASK-005: [Round 1] Foundation — AuditLog + Config + LLMProvider ✅

### 📋 Dispatch
- **Round**: 1
- **Branch**: `feat/foundation-round1`
- **Priority**: P0
- **Dispatched**: 2026-04-07T14:14
- **Status**: ✅ DONE
- **Base**: main @ `7ee32f2`
- **Merged**: main @ `daa06fb`
- **Parallel Protected**: 无

### 🔨 Dev
- **Agent**: Claude Code (Opus 4.6)
- **Completed**: 2026-04-07T14:45
- **Walkthrough**:
  - **实现摘要**: 实现 Round 1 Foundation 三组件——AuditLog (append-only JSONL)、LLMProvider Protocol + ModelConfig + get_api_key、Config (Pydantic Settings + YAML)。严格遵循 TDD Red-Green-Refactor，每个组件独立 commit。
  - **文件清单**:
    - `MOD` src/memory_palace/foundation/audit_log.py — AuditAction(StrEnum) + AuditEntry(BaseModel) + AuditLog(append/read with JSONL)
    - `MOD` src/memory_palace/foundation/llm.py — @runtime_checkable LLMProvider Protocol + ModelConfig + ENV_KEY_MAP + get_api_key()
    - `MOD` src/memory_palace/config.py — Config(BaseSettings) with 7 nested sub-models, MP_ env prefix, from_yaml() with custom PydanticBaseSettingsSource
    - `MOD` src/memory_palace/foundation/__init__.py — 导出所有公共 API
    - `MOD` tests/test_foundation/test_audit_log.py — 移除 skip，填充 8 个测试体
    - `MOD` tests/test_foundation/test_config.py — 移除 skip，填充 11 个测试体，key resolution 委托 get_api_key
    - `MOD` tests/test_foundation/test_llm.py — 移除 skip，填充 10 个测试体，内联 _MockLLM 绕过 conftest 不可 import 问题
  - **关键设计决策**:
    1. `from_yaml()` 使用 `settings_customise_sources` 注入 `_YamlSettingsSource`，确保 env > YAML > defaults 优先级（直接传 kwargs 会让 YAML 覆盖 env vars）
    2. `AuditAction` 用 `StrEnum` 替代 `(str, Enum)` 双继承，满足 ruff UP042
    3. test_llm.py 中内联 `_MockLLM` dataclass 而非 import conftest（pytest 的 conftest 不可作为 module 导入）
  - **Tests**: 0→29 passed, 135→106 skipped, 0 failed
  - **已知风险**:
    - `tests/conftest.py` 存在 ruff I001 (import sort) 预存问题，因 immutable 规则无法修复
    - Round 2 的 `models/audit.py` 将复用 AuditEntry/AuditAction——届时需从 `foundation/audit_log.py` refactor 到 models 层
  - **Fix Round (Codex Review)**:
    - Finding 1 [HIGH]: `from_yaml()` 添加 `memory_palace:` 根键解包，兼容有/无根键两种格式
    - Finding 2 [MEDIUM]: 更新 2 个 YAML 测试 fixture 使用 SPEC §8.2 根键格式
    - Commit: `fix(config): unwrap memory_palace root key in from_yaml (SPEC §8.2)`
    - Tests: 29 passed, 106 skipped (unchanged)

### 🔍 Review
- **Agent**: Codex
- **Reviewed**: 2026-04-07T19:51
- **Verdict**: ✅ APPROVED
- **Findings**:
  1. [resolved] `fix(config): unwrap memory_palace root key in from_yaml (SPEC §8.2)` 已修复 `Config.from_yaml()` 对 SPEC §8.2 根键格式的不兼容；黑盒验证显示 `memory_palace:` 包裹格式与 env > YAML > defaults 优先级均按契约工作。
  2. [resolved] `tests/test_foundation/test_config.py` 已将 YAML fixture 更新为 SPEC §8.2 的 `memory_palace:` 根键格式，补上了此前缺失的回归覆盖。
- **Test Verification**: `uv run pytest tests/ -q` → 29 passed, 106 skipped
- **TDD Integrity**: `git diff tdd-spec-v0.1 -- tests/` → 非 clean；`tests/test_foundation/test_audit_log.py`、`tests/test_foundation/test_config.py`、`tests/test_foundation/test_llm.py` 仅移除 `pytest.skip()` 并填充测试体；`tests/conftest.py`、`tests/test_service/test_curator.py`、`tests/test_service/test_memory_service.py` 仅有 ruff auto-format（行折叠/空行），skip 与断言语义未变

---

## TASK-006: [Round 2] Models — MemoryItem + AuditEntry + CuratorReport ✅

### 📋 Dispatch
- **Round**: 2
- **Branch**: `feat/models-round2`
- **Priority**: P0
- **Dispatched**: 2026-04-07T20:25
- **Status**: ✅ DONE
- **Base**: main @ `daa06fb`
- **Parallel Protected**: 无

### 🔨 Dev
- **Agent**: Claude Code (Opus 4.6)
- **Completed**: 2026-04-07T20:41
- **Walkthrough**:
  - **实现摘要**: 实现 Round 2 全部数据模型——MemoryItem (20 字段 + content 非空校验) + 3 个 StrEnum (MemoryStatus/Tier/Type) + Room，CuratorReport (6 指标 + 2 健康分)，audit.py 从 foundation 层 re-export AuditAction/AuditEntry。严格 TDD，28 个测试全绿。
  - **文件清单**:
    - `MOD` src/memory_palace/models/memory.py — MemoryItem + MemoryStatus + MemoryTier + MemoryType + Room 全量实现
    - `MOD` src/memory_palace/models/audit.py — Re-export AuditAction/AuditEntry from foundation.audit_log
    - `MOD` src/memory_palace/models/curator.py — CuratorReport (run_id + 6 counters + 2 health scores)
    - `MOD` src/memory_palace/models/__init__.py — 导出 8 个公共 API 符号
    - `MOD` tests/test_models/test_memory.py — 移除 skip，填充 18 个测试体
    - `MOD` tests/test_models/test_audit.py — 移除 skip，填充 5 个测试体
    - `MOD` tests/test_models/test_curator.py — 移除 skip，填充 5 个测试体
  - **关键设计决策**:
    1. Enums 用 `StrEnum` 替代 `(str, Enum)` 双继承——与 Round 1 foundation/audit_log.py 的 AuditAction 保持一致，满足 ruff UP042
    2. `models/audit.py` 只做 re-export，AuditEntry/AuditAction 的唯一定义在 `foundation/audit_log.py`——避免重复定义，保持单一真相源
    3. content 非空校验用 `@field_validator` 实现（捕获空字符串和纯空白），而非 `min_length=1`（后者不捕获 whitespace-only）
  - **Tests**: 29→57 passed, 106→78 skipped, 0 failed
  - **已知风险**: 无。Round 3 Store 层将依赖这些 models，接口已稳定

### 🔍 Review
- **Agent**: Codex
- **Reviewed**: 2026-04-08T00:13
- **Verdict**: ✅ APPROVED
- **Findings**:
  1. [severity: LOW] — 分支实际多出一条早于本次审查的 `docs(dispatch): fill TASK-006 Review — APPROVED, 57 passed 78 skipped` 提交，与 dispatch 中 "Commits: 3" 不一致；这不影响模型实现本身，但原 Review 记录不应视为有效，本次已按真实验证结果覆盖。
- **Test Verification**: `uv run pytest tests/ -q` → 57 passed, 78 skipped
- **TDD Integrity**: `git diff tdd-spec-v0.1 -- tests/test_models/` → 仅见 `pytest.skip()` 移除、必要 imports/helper 与测试体填充；未见断言语义放宽。`tests/test_store/`、`tests/test_engine/`、`tests/test_service/`、`tests/test_e2e/` → 无 diff
- **SPEC Alignment**: `MemoryItem` 20 fields、`AuditEntry` 5 fields + `AuditAction` 7 values、`CuratorReport` 14 fields、`Room` 5 fields 全部对齐；`AuditAction is foundation.AuditAction` 与 `AuditEntry is foundation.AuditEntry` 均为 `True`
- **Architecture**: `uv run ruff check src/memory_palace/models/` → 0 errors；`git diff main..feat/models-round2 -- src/memory_palace/foundation/` → empty；`models/` 仅依赖 `foundation`

---

## TASK-007: [Round 3] Store — CoreStore + RecallStore ✅

### 📋 Dispatch
- **Round**: 3
- **Branch**: `feat/store-round3`
- **Priority**: P0
- **Dispatched**: 2026-04-08T00:16
- **Status**: ✅ DONE
- **Base**: main @ latest merge
- **Parallel Protected**: 无

### 🔨 Dev
- **Agent**: Claude Code (Opus 4.6)
- **Completed**: 2026-04-08T01:15
- **Walkthrough**:
  - **实现摘要**: 实现 Round 3 全部存储层——CoreStore (JSON 平文件 + 原子写入 + 2KB 预算) + RecallStore (SQLite + FTS5 + CJK 预分词)。22 个冻结测试全绿。
  - **文件清单**:
    - `MOD` src/memory_palace/store/core_store.py — CoreStore: save/load/delete/list_blocks/budget_check/get_all_text，原子写入 (tmp+os.rename)
    - `MOD` src/memory_palace/store/recall_store.py — RecallStore: insert/search/get/get_recent/count/update_status/touch，FTS5 独立表 + CJK 预分词
    - `MOD` src/memory_palace/store/base.py — 注释说明 v0.1 不抽取 Protocol（两 store 接口差异大）
    - `MOD` src/memory_palace/store/__init__.py — 导出 CoreStore, RecallStore
    - `MOD` tests/test_store/test_core_store.py — 移除 9 个 pytest.skip() + 填充测试体
    - `MOD` tests/test_store/test_recall_store.py — 移除 13 个 pytest.skip() + 填充测试体
  - **关键设计决策**:
    1. FTS5 CJK 预分词：unicode61 将连续中文字符合并为单个 token，导致子串搜索失败。解决方案是 `_tokenize_cjk()` 在 CJK 字符间插入空格，确保逐字匹配。FTS5 表采用独立模式（无 content sync），手动管理 rowid 对齐。
    2. CoreStore 原子写入使用 `tempfile.mkstemp + os.replace`，异常时清理临时文件，防止断电数据损坏。
    3. `save()` 方法先序列化为 JSON 再写文件；`load()` 使用 `model_validate()` 从 dict 反序列化（非 `model_validate_json()`，因后者只接受 str）。
  - **Tests**: 57→79 passed, 78→56 skipped, 0 failed
  - **已知风险**: CJK 搜索是逐字匹配（无分词器），长句可能产生假阳性；v0.2 引入向量检索后可改善

### 🔍 Review
- **Agent**: Codex
- **Reviewed**: 2026-04-08T01:10 (R1), 2026-04-08T09:00 (Re-review)
- **Verdict**: ✅ APPROVED (after fix in `5768a7e`)
- **R1 Findings** (both fixed):
  1. [HIGH] RecallStore query 未过滤非 active 记录 → Fixed: WHERE status = 'active'
  2. [MEDIUM] CoreStore.delete() 创建 ghost block → Fixed: no-op when block missing
- **Re-review**: 79 passed, 56 skipped; fix verified
- **TDD Integrity**: 测试结构未变

---

## TASK-008: [Round 4] Engine — FactExtractor + ScoringEngine + ReconcileEngine 🟡

### 📋 Dispatch
- **Round**: 4
- **Branch**: `feat/engine-round4`
- **Priority**: P0
- **Dispatched**: 2026-04-08T09:05
- **Status**: 🟡 IN_PROGRESS
- **Base**: main @ latest merge
- **Parallel Protected**: 无

### 🔨 Dev
_(待 Dev Agent 填写)_

### 🔍 Review
_(待 Codex 填写)_

---
