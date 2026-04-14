# 🏛️ Memory Palace

> 给 AI 装一套「记忆操作系统」——不只让它记得住，而是让它**自己整理、自己归纳、自己遗忘**，越用越聪明。

## What

Memory Palace 是一个 Python library，可被任意 AI Agent 框架集成。它提供：

- **三层存储引擎** — Core（随身口袋）→ Recall（抽屉柜）→ Archival（地下室）
- **四因子混合检索** — 新鲜度 × 重要性 × 相关性 × 空间邻近性
- **搬运小人 (Curator)** — 自动整理、去重、冲突调和、渐进遗忘
- **5-pass 智能摄取** — 文档 → 事实提取 → 冲突调和 → 关系抽取 → 存储
- **双通道接入** — CLI (`palace`) + MCP Server (`palace-mcp`)
- **全程审计日志** — 每次操作不可篡改记录

---

## 安装

```bash
git clone <repo-url>
cd memory-palace
uv sync --extra dev

# 验证安装
palace --help
python -c "import memory_palace; print(memory_palace.__version__)"
```

如需图存储（KuzuDB）：

```bash
uv sync --extra graph
```

---

## 快速开始

### 1. 配置 LLM

Memory Palace 支持任何 OpenAI 兼容 API。通过环境变量配置：

```bash
# ── MiniMax（推荐）──────────────────────────
export MINIMAX_API_KEY="sk-cp-..."
export MP_LLM__PROVIDER="minimax"
export MP_LLM__MODEL_ID="MiniMax-M2.5"
export MP_LLM__BASE_URL="https://api.minimaxi.com/v1"
#                          ↑ 注意是 minimaxi（多一个 i）

# ── OpenAI ──────────────────────────────────
export OPENAI_API_KEY="sk-..."
# 默认即 openai/gpt-4o-mini，无需额外设置

# ── DeepSeek ────────────────────────────────
export DEEPSEEK_API_KEY="sk-..."
export MP_LLM__PROVIDER="deepseek"
export MP_LLM__MODEL_ID="deepseek-chat"
export MP_LLM__BASE_URL="https://api.deepseek.com/v1"
```

也可以通过 YAML 配置文件（放在数据目录下）：

```yaml
# ~/.memory_palace/memory_palace.yaml
memory_palace:
  llm:
    provider: minimax
    model_id: MiniMax-M2.5
    base_url: https://api.minimaxi.com/v1
    max_tokens: 2000
```

> **优先级**：环境变量 > YAML > 内置默认值

### 2. CLI 基本操作

```bash
# 保存记忆
palace save "我最喜欢的编程语言是 Python，最近在学 Rust" \
  --importance 0.8 --room preferences --tags "编程,语言"

# 搜索
palace search "Python"

# 智能摄取文档（需要 LLM）
palace ingest meeting_notes.txt

# 查看概览
palace inspect

# 手动触发整理（需要 LLM）
palace curate

# 启动 MCP Server
palace serve
```

### 3. MCP Server 接入

启动 MCP 服务后，AI Agent 可通过 JSON-RPC 协议调用 18 个工具：

```bash
# stdio 模式（Codex / Claude Desktop / Cursor 等）
palace serve

# 或直接用入口点
palace-mcp
```

`palace-mcp` 与 `palace serve` 在 `stdio` 模式下会默认关闭 banner 和常规运行日志，
避免把非 JSON-RPC 输出写进协议流；对 `Codex`、Claude Desktop、Cursor 这类 stdio 客户端，
不需要额外 wrapper。

**Claude Desktop 配置** (`claude_desktop_config.json`)：

```json
{
  "mcpServers": {
    "memory-palace": {
      "command": "palace-mcp",
      "env": {
        "MINIMAX_API_KEY": "sk-cp-...",
        "MP_LLM__PROVIDER": "minimax",
        "MP_LLM__MODEL_ID": "MiniMax-M2.5",
        "MP_LLM__BASE_URL": "https://api.minimaxi.com/v1"
      }
    }
  }
}
```

`Codex` / `Cursor` 也可直接使用同样的 stdio 入口。只有在 `HTTP` 模式下，服务端才会保留
人类可读的启动输出；`stdio` 模式默认按协议安全优先处理。

---

## Architecture

```
╔══════════════════════════════════════════════════════════╗
║  5F  Integration    — CLI / Python API / MCP [v1.0]     ║
╠══════════════════════════════════════════════════════════╣
║  4F  Service        — MemoryService │ Retriever │ Curator║
╠══════════════════════════════════════════════════════════╣
║  3F  Engine         — FactExtractor │ Scoring │ Reconcile║
╠══════════════════════════════════════════════════════════╣
║  2F  Storage        — CoreStore │ RecallStore │ Archival ║
╠══════════════════════════════════════════════════════════╣
║  1F  Foundation     — Config │ AuditLog │ LLM │ Embedding║
╚══════════════════════════════════════════════════════════╝
```

### 三层存储

| 层 | 实现 | 说明 | 路由规则 |
|----|------|------|----------|
| **Core** | JSON 文件 | 随身口袋，预算受限 (2KB) | importance ≥ 0.7 |
| **Recall** | SQLite FTS5 | 抽屉柜，全文检索 | importance < 0.7 |
| **Archival** | ChromaDB | 地下室，向量语义搜索 | 所有记忆同步写入 |

### 混合检索

```
search_sync(query)  →  Core 关键字匹配 + Recall FTS5  →  按 importance 排序
search(query)       →  FTS5 + Vector(Archival) RRF 融合  →  四因子评分
```

---

## CLI 命令参考

| 命令 | 说明 | 需要 LLM |
|------|------|:--------:|
| `palace save` | 保存一条记忆 | |
| `palace search` | 搜索记忆 | |
| `palace update` | 更新一条记忆（版本递增） | |
| `palace forget` | 软删除一条记忆 | |
| `palace inspect` | 查看概览或单条详情 | |
| `palace audit` | 查看审计日志 | |
| `palace rooms` | 列出所有房间 | |
| `palace metrics` | 查看运营指标 | |
| `palace ingest` | 5-pass 智能摄取文档 | ✅ |
| `palace curate` | 手动触发搬运小人 | ✅ |
| `palace import` | 批量导入（.md / .jsonl） | |
| `palace export` | 批量导出 | |
| `palace serve` | 启动 MCP Server | |
| `palace persona list/create/switch/delete` | 多角色管理 | |
| `palace schedule start/status` | Sleep-time 调度 | ✅ |

所有命令支持 `--data-dir` 指定数据目录（默认 `~/.memory_palace`）。

---

## MCP 工具参考

| 工具 | 说明 |
|------|------|
| `save_memory` | 保存记忆（content, importance, room, tags） |
| `search_memory` | 搜索记忆（query, top_k, room） |
| `update_memory` | 更新记忆内容 |
| `forget_memory` | 软删除 |
| `inspect_memory` | 查看单条详情 |
| `curate_now` | 触发 Curator 整理 |
| `reflect_now` | 生成高阶反思 |
| `ingest_document` | 5-pass 智能摄取 |
| `get_health` | 6 维健康评估 |
| `get_stats` | 统计概览（Core/Recall 数量） |
| `get_context` | 编译结构化上下文 |
| `get_audit_log` | 审计日志 |
| `get_metrics` | 运营指标 |
| `list_rooms` | 房间列表 |
| `import_memories` | 批量导入 |
| `export_memories` | 批量导出 |
| `list_personas` | Persona 列表 |
| `switch_persona` | 切换 Persona |

MCP 资源（`palace://` 协议）：`health`、`stats`、`rooms`、`context/{query}`、`memory/{id}`、`audit`、`personas`、`metrics`。

---

## 配置参考

### 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `MP_LLM__PROVIDER` | LLM 供应商 | `minimax` / `openai` / `deepseek` |
| `MP_LLM__MODEL_ID` | 模型名称 | `MiniMax-M2.5` / `gpt-4o-mini` |
| `MP_LLM__BASE_URL` | API 地址 | `https://api.minimaxi.com/v1` |
| `MP_LLM__MAX_TOKENS` | 最大输出 token | `2000` |
| `MINIMAX_API_KEY` | MiniMax API Key | `sk-cp-...` |
| `OPENAI_API_KEY` | OpenAI API Key | `sk-...` |
| `DEEPSEEK_API_KEY` | DeepSeek API Key | `sk-...` |

> API Key 解析规则：`{PROVIDER}_API_KEY`（如 provider=`foo` → 读 `FOO_API_KEY`）

### YAML 完整示例

```yaml
# memory_palace.yaml
memory_palace:
  llm:
    provider: minimax
    model_id: MiniMax-M2.5
    base_url: https://api.minimaxi.com/v1
    max_tokens: 2000

  embedding:
    provider: openai          # openai / local
    model_id: text-embedding-3-small
    dimension: 1536

  storage:
    base_dir: ./data

  core:
    max_bytes: 2048

  scoring:
    recency: 0.20
    importance: 0.20
    relevance: 0.50
    room_bonus: 0.10

  graph:
    enabled: false

  curator:
    trigger:
      timer_hours: 24
      session_count: 20
      cooldown_hours: 1

  ebbinghaus:
    enabled: true
    base_stability_hours: 168   # 7 天

  rooms:
    - name: general
      description: 未分类通用记忆
    - name: preferences
      description: 用户偏好
    - name: projects
      description: 项目知识
    - name: people
      description: 人物关系
    - name: skills
      description: 技能记忆
```

---

## MiniMax 配置说明

Memory Palace 内置支持 MiniMax 推理模型，已处理以下兼容性问题：

| 问题 | 处理方式 |
|------|----------|
| `<think>` 思考标签 | 在 `OpenAIProvider` 层自动剥离输出中的 `<think>...</think>` |
| Markdown 代码围栏 | 自动剥离 ` ```json ... ``` ` 包裹 |
| 不支持 `response_format: json_object` | 自动按 provider 跳过该参数 |
| Base URL 特殊 | 必须用 `api.minimaxi.com`（不是 `api.minimax.chat`） |

> **注意**：LLM 仍然完整执行推理（thinking），只是返回文本中的 `<think>` 标签被剥离，不影响推理质量。

---

## Python API

```python
from pathlib import Path
from memory_palace.service.memory_service import MemoryService
from memory_palace.foundation.llm import ModelConfig
from memory_palace.foundation.openai_provider import OpenAIProvider

# 构建 LLM
llm = OpenAIProvider(ModelConfig(
    provider="minimax",
    model_id="MiniMax-M2.5",
    base_url="https://api.minimaxi.com/v1",
))

# 初始化服务
svc = MemoryService(Path("./data"), llm=llm)

# CRUD
item = svc.save(content="Python 是我最常用的语言", importance=0.8, room="preferences")
results = svc.search_sync("Python", top_k=5)
svc.update(item.id, "Python 和 Rust 是我最常用的语言", reason="更新")
svc.forget(item.id, reason="不再需要")

# 异步搜索（FTS5 + Vector 混合）
import asyncio
results = asyncio.run(svc.search("Python", top_k=5))

# 统计
stats = svc.stats()  # {"core_count": ..., "recall_count": ..., "total": ...}
```

---

## 测试

```bash
# 全量测试（Mock LLM，无需 API Key）
uv run pytest tests/ -q

# 跳过真实 LLM 测试
uv run pytest tests/ -m "not real_llm" -q

# 仅运行 MiniMax 真实 LLM 测试（需设置 MINIMAX_API_KEY）
uv run pytest tests/test_e2e/test_minimax_real.py -v

# Lint
uv run ruff check src/ tests/
```

---

## Documentation

| 文档 | 内容 |
|------|------|
| [SPEC v2.0](SPEC.md) | 完整技术规格——数据模型、接口契约、Prompt 模板 |
| [CONVENTIONS.md](CONVENTIONS.md) | 代码约定——TDD 纪律、分层规则、Gotchas |
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | 项目全貌——模块状态、版本规划、测试 baseline |

## License

MIT
