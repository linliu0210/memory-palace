"""
Round 1: Foundation — Config Tests

IMMUTABLE SPEC: These tests define the Config contract.
Ref: SPEC v2.0 §4.1 S-2, §8.2

Config uses Pydantic Settings to load from .env/YAML.
Provider API keys are resolved from environment variables
following the pi-mono pattern.
"""

from memory_palace.config import Config
from memory_palace.foundation.llm import get_api_key


class TestConfigDefaults:
    """Config should have sane defaults even with no env/file."""

    def test_default_values_are_sane(self):
        """Config() with no input should produce valid defaults:
        - llm.provider = "openai"
        - llm.model_id = "gpt-4o-mini"
        - storage.base_dir = "./data"
        - core.max_bytes = 2048
        - scoring.weights sum to ~1.0
        """
        cfg = Config()
        assert cfg.llm.provider == "openai"
        assert cfg.llm.model_id == "gpt-4o-mini"
        assert cfg.storage.base_dir == "./data"
        assert cfg.core.max_bytes == 2048
        assert (
            abs(cfg.scoring.recency + cfg.scoring.importance + cfg.scoring.relevance - 1.0) < 0.01
        )

    def test_default_rooms_include_five_standard(self):
        """Default rooms: general, preferences, projects, people, skills."""
        cfg = Config()
        room_names = [r.name for r in cfg.rooms]
        assert room_names == ["general", "preferences", "projects", "people", "skills"]

    def test_default_scoring_weights(self):
        """v0.1 weights: recency=0.25, importance=0.25, relevance=0.50."""
        cfg = Config()
        assert cfg.scoring.recency == 0.25
        assert cfg.scoring.importance == 0.25
        assert cfg.scoring.relevance == 0.50

    def test_default_curator_trigger_values(self):
        """timer_hours=24, session_count=20, cooldown_hours=1."""
        cfg = Config()
        assert cfg.curator.trigger.timer_hours == 24
        assert cfg.curator.trigger.session_count == 20
        assert cfg.curator.trigger.cooldown_hours == 1


class TestConfigLoading:
    """Config can be loaded from env vars and YAML files."""

    def test_loads_from_env_vars(self, monkeypatch):
        """Setting MP_LLM__PROVIDER env var should override default."""
        monkeypatch.setenv("MP_LLM__PROVIDER", "deepseek")
        cfg = Config()
        assert cfg.llm.provider == "deepseek"

    def test_loads_from_yaml_file(self, tmp_path):
        """Config.from_yaml(path) should parse and apply settings."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "memory_palace:\n"
            "  llm:\n"
            "    provider: anthropic\n"
            "    model_id: claude-3\n"
        )
        cfg = Config.from_yaml(yaml_file)
        assert cfg.llm.provider == "anthropic"
        assert cfg.llm.model_id == "claude-3"

    def test_env_vars_override_yaml(self, monkeypatch, tmp_path):
        """Env vars take precedence over YAML values."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "memory_palace:\n"
            "  llm:\n"
            "    provider: anthropic\n"
        )
        monkeypatch.setenv("MP_LLM__PROVIDER", "deepseek")
        cfg = Config.from_yaml(yaml_file)
        assert cfg.llm.provider == "deepseek"


class TestProviderKeyResolution:
    """API key resolution from env vars (pi-mono pattern)."""

    def test_resolves_openai_key(self, monkeypatch):
        """provider='openai' → reads OPENAI_API_KEY."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-123")
        assert get_api_key("openai") == "sk-openai-123"

    def test_resolves_deepseek_key(self, monkeypatch):
        """provider='deepseek' → reads DEEPSEEK_API_KEY."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-456")
        assert get_api_key("deepseek") == "sk-deepseek-456"

    def test_local_provider_needs_no_key(self):
        """provider='local' → returns None, no error."""
        assert get_api_key("local") is None

    def test_unknown_provider_uses_convention(self, monkeypatch):
        """provider='foo' → tries FOO_API_KEY."""
        monkeypatch.setenv("FOO_API_KEY", "sk-foo-789")
        assert get_api_key("foo") == "sk-foo-789"
