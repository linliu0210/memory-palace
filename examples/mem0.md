# Mem0

> **启发了**：FactExtractor（原子事实提取）、ReconcileEngine（冲突调和）、MemoryService 四操作 CRUD

## 是什么

Mem0 是 YC 孵化的开源记忆层，GitHub 25K+ Stars。它的核心创新是
用 LLM 提取"原子事实"（atomic facts），然后通过 LLM 判断新旧记忆的冲突关系
（ADD / UPDATE / DELETE / NO-OP），实现了比传统 RAG 更精准的记忆管理。

## 我们借鉴了什么

| Mem0 概念 | Memory Palace 对应 | 差异 |
|----------|-------------------|------|
| Atomic Fact Extraction | FactExtractor（3F Engine） | 相同模式，LLM 提取原子事实 |
| Memory Reconciliation | ReconcileEngine（3F Engine） | 相同 4 种判决（ADD/UPDATE/DELETE/NO-OP） |
| save/search/update/forget | MemoryService（4F Service） | 相同 4 操作 API |
| 即时冲突解决 | 可延迟到 Curator 批量处理 | **我们的差异点**：离线批量更高效 |

## 关键参考文档

```yaml
- repo: https://github.com/mem0ai/mem0
  why: 核心 pipeline 架构，特别是 memory/core.py
  stars: 25K+

- docs: https://docs.mem0.ai/
  why: 官方文档，特别是 "How Mem0 Works" 和 "Memory Operations"
  section: "Add Memory", "Search Memory", "Memory Update"

- file: mem0/memory/core.py
  why: add_memory / search / update 的实现模式
  critical: 注意 Mem0 的 reconcile 是即时的，我们的可以延迟
```
