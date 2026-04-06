# Stanford Generative Agents

> **启发了**：ScoringEngine（三因子检索评分公式）

## 是什么

斯坦福 2023 年发表的经典论文，模拟了 25 个 AI 小镇居民的生活。
每个 Agent 拥有记忆流（Memory Stream），用三因子公式检索最相关的记忆：

```
score = α · recency + β · importance + γ · relevance
```

- **引用量**：4781+ 次（截至 2026 年）
- **业界影响**：几乎所有 Agent 记忆系统都借鉴了这个公式

## 我们借鉴了什么

| Generative Agents | Memory Palace 对应 | 差异 |
|-------------------|-------------------|------|
| Recency（新鲜度） | ScoringEngine.recency | 我们用指数衰减 `exp(-λ·Δt)` |
| Importance（重要性） | ScoringEngine.importance | LLM 在提取时赋值 [0,1] |
| Relevance（相关性） | ScoringEngine.relevance | v0.1 用 FTS5 关键词，v0.2 加向量余弦 |
| — | **Proximity（邻近性）** | 🆕 **我们原创的第四因子**——同一 Room 的记忆加权 |

## 关键参考文档

```yaml
- paper: https://arxiv.org/abs/2304.03442
  why: "Generative Agents: Interactive Simulacra of Human Behavior"
  section: "§5.2 Retrieval" — 三因子公式的完整定义和权重推导

- repo: https://github.com/joonspk-research/generative_agents
  why: 参考实现，特别是 retrieval/scoring 部分
  critical: 注意原论文的 recency 用的是 game-time hours，我们用 real-time hours
```
