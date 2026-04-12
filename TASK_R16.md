# Round 16 — HeartbeatController

> **Round**: 16 / Phase A  
> **分支**: `feat/v1.0-phase-a`  
> **前置**: R15 完成 (Ebbinghaus)  
> **交付**: HeartbeatController + CuratorGraph 安全注入 + 自定义异常

---

## 目标

给 Curator 装"安全阀"。防止状态机无限循环、LLM 过度调用或运行超时。

---

## 必读文档

1. `PROJECT_CONTEXT_V10.md` + `CONVENTIONS_V10.md`
2. `src/memory_palace/service/curator_graph.py` — 7 阶段状态机，理解状态转换流程
3. `src/memory_palace/models/curator.py` — CuratorReport 结构

---

## 交付件

### 1. [NEW] `src/memory_palace/models/errors.py`

```python
class CuratorSafetyError(Exception):
    """Raised when HeartbeatController detects safety limit breach."""
    def __init__(self, reason: str, stats: dict): ...
    # reason: "max_steps_exceeded" | "max_llm_calls_exceeded" | "max_duration_exceeded"
```

### 2. [NEW] `src/memory_palace/service/heartbeat.py`

```python
class HeartbeatController:
    """Curator 运行时安全守卫.
    
    三重保护:
    1. MAX_STEPS: 状态机最大步数 (默认 50)
    2. MAX_LLM_CALLS: 单次运行 LLM 调用上限 (默认 30)
    3. MAX_DURATION: 单次运行最大秒数 (默认 120)
    + Dedup guard: 同一 memory_id 不重复处理
    """
    
    def __init__(
        self,
        max_steps: int = 50,
        max_llm_calls: int = 30,
        max_duration_seconds: int = 120,
    ): ...

    def tick(self) -> None:
        """每次状态转换调用。超限 raise CuratorSafetyError."""

    def record_llm_call(self) -> None:
        """记录一次 LLM 调用。超限 raise CuratorSafetyError."""

    def check_dedup(self, memory_id: str) -> bool:
        """True = 已处理过(跳过), False = 首次(继续处理)."""

    def reset(self) -> None:
        """重置所有计数器 (新一次 Curator run 前调用)."""

    @property
    def stats(self) -> dict:
        """{'steps': int, 'llm_calls': int, 'elapsed_seconds': float, 'dedup_skipped': int}"""
```

### 3. [MODIFY] `src/memory_palace/service/curator_graph.py`

- `CuratorGraph.__init__()` 新增可选 `heartbeat: HeartbeatController | None = None`
- `run()` 开始时: 如有 heartbeat 则 `heartbeat.reset()`
- 每个阶段转换时: `heartbeat.tick()`
- LLM 调用前: `heartbeat.record_llm_call()` (EXTRACT, RECONCILE, REFLECT 阶段)
- RECONCILE 阶段: `heartbeat.check_dedup(memory_id)` 跳过已处理项
- **异常处理**: catch `CuratorSafetyError` → 跳到 REPORT 阶段，report.errors 中记录原因
- Heartbeat 为 None 时行为不变（完全向后兼容）

### 4. [MODIFY] `src/memory_palace/service/curator.py`

- `CuratorService.__init__()` 创建 `HeartbeatController` 实例
- 传递给 `CuratorGraph(heartbeat=self._heartbeat)`

### 5. [NEW] `tests/test_service/test_heartbeat.py`

```
test_heartbeat_tick_within_limit — 正常范围不报错
test_max_steps_exceeded — 超过 max_steps raise CuratorSafetyError
test_max_llm_calls_exceeded — 超过 max_llm_calls raise
test_max_duration_exceeded — 超过 max_duration raise (用 time.sleep 或 mock)
test_dedup_first_time — 首次返回 False
test_dedup_second_time — 重复返回 True
test_reset_clears_all — reset 后计数归零
test_stats_accuracy — stats 反映真实计数
test_curator_graph_with_heartbeat — CuratorGraph 注入 heartbeat 运行成功
test_curator_graph_safety_stop — CuratorGraph 超限后优雅报告而非崩溃
```

预计 ~10 tests。

---

## 约束

1. HeartbeatController 无 I/O，无 LLM — 纯内存计数
2. CuratorGraph 的 heartbeat 参数可选 — None 时完全兼容 v0.2
3. `CuratorSafetyError` 放 `models/errors.py`（Models 层不依赖上层）
4. 时间使用 `time.monotonic()` 而非 `datetime.now()`

---

## 验证

```bash
pytest tests/ -q
pytest tests/test_service/test_heartbeat.py -v
ruff check
git commit -m "feat(R16): HeartbeatController with 3-layer safety guard"
```
