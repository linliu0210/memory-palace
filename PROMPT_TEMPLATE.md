# Memory Palace — Subagent Prompt 模板

> **用途**: Orchestrator 用此模板生成发给 subagent 的任务 prompt。
> **类型**: STATIC — 模板结构不变，只填变量部分。

---

## 模板结构

```markdown
# [TASK_TITLE]

> Agent: [Antigravity / Claude Code] | Priority: [P0/P1/P2] | Round: [1-6]

---

## 开始前（必读）

顺序阅读仓库根目录的以下文件：
1. `PROJECT_CONTEXT.md` — 项目全貌、模块拓扑、当前状态
2. `CONVENTIONS.md` — 代码约定、TDD 纪律、并行护栏、Dispatch 协议
3. `DISPATCH_LOG.md` — 其他 agent 的进展（只读，不修改已有 entry）
4. `SPEC.md` — 完整技术 spec（需要时查阅接口契约和 Prompt 模板）

---

## TDD Round 上下文

当前处于 Round [N]（共 6 Round）。
- **Round 依赖**: [本 Round 依赖哪些已完成的 Round]
- **测试文件**: [本 Round 需要先写的测试文件路径]
- **实现文件**: [本 Round 需要实现的源文件路径]

> [!IMPORTANT]
> 先写测试，看到 RED，再写实现。每个 test case 单独走 Red-Green-Refactor。

---

## 任务

[具体任务规格。包含：
 - 动机/背景
 - 需求规格
 - 文件清单（NEW / MODIFY / DELETE）
 - 接口定义（从 SPEC.md 引用）
 - 设计决策空间（如有多个方案需要选择）]

---

## 并行保护文件

以下文件正在被其他 agent 修改，**不可触碰**：
- `path/to/file1.py`（[谁在改，做什么]）
- `path/to/file2.py`（[谁在改，做什么]）

_如果你认为某个被保护文件需要修改，在 DISPATCH_LOG 的 Issues found 中记录。_

---

## Git

\```bash
git checkout main
git checkout -b feat/[branch-name]
# ... 工作 ...
git commit -m "[type]([scope]): [description]"
\```

---

## 验收

> 固定验证命令见 `CONVENTIONS.md` 第六节，此处仅列出任务特定的额外检查。

1. [任务特定验证命令或检查点]
2. [任务特定验证命令或检查点]

---

## 完成后

在 `DISPATCH_LOG.md` 末尾追加 entry（格式见 `CONVENTIONS.md` 第七节）。
```

---

## 变量清单

每次生成 prompt 时，Orchestrator 需要填写以下变量：

| 变量 | 示例 | 来源 |
|------|------|------|
| `TASK_TITLE` | Round 3: CoreStore + RecallStore | TDD 计划 |
| `Agent` | Antigravity | 按任务类型分配 |
| `Priority` | P0 | 版本规划 |
| `Round` | 3 | TDD 实施顺序 |
| `Round 依赖` | Round 1 (Foundation) + Round 2 (Models) | 依赖拓扑 |
| `测试文件` | tests/test_store/test_core_store.py | SPEC §5.3 |
| `实现文件` | src/memory_palace/store/core_store.py | SPEC §3.2 |
| `任务正文` | 需求 + 文件清单 + 接口定义 | 每次手写 |
| `并行保护文件` | 当前其他分支在改的文件 | 查 DISPATCH_LOG + git |
| `branch-name` | feat/store-core-recall | 每次命名 |
| `任务特定验证` | pytest tests/test_store/ -v | 按需 |

---

## Round → Prompt 映射速查

| Round | 标题 | 测试文件 | 实现文件 |
|-------|------|---------|---------|
| 1 | Foundation | test_foundation/ | foundation/ + config.py |
| 2 | Models | test_models/ | models/ |
| 3 | Store | test_store/ | store/ |
| 4 | Engine | test_engine/ | engine/ |
| 5 | Service | test_service/ | service/ |
| 6 | E2E | test_e2e/ | integration/ |

---

## Agent 分配规则

| 任务特征 | 分配给 |
|---------|--------|
| 需要架构设计、方案选型、多方案论证 | Antigravity |
| 已有明确测试用例和接口定义的实现 | Claude Code |
| 调研、文档、prompt 设计 | Antigravity |
| 批量替换、重命名、格式统一 | Claude Code |

---

## Orchestrator 自检清单

每完成一个 TDD Round 后，Orchestrator 必须：

- [ ] 更新 `PROJECT_CONTEXT.md` 的「当前状态」表（🔴→🟡/🟢）
- [ ] 更新 `PROJECT_CONTEXT.md` 的「测试 Baseline」数字
- [ ] 更新 `PROJECT_CONTEXT.md` 的「模块拓扑」状态图标
- [ ] 更新 `PROJECT_CONTEXT.md` 的「代码规模」统计
- [ ] 检查 `CONVENTIONS.md` 的 `<!-- SEMI-FIXED -->` 标记是否需要更新
- [ ] 确认 `DISPATCH_LOG.md` 中该 Round 的 entry 状态为 ✅
