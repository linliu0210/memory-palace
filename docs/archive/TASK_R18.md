# Round 18 — MCP Server 基础

> **Round**: 18 / Phase B  
> **分支**: `feat/v1.0-phase-b` (从 Phase A 完成后的 main 开)  
> **前置**: Phase A 完成 (R14-R17)  
> **交付**: FastMCP Server + 12 Tools + 6 Resources + 请求上下文管理

---

## 目标

用 FastMCP v2.x 将 Memory Palace 暴露为标准 MCP Server，让任意 MCP Client (Claude Desktop, Cursor, Antigravity) 即插即用。

**这是系统边界变更**: 从 Python library → network service。

---

## 必读文档

1. `PROJECT_CONTEXT_V10.md` + `CONVENTIONS_V10.md`
2. `src/memory_palace/integration/cli.py` — 现有 CLI 构建 MemoryService 的模式 (特别是 `_build_memory_service()`, `_build_embedding_provider()`)
3. `src/memory_palace/service/memory_service.py` — 所有公开 API
4. FastMCP v2 文档: `pip install fastmcp` 后 `python -c "import fastmcp; help(fastmcp)"`，或参考 https://gofastmcp.com

---

## 交付件

### 1. [MODIFY] `pyproject.toml`

```diff
 dependencies = [
     ...
+    "fastmcp>=2.0,<3.0",
 ]

 [project.scripts]
 palace = "memory_palace.integration.cli:app"
+palace-mcp = "memory_palace.integration.mcp_server:main"
```

### 2. [NEW] `src/memory_palace/integration/mcp_server.py`

**完整 MCP Server**。遵循 Tool/Resource 分离原则:
- **Tool**: 有副作用的操作 (save, update, forget, curate, reflect)
- **Resource**: 只读数据 (health, stats, rooms, memory detail)

**12 Tools**:
| Tool | 签名 | 描述 |
|------|------|------|
| `save_memory` | `(content, importance=0.5, room="general", tags=None) -> dict` | 保存记忆 |
| `search_memory` | `async (query, top_k=5, room=None) -> list[dict]` | 混合检索 |
| `update_memory` | `(memory_id, new_content, reason="update") -> dict` | 版本更新 |
| `forget_memory` | `(memory_id, reason="request") -> dict` | 软删除 |
| `inspect_memory` | `(memory_id) -> dict` | 单条详情 |
| `curate_now` | `async () -> dict` | 触发整理 |
| `reflect_now` | `async () -> dict` | 反思生成洞察 |
| `get_health` | `() -> dict` | 健康评分 |
| `list_rooms` | `() -> list[dict]` | 房间列表 |
| `get_stats` | `() -> dict` | 统计概览 |
| `get_audit_log` | `(last_n=20) -> list[dict]` | 审计日志 |
| `get_context` | `async (query=None, top_k=5) -> str` | 编译上下文 |

**6 Resources**:
| Resource URI | 描述 |
|---|---|
| `palace://health` | 实时健康评分 |
| `palace://stats` | 统计概览 |
| `palace://rooms` | 房间列表 |
| `palace://context/{query}` | 编译上下文 |
| `palace://memory/{memory_id}` | 单条记忆 |
| `palace://audit` | 审计日志 |

**返回值**: 全部为 dict/list (JSON serializable)，不暴露 Pydantic model。
MemoryItem → dict 转换时用 `.model_dump()` 并把 datetime 转 ISO string。

**main() 入口**:
```python
def main():
    mcp.run()  # stdio transport (默认)
```

### 3. [NEW] `src/memory_palace/integration/mcp_context.py`

请求级上下文管理，确保 MCP tools/resources 共享同一个 MemoryService 实例。

```python
class MCPServiceManager:
    """Singleton MemoryService for MCP server lifecycle.
    
    复用 cli.py 的 _build_memory_service() 逻辑。
    使用 asyncio.Lock 保护初始化（首次调用 lazy init）。
    """
    
    _service: MemoryService | None = None
    _lock: asyncio.Lock = asyncio.Lock()
    _data_dir: Path = Path("~/.memory_palace").expanduser()
    
    @classmethod
    async def get_service(cls) -> MemoryService: ...
    
    @classmethod
    def configure(cls, data_dir: Path) -> None: ...
    
    @classmethod
    async def shutdown(cls) -> None: ...
```

### 4. [DELETE or REPLACE] `src/memory_palace/integration/tools.py`

现有 3 行占位符，替换为:
```python
# tools.py — Deprecated. See mcp_server.py
# Retained for backward compatibility reference only.
```

### 5. [NEW] `tests/test_integration/test_mcp_server.py`

用 FastMCP 内置 Client 做进程内测试（不启动真实 server）:

```python
from fastmcp import Client

# 或者 from mcp_server import mcp 直接测试
```

```
test_save_memory_tool — save 返回 dict 含 id, tier
test_search_memory_tool — save → search 找到
test_update_memory_tool — save → update 返回新 id
test_forget_memory_tool — save → forget → inspect 状态为 PRUNED
test_inspect_memory_tool — save → inspect 返回完整详情
test_curate_now_tool — curate 返回 CuratorReport dict
test_get_health_tool — health 返回 5 维度
test_list_rooms_tool — 返回默认 5 个房间
test_get_stats_tool — 返回 core_count, recall_count
test_get_audit_log_tool — save 后 audit 有 CREATE 记录
test_get_context_tool — 返回格式化字符串
test_health_resource — 通过 resource URI 读取
test_stats_resource — 通过 resource URI 读取
test_memory_resource — 通过 resource URI 读取单条
test_save_invalid_importance — importance > 1.0 返回错误
test_forget_nonexistent — 不存在的 ID 返回错误
test_search_empty — 空库搜索返回空 list
test_reflect_no_memories — 无记忆时 reflect 返回提示
```

预计 ~20 tests。

---

## 约束

1. **唯一新依赖**: `fastmcp>=2.0,<3.0`，Pin 到 v2.x (不用 v3 beta)
2. 引入前执行 `pip install --dry-run fastmcp` 检查传递依赖
3. **所有 Tool 包裹 try/except**，返回 `{"success": False, "error": "...", "code": "..."}` 而非 raise
4. **不修改 Service 层接口** — MCP 是 Integration 层，只调用现有 Service API
5. Transport 默认 stdio (for Claude Desktop)

---

## 验证

```bash
pip install "fastmcp>=2.0,<3.0"
pytest tests/ -q
pytest tests/test_integration/test_mcp_server.py -v
palace-mcp --help  # 确认 entry point 可用
ruff check
git commit -m "feat(R18): MCP Server with 12 tools and 6 resources via FastMCP"
```
