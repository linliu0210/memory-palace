"""BatchImporter / BatchExporter — Batch Import/Export for Markdown and JSONL.

Ref: TASK_R21
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from memory_palace.models.memory import MemoryItem, MemoryStatus
from memory_palace.service.memory_service import MemoryService


@dataclass
class ImportReport:
    total_found: int
    imported: int
    skipped: int
    errors: list[str]
    duration_seconds: float


@dataclass
class ExportReport:
    total_exported: int
    output_path: str
    duration_seconds: float


def _content_hash(content: str) -> str:
    """SHA-256 hash of stripped content for dedup."""
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


class BatchImporter:
    """Import memories from files."""

    def __init__(self, memory_service: MemoryService) -> None:
        self._svc = memory_service

    def _existing_hashes(self) -> set[str]:
        """Collect content hashes from all existing memories."""
        hashes: set[str] = set()
        # Core
        for block in self._svc._core_store.list_blocks():
            for item in self._svc._core_store.load(block):
                if item.status == MemoryStatus.ACTIVE:
                    hashes.add(_content_hash(item.content))
        # Recall
        items = self._svc._recall_store.get_recent(100_000)
        for item in items:
            hashes.add(_content_hash(item.content))
        return hashes

    async def import_markdown(self, path: Path) -> ImportReport:
        """导入 Markdown 文件.

        每个 ## heading 视为一条记忆。
        YAML frontmatter (如有) 解析为 importance, room, tags。
        """
        start = time.monotonic()
        errors: list[str] = []

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        text = path.read_text(encoding="utf-8")

        # Parse optional YAML frontmatter
        global_importance: float | None = None
        global_room: str | None = None
        global_tags: list[str] | None = None

        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if fm_match:
            fm_text = fm_match.group(1)
            text = text[fm_match.end():]
            # Simple key: value parsing (no YAML lib)
            for line in fm_text.splitlines():
                line = line.strip()
                if line.startswith("importance:"):
                    try:
                        global_importance = float(line.split(":", 1)[1].strip())
                    except ValueError:
                        errors.append(f"Invalid importance in frontmatter: {line}")
                elif line.startswith("room:"):
                    global_room = line.split(":", 1)[1].strip()
                elif line.startswith("tags:"):
                    raw = line.split(":", 1)[1].strip()
                    # Support both [a, b] and a, b
                    raw = raw.strip("[]")
                    global_tags = [t.strip() for t in raw.split(",") if t.strip()]

        # Split by ## headings
        sections = re.split(r"^##\s+", text, flags=re.MULTILINE)
        # First element is content before the first ## (skip if empty)
        entries: list[str] = []
        for section in sections[1:]:  # skip preamble
            content = section.strip()
            if content:
                # Remove the heading line itself, keep body
                lines = content.split("\n", 1)
                body = lines[1].strip() if len(lines) > 1 else ""
                if body:
                    entries.append(body)

        total_found = len(entries)
        existing = self._existing_hashes()
        imported = 0
        skipped = 0

        for entry in entries:
            h = _content_hash(entry)
            if h in existing:
                skipped += 1
                continue
            try:
                self._svc.save(
                    content=entry,
                    importance=global_importance if global_importance is not None else 0.5,
                    room=global_room if global_room is not None else "general",
                    tags=list(global_tags) if global_tags else [],
                )
                existing.add(h)
                imported += 1
            except Exception as exc:
                errors.append(f"Failed to import entry: {exc}")

        duration = time.monotonic() - start
        return ImportReport(
            total_found=total_found,
            imported=imported,
            skipped=skipped,
            errors=errors,
            duration_seconds=round(duration, 3),
        )

    async def import_jsonl(self, path: Path) -> ImportReport:
        """导入 JSONL 文件.

        每行 JSON: {"content": "...", "importance": 0.5, "room": "...", "tags": []}
        """
        start = time.monotonic()
        errors: list[str] = []

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        lines = path.read_text(encoding="utf-8").strip().splitlines()
        total_found = len(lines)
        existing = self._existing_hashes()
        imported = 0
        skipped = 0

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"Line {i + 1}: invalid JSON — {exc}")
                continue

            content = data.get("content", "").strip()
            if not content:
                errors.append(f"Line {i + 1}: missing or empty content")
                continue

            h = _content_hash(content)
            if h in existing:
                skipped += 1
                continue

            try:
                self._svc.save(
                    content=content,
                    importance=data.get("importance", 0.5),
                    room=data.get("room", "general"),
                    tags=data.get("tags", []),
                )
                existing.add(h)
                imported += 1
            except Exception as exc:
                errors.append(f"Line {i + 1}: save failed — {exc}")

        duration = time.monotonic() - start
        return ImportReport(
            total_found=total_found,
            imported=imported,
            skipped=skipped,
            errors=errors,
            duration_seconds=round(duration, 3),
        )


class BatchExporter:
    """Export memories to files."""

    def __init__(self, memory_service: MemoryService) -> None:
        self._svc = memory_service

    def _collect_all(self) -> list[MemoryItem]:
        """Collect all active memories from Core + Recall."""
        items: list[MemoryItem] = []
        for block in self._svc._core_store.list_blocks():
            for item in self._svc._core_store.load(block):
                if item.status == MemoryStatus.ACTIVE:
                    items.append(item)
        recall = self._svc._recall_store.get_recent(100_000)
        items.extend(recall)
        return items

    def export_markdown(self, output_dir: Path) -> ExportReport:
        """每个 room 导出为一个 .md 文件.

        文件名: {room}.md
        格式: # {room}\\n\\n## {id[:8]}\\n{content}\\n---\\n
        """
        start = time.monotonic()
        output_dir.mkdir(parents=True, exist_ok=True)

        items = self._collect_all()

        # Group by room
        rooms: dict[str, list[MemoryItem]] = {}
        for item in items:
            rooms.setdefault(item.room, []).append(item)

        total = 0
        for room_name, room_items in rooms.items():
            lines = [f"# {room_name}\n"]
            for item in room_items:
                lines.append(f"\n## {item.id[:8]}\n{item.content}\n---\n")
                total += 1
            file_path = output_dir / f"{room_name}.md"
            file_path.write_text("".join(lines), encoding="utf-8")

        duration = time.monotonic() - start
        return ExportReport(
            total_exported=total,
            output_path=str(output_dir),
            duration_seconds=round(duration, 3),
        )

    def export_jsonl(self, output_path: Path) -> ExportReport:
        """全量导出为单个 JSONL 文件.

        每行: item.model_dump(mode='json')
        """
        start = time.monotonic()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        items = self._collect_all()
        total = 0

        with output_path.open("w", encoding="utf-8") as f:
            for item in items:
                data = item.model_dump(mode="json")
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
                total += 1

        duration = time.monotonic() - start
        return ExportReport(
            total_exported=total,
            output_path=str(output_path),
            duration_seconds=round(duration, 3),
        )
