# Round 21 — Batch Import/Export

> **Round**: 21 / Phase C  
> **分支**: `feat/v1.0-phase-c` (从 Phase B 完成后的 main 开)  
> **前置**: Phase B 完成 (R18-R20)  
> **交付**: BatchImporter (Markdown + JSONL) + BatchExporter + CLI + MCP Tools

---

## 目标

支持 Markdown/JSONL 批量导入导出，让用户能快速迁移数据或构建知识库。

---

## 必读文档

1. `PROJECT_CONTEXT_V10.md` + `CONVENTIONS_V10.md`
2. `src/memory_palace/service/memory_service.py` — save() 和 save_batch() 接口
3. `src/memory_palace/models/memory.py` — MemoryItem 字段

---

## 交付件

### 1. [NEW] `src/memory_palace/service/batch_io.py`

```python
@dataclass
class ImportReport:
    total_found: int
    imported: int
    skipped: int       # 重复
    errors: list[str]
    duration_seconds: float

@dataclass
class ExportReport:
    total_exported: int
    output_path: str
    duration_seconds: float


class BatchImporter:
    """Import memories from files."""
    
    def __init__(self, memory_service: MemoryService): ...
    
    async def import_markdown(self, path: Path) -> ImportReport:
        """导入 Markdown 文件.
        每个 ## heading 视为一条记忆。
        YAML frontmatter (如有) 解析为 importance, room, tags。
        """
    
    async def import_jsonl(self, path: Path) -> ImportReport:
        """导入 JSONL 文件.
        每行 JSON: {"content": "...", "importance": 0.5, "room": "...", "tags": []}
        """


class BatchExporter:
    """Export memories to files."""
    
    def __init__(self, memory_service: MemoryService): ...
    
    def export_markdown(self, output_dir: Path) -> ExportReport:
        """每个 room 导出为一个 .md 文件。
        文件名: {room}.md
        格式: # {room}\n\n## {id[:8]}\n{content}\n---\n
        """
    
    def export_jsonl(self, output_path: Path) -> ExportReport:
        """全量导出为单个 JSONL 文件。
        每行: item.model_dump() (JSON serializable)
        """
```

### 2. [MODIFY] `src/memory_palace/integration/cli.py`

```python
@app.command("import")
def import_cmd(
    file: str = typer.Argument(..., help="输入文件 (.md 或 .jsonl)"),
    data_dir: str = typer.Option("~/.memory_palace"),
) -> None:
    """批量导入记忆."""

@app.command("export")
def export_cmd(
    output: str = typer.Argument(..., help="输出路径 (目录=Markdown, 文件=JSONL)"),
    format: str = typer.Option("markdown", help="格式: markdown | jsonl"),
    data_dir: str = typer.Option("~/.memory_palace"),
) -> None:
    """批量导出记忆."""
```

### 3. [MODIFY] `src/memory_palace/integration/mcp_server.py`

新增 2 个 Tools:
```python
@mcp.tool
async def import_memories(file_path: str) -> dict:
    """从文件批量导入."""

@mcp.tool
def export_memories(output_path: str, format: str = "jsonl") -> dict:
    """批量导出."""
```

### 4. [NEW] `tests/test_service/test_batch_io.py`

```
test_import_markdown_basic — 3 个 heading → 3 条记忆
test_import_markdown_with_frontmatter — YAML importance/room 解析
test_import_markdown_empty — 空文件 → 0 条
test_import_jsonl_basic — 3 行 → 3 条
test_import_jsonl_invalid_line — 跳过坏行, errors 记录
test_import_jsonl_duplicate — 重复 content 跳过
test_export_markdown — 导出后文件存在, 内容正确
test_export_markdown_per_room — 每个房间一个文件
test_export_jsonl — 导出后每行可解析为 dict
test_export_jsonl_roundtrip — 导出 → 导入 → 记忆数量一致
test_import_nonexistent_file — FileNotFoundError 处理
test_import_report_fields — report 字段完整
test_export_report_fields — report 字段完整
```

预计 ~15 tests。

---

## 约束

1. Markdown 解析用正则 + 简单分割，不引入 markdown 解析库
2. 导入时检查重复 (content hash)，跳过已存在的
3. 导出的 datetime 字段转 ISO string
4. 不修改 MemoryItem 模型

---

## 验证

```bash
pytest tests/ -q
pytest tests/test_service/test_batch_io.py -v
ruff check
git commit -m "feat(R21): Batch Import/Export for Markdown and JSONL"
```
