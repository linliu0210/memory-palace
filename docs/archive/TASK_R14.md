# Round 14 — SleepTimeScheduler

> **Round**: 14 / Phase A  
> **分支**: `feat/v1.0-phase-a`  
> **前置**: `main @ v0.2.0` (284 tests, 全绿)  
> **交付**: SleepTimeScheduler + CuratorService 增强 + MemoryService 通知集成

---

## 目标

实现 Sleep-time Compute 调度器，让 Curator 从 "你喊它才干活" 变成 "后台自动巡逻"。

基于 `asyncio` 原生实现，**零新依赖**。

---

## 必读文档

开始前必须阅读以下文件获取项目上下文：

1. `PROJECT_CONTEXT_V10.md` — 架构、文件布局、数据流
2. `CONVENTIONS_V10.md` — TDD 纪律、代码规范、Git 规范
3. `src/memory_palace/service/curator.py` — CuratorService.should_trigger() 现有逻辑
4. `src/memory_palace/service/memory_service.py` — save()/save_batch() 需要插入 notify
5. `src/memory_palace/config.py` — CuratorConfig/CuratorTrigger 结构
6. `tests/conftest.py` — MockLLM, tmp_data_dir 等 fixture

---

## 交付件

### 1. [NEW] `src/memory_palace/service/scheduler.py`

**SleepTimeScheduler** — asyncio 后台调度器。

核心机制:
- 用 `asyncio.Event` + `wait(timeout=check_interval)` 同时支持定时和事件触发
- `start()` 创建后台 `asyncio.Task`，循环检查 `should_trigger()`
- `stop()` 优雅关闭：设置 `_running = False`，`event.set()` 唤醒 wait，await task 完成
- `notify(event: str)` 外部通知（如 save 后调用），set event 让 loop 提前检查
- 运行中 Curator 期间不接受新的 trigger（防并发执行）

```python
class SleepTimeScheduler:
    def __init__(
        self,
        curator_service: CuratorService,
        check_interval: int = 300,    # 5 min default
    ): ...
    
    async def start(self) -> None: ...       # 启动后台 task
    async def stop(self) -> None: ...        # 优雅关闭
    def notify(self, event: str) -> None: ... # 外部事件通知
    
    @property
    def is_running(self) -> bool: ...
    @property
    def last_run_report(self) -> CuratorReport | None: ...
    @property 
    def stats(self) -> dict: ...             # 运行统计 (trigger_count, last_trigger_reason, ...)
```

### 2. [MODIFY] `src/memory_palace/service/curator.py`

CuratorService 增强:
- `should_trigger()` 增加第三个条件: `importance_sum >= 5.0` (可配置)
- 新增 `increment_session()` 方法（取代外部直接 `_session_count += 1`）
- 新增 `record_importance(value: float)` 方法，累加近期 importance
- `_importance_sum: float` 内部跟踪，run() 后 reset

### 3. [MODIFY] `src/memory_palace/service/memory_service.py`

- 新增 `_scheduler: SleepTimeScheduler | None` 属性 (默认 None)
- 新增 `set_scheduler(scheduler: SleepTimeScheduler)` 注入方法
- `save()` 末尾：如果 scheduler 存在，调用 `scheduler.notify("save")` + `curator.increment_session()` + `curator.record_importance(importance)`
- `save_batch()` 同理
- **注意**: scheduler 是可选的，不影响现有 284 个测试

### 4. [MODIFY] `src/memory_palace/config.py`

CuratorTrigger 新增:
```python
class CuratorTrigger(BaseModel):
    timer_hours: int = 24
    session_count: int = 20
    cooldown_hours: int = 1
    importance_sum: float = 5.0    # ← 新增
```

### 5. [NEW] `tests/test_service/test_scheduler.py`

最低测试清单（可多不可少）：

```
test_scheduler_starts_and_stops — 基本生命周期，start 后 is_running=True，stop 后 False
test_scheduler_triggers_on_timer — 设置极短 check_interval，验证自动触发
test_scheduler_triggers_on_notify — notify() 后立即检查触发
test_scheduler_respects_cooldown — 连续两次触发间隔符合 cooldown
test_scheduler_no_concurrent_runs — curator 运行中再次触发不会并发执行
test_scheduler_graceful_stop — stop 时等待当前 cycle 完成
test_scheduler_stats — 验证 trigger_count, last_trigger_reason 更新
test_save_triggers_notify — MemoryService.save() 后 scheduler.notify 被调用
test_importance_sum_trigger — importance 累加超阈值触发
test_scheduler_without_scheduler — MemoryService 无 scheduler 时正常工作（不报错）
```

预计 ~12 tests。

---

## 约束

1. **零新依赖** — 只用 `asyncio` 标准库
2. **不破坏现有测试** — 先跑 `pytest tests/ -q` 确认 284 全绿，改完再跑全绿
3. **scheduler 是可选的** — MemoryService 不依赖 scheduler 存在
4. **单向依赖** — scheduler.py 在 Service 层，可 import CuratorService，但 CuratorService 不 import scheduler
5. **Git**: 完成后 `git add -A && git commit -m "feat(R14): SleepTimeScheduler with asyncio background loop"`

---

## 验证命令

```bash
cd /Users/link/Documents/Agent_Project/memory-palace
source /Users/link/Documents/Agent_Project/.venv/bin/activate

# 确认 v0.2 基线
pytest tests/ -q

# 开发完成后
pytest tests/ -q                    # 全绿
ruff check                          # 无警告
pytest tests/test_service/test_scheduler.py -v  # 新测试详情
```
