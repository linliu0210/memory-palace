# Round 20 — Phase B Integration + CI + 部署

> **Round**: 20 / Phase B (Final)  
> **分支**: `feat/v1.0-phase-b`  
> **前置**: R18-R19 完成  
> **交付**: CLI serve 命令 + MCP E2E 测试 + GitHub Actions CI + Claude Desktop 配置示例

---

## 目标

将 MCP Server 接入 CLI 和 CI，完成 Phase B 集成闭环。

---

## 必读文档

1. `PROJECT_CONTEXT_V10.md` + `CONVENTIONS_V10.md`
2. R18-R19 新增的所有文件
3. `src/memory_palace/integration/cli.py`

---

## 交付件

### 1. [MODIFY] `src/memory_palace/integration/cli.py`

新增 `serve` 命令:

```python
@app.command()
def serve(
    transport: str = typer.Option("stdio", help="传输协议: stdio | http"),
    host: str = typer.Option("localhost", help="HTTP 主机"),
    port: int = typer.Option(8765, help="HTTP 端口"),
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """启动 Memory Palace MCP Server."""
    # 设置 data_dir
    # 调用 mcp_server.main() 或直接 mcp.run(transport=transport, ...)
```

### 2. [NEW] `.github/workflows/ci.yml`

最小 CI — pytest + ruff:

```yaml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      - name: Lint
        run: ruff check
      - name: Test
        run: pytest tests/ -q --tb=short
```

### 3. [NEW] `docs/mcp-setup.md`

MCP 客户端配置指南:

```markdown
# Memory Palace MCP 配置指南

## Claude Desktop

在 `claude_desktop_config.json` 中添加:
{
  "mcpServers": {
    "memory-palace": {
      "command": "palace-mcp",
      "env": { "OPENAI_API_KEY": "sk-..." }
    }
  }
}

## Cursor
... (类似配置)

## HTTP 模式
palace serve --transport http --port 8765
```

### 4. [NEW] `tests/test_e2e/test_mcp_e2e.py`

```
test_full_mcp_lifecycle — 
    MCP Client: save → search → update → forget → curate → verify

test_mcp_context_compilation — 
    save 几条 → get_context → 验证格式含 [CORE] [RETRIEVED] 段

test_mcp_health_and_stats — 
    save 几条 → get_health → 验证 5 维度 → get_stats → 验证计数

test_mcp_with_scheduler_notify —
    save via MCP → 验证 scheduler 被 notify（如集成了 scheduler）

test_mcp_audit_trail —
    save → update → forget → get_audit_log → 验证操作链完整

test_mcp_error_handling_e2e —
    forget 不存在的 ID → 验证返回格式正确
```

预计 ~6 tests。

### 5. [MODIFY] `tests/test_integration/test_cli.py`

- `test_serve_help` — `palace serve --help` 不报错
- 预计 +1 test

---

## 约束

1. CI 只测 `[dev]` 依赖，不安装 `[local]` (sentence-transformers 太重)
2. CI 不需要 API key — 所有 LLM 测试使用 MockLLM
3. `docs/` 目录是新建的，只放 markdown 文档
4. `serve` 命令的 HTTP 模式允许但不强制测试

---

## Phase B 完成标准

```bash
pytest tests/ -q                  # 全部绿 (~363 tests)
ruff check
cat .github/workflows/ci.yml     # CI 配置存在
palace serve --help               # 命令可用
palace-mcp --help                 # entry point 可用
```

---

## 验证

```bash
pytest tests/ -q
pytest tests/test_e2e/test_mcp_e2e.py -v
ruff check
git commit -m "feat(R20): Phase B integration — CLI serve + CI + MCP E2E"
```
