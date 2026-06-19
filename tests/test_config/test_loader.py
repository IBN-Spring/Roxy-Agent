"""Tests for Config loader — layered resolution, save/load, priority."""

import os
from pathlib import Path

import yaml

from roxy.config.loader import Config


class TestConfigDefaults:
    """Default values are returned when nothing is set."""

    def test_default_model(self, config: Config):
        config.load()
        assert config.get("models.default") == "openai/gpt-4.1-mini"

    def test_default_user_name(self, config: Config):
        config.load()
        assert config.get("user.name") == ""

    def test_custom_default(self, config: Config):
        config.load()
        assert config.get("nonexistent.key", "fallback") == "fallback"


class TestConfigSetGet:
    """Setting and getting values through the YAML layer."""

    def test_set_get_string(self, config: Config):
        config.load()
        config.set("user.name", "Alice")
        assert config.get("user.name") == "Alice"

    def test_set_get_nested(self, config: Config):
        config.load()
        config.set("models.providers.openai.api_key", "sk-abc")
        assert config.get("models.providers.openai.api_key") == "sk-abc"

    def test_set_get_list(self, config: Config):
        config.load()
        config.set("user.topics", ["AI", "biology"])
        assert config.get("user.topics") == ["AI", "biology"]

    def test_set_get_bool(self, config: Config):
        config.load()
        config.set("monitoring.enabled", True)
        assert config.get("monitoring.enabled") is True


class TestConfigSaveLoad:
    """Config persists correctly to YAML and loads back."""

    def test_save_and_reload(self, tmp_config_path: Path):
        # Write
        cfg1 = Config(path=tmp_config_path)
        cfg1.load()
        cfg1.set("user.name", "Bob")
        cfg1.set("user.topics", ["physics"])
        cfg1.save()

        # Read back
        cfg2 = Config(path=tmp_config_path)
        cfg2.load()
        assert cfg2.get("user.name") == "Bob"
        assert cfg2.get("user.topics") == ["physics"]

    def test_load_empty_file(self, tmp_config_path: Path):
        """Loading a non-existent file should not crash."""
        cfg = Config(path=tmp_config_path)
        cfg.load()
        assert cfg.get("user.name") == ""


class TestConfigPriority:
    """CLI > env > YAML > defaults priority chain."""

    def test_env_overrides_yaml(self, config: Config, monkeypatch):
        config.load()
        config.set("user.name", "YamlName")
        config.save()

        monkeypatch.setenv("ROXY_USER_NAME", "EnvName")
        result = config.get("user.name")
        assert result == "EnvName"

    def test_cli_overrides_env(self, config: Config, monkeypatch):
        config.load()
        config.set("user.name", "YamlName")
        config.save()
        monkeypatch.setenv("ROXY_USER_NAME", "EnvName")
        config.set_cli_override("user.name", "CliName")

        result = config.get("user.name")
        assert result == "CliName"

    def test_default_last(self, config: Config):
        config.load()
        assert config.get("ui.theme") == "dark"  # from DEFAULTS

    def test_env_coerces_list(self, config: Config, monkeypatch):
        config.load()
        monkeypatch.setenv("ROXY_USER_TOPICS", "AI, biology, drug design")
        result = config.get("user.topics")
        assert result == ["AI", "biology", "drug design"]

    def test_env_coerces_bool(self, config: Config, monkeypatch):
        config.load()
        monkeypatch.setenv("ROXY_MONITORING_ENABLED", "true")
        assert config.get("monitoring.enabled") is True

        monkeypatch.setenv("ROXY_MONITORING_ENABLED", "false")
        assert config.get("monitoring.enabled") is False


class TestConfigMasking:
    """Secret values are masked in display output."""

    def test_api_key_masked(self, config: Config):
        config.load()
        config.set("models.providers.openai.api_key", "sk-1234567890abcdefghij")
        result = config.to_dict(mask_secrets=True)
        for key, val in result.items():
            if "api_key" in key.lower():
                assert "1234567890" not in str(val)  # middle is hidden
                assert "sk-123" in str(val) or "****" in str(val)

    def test_token_masked(self, config: Config):
        config.load()
        config.set("models.providers.openai.token", "tokensecret12345")
        result = config.to_dict(mask_secrets=True)
        for key, val in result.items():
            if "token" in key.lower():
                assert "tokensecret12345" not in str(val)


class TestConfigIsConfigured:
    """Feature readiness checks."""

    def test_not_configured_by_default(self, config: Config):
        config.load()
        assert not config.is_configured("user")

    def test_configured_after_user_set(self, config: Config):
        config.load()
        config.set("user.name", "Alice")
        config.save()
        assert config.is_configured("user")

    def test_llm_configured(self, populated_config: Config):
        assert populated_config.is_configured("llm")

    def test_research_needs_domain_and_topics(self, config: Config):
        config.load()
        assert not config.is_configured("research")
        config.set("user.research_domain", "physics")
        config.set("user.topics", ["quantum"])
        assert config.is_configured("research")
