"""
Round 1: Foundation — Config Tests

IMMUTABLE SPEC: These tests define the Config contract.
Ref: SPEC v2.0 §4.1 S-2, §8.2

Config uses Pydantic Settings to load from .env/YAML.
Provider API keys are resolved from environment variables
following the pi-mono pattern.
"""

import pytest


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
        pytest.skip("RED: Config not implemented")

    def test_default_rooms_include_five_standard(self):
        """Default rooms: general, preferences, projects, people, skills."""
        pytest.skip("RED: Config not implemented")

    def test_default_scoring_weights(self):
        """v0.1 weights: recency=0.25, importance=0.25, relevance=0.50."""
        pytest.skip("RED: Config not implemented")

    def test_default_curator_trigger_values(self):
        """timer_hours=24, session_count=20, cooldown_hours=1."""
        pytest.skip("RED: Config not implemented")


class TestConfigLoading:
    """Config can be loaded from env vars and YAML files."""

    def test_loads_from_env_vars(self, monkeypatch):
        """Setting MP_LLM__PROVIDER env var should override default."""
        pytest.skip("RED: Config not implemented")

    def test_loads_from_yaml_file(self, tmp_path):
        """Config.from_yaml(path) should parse and apply settings."""
        pytest.skip("RED: Config not implemented")

    def test_env_vars_override_yaml(self, monkeypatch, tmp_path):
        """Env vars take precedence over YAML values."""
        pytest.skip("RED: Config not implemented")


class TestProviderKeyResolution:
    """API key resolution from env vars (pi-mono pattern)."""

    def test_resolves_openai_key(self, monkeypatch):
        """provider='openai' → reads OPENAI_API_KEY."""
        pytest.skip("RED: Config not implemented")

    def test_resolves_deepseek_key(self, monkeypatch):
        """provider='deepseek' → reads DEEPSEEK_API_KEY."""
        pytest.skip("RED: Config not implemented")

    def test_local_provider_needs_no_key(self):
        """provider='local' → returns None, no error."""
        pytest.skip("RED: Config not implemented")

    def test_unknown_provider_uses_convention(self, monkeypatch):
        """provider='foo' → tries FOO_API_KEY."""
        pytest.skip("RED: Config not implemented")
