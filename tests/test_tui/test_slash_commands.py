"""Tests for slash command dispatch logic (unit tests, no TUI needed)."""

import pytest

from roxy.config.loader import Config
from roxy.tui.screens.chat import ChatScreen, HELP_TEXT


class _FakeEngine:
    """Minimal fake for testing slash commands that don't need the engine."""
    session_id = "test12345678"
    message_count = 0

    class provider:
        @staticmethod
        def resolve_model(override=None):
            return override or "deepseek/deepseek-chat"


class TestSlashCommands:
    """Test slash command dispatch returns correct strings."""

    @pytest.fixture
    def screen(self) -> ChatScreen:
        cfg = Config()
        cfg.load()
        return ChatScreen.__new__(ChatScreen)

    def _setup_engine(self, screen: ChatScreen):
        screen._engine = _FakeEngine()
        screen._session = type("s", (), {"id": "test12345678", "message_count": 0})()
        screen.config = Config()
        screen.model_override = None

    def test_help(self, screen: ChatScreen):
        result = screen._handle_slash("/help")
        assert "Slash Commands" in result
        assert "/doctor" in result
        assert "/model" in result

    def test_model_show(self, screen: ChatScreen):
        self._setup_engine(screen)
        result = screen._handle_slash("/model")
        assert "deepseek/deepseek-chat" in result

    def test_model_switch(self, screen: ChatScreen):
        self._setup_engine(screen)
        result = screen._handle_slash("/model openai/gpt-4.1")
        assert "openai/gpt-4.1" in result
        assert screen.model_override == "openai/gpt-4.1"

    def test_sessions_empty(self, screen: ChatScreen):
        # Create screen with fake engine pointing at isolated sessions dir
        screen._engine = _FakeEngine()
        screen._session = type("s", (), {"id": "test12345678", "message_count": 0})()
        result = screen._handle_slash("/sessions")
        assert "No saved sessions" in result or "Recent Sessions" in result

    def test_doctor(self, screen: ChatScreen):
        self._setup_engine(screen)
        result = screen._handle_slash("/doctor")
        assert "Roxy Status" in result

    def test_clear(self, screen: ChatScreen):
        """Clear needs a mounted Textual DOM — just verify the handler exists."""
        assert hasattr(screen, "_cmd_clear")

    def test_resume_no_arg(self, screen: ChatScreen):
        result = screen._handle_slash("/resume")
        assert "Usage" in result

    def test_resume_not_found(self, screen: ChatScreen):
        result = screen._handle_slash("/resume nonexis7")
        assert "not found" in result.lower()

    def test_unknown_command(self, screen: ChatScreen):
        result = screen._handle_slash("/foobar")
        assert "Unknown command" in result

    def test_help_text_has_all_commands(self, screen: ChatScreen):
        assert "/help" in HELP_TEXT
        assert "/clear" in HELP_TEXT
        assert "/doctor" in HELP_TEXT
        assert "/model" in HELP_TEXT
        assert "/sessions" in HELP_TEXT
        assert "/resume" in HELP_TEXT
        assert "/exit" in HELP_TEXT
