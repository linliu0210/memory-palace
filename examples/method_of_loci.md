# Method of Loci（位点记忆法）

> **启发了**：第四因子「空间邻近性」、Room 数据模型、整个"记忆宫殿"隐喻

## 是什么

Method of Loci 是古希腊发明的记忆术（公元前 500 年），也是"记忆宫殿"的原始含义：

1. 在脑中构建一个**熟悉的空间**（比如你家）
2. 在每个位置**放置**要记忆的东西（客厅放数学公式，厨房放历史人物）
3. 回忆时**在脑中走一遍路线**，沿途"看到"每个位置的内容

核心认知科学原理：**空间记忆比语义记忆更持久**。
人类大脑的海马体同时负责空间导航和记忆编码——这不是巧合。

## 我们借鉴了什么

| 认知科学概念 | Memory Palace 对应 | 差异 |
|------------|-------------------|------|
| Loci（位置） | Room 数据模型 | 我们的 Room 是软标签，不是物理位置 |
| 空间邻近性 | ScoringEngine 第四因子 Proximity | 同一 Room 的记忆查询时加权 |
| 路线遍历 | Retriever 按 Room 分组返回 | 搜索结果按"房间"组织 |
| 宫殿整体隐喻 | 项目名 "Memory Palace" | 不只是名字——是核心设计哲学 |

## 为什么这是我们的核心差异点

几乎所有竞品（ChatGPT Memory、Mem0、Claude MEMORY.md）都把记忆存成**平铺列表**。
我们是唯一一个用**空间结构**组织记忆的系统：

- 同一个"房间"里的记忆天然更相关
- "走过"的路径就是知识之间的关联
- 空间感让记忆更直觉、更易检索

## 关键参考文档

```yaml
- paper: "The Method of Loci as a Mnemonic Device"
  author: Verhaeghen & Kliegl (2000)
  why: 记忆宫殿的认知科学基础

- book: "Moonwalking with Einstein" by Joshua Foer
  why: 记忆冠军如何使用记忆宫殿——最佳通俗读物

- wikipedia: https://en.wikipedia.org/wiki/Method_of_loci
  why: 快速概览，含历史背景

- paper: "Hippocampal involvement in spatial and episodic memory"
  why: 海马体同时负责空间和记忆的神经科学证据
  critical: 这解释了为什么空间组织的记忆比列表更好检索
```
