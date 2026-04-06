# Memory Palace — Conventions & Constraints

> **⚙️ STATIC**: 本文档内容在项目生命周期内基本不变。
> 标注 `<!-- SEMI-FIXED -->` 的段落例外，需随里程碑更新。
>
> 所有对本项目贡献代码的 agent 必须遵守以下规范。

---

## 一、代码风格 ⚙️

### 日志
```python
# ✅ 正确
import structlog
logger = structlog.get_logger(__name__)
logger.info("Curator run complete", facts_extracted=count)

# ❌ 禁止
import logging
print("debug:", x)
```

### 类型标注
```python
# ✅ 每个函数必须有 type hints + docstring
async def save(self, content: str,
               importance: float | None = None,
               room: str = "general") -> MemoryItem:
    """Save a new memory. Routes to Core or Recall by importance."""
    ...

# ❌ 禁止裸函数
def save(self, content, importance=None):
    ...
```

### 格式化
```bash
ruff check --fix && ruff format
```
所有代码必须通过 `ruff check && ruff format --check`，零 error。

### Pydantic 规范
```python
# ✅ 使用 Pydantic v2 BaseModel，显式 Field
class MemoryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    importance: float = Field(ge=0.0, le=1.0)

# ❌ 禁止 dict-as-schema
memory = {"id": "...", "content": "...", "importance": 0.5}
```

---

## 二、架构模式 ⚙️

### 分层依赖规则
```
Integration → Service → Engine → Store → Foundation → Models
     ↑ 高层可调低层    ↓ 低层不可引用高层
```
**严格单向依赖**：`store/` 不得 import `service/`，`engine/` 不得 import `integration/`。

### Protocol-Based DI（依赖注入）
所有外部依赖（LLM、Embedding、文件系统）通过 Protocol 注入，不得硬编码：
```python
# ✅ 通过 Protocol 注入
class FactExtractor:
    def __init__(self, llm: LLMProvider): ...

# ❌ 硬编码依赖
class FactExtractor:
    def __init__(self):
        self._client = openai.Client(api_key=os.getenv("OPENAI_API_KEY"))
```

### 错误处理三层模式
```
Layer 1: Validation   — 前置条件不满足（importance 越界、空内容）→ ValueError
Layer 2: Graceful     — 单条记忆操作失败 → log warning + skip，不中断批量
Layer 3: Fatal        — 存储不可用、LLM 连续失败 → raise RuntimeError
```

### 同步 vs 异步
```python
# v0.1: 所有操作同步（包括 LLM 调用用 asyncio.run 包装）
# v0.2+: Engine 层升级为 async

# ✅ v0.1 LLM Provider 接口（async，但调用端可 sync wrapper）
class LLMProvider(Protocol):
    async def complete(self, prompt: str,
                       response_format: type | None = None) -> str: ...
```

---

## 三、TDD 纪律 ⚙️（没有例外）

> [!CAUTION]
> 以下规则**没有例外**。违反任何一条等同于任务未完成。

### 规则 1: 先跑现有测试
开始写代码前，必须先运行全量测试确认 baseline：
```bash
uv run pytest tests/ -q
```
<!-- SEMI-FIXED: baseline 数字随 merge 更新，见 PROJECT_CONTEXT.md -->
当前 baseline 见 `PROJECT_CONTEXT.md` 的"测试 Baseline"章节。

### 规则 2: 不许偷改测试
**除非任务明确要求修改某个测试，否则禁止修改任何现有测试文件。**

如果你的代码改动导致现有测试失败：
- ✅ 修你的代码，让测试通过
- ❌ 修改测试断言让它"通过"

唯一允许修改现有测试的情况：
- 任务 spec 中**明确列出**该测试文件为 `[MODIFY]`
- 被修改的模块 API 签名发生了变化（如新增了必须参数），测试代码需要适配
- 必须在 DISPATCH_LOG 的 `Issues found` 中**显式声明**修改了哪个测试及原因

### 规则 2.5: 测试 = 可执行规约（不可变契约）

> [!CAUTION]
> TDD 测试一旦写定并通过 RED 验证，就不是"测试代码"——它是**可执行的规格说明书**。

**核心原则**：测试先于实现写出，定义的是系统"应该做什么"。它的地位等同于 SPEC.md 中的接口契约。

**不可变性规则**：
- 测试在 RED 阶段写定后，进入**冻结状态**
- GREEN 阶段仅允许写产品代码使测试通过，**禁止反向修改测试来适配实现**
- REFACTOR 阶段可以重构测试的内部结构（提取 helper、改善 fixture），但**断言语义不得改变**

**违规判定**：
```python
# ❌ 违规：实现困难就放宽断言
# 原测试
assert result.importance == 0.8
# "改进"后
assert result.importance > 0.5  # "差不多就行"

# ❌ 违规：实现返回了意外格式就改测试
# 原测试
assert isinstance(items, list)
assert len(items) == 2
# "适配"后
assert items is not None  # "只要不是 None 就好"
```

**如果测试本身有 bug**（Spec 描述错误、fixture 数据不合理）：
1. 在 DISPATCH_LOG 中记录发现
2. 请求 orchestrator 批准修改
3. 修改后重新走 RED 验证确认测试失败原因正确

### 规则 3: Red-Green-Refactor
每个新功能严格遵循 TDD 循环：
1. **RED** — 写一个失败的测试（`pytest tests/test_xxx.py::test_name -v` → FAILED）
2. **Verify RED** — 确认失败原因是"功能缺失"而非"语法错误"
3. **GREEN** — 写最小代码使测试通过
4. **Verify GREEN** — 确认所有现有测试仍通过
5. **REFACTOR** — 清理代码，保持所有测试绿色；可重构测试结构但**断言语义不变**

### 规则 4: 实现顺序
严格按依赖拓扑排序实现，不得跳 Round：
```
Round 1: Foundation (AuditLog, Config, LLM)    ← 无外部依赖
Round 2: Models (MemoryItem, AuditEntry, Room) ← 纯数据
Round 3: Store (CoreStore, RecallStore)        ← I/O 层
Round 4: Engine (Scoring, FactExtractor, Reconcile) ← LLM Mock
Round 5: Service (MemoryService, Retriever, Curator) ← Integration
Round 6: E2E Pipeline                          ← 全链路
```
每个 Round 结束后运行 `uv run pytest tests/ -q` 确认全绿。

### 规则 5: Mock 边界
- **LLM 必须 Mock** — 使用 `MockLLM` fixture，通过 `LLMProvider` Protocol 注入
- **文件系统用 tmp_path** — 所有 Store 测试使用 pytest `tmp_path` fixture
- **不测 Mock 本身** — Mock 仅隔离 LLM 边界，测试真实行为

### 规则 6: 完成后再跑一次全量测试
```bash
uv run pytest tests/ -q
```
确认通过数 ≥ baseline（可以更多，不能更少）。

---

## 四、并行护栏 ⚙️ + ⚡

### 冲突规避原则 ⚙️

当多个 agent 并行工作时，每个 prompt 会在 **「并行保护文件」** 章节列出不可修改的文件。

**即使你认为某个被保护的文件"应该"被修改 — 也不要碰。** 在 DISPATCH_LOG 的 `Issues found` 中记录你的发现即可。

### Schema 保护 ⚙️

以下文件是全局数据契约，未经 orchestrator 批准不得修改：
- `src/memory_palace/models/*.py`（所有数据模型定义）
- `src/memory_palace/foundation/llm.py`（LLMProvider Protocol）

如果你的任务需要新增字段或修改 Protocol，**必须**在 DISPATCH_LOG 的 `Issues found` 中提出请求，由 orchestrator 在后续 prompt 中批准。

### 当前并行保护列表

<!-- SEMI-FIXED: 每次发新任务时由 orchestrator 更新此列表 -->
<!-- 如果你收到的 prompt 中有「并行保护文件」章节，以 prompt 为准；否则参考此列表 -->

> 具体保护文件列表以每次 prompt 正文中的「并行保护文件」章节为准。
> 本处仅作为 fallback 参考。

---

## 五、Git 规范 ⚙️

### 分支命名
```
feat/[scope]-[description]     # 新功能
fix/[scope]-[description]      # 修复
refactor/[scope]-[description] # 重构
```
Scope 枚举: `foundation`, `models`, `store`, `engine`, `service`, `integration`, `e2e`

### Commit Message
[Conventional Commits](https://www.conventionalcommits.org/) 格式：
```
feat(store): add RecallStore with FTS5 search
fix(engine): handle malformed LLM response in FactExtractor
refactor(service): extract scoring logic from MemoryService
test(e2e): add full lifecycle pipeline test
docs: update PROJECT_CONTEXT.md for v0.1 baseline
```

### 原子性
一个 commit 做一件事。如果任务包含多个逻辑独立的改动（如"Store + Engine"），应拆为多个 commit。

---

## 六、固定验证命令 ⚙️

以下命令**每次任务都必须运行**，无需在 prompt 中重复：

```bash
# 1. 全量测试
uv run pytest tests/ -q

# 2. Lint + 格式检查
ruff check && ruff format --check
```

任务特定的额外验证命令会在 prompt 的「验收」章节列出。

---

## 七、Dispatch Log 协议 ⚙️

完成任务后，在 `DISPATCH_LOG.md` **末尾追加** entry（不修改已有内容）：

```markdown
## [YYYY-MM-DDTHH:MM] branch-name — 任务简述 STATUS_EMOJI
- **Agent**: 执行者
- **Status**: DONE / IN_PROGRESS / BLOCKED
- **Base**: 基准分支 @ commit hash
- **Files changed**: 新增(NEW)/修改(MOD)/删除(DEL) 清单
- **Key decisions**: 1-3 条设计决策
- **Issues found**: 执行中发现的问题（包括"想改但被禁止的文件"）
- **Tests**: before → after（如 0→15 passed）
- **Merge note**: 合并风险评估
```

---

## 八、Known Gotchas & Library Quirks ⚙️

> [!CAUTION]
> 以下是实现过程中已知的技术陷阱。每位 Agent 在开始 Round 实现前**必须阅读**。

```python
# === Storage ===
# CRITICAL: SQLite FTS5 中文分词需要 simple tokenizer（不支持 ICU）
# CRITICAL: JSON 文件原子写入必须用 write-to-tmp + os.rename 模式，防止断电数据损坏
# CRITICAL: Core Store 超过 budget 时必须优雅降级（prune 最低分记忆），不能直接报错

# === Pydantic v2 ===
# CRITICAL: model_validate_json() 只接受 str/bytes，不接受 dict — 用 model_validate() 替代
# CRITICAL: model_dump() 默认 mode='python'，写 JSON 需要 mode='json' 或用 model_dump_json()
# CRITICAL: datetime 字段序列化需要在 model_config 中设置 json_encoders 或用 PlainSerializer

# === structlog ===
# CRITICAL: structlog 必须在进程入口配置一次，重复 configure() 会丢失处理器链
# CRITICAL: 测试中需要 structlog.testing.capture_logs() 而不是 mock

# === pytest ===
# CRITICAL: pytest-asyncio auto 模式需要 pyproject.toml 中显式声明 asyncio_mode = "auto"
# CRITICAL: tmp_path fixture 每个 test function 独立，tmp_path_factory 可跨 session 共享

# === LLM ===
# CRITICAL: MockLLM 采用 Protocol 兼容（非继承），确保 isinstance check 不可用——使用 structural subtyping
# CRITICAL: LLM 返回可能是 malformed JSON — FactExtractor/Reconcile 必须有 JSON parse fallback
# CRITICAL: uuid4() 在测试中不确定——需要固定 seed 或 monkeypatch uuid.uuid4

# === 衰减公式 ===
# CRITICAL: 指数衰减 decay = exp(-λ·Δt) 中 λ 的量纲是 1/小时，不是 1/天——注意单位转换
```

---

## 图例

| 标记 | 含义 |
|------|------|
| ⚙️ | **STATIC** — 整个项目生命周期不变 |
| ⚡ | **SEMI-FIXED** — 随里程碑或每次 dispatch 更新 |
| `<!-- SEMI-FIXED -->` | HTML 注释标记需要定期更新的具体位置 |
