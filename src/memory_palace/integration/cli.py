"""CLI — Typer command-line interface for Memory Palace.

Provides ``palace`` commands for all memory operations:
save, save-batch, search, update, forget, curate, inspect, audit, rooms.

Ref: SPEC v2.0 §4.4, §5.6
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="palace",
    help="Memory Palace — AI 记忆管理系统",
    no_args_is_help=True,
)
console = Console()


# ── Shared helpers ────────────────────────────────────────────────────


def _resolve_data_dir(data_dir: str) -> Path:
    """Expand ``~`` and ensure the data directory exists."""
    path = Path(data_dir).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    # CoreStore needs a core/ sub-directory
    (path / "core").mkdir(exist_ok=True)
    return path


def _build_memory_service(data_dir: Path, need_llm: bool = False):
    """Build a MemoryService, optionally with an LLM provider."""
    from memory_palace.service.memory_service import MemoryService

    llm = None
    if need_llm:
        llm = _build_llm_provider(data_dir)

    return MemoryService(data_dir, llm=llm)


def _build_llm_provider(data_dir: Path):
    """Build an OpenAIProvider from config (YAML or defaults)."""
    from memory_palace.foundation.llm import ModelConfig
    from memory_palace.foundation.openai_provider import OpenAIProvider

    yaml_path = data_dir / "memory_palace.yaml"
    if yaml_path.exists():
        from memory_palace.config import Config

        cfg = Config.from_yaml(yaml_path)
        model_config = ModelConfig(
            provider=cfg.llm.provider,
            model_id=cfg.llm.model_id,
            base_url=cfg.llm.base_url,
            max_tokens=cfg.llm.max_tokens,
        )
    else:
        model_config = ModelConfig()

    return OpenAIProvider(model_config)


# ── Room list (from Config defaults) ─────────────────────────────────

DEFAULT_ROOMS = [
    ("general", "未分类通用记忆"),
    ("preferences", "用户偏好"),
    ("projects", "项目知识"),
    ("people", "人物关系"),
    ("skills", "技能记忆"),
]


# ── Commands ──────────────────────────────────────────────────────────


@app.command()
def save(
    content: str = typer.Argument(..., help="记忆内容"),
    importance: float = typer.Option(0.5, help="重要性 0.0-1.0"),
    room: str = typer.Option("general", help="房间名"),
    tags: str = typer.Option("", help="标签，逗号分隔"),
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """保存一条记忆。"""
    try:
        path = _resolve_data_dir(data_dir)
        svc = _build_memory_service(path)
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        item = svc.save(content=content, importance=importance, room=room, tags=tag_list)
        console.print(f"[green]✓[/green] 记忆已保存  id={item.id[:8]}…  tier={item.tier}")
    except Exception as exc:
        console.print(f"[red]✗ 保存失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command("save-batch")
def save_batch(
    file: str = typer.Option(..., help="输入文件路径"),
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """从文件批量提取记忆（需要 LLM）。"""
    try:
        path = _resolve_data_dir(data_dir)
        svc = _build_memory_service(path, need_llm=True)
        file_path = Path(file).expanduser()
        if not file_path.exists():
            console.print(f"[red]✗ 文件不存在：{file}[/red]")
            raise typer.Exit(code=1)

        text = file_path.read_text(encoding="utf-8")
        texts = [text]  # Treat entire file as one batch input
        items = asyncio.run(svc.save_batch(texts))
        console.print(f"[green]✓[/green] 批量提取完成，共保存 {len(items)} 条记忆")
    except typer.Exit:
        raise
    except Exception as exc:
        console.print(f"[red]✗ 批量保存失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def search(
    query: str = typer.Argument(..., help="搜索查询"),
    top_k: int = typer.Option(5, help="返回条数"),
    room: str = typer.Option(None, help="房间过滤"),
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """搜索记忆。"""
    try:
        path = _resolve_data_dir(data_dir)
        svc = _build_memory_service(path)
        results = svc.search(query=query, top_k=top_k, room=room)

        if not results:
            console.print("[yellow]未找到匹配的记忆。[/yellow]")
            return

        table = Table(title=f"搜索结果：「{query}」")
        table.add_column("ID", style="dim", max_width=8)
        table.add_column("内容", min_width=30)
        table.add_column("重要性", justify="right")
        table.add_column("房间", style="cyan")
        table.add_column("标签")

        for item in results:
            table.add_row(
                item.id[:8],
                item.content[:60] + ("…" if len(item.content) > 60 else ""),
                f"{item.importance:.2f}",
                item.room,
                ", ".join(item.tags) if item.tags else "—",
            )

        console.print(table)
    except Exception as exc:
        console.print(f"[red]✗ 搜索失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def update(
    memory_id: str = typer.Argument(..., help="记忆 ID"),
    new_content: str = typer.Argument(..., help="新内容"),
    reason: str = typer.Option("user update", help="更新原因"),
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """更新一条记忆（版本更新）。"""
    try:
        path = _resolve_data_dir(data_dir)
        svc = _build_memory_service(path)
        new_item = svc.update(memory_id, new_content, reason)
        console.print(
            f"[green]✓[/green] 记忆已更新  "
            f"old={memory_id[:8]}… → new={new_item.id[:8]}…  v{new_item.version}"
        )
    except ValueError as exc:
        console.print(f"[red]✗ 更新失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]✗ 更新失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def forget(
    memory_id: str = typer.Argument(..., help="记忆 ID"),
    reason: str = typer.Option("user request", help="遗忘原因"),
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """软删除一条记忆。"""
    try:
        path = _resolve_data_dir(data_dir)
        svc = _build_memory_service(path)
        success = svc.forget(memory_id, reason)
        if success:
            console.print(f"[green]✓[/green] 记忆已遗忘  id={memory_id[:8]}…")
        else:
            console.print(f"[yellow]未找到记忆 {memory_id[:8]}…[/yellow]")
    except Exception as exc:
        console.print(f"[red]✗ 遗忘失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def curate(
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """手动触发搬运小人（需要 LLM）。"""
    try:
        path = _resolve_data_dir(data_dir)
        llm = _build_llm_provider(path)

        from memory_palace.service.curator import CuratorService

        curator = CuratorService(path, llm)
        report = asyncio.run(curator.run())

        console.print("[green]✓[/green] 搬运小人完成整理")
        console.print(f"  提取事实: {report.facts_extracted}")
        console.print(f"  新增记忆: {report.memories_created}")
        console.print(f"  更新记忆: {report.memories_updated}")
        console.print(f"  淘汰记忆: {report.memories_pruned}")
        console.print(f"  耗时: {report.duration_seconds:.2f}s")
        if report.errors:
            console.print(f"  [yellow]错误: {len(report.errors)}[/yellow]")
            for err in report.errors:
                console.print(f"    ⚠ {err}")
    except Exception as exc:
        console.print(f"[red]✗ 搬运小人运行失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def inspect(
    memory_id: str = typer.Argument(None, help="记忆 ID（可选，不填则显示概览）"),
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """查看记忆概览或单条详情。"""
    try:
        path = _resolve_data_dir(data_dir)
        svc = _build_memory_service(path)

        if memory_id is None:
            # Overview mode
            s = svc.stats()
            console.print("[bold]Memory Palace 概览[/bold]")
            console.print(f"  Core 记忆数: {s['core_count']}")
            console.print(f"  Recall 记忆数: {s['recall_count']}")
            console.print(f"  总计: {s['total']}")
            if s["core_blocks"]:
                console.print(f"  Core blocks: {', '.join(s['core_blocks'])}")
        else:
            # Single item detail
            from memory_palace.store.recall_store import RecallStore

            recall_store = RecallStore(path)
            item = recall_store.get(memory_id)
            if item is None:
                # Try core
                from memory_palace.store.core_store import CoreStore

                core_store = CoreStore(path)
                for block in core_store.list_blocks():
                    for ci in core_store.load(block):
                        if ci.id == memory_id:
                            item = ci
                            break
                    if item is not None:
                        break

            if item is None:
                console.print(f"[yellow]未找到记忆 {memory_id[:8]}…[/yellow]")
                return

            table = Table(title=f"记忆详情 — {item.id[:8]}…")
            table.add_column("字段", style="bold")
            table.add_column("值")
            table.add_row("ID", item.id)
            table.add_row("内容", item.content)
            table.add_row("类型", str(item.memory_type))
            table.add_row("层级", str(item.tier))
            table.add_row("重要性", f"{item.importance:.2f}")
            table.add_row("房间", item.room)
            table.add_row("标签", ", ".join(item.tags) if item.tags else "—")
            table.add_row("状态", str(item.status))
            table.add_row("版本", str(item.version))
            table.add_row("创建时间", str(item.created_at))
            table.add_row("访问次数", str(item.access_count))
            if item.parent_id:
                table.add_row("父记忆", item.parent_id)
            if item.change_reason:
                table.add_row("变更原因", item.change_reason)
            console.print(table)

            # Show audit trail
            from memory_palace.foundation.audit_log import AuditLog

            audit_log = AuditLog(path)
            entries = audit_log.read(memory_id=memory_id)
            if entries:
                console.print(f"\n[bold]审计记录 ({len(entries)} 条)[/bold]")
                for entry in entries[-5:]:
                    console.print(
                        f"  [{entry.timestamp.strftime('%Y-%m-%d %H:%M')}] "
                        f"{entry.action} by {entry.actor}"
                    )
    except Exception as exc:
        console.print(f"[red]✗ 检查失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def audit(
    last: int = typer.Option(20, help="显示最近 N 条审计日志"),
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """查看审计日志。"""
    try:
        path = _resolve_data_dir(data_dir)
        from memory_palace.foundation.audit_log import AuditLog

        audit_log = AuditLog(path)
        entries = audit_log.read()

        if not entries:
            console.print("[yellow]暂无审计日志。[/yellow]")
            return

        # Show last N entries
        entries = entries[-last:]

        table = Table(title=f"审计日志（最近 {len(entries)} 条）")
        table.add_column("时间", style="dim")
        table.add_column("操作", style="bold")
        table.add_column("记忆 ID", max_width=8)
        table.add_column("执行者")
        table.add_column("详情")

        for entry in entries:
            details_str = ", ".join(f"{k}={v}" for k, v in entry.details.items())
            table.add_row(
                entry.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                str(entry.action),
                entry.memory_id[:8],
                entry.actor,
                details_str[:50] + ("…" if len(details_str) > 50 else ""),
            )

        console.print(table)
    except Exception as exc:
        console.print(f"[red]✗ 审计读取失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def rooms(
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """列出所有房间。"""
    try:
        table = Table(title="记忆宫殿 — 房间列表")
        table.add_column("房间", style="bold cyan")
        table.add_column("描述")

        for name, desc in DEFAULT_ROOMS:
            table.add_row(name, desc)

        console.print(table)
    except Exception as exc:
        console.print(f"[red]✗ 获取房间列表失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc
