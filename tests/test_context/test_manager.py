"""Tests for ContextManager — system prompt assembly."""

from roxy.config.loader import Config
from roxy.context.manager import ContextManager


class TestContextManager:
    def test_base_prompt_always_present(self, config: Config):
        config.load()
        cm = ContextManager(config)
        prompt = cm.build_system_prompt()
        assert "Roxy" in prompt
        assert "research assistant" in prompt

    def test_includes_profile_when_set(self, populated_config: Config):
        cm = ContextManager(populated_config)
        prompt = cm.build_system_prompt()
        assert "TestUser" in prompt

    def test_no_profile_when_empty(self, config: Config):
        config.load()
        cm = ContextManager(config)
        prompt = cm.build_system_prompt()
        assert "TestUser" not in prompt
        assert "User Profile" not in prompt
