# Round 23 — 监控指标 + Core 预算增强

> **Round**: 23 / Phase C (Final)  
> **分支**: `feat/v1.0-phase-c`  
> **前置**: R21-R22 完成  
> **交付**: MemoryMetrics 收集 + Health 增强 + Phase C E2E + CLI/MCP 暴露

---

## 目标

给 Memory Palace 装"仪表盘"。收集操作延迟、增长率、整理频率等运营指标。

---

## 必读文档

1. `PROJECT_CONTEXT_V10.md` + `CONVENTIONS_V10.md`
2. `src/memory_palace/engine/health.py` — 现有 5 维度健康评分
3. `src/memory_palace/service/memory_service.py` — stats() 方法

---

## 交付件

### 1. [NEW] `src/memory_palace/engine/metrics.py`

```python
class OperationTimer:
    """上下文管理器，记录操作延迟."""
    
    def __init__(self, operation: str): ...
    def __enter__(self): ...
    def __exit__(self, *args): ...

class MemoryMetrics:
    """Operational metrics collection (singleton).
    
    收集:
    - search_latencies: list[float]   (最近 100 次)
    - save_latencies: list[float]
    - curator_durations: list[float]
    - memory_count_history: list[tuple[datetime, int]]
    """
    
    def record_search(self, duration_ms: float) -> None: ...
    def record_save(self, duration_ms: float) -> None: ...
    def record_curate(self, duration_s: float) -> None: ...
    def record_count(self, count: int) -> None: ...
    
    @property
    def summary(self) -> dict:
        """返回:
        {
            "search_p95_ms": float,
            "save_p95_ms": float,
            "curator_avg_duration_s": float,
            "growth_rate_per_day": float,  # 基于 count_history 计算
            "total_searches": int,
            "total_saves": int,
            "total_curations": int,
        }
        """
```

### 2. [MODIFY] `src/memory_palace/service/memory_service.py`

- 新增 `_metrics: MemoryMetrics` 属性
- `save()` 包裹 OperationTimer → `_metrics.record_save()`
- `search()` 包裹 OperationTimer → `_metrics.record_search()`
- `get_metrics() -> dict` 新方法返回 metrics.summary

### 3. [MODIFY] `src/memory_palace/engine/health.py`

MemoryHealthScore 增加第 6 维度:
```python
class MemoryHealthScore(BaseModel):
    ...
    operations: float = 0.0  # [0,1] — 操作指标健康度
    
    @property
    def overall(self) -> float:
        # 调整权重分配给 6 维度
```

operations 评分逻辑:
- search_p95 < 100ms → 1.0, < 200ms → 0.7, else → 0.3
- 加权平均

### 4. [MODIFY] CLI + MCP

- CLI `palace health` 增加 metrics 显示
- CLI 新增 `palace metrics` 命令
- MCP: `get_metrics()` tool + `palace://metrics` resource

### 5. [NEW] `tests/test_engine/test_metrics.py`

```
test_record_search — 记录并查看 p95
test_record_save — 记录并查看 p95
test_record_curate — 记录并查看 avg
test_growth_rate — 两次 count → 计算日增长率
test_summary_format — summary 含所有必要字段
test_p95_calculation — 验证 percentile 计算正确
test_empty_metrics — 未记录时 summary 返回 0
test_operation_timer — OperationTimer 上下文管理器
test_health_operations_dimension — 新维度纳入 overall
test_metrics_rolling_window — 超过 100 条自动丢弃旧记录
```

预计 ~10 tests。

---

## Phase C 完成标准

```bash
pytest tests/ -q                  # 全部绿 (~398 tests)
ruff check
palace metrics --help             # 命令可用
```

---

## 验证

```bash
pytest tests/ -q
pytest tests/test_engine/test_metrics.py -v
ruff check
git commit -m "feat(R23): operational metrics + health v2 (6-dimension)"
```
