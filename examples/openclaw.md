# OpenClaw Auto-Dream

> **启发了**：CuratorService 的反思与洞察生成、Health Score 健康评分

## 是什么

OpenClaw 是 Claude Code Auto-Dream 的第一个开源复现项目（624 Stars）。
它不仅复现了基础的记忆整理，还扩展了**洞察生成**功能：

搬运小人不只打扫卫生——它还会发现模式，主动生成洞察：
> *"我发现你最近三个项目的策略模式很像当年 Project X 的成功模式"*

核心概念：**整理工 → 认知管家**。

## 我们借鉴了什么

| OpenClaw | Memory Palace 对应 | 差异 |
|---------|-------------------|------|
| Dream insights | Curator Step 4: Reflect [v0.2] | v0.1 先跳过，v0.2 实现洞察 |
| Health scoring | CuratorReport.health_* | v0.1 简化为 freshness + efficiency |
| Memory decay | 指数衰减 `exp(-λ·Δt)` | 来自 Ebbinghaus 遗忘曲线，OpenClaw 的实现启发了我们 |
| Trigger modes | 定时 / 会话累积 / 手动 | 完全采纳 OpenClaw 的三触发模式 |

## 关键参考文档

```yaml
- repo: https://github.com/AiAutoTool/OpenClaw
  why: Auto-Dream 的开源实现
  stars: 624
  critical: 重点看 dream/ 目录的 insight_generator 和 health_checker

- file: src/dream/insight_generator.py
  why: 洞察生成的 prompt 设计和 pattern detection 逻辑

- file: src/dream/health_checker.py
  why: Health Score 的五维度评估模型（freshness, coverage, coherence, efficiency, connectivity）
```
