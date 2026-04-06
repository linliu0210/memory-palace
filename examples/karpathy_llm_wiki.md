# Karpathy LLM Wiki

> **启发了**：Core Memory 作为"活 Wiki"、Query Write-back、Curator 的 Lint 操作

## 是什么

Andrej Karpathy（前特斯拉 AI 总监、OpenAI 创始成员）在 2025 年底提出的
LLM Wiki 模式。核心观点：

> *"Obsidian is the IDE, LLM is the programmer, Wiki is the codebase."*

LLM 不再只是"回答问题"，而是**持续维护一个知识库**：
- 知识编译一次（compiled once），然后持续更新（kept current）
- 每次查询不是从零推导（re-derive），而是查已编译的知识
- LLM 负责所有簿记工作（bookkeeping），用户只需要读

## 我们借鉴了什么

| Karpathy 概念 | Memory Palace 对应 | 差异 |
|-------------|-------------------|------|
| Wiki = compiled knowledge | Core Store 作为"活 Wiki" | 核心相同 |
| LLM does bookkeeping | Curator 搬运小人职责 | 我们更系统化（7 步流程） |
| Lint 操作 | Curator 健康检查 | 自动化 + Health Score 量化 |
| Query Write-back | Retriever 好答案回写 | **v0.2 实现** |
| `log.md` 时间线 | AuditLog JSONL | 同理，不可篡改的操作日志 |

## 关键参考文档

```yaml
- video: https://www.youtube.com/watch?v=FJkLJvRGNyg
  why: Karpathy 的 "LLM Wiki" 完整讲解
  critical: 重点看 "compiled knowledge" 和 "lint operations" 部分

- tweet: https://x.com/karpathy/status/1882185704237945036
  why: 原始推文，精炼阐述 Wiki 理念

- blog: https://karpathy.ai
  why: 关于 AI 记忆管理的思考文章
```
