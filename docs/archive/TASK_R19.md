# Round 19 — 并发安全 + Error Handling

> **Round**: 19 / Phase B  
> **分支**: `feat/v1.0-phase-b`  
> **前置**: R18 完成 (MCP Server 基础)  
> **交付**: 并发安全加固 + MCP 错误处理规范化 + 输入验证

---

## 目标

MCP Server 意味着多个 Agent 可能同时调用 Memory Palace。确保并发安全和健壮的错误处理。

---

## 必读文档

1. `PROJECT_CONTEXT_V10.md` + `CONVENTIONS_V10.md`
2. R18 新增的 `mcp_server.py` 和 `mcp_context.py`
3. `src/memory_palace/store/core_store.py` — JSON 文件操作（非线程安全）
4. `src/memory_palace/store/recall_store.py` — SQLite（有事务但需 WAL）

---

## 交付件

### 1. [MODIFY] `src/memory_palace/service/memory_service.py`

并发安全:
- 新增 `_write_lock: asyncio.Lock` 属性
- `save()`, `update()`, `forget()` 包裹在 `async with self._write_lock:`
- `search()`, `get_by_id()`, `stats()` 不需要锁（只读）
- `_auto_demote_if_needed()` 已在 save 内部，自动受锁保护

### 2. [MODIFY] `src/memory_palace/store/recall_store.py`

SQLite WAL 模式:
- `__init__()` 中设置: `conn.execute("PRAGMA journal_mode=WAL")`
- 允许并发读，写自动排队

### 3. [MODIFY] `src/memory_palace/integration/mcp_server.py`

错误处理规范化:
- 所有 Tool 统一返回格式:
  - 成功: `{"success": True, "data": {...}}`
  - 失败: `{"success": False, "error": "message", "code": "ERROR_CODE"}`
- Error codes:
  ```python
  NOT_FOUND = "NOT_FOUND"           # memory_id 不存在
  VALIDATION_ERROR = "VALIDATION"   # 输入不合法
  INTERNAL_ERROR = "INTERNAL"       # 未预期异常
  LLM_ERROR = "LLM_ERROR"          # LLM 调用失败
  ```

输入验证:
- `importance` 范围 [0.0, 1.0]，越界返回 VALIDATION_ERROR
- `room` 必须在 Config.rooms 列表中（或允许 "general" 作为 fallback）
- `memory_id` 格式验证（UUID 格式或非空字符串）
- `top_k` 范围 [1, 100]

### 4. [NEW] `tests/test_integration/test_mcp_concurrent.py`

```
test_concurrent_saves — asyncio.gather 并行 save 10 条，全部成功，数量正确
test_concurrent_search_during_save — 边写边读不崩溃
test_concurrent_curate_dedup — 同时触发两次 curate，只执行一次
test_concurrent_update_same_memory — 同一条记忆并发 update
test_sqlite_wal_mode — 验证 recall_store WAL 已开启
test_validation_importance_range — importance=1.5 返回 VALIDATION_ERROR
test_validation_room — 不存在的 room 返回 VALIDATION_ERROR 或 fallback
test_error_format_consistency — 所有错误返回包含 success, error, code 字段
```

预计 ~8 tests。

---

## 约束

1. Lock 用 `asyncio.Lock` (不用 threading.Lock — 我们是单线程 asyncio)
2. WAL 设置只需一行 PRAGMA，不引入新依赖
3. 不修改 MCP tool 签名 — 只修改内部实现和返回结构
4. 错误返回用 Python dict，FastMCP 自动 JSON 序列化

---

## 验证

```bash
pytest tests/ -q
pytest tests/test_integration/test_mcp_concurrent.py -v
ruff check
git commit -m "feat(R19): concurrency safety + MCP error handling"
```
