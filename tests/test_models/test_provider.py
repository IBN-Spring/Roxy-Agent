"""Tests for ModelProvider — resolve model, provider config extraction."""

from roxy.config.loader import Config
from roxy.models.provider import ModelProvider


class TestResolveModel:
    def test_uses_config_default(self, config: Config):
        config.load()
        config.set("models.default", "anthropic/claude-sonnet")
        provider = ModelProvider(config)
        assert provider.resolve_model() == "anthropic/claude-sonnet"

    def test_override_wins(self, config: Config):
        config.load()
        config.set("models.default", "anthropic/claude-sonnet")
        provider = ModelProvider(config)
        assert provider.resolve_model("openai/gpt-4.1") == "openai/gpt-4.1"

    def test_falls_back_to_default(self, config: Config):
        config.load()
        provider = ModelProvider(config)
        assert provider.resolve_model() == "openai/gpt-4.1-mini"


class TestProviderConfig:
    def test_extracts_api_key(self, populated_config: Config):
        provider = ModelProvider(populated_config)
        cfg = provider._get_provider_config("openai/gpt-4.1-mini")
        assert cfg["api_key"] == "sk-test1234567890abcdef"

    def test_unknown_provider_returns_empty(self, config: Config):
        config.load()
        provider = ModelProvider(config)
        cfg = provider._get_provider_config("unknown/model")
        assert cfg["api_key"] == ""
