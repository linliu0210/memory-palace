"""CoreStore — JSON flat file storage for Core Memory.

One block = one JSON file in {data_dir}/core/{block_name}.json.
Max 2KB (2048 bytes) per block. Atomic write via tmp+rename.

Ref: SPEC v2.0 §4.1 S-8
"""

import json
import os
import tempfile
from pathlib import Path

from memory_palace.models.memory import MemoryItem

# Reason: 2KB budget per SPEC §4.1 S-8
BUDGET_LIMIT = 2048
# Reason: 80% threshold for budget warning
BUDGET_WARN_THRESHOLD = 0.8


class CoreStore:
    """Core Memory store: always-loaded short-term memory.

    Stores MemoryItems as JSON flat files, one file per block.
    Standard blocks: persona, user, preferences.
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialize CoreStore.

        Args:
            data_dir: Root data directory. Core files stored in {data_dir}/core/.
        """
        self._core_dir = data_dir / "core"
        self._core_dir.mkdir(parents=True, exist_ok=True)

    def _block_path(self, block: str) -> Path:
        """Return the file path for a given block name."""
        return self._core_dir / f"{block}.json"

    def save(self, block: str, items: list[MemoryItem]) -> None:
        """Save items to a block, replacing any existing content.

        Uses atomic write (write-to-tmp + os.rename) to prevent corruption.

        Args:
            block: Block name (e.g. 'persona', 'user', 'preferences').
            items: List of MemoryItems to save.
        """
        path = self._block_path(block)
        # Reason: model_dump_json() for proper datetime serialization (Pydantic v2)
        data = json.loads("[" + ",".join(item.model_dump_json() for item in items) + "]")
        content = json.dumps(data, ensure_ascii=False, indent=2)

        # Atomic write: write to temp file then rename
        fd, tmp_path = tempfile.mkstemp(dir=str(self._core_dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, str(path))
        except BaseException:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def load(self, block: str) -> list[MemoryItem]:
        """Load items from a block.

        Args:
            block: Block name to load.

        Returns:
            List of MemoryItems, or empty list if block doesn't exist.
        """
        path = self._block_path(block)
        if not path.exists():
            return []
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
        # Reason: model_validate() for dict→Pydantic (not model_validate_json which takes str)
        return [MemoryItem.model_validate(item) for item in data]

    def delete(self, block: str, memory_id: str) -> None:
        """Delete a single item from a block by its ID.

        Args:
            block: Block name.
            memory_id: ID of the MemoryItem to remove.
        """
        items = self.load(block)
        remaining = [item for item in items if item.id != memory_id]
        self.save(block, remaining)

    def list_blocks(self) -> list[str]:
        """List all existing block names.

        Returns:
            Sorted list of block names (without .json extension).
        """
        if not self._core_dir.exists():
            return []
        return sorted(p.stem for p in self._core_dir.glob("*.json"))

    def budget_check(self, block: str) -> dict:
        """Check the current size of a block against the 2KB budget.

        Args:
            block: Block name to check.

        Returns:
            Dict with 'size' (bytes), 'limit' (2048), 'warning' (bool).
        """
        path = self._block_path(block)
        size = path.stat().st_size if path.exists() else 0
        return {
            "size": size,
            "limit": BUDGET_LIMIT,
            "warning": size >= BUDGET_LIMIT * BUDGET_WARN_THRESHOLD,
        }

    def get_all_text(self) -> str:
        """Concatenate all block texts into a single string.

        Returns:
            All MemoryItem contents from all blocks, joined by newlines.
        """
        texts: list[str] = []
        for block_name in self.list_blocks():
            items = self.load(block_name)
            for item in items:
                texts.append(item.content)
        return "\n".join(texts)
