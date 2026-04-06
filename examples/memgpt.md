# MemGPT / Letta

> **启发了**：五层分层架构、三层存储分级（Core / Recall / Archival）

## 是什么

MemGPT（现更名 Letta）是第一个将操作系统内存管理类比引入 LLM Agent 的项目。
它把 Agent 的记忆分为 RAM（始终加载）→ Cache（按需检索）→ Disk（持久存储），
让 LLM 自己管理上下文窗口，实现了"无限上下文"的效果。

- **生产验证**：100 万+ Agent 实例在 Letta Cloud 运行
- **核心论文**：*MemGPT: Towards LLMs as Operating Systems* (2023)

## 我们借鉴了什么

| MemGPT 概念 | Memory Palace 对应 | 差异 |
|-------------|-------------------|------|
| Main Context (RAM) | Core Store（随身口袋） | 我们限制 ≤200 条 + 预算降级 |
| Recall Storage (Cache) | Recall Store（抽屉柜） | 我们用 SQLite+FTS5 而非 PostgreSQL |
| Archival Storage (Disk) | Archival Store（地下室）[v0.2] | 推迟到 v0.2，v0.1 用 Recall 兼顾 |
| OS-level memory management | 五层分层架构 | 我们的层级更细（5 层 vs 3 层） |

## 关键参考文档

```yaml
- repo: https://github.com/letta-ai/letta
  why: 核心架构、Agent Memory 管理模式
  stars: 14K+

- paper: https://arxiv.org/abs/2310.08560
  why: MemGPT 原始论文，OS 类比的理论基础

- docs: https://docs.letta.com/
  why: Letta 官方文档，特别是 Memory Management 章节
  section: "Core Memory", "Recall Memory", "Archival Memory"
```
