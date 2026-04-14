# Round 15 — Ebbinghaus 衰减引擎

> **Round**: 15 / Phase A  
> **分支**: `feat/v1.0-phase-a`  
> **前置**: R14 完成 (SleepTimeScheduler)  
> **交付**: Ebbinghaus 遗忘曲线引擎 + Scoring/CuratorGraph 集成 + Config 扩展

---

## 目标

用 Ebbinghaus 遗忘曲线替代 v0.2 的简单线性衰减。记忆自然遗忘，复习（访问）增加稳定性。

纯数学引擎，**零 I/O，零 LLM**。

---

## 必读文档

1. `PROJECT_CONTEXT_V10.md` + `CONVENTIONS_V10.md`
2. `src/memory_palace/engine/scoring.py` — 现有 `recency_score()` 和 `rank()`
3. `src/memory_palace/service/curator_graph.py` — PRUNE 阶段逻辑
4. `src/memory_palace/config.py` — 现有配置结构

---

## 交付件

### 1. [NEW] `src/memory_palace/engine/ebbinghaus.py`

Ebbinghaus 遗忘曲线。所有函数为纯函数，无副作用。

**数学公式**:

```
R(t) = exp(-t / S)                              — 保留率
S = S₀ × (1 + ln(1 + n))                        — 稳定性 (n=访问次数)
effective_importance = importance × R(t)          — 有效重要性
prune when effective_importance < threshold       — 淘汰判定
```

```python
def retention(hours_since_access: float, stability: float) -> float:
    """R(t) = exp(-t / S). 返回 [0, 1]."""

def stability(base_stability: float = 168.0, access_count: int = 0) -> float:
    """S = S₀ × (1 + ln(1 + n)). base=168h(1周), 访问越多越稳定."""

def effective_importance(
    importance: float, hours_since_access: float,
    access_count: int = 0, base_stability: float = 168.0,
) -> float:
    """effective = importance × retention."""

def should_prune(
    importance: float, hours_since_access: float,
    access_count: int = 0, threshold: float = 0.05,
) -> bool:
    """effective_importance < threshold → True."""
```

**边界处理**:
- `hours_since_access < 0` → clamp to 0
- `hours_since_access = inf` → return 0.0
- `access_count < 0` → clamp to 0

### 2. [MODIFY] `src/memory_palace/engine/scoring.py`

- 新增 `ebbinghaus_recency(hours_since_access, access_count, base_stability) -> float`
  - 调用 `ebbinghaus.retention()` + `ebbinghaus.stability()`
- `rank()` 新增可选参数 `decay_mode: Literal["exponential", "ebbinghaus"] = "exponential"`
  - `"exponential"`: 沿用 v0.2 的 `recency_score()` (默认, 向后兼容)
  - `"ebbinghaus"`: 使用 `ebbinghaus_recency()`
- `ScoredCandidate` 新增可选字段 `access_count: int = 0`

### 3. [MODIFY] `src/memory_palace/service/curator_graph.py`

- PRUNE 阶段: 导入 `ebbinghaus.should_prune()`
- 替代现有简单 importance 阈值检查
- 使用 MemoryItem 的 `access_count` 和 `accessed_at` 计算 hours_since_access
- CuratorState 新增 `ebbinghaus_pruned: int = 0` 计数
- CuratorReport 中体现 ebbinghaus 淘汰数

### 4. [MODIFY] `src/memory_palace/config.py`

```python
class EbbinghausConfig(BaseModel):
    """Ebbinghaus forgetting curve parameters."""
    enabled: bool = True
    base_stability_hours: float = 168.0  # 1 week
    prune_threshold: float = 0.05

# Config 新增:
class Config(BaseSettings):
    ...
    ebbinghaus: EbbinghausConfig = EbbinghausConfig()
```

### 5. [NEW] `tests/test_engine/test_ebbinghaus.py`

```
test_retention_at_zero — R(0) = 1.0
test_retention_decays_over_time — R(168h) ≈ 0.368 (1/e)
test_retention_approaches_zero — R(very large) → 0
test_stability_base_case — S(n=0) = 168
test_stability_increases_with_access — S(n=5) > S(n=0)
test_stability_log_growth — 增长速度递减
test_effective_importance_fresh — 刚访问 = importance
test_effective_importance_decayed — 一周后衰减到 importance/e
test_should_prune_below_threshold — effective < 0.05 → True
test_should_prune_fresh_memory — 刚访问 → False
test_should_not_prune_frequently_accessed — 高 access_count 保护
test_edge_negative_hours — 负数 clamp to 0
test_edge_infinite_hours — inf → retention = 0
test_edge_negative_access_count — 负数 clamp to 0
test_ebbinghaus_recency_in_scoring — 与 scoring.py 集成
```

预计 ~15 tests。

---

## 约束

1. **ebbinghaus.py 为纯函数模块** — 无 class，无 I/O，无 LLM
2. `rank()` 默认仍用 `"exponential"` — 向后兼容
3. CuratorGraph PRUNE 从 config 读取 `ebbinghaus.enabled`，False 时走旧逻辑
4. **不修改 MemoryItem 模型** — access_count 字段已存在

---

## 验证

```bash
pytest tests/ -q                           # 全绿
pytest tests/test_engine/test_ebbinghaus.py -v  # 新测试
ruff check
git commit -m "feat(R15): Ebbinghaus forgetting curve engine"
```
