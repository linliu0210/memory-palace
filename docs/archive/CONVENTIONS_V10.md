# Memory Palace v1.0 — Conventions & Constraints (for Subagents)

> **读者**: 执行 v1.0 开发的 AI Subagent  
> **目的**: 不可违反的规则和约束。违反任何一条即视为 Round 失败  
> **前置**: 先读 PROJECT_CONTEXT_V10.md 了解架构

---

## 1. TDD 纪律 (Iron Law)

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST.
```

### 每个 Round 的执行流程

1. **先写测试** → 运行 → 看到 RED (FAILED)
2. **写最小实现** → 运行 → 看到 GREEN (PASSED)
3. **重构** → 运行 → 保持 GREEN
4. **Round 结束**: `pytest tests/ -q` 全绿才能 commit

### 测试文件命名

```
tests/test_{layer}/test_{module}.py

示例:
  tests/test_engine/test_ebbinghaus.py
  tests/test_service/test_scheduler.py
  tests/test_integration/test_mcp_server.py
```

### Mock 策略

- **LLM**: 永远用 `MockLLM` (见 conftest.py)，不调用真实 API
- **文件系统**: 永远用 `tmp_path` / `tmp_data_dir` fixture
- **时间**: 用 `datetime` 参数注入或 freezegun，不 mock `datetime.now()` 全局
- **Embedding**: 用 `MockEmbedding` (见 conftest.py)

## 2. 架构边界 (不可违反)

### 依赖方向

```
Integration → Service → Engine → Store → Foundation → Models
              ↑ 只能向下引用，不能反向或跨层
```

**禁止**:
- Engine import Service
- Store import Engine
- Foundation import 任何上层
- 同层循环依赖 (如 Service A import Service B, B import A)

**例外**: `curator.py` 通过 lazy import 解决与 `memory_service.py` 的循环 (已有先例，不要新增)

### 新文件必须声明层级

```python
"""ModuleName — 一句话描述.

Ref: SPEC_V10 §X.X (如有)
"""
```

## 3. 依赖管理

### v1.0 允许新增的依赖

| 依赖 | 用途 | Round |
|------|------|-------|
| `fastmcp>=2.0,<3.0` | MCP Server | R18 |

### 禁止引入的依赖

- APScheduler (asyncio 原生替代)
- LangGraph / langchain-* (v0.2 已拒绝)
- KuzuDB (Phase D 触发条件未满足前不引入)
- 任何未在上表列出的运行时依赖

**检查方法**: 引入新依赖前执行 `pip install --dry-run <pkg>` 查看传递依赖数量。超过 10 个需要报告 Dispatcher。

## 4. Git 规范

### 分支

```
每个 Phase 一个分支:
  feat/v1.0-phase-a   (R14-R17)
  feat/v1.0-phase-b   (R18-R20)
  feat/v1.0-phase-c   (R21-R23)
  feat/v1.0-phase-d   (R24-R25, optional)
```

### Commit

```
格式: <type>(R<round>): <description>

示例:
  feat(R14): SleepTimeScheduler with asyncio background loop
  test(R15): Ebbinghaus decay curve unit tests
  fix(R16): HeartbeatController max duration enforcement
  docs(R17): Phase A integration summary

type: feat | test | fix | refactor | docs | chore
```

每个 Round 结束时至少一个 commit，全绿后才能 commit。

## 5. 代码风格

### Ruff 配置 (已在 pyproject.toml)

```toml
[tool.ruff]
target-version = "py311"
line-length = 99

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP"]
```

### 命名

- 类: `PascalCase`
- 函数/方法: `snake_case`
- 常量: `UPPER_SNAKE_CASE`
- 私有: `_leading_underscore`
- 文件: `snake_case.py`

### Docstring

```python
def my_function(param: str) -> bool:
    """一句话描述.

    更详细的说明 (可选).

    Args:
        param: 参数说明.

    Returns:
        返回值说明.
    """
```

### Type Hints

- 所有公开函数必须有完整类型标注
- 使用 `from __future__ import annotations`
- 用 `TYPE_CHECKING` 避免循环导入

## 6. 异步规范

### 原则

- I/O 操作 (LLM, embedding, HTTP) 用 `async def`
- 纯计算函数 (scoring, health) 用普通 `def`
- 测试中用 `pytest.mark.asyncio` (已全局配置 `asyncio_mode = "auto"`)

### Sleep-time Scheduler 特殊规则

- 后台任务必须用 `asyncio.Task` + `asyncio.Event`
- 必须实现 `stop()` 方法做优雅关闭
- 必须有超时保护防止挂起

## 7. 错误处理

- 自定义异常放 `models/errors.py`
- 操作失败返回 `None` 或 raise，不 return `False` 表示失败
- MCP Tool 异常: 全部 catch，返回 `{"success": False, "error": "...", "code": "..."}`
- Curator 安全限制: raise `CuratorSafetyError` → 跳到 REPORT 阶段

## 8. 配置新增规范

新增配置项必须:
1. 在 `config.py` 中定义 Pydantic model
2. 有合理默认值 (系统无 YAML 也能跑)
3. 支持 `MP_` 环境变量覆盖
4. 在 `memory_palace.yaml` 示例中记录

## 9. v1.0 Round 清单概览

```
Phase A: 自动化
  R14: SleepTimeScheduler (asyncio 后台调度)
  R15: Ebbinghaus 衰减引擎 (纯函数)
  R16: HeartbeatController (Curator 安全守卫)
  R17: Phase A Integration + E2E + CLI schedule 命令

Phase B: MCP 集成
  R18: MCP Server 基础 (FastMCP, 12 tools + 6 resources)
  R19: 并发安全 + Error Handling
  R20: Phase B Integration + CLI serve 命令 + CI

Phase C: 增强
  R21: Batch Import/Export
  R22: Multi-persona
  R23: 监控指标 + Core 预算增强

Phase D: 深水区
  R24: KuzuDB 图存储 (条件触发)
  R25: Full Ingest Pipeline (条件触发)
```

## 10. Round 完成标准

一个 Round 完成当且仅当:

- [ ] 所有测试通过 (`pytest tests/ -q`)
- [ ] 无 ruff 警告 (`ruff check`)
- [ ] Git commit 完成 (conventional commit format)
- [ ] 新文件有 docstring 和层级声明
- [ ] 无新的技术债 (或已记录到 TODO)
