# 🏛️ Memory Palace v0.2 — 开发者教学指南

> **写给谁**: Python 基础较弱、但想完全理解这个项目的开发者  
> **前置阅读**: [NAVIGATION.md](NAVIGATION.md)（项目导航）  
> **版本**: v0.2.0 (284 tests, 42 files, ~4400 lines)  
> **Date**: 2026-04-12

---

## 📖 目录

| 章 | 标题 | 你会学到 |
|---|------|---------|
| [1](#1-v01-回顾你已经有什么) | v0.1 回顾：你已经有什么 | 快速回忆 v0.1 的架构和能力边界 |
| [2](#2-为什么要做-v02开发者遇到的真实问题) | 为什么要做 v0.2：开发者遇到的真实问题 | 4 个痛点 → 4 个改进方向 |
| [3](#3-v02-全景图spec_v02md-导读) | v0.2 全景图：SPEC_V02.md 导读 | 看懂 spec，知道做了什么以及为什么 |
| [4](#4-架构升级五层楼的装修) | 架构升级：五层楼的装修 | 每一层改了什么，新增了什么 |
| [5](#5-数据流一条记忆的完整生命周期) | 数据流：一条记忆的完整生命周期 | 从 `save()` 到 `search()` 到 `curate()` 的全流程 |
| [6](#6-逐文件拆解每个脚本做了什么) | 逐文件拆解：每个脚本做了什么 | 16 个新文件、12 个修改文件的逐一讲解 |
| [7](#7-核心设计模式为什么这么写) | 核心设计模式：为什么这么写 | Protocol、纯函数、状态机等模式的通俗解释 |
| [8](#8-关键决策复盘做过的取舍) | 关键决策复盘：做过的取舍 | LangGraph 被拒、KuzuDB 延迟等设计选择 |
| [9](#9-技术债从-v01-继承的问题怎么解决的) | 技术债：从 v0.1 继承的问题怎么解决的 | 7 个债务的产生原因和修复方式 |
| [10](#10-测试策略怎么保证改了不出事) | 测试策略：怎么保证改了不出事 | 284 个测试的分层逻辑和 Mock 策略 |
| [11](#11-hands-on-动手跟着走一遍) | Hands-on：动手跟着走一遍 | 本地运行、CLI 操作、读测试的实操 |
| [12](#12-v10-前瞻下一步去哪里) | v1.0 前瞻：下一步去哪里 | 未来功能和你可以贡献的方向 |

---

## 1. v0.1 回顾：你已经有什么

> 如果你还没读过 v0.1 的资料，请先看 [NAVIGATION.md](NAVIGATION.md)。这里只做快速回顾。

### 1.1 一句话定位

Memory Palace 是给 **AI Agent 装的记忆操作系统**。普通聊天机器人聊完就忘，Memory Palace 让 Agent 能记住、能整理、能遗忘。

### 1.2 v0.1 的核心结构 — 五层建筑

把它想象成一栋五层商业大楼，每层做不同的事：

```
🏢 Memory Palace 大厦

5F 接待层 (Integration)    ← 和外界打交道：CLI 命令行
4F 管家层 (Service)         ← 协调所有工作：保存、搜索、整理
3F 引擎层 (Engine)          ← 做脑力活：评分、提取事实、调和冲突
2F 存储层 (Store)           ← 放东西：JSON 文件(重要的)、SQLite 数据库(一般的)
1F 基建层 (Foundation)      ← 水电煤：日志、LLM 连接、配置
```

**严格规矩：高层可以调用低层，低层绝不能反过来调用高层。** 就像公司里 CEO 可以找部门经理要数据，但部门经理不能指挥 CEO。

### 1.3 v0.1 能做什么

```bash
palace save "用户喜欢深色模式" --importance 0.9 --room preferences
palace search "界面偏好"
palace curate    # AI 自动整理记忆
palace inspect   # 查看所有记忆
```

### 1.4 v0.1 的两层存储

```
重要性 ≥ 0.7  →  CoreStore  (JSON 文件，就像你口袋里的便签纸)
重要性 < 0.7  →  RecallStore (SQLite 数据库，就像你的笔记本)
```

### 1.5 v0.1 的搜索方式 — 纯关键词

v0.1 用的是 **FTS5 (Full-Text Search)**，本质上就是关键词搜索。你搜「深色模式」，只有内容里包含「深色」或「模式」这几个字的记忆才会被找到。

**这是 v0.1 最大的局限**——下一章会详细讲。

---

## 2. 为什么要做 v0.2：开发者遇到的真实问题

> v0.2 不是拍脑袋做的。是 v0.1 用着用着，发现了 4 个真实痛点。

### 痛点 1：搜不到该搜的 — 「关键词匹配的局限」

**场景**：你存了一条记忆 `"用户偏好 Python 而不是 Java"`。你搜 `"编程语言偏好"`。

**v0.1 结果**：❌ 搜不到。因为 FTS5 关键词搜索要求词要匹配，「编程语言偏好」这几个字在内容里一个都没出现。

**v0.2 解法**：引入**向量搜索（Embedding）**——把文字转成数学向量，算语义相似度。「Python vs Java」和「编程语言偏好」在语义空间里很近。

```
v0.1：搜索 ≈ Ctrl+F（找字面匹配）
v0.2：搜索 ≈ 大脑联想（找含义匹配）
```

### 痛点 2：只存不整理 — 「缺少高阶思考」

**场景**：Agent 连续存了这些记忆：
1. "用户今天 deadline 来不及"
2. "用户上周任务也延期了"
3. "用户说总是低估工作量"

**v0.1 结果**：三条记忆老老实实存着，但系统不会自动发现它们有共同模式。

**v0.2 解法**：新增 **ReflectionEngine（反思引擎）**——让 LLM 读一批近期记忆，生成高阶洞察：

> **Insight**: "用户有持续性的时间管理困难。有过 3 次延期记录，自述低估工作量。建议后续交互中主动建议拆分任务。"

这条洞察会作为新记忆存入系统（类型 = REFLECTION），下次搜索时能命中。

### 痛点 3：不知道健不健康 — 「没有体检报告」

**场景**：系统运行一个月了，里面存了 200 条记忆。但你完全不知道：
- 有多少记忆已经过期没人引用了？（新鲜度）
- Core（重要记忆区）是不是塞满了废弃内容？（效率）
- 所有记忆是不是都集中在一个房间？（覆盖率）
- 记忆类型是不是全是 observation、没有 reflection？（多样性）

**v0.2 解法**：新增 **MemoryHealthScore（5 维度健康评分）**，像体检报告一样打分。

### 痛点 4：整理流程不够自动化 — 「管家太笨」

**场景**：v0.1 的 Curator（搬运小人）只会做简单的 3 步：收集 → 提取事实 → 调和冲突。

**v0.2 解法**：升级为 **7 步全流程状态机**：

```
收集(GATHER) → 提取(EXTRACT) → 调和(RECONCILE) → 反思(REFLECT) 
→ 修剪(PRUNE) → 体检(HEALTH_CHECK) → 报告(REPORT)
```

新增了 **反思**（自动生成洞察）、**修剪**（删低价值记忆）、**体检**（健康评分）三步。

---

## 3. v0.2 全景图：SPEC_V02.md 导读

> [SPEC_V02.md](SPEC_V02.md) 是 v0.2 的完整技术规格书。这里用大白话解释每一节。

### 3.1 文档结构速览

| 节 | 在说什么 | 一句话总结 |
|---|---------|-----------|
| §0 版本定位 | v0.1→v0.2 升了什么 | 两层变三层，关键词变语义，手动变自动 |
| §1 差异决策 | 跟原始 SPEC 有什么不同 | 砍了图数据库、降级了评分公式、拒了 LangGraph |
| §2 新增组件 | 新建了哪些类/文件 | 6 个新组件，按层分类 |
| §3 改动影响 | 改了 v0.1 的哪些文件 | 12 个文件被修改，7 个技术债被修 |
| §4-§5 依赖+目录 | 装了什么新库、文件放哪 | ChromaDB 是唯一新核心依赖 |
| §6 接口契约 | API 长什么样 | EmbeddingProvider、MemoryService、CLI 签名 |
| §7 测试策略 | Mock 怎么做 | MockEmbedding 用 hash→向量保证确定性 |
| §8 不做什么 | v0.2 显式不做 | 知识图谱、MCP、自动触发、批量导入 |
| §9 风险 | 担心什么 | LangGraph 太重、ChromaDB 新、sync→async 迁移 |

### 3.2 对面试有用的关键认知

读完 SPEC_V02.md，你应该能回答这些问题：

1. **「为什么选 ChromaDB 而不是 Pinecone？」**  
   → ChromaDB 支持本地持久化，不依赖外部服务，和我们"轻量化"的设计理念一致。

2. **「Embedding 是什么？和 RAG 是什么关系？」**  
   → Embedding 是把文字转成数字向量（一组浮点数）。我们用它做记忆检索，不是做 RAG（检索增强生成）。区别：RAG 是检索+LLM 生成答案，我们是检索+直接返回记忆给 Agent。

3. **「为什么拒绝了 LangGraph？」**  
   → 实测发现它拖入 13 个依赖包。我们的原则是 "stability before sophistication"，所以用了纯 Python 状态机替代。

4. **「什么是混合检索（Hybrid Retrieval）？」**  
   → 同时用关键词搜索（FTS5）和语义搜索（向量），再用 RRF 算法合并排名。两者的优势互补。

---

## 4. 架构升级：五层楼的装修

> v0.2 没有拆楼重建，而是在每层做了「装修」。

### 4.1 装修前后对比

```
v0.1 大厦                          v0.2 大厦
─────────                          ─────────
5F  CLI (3个命令)                   5F  CLI (6个命令: +context +reflect +health)
4F  MemoryService + Retriever      4F  MemoryService(升级) + HybridRetriever(新)
    + Curator(简版)                     + ContextCompiler(新) + CuratorGraph(新)
3F  ScoringEngine(3因子)           3F  ScoringEngine(4因子) + ReflectionEngine(新)
    + FactExtractor + Reconcile         + HealthScore(新) + FactExtractor + Reconcile
2F  CoreStore + RecallStore        2F  CoreStore + RecallStore(+update_field)
                                       + ArchivalStore(新: ChromaDB向量)
1F  AuditLog + LLM + Config       1F  AuditLog + LLM + Config(扩展)
                                       + EmbeddingProvider(新) + OpenAI/Local实现
```

### 4.2 新增组件速查表

| 层 | 新组件名 | 隐喻 | 文件 |
|---|---------|------|------|
| 1F 基建 | `EmbeddingProvider` | 翻译官（把文字翻成数字） | `foundation/embedding.py` |
| 1F 基建 | `OpenAIEmbedding` | 在线翻译（API） | `foundation/openai_embedding.py` |
| 1F 基建 | `LocalEmbedding` | 离线翻译（本地模型） | `foundation/local_embedding.py` |
| 2F 存储 | `ArchivalStore` | 第三个仓库（向量索引） | `store/archival_store.py` |
| 3F 引擎 | `ReflectionEngine` | 反思日记写手 | `engine/reflection.py` |
| 3F 引擎 | `MemoryHealthScore` | 记忆体检报告 | `engine/health.py` |
| 4F 管家 | `HybridRetriever` | 升级版搜索管家 | `service/hybrid_retriever.py` |
| 4F 管家 | `ContextCompiler` | 上下文整理员 | `service/context_compiler.py` |
| 4F 管家 | `CuratorGraph` | 自动整理状态机 | `service/curator_graph.py` |

---

## 5. 数据流：一条记忆的完整生命周期

> 这是最重要的一章。理解了数据流，就理解了整个项目。

### 5.1 保存流程（save）

当你执行 `palace save "用户喜欢Python" --importance 0.9 --room preferences`：

```
用户输入
  │
  ▼
[CLI] 解析命令参数
  │
  ▼
[MemoryService.save()]
  │
  ├─ 创建 MemoryItem 对象（自动生成 id、时间戳）
  │
  ├─ 判断重要性 → importance=0.9 ≥ 0.7
  │     │
  │     ▼ Yes
  │   写入 CoreStore (JSON 文件)
  │     └─ 同时检查 Core 预算（一个 block 最多 10 条）
  │        └─ 超限？自动把最不重要的降级到 RecallStore
  │
  ├─ 同时无论怎样，都写入 RecallStore (SQLite)
  │
  ├─ 【v0.2 新增】写入 ArchivalStore (ChromaDB 向量索引)
  │     └─ 先调用 EmbeddingProvider 把文本转成向量
  │        └─ 向量 + 元数据(room, importance, tags) 存入 ChromaDB
  │
  └─ 记录 AuditLog（审计日志）
```

**为什么要同时存三个地方？**

| 存到哪 | 为什么 | 类比 |
|--------|--------|------|
| CoreStore | 高重要性内容，Agent 每次对话都要看 | 手机桌面上的便签 |
| RecallStore | 所有内容的完整记录 + 关键词索引 | 日记本 + 目录 |
| ArchivalStore | 所有内容的语义向量索引 | 图书馆的分类检索系统 |

### 5.2 搜索流程（search）

当你执行 `palace search "编程语言偏好"`：

```
用户输入 "编程语言偏好"
  │
  ▼
[HybridRetriever.search()]
  │
  ├─── 通道1: FTS5 关键词搜索 (RecallStore.search)
  │     └─ 在 SQLite 里找包含"编程""语言""偏好"的记忆
  │     └─ 返回: [{item: ..., rank: -2.5}, {item: ..., rank: -1.8}]
  │
  ├─── 通道2: 向量语义搜索 (ArchivalStore.search)    ← v0.2 新增
  │     └─ 把查询词转成向量 → 在 ChromaDB 中找余弦距离最近的记忆
  │     └─ 返回: [{id: ..., distance: 0.15}, {id: ..., distance: 0.32}]
  │
  ▼
[Reciprocal Rank Fusion (RRF)]  ← 合并两个通道的排名
  │
  │ 算法原理（很简单）:
  │   每个记忆的 RRF 分 = 1/(60+排名1) + 1/(60+排名2)
  │   如果一个记忆同时出现在两个通道的前几名，它的分数会很高
  │
  ▼
[ScoredCandidate 四因子重排序]
  │
  │ 最终得分 = 0.20×时效性 + 0.20×重要性 + 0.50×相关性 + 0.10×房间加成
  │
  │ 时效性 = exp(-0.01 × 距上次访问的小时数)  ← 越近越好
  │ 重要性 = 记忆的 importance 字段           ← 人为标注的
  │ 相关性 = BM25归一化 或 余弦相似度          ← 搜索引擎算的
  │ 房间加成 = 搜索指定了房间且匹配？1:0      ← 空间过滤
  │
  ▼
[返回 top_k 个最相关的 MemoryItem]
```

**v0.1 vs v0.2 搜索的区别一图看懂**：

```
v0.1:  查询 → FTS5 → BM25排名 → 三因子评分 → 返回
v0.2:  查询 → FTS5 ─┐
                     ├─ RRF合并 → 四因子评分 → 返回
       查询 → 向量 ─┘
```

### 5.3 整理流程（curate）

当你执行 `palace curate`（或系统自动触发）：

```
[CuratorGraph] 7 步状态机

GATHER (收集)
  │ 从 RecallStore 拿最近 20 条记忆
  │ 如果是空的 → 跳到 HEALTH_CHECK
  │
  ▼
EXTRACT (提取事实)
  │ 把 20 条记忆的内容拼成一大段文本
  │ 调用 LLM: "请从这些文本中提取原子事实"
  │ 例: "用户喜欢Python" → 事实: {content: "偏好Python", importance: 0.7}
  │
  ▼
RECONCILE (调和冲突)
  │ 对每个提取出的事实，跟已有记忆比对
  │ 调用 LLM: "这个新事实和已有记忆是什么关系？"
  │ 可能的决定:
  │   ADD    → 新事实，存入
  │   UPDATE → 更新已有记忆
  │   DELETE → 旧的已过时，删除
  │   NOOP   → 无需操作
  │
  ▼
REFLECT (反思)    ← v0.2 新增！
  │ 检查: 这批记忆的重要性总和 > 2.0 吗？
  │ 是 → 调用 LLM: "分析这些记忆，生成高阶洞察"
  │ 生成的洞察作为 REFLECTION 类型记忆存入
  │
  ▼
PRUNE (修剪)      ← v0.2 新增！
  │ 扫描所有记忆，找 importance < 0.05 且 status=ACTIVE 的
  │ 标记为 PRUNED（逻辑删除，不物理删除）
  │
  ▼
HEALTH_CHECK (体检)  ← v0.2 新增！
  │ 计算 5 维度健康分
  │
  ▼
REPORT (报告)
  │ 生成 CuratorReport 汇总所有操作
  │ 包含: 提取了几个事实、创建了几条、更新了几条、
  │        修剪了几条、生成了几条反思、耗时多少、健康分多少
```

### 5.4 上下文编译流程（context）— v0.2 新增

当 Agent 需要"此刻该记住什么"时：

```
[ContextCompiler.compile(query="...")]
  │
  ├─ Section 1: [CORE MEMORY]
  │   从 CoreStore 获取所有 ACTIVE 的高重要性记忆
  │   "用户名：链克 | 偏好语言：Python | 项目：Memory Palace"
  │
  ├─ Section 2: [RETRIEVED]
  │   用 HybridRetriever 搜索与 query 相关的记忆 (top 5)
  │   "1. [preferences] 用户喜欢深色模式 (importance=0.9)"
  │
  └─ Section 3: [RECENT ACTIVITY]
      从 RecallStore 获取最近 3 条
      "- 昨天讨论了部署方案 (projects)"

→ 拼成一个字符串，交给 Agent 当上下文
```

---

## 6. 逐文件拆解：每个脚本做了什么

### 6.1 — 1F 基建层 (Foundation)

#### 📄 `foundation/embedding.py` — 翻译官的规矩

```python
# 这是一个 Protocol（接口契约），不是实现
class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """把文字列表变成向量列表"""
        ...

    @property
    def dimension(self) -> int:
        """向量的维度（长度）"""
        ...
```

**大白话**：这个文件只定义了「翻译官必须会什么」——必须能把文字转成数字向量。它没有写具体怎么翻译，那是下面两个文件的事。

**为什么不直接写实现？** 因为我们想支持多种翻译方式（OpenAI API、本地模型），如果直接写死一种，以后要换的时候到处改代码。用 Protocol 就像定一个合同：只要你满足这个合同，我不管你具体是谁。

同时还定义了 `EmbeddingConfig`：

```python
class EmbeddingConfig(BaseModel):
    provider: str = "openai"            # 用哪个翻译官
    model_id: str = "text-embedding-3-small"  # 用哪个模型
    dimension: int = 1536               # 向量多长
    batch_size: int = 64                # 一次最多翻译多少条
```

---

#### 📄 `foundation/openai_embedding.py` — 在线翻译官

调用 OpenAI 的 API 把文字转成向量。核心就是发一个 HTTP 请求：

```python
# 简化版核心逻辑
response = await self._client.post(
    "/v1/embeddings",
    json={"model": "text-embedding-3-small", "input": ["用户喜欢Python"]}
)
# response 返回: [[0.012, -0.034, 0.078, ...]]  ← 1536个浮点数
```

**什么时候用这个？** 有网络、有 API key、想要最好效果的时候。

---

#### 📄 `foundation/local_embedding.py` — 离线翻译官

不调 API，直接在本机跑一个小模型（`all-MiniLM-L6-v2`）来生成向量。

```python
# 简化版
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("all-MiniLM-L6-v2")
vectors = model.encode(["用户喜欢Python"])  # 本地计算，不需要网络
```

**聪明的地方**：如果你没装 `sentence-transformers` 这个库，它不会崩溃，而是给你一个友好提示：

```python
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    raise ImportError(
        "sentence-transformers is required for local embedding. "
        "Install with: pip install memory-palace[local]"
    )
```

---

### 6.2 — 2F 存储层 (Store)

#### 📄 `store/archival_store.py` — 第三个仓库

**v0.1 状态**：只有 2 行 placeholder 代码（空壳）。  
**v0.2 状态**：236 行完整实现。

这是全量向量索引层，用 **ChromaDB** 实现。ChromaDB 是一个开源的向量数据库，可以理解成「一个专门存数字向量的数据库」。

**核心操作**：

| 方法 | 做什么 | 类比 |
|------|--------|------|
| `insert(item)` | 存一条记忆的向量 | 图书馆登记一本新书 |
| `search(query)` | 找语义最相似的记忆 | 读者描述想看的内容，图书管理员找最匹配的书 |
| `get(id)` | 按 ID 精确查找 | 按书号找书 |
| `delete(id)` | 删除一条 | 下架一本书 |
| `count()` | 共存了多少条 | 统计馆藏量 |

**关键设计细节**：

1. **upsert 而非 add**：如果同一条记忆存两次，不会报错，而是覆盖更新
2. **元数据过滤**：搜索时可以加条件，比如「只在 preferences 房间找、importance ≥ 0.5 的」
3. **测试用内存模式**：正式用 PersistentClient（数据存磁盘），测试用 EphemeralClient（数据在内存，用完就没）

```python
# 正式环境
self._client = chromadb.PersistentClient(path="~/.memory_palace/archival/")

# 测试环境
self._client = chromadb.EphemeralClient()  # 不写磁盘，测试隔离
```

---

#### 📄 `store/recall_store.py` — 旧仓库的小升级

v0.2 只加了一个方法：`update_field(memory_id, field, value)`。

**背景**：v0.1 里 MemoryService 想更新某条记忆的某个字段时，得这样写：

```python
# v0.1：直接操作 RecallStore 的内部数据库连接（不好的做法！）
self._recall_store._conn.execute(
    "UPDATE memories SET status = ? WHERE id = ?", ("superseded", memory_id)
)
```

这就像绕过图书管理员，直接去后台改数据库——不安全，容易出错。

v0.2 加了正规渠道：

```python
# v0.2：通过定义好的方法来操作（好的做法）
self._recall_store.update_field(memory_id, "status", "superseded")
```

**安全措施**：有一个白名单，只允许更新特定字段，防止恶意或误操作修改 ID 之类的关键字段。

---

### 6.3 — 3F 引擎层 (Engine)

#### 📄 `engine/scoring.py` — 评分改革

**v0.1 的问题**：评分函数接收 4 个平行数组：

```python
# v0.1 写法（容易出错！）
rank_legacy(
    items=[记忆A, 记忆B, 记忆C],
    recency_hours=[2.0, 48.0, 0.5],       # 必须对齐顺序！
    importances=[0.8, 0.3, 0.9],           # 如果顺序搞错，全乱了
    relevances=[0.7, 0.9, 0.2],
)
```

**v0.2 的改进**：把数据打包成一个对象：

```python
# v0.2 写法（清晰、不会搞混）
rank([
    ScoredCandidate(item=记忆A, recency_hours=2.0, importance=0.8, relevance=0.7, room_bonus=1.0),
    ScoredCandidate(item=记忆B, recency_hours=48.0, importance=0.3, relevance=0.9, room_bonus=0.0),
    ScoredCandidate(item=记忆C, recency_hours=0.5, importance=0.9, relevance=0.2, room_bonus=1.0),
])
```

每条记忆的所有评分因子「粘在一起」，不可能搞混顺序。

**新增 `cosine_similarity()` 纯函数**：

```python
def cosine_similarity(a: list[float], b: list[float]) -> float:
    """两个向量的余弦相似度 — 越接近 1 越相似"""
    # 想象两个箭头从原点射出，夹角越小越相似
    dot = sum(x * y for x, y in zip(a, b))   # 点积
    norm_a = sqrt(sum(x * x for x in a))       # 向量A的长度
    norm_b = sqrt(sum(x * x for x in b))       # 向量B的长度
    return dot / (norm_a * norm_b)             # cos(θ)
```

---

#### 📄 `engine/reflection.py` — 反思引擎

**原理**：把近期记忆喂给 LLM，让它生成高阶洞察。

```python
REFLECTION_PROMPT = """你是一个记忆宫殿的反思引擎。
根据以下近期记忆，生成 1-3 条高阶洞察。

每条洞察应该：
- 综合多条记忆（不是简单复述）
- 揭示用户可能没注意到的模式
- 有可操作性

MEMORIES:
{formatted_memories}

返回 JSON 数组:
[{"content": "洞察文本", "source_ids": ["id1", "id2"]}]
"""
```

**关键决策**：
- 洞察的 `importance` 固定为 0.8（反思天然重要）
- 类型为 `REFLECTION`（区别于普通 `OBSERVATION`）
- `merged_from` 字段记录「这条洞察是从哪些记忆合成的」

**`should_reflect()` 门控函数**：不是每次整理都生成反思，只在「近期记忆的重要性总和 > 2.0」时才触发。防止对鸡毛蒜皮的事也做深度反思。

---

#### 📄 `engine/health.py` — 记忆体检报告

5 个维度，每个 0~1 分：

| 维度 | 怎么算 | 类比 |
|------|--------|------|
| **freshness 新鲜度** | 近 30 天被访问过的记忆占比 | 冰箱里过期食物比例 |
| **efficiency 效率** | Core 层中 ACTIVE 状态的占比 | 办公桌上有用文件的比例 |
| **coverage 覆盖率** | 有记忆的房间 / 配置的房间总数 | 图书馆各区域是否都有藏书 |
| **diversity 多样性** | MemoryType 的 Shannon 熵 | 食谱里是不是各种菜系都有 |
| **coherence 一致性** | 1 - 重复率 | 有没有重复的书 |

```python
# 综合分 = 加权平均
overall = 0.25×freshness + 0.25×efficiency + 0.15×coverage 
        + 0.15×diversity + 0.20×coherence
```

**核心设计**：`compute_health()` 是一个**纯函数**——给定相同的输入必然得到相同的输出，不做任何数据库操作。这让它 100% 可测试。

---

### 6.4 — 4F 管家层 (Service)

#### 📄 `service/hybrid_retriever.py` — 混合搜索管家

这是 v0.2 最核心的新组件。它做的事情用一句话概括：**关键词搜索和语义搜索同时做，然后用数学方法合并结果**。

**RRF 算法（大白话版）**：

假设搜索「编程偏好」:
- FTS5 关键词结果：记忆A 排第1，记忆C 排第2
- 向量语义结果：记忆B 排第1，记忆A 排第2

```
记忆A 的 RRF 分 = 1/(60+1) + 1/(60+2) = 0.0164 + 0.0161 = 0.0325  ← 最高！
记忆B 的 RRF 分 = 0        + 1/(60+1) = 0.0164
记忆C 的 RRF 分 = 1/(60+2) + 0        = 0.0161
```

记忆A 在两个渠道都出现了，所以 RRF 分最高。这就是「交叉验证，双保险」。

**降级策略**（向后兼容 v0.1）：

```python
self._hybrid_enabled = archival_store is not None and embedding is not None

# 如果没配置向量组件，自动退回 v0.1 的纯 FTS5 搜索
if self._hybrid_enabled:
    return await self._hybrid_search(...)
else:
    return self._fts_only_search(...)
```

---

#### 📄 `service/context_compiler.py` — 上下文整理员

把 Core 记忆 + 搜索结果 + 近期活动拼成一个文本块，给 Agent 当 system prompt 用。

```
[CORE MEMORY]
用户名: 链克 | 职业: 研究生 | 偏好: Python, 深色模式

[RETRIEVED]
1. [projects] Memory Palace 项目使用五层架构 (importance=0.8)
2. [preferences] 用户喜欢简洁的代码风格 (importance=0.7)

[RECENT ACTIVITY]
- 刚讨论了 v0.2 的 SPEC (projects)
- 问了 ChromaDB 的使用方法 (skills)
```

---

#### 📄 `service/curator_graph.py` — 整理状态机

**重要背景**：原计划用 LangGraph（一个 AI 流程编排框架）来实现。但实施前的检查发现 LangGraph 会拖入 13 个依赖包，太重了。所以改用纯 Python 写了一个状态机。

**什么是状态机？** 就是一个有明确步骤的流程图，每一步完成后自动转到下一步。

```python
class CuratorPhase(StrEnum):
    GATHER = auto()       # 第1步：收集
    EXTRACT = auto()      # 第2步：提取
    RECONCILE = auto()    # 第3步：调和
    REFLECT = auto()      # 第4步：反思
    PRUNE = auto()        # 第5步：修剪
    HEALTH_CHECK = auto() # 第6步：体检
    REPORT = auto()       # 第7步：出报告
    DONE = auto()         # 结束标记
```

执行引擎是一个 while 循环：

```python
async def run(self):
    phase = CuratorPhase.GATHER
    while phase != CuratorPhase.DONE:
        if phase == CuratorPhase.GATHER:
            phase = await self._gather(state)
        elif phase == CuratorPhase.EXTRACT:
            phase = await self._extract(state)
        # ... 每个 phase 执行完返回下一个 phase
```

**错误处理**：如果某一步出错，不会整个崩掉：
- 前面的步骤出错 → 跳到 HEALTH_CHECK（跳过剩余步骤，但还是做体检和报告）
- HEALTH_CHECK 或 REPORT 出错 → 生成一个降级报告，直接结束

---

### 6.5 — 5F 接待层 (Integration)

#### 📄 `integration/cli.py` — 命令行升级

新增 3 个命令：

```bash
palace context          # 编译当前上下文（Agent 会看到什么）
palace context --query "Python"  # 带查询的上下文编译
palace reflect          # 手动触发反思
palace health           # 显示 5 维度健康报告
```

修复 2 个 v0.1 问题：
- `palace rooms` 从配置文件读房间列表（不再硬编码）
- `palace inspect <id>` 通过 MemoryService 查询（不再绕过管家）

---

## 7. 核心设计模式：为什么这么写

> 这一章解释代码里反复出现的设计思路，理解了这些，你就能自己设计新功能。

### 7.1 Protocol 模式 — 合同制

**问题**：我们想支持多种 LLM（OpenAI、DeepSeek）和多种 Embedding（API、本地）。如果写死，以后换不了。

**解法**：用 Python 的 `Protocol`（协议）。

```python
# 定义合同："你必须会这个"
class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimension(self) -> int: ...

# 任何满足合同的类都行，不需要继承
class OpenAIEmbedding:
    async def embed(self, texts):    # ✅ 方法签名匹配
        return call_openai_api(texts)
    @property
    def dimension(self):             # ✅ 属性签名匹配
        return 1536

class LocalEmbedding:
    async def embed(self, texts):    # ✅ 也匹配
        return run_local_model(texts)
    @property
    def dimension(self):             # ✅ 也匹配
        return 384
```

在 Memory Palace 里用 Protocol 的地方有 3 个：
- `LLMProvider` — LLM 调用（v0.1 就有）
- `EmbeddingProvider` — 向量生成（v0.2 新增）
- `AbstractStore` — 存储接口（v0.1 就有）

**你需要记住**：Protocol = 鸭子类型（duck typing）的形式化。"如果它走路像鸭子、叫声像鸭子——它就是鸭子。"

### 7.2 纯函数 — 不碰外部世界

项目里有些函数被刻意设计为「纯函数」：给相同输入，永远返回相同输出，不读数据库、不写文件、不调 API。

```python
# ✅ 纯函数示例
def cosine_similarity(a, b) -> float:      # 同样的两个向量 → 同样的结果
def recency_score(hours, decay) -> float:  # 同样的参数 → 同样的分数
def compute_health(core, recall, rooms):   # 同样的列表 → 同样的分数

# ❌ 非纯函数示例
async def search(query):                   # 每次执行结果可能不同（数据库变了）
```

**纯函数的好处**：
1. **测试极其简单**——不需要搭数据库、mock API，直接传参验证
2. **不会产生意外**——不会悄悄改了你的数据
3. **可以随意组合**——像乐高积木一样拼

### 7.3 状态机 vs 框架 — 自己种田 vs 买超市的菜

v0.2 原计划用 **LangGraph**（一个流程编排框架）来做 Curator 的 7 步流程。

**为什么最终不用？**

| 对比 | LangGraph | 纯 Python 状态机 |
|------|-----------|------------------|
| 额外依赖 | 13 个包 | 0 个包 |
| 学习成本 | 要学 LangGraph API | Python 基础即可 |
| 调试难度 | 框架内部黑盒 | 所有代码都是自己的 |
| 功能覆盖 | 超出需求（checkpoint、streaming） | 刚好够用 |

**决策原则**：「Stability before Sophistication」（稳定优于花哨）。在 v0.2 只需要一个简单的顺序流程时，状态机完全够用。等 v1.0 需要定时触发、断点续传时，再评估框架。

### 7.4 降级策略 — 没配也能跑

v0.2 引入了 Embedding 和 ChromaDB，但**没有强制要求配置它们**。

```python
# HybridRetriever 的核心逻辑
self._hybrid_enabled = archival_store is not None and embedding is not None

if self._hybrid_enabled:
    return await self._hybrid_search(...)    # 有向量 → 混合搜索
else:
    return self._fts_only_search(...)        # 没向量 → 退化为 v0.1 行为
```

这个模式叫 **Graceful Degradation（优雅降级）**：有高级功能就用，没有也不崩溃。

---

## 8. 关键决策复盘：做过的取舍

### 决策 1: ChromaDB vs Pinecone vs FAISS

| 选项 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| Pinecone | 云端，可扩展 | 需要注册、要钱、有网络依赖 | ❌ |
| FAISS | Meta 出品，超快 | 不带元数据过滤，要自己拼 | ❌ |
| ChromaDB | 本地持久化，API 简单，带元数据过滤 | v1.0 刚出，API 可能变 | ✅ |

**决定因素**：Memory Palace 是 Agent 的本地记忆系统，不应该依赖云服务。ChromaDB 的 `PersistentClient` 把数据存在本地，符合我们的设计理念。

### 决策 2: LangGraph 被拒绝

原计划在 SPEC_V02 §1.3 中说用 LangGraph。实施时：

```bash
pip install langgraph
pip list | grep lang  # 发现拖入了 13 个包！
```

包括 `langchain-core`、`langsmith`、`tenacity` 等。远超我们设定的 5 包阈值。

**替代方案**：用 Python 标准库的 `StrEnum` + `while` 循环实现状态机。307 行代码，零额外依赖。

### 决策 3: KuzuDB 图数据库延迟到 v1.0

原始 SPEC 主文档的 §5.1 计划 v0.2 引入 KuzuDB（一个图数据库，用来存「记忆A和记忆B有关联」这种关系）。

**延迟理由**：v0.2 已经引入了 ChromaDB + Embedding 两个全新的技术栈。如果再加 KuzuDB，一个版本内三个新存储介质同时引入，出了 bug 很难定位是谁的问题。

**替代**：用简单的 Room 匹配 bonus 代替图距离计算。5 个房间尺度下，图查询没有优势。

### 决策 4: Embedding 不是 RAG

有人可能会问：「你们用了 Embedding，是不是搞了个 RAG？」

**不是**。区分很重要：

| | RAG | Memory Palace |
|---|-----|---------------|
| 检索之后做什么 | 把检索结果塞进 LLM Prompt，让 LLM 回答问题 | 直接返回记忆给 Agent |
| 数据源 | 外部文档（PDF、网页） | Agent 自己的观察和反思 |
| 目标 | 回答用户问题 | 给 Agent 提供上下文 |

Memory Palace 的 Embedding 只用于**记忆的语义检索**，检索完就直接返回 MemoryItem，不做二次生成。

---

## 9. 技术债：从 v0.1 继承的问题怎么解决的

> 技术债(Tech Debt) = 开发中为了赶进度而留下的「凑合写法」，迟早要还。

### 全部 7 笔债务

| # | 问题 | 怎么凑合的(v0.1) | 怎么还的(v0.2) |
|---|------|------------------|----------------|
| TD-1 | update() 绕过 RecallStore 直接操作数据库连接 | `self._recall_store._conn.execute(SQL)` | 新增 `RecallStore.update_field()` 正规方法 |
| TD-2 | `get_core_context()` 返回含已废弃/已修剪的记忆 | 没过滤 status | 加了 `ACTIVE` 状态过滤 |
| TD-3 | `rank()` 用平行数组传参，容易搞混顺序 | 4个 list 必须索引对齐 | 新增 `ScoredCandidate` dataclass 打包 |
| TD-4 | CLI `inspect` 命令绕过 MemoryService 直接读 Store | 直接 `RecallStore.get()` | 用 `MemoryService.get_by_id()` 三层查找 |
| TD-5 | CLI `rooms` 命令硬编码房间列表 | `["general", "preferences", ...]` | 改从 `Config.rooms` 读 |
| TD-6 | 测试文件里有没用到的 import | `import httpx` 被 ruff 警告 | 删除 |
| TD-7 | `save()` 不检查 Core 预算，可能存超 | 直接都塞进去 | 超限自动 demote 最不重要的到 Recall |

---

## 10. 测试策略：怎么保证改了不出事

### 10.1 分层测试金字塔

```
                 ╱  E2E  ╲           ← 25 tests，全流程验证
               ╱ Integration ╲       ← 13 tests，CLI 命令、包导入
             ╱    Service     ╲      ← 80 tests，管家层逻辑
           ╱      Engine       ╲     ← 51 tests，引擎层纯逻辑
         ╱        Store         ╲    ← 44 tests，数据库读写
       ╱       Foundation        ╲   ← 46 tests，基建层
     ╱          Models            ╲  ← 25 tests，数据结构
    ─────────────────────────────────
                  284 total
```

越底层测试越多、跑得越快。越顶层测试越少、覆盖面越宽。

### 10.2 Mock 策略 — 假装有 LLM 和 API

测试时不能真的调 OpenAI（太慢、要钱、结果不确定）。所以用 Mock：

```python
# MockLLM：假装是 GPT，其实返回预设的固定回答
class MockLLM:
    responses: list[str]     # 预设的回答列表
    _call_count: int = 0     # 第几次被调用

    async def complete(self, prompt, response_format=None) -> str:
        response = self.responses[self._call_count % len(self.responses)]
        self._call_count += 1
        return response      # 每次返回下一个预设回答
```

```python
# MockEmbedding：假装是 Embedding API，用哈希生成确定性向量
class MockEmbedding:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        # 同样的文本 → 永远同样的向量（确定性！）
        return [self._hash_to_vector(t) for t in texts]

    def _hash_to_vector(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode()).digest()
        raw = [b / 255.0 for b in h[:self._dimension]]
        norm = sum(x*x for x in raw) ** 0.5
        return [x / norm for x in raw]
```

**为什么 MockEmbedding 这么写？**

关键词：**确定性（deterministic）**。

"用户喜欢Python" 这句话，不管跑多少次测试，sha256 哈希值永远一样 → 生成的向量永远一样 → 测试结果永远一样。如果用随机向量，每次跑测试可能通过也可能失败，那测试就没意义了。

### 10.3 ChromaDB 的测试隔离

ChromaDB 用 `EphemeralClient`（内存模式）测试，但同一个 Client 里的 Collection 是共享的。如果两个测试都往 `"memory_palace"` 集合里写数据，它们会互相干扰。

**解法**：每个测试用独立的集合名（UUID）：

```python
import uuid

def test_search():
    store = ArchivalStore(
        client=chromadb.EphemeralClient(),
        collection_name=str(uuid.uuid4()),  # 随机名，测试间互不干扰
    )
```

---

## 11. Hands-on：动手跟着走一遍

### 11.1 运行全部测试

```bash
cd /Users/link/Documents/Agent_Project/memory-palace
uv run pytest tests/ -q
# 期望输出: 284 passed in ~1s
```

### 11.2 按层运行测试

```bash
# 看某个具体层的测试
uv run pytest tests/test_foundation/ -v   # Foundation (46 tests)
uv run pytest tests/test_store/ -v        # Store (44 tests)
uv run pytest tests/test_engine/ -v       # Engine (51 tests)
uv run pytest tests/test_service/ -v      # Service (80 tests)
uv run pytest tests/test_e2e/ -v          # E2E (25 tests)
```

### 11.3 CLI 体验

```bash
# 保存记忆
uv run palace save "用户喜欢Python，偏好深色模式" --importance 0.9 --room preferences

# 关键词搜索
uv run palace search "编程语言"

# 查看所有记忆
uv run palace inspect

# 手动整理
uv run palace curate

# v0.2 新命令
uv run palace health    # 查看健康报告
uv run palace rooms     # 查看房间列表
```

### 11.4 读一个测试文件学架构

推荐从 `tests/test_service/test_hybrid_retriever.py` 开始读：

```bash
uv run pytest tests/test_service/test_hybrid_retriever.py -v
```

这个文件覆盖了 v0.2 的核心能力：
- Mock 怎么搭建
- 混合搜索的完整流程
- FTS5-only 降级
- RRF 融合

### 11.5 看你改的代码的影响

```bash
# 看 v0.1 → v0.2 的完整代码差异
git diff main..feat/integration-round13 --stat

# 看某个具体文件的改动
git diff main..feat/integration-round13 -- src/memory_palace/engine/scoring.py
```

---

## 12. v1.0 前瞻：下一步去哪里

### 12.1 v1.0 规划的大功能

| 功能 | v0.2 打下的基础 | v1.0 要做的 |
|------|----------------|-------------|
| **Sleep-time 自动整理** | CuratorGraph 状态机可复用 | 加定时器 + 事件驱动触发 |
| **Ebbinghaus 遗忘曲线** | Health freshness 已有访问时间 | `importance *= exp(-t/S)` 自动衰减 |
| **KuzuDB 图存储** | ArchivalStore 全量索引搭好 | 加关系边 → 图距离真正发挥作用 |
| **MCP Server** | Protocol 化的 clean API | 直接暴露为 MCP Tools |
| **多人格** | Room 和 Config 已模块化 | persona profile 切换 |

### 12.2 你现在可以尝试的练手任务

1. **加一个新房间**：在 `memory_palace.yaml` / `Config.rooms` 里加一个 `"hobbies"` 房间
2. **调权重**：改 `ScoringConfig` 的四因子权重，看搜索排序变化
3. **加一个 CLI 命令**：类似 `palace stats`，调用 `MemoryService.stats()` 显示统计
4. **写一个测试**：为 `cosine_similarity()` 增加一个测试用例 — 正交向量(90°)应该返回 0

---

## 附录 A: 词汇表

| 术语 | 含义 |
|------|------|
| **Protocol** | Python 的接口机制，定义"必须有哪些方法"，不需要继承 |
| **Embedding** | 把文本转成一组浮点数（向量），让计算机能算语义相似度 |
| **ChromaDB** | 开源向量数据库，专门存和查向量 |
| **FTS5** | SQLite 的全文搜索扩展，做关键词匹配 |
| **RRF** | Reciprocal Rank Fusion — 合并多个搜索结果排名的算法 |
| **BM25** | 搜索引擎的经典关键词相关性打分算法 |
| **余弦相似度** | 两个向量夹角的余弦值，越接近 1 越相似 |
| **状态机** | 有固定步骤的流程，每一步完成后自动转到下一步 |
| **纯函数** | 不依赖外部状态、同样输入永远同样输出的函数 |
| **Mock** | 测试中用的假对象，模拟真实依赖的行为 |
| **确定性** | 每次运行结果一样（测试的基本要求） |
| **降级** | 高级功能不可用时，退回低级功能而不是崩溃 |
| **技术债** | 为赶进度写的"凑合"代码，以后要修 |
| **TDD** | 测试驱动开发——先写测试，再写实现代码 |
| **ScoredCandidate** | v0.2 的评分对象，把记忆和它的各项评分打包在一起 |

## 附录 B: 文件地图（v0.2 完整版）

```
src/memory_palace/
├── __init__.py                        version = "0.2.0"
├── config.py                          配置管理 (LLM + Embedding + Scoring + Rooms + ...)
│
├── foundation/                        1F 基建层
│   ├── audit_log.py                   审计日志 (append-only JSONL)
│   ├── llm.py                         LLMProvider Protocol + ModelConfig
│   ├── embedding.py            ← NEW  EmbeddingProvider Protocol + EmbeddingConfig
│   ├── openai_embedding.py     ← NEW  OpenAI API 调用实现
│   └── local_embedding.py      ← NEW  本地 sentence-transformers 实现
│
├── models/                            2F 数据模型
│   ├── memory.py                      MemoryItem, MemoryStatus, MemoryTier, MemoryType, Room
│   ├── audit.py                       AuditEntry
│   └── curator.py                     CuratorReport (+health 字段)
│
├── store/                             2F 存储层
│   ├── base.py                        AbstractStore Protocol
│   ├── core_store.py                  Core: JSON flat file (重要记忆)
│   ├── recall_store.py          MOD   Recall: SQLite+FTS5 (+update_field)
│   └── archival_store.py       ← NEW  Archival: ChromaDB 向量存储 (全量索引)
│
├── engine/                            3F 引擎层
│   ├── scoring.py               MOD   ScoredCandidate + cosine_similarity + 4因子rank
│   ├── fact_extractor.py              LLM 事实提取 (v0.1 不变)
│   ├── reconcile.py                   LLM 冲突调和 (v0.1 不变)
│   ├── reflection.py           ← NEW  LLM 反思引擎 → REFLECTION 类型记忆
│   └── health.py               ← NEW  5 维度健康评分 (纯函数)
│
├── service/                           4F 管家层
│   ├── memory_service.py        MOD   CRUD (三层路由 + auto-demote + get_by_id)
│   ├── retriever.py             MOD   FTS5-only 检索器 (v0.1 fallback)
│   ├── hybrid_retriever.py     ← NEW  FTS5+Vector → RRF → 4因子重排序
│   ├── context_compiler.py     ← NEW  Core+Retrieved+Recent 上下文编译
│   ├── curator.py               MOD   接口层 (委托给 CuratorGraph)
│   └── curator_graph.py        ← NEW  7步状态机 (纯Python, 无LangGraph)
│
└── integration/                       5F 接待层
    ├── tools.py                       LLM Tool 定义 (v0.1 不变)
    └── cli.py                   MOD   +context +reflect +health, TD-4/TD-5 修复
```

---

> 📚 写完这份指南，你应该能：
> 1. 向面试官解释 Memory Palace 的架构和设计哲学
> 2. 打开任何一个源文件，知道它在系统中的位置和职责
> 3. 给定一个新需求（比如 "加一个 `palace export` 命令"），知道要改哪些文件
> 4. 理解 v0.2 的每个重要技术决策背后的 why
