"""Configuration management via Pydantic Settings.

Supports defaults, environment variable overrides (``MP_`` prefix with
``__`` nested delimiter), and YAML file loading.

Ref: SPEC v2.0 §8.2
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource


class LLMConfig(BaseModel):
    """LLM backend selection."""

    provider: str = "openai"
    model_id: str = "gpt-4o-mini"


class StorageConfig(BaseModel):
    """Storage paths."""

    base_dir: str = "./data"


class CoreConfig(BaseModel):
    """Core memory budget."""

    max_bytes: int = 2048


class RoomConfig(BaseModel):
    """A single memory room definition."""

    name: str
    description: str = ""


class ScoringConfig(BaseModel):
    """Three-factor scoring weights (must sum to ~1.0)."""

    recency: float = 0.25
    importance: float = 0.25
    relevance: float = 0.50


class CuratorTrigger(BaseModel):
    """When the Memory Curator should wake up."""

    timer_hours: int = 24
    session_count: int = 20
    cooldown_hours: int = 1


class CuratorConfig(BaseModel):
    """Memory Curator configuration."""

    trigger: CuratorTrigger = CuratorTrigger()
    prune_threshold: float = 0.05


class _YamlSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source that reads from a YAML file.

    Priority is controlled by position in ``settings_customise_sources``.
    """

    def __init__(self, settings_cls: type[BaseSettings], yaml_data: dict[str, Any]):
        super().__init__(settings_cls)
        self._yaml_data = yaml_data

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        val = self._yaml_data.get(field_name)
        return val, field_name, val is not None

    def __call__(self) -> dict[str, Any]:
        return self._yaml_data


class Config(BaseSettings):
    """Memory Palace configuration.

    Loads from environment variables (``MP_`` prefix, ``__`` nesting)
    and optionally from a YAML file via :meth:`from_yaml`.
    """

    model_config = {"env_prefix": "MP_", "env_nested_delimiter": "__"}

    llm: LLMConfig = LLMConfig()
    storage: StorageConfig = StorageConfig()
    core: CoreConfig = CoreConfig()
    rooms: list[RoomConfig] = [
        RoomConfig(name="general", description="未分类通用记忆"),
        RoomConfig(name="preferences", description="用户偏好"),
        RoomConfig(name="projects", description="项目知识"),
        RoomConfig(name="people", description="人物关系"),
        RoomConfig(name="skills", description="技能记忆"),
    ]
    scoring: ScoringConfig = ScoringConfig()
    curator: CuratorConfig = CuratorConfig()

    @classmethod
    def from_yaml(cls, path: Path) -> Config:
        """Load configuration from a YAML file.

        Priority (high → low): env vars > YAML > defaults.
        """
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

        # SPEC §8.2: YAML uses 'memory_palace' as root key.
        # Support both wrapped and unwrapped formats for flexibility.
        yaml_data = raw.get("memory_palace", raw)

        return _ConfigFromYaml(yaml_data)


def _ConfigFromYaml(yaml_data: dict[str, Any]) -> Config:
    """Build a Config where YAML sits between env vars and defaults.

    Pydantic Settings source priority (first wins):
      init > env > yaml_source > secrets > defaults
    We inject YAML as init kwargs — but that gives them highest priority.

    Instead, we create a thin subclass that overrides source ordering
    to place YAML *below* env vars.
    """

    class _WithYaml(Config):
        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            dotenv_settings: PydanticBaseSettingsSource,
            file_secret_settings: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            return (
                init_settings,
                env_settings,
                _YamlSettingsSource(settings_cls, yaml_data),
                dotenv_settings,
                file_secret_settings,
            )

    return _WithYaml()
