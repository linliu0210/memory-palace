# Round 17 — Phase A Integration + E2E

> **Round**: 17 / Phase A (Final)  
> **分支**: `feat/v1.0-phase-a`  
> **前置**: R14-R16 全部完成  
> **交付**: CLI schedule 命令 + Phase A E2E 测试 + 集成验证

---

## 目标

将 R14-R16 的三个组件（Scheduler + Ebbinghaus + Heartbeat）串联为完整的自动化体验，并通过 E2E 测试验证端到端流程。

---

## 必读文档

1. `PROJECT_CONTEXT_V10.md` + `CONVENTIONS_V10.md`
2. `src/memory_palace/integration/cli.py` — 现有 CLI 命令结构
3. R14-R16 新增的所有文件

---

## 交付件

### 1. [MODIFY] `src/memory_palace/integration/cli.py`

新增 `schedule` 命令组:

```python
schedule_app = typer.Typer(name="schedule", help="Sleep-time 调度管理")
app.add_typer(schedule_app)

@schedule_app.command("start")
def schedule_start(
    check_interval: int = typer.Option(300, help="检查间隔(秒)"),
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """启动后台 Sleep-time 调度."""

@schedule_app.command("status")
def schedule_status(...) -> None:
    """查看调度器状态."""
```

注意: CLI 中的 `start` 是阻塞的 (asyncio.run)，用 Ctrl+C 停止。
`status` 读取上次运行的持久化状态（如果有的话），否则提示未运行。

### 2. [MODIFY] `src/memory_palace/integration/cli.py`

现有 `curate` 命令增强:
- 在 report 输出中增加 ebbinghaus_pruned 计数（如果非零）
- 增加 heartbeat stats 输出（steps, llm_calls, duration）

### 3. [NEW] `tests/test_e2e/test_automation_e2e.py`

**端到端集成测试** — 验证 Phase A 三个组件协同:

```
test_save_accumulates_importance_sum — 
    save N 条记忆 → importance_sum 累加 → 达到阈值 → should_trigger = True
    
test_ebbinghaus_decay_lifecycle — 
    save 记忆 → 模拟时间推进 → effective_importance 衰减 → 
    触发 curate → PRUNE 阶段淘汰低有效重要性记忆
    
test_heartbeat_prevents_runaway — 
    设置 max_steps=3 的 heartbeat → curator_graph.run() → 
    超限后优雅退出，report.errors 包含 safety 信息
    
test_scheduler_integration — 
    创建 scheduler + curator → start → save 多条 → 
    等待自动触发 → 验证 curate 被执行 → stop

test_full_phase_a_lifecycle —
    综合: save → decay → auto-trigger → curate with heartbeat → 
    验证记忆被 ebbinghaus 淘汰 + heartbeat 未超限

test_backward_compatibility —
    不设置 scheduler, 不启用 ebbinghaus → 
    v0.2 行为完全不变 (regression guard)
```

预计 ~8 tests。

### 4. [MODIFY] `tests/test_integration/test_cli.py`

为 `schedule` 相关命令添加基本 CLI 调用测试 (用 typer.testing.CliRunner):
- `test_schedule_status_no_scheduler` — 未运行时显示提示
- 预计 ~2 tests

---

## 约束

1. E2E 测试全部使用 MockLLM + tmp_path，不依赖真实 LLM
2. 时间模拟: 用 MemoryItem 的 `accessed_at` 字段直接赋值历史时间
3. Scheduler 测试中使用极短 check_interval (如 0.1s) 加速
4. 不引入新依赖

---

## Phase A 完成标准

```bash
pytest tests/ -q                  # 全部绿 (284 + ~45 = ~329)
ruff check                        # 无警告
git log --oneline -5              # R14-R17 四个 commit
```

Phase A 完成后，等待 Dispatcher 指示是否 merge 到 main 或继续 Phase B。

---

## 验证

```bash
pytest tests/ -q
pytest tests/test_e2e/test_automation_e2e.py -v
ruff check
git commit -m "feat(R17): Phase A integration — CLI schedule + E2E automation tests"
```
