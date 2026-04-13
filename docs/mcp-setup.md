# Memory Palace MCP 配置指南

Memory Palace 提供 MCP (Model Context Protocol) 接口，让 AI 助手直接管理你的记忆宫殿。

## Claude Desktop

在 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "memory-palace": {
      "command": "palace-mcp",
      "env": {
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

配置文件位置：
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

## Cursor

在 Cursor Settings → MCP 中添加：

```json
{
  "mcpServers": {
    "memory-palace": {
      "command": "palace-mcp",
      "env": {
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

## HTTP 模式

如需通过 HTTP 提供服务（多客户端共享）：

```bash
palace serve --transport http --host localhost --port 8765
```

客户端连接地址：`http://localhost:8765/mcp`

## CLI 模式

默认使用 stdio 传输协议：

```bash
palace serve
```

## 可用工具

MCP Server 提供 12 个工具：

| 工具 | 说明 |
|------|------|
| `save_memory` | 保存新记忆 |
| `search_memory` | 搜索记忆 |
| `update_memory` | 更新记忆（版本化） |
| `forget_memory` | 软删除记忆 |
| `inspect_memory` | 查看记忆详情 |
| `curate_now` | 手动触发搬运小人（需 LLM） |
| `reflect_now` | 生成反思洞察（需 LLM） |
| `get_health` | 5 维健康评估 |
| `list_rooms` | 列出房间 |
| `get_stats` | 统计概览 |
| `get_audit_log` | 审计日志 |
| `get_context` | 编译上下文 |

## 可用资源

6 个只读资源：

| URI | 说明 |
|-----|------|
| `palace://health` | 实时健康评估 |
| `palace://stats` | 统计概览 |
| `palace://rooms` | 房间列表 |
| `palace://context/{query}` | 编译上下文 |
| `palace://memory/{id}` | 单条记忆 |
| `palace://audit` | 审计日志 |

## 数据目录

默认数据目录为 `~/.memory_palace`。可通过 LLM 配置文件 `~/.memory_palace/memory_palace.yaml` 自定义 LLM 设置。
