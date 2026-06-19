"""Tests for ModelProvider — resolve model, provider config extraction, error handling."""

import pytest

from roxy.config.loader import Config
from roxy.models.provider import ModelProvider, ProviderError


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


class TestProviderError:
    """ProviderError is raised (not yielded) so callers can handle it cleanly."""

    @pytest.mark.asyncio
    async def test_stream_raises_on_import_error(self, config: Config):
        """When litellm is not importable, stream() raises ProviderError, not yielding text."""
        config.load()
        provider = ModelProvider(config)

        # Simulate missing litellm by blocking the import
        import builtins
        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "litellm":
                raise ImportError("No module named 'litellm'")
            return original_import(name, *args, **kwargs)

        builtins.__import__ = fake_import
        try:
            with pytest.raises(ProviderError) as exc_info:
                async for _ in provider.stream("hello"):
                    pass
            assert exc_info.value.reason == "not_installed"
            assert "litellm" in exc_info.value.message
        finally:
            builtins.__import__ = original_import

    def test_provider_error_str(self):
        err = ProviderError("test message", reason="timeout")
        assert str(err) == "test message"
        assert err.reason == "timeout"
