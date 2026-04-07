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
