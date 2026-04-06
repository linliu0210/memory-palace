# Memory Palace — Dispatch Log

> 每次任务完成后在末尾追加 entry。格式见 `CONVENTIONS.md` 第七节。
> **只追加，不修改已有 entry。**

---

## [2026-04-04T23:25] — 项目初始化 ✅
- **Agent**: Antigravity (Orchestrator)
- **Status**: DONE
- **Base**: N/A (首次)
- **Files changed**:
  - NEW `CONVENTIONS.md` — Tier 1 静态约束
  - NEW `PROJECT_CONTEXT.md` — Tier 2 项目上下文
  - NEW `PROMPT_TEMPLATE.md` — Tier 3 任务 prompt 模板
  - NEW `DISPATCH_LOG.md` — 本文件
- **Key decisions**:
  1. 三层 prompt 体系对标 dream-engine，适配 memory-palace 的 TDD Round 模式
  2. 新增 Round → Prompt 映射速查表简化 dispatch 流程
  3. Protocol-based DI 作为核心架构约束写入 CONVENTIONS
- **Issues found**: 无
- **Tests**: N/A (无代码)
- **Merge note**: 无风险，纯文档初始化

## [2026-04-06T23:30] — TDD 规约 + 约束对齐 ✅
- **Agent**: Antigravity (Orchestrator)
- **Status**: DONE
- **Base**: `1161300`
- **Files changed**:
  - MOD `CONVENTIONS.md` — 新增 Rule 2.5（TDD 不可变规则）
  - MOD `PROJECT_CONTEXT.md` — 更新 test baseline 至 135 skipped
  - NEW `tests/conftest.py` — MockLLM + 7 个预配置 fixture
  - NEW `tests/test_foundation/` — 21 tests (audit_log, config, llm)
  - NEW `tests/test_models/` — 21 tests (memory, audit, curator)
  - NEW `tests/test_store/` — 23 tests (core_store, recall_store)
  - NEW `tests/test_engine/` — 24 tests (scoring, fact_extractor, reconcile)
  - NEW `tests/test_service/` — 27 tests (memory_service, retriever, curator)
  - NEW `tests/test_e2e/` — 2 tests (full_lifecycle)
  - NEW `pyproject.toml` — 依赖声明 + pytest 配置
  - NEW `.gitignore`
- **Key decisions**:
  1. 135 tests 全部 skipped（RED 状态），作为可执行规约冻结
  2. Git tag `tdd-spec-v0.1` 保护测试不可变性
  3. MockLLM 用 Protocol 兼容而非继承
- **Issues found**: 无
- **Tests**: 0 passed, 135 skipped
- **Merge note**: 无风险，纯测试 + 文档

## [2026-04-07T00:35] — 基础设施补齐 + 导航 ✅
- **Agent**: Antigravity (Orchestrator)
- **Status**: DONE
- **Base**: `0d0eb5b`
- **Files changed**:
  - NEW `src/memory_palace/` — 6 层 × 21 个 placeholder 文件
  - MOD `CONVENTIONS.md` — 新增 §8 Known Gotchas（16 条 CRITICAL）
  - NEW `.env.example` — 5 组环境变量模板
  - NEW `README.md` — 架构图 + Quick Start + 文档链接
  - NEW `examples/` — 8 个灵感源文档（含参考 URL）
  - NEW `SPEC.md` — 完整技术规格 v2.0（835 行，从 artifact 入库）
  - NEW `NAVIGATION.md` — 项目全局导航入口（293 行）
  - NEW `scripts/` — curator_run.py, memory_inspect.py
- **Key decisions**:
  1. SPEC 从 conversation artifact 复制入 repo，成为版本控制下的单一真相源
  2. examples/ 每个文件格式统一：是什么→启发了什么→差异→关键 URL
  3. NAVIGATION.md 包含 9 节完整导航，覆盖项目所有上下文
- **Issues found**: 无
- **Tests**: 0 passed, 135 skipped（无回归）
- **Merge note**: 无风险，纯文档 + 骨架
