# Examples & Inspirations

> 本目录记录启发 Memory Palace 设计的所有灵感来源项目和参考文档。
> 每个子文件对应一个灵感源，包含：**是什么 → 启发了什么 → 关键文档链接**。

## 灵感源索引

| 灵感源 | 启发了什么 | 文件 |
|--------|-----------|------|
| **MemGPT / Letta** | 五层 OS 类比、三层存储分级 | [memgpt.md](memgpt.md) |
| **Mem0** | 原子事实提取、冲突调和、四操作 CRUD | [mem0.md](mem0.md) |
| **Stanford Generative Agents** | 三因子检索评分 (Recency × Importance × Relevance) | [generative_agents.md](generative_agents.md) |
| **Karpathy LLM Wiki** | Core Memory 作为活 Wiki、Query Write-back、Lint 操作 | [karpathy_llm_wiki.md](karpathy_llm_wiki.md) |
| **Claude Code Auto-Dream** | 搬运小人的「梦境」整理机制 | [auto_dream.md](auto_dream.md) |
| **OpenClaw Auto-Dream** | 搬运小人的反思与洞察生成 | [openclaw.md](openclaw.md) |
| **DreamEngine** | LLM Provider Protocol 抽象模式 | [dreamengine.md](dreamengine.md) |
| **Method of Loci** | 第四因子「空间邻近性」、Room 概念 | [method_of_loci.md](method_of_loci.md) |

## 如何使用

Agent 在实现某个模块前，应阅读该模块对应的灵感源文档，理解设计决策的 **why**：

```
实现 ScoringEngine → 读 generative_agents.md（三因子公式）
实现 CuratorService → 读 auto_dream.md + openclaw.md（梦境整理）
实现 CoreStore     → 读 karpathy_llm_wiki.md（活 Wiki 模式）
实现 FactExtractor → 读 mem0.md（原子事实提取 pipeline）
实现 LLMProvider   → 读 dreamengine.md（Provider Protocol）
```
