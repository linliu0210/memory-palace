# Claude Code Auto-Dream

> **启发了**：CuratorService（搬运小人）的「梦境」整理机制

## 是什么

Anthropic 在 Claude Code 中悄悄上线的功能。在 Agent 空闲时，
系统会执行一次 **"dream"** — 对 MEMORY.md 文件做一次反思性整理：

> *"You are performing a dream — a reflective pass over your memory files.
> Review them for accuracy, freshness, and relevance."*

关键设计：
- 触发条件：Agent 空闲或 session 结束时
- 操作：扫描 MEMORY.md，去除过时信息，合并重复记忆，标记矛盾
- 输出：更新后的 MEMORY.md

## 我们借鉴了什么

| Auto-Dream | Memory Palace 对应 | 差异 |
|-----------|-------------------|------|
| 整理 MEMORY.md | Curator 7 步巡检流程 | 我们分成 7 个独立步骤，更系统 |
| Reflective pass | Curator Step 4: Reflect | 我们有独立的 Reflection Engine |
| Accuracy check | Curator Step 3: Reconcile | 用 ReconcileEngine 做判断 |
| Freshness check | Curator Step 5: Prune | 用衰减公式量化 |
| 单文件操作 | 多层存储 + 结构化数据 | **我们的差异点**：不依赖单一文件 |

## 关键参考文档

```yaml
- source: Claude Code 内部 prompt（逆向工程）
  why: Auto-Dream 的原始提示词
  critical: "dream" 比喻来自 REM 睡眠——大脑在深睡眠中整合白天的记忆

- docs: https://docs.anthropic.com/en/docs/claude-code/memory
  why: Claude Code MEMORY.md 官方文档
  section: "Memory Management" — 200 行上限、自动整理触发条件

- thread: https://x.com/skirano/status/1867650037818749039
  why: Simon Willison 对 Auto-Dream 机制的分析
```
