# 🏛️ Memory Palace 深入浅出教学指南

> **版本**: v1.0.0 | **目标读者**: Python 入门级 | **阅读时间**: ~2 小时粗读，1-2 天精读
>
> 本指南直接讲解 v1.0 最终态。版本演进与踩坑经验集中在第十章（面试备用）。

---

## 目录

- [第零章：30 秒看懂 Memory Palace](#第零章30-秒看懂-memory-palace)
- [第一章：灵感与设计理念](#第一章灵感与设计理念)
- [第二章：核心概念词典——10 个关键词](#第二章核心概念词典10-个关键词)
- [第三章：项目结构全览——五层楼的大厦](#第三章项目结构全览五层楼的大厦)
- [第四章：数据模型——系统的"语言"](#第四章数据模型系统的语言)
- [第五章：四条核心数据流——Token 怎么流动](#第五章四条核心数据流token-怎么流动)
- [第六章：逐层精读——每个包干什么](#第六章逐层精读每个包干什么)
- [第七章：功能实现地图——SPEC 怎么落地](#第七章功能实现地图spec-怎么落地)
- [第八章：关键设计模式——为什么这么写](#第八章关键设计模式为什么这么写)
- [第九章：配置与运行——动手跑起来](#第九章配置与运行动手跑起来)
- [第十章：版本演进与踩坑经验（面试章）](#第十章版本演进与踩坑经验面试章)
- [附录](#附录)

---

# 第零章：30 秒看懂 Memory Palace

## 一句话定位

**给 AI Agent 装一套「记忆操作系统」**——不只让它记得住，而是让它**自己整理、自己归纳、自己遗忘**，越用越聪明。

## 现实类比

想象你开了一家**私人图书馆**：

- 📚 **书 = 记忆条目**（MemoryItem）——每本书记录一个原子事实
- 🏠 **房间 = 分类空间**（Room）——"小说区"、"工具书区"、"杂志区"
- 🧳 **口袋 = Core**——你随身带着的最重要的几本书（容量很小）
- 🗄️ **抽屉柜 = Recall**——办公室里的文件柜，需要时打开找（按关键词搜索）
- 🏚️ **地下室 = Archival**——地下仓库，什么都存，按"意思相近"也能找到（向量搜索）
- 🧹 **图书管理员 = Curator（搬运小人）**——每天晚上自动整理：丢掉过时的、合并重复的、发现新规律

## 核心公式

```
知识价值 = f(摄取次数 × 查询次数 × 梦境次数)   ← 越用越值钱（复合增长）
        ≠ f(文档上传数)                        ← 堆文档没用（线性堆积）
```

「梦境」就是搬运小人在后台自动整理、反思、生成新洞察的过程。

## 竞品一句话对比

| 竞品 | 做法 | 短板 |
|------|------|------|
| **mem0** | 向量数据库 + 简单增删改查 | 记忆只增不减，没人打扫 |
| **MemGPT** | 模拟操作系统虚拟内存分页 | 概念太复杂，不直觉 |
| **Memory Palace** | 🏛️ 空间化宫殿 + 🧹 搬运小人 | 空间分类 + 自动整理 + 混合检索 + 自我反思 |

---

# 第一章：灵感与设计理念

## 1.1 记忆宫殿——空间化存储

**灵感来源**：古希腊记忆术「Method of Loci」——在脑海中构建一座宫殿，把要记的东西放在不同房间里。当你需要回忆时，沿着房间走一遍就能想起来。

**对应到系统**：
- 宫殿 = 整个 Memory Palace 系统
- 房间（Room）= 记忆的分类命名空间：`general`、`preferences`、`projects`、`people`、`skills`
- 在房间里放东西 = 把记忆条目标记到对应的 room

**为什么不只用标签（tags）？** 因为房间有**空间关系**——`preferences` 和 `people` 是邻居，搜「编程偏好」时也能找到相关人物。这就是「空间邻近性」(Proximity) 的价值。

## 1.2 搬运小人——自动化整理

**灵感来源**：你有一个勤劳的私人图书管理员，每天晚上（你不用系统的时候）偷偷干这些事：

1. 📋 **扫描**——把最近新到的书看一遍
2. 📝 **提取事实**——从长文中拆出独立知识点
3. 🔍 **调和冲突**——"上次说你喜欢 Python，这次说喜欢 Rust，到底哪个？"
4. 💡 **思考洞察**——"你最近问了 5 次 AI 相关问题，看来你对 AI 很感兴趣"
5. 🗑️ **淘汰过时**——半年没翻过的、不重要的笔记，移到地下室或标记淘汰
6. 📊 **健康报告**——"你的记忆系统新鲜度 85%，覆盖面有点窄"

## 1.3 遗忘是智慧——认知科学的启发

**灵感**：心理学家 Ebbinghaus 发现人脑的遗忘规律——刚学的东西忘得快，复习越多忘得越慢。

Memory Palace 把这个规律变成了代码：

```
记忆保留率 = e^(-时间/稳定性)
稳定性 = 基础值 × (1 + ln(1 + 访问次数))
```

**翻译成大白话**：
- 一条记忆刚存进来，如果一直没人查它，重要性会随时间指数衰减
- 但每次你查询、使用它，它的「稳定性」就增加——就像你复习一道题，记得越牢
- 当有效重要性降到 0.05 以下，搬运小人就会把它淘汰

**为什么不直接删除？** 因为系统永远只做「软删除」（标记为 `PRUNED`），不物理删除。万一将来需要，还能找回来。这就像图书馆的书不会被烧掉，只是放到了一个不太方便拿的角落。

## 1.4 核心公式拆解

```
知识价值 = f(摄取次数 × 查询次数 × 梦境次数)
```

- **摄取**：你告诉系统一条新信息 → `palace save "我喜欢 Python"`
- **查询**：你搜索一条记忆 → `palace search "编程语言"` → 每次搜索都会增加访问计数，让相关记忆"更牢固"
- **梦境**：搬运小人自动整理的过程 → 发现模式、合并重复、生成新洞察

三者是**乘法关系**：只存不查 = 死知识；只查不整理 = 信息噪声越来越多。

## 1.5 设计哲学

> **Stability before Sophistication** — 先跑通再跑好。

这句话决定了整个项目的迭代策略：v0.1 先用最简单的方式把完整流程跑通，v0.2 加入高级功能，v1.0 才做生产级优化。

---

# 第二章：核心概念词典——10 个关键词

学一个系统，最重要的是搞清楚它的"词汇表"。下面 10 个词贯穿整个项目。

## ① MemoryItem（记忆条目）

**类比**：图书馆里的一张索引卡片。

每条记忆是一个独立的**原子事实**，比如「用户最喜欢的语言是 Python」。不是一整段对话，而是从对话中提取出的一个个独立知识点。

关键属性：内容（content）、重要性（importance 0~1）、类型（observation/preference/...）、所属房间（room）、状态（active/pruned/...）。

## ② 三层存储：Core / Recall / Archival

| 层 | 类比 | 容量 | 搜索方式 | 什么时候用 |
|----|------|------|---------|-----------|
| **Core** | 随身口袋 | 很小（10 条/block） | 全量加载 | 最重要的记忆，Agent 永远能看到 |
| **Recall** | 自己的抽屉柜 | 中等 | 关键词搜索（FTS5） | 需要时按关键词找 |
| **Archival** | 地下室仓库 | 无限 | 语义搜索（向量） | 所有记忆的全量语义索引 |

## ③ Room（房间）

**类比**：图书馆的不同区域。

默认有 5 个房间：`general`（通用）、`preferences`（偏好）、`projects`（项目）、`people`（人物）、`skills`（技能）。你也可以自定义更多。

房间的意义不只是分类标签——它还有**空间邻近性**的概念：搜索时，和查询所在房间"近"的记忆会获得额外加分。

## ④ Tier Routing（分拣规则）

**类比**：邮件分拣——重要信件放保险箱，普通信件放文件柜。

规则很简单：
- `importance ≥ 0.7` → 进入 Core（口袋）
- `importance < 0.7` → 进入 Recall（抽屉）
- **所有记忆**同时写入 Archival（地下室的全量备份）

如果 Core 的容量满了（每个 block 最多 10 条），系统会自动把 Core 中最不重要的那条"降级"到 Recall。

## ⑤ Curator（搬运小人）

**类比**：图书管理员，每天晚上自动巡检。

搬运小人是一个 7 阶段的工作流程（状态机）：
1. GATHER（收集最近的记忆）
2. EXTRACT（提取原子事实）
3. RECONCILE（调和冲突）
4. REFLECT（生成高阶洞察）
5. PRUNE（淘汰过时记忆）
6. HEALTH_CHECK（评估系统健康度）
7. REPORT（生成工作报告）

## ⑥ Ebbinghaus 衰减

**类比**：你很久没翻的笔记，记忆会越来越模糊。

数学公式：`effective_importance = importance × e^(-时间/稳定性)`

- 新鲜的记忆 → 衰减少 → 有效重要性接近原始重要性
- 长期未访问 → 衰减大 → 有效重要性趋近于零
- 被频繁查阅 → 稳定性高 → 衰减慢

## ⑦ 混合检索（Hybrid Retrieval）

**类比**：同时用三种方式找书——按书名查（关键词）、按内容含义找（语义）、按相邻书架找（空间）。

三个搜索通道：
- **FTS5**：SQLite 全文搜索，按关键词匹配（像 Google 搜索框）
- **Vector**：ChromaDB 向量搜索，按语义相似度（搜"编程偏好"能找到"喜欢 Python"）
- **Graph**：KuzuDB 图遍历，按房间邻近关系（可选）

## ⑧ RRF（Reciprocal Rank Fusion）

**类比**：三个评委各自打分，然后综合取一个最终排名。

公式：`rrf_score(d) = Σ 1/(k + rank_i(d))`，其中 k=60。

简单说：一个结果如果在多个搜索通道中都排名靠前，综合得分就更高。这比简单地取并集、按某一个分数排序更鲁棒。

## ⑨ Context Compiler（上下文编译器）

**类比**：考前你给自己整理的"临场小抄"。

Context Compiler 把三类记忆拼成一段结构化文本，直接注入 Agent 的系统提示词：

```
[CORE MEMORY]           ← Core 中所有 active 记忆（始终在）
[RETRIEVED]             ← 根据当前查询检索到的 top-k 结果
[RECENT ACTIVITY]       ← Recall 中最新的 N 条记录
```

## ⑩ Audit Log（审计日志）

**类比**：图书馆的借还记录本。

每一次操作（创建、更新、合并、淘汰、访问）都会被不可篡改地记录到一个 JSONL 文件里。谁在什么时间对哪条记忆做了什么操作，全有记录。

---

# 第三章：项目结构全览——五层楼的大厦

## 3.1 建筑隐喻

Memory Palace 的代码组织就像一栋 5 层大楼，每层有明确的职责，依赖方向**严格向下**——5 楼可以调用 4 楼，4 楼可以调用 3 楼，但 3 楼绝对不会反过来调用 4 楼。

```
╔══════════════════════════════════════════════════════════════════╗
║  5F  Integration（大门）   CLI 19 命令 │ MCP Server 18 tools    ║
╠══════════════════════════════════════════════════════════════════╣
║  4F  Service（管家团队）  MemoryService │ Curator │ Retriever   ║
║                           Scheduler │ ContextCompiler │ ...     ║
╠══════════════════════════════════════════════════════════════════╣
║  3F  Engine（加工车间）    Scoring │ Ebbinghaus │ FactExtractor ║
║                            Reconcile │ Reflection │ Health │ ...║
╠══════════════════════════════════════════════════════════════════╣
║  2F  Store（三个仓库）    CoreStore │ RecallStore │ ArchivalStore║
║                            GraphStore (opt-in)                   ║
╠══════════════════════════════════════════════════════════════════╣
║  1F  Foundation（水电煤） Config │ AuditLog │ LLM │ Embedding   ║
╠══════════════════════════════════════════════════════════════════╣
║  B1  Models（地基）       MemoryItem │ CuratorReport │ AuditEntry║
╚══════════════════════════════════════════════════════════════════╝

依赖方向: 5F → 4F → 3F → 2F → 1F → B1 （严格单向向下）
```

**为什么要分层？** 跟盖房子一个道理——地基不稳，上面再好看也会塌。分层让每一层可以独立测试、独立替换。比如你想把 SQLite 换成 PostgreSQL？只需要改 2F Store 层，其他层完全不用动。

## 3.2 文件树全览

```
src/memory_palace/
├── __init__.py                          # 包入口
├── config.py                            # 配置管理（~250 行）
│
├── models/                              # B1 地基：纯数据定义（~400 行）
│   ├── memory.py                        #   MemoryItem, Room（系统的"语言"）
│   ├── audit.py                         #   AuditEntry（审计条目）
│   ├── curator.py                       #   CuratorReport（搬运小人报告）
│   ├── errors.py                        #   统一错误码（MCP 通信用）
│   └── ingest.py                        #   IngestReport（文档摄取报告）
│
├── foundation/                          # 1F 水电煤：基础设施（~600 行）
│   ├── llm.py                           #   LLMProvider Protocol + API key
│   ├── embedding.py                     #   EmbeddingProvider Protocol
│   ├── audit_log.py                     #   JSONL 审计日志
│   ├── openai_provider.py               #   OpenAI LLM 实现
│   ├── local_embedding.py               #   本地 Embedding（免费）
│   └── openai_embedding.py              #   OpenAI Embedding（付费）
│
├── store/                               # 2F 仓库：数据存储（~1,300 行）
│   ├── core_store.py                    #   Core 层：JSON 平文件
│   ├── recall_store.py                  #   Recall 层：SQLite + FTS5
│   ├── archival_store.py                #   Archival 层：ChromaDB 向量
│   └── graph_store.py                   #   Graph 层：KuzuDB 图（可选）
│
├── engine/                              # 3F 加工车间：业务算法（~1,200 行）
│   ├── scoring.py                       #   四因子评分公式
│   ├── ebbinghaus.py                    #   遗忘曲线衰减
│   ├── fact_extractor.py                #   LLM 提取原子事实
│   ├── reconcile.py                     #   LLM 冲突调和
│   ├── reflection.py                    #   LLM 高阶洞察生成
│   ├── health.py                        #   六维健康评分
│   └── metrics.py                       #   运营指标追踪
│
├── service/                             # 4F 管家团队：业务编排（~3,500 行）
│   ├── memory_service.py                #   核心 CRUD + 分拣路由（720 行）
│   ├── retriever.py                     #   FTS5-only 检索（v0.1 兼容）
│   ├── hybrid_retriever.py              #   FTS5 + Vector + Graph 混合检索
│   ├── curator.py                       #   搬运小人协调者
│   ├── curator_graph.py                 #   搬运小人 7 阶段状态机
│   ├── scheduler.py                     #   Sleep-time 异步调度器
│   ├── heartbeat.py                     #   安全守卫（防无限循环）
│   ├── context_compiler.py              #   上下文编译器
│   ├── ingest_pipeline.py               #   5-pass 文档摄取管道
│   ├── batch_io.py                      #   批量导入/导出
│   └── persona_manager.py               #   多角色管理
│
└── integration/                         # 5F 大门：对外接口（~2,100 行）
    ├── cli.py                           #   19 个 CLI 命令（Typer）
    ├── mcp_server.py                    #   MCP Server（18 tools + 9 resources）
    ├── mcp_context.py                   #   MCP 生命周期管理
    └── tools.py                         #   工具绑定辅助
```

## 3.3 规模感

| 层 | 文件数 | 总行数 | 一句话 |
|---|--------|-------|--------|
| Models | 5 | ~400 | 纯数据结构，零逻辑 |
| Foundation | 6 | ~600 | 接口定义 + 基础 I/O |
| Store | 4(+1) | ~1,300 | 四种存储引擎 |
| Engine | 7 | ~1,200 | 评分/衰减/提取/调和/反思 |
| Service | 11 | ~3,500 | 业务编排（最大层） |
| Integration | 4 | ~2,100 | CLI + MCP 对外接口 |
| **源码合计** | **46** | **~8,175** | |
| **测试合计** | **56** | **~11,552** | 测试比源码还多！ |

> 💡 测试代码量是源码的 **1.4 倍**——这意味着每一行生产代码背后都有大量的"活文档"在保护它。读测试就能理解代码应该怎么用。

---

# 第四章：数据模型——系统的"语言"

数据模型是整个系统的"语言"——所有代码围绕这些数据结构展开。你先搞懂这些"名词"，后面的"动词"（操作）就容易理解了。

## 4.1 MemoryItem——原子记忆单元

`MemoryItem` 是整个系统最核心的数据结构。**系统里的每一条记忆都是一个 MemoryItem**。

用图书馆索引卡片来类比每个字段：

```python
class MemoryItem:
    # ── 身份信息 ──
    id: str               # 唯一编号（自动生成的 UUID）
    content: str           # 记忆内容。"用户最喜欢 Python"
    memory_type: MemoryType  # 这是什么类型的记忆？（见下文）
    tier: MemoryTier       # 存在口袋/抽屉/地下室？
    importance: float      # 重要性评分 0.0 ~ 1.0
    tags: list[str]        # 标签。["编程", "语言"]
    room: str              # 所属房间。"preferences"

    # ── 时间维度 ──
    created_at: datetime   # 什么时候创建的
    accessed_at: datetime  # 最后一次被查询的时间
    updated_at: datetime   # 最后一次被修改的时间
    access_count: int      # 被查询了多少次（影响遗忘曲线）

    # ── 生命周期 ──
    status: MemoryStatus   # 当前状态（见下文）
    version: int           # 第几个版本（每次更新 +1）
    user_pinned: bool      # 用户钉住 → 永不淘汰

    # ── 版本追溯 ──
    parent_id: str | None      # 如果这条是更新出来的，父记忆是谁
    merged_from: list[str]     # 如果这条是合并出来的，合并了哪些
    superseded_by: str | None  # 如果被更新替代了，新版本的 ID
    change_reason: str | None  # 为什么改的

    # ── 可选扩展 ──
    embedding: list[float] | None    # 向量化表示（语义搜索用）
    source_hash: str | None          # 来源文档的哈希（防重复摄取）
```

## 4.2 MemoryStatus——生命周期

一条记忆从出生到淘汰，有 4 种状态：

```
                    ┌─ UPDATE ──→ SUPERSEDED（被新版本替代）
                    │
ACTIVE（正常存活）──├─ MERGE ───→ MERGED（被合并到另一条）
                    │
                    └─ PRUNE ───→ PRUNED（被淘汰，软删除）
```

**关键点**：`SUPERSEDED`、`MERGED`、`PRUNED` 都不会物理删除数据，只是改了状态标记。在 Audit Log 里你能查到完整的变更历史。

## 4.3 MemoryTier——三层存储

| 值 | 类比 | 实现 | 路由规则 |
|----|------|------|---------|
| `CORE` | 随身口袋 | JSON 文件 | importance ≥ 0.7 |
| `RECALL` | 抽屉柜 | SQLite + FTS5 | importance < 0.7 |
| `ARCHIVAL` | 地下室 | ChromaDB 向量 | 所有记忆同步写入 |

## 4.4 MemoryType——六种记忆类型

| 类型 | 含义 | 例子 | 谁创建的 |
|------|------|------|---------|
| `OBSERVATION` | 直接观察到的事实 | "用户在做 AI 项目" | 系统提取 |
| `PREFERENCE` | 用户偏好 | "喜欢深色模式" | 系统提取 |
| `PROCEDURE` | 操作知识/技能 | "部署用 Docker Compose" | 系统提取 |
| `DECISION` | 决策记录 | "数据库选了 PostgreSQL" | 系统提取 |
| `SYNTHESIS` | 查询中发现的知识 | "Python 和 Rust 常一起讨论" | 查询回写 |
| `REFLECTION` | 高阶洞察 | "用户对 AI 记忆系统特别感兴趣" | 搬运小人生成 |

> 前 4 种是从用户输入中提取的事实，后 2 种是**系统自己创造的知识**——这就是"越用越聪明"的体现。

## 4.5 Room——记忆宫殿的房间

```python
class Room:
    name: str                 # 唯一名称，如 "preferences"
    description: str          # 描述
    parent: str | None        # 父房间（支持层级）
    memory_count: int         # 房间里有多少条记忆
    last_accessed: datetime   # 最近一次访问这个房间
```

默认 5 个房间：`general`、`preferences`、`projects`、`people`、`skills`。

## 4.6 其他数据模型

**AuditEntry**（审计条目）：记录谁在什么时间对哪条记忆做了什么。

```python
class AuditEntry:
    timestamp: datetime      # 什么时候
    action: AuditAction      # CREATE / UPDATE / MERGE / PRUNE / PROMOTE / DEMOTE / ACCESS
    memory_id: str           # 对哪条记忆
    actor: str               # "user" / "curator" / "system"
    details: dict            # 额外信息
```

**CuratorReport**（搬运小人报告）：一次整理的工作总结。

```python
class CuratorReport:
    run_id: str                   # 这次整理的唯一 ID
    triggered_at: datetime        # 什么时候触发的
    trigger_reason: str           # "timer" / "session_count" / "manual"
    facts_extracted: int          # 提取了多少事实
    memories_created: int         # 新建了多少条
    memories_merged: int          # 合并了多少条
    memories_pruned: int          # 淘汰了多少条
    reflections_generated: int    # 生成了多少洞察
    duration_seconds: float       # 花了多久
    tokens_consumed: int          # 消耗了多少 LLM token
```

---

# 第五章：四条核心数据流——Token 怎么流动

这是最核心的一章。理解了这四条数据流，你就理解了整个系统的运行时行为。

## 5.1 路径一：Save（保存）——从用户输入到存储

**场景**：用户执行 `palace save "我最喜欢 Python" --importance 0.8 --room preferences`

```
用户输入 "我最喜欢 Python"
     │
     ▼
┌─ CLI (cli.py) ──────────────────────────────────────────┐
│  解析参数: content="我最喜欢 Python"                      │
│            importance=0.8, room="preferences"             │
└────────────────────────┬────────────────────────────────┘
                         │ 调用
                         ▼
┌─ MemoryService.save() ─────────────────────────────────┐
│                                                         │
│  1. 创建 MemoryItem 对象                                │
│     id = "abc-123", tier = ?（待分拣）                   │
│                                                         │
│  2. 分拣路由：importance 0.8 ≥ 0.7                      │
│     → tier = CORE                                       │
│                                                         │
│  3. Core 预算检查：                                     │
│     preferences block 已有 10 条了吗？                   │
│     ├─ 没满 → 直接写入 CoreStore                        │
│     └─ 满了 → 把最不重要的那条 demote 到 Recall         │
│               然后写入 CoreStore                         │
│                                                         │
│  4. 同步写入 ArchivalStore（向量化全量索引）              │
│                                                         │
│  5. AuditLog.append(CREATE, "abc-123", actor="user")    │
│                                                         │
│  6. 通知 Scheduler（"有新记忆了"）                       │
│     → scheduler.notify() 累加 importance                 │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**关键设计点**：

1. **分拣规则**：importance ≥ 0.7 进 Core，< 0.7 进 Recall。这个阈值在 `config.py` 可配置。
2. **Core 有预算上限**：每个 block 最多 10 条（`CoreConfig.max_items_per_block = 10`）。模拟人脑的工作记忆容量限制——你一次能记住的东西是有限的。
3. **自动降级**：Core 满了不会报错，而是把最不重要的那条降级到 Recall。就像你口袋放不下了，主动把最不重要的东西放回抽屉。
4. **全量索引**：不管进 Core 还是 Recall，所有记忆都会同时写入 Archival。这样语义搜索能覆盖所有记忆。

## 5.2 路径二：Search（搜索）——从查询到结果

**场景**：用户执行 `palace search "编程语言偏好"`

```
查询 "编程语言偏好"
     │
     ▼
┌─ HybridRetriever.search() ─────────────────────────────┐
│                                                         │
│  并行启动两个搜索通道：                                   │
│                                                         │
│  通道① FTS5（关键词匹配）                               │
│  ┌─ RecallStore.search("编程语言偏好") ──┐              │
│  │  SQL: SELECT ... FROM memories_fts    │              │
│  │       WHERE memories_fts MATCH ?      │              │
│  │  返回: BM25 排名的结果列表            │              │
│  └───────────────────────────────────────┘              │
│                                                         │
│  通道② Vector（语义匹配）                               │
│  ┌─ ArchivalStore.search(embed("编程语言偏好")) ─┐      │
│  │  ChromaDB: 余弦相似度 top-k              │          │
│  │  能找到"我喜欢 Python"（语义相近）       │          │
│  └──────────────────────────────────────────┘          │
│                                                         │
│  通道③ Graph（空间邻近，可选）                           │
│  ┌─ GraphStore.proximity_score() ────────┐              │
│  │  查询 room 与记忆 room 的图距离        │              │
│  └───────────────────────────────────────┘              │
│                                                         │
│  RRF 融合：                                             │
│  rrf_score(d) = Σ 1/(60 + rank_i(d))                   │
│  → 在多个通道都排名靠前的结果，综合得分高                 │
│                                                         │
│  四因子重打分：                                          │
│  final = 0.20×recency + 0.20×importance                 │
│        + 0.50×relevance + 0.10×proximity                │
│                                                         │
│  返回 top_k 条结果                                      │
│                                                         │
│  副作用: 每条返回结果的 access_count += 1                │
│         （增强遗忘曲线的稳定性）                          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**四因子评分公式拆解**：

```
final_score = α·recency + β·importance + γ·relevance + δ·proximity
```

| 因子 | 权重 | 含义 | 计算方式 |
|------|------|------|---------|
| recency | 0.20 | 最近访问的记忆优先 | `e^(-0.01 × 小时数)` — 约 69 小时半衰期 |
| importance | 0.20 | 高重要性优先 | 直接用 `importance` 值 |
| relevance | 0.50 | 与查询最相关的优先 | RRF 融合后的归一化得分 |
| proximity | 0.10 | 同房间/邻近房间优先 | 图距离的倒数，或二值匹配 |

> 注意 relevance 权重最大（0.50），因为"跟你问的最相关"是搜索最重要的目标。

**降级模式**：如果没有配置 Embedding（没有 ArchivalStore），系统会自动降级到 FTS5-only 模式。混合检索只是增强，基本功能始终可用。

## 5.3 路径三：Curate（整理）——搬运小人的工作流

**场景**：`palace curate`（手动触发）或 Scheduler 自动触发

```
触发整理
     │
     ▼
┌─ CuratorService.run() ────────────────────────────────────────┐
│   检查冷却期（距上次 ≥ 1 小时才运行）                           │
│   初始化 HeartbeatController（安全守卫）                        │
│   委托给 CuratorGraph 执行                                     │
└───────────────────────┬───────────────────────────────────────┘
                        │
                        ▼
┌─ CuratorGraph（7 阶段状态机）─────────────────────────────────┐
│                                                               │
│  ① GATHER ─────────────────────────────────────────────┐      │
│  │ RecallStore.get_recent(20)                          │      │
│  │ → 获取最近 20 条记忆作为工作集                        │      │
│  │ 如果没有新内容 → 直接跳到 HEALTH_CHECK               │      │
│  └─────────────────────────────────────────────────────┘      │
│           │ heartbeat.tick() ✓                                │
│           ▼                                                   │
│  ② EXTRACT ────────────────────────────────────────────┐      │
│  │ FactExtractor.extract(combined_text)                │      │
│  │ → LLM 从文本中提取原子事实                           │      │
│  │ → 例: "用户在做 AI 项目" "用户喜欢 Python"           │      │
│  └─────────────────────────────────────────────────────┘      │
│           │ heartbeat.tick() ✓                                │
│           ▼                                                   │
│  ③ RECONCILE ──────────────────────────────────────────┐      │
│  │ 对每个新事实 vs 已有记忆：                           │      │
│  │  ReconcileEngine.reconcile(new_fact, existing)      │      │
│  │  → LLM 判断: ADD（新增）/ UPDATE（更新）/            │      │
│  │             NOOP（已有）/ DELETE（矛盾，淘汰旧的）    │      │
│  │ 例: "喜欢 Python" vs 已有 "喜欢 Java" → UPDATE      │      │
│  └─────────────────────────────────────────────────────┘      │
│           │ heartbeat.tick() ✓                                │
│           ▼                                                   │
│  ④ REFLECT ────────────────────────────────────────────┐      │
│  │ 如果 importance 总和 > 阈值 (2.0)：                  │      │
│  │   ReflectionEngine.reflect(memories)                │      │
│  │   → LLM 发现跨记忆的高阶模式                        │      │
│  │   → 生成 REFLECTION 类型记忆                        │      │
│  │   例: "用户对 AI 记忆系统特别感兴趣"                 │      │
│  └─────────────────────────────────────────────────────┘      │
│           │ heartbeat.tick() ✓                                │
│           ▼                                                   │
│  ⑤ PRUNE ──────────────────────────────────────────────┐      │
│  │ 对每条记忆计算 Ebbinghaus 衰减：                     │      │
│  │   effective_importance = importance × e^(-t/S)      │      │
│  │   S = 168h × (1 + ln(1 + access_count))            │      │
│  │ 如果 effective_importance < 0.05：                   │      │
│  │   → 标记为 PRUNED（软删除）                          │      │
│  │ 豁免: user_pinned = True 的永不淘汰                  │      │
│  └─────────────────────────────────────────────────────┘      │
│           │ heartbeat.tick() ✓                                │
│           ▼                                                   │
│  ⑥ HEALTH_CHECK ───────────────────────────────────────┐      │
│  │ 计算 6 维健康评分：                                   │      │
│  │  freshness  — 近 30 天活跃记忆比例                    │      │
│  │  efficiency — Core 利用率                             │      │
│  │  coverage   — 房间覆盖均匀度                          │      │
│  │  diversity  — 记忆类型多样性                           │      │
│  │  coherence  — 语义一致性                              │      │
│  │  operations — 操作频率健康度                           │      │
│  └─────────────────────────────────────────────────────┘      │
│           │                                                   │
│           ▼                                                   │
│  ⑦ REPORT ─────────────────────────────────────────────┐      │
│  │ 汇总 CuratorReport：                                │      │
│  │  "提取 5 个事实, 创建 3 条, 合并 1 条, 淘汰 2 条,    │      │
│  │   生成 1 条洞察, 耗时 8.3s, 消耗 1200 token"         │      │
│  └─────────────────────────────────────────────────────┘      │
│                                                               │
│  全程有 HeartbeatController 守卫：                             │
│  ├─ 每个阶段转换时 tick()，超过 50 步 → 强制停止               │
│  ├─ 每次 LLM 调用计数，超过 30 次 → 强制停止                   │
│  └─ 总耗时超过 120 秒 → 强制停止                              │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

## 5.4 路径四：Context Compile（上下文编译）——给 Agent 组装记忆

**场景**：AI Agent 需要回答问题前，先获取相关记忆作为上下文

```
ContextCompiler.compile(query="项目进展")
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  段落一: [CORE MEMORY]                                  │
│  ┌─────────────────────────────────────────────────┐    │
│  │ CoreStore.get_all_active()                      │    │
│  │ → 口袋里的所有记忆，无条件全部加载               │    │
│  │ "用户叫小明 | 喜欢 Python | 在做 AI 项目"      │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  段落二: [RETRIEVED]                                    │
│  ┌─────────────────────────────────────────────────┐    │
│  │ HybridRetriever.search("项目进展", top_k=5)    │    │
│  │ → 与当前查询最相关的 top-k 条记忆               │    │
│  │ "4月10日完成了 v0.2 | 下一步做 MCP Server"      │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  段落三: [RECENT ACTIVITY]                              │
│  ┌─────────────────────────────────────────────────┐    │
│  │ RecallStore.get_recent(N)                       │    │
│  │ → 最新的 N 条记忆（不管相不相关）                │    │
│  │ "刚才讨论了 Docker 部署方案"                    │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  拼接 → 截断到 max_chars → 输出结构化文本              │
│                                                         │
└─────────────────────────────────────────────────────────┘

最终输出（注入 Agent 的 system prompt）：

===== CORE MEMORY =====
用户叫小明。喜欢 Python。在做 AI 项目。

===== RELEVANT MEMORIES =====
4月10日完成了 v0.2 Foundation。
下一步计划做 MCP Server 接入。

===== RECENT CONTEXT =====
刚才讨论了 Docker 部署方案，决定先用 Compose。
```

**为什么分三段？** 因为 Agent 需要的上下文有三种不同的性质：
1. **Core** = 你是谁、你喜欢什么——**始终需要知道**
2. **Retrieved** = 跟当前话题相关的——**按需调取**
3. **Recent** = 刚才聊了什么——**短期记忆**

---

# 第六章：逐层精读——每个包干什么

> 本章是**正向映射**：从每个源码文件出发，讲它具体实现了什么功能。
> 第七章是**反向映射**：从 SPEC 的功能需求出发，讲工程上怎么实现。

## 6.1 foundation/——1F 水电煤

这一层提供最基础的"公共服务"，没有任何业务逻辑。

### llm.py（~70 行）——LLM 接口定义

定义了系统与 LLM（大语言模型）交互的"合同"：

```python
class LLMProvider(Protocol):
    async def complete(self, prompt: str, response_format: type | None = None) -> str: ...
```

这是一个 `Protocol`——你可以理解为"只要你有一个 `complete` 方法，你就是一个合格的 LLM 供应商"。不需要继承任何基类。OpenAI、DeepSeek、MiniMax，甚至测试用的 MockLLM，都满足这个合同。

还提供了 `get_api_key()` 函数，根据 provider 名字自动从环境变量里找对应的 API key。

### embedding.py（~50 行）——Embedding 接口定义

类似 LLM，定义了向量化的"合同"：

```python
class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimension(self) -> int: ...
```

把文本变成一串数字（向量），这样才能做语义搜索。

### audit_log.py——审计日志

最简单的 I/O 组件：把每条审计记录序列化为 JSON，追加写入（append-only）到 `audit.jsonl` 文件。一旦写入就不再修改，像区块链的"只增不改"。

### openai_provider.py——OpenAI LLM 实现

`LLMProvider` 的具体实现：用 `httpx` 调 OpenAI 兼容 API。任何 OpenAI 兼容的 API（DeepSeek、MiniMax 等）都能用这一个实现。

### local_embedding.py / openai_embedding.py——Embedding 实现

两种 Embedding 方案：
- **local**：用 `sentence-transformers` 本地模型，免费但需要下载模型文件（~80MB）
- **openai**：调 OpenAI API，付费但无需本地资源

## 6.2 store/——2F 三个仓库

### core_store.py（~140 行）——Core 层存储

**实现**：JSON 平文件。每个 block（如 `preferences`、`user`）一个 JSON 文件。

**关键特性**：
- **原子写入**：先写临时文件，再用 `os.replace()` 原子替换。就像先在草稿纸上写好，确认无误再替换正式文件——断电也不会写坏数据。
- **预算控制**：每个 block 最多存 `max_items_per_block`（默认 10 条）。

### recall_store.py（~390 行）——Recall 层存储

**实现**：SQLite 数据库 + FTS5 全文搜索索引。

**关键特性**：
- **FTS5 全文搜索**：SQLite 自带的搜索引擎，用 BM25 算法排名——跟 Google 搜索的原理类似。
- **CJK 处理**：中文没有空格分隔词语，FTS5 默认按空格分词会失效。所以代码里有一个 `_tokenize_cjk()` 函数，在中文字符间插入空格，实现逐字匹配。
- **WAL 模式**：SQLite 的一种并发模式，读写可以同时进行，不会互相阻塞。

这是代码量最大的 Store（~390 行），因为 SQL schema 定义、FTS5 配置、中文处理都需要细致处理。

### archival_store.py（~230 行）——Archival 层存储

**实现**：ChromaDB 向量数据库。

每条记忆存入时，先用 Embedding 模型把文本变成向量，再存入 ChromaDB。搜索时，查询也先变成向量，然后按余弦相似度找最接近的结果。

**类比**：FTS5 是按"字面一样"找，ChromaDB 是按"意思一样"找。搜"编程偏好"能找到"喜欢 Python"——虽然没有一个字重合，但意思是相关的。

### graph_store.py（~300 行）——Graph 层存储（可选）

**实现**：KuzuDB 图数据库。把房间和记忆建模为图的节点，关系建模为边。

主要用途：计算**空间邻近性**。比如查询在 `preferences` 房间，`skills` 房间离它图距离为 2，那 skills 里的记忆就会获得 proximity 加分。

这是 **opt-in**（默认关闭）的组件，需要额外安装 `kuzu` 包。

## 6.3 engine/——3F 加工车间

这一层全是"业务算法"——纯函数为主，不做 I/O，非常适合单元测试。

### scoring.py（~240 行）——四因子评分

所有搜索结果的排序逻辑都在这里。核心函数：

```python
def rank(candidates, weights=(0.20, 0.20, 0.50, 0.10), ...) -> list[MemoryItem]:
    """四因子排序: recency × importance × relevance × proximity"""
```

另外还有一些辅助函数：
- `recency_score(hours)` — 时间衰减：`e^(-0.01 × h)`
- `normalize_bm25(rank, all_ranks)` — 把 FTS5 的负数排名转成 0~1
- `cosine_similarity(a, b)` — 向量间的余弦相似度

### ebbinghaus.py（~110 行）——遗忘曲线

纯数学函数，零依赖——只用了 Python 的 `math` 模块。

```python
def retention(hours_since_access, stability) -> float:
    """R(t) = e^(-t/S)  记忆保留率"""

def stability(base_stability=168, access_count=0) -> float:
    """S = S₀ × (1 + ln(1 + n))  稳定性随访问次数增长"""

def effective_importance(importance, hours, access_count, ...) -> float:
    """importance × retention  有效重要性"""

def should_prune(importance, hours, access_count, threshold=0.05) -> bool:
    """有效重要性 < 0.05 → 应该淘汰"""
```

`base_stability = 168`（小时）= 1 周。意思是：只看过一次的东西，一周后保留率降到约 37%（`e^(-1) ≈ 0.37`）。如果你又查了它 3 次，稳定性变成 `168 × (1 + ln(4)) ≈ 400 小时`，衰减变慢了。

### fact_extractor.py（~90 行）——LLM 提取原子事实

输入一段文本，调用 LLM 提取出一个个独立的原子事实。

```python
class FactExtractor:
    async def extract(self, text: str) -> list[MemoryItem]:
        # 1. 构造 prompt，告诉 LLM "请从这段对话中提取原子事实"
        # 2. 调 LLM
        # 3. 解析 JSON 响应 → list[MemoryItem]
```

Prompt 会指导 LLM：每个事实要自包含、不复合、有 importance 评分（0.0~1.0）。

### reconcile.py（~130 行）——冲突调和

当新事实和已有记忆可能冲突时，让 LLM 做裁判：

```python
class ReconcileEngine:
    async def reconcile(self, new_fact: str, existing: list[MemoryItem]) -> dict:
        # LLM 返回决策:
        # ADD     — 全新信息，直接新增
        # UPDATE  — 更正/更新已有记忆
        # DELETE  — 新事实否定了旧记忆
        # NOOP    — 已经有了，不需要动
```

### reflection.py（~140 行）——高阶洞察生成

搬运小人整理完一批记忆后，如果累积的重要性足够高（`importance_sum > 2.0`），就会调用 LLM 生成跨记忆的高阶洞察。

```python
class ReflectionEngine:
    async def reflect(self, memories: list[MemoryItem], max_insights=3) -> list[MemoryItem]:
        # LLM: "看了这些记忆，你发现了什么规律？"
        # 返回 REFLECTION 类型的新记忆
```

### health.py（~200 行）——六维健康评分

从 6 个维度给记忆系统打分：

| 维度 | 含义 | 计算方式 |
|------|------|---------|
| freshness | 新鲜度 | 近 30 天创建的记忆占比 |
| efficiency | 高效性 | Core 层的利用率 |
| coverage | 覆盖面 | 房间分布均匀度 |
| diversity | 多样性 | 记忆类型分布 |
| coherence | 一致性 | 语义聚类质量 |
| operations | 运维健康 | 操作频率是否正常 |

### metrics.py——运营指标

追踪 p95 延迟、增长率、整理频率等数字。用滑动窗口实现（保留最近 N 个数据点）。

## 6.4 service/——4F 管家团队

这是最大的一层（~3,500 行），负责把各个底层组件编排成完整的业务流程。

### memory_service.py（~720 行）——核心 CRUD

**系统的大管家**——所有记忆操作的入口。对上层隐藏了三层存储的细节。

```python
class MemoryService:
    def save(content, importance, tags, room, ...) -> MemoryItem    # 保存
    async def search(query, top_k, room, ...) -> list[MemoryItem]   # 搜索
    def update(memory_id, **fields) -> MemoryItem                    # 更新
    def delete(memory_id, reason) -> None                            # 删除
    def get_core_context() -> str                                    # 获取所有 Core 记忆
    def stats() -> dict                                              # 统计信息
```

内部协调了 `CoreStore`、`RecallStore`、`ArchivalStore`、`FactExtractor`、`AuditLog` 等多个组件。这就是 **Facade 模式**——一个统一的"前台"，背后协调一个团队。

### hybrid_retriever.py（~320 行）——混合检索

编排 FTS5 + Vector + Graph 三通道搜索，用 RRF 融合，再用四因子评分排序。

当 ArchivalStore 不可用时（未配 Embedding），自动降级为 FTS5-only。

### curator.py（~180 行）——搬运小人协调者

负责"要不要触发整理"和"触发后委托谁执行"。

触发条件（满足任一就触发）：
- 累计新增 ≥ 20 条记忆
- 重要性总和 ≥ 5.0
- 距上次整理 ≥ 24 小时
- 手动 CLI/API 调用

### curator_graph.py（~400 行）——搬运小人的大脑

7 阶段状态机的具体实现（第五章的路径三已详细讲过）。

**为什么是纯 Python 状态机而不用 LangGraph？** 因为预检发现 LangGraph 会拉入 13 个传递依赖，超过了复杂度预算。纯 Python 实现只需要一个 `while` 循环 + `match-case` 分支。详见第八章。

### scheduler.py（~230 行）——Sleep-time 调度器

后台的 asyncio 协程，每 5 分钟检查一次要不要触发搬运小人。也支持事件驱动：`memory_service.save()` 时会发出通知，如果累计的 importance 超标就立即触发。

### heartbeat.py（~130 行）——安全守卫

纯计数器，防止搬运小人陷入无限循环：

| 保护 | 限制 | 触发行为 |
|------|------|---------|
| MAX_STEPS | 50 次状态转换 | 强制停止 |
| MAX_LLM_CALLS | 30 次 LLM 调用 | 强制停止 |
| MAX_DURATION | 120 秒 | 强制停止 |
| 去重检查 | 已处理的 memory_id | 跳过 |

### context_compiler.py（~100 行）——上下文编译器

把 Core + Retrieved + Recent 三段记忆拼成结构化文本（第五章路径四已详细讲过）。

### ingest_pipeline.py（~350 行）——5-pass 文档摄取

处理长文档的完整管道：

| Pass | 做什么 | 技术手段 |
|------|--------|---------|
| 1. DIFF | 内容去重 | SHA-256 哈希比对 |
| 2. EXTRACT | 提取原子事实 | FactExtractor（LLM） |
| 3. MAP | 分配房间 + 重要性 | LLM 分类 |
| 4. LINK | 发现关系 | LLM + GraphStore |
| 5. UPDATE | 调和写入 | ReconcileEngine → 各 Store |

### batch_io.py——批量导入/导出

支持 Markdown 和 JSONL 格式的批量导入导出。导出时按房间分组，支持往返（export → import 不丢数据）。

### persona_manager.py——多角色管理

不同的 Persona（角色配置）可以有独立的数据目录。比如"工作助手"和"学习伙伴"各自维护独立的记忆库。

## 6.5 integration/——5F 大门

### cli.py（~857 行）——19 个 CLI 命令

用 Typer 框架写的命令行工具。每个命令对应一个 `@app.command()` 函数。

| 命令 | 功能 | 需要 LLM |
|------|------|:--------:|
| `palace save` | 保存一条记忆 | |
| `palace search` | 搜索记忆 | |
| `palace update` | 更新记忆 | |
| `palace forget` | 软删除记忆 | |
| `palace inspect` | 查看概览或详情 | |
| `palace audit` | 查看审计日志 | |
| `palace rooms` | 列出房间 | |
| `palace metrics` | 查看运营指标 | |
| `palace ingest` | 摄取文档 | ✅ |
| `palace curate` | 手动整理 | ✅ |
| `palace import` | 批量导入 | |
| `palace export` | 批量导出 | |
| `palace serve` | 启动 MCP Server | |
| `palace persona list/create/switch/delete` | 角色管理 | |
| `palace schedule start/status` | 后台调度 | ✅ |
| `palace context` | 编译上下文 | |

### mcp_server.py（~891 行）——MCP Server

通过 FastMCP v2 框架暴露 18 个工具和 9 个资源，让 AI Agent（如 Claude Desktop、Cursor）可以直接通过 JSON-RPC 协议调用 Memory Palace 的功能。

**设计亮点**：所有业务逻辑封装在 `_impl_*` 函数里，`@mcp.tool()` 装饰器只做协议层的包装。这样 `_impl_*` 函数可以直接被单元测试调用，不需要启动 MCP 协议栈。

### mcp_context.py——MCP 生命周期管理

管理 MCP Server 的 `MCPServiceManager` 单例——确保同时只有一个 MemoryService 实例在运行，处理启动和关闭时的资源清理。

---

# 第七章：功能实现地图——SPEC 怎么落地

> 本章是第六章的**对偶**：第六章从代码出发（"这个文件干什么"），本章从功能需求出发（"这个功能怎么实现的"）。

当你拿到一个 SPEC 说"我要做 XXX 功能"，工程上到底要动哪些文件、为什么这么拆？

## 7.1 三层存储（Core / Recall / Archival）

**SPEC 要求**：模拟记忆的层级结构——随身口袋、抽屉柜、地下室。高重要性常驻，低重要性按需检索，全量可语义搜索。

**实现拆法**：

| 需求层面 | 对应实现 |
|---------|---------|
| 三种存储引擎 | `store/core_store.py` + `store/recall_store.py` + `store/archival_store.py` |
| 分拣路由（谁进哪层） | `service/memory_service.py` 的 `save()` 方法内部写路由逻辑 |
| Core 预算上限 | `config.py` 的 `CoreConfig.max_items_per_block` |
| 满了自动降级 | `memory_service.py` 的 `_enforce_core_budget()` → demote 到 RecallStore |

**为什么这么拆**：
- 存储引擎各自独立 → 可以独立测试、独立替换
- 路由逻辑放在 Service 层 → Store 层不需要知道其他 Store 的存在
- 预算放在 Config → 不用改代码就能调整

## 7.2 混合检索（FTS5 + Vector + Graph + RRF）

**SPEC 要求**：四因子评分（recency × importance × relevance × proximity），关键词 + 语义 + 空间三通道搜索。

**实现拆法**：

| 需求层面 | 对应实现 |
|---------|---------|
| FTS5 关键词搜索 | `store/recall_store.py` 的 `.search()` |
| Vector 语义搜索 | `store/archival_store.py` 的 `.search()` |
| Graph 邻近搜索 | `store/graph_store.py` 的 `.proximity_score()` |
| 三通道融合 | `service/hybrid_retriever.py` 的 RRF 算法 |
| 四因子排序 | `engine/scoring.py` 的 `rank()` |

**为什么用 RRF 而不是线性加权？** 因为 FTS5 的分数（BM25）和 Vector 的分数（余弦距离）尺度完全不同，直接加权没意义。RRF 只看排名位置、不看绝对分数，天然适合跨来源融合。

**为什么 Graph 是 opt-in？** 因为 5 个房间的场景下图查询没有明显优势（直接判断房间名相同就行了）。只有记忆量到 1000+ 且房间有复杂层级时，Graph 才体现价值。

## 7.3 搬运小人自动化（Curator 7 阶段）

**SPEC 要求**：后台自动扫描、提取事实、调和冲突、反思生成、淘汰过时、健康评估、生成报告。

**实现拆法**：

| 需求层面 | 对应实现 |
|---------|---------|
| 何时触发 | `service/curator.py` 的 `should_trigger()` |
| 自动触发 | `service/scheduler.py` 轮询 + 事件驱动 |
| 7 阶段工作流自身 | `service/curator_graph.py` 的状态机 |
| 事实提取 | `engine/fact_extractor.py`（LLM） |
| 冲突调和 | `engine/reconcile.py`（LLM） |
| 高阶反思 | `engine/reflection.py`（LLM） |
| 遗忘淘汰 | `engine/ebbinghaus.py`（纯数学） |
| 健康评估 | `engine/health.py` |
| 防无限循环 | `service/heartbeat.py` |

**为什么拒绝 LangGraph 用纯 Python？** 最初 SPEC 规划用 LangGraph 做状态机编排。但实际预检发现 LangGraph 拉入 `langchain-core`、`langsmith` 等 13 个传递依赖，而我们的状态机只需要 7 个阶段、线性流转。纯 Python 实现只要一个 `while True` + `match phase` 就搞定，依赖为零。

## 7.4 Ebbinghaus 遗忘衰减（P-3）

**SPEC 要求**：记忆按遗忘曲线自动衰减，复习越多衰减越慢。

**实现链路**：

```
ebbinghaus.py                    # 纯数学公式
    ↑ 被调用
scoring.py                       # effective_importance() 集成衰减
    ↑ 被调用
curator_graph.py (PRUNE 阶段)    # should_prune() 判断是否淘汰
```

**为什么拆成三个文件而不是一个？**
- `ebbinghaus.py` 是纯数学，可以单独测试公式正确性
- `scoring.py` 把衰减集成到评分体系中
- `curator_graph.py` 只关心"要不要淘汰"的决策

## 7.5 Sleep-time 自动调度（P-1）

**SPEC 要求**：定时器 + 事件驱动自动触发 Curator，不需要人手动干预。

**实现**：

```python
# service/scheduler.py
class SleepTimeScheduler:
    async def _loop(self):
        while True:
            # 方式1: 每 5 分钟定时检查
            await asyncio.wait_for(self._event.wait(), timeout=300)
            # 方式2: 收到 notify() 事件立即唤醒
            
            if self.curator.should_trigger():
                await self.curator.run()
```

**为什么用 asyncio.Event 而不是 cron？** 因为 Memory Palace 是一个嵌入式 library，不是独立服务。用 asyncio 可以无缝嵌入到调用方的事件循环里，不需要额外的系统配置。

## 7.6 安全守卫——Heartbeat Controller（P-2）

**SPEC 要求**：防止 Curator 进入无限循环（LLM 可能产生幻觉，让状态机反复执行）。

**实现**：`service/heartbeat.py` — 一个纯计数器对象，嵌入到 `curator_graph.py` 的每个阶段转换中。

```
每次状态转换 → heartbeat.tick() → 超过 50 步抛异常
每次 LLM 调用 → heartbeat.record_llm_call() → 超过 30 次抛异常
持续计时 → heartbeat.check_duration() → 超过 120 秒抛异常
```

## 7.7 MCP Server（P-6）

**SPEC 要求**：把 Memory Palace 的能力通过标准 MCP 协议暴露给 AI Agent。

**实现拆法**：

| 需求层面 | 对应实现 |
|---------|---------|
| 协议层 | `integration/mcp_server.py` — FastMCP v2 框架 |
| 生命周期管理 | `integration/mcp_context.py` — `MCPServiceManager` 单例 |
| 业务逻辑 | `mcp_server.py` 里的 `_impl_*` 函数 |
| 统一错误码 | `models/errors.py` |

**为什么 `_impl_*` 和 `@mcp.tool()` 分离？** 因为 `@mcp.tool()` 需要协议框架运行才能测试。把逻辑放在 `_impl_*` 里，测试时直接调函数就行，不需要启动 MCP 服务。

## 7.8 5-pass 文档摄取（P-10）

**SPEC 要求**：文档 → 原子事实 → 分类 → 关系发现 → 存储，全自动。

**实现**：`service/ingest_pipeline.py` — 一个 5 步管道：

```
DIFF → EXTRACT → MAP → LINK → UPDATE
  │       │        │       │       │
  │       │        │       │       └─ reconcile.py → 各 Store
  │       │        │       └─ LLM → graph_store.py
  │       │        └─ LLM 分配 room + importance
  │       └─ fact_extractor.py
  └─ SHA-256 哈希检查（已处理过的文档跳过）
```

## 7.9 监控指标（P-5）

**SPEC 要求**：p95 延迟、增长率、健康评分、运营仪表盘。

**实现**：
- `engine/metrics.py` — 滑动窗口追踪 p95 延迟、记忆增长率
- `engine/health.py` — 6 维健康评分
- `integration/cli.py` 的 `palace metrics` 和 `palace inspect` 命令展示结果

## 7.10 Multi-persona（P-9）/ Batch Import-Export（P-7, P-8）

| 功能 | 实现 |
|------|------|
| 多角色管理 | `service/persona_manager.py` — 每个 Persona 独立数据目录 |
| 批量导入 Markdown/JSONL | `service/batch_io.py` 的 `BatchImporter` |
| 批量导出 Markdown | `service/batch_io.py` 的 `BatchExporter`（按房间分组） |

## 7.11 功能 ↔ 代码交叉索引表

| SPEC 编号 | 功能名 | 实现文件 | 测试文件 | 关键类/函数 |
|----------|--------|---------|---------|------------|
| P-1 | Sleep-time 调度 | `service/scheduler.py` | `test_scheduler.py` (16) + `test_automation_e2e.py` (10) | `SleepTimeScheduler` |
| P-2 | Heartbeat 守卫 | `service/heartbeat.py` | `test_heartbeat.py` | `HeartbeatController` |
| P-3 | Ebbinghaus 衰减 | `engine/ebbinghaus.py` | `test_ebbinghaus.py` | `retention()`, `effective_importance()` |
| P-4 | Core 预算 | `service/memory_service.py` + `config.py` | `test_memory_service.py` | `_enforce_core_budget()` |
| P-5 | 监控指标 | `engine/metrics.py` + `engine/health.py` | `test_metrics.py` + `test_health.py` | `OperationMetrics`, `HealthScorer` |
| P-6 | MCP Server | `integration/mcp_server.py` + `mcp_context.py` | `test_mcp_server.py` + `test_v10_mcp_tools.py` | `FastMCP`, `MCPServiceManager` |
| P-7 | Batch Import | `service/batch_io.py` | `test_batch_io.py` | `BatchImporter` |
| P-8 | Batch Export | `service/batch_io.py` | `test_batch_io.py` | `BatchExporter` |
| P-9 | Multi-persona | `service/persona_manager.py` | `test_persona_manager.py` | `PersonaManager` |
| P-10 | Ingest Pipeline | `service/ingest_pipeline.py` | `test_ingest_pipeline.py` | `IngestPipeline` |

---

# 第八章：关键设计模式——为什么这么写

## 8.1 Protocol + 依赖注入（vs 继承）

**问题**：系统需要调用 LLM，但不想跟某一家 LLM 绑死。测试时又不想真的调 API。

**解法**：Python `Protocol`（结构化类型）

```python
# 定义"合同"
class LLMProvider(Protocol):
    async def complete(self, prompt: str, ...) -> str: ...

# 真实实现
class OpenAIProvider:
    async def complete(self, prompt, ...) -> str:
        return await httpx_call(...)

# 测试用的假实现
class MockLLM:
    responses = ["预设回答1", "预设回答2"]
    async def complete(self, prompt, ...) -> str:
        return self.responses[self._call_count]
```

**为什么不用继承（ABC）？** Protocol 不需要继承基类——只要你的类恰好有 `complete` 方法且签名匹配，就自动满足 Protocol。这跟 Go 语言的 interface 理念一样：**鸭子类型**——"走起来像鸭子、叫起来像鸭子，那它就是鸭子"。

**好处**：600 个测试全部用 MockLLM，零 API 调用，7.8 秒跑完。

## 8.2 Facade 模式（MemoryService）

**问题**：保存一条记忆需要跟 CoreStore、RecallStore、ArchivalStore、AuditLog、Scheduler 五个组件交互。上层不可能一个一个调。

**解法**：`MemoryService` 是一个 **Facade**——统一的"前台接待"。上层只需要 `service.save("内容")`，前台会自动分拣路由、写审计日志、通知调度器。

```
调用方 ──→ MemoryService.save()
                │
                ├─→ CoreStore 或 RecallStore
                ├─→ ArchivalStore
                ├─→ AuditLog
                └─→ Scheduler.notify()
```

## 8.3 状态机模式（CuratorGraph）

**问题**：搬运小人的整理流程有 7 个阶段，每个阶段可能成功或失败，中途还可能被安全守卫中断。

**解法**：纯 Python 状态机——用一个枚举表示当前阶段，`while` 循环 + `match-case` 驱动流转。

```python
class CuratorPhase(StrEnum):
    GATHER = "gather"
    EXTRACT = "extract"
    RECONCILE = "reconcile"
    REFLECT = "reflect"
    PRUNE = "prune"
    HEALTH_CHECK = "health_check"
    REPORT = "report"
    DONE = "done"

# 核心循环
phase = CuratorPhase.GATHER
while phase != CuratorPhase.DONE:
    heartbeat.tick()                    # 安全检查
    match phase:
        case CuratorPhase.GATHER:
            items = recall_store.get_recent(20)
            phase = CuratorPhase.EXTRACT if items else CuratorPhase.HEALTH_CHECK
        case CuratorPhase.EXTRACT:
            facts = await extractor.extract(text)
            phase = CuratorPhase.RECONCILE
        # ...以此类推
```

**优点**：每个阶段独立可测；流程可观测（随时知道在哪个阶段）；异常处理清晰（某阶段失败可以跳到 REPORT）。

## 8.4 严格分层 + 单向依赖

**规则**：上层可以调下层，下层绝不调上层。

```
Integration → Service → Engine → Store → Foundation → Models
     ↓            ↓         ↓        ↓          ↓
   OK           OK        OK      OK         OK
     ←            ←         ←        ←          ←
   禁止!        禁止!     禁止!   禁止!      禁止!
```

**好处**：
- Foundation 变了不影响 Integration
- 你可以换 Store 的实现（比如 SQLite → PostgreSQL）而不用改 Engine
- 测试时可以从底层开始逐层验证

## 8.5 原子写入

**问题**：CoreStore 写 JSON 文件时如果断电，可能写到一半，文件损坏。

**解法**：先写临时文件，再用 `os.replace()` 原子替换。

```python
# 1. 写到临时文件
with tempfile.NamedTemporaryFile(dir=self.path, delete=False) as f:
    f.write(json_bytes)
    tmp_name = f.name
# 2. 原子替换（操作系统保证要么全替换要么不替换）
os.replace(tmp_name, target_file)
```

## 8.6 软删除 + 版本链

**规则**：永远不物理删除数据。

- 更新 → 旧记忆标记 `SUPERSEDED`，`superseded_by` 指向新版本
- 合并 → 多条旧记忆标记 `MERGED`，新记忆的 `merged_from` 记录来源
- 淘汰 → 标记 `PRUNED`，数据还在

**好处**：完整的变更历史，任何操作都可追溯；配合 Audit Log 可以回答"上个月这条记忆长什么样？"

## 8.7 MockLLM + TDD

**开发纪律**：每一行生产代码都先有测试。

```
1. 写 failing test (RED)     — 先定义"什么是对的"
2. 写最少的代码 (GREEN)      — 刚好让测试通过
3. 重构 (REFACTOR)           — 清理代码

重复直到功能完成
```

**MockLLM** 是测试的核心——预设一组确定性回答，测试时不调真 API。

```python
class MockLLM:
    responses: list[str]     # 预设回答队列
    async def complete(self, prompt, ...):
        return self.responses[self._call_count % len(self.responses)]
```

**效果**：600 个测试、11,552 行测试代码，全在 CI 环境零 API 调用运行。

---

# 第九章：配置与运行——动手跑起来

## 9.1 环境搭建

```bash
# 克隆项目
cd /Users/link/Documents/Agent_Project/memory-palace

# 安装依赖（推荐用 uv，更快）
uv sync --extra dev

# 验证安装
palace --help
python -c "import memory_palace; print(memory_palace.__version__)"
```

如需图存储（KuzuDB）：
```bash
uv sync --extra graph
```

## 9.2 LLM 配置

Memory Palace 支持任何 OpenAI 兼容 API。三种配置方式：

**方式一：环境变量**（推荐，优先级最高）
```bash
# MiniMax（推荐）
export MINIMAX_API_KEY="sk-cp-..."
export MP_LLM__PROVIDER="minimax"
export MP_LLM__MODEL_ID="MiniMax-M2.5"
export MP_LLM__BASE_URL="https://api.minimaxi.com/v1"

# 或 DeepSeek
export DEEPSEEK_API_KEY="sk-..."
export MP_LLM__PROVIDER="deepseek"
export MP_LLM__MODEL_ID="deepseek-chat"
export MP_LLM__BASE_URL="https://api.deepseek.com/v1"
```

**方式二：YAML 配置文件**
```yaml
# ~/.memory_palace/memory_palace.yaml
memory_palace:
  llm:
    provider: minimax
    model_id: MiniMax-M2.5
    base_url: https://api.minimaxi.com/v1
    max_tokens: 2000
```

**方式三：内置默认值**（OpenAI gpt-4o-mini）

> 优先级：环境变量 > YAML > 内置默认值

## 9.3 CLI 速查表

```bash
# ── 基本操作 ──
palace save "我喜欢 Python" --importance 0.8 --room preferences --tags "编程"
palace search "编程语言"
palace update <id> "改为喜欢 Rust" --reason "技术栈切换"
palace forget <id> --reason "不再需要"

# ── 查看 ──
palace inspect              # 概览（各层统计）
palace inspect <id>         # 单条详情 + 审计历史
palace audit --last 20      # 最近 20 条审计
palace rooms                # 房间列表
palace metrics              # 运营指标

# ── 高级操作（需要 LLM）──
palace ingest meeting.txt   # 5-pass 智能摄取
palace curate               # 手动触发搬运小人
palace context --query "项目进展"  # 编译上下文

# ── 批量 ──
palace import notes.md      # 导入 Markdown
palace export output/       # 导出到目录

# ── 服务 ──
palace serve                # 启动 MCP Server（stdio 模式）

# ── 角色 ──
palace persona list
palace persona create work --description "工作助手"
palace persona switch work

# ── 后台调度 ──
palace schedule start       # 启动后台巡检
palace schedule status      # 查看调度状态
```

## 9.4 MCP Server 接入

**Claude Desktop**：
```json
{
  "mcpServers": {
    "memory-palace": {
      "command": "palace-mcp",
      "env": {
        "MINIMAX_API_KEY": "sk-cp-...",
        "MP_LLM__PROVIDER": "minimax",
        "MP_LLM__MODEL_ID": "MiniMax-M2.5",
        "MP_LLM__BASE_URL": "https://api.minimaxi.com/v1"
      }
    }
  }
}
```

`palace-mcp` 和 `palace serve` 在 stdio 模式下会自动抑制非 JSON-RPC 输出，直接兼容 Claude Desktop、Cursor、Codex 等客户端。

## 9.5 跑测试

```bash
# 全量测试（600 个，约 8 秒）
pytest tests/ -v

# 只跑某一层
pytest tests/test_models/ -v         # 数据模型
pytest tests/test_store/ -v          # 存储层
pytest tests/test_engine/ -v         # 引擎层
pytest tests/test_service/ -v        # 服务层
pytest tests/test_e2e/ -v            # 端到端

# 带覆盖率
pytest tests/ --cov=memory_palace --cov-report=term-missing
```

> 所有测试使用 MockLLM，不需要真实 API key。

---

# 第十章：版本演进与踩坑经验（面试章）

> 本章专门为面试准备，汇总了版本演进、关键决策、遇到的问题、以及可以引用的量化指标。

## 10.1 三版迭代的演进逻辑

| 版本 | 代号 | 核心交付 | 源码行数 | 测试数 |
|------|------|---------|---------|-------|
| **v0.1** | 🦴 Skeleton | Pipeline 跑通，两层存储，FTS5 检索 | ~2,000 | ~120 |
| **v0.2** | 🧱 Foundation | 三层存储，混合检索 RRF，Curator 7 阶段状态机，反思 | ~5,200 | 284 |
| **v1.0** | 🏛️ Palace | Sleep-time 调度，Ebbinghaus 衰减，MCP Server，5-pass 摄取 | **8,175** | **600** |

**演进哲学**：Stability before Sophistication。

- v0.1 用最简单的方式验证核心假设：能存、能搜、能整理、能遗忘
- v0.2 补齐关键能力：语义搜索、自动化编排、自我反思
- v1.0 做生产级加固：安全守卫、自动调度、监控、对外接口

## 10.2 关键设计决策（面试高频问）

### "为什么拒绝 LangGraph？"

> **原始计划**：SPEC 规划用 LangGraph 来编排 Curator 的多步状态机。
>
> **发现问题**：预检发现 LangGraph 会拉入 `langchain-core`、`langsmith`、`orjson` 等 13 个传递依赖。对于一个嵌入式 library 来说，这太重了。
>
> **解决方案**：用纯 Python `while` + `match-case` 实现 7 阶段状态机。代码约 400 行，依赖为零。
>
> **教训**：选择库之前先做 `pip install --dry-run` 看传递依赖。框架的价值要大于它带来的复杂度。

### "为什么 Archival 是全量索引而不是低重要性存放地？"

> **原始 SPEC**：Archival = 低重要性记忆的归宿。
>
> **发现问题**：如果高重要性记忆只在 Core（JSON 平文件），就无法被语义搜索找到。
>
> **调整**：Archival 变成所有记忆的全量语义索引层——不管 importance 高低，都同时写入 Archival。
>
> **效果**：搜索"编程偏好"不仅能从 Recall 的关键词匹配找到，还能从 Archival 的语义匹配找到。

### "为什么 CoreStore 用 JSON 平文件而不是 SQLite？"

> Core 的设计意图是"随身口袋"——容量极小（10 条/block），始终全量加载。这种场景下 JSON 文件最简单：读一次全拿到，写一次全更新。不需要 SQL 的复杂查询能力。

### "为什么测试比源码还多？"

> 测试:源码 = 11,552:8,175 = **1.41:1**。
>
> 原因：TDD 纪律——每一行生产代码都先有测试；MockLLM 需要精心预设回答；E2E 测试需要构造完整的场景数据。
>
> 效果：600 个测试在 CI 里 7.8 秒跑完，零 API 调用。任何改动如果破坏了现有行为，测试会立即报红。

## 10.3 遇到的问题与解决

| 问题 | 影响 | 解决方案 |
|------|------|---------|
| FTS5 不支持中文分词 | 搜中文关键词无结果 | `_tokenize_cjk()` 在中文字符间插空格，实现逐字匹配 |
| Core 2KB 预算 vs importance ≥ 0.7 冲突 | 高重要性记忆太多，Core 放不下 | `max_items_per_block` 预算机制 + 自动 demote 最不重要的到 Recall |
| LangGraph 传递依赖太重 | 13 个额外包 | 纯 Python 状态机替代 |
| Curator 可能无限循环 | LLM 幻觉驱动反复执行 | HeartbeatController 三层守卫 |
| MCP stdio 输出污染 | 非 JSON-RPC 内容破坏协议 | `palace-mcp` 入口自动抑制 banner 和日志 |
| Embedding 未配置时搜索降级 | 语义搜索不可用 | HybridRetriever 自动降级到 FTS5-only |

## 10.4 开发方法论

### Dispatcher + SubAgent 模式

v1.0 的开发不是一个人从头写到尾，而是：

- **Dispatcher**（调度者）：制定 12 轮任务计划，编写 context 文档和约束
- **SubAgent**（执行者）：每轮由独立的 Agent 实例执行，自带 TDD 循环

```
R14: SleepTimeScheduler    → 1 个独立 conversation
R15: Ebbinghaus Engine     → 1 个独立 conversation
R16: HeartbeatController   → 1 个独立 conversation
R18: MCP Server Foundation → 1 个独立 conversation
...
```

**好处**：每个 SubAgent 有干净的上下文窗口，不被之前轮次的信息干扰。

### 严格 TDD

每一轮遵循 RED → GREEN → REFACTOR 循环。`pytest tests/ -v` 全绿才能提交。

## 10.5 可引用的量化指标

| 指标 | 数值 | 说明 |
|------|------|------|
| 源码行数 | 8,175 | 46 个 .py 文件 |
| 测试行数 | 11,552 | 56 个测试文件 |
| 测试用例 | 600 passed | 11 skipped（真实 API 测试） |
| 测试:源码比 | 1.41:1 | TDD 纪律的体现 |
| CI 测试耗时 | ~7.8s | 零 API 调用 |
| v0.2→v1.0 净增 | +15,908 行 | 19 个 commits |
| 新增文件 | +16 源码 +21 测试 | |
| 依赖数 | 10 核心 + 1 可选 | 精简依赖策略 |
| CLI 命令 | 19 | Typer 框架 |
| MCP 工具 | 18 tools + 9 resources | FastMCP v2 |

---

# 附录

## 附录 A：术语表

| 术语 | 英文 | 含义 |
|------|------|------|
| 记忆条目 | MemoryItem | 系统中的最小记忆单元（原子事实） |
| 搬运小人 | Curator | 后台自动整理记忆的智能体 |
| 记忆宫殿 | Memory Palace | 整个系统的隐喻名称 |
| 房间 | Room | 记忆的空间分类 |
| 分拣 | Tier Routing | 按 importance 将记忆路由到不同存储层 |
| 降级 | Demote | Core 满了把记忆移到 Recall |
| 提升 | Promote | 从 Recall 提升到 Core |
| 淘汰 | Prune | 标记为 PRUNED（软删除） |
| 调和 | Reconcile | 解决新旧记忆之间的冲突 |
| 反思 | Reflect | 从多条记忆中生成高阶洞察 |
| 遗忘曲线 | Ebbinghaus Curve | 记忆随时间指数衰减的数学模型 |
| 混合检索 | Hybrid Retrieval | FTS5 + Vector + Graph 三通道搜索 |
| 融合排序 | RRF | Reciprocal Rank Fusion，跨通道排名融合 |
| 上下文编译 | Context Compile | 拼装 Core + Retrieved + Recent 给 Agent |
| 心跳守卫 | Heartbeat | 防止 Curator 无限循环的安全机制 |

## 附录 B：文件清单速查表

| 文件 | 层 | 行数 | 一句话 |
|------|---|------|--------|
| `config.py` | Config | ~250 | Pydantic Settings 配置管理 |
| `models/memory.py` | Models | ~80 | MemoryItem、Room 数据定义 |
| `models/audit.py` | Models | ~40 | AuditEntry 审计条目 |
| `models/curator.py` | Models | ~60 | CuratorReport |
| `models/errors.py` | Models | ~30 | 统一错误码 |
| `models/ingest.py` | Models | ~40 | IngestReport |
| `foundation/llm.py` | 1F | ~70 | LLMProvider Protocol |
| `foundation/embedding.py` | 1F | ~50 | EmbeddingProvider Protocol |
| `foundation/audit_log.py` | 1F | ~80 | JSONL 审计日志 |
| `foundation/openai_provider.py` | 1F | ~120 | OpenAI 兼容 LLM 客户端 |
| `foundation/local_embedding.py` | 1F | ~100 | 本地 Embedding |
| `foundation/openai_embedding.py` | 1F | ~80 | OpenAI Embedding |
| `store/core_store.py` | 2F | ~140 | JSON 平文件 Core 存储 |
| `store/recall_store.py` | 2F | ~390 | SQLite FTS5 Recall 存储 |
| `store/archival_store.py` | 2F | ~230 | ChromaDB 向量 Archival 存储 |
| `store/graph_store.py` | 2F | ~300 | KuzuDB 图存储（opt-in） |
| `engine/scoring.py` | 3F | ~240 | 四因子评分 |
| `engine/ebbinghaus.py` | 3F | ~110 | 遗忘曲线 |
| `engine/fact_extractor.py` | 3F | ~90 | LLM 事实提取 |
| `engine/reconcile.py` | 3F | ~130 | LLM 冲突调和 |
| `engine/reflection.py` | 3F | ~140 | LLM 高阶洞察生成 |
| `engine/health.py` | 3F | ~200 | 六维健康评分 |
| `engine/metrics.py` | 3F | ~120 | 运营指标 |
| `service/memory_service.py` | 4F | ~720 | 核心 CRUD Facade |
| `service/hybrid_retriever.py` | 4F | ~320 | FTS5+Vector+Graph 混合检索 |
| `service/curator.py` | 4F | ~180 | 搬运小人协调者 |
| `service/curator_graph.py` | 4F | ~400 | 7 阶段状态机 |
| `service/scheduler.py` | 4F | ~230 | Sleep-time 异步调度 |
| `service/heartbeat.py` | 4F | ~130 | 安全守卫 |
| `service/context_compiler.py` | 4F | ~100 | 上下文编译 |
| `service/ingest_pipeline.py` | 4F | ~350 | 5-pass 摄取管道 |
| `service/batch_io.py` | 4F | ~200 | 批量导入/导出 |
| `service/persona_manager.py` | 4F | ~150 | 多角色管理 |
| `service/retriever.py` | 4F | ~120 | FTS5-only 检索（兼容） |
| `integration/cli.py` | 5F | ~857 | 19 个 CLI 命令 |
| `integration/mcp_server.py` | 5F | ~891 | MCP Server 18 tools |
| `integration/mcp_context.py` | 5F | ~150 | MCP 生命周期管理 |
| `integration/tools.py` | 5F | ~100 | 工具绑定辅助 |

## 附录 C：推荐阅读顺序（按依赖拓扑）

从最底层开始，沿依赖链往上读。**每读一个文件，先看对应的 test 文件**——测试就是活文档。

```
Stage 1: models/ (纯数据，0 依赖)
  → memory.py — 整个系统的"语言"，必须先读
  → curator.py — 搬运小人的"指令集"
  → errors.py — MCP 通信的错误码

Stage 2: foundation/ (接口定义，0 业务逻辑)
  → llm.py — 理解 Protocol 依赖注入的核心
  → embedding.py — 向量化接口
  → audit_log.py — 最简单的 I/O

Stage 3: store/ (存储实现，独立可测)
  → core_store.py — 最简单的 Store（141 行）
  → recall_store.py — 最复杂的 Store（理解 FTS5）
  → archival_store.py — 理解 ChromaDB 向量存储

Stage 4: engine/ (业务算法，纯函数为主)
  → scoring.py — 四因子排序逻辑
  → ebbinghaus.py — 纯数学，直觉性强
  → fact_extractor.py — prompt engineering
  → reconcile.py — LLM 做裁判的模式

Stage 5: service/ (编排层，最大最复杂)
  → memory_service.py — 核心 CRUD，理解 Facade
  → hybrid_retriever.py — 理解 RRF 融合
  → curator.py → curator_graph.py — 状态机
  → scheduler.py — asyncio 事件循环

Stage 6: integration/ (对外接口)
  → cli.py — 逐个命令阅读
  → mcp_server.py — _impl_ 与 @mcp.tool 双层设计
```

---

> **写在最后**：读完本指南，你应该能回答这些问题：
> 1. Memory Palace 跟 mem0/MemGPT 有什么不同？
> 2. 一条记忆从输入到存储经历了什么流程？
> 3. 搜索时三个通道怎么融合？
> 4. 搬运小人的 7 个阶段各做什么？
> 5. 为什么选择纯 Python 状态机而不是 LangGraph？
> 6. 系统的任何一个功能，你能定位到具体哪个文件实现的。
>
> 如果你能回答以上问题，那你已经具备了独立开发和维护这个项目的宏观理解。祝学习顺利！🏛️
