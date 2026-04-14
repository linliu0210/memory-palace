"""PersonaManager — Multi-persona profile management tests.

TDD RED → GREEN for R22: Multi-persona support.
Tests cover CRUD, isolation, persistence, and constraint enforcement.

Ref: TASK_R22
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from memory_palace.config import Config
from memory_palace.service.persona_manager import PersonaManager

# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def persona_config_path(tmp_path: Path) -> Path:
    """Create a minimal YAML config for persona testing."""
    yaml_path = tmp_path / "memory_palace.yaml"
    data = {
        "memory_palace": {
            "personas": [
                {
                    "name": "default",
                    "data_dir": str(tmp_path / "default_data"),
                    "description": "默认 persona",
                },
            ],
            "active_persona": "default",
        }
    }
    yaml_path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return yaml_path


@pytest.fixture
def manager(persona_config_path: Path, tmp_path: Path) -> PersonaManager:
    """Build a PersonaManager with tmp-based config."""
    cfg = Config.from_yaml(persona_config_path)
    return PersonaManager(cfg, config_path=persona_config_path)


# ── Tests ─────────────────────────────────────────────────────


class TestListPersonas:
    """list_personas() returns all configured personas."""

    def test_list_personas_default(self, manager: PersonaManager) -> None:
        """Default config has exactly one 'default' persona."""
        personas = manager.list_personas()
        assert len(personas) == 1
        assert personas[0].name == "default"

    def test_list_after_create(self, manager: PersonaManager, tmp_path: Path) -> None:
        """After creating a persona, list includes it."""
        manager.create("work", str(tmp_path / "work_data"), "工作记忆")
        personas = manager.list_personas()
        names = [p.name for p in personas]
        assert "default" in names
        assert "work" in names
        assert len(personas) == 2


class TestCreatePersona:
    """create() adds a new persona profile."""

    def test_create_persona(self, manager: PersonaManager, tmp_path: Path) -> None:
        """Creating a new persona returns it with correct fields."""
        result = manager.create("research", str(tmp_path / "research_data"), "学术调研")
        assert result.name == "research"
        assert result.description == "学术调研"
        assert "research_data" in result.data_dir

    def test_duplicate_name_fails(self, manager: PersonaManager, tmp_path: Path) -> None:
        """Creating a persona with an existing name raises ValueError."""
        manager.create("work", str(tmp_path / "work_data"))
        with pytest.raises(ValueError, match="already exists"):
            manager.create("work", str(tmp_path / "work_data2"))

    def test_create_ensures_data_dir(self, manager: PersonaManager, tmp_path: Path) -> None:
        """Creating a persona creates the data directory structure."""
        data_dir = tmp_path / "new_persona_data"
        manager.create("new", str(data_dir))
        assert data_dir.exists()
        assert (data_dir / "core").exists()


class TestSwitchPersona:
    """switch() changes the active persona."""

    def test_switch_persona(self, manager: PersonaManager, tmp_path: Path) -> None:
        """Switching updates active persona."""
        manager.create("work", str(tmp_path / "work_data"))
        result = manager.switch("work")
        assert result.name == "work"
        assert manager.get_active().name == "work"

    def test_switch_nonexistent_fails(self, manager: PersonaManager) -> None:
        """Switching to a non-existent persona raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            manager.switch("nonexistent")


class TestDeletePersona:
    """delete() removes a persona profile."""

    def test_delete_persona(self, manager: PersonaManager, tmp_path: Path) -> None:
        """Deleting a non-active persona succeeds."""
        manager.create("temp", str(tmp_path / "temp_data"))
        assert manager.delete("temp") is True
        names = [p.name for p in manager.list_personas()]
        assert "temp" not in names

    def test_delete_active_persona_fails(
        self, manager: PersonaManager, tmp_path: Path
    ) -> None:
        """Cannot delete the currently active persona."""
        manager.create("work", str(tmp_path / "work_data"))
        manager.switch("work")
        with pytest.raises(ValueError, match="active"):
            manager.delete("work")

    def test_delete_default_persona_fails(self, manager: PersonaManager) -> None:
        """Cannot delete the 'default' persona."""
        with pytest.raises(ValueError, match="default"):
            manager.delete("default")


class TestBuildService:
    """build_service() creates a MemoryService for a persona."""

    def test_build_service_default(self, manager: PersonaManager) -> None:
        """Build service for default persona succeeds."""
        svc = manager.build_service()
        assert svc is not None
        # Service should use the default persona's data_dir
        assert svc._data_dir.exists()

    def test_build_service_custom(self, manager: PersonaManager, tmp_path: Path) -> None:
        """Build service for a custom persona uses its data_dir."""
        custom_dir = tmp_path / "custom_data"
        manager.create("custom", str(custom_dir))
        svc = manager.build_service("custom")
        assert svc._data_dir == custom_dir


class TestDataIsolation:
    """Two personas do not share data."""

    def test_persona_data_isolation(
        self, manager: PersonaManager, tmp_path: Path
    ) -> None:
        """Saving in one persona is invisible in another."""
        dir_a = tmp_path / "persona_a"
        dir_b = tmp_path / "persona_b"
        manager.create("alice", str(dir_a))
        manager.create("bob", str(dir_b))

        svc_a = manager.build_service("alice")
        svc_b = manager.build_service("bob")

        # Save in persona A
        svc_a.save("Alice private memo", importance=0.5, room="general")

        # Search in persona B — should find nothing
        results_b = svc_b.search_sync("Alice")
        assert len(results_b) == 0

        # Search in persona A — should find it
        results_a = svc_a.search_sync("Alice")
        assert len(results_a) == 1


class TestConfigPersistence:
    """Config changes are persisted to YAML."""

    def test_persona_config_persistence(
        self, persona_config_path: Path, tmp_path: Path
    ) -> None:
        """Creating a persona persists it; reloading config finds it."""
        cfg = Config.from_yaml(persona_config_path)
        mgr = PersonaManager(cfg, config_path=persona_config_path)
        mgr.create("persistent", str(tmp_path / "persist_data"), "持久化测试")

        # Reload from YAML
        cfg2 = Config.from_yaml(persona_config_path)
        mgr2 = PersonaManager(cfg2, config_path=persona_config_path)
        names = [p.name for p in mgr2.list_personas()]
        assert "persistent" in names

    def test_switch_persists_active(
        self, persona_config_path: Path, tmp_path: Path
    ) -> None:
        """Switching persona persists the active_persona field."""
        cfg = Config.from_yaml(persona_config_path)
        mgr = PersonaManager(cfg, config_path=persona_config_path)
        mgr.create("work", str(tmp_path / "work_data"))
        mgr.switch("work")

        # Reload
        cfg2 = Config.from_yaml(persona_config_path)
        assert cfg2.active_persona == "work"
