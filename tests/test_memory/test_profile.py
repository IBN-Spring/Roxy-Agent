"""Tests for UserProfile — config-driven system context."""

from roxy.config.loader import Config
from roxy.memory.profile import UserProfile


class TestUserProfile:
    def test_empty_profile_returns_empty(self, config: Config):
        config.load()
        profile = UserProfile(config)
        assert profile.to_system_context() == ""

    def test_name_only(self, config: Config):
        config.load()
        config.set("user.name", "Alice")
        profile = UserProfile(config)
        ctx = profile.to_system_context()
        assert "Alice" in ctx
        assert "User Profile" in ctx

    def test_full_profile(self, populated_config: Config):
        profile = UserProfile(populated_config)
        ctx = profile.to_system_context()
        assert "TestUser" in ctx
        assert "Researcher" in ctx
        assert "bioinformatics" in ctx
        assert "protein folding" in ctx
        assert "drug design" in ctx
        assert ctx.startswith("## User Profile")
