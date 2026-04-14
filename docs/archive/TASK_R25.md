# Round 25 — Full Ingest Pipeline

> **Round**: 25 / Phase D (Final)  
> **分支**: `feat/v1.0-phase-d`  
> **前置**: R24 完成 (GraphStore 可选)  
> **交付**: 5-pass Ingest Pipeline + CLI/MCP 集成 + v1.0 E2E 综合

---

## 目标

实现完整的 5-pass 摄取管线，将原始文档转化为结构化记忆并建立关联。

灵感来源: sage-wiki ingest pipeline。

---

## 必读文档

1. `PROJECT_CONTEXT_V10.md` + `CONVENTIONS_V10.md`
2. `src/memory_palace/engine/fact_extractor.py` — 现有事实提取
3. `src/memory_palace/engine/reconcile.py` — 现有调和引擎
4. `src/memory_palace/service/batch_io.py` (R21) — BatchImporter 接口
5. `src/memory_palace/store/graph_store.py` (R24, 如存在)

---

## 交付件

### 1. [NEW] `src/memory_palace/service/ingest_pipeline.py`

5-pass Pipeline:

```python
@dataclass
class IngestReport:
    total_input_chars: int
    pass_results: dict[str, dict]  # 每个 pass 的统计
    memories_created: int
    relations_created: int
    duration_seconds: float
    errors: list[str]


class IngestPipeline:
    """5-pass document ingestion pipeline.
    
    Pass 1 — DIFF: 检查文档是否已处理过 (content hash)
    Pass 2 — EXTRACT: FactExtractor 提取原子事实  
    Pass 3 — MAP: 为每个事实分配 room + importance
    Pass 4 — LINK: 发现事实间关联 (如有 GraphStore)
    Pass 5 — UPDATE: ReconcileEngine 对比存量后写入
    """
    
    def __init__(
        self,
        memory_service: MemoryService,
        fact_extractor: FactExtractor,
        reconcile_engine: ReconcileEngine,
        llm: LLMProvider,
        graph_store: GraphStore | None = None,
    ): ...
    
    async def ingest(self, text: str, source_id: str = "") -> IngestReport: ...
    async def ingest_file(self, path: Path) -> IngestReport: ...
    async def ingest_batch(self, paths: list[Path]) -> IngestReport: ...
```

**Pass 详细逻辑**:

1. **DIFF**: 计算 text hash → 查 AuditLog 是否已处理 → 已处理则 skip
2. **EXTRACT**: `FactExtractor.extract([text])` → 原子事实列表
3. **MAP**: LLM prompt "给每个事实分配 room 和 importance" → 带元数据的事实
4. **LINK**: (可选, 需 GraphStore) LLM prompt "这些事实之间有什么关联" → 关联边
5. **UPDATE**: 对每个事实调用 `ReconcileEngine.reconcile(fact, existing_memories)` → ADD/UPDATE/NOOP

### 2. [MODIFY] `src/memory_palace/integration/cli.py`

```python
@app.command()
def ingest(
    file: str = typer.Argument(..., help="文档路径"),
    data_dir: str = typer.Option("~/.memory_palace"),
) -> None:
    """5-pass 智能摄取文档."""
```

### 3. [MODIFY] `src/memory_palace/integration/mcp_server.py`

```python
@mcp.tool
async def ingest_document(text: str, source_id: str = "") -> dict:
    """5-pass 智能摄取."""
```

### 4. [NEW] `tests/test_service/test_ingest_pipeline.py`

```
test_ingest_basic — 一段文本 → 提取事实 → 写入记忆
test_ingest_diff_skip — 同一文本第二次 skip
test_ingest_room_mapping — 事实被分配到正确 room
test_ingest_reconcile_update — 冲突事实被 update 而非重复 add
test_ingest_reconcile_noop — 已存在的相同事实 noop
test_ingest_link_with_graph — (需 GraphStore) 关联边创建
test_ingest_link_without_graph — 无 GraphStore 时 pass 4 skip
test_ingest_file — 文件路径输入
test_ingest_batch — 多文件批量
test_ingest_error_handling — LLM 失败时 partial results + errors
test_ingest_report_fields — report 所有字段完整
test_ingest_empty_text — 空文本 → 0 条记忆
```

预计 ~12 tests。

### 5. [NEW] `tests/test_e2e/test_v10_final_e2e.py`

v1.0 综合 E2E:

```
test_v10_full_lifecycle —
    1. ingest 文档 → 记忆创建
    2. search 验证可检索
    3. scheduler 自动触发 curate
    4. ebbinghaus 衰减验证
    5. MCP tool 调用验证
    6. health + metrics 正常
    
test_v10_multi_persona_isolation —
    persona A save → persona B search → 找不到 → 数据隔离

test_v10_batch_roundtrip —
    ingest → export JSONL → import JSONL → 数量一致
```

预计 ~3 tests。

---

## Phase D + v1.0 完成标准

```bash
pytest tests/ -q                  # 全部绿 (~425+ tests)
ruff check
palace ingest --help              # 命令可用
```

---

## 验证

```bash
pytest tests/ -q
pytest tests/test_service/test_ingest_pipeline.py -v
pytest tests/test_e2e/test_v10_final_e2e.py -v
ruff check
git commit -m "feat(R25): Full 5-pass ingest pipeline + v1.0 final E2E"
```

---

## v1.0 收尾清单 (R25 完成后)

Phase D 完成后，等待 Dispatcher 执行:
1. Merge `feat/v1.0-phase-d` → main
2. Tag `v1.0.0`
3. 更新 README.md
4. 生成 HANDOVER_V10.md
5. 归档产物
