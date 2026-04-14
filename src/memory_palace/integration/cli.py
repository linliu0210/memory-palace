"""CLI — Typer command-line interface for Memory Palace.

Provides ``palace`` commands for all memory operations:
save, save-batch, search, update, forget, curate, inspect, audit, rooms,
schedule start, schedule status.

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


def _resolve_persona_data_dir(
    persona: str | None, data_dir: str = "~/.memory_palace"
) -> Path:
    """Resolve effective data directory: --persona overrides --data-dir."""
    if persona is None:
        return _resolve_data_dir(data_dir)

    from memory_palace.config import Config
    from memory_palace.service.persona_manager import PersonaManager

    base = Path(data_dir).expanduser()
    yaml_path = base / "memory_palace.yaml"
    if yaml_path.exists():
        cfg = Config.from_yaml(yaml_path)
    else:
        cfg = Config()
    mgr = PersonaManager(cfg, config_path=yaml_path)
    persona_cfg = mgr._find_persona(persona)
    if persona_cfg is None:
        console.print(f"[red]✗ Persona '{persona}' 不存在[/red]")
        raise typer.Exit(code=1)
    return _resolve_data_dir(persona_cfg.data_dir)


def _build_memory_service(data_dir: Path, need_llm: bool = False):
    """Build a MemoryService with full v1.0 stack.

    Wires embedding → archival → graph based on config.
    Gracefully degrades: no API key → FTS-only, no kuzu → no graph.
    """
    from memory_palace.service.memory_service import MemoryService

    llm = None
    if need_llm:
        llm = _build_llm_provider(data_dir)

    # Embedding + Archival
    embedding = _build_embedding_provider(data_dir)
    archival_store = None
    if embedding is not None:
        from memory_palace.store.archival_store import ArchivalStore

        archival_store = ArchivalStore(data_dir=data_dir, embedding=embedding)

    # Graph (optional — only when config.graph.enabled)
    graph_store = None
    try:
        from memory_palace.config import Config

        yaml_path = data_dir / "memory_palace.yaml"
        cfg = Config.from_yaml(yaml_path) if yaml_path.exists() else Config()
        if cfg.graph.enabled:
            from memory_palace.store.graph_store import GraphStore

            graph_store = GraphStore(data_dir)
    except ImportError:
        pass  # kuzu not installed — degrade gracefully

    return MemoryService(
        data_dir,
        llm=llm,
        archival_store=archival_store,
        embedding=embedding,
        graph_store=graph_store,
    )


def _build_llm_provider(data_dir: Path):
    """Build an OpenAIProvider from config (YAML, env vars, or defaults)."""
    from memory_palace.config import Config
    from memory_palace.foundation.llm import ModelConfig
    from memory_palace.foundation.openai_provider import OpenAIProvider

    yaml_path = data_dir / "memory_palace.yaml"
    if yaml_path.exists():
        cfg = Config.from_yaml(yaml_path)
    else:
        # Config() reads MP_LLM__* environment variables via BaseSettings
        cfg = Config()

    model_config = ModelConfig(
        provider=cfg.llm.provider,
        model_id=cfg.llm.model_id,
        base_url=cfg.llm.base_url,
        max_tokens=cfg.llm.max_tokens,
    )

    return OpenAIProvider(model_config)


def _build_embedding_provider(data_dir: Path):
    """Build an EmbeddingProvider from config (YAML or defaults).

    Returns None if no API key is available and provider is not local.
    """
    from memory_palace.config import Config
    from memory_palace.foundation.embedding import EmbeddingConfig

    yaml_path = data_dir / "memory_palace.yaml"
    if yaml_path.exists():
        cfg = Config.from_yaml(yaml_path)
        emb_cfg = cfg.embedding
    else:
        emb_cfg = EmbeddingConfig()

    if emb_cfg.provider == "local":
        # Local embedding (sentence-transformers)
        from memory_palace.foundation.local_embedding import LocalEmbedding

        return LocalEmbedding(emb_cfg)
    else:
        # OpenAI-compatible embedding — requires API key
        import os

        if not os.environ.get("OPENAI_API_KEY"):
            return None
        from memory_palace.foundation.openai_embedding import OpenAIEmbedding

        return OpenAIEmbedding(config=emb_cfg)


# ── Room list (from Config) ───────────────────────────────────────────


def _get_rooms() -> list[tuple[str, str]]:
    """Load rooms from Config (single source of truth)."""
    from memory_palace.config import Config
    try:
        cfg = Config()
        return [(r.name, r.description) for r in cfg.rooms]
    except Exception:
        return [
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
    persona: str = typer.Option(None, help="Persona 名"),
) -> None:
    """保存一条记忆。"""
    try:
        path = _resolve_persona_data_dir(persona, data_dir)
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
    persona: str = typer.Option(None, help="Persona 名"),
) -> None:
    """搜索记忆。"""
    try:
        path = _resolve_persona_data_dir(persona, data_dir)
        svc = _build_memory_service(path)
        results = svc.search_sync(query=query, top_k=top_k, room=room)

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
    persona: str = typer.Option(None, help="Persona 名"),
) -> None:
    """更新一条记忆（版本更新）。"""
    try:
        path = _resolve_persona_data_dir(persona, data_dir)
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
    persona: str = typer.Option(None, help="Persona 名"),
) -> None:
    """软删除一条记忆。"""
    try:
        path = _resolve_persona_data_dir(persona, data_dir)
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
        if report.ebbinghaus_pruned:
            console.print(f"  Ebbinghaus 淘汰: {report.ebbinghaus_pruned}")
        console.print(f"  耗时: {report.duration_seconds:.2f}s")

        # Heartbeat stats (from CuratorService._heartbeat)
        heartbeat = curator._heartbeat
        if heartbeat is not None:
            hb_stats = heartbeat.stats
            console.print(
                f"  心跳: steps={hb_stats['steps']}  "
                f"llm_calls={hb_stats['llm_calls']}  "
                f"elapsed={hb_stats['elapsed_seconds']:.1f}s"
            )

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
    persona: str = typer.Option(None, help="Persona 名"),
) -> None:
    """查看记忆概览或单条详情。"""
    try:
        path = _resolve_persona_data_dir(persona, data_dir)
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

        for name, desc in _get_rooms():
            table.add_row(name, desc)

        console.print(table)
    except Exception as exc:
        console.print(f"[red]✗ 获取房间列表失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def metrics(
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
    persona: str = typer.Option(None, help="Persona 名"),
) -> None:
    """查看运营指标（延迟、增长率等）。"""
    try:
        path = _resolve_persona_data_dir(persona, data_dir)
        svc = _build_memory_service(path)
        m = svc.get_metrics()

        table = Table(title="Memory Palace — 运营指标")
        table.add_column("指标", style="bold cyan")
        table.add_column("值", justify="right")

        table.add_row("搜索 P95 延迟", f"{m['search_p95_ms']:.1f} ms")
        table.add_row("保存 P95 延迟", f"{m['save_p95_ms']:.1f} ms")
        table.add_row("整理平均耗时", f"{m['curator_avg_duration_s']:.2f} s")
        table.add_row("日增长率", f"{m['growth_rate_per_day']:.1f} 条/天")
        table.add_row("总搜索次数", str(m["total_searches"]))
        table.add_row("总保存次数", str(m["total_saves"]))
        table.add_row("总整理次数", str(m["total_curations"]))

        console.print(table)
    except Exception as exc:
        console.print(f"[red]✗ 获取指标失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


# ── Import / Export commands ──────────────────────────────────────────


@app.command("import")
def import_cmd(
    file: str = typer.Argument(..., help="输入文件 (.md 或 .jsonl)"),
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """批量导入记忆."""
    try:
        path = _resolve_data_dir(data_dir)
        svc = _build_memory_service(path)

        from memory_palace.service.batch_io import BatchImporter

        importer = BatchImporter(svc)
        file_path = Path(file).expanduser()

        if file_path.suffix == ".jsonl":
            report = asyncio.run(importer.import_jsonl(file_path))
        else:
            report = asyncio.run(importer.import_markdown(file_path))

        console.print("[green]✓[/green] 导入完成")
        console.print(
            f"  发现: {report.total_found}  导入: {report.imported}"
            f"  跳过: {report.skipped}"
        )
        console.print(f"  耗时: {report.duration_seconds:.2f}s")
        if report.errors:
            console.print(f"  [yellow]错误: {len(report.errors)}[/yellow]")
            for err in report.errors:
                console.print(f"    ⚠ {err}")
    except FileNotFoundError as exc:
        console.print(f"[red]✗ 文件不存在：{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]✗ 导入失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command("export")
def export_cmd(
    output: str = typer.Argument(..., help="输出路径 (目录=Markdown, 文件=JSONL)"),
    format: str = typer.Option("markdown", help="格式: markdown | jsonl"),
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """批量导出记忆."""
    try:
        path = _resolve_data_dir(data_dir)
        svc = _build_memory_service(path)

        from memory_palace.service.batch_io import BatchExporter

        exporter = BatchExporter(svc)
        output_path = Path(output).expanduser()

        if format == "jsonl":
            report = exporter.export_jsonl(output_path)
        else:
            report = exporter.export_markdown(output_path)

        console.print("[green]✓[/green] 导出完成")
        console.print(f"  导出: {report.total_exported} 条记忆")
        console.print(f"  路径: {report.output_path}")
        console.print(f"  耗时: {report.duration_seconds:.2f}s")
    except Exception as exc:
        console.print(f"[red]✗ 导出失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


# ── Ingest command ────────────────────────────────────────────────────


@app.command()
def ingest(
    file: str = typer.Argument(..., help="文档路径"),
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
    persona: str = typer.Option(None, help="Persona 名"),
) -> None:
    """5-pass 智能摄取文档."""
    try:
        path = _resolve_persona_data_dir(persona, data_dir)
        llm = _build_llm_provider(path)

        from memory_palace.engine.fact_extractor import FactExtractor
        from memory_palace.engine.reconcile import ReconcileEngine
        from memory_palace.service.ingest_pipeline import IngestPipeline
        from memory_palace.service.memory_service import MemoryService

        svc = MemoryService(path, llm=llm)
        extractor = FactExtractor(llm)
        reconciler = ReconcileEngine(llm)
        pipeline = IngestPipeline(
            memory_service=svc,
            fact_extractor=extractor,
            reconcile_engine=reconciler,
            llm=llm,
        )

        file_path = Path(file).expanduser()
        report = asyncio.run(pipeline.ingest_file(file_path))

        console.print("[green]✓[/green] 摄取完成")
        console.print(f"  输入字符: {report.total_input_chars}")
        console.print(f"  创建记忆: {report.memories_created}")
        console.print(f"  创建关联: {report.relations_created}")
        console.print(f"  耗时: {report.duration_seconds:.2f}s")

        if report.pass_results.get("diff", {}).get("skipped"):
            console.print("  [yellow]文档已处理过，跳过[/yellow]")

        if report.errors:
            console.print(f"  [yellow]错误: {len(report.errors)}[/yellow]")
            for err in report.errors:
                console.print(f"    ⚠ {err}")
    except FileNotFoundError as exc:
        console.print(f"[red]✗ 文件不存在：{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]✗ 摄取失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


# ── Schedule commands ─────────────────────────────────────────────────

schedule_app = typer.Typer(name="schedule", help="Sleep-time 调度管理")
app.add_typer(schedule_app)


@schedule_app.command("start")
def schedule_start(
    check_interval: int = typer.Option(300, help="检查间隔(秒)"),
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """启动后台 Sleep-time 调度 (Ctrl+C 停止)。"""
    try:
        path = _resolve_data_dir(data_dir)
        llm = _build_llm_provider(path)

        from memory_palace.service.curator import CuratorService
        from memory_palace.service.memory_service import MemoryService
        from memory_palace.service.scheduler import SleepTimeScheduler

        ms = MemoryService(path, llm)
        curator = CuratorService(path, llm)
        # Wire up MemoryService ↔ CuratorService ↔ Scheduler
        ms._curator = curator
        scheduler = SleepTimeScheduler(curator, check_interval=check_interval)
        ms.set_scheduler(scheduler)

        console.print(
            f"[green]✓[/green] Sleep-time 调度启动  interval={check_interval}s  "
            f"data_dir={path}"
        )
        console.print("[dim]按 Ctrl+C 停止调度...[/dim]")

        async def _run() -> None:
            await scheduler.start()
            try:
                # Block until interrupted
                while scheduler.is_running:
                    await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                pass
            finally:
                await scheduler.stop()

        try:
            asyncio.run(_run())
        except KeyboardInterrupt:
            console.print("\n[yellow]调度已停止[/yellow]")

    except Exception as exc:
        console.print(f"[red]✗ 调度启动失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


@schedule_app.command("status")
def schedule_status(
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """查看调度器状态。"""
    # No persistent state file yet — just report not running
    console.print("[yellow]调度器未运行。使用 `palace schedule start` 启动。[/yellow]")

# ── Persona commands ──────────────────────────────────────────────────

persona_app = typer.Typer(name="persona", help="Persona 多角色管理")
app.add_typer(persona_app)


@persona_app.command("list")
def persona_list(
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """列出所有 persona。"""
    try:
        from memory_palace.config import Config
        from memory_palace.service.persona_manager import PersonaManager

        base = Path(data_dir).expanduser()
        yaml_path = base / "memory_palace.yaml"
        cfg = Config.from_yaml(yaml_path) if yaml_path.exists() else Config()
        mgr = PersonaManager(cfg)

        table = Table(title="Persona 列表")
        table.add_column("名称", style="bold cyan")
        table.add_column("数据目录")
        table.add_column("描述")
        table.add_column("状态")

        for p in mgr.list_personas():
            status = "✓ active" if p.name == cfg.active_persona else ""
            table.add_row(p.name, p.data_dir, p.description, status)

        console.print(table)
    except Exception as exc:
        console.print(f"[red]✗ 获取 persona 列表失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


@persona_app.command("create")
def persona_create(
    name: str = typer.Option(..., help="Persona 名称"),
    dir: str = typer.Option(..., help="数据目录"),
    desc: str = typer.Option("", help="描述"),
    data_dir: str = typer.Option("~/.memory_palace", help="配置所在数据目录"),
) -> None:
    """创建新 persona。"""
    try:
        from memory_palace.config import Config
        from memory_palace.service.persona_manager import PersonaManager

        base = Path(data_dir).expanduser()
        yaml_path = base / "memory_palace.yaml"
        cfg = Config.from_yaml(yaml_path) if yaml_path.exists() else Config()
        mgr = PersonaManager(cfg, config_path=yaml_path)

        persona = mgr.create(name, dir, desc)
        console.print(
            f"[green]✓[/green] Persona 已创建  "
            f"name={persona.name}  data_dir={persona.data_dir}"
        )
    except ValueError as exc:
        console.print(f"[red]✗ 创建失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]✗ 创建失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


@persona_app.command("switch")
def persona_switch(
    name: str = typer.Option(..., help="要切换到的 persona 名称"),
    data_dir: str = typer.Option("~/.memory_palace", help="配置所在数据目录"),
) -> None:
    """切换 active persona。"""
    try:
        from memory_palace.config import Config
        from memory_palace.service.persona_manager import PersonaManager

        base = Path(data_dir).expanduser()
        yaml_path = base / "memory_palace.yaml"
        cfg = Config.from_yaml(yaml_path) if yaml_path.exists() else Config()
        mgr = PersonaManager(cfg, config_path=yaml_path)

        persona = mgr.switch(name)
        console.print(f"[green]✓[/green] 已切换到 persona: {persona.name}")
    except ValueError as exc:
        console.print(f"[red]✗ 切换失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]✗ 切换失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


@persona_app.command("delete")
def persona_delete(
    name: str = typer.Option(..., help="要删除的 persona 名称"),
    data_dir: str = typer.Option("~/.memory_palace", help="配置所在数据目录"),
) -> None:
    """删除 persona（不能删除 default 或 active）。"""
    try:
        from memory_palace.config import Config
        from memory_palace.service.persona_manager import PersonaManager

        base = Path(data_dir).expanduser()
        yaml_path = base / "memory_palace.yaml"
        cfg = Config.from_yaml(yaml_path) if yaml_path.exists() else Config()
        mgr = PersonaManager(cfg, config_path=yaml_path)

        mgr.delete(name)
        console.print(f"[green]✓[/green] Persona '{name}' 已删除")
    except ValueError as exc:
        console.print(f"[red]✗ 删除失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        console.print(f"[red]✗ 删除失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc


# ── MCP Server command ────────────────────────────────────────────────


@app.command()
def serve(
    transport: str = typer.Option("stdio", help="传输协议: stdio | http"),
    host: str = typer.Option("localhost", help="HTTP 主机"),
    port: int = typer.Option(8765, help="HTTP 端口"),
    data_dir: str = typer.Option("~/.memory_palace", help="数据目录"),
) -> None:
    """启动 Memory Palace MCP Server."""
    try:
        path = _resolve_data_dir(data_dir)

        from memory_palace.integration.mcp_context import MCPServiceManager
        from memory_palace.integration.mcp_server import mcp, run_stdio_server

        MCPServiceManager.configure(path)

        if transport == "http":
            console.print(
                f"[green]✓[/green] MCP Server 启动  transport={transport}  data_dir={path}"
            )
            mcp.run(transport="streamable-http", host=host, port=port)
        else:
            run_stdio_server()
    except Exception as exc:
        console.print(f"[red]✗ MCP Server 启动失败：{exc}[/red]")
        raise typer.Exit(code=1) from exc
