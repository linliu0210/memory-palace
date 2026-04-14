"""PersonaManager — Multi-persona profile management.

Manages multiple persona profiles, each with its own isolated data directory.
Shared config (LLM, embedding, scoring) applies across all personas.

Layer: Service (imports Config from Foundation, builds MemoryService).

Ref: TASK_R22
"""

from __future__ import annotations

from pathlib import Path

import structlog
import yaml

from memory_palace.config import Config, PersonaConfig

logger = structlog.get_logger(__name__)


class PersonaManager:
    """Manages multiple persona profiles.

    Each persona has:
    - Independent data_dir (Core, Recall, Archival, Audit all separate)
    - Shared config (LLM, embedding, scoring settings)

    Args:
        config: The loaded Config with personas list and active_persona.
        config_path: Path to memory_palace.yaml for persistence.
                     If None, changes are in-memory only.
    """

    def __init__(self, config: Config, config_path: Path | None = None) -> None:
        self._config = config
        self._config_path = config_path

    def list_personas(self) -> list[PersonaConfig]:
        """Return all configured persona profiles.

        Returns:
            List of PersonaConfig instances.
        """
        return list(self._config.personas)

    def get_active(self) -> PersonaConfig:
        """Return the currently active persona.

        Returns:
            The active PersonaConfig.

        Raises:
            ValueError: If active_persona references a non-existent name.
        """
        for p in self._config.personas:
            if p.name == self._config.active_persona:
                return p
        raise ValueError(
            f"Active persona '{self._config.active_persona}' not found in config"
        )

    def switch(self, name: str) -> PersonaConfig:
        """Switch the active persona.

        Args:
            name: Name of the persona to activate.

        Returns:
            The newly active PersonaConfig.

        Raises:
            ValueError: If persona name not found.
        """
        persona = self._find_persona(name)
        if persona is None:
            raise ValueError(f"Persona '{name}' not found")

        self._config.active_persona = name
        self._persist_config()

        logger.info("Persona switched", active=name)
        return persona

    def create(
        self, name: str, data_dir: str, description: str = ""
    ) -> PersonaConfig:
        """Create a new persona profile.

        Creates the data directory structure (including core/ subdir)
        and persists the updated config to YAML.

        Args:
            name: Unique persona name.
            data_dir: Path for the persona's data directory (~ expansion supported).
            description: Optional human-readable description.

        Returns:
            The newly created PersonaConfig.

        Raises:
            ValueError: If a persona with this name already exists.
        """
        if self._find_persona(name) is not None:
            raise ValueError(f"Persona '{name}' already exists")

        persona = PersonaConfig(name=name, data_dir=data_dir, description=description)

        # Ensure data directory structure exists
        resolved = Path(data_dir).expanduser()
        resolved.mkdir(parents=True, exist_ok=True)
        (resolved / "core").mkdir(exist_ok=True)

        # Add to config and persist
        self._config.personas.append(persona)
        self._persist_config()

        logger.info("Persona created", name=name, data_dir=data_dir)
        return persona

    def delete(self, name: str) -> bool:
        """Delete a persona profile.

        Cannot delete 'default' or the currently active persona.

        Args:
            name: Name of the persona to delete.

        Returns:
            True if deleted successfully.

        Raises:
            ValueError: If trying to delete 'default' or active persona,
                       or if persona not found.
        """
        if name == "default":
            raise ValueError("Cannot delete the 'default' persona")

        if name == self._config.active_persona:
            raise ValueError(
                f"Cannot delete active persona '{name}'. Switch first."
            )

        persona = self._find_persona(name)
        if persona is None:
            raise ValueError(f"Persona '{name}' not found")

        self._config.personas = [
            p for p in self._config.personas if p.name != name
        ]
        self._persist_config()

        logger.info("Persona deleted", name=name)
        return True

    def build_service(self, persona_name: str | None = None):
        """Build a MemoryService for the given (or active) persona.

        Args:
            persona_name: Name of the persona. Uses active if None.

        Returns:
            MemoryService instance with the persona's data_dir.

        Raises:
            ValueError: If persona not found.
        """
        from memory_palace.service.memory_service import MemoryService

        if persona_name is None:
            persona = self.get_active()
        else:
            persona = self._find_persona(persona_name)
            if persona is None:
                raise ValueError(f"Persona '{persona_name}' not found")

        # Resolve path and ensure structure
        data_dir = Path(persona.data_dir).expanduser()
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "core").mkdir(exist_ok=True)

        return MemoryService(data_dir)

    def _find_persona(self, name: str) -> PersonaConfig | None:
        """Find a persona by name.

        Args:
            name: Persona name to look up.

        Returns:
            PersonaConfig if found, None otherwise.
        """
        for p in self._config.personas:
            if p.name == name:
                return p
        return None

    def _persist_config(self) -> None:
        """Write current persona config back to YAML.

        Preserves existing YAML structure, only updating the
        'personas' and 'active_persona' keys under 'memory_palace:'.
        Does nothing if no config_path was provided.
        """
        if self._config_path is None:
            return

        # Read existing YAML to preserve non-persona fields
        if self._config_path.exists():
            with open(self._config_path, encoding="utf-8") as fh:
                existing = yaml.safe_load(fh) or {}
        else:
            existing = {}

        root = existing.get("memory_palace", {})

        # Update persona fields
        root["personas"] = [
            {"name": p.name, "data_dir": p.data_dir, "description": p.description}
            for p in self._config.personas
        ]
        root["active_persona"] = self._config.active_persona

        existing["memory_palace"] = root

        with open(self._config_path, "w", encoding="utf-8") as fh:
            yaml.dump(existing, fh, allow_unicode=True, default_flow_style=False)

        logger.debug("Config persisted", path=str(self._config_path))
