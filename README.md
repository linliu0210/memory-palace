# 🏛️ Memory Palace

> 给 AI 装一套「记忆操作系统」——不只让它记得住，而是让它**自己整理、自己归纳、自己遗忘**，越用越聪明。

## What

Memory Palace 是一个 Python library，可被任意 AI Agent 框架集成。它提供：

- **三层存储引擎** — Core（随身口袋）→ Recall（抽屉柜）→ Archival（地下室）
- **四因子混合检索** — 新鲜度 × 重要性 × 相关性 × 空间邻近性
- **搬运小人 (Curator)** — 自动整理、去重、冲突调和、渐进遗忘
- **全程审计日志** — 每次操作不可篡改记录

## Quick Start

```bash
# 克隆 & 安装
git clone <repo-url>
cd memory-palace
uv sync --extra dev

# 运行测试（当前为 TDD RED 状态）
uv run pytest tests/ -q

# 验证包可导入
uv run python -c "import memory_palace; print(memory_palace.__version__)"
```

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

## Documentation

| 文档 | 内容 |
|------|------|
| [SPEC v2.0](SPEC.md) | 完整技术规格——数据模型、接口契约、Prompt 模板 |
| [CONVENTIONS.md](CONVENTIONS.md) | 代码约定——TDD 纪律、分层规则、Gotchas |
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | 项目全貌——模块状态、版本规划、测试 baseline |

## Version Roadmap

| 版本 | 代号 | 核心交付 |
|------|------|---------|
| **v0.1** 🦴 | Skeleton | Pipeline 跑通；全构件就位；两层存储 |
| **v0.2** 🧱 | Foundation | 三层存储；混合检索；Curator 自动化+反思 |
| **v1.0** 🏛️ | Palace | Sleep-time 自动化；空间邻近性；监控仪表盘 |

## Inspirations

详见 [`examples/`](examples/) 目录，记录了启发本项目设计的所有灵感来源和参考文档。

## License

MIT
