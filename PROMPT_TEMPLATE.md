# Memory Palace — Subagent Prompt 模板

> **用途**: Dispatcher 用此模板生成发给 subagent 的任务 prompt。
> **类型**: STATIC — 模板结构不变，只填变量部分。
> **角色**: Dev (Claude Code) 实现代码，Reviewer (Codex) 审查代码。

---

## A. Dev Prompt 模板（Claude Code）

```markdown
# [TASK_ID]: [TASK_TITLE]

> Agent: Claude Code (Dev) | Priority: [P0/P1/P2] | Round: [1-6]

---

## 开始前（必读）

顺序阅读仓库根目录的以下文件：
1. `DISPATCH_LOG.md` — **先读最新 block**，30 秒了解当前状态和前序工作
2. `PROJECT_CONTEXT.md` — 项目架构、模块拓扑、test baseline
3. `CONVENTIONS.md` — 代码约定、TDD 纪律、并行护栏、Known Gotchas
4. `SPEC.md` — 完整技术 spec（按需查阅接口契约和 Prompt 模板）

---

## TDD Round 上下文

当前处于 Round [N]（共 6 Round）。
- **Round 依赖**: [本 Round 依赖哪些已完成的 Round]
- **测试文件**: [需要解锁的测试路径]
- **实现文件**: [需要实现的源文件路径]
- **前序 Walkthrough**: [DISPATCH_LOG 中相关 TASK 的 Dev walkthrough 摘要]

> [!IMPORTANT]
> 测试已冻结在 `tdd-spec-v0.1` tag。先移除 `@pytest.mark.skip`，看到 RED，再写实现。
> 每个 test case 单独走 Red-Green-Refactor。

---

## 任务

[具体任务规格。包含：
 - 动机/背景
 - 需求规格
 - 文件清单（NEW / MODIFY / DELETE）
 - 接口定义（从 SPEC.md 引用）
 - 设计决策（Dispatcher 已确定 or 需要 Dev 选择）]

---

## 并行保护文件

以下文件正在被其他 agent 修改，**不可触碰**：
- `path/to/file1.py`（[谁在改，做什么]）

_如果你认为某个被保护文件需要修改，在 DISPATCH_LOG 你的 Dev walkthrough 的「已知风险」中记录。_

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

1. `uv run pytest tests/test_[round]/ -v` → 本 Round 全绿
2. `uv run pytest tests/ -q` → baseline 不回归
3. [任务特定验证]

---

## 完成后

在 `DISPATCH_LOG.md` 末尾的当前任务 block 中，填写 `### 🔨 Dev` sub-block：

\```markdown
### 🔨 Dev
- **Agent**: Claude Code
- **Completed**: YYYY-MM-DDTHH:MM
- **Walkthrough**:
  - **实现摘要**: [1-3 句话]
  - **文件清单**:
    - `NEW` path/to/file.py — 简述
    - `MOD` path/to/file.py — 改了什么
  - **关键设计决策**:
    1. [决策 + 理由]
  - **Tests**: before → after (如 0→21 passed, 135→114 skipped)
  - **已知风险**: [后续 Round 需注意的点 / 想改但被禁止的文件]
\```
```

---

## B. Reviewer Prompt 模板（Codex）

```markdown
# [TASK_ID] Review: [TASK_TITLE]

> Agent: Codex (Reviewer) | Priority: [P0/P1/P2] | Round: [1-6]

---

## 开始前（必读）

1. `DISPATCH_LOG.md` — 读当前任务 block 的 `### 🔨 Dev` walkthrough
2. `CONVENTIONS.md` — 代码约定、TDD 纪律、Known Gotchas
3. `SPEC.md` — 接口契约（验证实现是否对齐 SPEC）

---

## Review 范围

- **Branch**: `feat/[branch-name]`
- **Dev Agent**: Claude Code
- **Dev Walkthrough**: 见 DISPATCH_LOG [TASK_ID] `### 🔨 Dev`
- **变更文件**: [Dev walkthrough 中的文件清单]

---

## Review 检查清单

> [!CAUTION]
> 以下每个条目都必须逐一检查。任何一项不通过 = CHANGES_REQUESTED。

### 功能正确性
- [ ] 所有新增/修改的代码与 SPEC 接口契约一致
- [ ] 测试覆盖 happy path + error path + edge case
- [ ] 全量测试通过（`uv run pytest tests/ -q`）

### TDD 纪律
- [ ] 测试未被篡改：`git diff tdd-spec-v0.1 -- tests/` 无意外差异
- [ ] 仅移除了 `@pytest.mark.skip`，断言语义未改变
- [ ] 新增代码通过 Red-Green-Refactor 流程

### 代码质量
- [ ] structlog（无 print/logging）
- [ ] 每个函数有 type hints + docstring
- [ ] Protocol-based DI（无硬编码依赖）
- [ ] 错误处理三层模式
- [ ] `ruff check && ruff format --check` 零 error

### 架构合规
- [ ] 分层依赖方向正确（高层→低层，无逆向引用）
- [ ] Schema 保护文件未被未授权修改
- [ ] Known Gotchas 中的陷阱已正确处理

### Git 规范
- [ ] Commit message 符合 Conventional Commits
- [ ] 一个 commit 做一件事（原子性）
- [ ] 分支命名正确

---

## 完成后

在 `DISPATCH_LOG.md` 当前任务 block 中，填写 `### 🔍 Review` sub-block：

\```markdown
### 🔍 Review
- **Agent**: Codex
- **Reviewed**: YYYY-MM-DDTHH:MM
- **Verdict**: ✅ APPROVED / ⚠️ CHANGES_REQUESTED / 🚫 REJECTED
- **Findings**:
  1. [severity: LOW/MEDIUM/HIGH/CRITICAL] — [描述 + 建议]
  2. ...
- **Test Verification**: `uv run pytest tests/ -q` → [X passed, Y skipped]
- **TDD Integrity**: `git diff tdd-spec-v0.1 -- tests/` → [clean / 差异说明]
\```
```

---

## C. Dispatcher 自用块模板

Dispatcher 在创建任务时，先在 DISPATCH_LOG.md 末尾追加任务 block：

```markdown
## TASK-[NNN]: [Round X] [任务简述] [STATUS_EMOJI]

### 📋 Dispatch
- **Round**: [N]
- **Branch**: `feat/[branch-name]`
- **Priority**: [P0/P1/P2]
- **Dispatched**: YYYY-MM-DDTHH:MM
- **Status**: 🟡 IN_PROGRESS
- **Base**: main @ [commit hash]
- **Parallel Protected**: [被保护文件列表，或「无」]

### 🔨 Dev
_待 Claude Code 填写_

### 🔍 Review
_待 Codex 填写_
```

---

## D. 变量清单

每次生成 prompt 时，Dispatcher 需要填写以下变量：

| 变量 | 示例 | 来源 |
|------|------|------|
| `TASK_ID` | TASK-004 | 自增序号 |
| `TASK_TITLE` | Round 1: Foundation (AuditLog + Config + LLM) | TDD 计划 |
| `Agent` | Claude Code (Dev) / Codex (Reviewer) | 按角色 |
| `Priority` | P0 | 版本规划 |
| `Round` | 1 | TDD 实施顺序 |
| `Round 依赖` | 无（Round 1 = 叶子节点） | 依赖拓扑 |
| `测试文件` | tests/test_foundation/ | SPEC §7.3 |
| `实现文件` | foundation/ + config.py | SPEC §4.1 |
| `任务正文` | 需求 + 文件清单 + 接口定义 | 每次手写 |
| `并行保护文件` | 当前其他分支在改的文件 | 查 DISPATCH_LOG + git |
| `branch-name` | feat/foundation-round1 | 每次命名 |
| `前序 Walkthrough` | DISPATCH_LOG 中相关任务的 Dev 摘要 | 查 DISPATCH_LOG |

---

## E. Round → Prompt 映射速查

| Round | 标题 | 测试文件 | 实现文件 | Tests |
|-------|------|---------|---------| ------|
| 1 | Foundation | test_foundation/ | foundation/ + config.py | 21 |
| 2 | Models | test_models/ | models/ | 21 |
| 3 | Store | test_store/ | store/ | 23 |
| 4 | Engine | test_engine/ | engine/ | 24 |
| 5 | Service | test_service/ | service/ | 27 |
| 6 | E2E | test_e2e/ | integration/ | 2 |

---

## F. Agent 分配规则

| 角色 | 分配给 | 职责 |
|------|--------|------|
| **Dev** | Claude Code | 实现代码：TDD Red→Green→Refactor，写 walkthrough |
| **Reviewer** | Codex | 审查代码：SPEC 对齐、TDD 合规、代码质量、写 findings |
| **Dispatcher** | Antigravity | 架构设计、任务拆解、prompt 生成、仲裁冲突、合并决策 |

### 细分

| 任务特征 | Dev Agent |
|---------|-----------|
| 已有明确测试和接口定义的实现 | Claude Code |
| 批量替换、重命名、格式统一 | Claude Code |
| 架构设计、方案选型、多方案论证 | Antigravity (Dispatcher 自行完成) |
| 调研、文档、prompt 设计 | Antigravity (Dispatcher 自行完成) |

---

## G. Dispatcher 自检清单

每完成一个 TDD Round 后（Review APPROVED + Merged），Dispatcher 必须：

- [ ] 更新 DISPATCH_LOG 当前 block 状态 → ✅ DONE
- [ ] 更新 `PROJECT_CONTEXT.md` 的「当前状态」表（🔴→🟡/🟢）
- [ ] 更新 `PROJECT_CONTEXT.md` 的「测试 Baseline」数字
- [ ] 更新 `PROJECT_CONTEXT.md` 的「模块拓扑」状态图标
- [ ] 更新 `PROJECT_CONTEXT.md` 的「代码规模」统计
- [ ] 检查 `CONVENTIONS.md` 的 `<!-- SEMI-FIXED -->` 标记是否需要更新
- [ ] 运行 `git diff tdd-spec-v0.1 -- tests/` 验证测试完整性

---

## H. 任务生命周期

```
Dispatcher 创建任务 block (📋 Dispatch)
    │
    ├─ 生成 Dev Prompt → 发给 Claude Code
    │
    ▼
Claude Code 执行 → 写 Dev walkthrough (🔨 Dev)
    │
    ├─ Dispatcher 生成 Reviewer Prompt → 发给 Codex
    │
    ▼
Codex 审查 → 写 Review findings (🔍 Review)
    │
    ├── ✅ APPROVED → Dispatcher merge + 更新状态
    ├── ⚠️ CHANGES_REQUESTED → Dispatcher 生成修复 prompt → Claude Code
    └── 🚫 REJECTED → Dispatcher 重新设计
```
